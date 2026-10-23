"""Against the morning book line: every model, every filter, tuned on one half of
the lined games and checked on the other.

  cd nba_pipeline && python3 -m sim.backtest_ats --results R.json [R2.json ...] --lines lines.csv --out DIR

Predictors (home margin): each sim run in the results files, the old model as it ran
live (the morning snapshot's sim_spread), net rating to date + home court. A side is
home when margin + home line > 0. Filters: how far the model is from the book, both
models agreeing, favourite / underdog, home / away, back-to-backs, thin lineup data,
month. A filter is only reported as holding up if it clears the bar on the first half
(Feb 14 - Mar 14 dates) and is then scored, untouched, on the second half.
"""

import argparse
import csv
import itertools
import json
import math
import os
from collections import defaultdict

SPLIT = "2026-03-15"
BREAKEVEN = 0.5238      # -110


def binom_p(w, n, p=0.5):
    """P(at least w wins in n at p): how often luck alone does this well."""
    return sum(math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(w, n + 1))


def wilson(w, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    ph = w / n
    d = 1 + z * z / n
    c = ph + z * z / (2 * n)
    m = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def load(results, lines_path):
    games = {}
    for path in results:
        for g in json.load(open(path))["games"]:
            k = (g["date"], g["home"], g["away"])
            games.setdefault(k, {}).update(g)
    rows = []
    for r in csv.DictReader(open(lines_path)):
        k = (r["date"], r["home"], r["away"])
        g = games.get(k)
        if g is None or not r.get("book_spread_home"):
            continue
        g = dict(g)
        g["line"] = float(r["book_spread_home"])
        if r.get("old_sim_spread_home"):
            g["old_margin"] = -float(r["old_sim_spread_home"])
        g["late"] = r.get("late") == "1"
        rows.append(g)
    return rows


def grade(g, margin):
    """(side, result) for a model's home margin: side 'H'/'A'/None, result 1 win / 0 loss / None push."""
    edge = margin + g["line"]
    if abs(edge) < 1e-9:
        return None, None
    side = "H" if edge > 0 else "A"
    cover = g["actual_margin"] + g["line"]
    if cover == 0:
        return side, None
    return side, int((cover > 0) == (side == "H"))


def record(rows, model, filt):
    w = l = 0
    for g in rows:
        m = g.get(f"{model}_margin") if model not in ("old", "nrtg") else (g.get("old_margin") if model == "old" else g.get("base_nrtg"))
        if m is None or not filt(g, m):
            continue
        _, r = grade(g, m)
        if r is None:
            continue
        w += r
        l += 1 - r
    return w, l


def filters(models):
    """name -> filter(game, margin)."""
    out = {"all": lambda g, m: True}
    for k in (1, 2, 3, 4, 5, 6, 8):
        out[f"edge>={k}"] = (lambda k: lambda g, m: abs(m + g["line"]) >= k)(k)
    for k_lo, k_hi in ((0, 2), (2, 4), (4, 6), (6, 99)):
        out[f"edge {k_lo}-{k_hi}"] = (lambda a, b: lambda g, m: a <= abs(m + g["line"]) < b)(k_lo, k_hi)
    out["takes the dog"] = lambda g, m: (m + g["line"] > 0) == (g["line"] > 0)
    out["takes the fav"] = lambda g, m: (m + g["line"] > 0) == (g["line"] < 0)
    out["takes home"] = lambda g, m: m + g["line"] > 0
    out["takes road"] = lambda g, m: m + g["line"] < 0
    out["no thin team"] = lambda g, m: not any((g.get("thin") or {}).values())
    out["a b2b team"] = lambda g, m: g.get("home_b2b") or g.get("away_b2b")
    out["no b2b"] = lambda g, m: not (g.get("home_b2b") or g.get("away_b2b"))
    out["line >= 7"] = lambda g, m: abs(g["line"]) >= 7
    out["line < 7"] = lambda g, m: abs(g["line"]) < 7
    for other in models:
        out[f"agrees with {other}"] = (lambda o: lambda g, m: _agree(g, m, o))(other)
    return out


def _margin(g, model):
    return g.get("old_margin") if model == "old" else g.get("base_nrtg") if model == "nrtg" else g.get(f"{model}_margin")


def _agree(g, m, other):
    o = _margin(g, other)
    return o is not None and (o + g["line"] > 0) == (m + g["line"] > 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", nargs="+", required=True)
    ap.add_argument("--lines", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--bar", type=float, default=0.75)
    ap.add_argument("--min-n", type=int, default=15)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    rows = [g for g in load(args.results, args.lines) if not g["late"]]
    runs = sorted({k[:-7] for g in rows for k in g if k.endswith("_margin") and k != "actual_margin"} - {"old"})
    models = runs + ["old", "nrtg"]
    train = [g for g in rows if g["date"] < SPLIT]
    test = [g for g in rows if g["date"] >= SPLIT]
    F = filters(models)
    single = {}
    for model in models:
        for name, f in F.items():
            if name == f"agrees with {model}":
                continue
            single[(model, name)] = f
    # two-filter combinations (one edge filter + one other), the most a sane search should try
    edge_f = [n for n in F if n.startswith("edge")]
    other_f = [n for n in F if not n.startswith("edge") and n != "all"]
    combos = {}
    for model in models:
        for e, o in itertools.product(edge_f, other_f):
            if o == f"agrees with {model}":
                continue
            combos[(model, f"{e} & {o}")] = (lambda f1, f2: lambda g, m: f1(g, m) and f2(g, m))(F[e], F[o])
    tried = {**single, **combos}
    res = []
    for (model, name), f in tried.items():
        wa, la = record(rows, model, f)
        wt, lt = record(train, model, f)
        wv, lv = record(test, model, f)
        res.append({"model": model, "filter": name, "all": (wa, la), "train": (wt, lt), "test": (wv, lv)})
    pct = lambda wl: wl[0] / (wl[0] + wl[1]) if sum(wl) else float("nan")
    lines = [f"# Against the morning book line\n",
             f"{len(rows)} lined games ({len(train)} before {SPLIT}, {len(test)} from it). "
             f"{len(tried)} model x filter combinations tried; at {len(tried)} tries, some clear any bar by luck.\n",
             "\n## Every model, every lined game\n", "| model | ATS | % | 95% range |", "|---|---|---|---|"]
    for model in models:
        w, l = record(rows, model, F["all"])
        lo, hi = wilson(w, w + l)
        lines.append(f"| {model} | {w}-{l} | {pct((w, l)):.1%} | {lo:.0%}-{hi:.0%} |")
    lines += ["\n## Filters by model (all lined games)\n", "| model | filter | ATS | % | first half | second half |", "|---|---|---|---|---|---|"]
    for r in sorted([r for r in res if (r["model"], r["filter"]) in single], key=lambda r: (r["model"], r["filter"])):
        if sum(r["all"]) >= args.min_n:
            lines.append(f"| {r['model']} | {r['filter']} | {r['all'][0]}-{r['all'][1]} | {pct(r['all']):.1%} | "
                         f"{r['train'][0]}-{r['train'][1]} | {r['test'][0]}-{r['test'][1]} |")
    lines += [f"\n## Over {args.bar:.0%}: chosen on the first half, scored on the second\n",
              f"A model x filter qualifies if its first-half record is at least {args.bar:.0%} on {args.min_n}+ picks. "
              "The second-half record is the honest number.\n",
              "| model | filter | first half | second half | second-half % | luck p (vs 50%) |", "|---|---|---|---|---|---|"]
    qual = [r for r in res if sum(r["train"]) >= args.min_n and pct(r["train"]) >= args.bar]
    for r in sorted(qual, key=lambda r: -pct(r["test"]) if sum(r["test"]) else 1):
        wv, lv = r["test"]
        p = binom_p(wv, wv + lv) if wv + lv else float("nan")
        lines.append(f"| {r['model']} | {r['filter']} | {r['train'][0]}-{r['train'][1]} | {wv}-{lv} | "
                     f"{pct(r['test']):.1%} | {p:.3f} |")
    if not qual:
        lines.append("| none | | | | | |")
    lines += [f"\n## Over {args.bar:.0%} on the whole lined set ({args.min_n}+ picks)\n",
              "Found after the fact over every combination; the first/second half split shows whether it holds.\n",
              "| model | filter | all | % | first half | second half | luck p, all (vs 50%) |", "|---|---|---|---|---|---|---|"]
    for r in sorted([r for r in res if sum(r["all"]) >= args.min_n and pct(r["all"]) >= args.bar], key=lambda r: -pct(r["all"])):
        w, l = r["all"]
        lines.append(f"| {r['model']} | {r['filter']} | {w}-{l} | {pct(r['all']):.1%} | {r['train'][0]}-{r['train'][1]} | "
                     f"{r['test'][0]}-{r['test'][1]} | {binom_p(w, w + l):.4f} |")
    open(os.path.join(args.out, "ats.md"), "w").write("\n".join(lines) + "\n")
    json.dump(res, open(os.path.join(args.out, "ats.json"), "w"), indent=1)
    print("\n".join(lines[:12 + len(models)]))


if __name__ == "__main__":
    main()

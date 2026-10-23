"""Moneylines and moneyline parlays against real prices: does the sim find value?

  cd nba_pipeline && python3 -m sim.backtest_ml --results R.json [R2.json] --odds odds_2025-26.csv --out DIR

For every game the sim ran (sim/backtest_pit.py results) and ESPN has a moneyline for
(collectors/espn_odds.py, DraftKings open and close):
  model win chance   P(home) = Phi(margin / SD), SD the sim's own miss on 2025-26
  market win chance  the open moneylines with the book's margin taken out
  blend              w x model + (1 - w) x market, w chosen on the first half
A bet is a side whose chance x decimal price - 1 (its expected value) clears a bar,
priced at the OPEN (the morning bet) and checked against the CLOSE (did the market
move our way). Singles, then parlays of each day's best 2 or 3 legs from different
games. Every rule is chosen on games before SPLIT and scored, unchanged, after it.
"""

import argparse
import csv
import itertools
import json
import math
import os
from collections import defaultdict

SPLIT = "2026-01-20"           # about half the 2025-26 regular season on each side
SD = 14.6                      # residual SD of the point-in-time sim (backtest_pit, 2025-26)
ABBR = {"GS": "GSW", "NY": "NYK", "NO": "NOP", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS", "PHO": "PHX"}


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def dec(american):
    a = float(american)
    return 1 + (a / 100 if a > 0 else 100 / -a)


def no_vig(ml_h, ml_a):
    ih, ia = 1 / dec(ml_h), 1 / dec(ml_a)
    return ih / (ih + ia)


def load(results, odds_path):
    sims = {}
    for path in results:
        for g in json.load(open(path))["games"]:
            sims.setdefault((g["date"], g["home"], g["away"]), {}).update(g)
    rows = []
    for r in csv.DictReader(open(odds_path)):
        if r.get("season_type") not in ("2", 2):
            continue
        h, a = ABBR.get(r["home"], r["home"]), ABBR.get(r["away"], r["away"])
        g = sims.get((r["date"], h, a))
        need = ("ml_home_open", "ml_away_open", "ml_home_close", "ml_away_close")
        if g is None or any(not r.get(k) for k in need):
            continue
        g = dict(g)
        for k in need:
            g[k] = float(r[k])
        g["home_win"] = g["actual_margin"] > 0
        g["p_mkt"] = no_vig(g["ml_home_open"], g["ml_away_open"])
        g["p_close"] = no_vig(g["ml_home_close"], g["ml_away_close"])
        rows.append(g)
    return rows


def p_model(g, run):
    m = g.get(f"{run}_margin") if run != "nrtg" else g.get("base_nrtg")
    return None if m is None else phi(m / SD)


def logloss(rows, f):
    s = n = 0
    for g in rows:
        p = f(g)
        if p is None:
            continue
        p = min(max(p, 1e-4), 1 - 1e-4)
        s -= math.log(p if g["home_win"] else 1 - p)
        n += 1
    return s / n if n else float("nan")


def bets(rows, f, bar, side_filter=None):
    """Each game's best side if its EV at the open clears bar: dicts with p, decimal, won, clv."""
    out = []
    for g in rows:
        p = f(g)
        if p is None:
            continue
        for side, pp, ml, mlc, won in (("H", p, g["ml_home_open"], g["ml_home_close"], g["home_win"]),
                                       ("A", 1 - p, g["ml_away_open"], g["ml_away_close"], not g["home_win"])):
            d = dec(ml)
            ev = pp * d - 1
            if ev >= bar and (side_filter is None or side_filter(side, ml)):
                out.append({"date": g["date"], "game": (g["home"], g["away"]), "side": side, "p": pp, "dec": d,
                            "won": won, "ev": ev, "clv": 1 / dec(mlc) - 1 / d, "ml": ml})
    return out


def single_roi(bs, stake=1.0):
    if not bs:
        return {"n": 0}
    profit = sum((b["dec"] - 1) * stake if b["won"] else -stake for b in bs)
    return {"n": len(bs), "won": sum(b["won"] for b in bs), "hit": sum(b["won"] for b in bs) / len(bs),
            "units": profit, "roi": profit / (len(bs) * stake), "clv": sum(b["clv"] > 0 for b in bs) / len(bs),
            "avg_ml": sum(b["ml"] for b in bs) / len(bs)}


def parlays(bs, legs, per_day=1):
    """Each day's top-EV legs (different games) as one parlay of `legs` legs, 1 unit each."""
    by_day = defaultdict(list)
    for b in bs:
        by_day[b["date"]].append(b)
    out = []
    for d, day in sorted(by_day.items()):
        day = sorted(day, key=lambda b: -b["ev"])
        seen, pick = set(), []
        for b in day:
            if b["game"] not in seen:
                pick.append(b)
                seen.add(b["game"])
            if len(pick) == legs * per_day:
                break
        for k in range(per_day):
            grp = pick[k * legs:(k + 1) * legs]
            if len(grp) == legs:
                dd = math.prod(b["dec"] for b in grp)
                out.append({"date": d, "won": all(b["won"] for b in grp), "dec": dd,
                            "ev": math.prod(b["p"] for b in grp) * dd - 1})
    if not out:
        return {"n": 0}
    profit = sum(p["dec"] - 1 if p["won"] else -1 for p in out)
    return {"n": len(out), "won": sum(p["won"] for p in out), "hit": sum(p["won"] for p in out) / len(out),
            "units": profit, "roi": profit / len(out), "avg_payout": sum(p["dec"] for p in out) / len(out)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", nargs="+", required=True)
    ap.add_argument("--odds", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    rows = load(args.results, args.odds)
    train = [g for g in rows if g["date"] < SPLIT]
    test = [g for g in rows if g["date"] >= SPLIT]
    runs = sorted({k[:-7] for g in rows for k in g if k.endswith("_margin") and k != "actual_margin"}) + ["nrtg"]
    L = [f"# Moneylines and parlays at DraftKings prices (2025-26 regular season)\n",
         f"{len(rows)} games with a sim line and open/close moneylines; {len(train)} before {SPLIT}, {len(test)} from it.\n",
         "## Who knows more: log loss (lower is better) on the second half\n",
         "| source | log loss | games |", "|---|---|---|",
         f"| market (open, no vig) | {logloss(test, lambda g: g['p_mkt']):.4f} | {len(test)} |",
         f"| market (close, no vig) | {logloss(test, lambda g: g['p_close']):.4f} | {len(test)} |"]
    blends = {}
    for run in runs:
        L.append(f"| {run} alone | {logloss(test, lambda g, r=run: p_model(g, r)):.4f} | "
                 f"{sum(p_model(g, run) is not None for g in test)} |")
        # the blend weight that fits the first half best
        if any(p_model(g, run) is not None for g in train):
            w = min((logloss(train, lambda g, w=w, r=run: None if p_model(g, r) is None else w * p_model(g, r) + (1 - w) * g["p_mkt"]), w)
                    for w in [i / 20 for i in range(21)])[1]
        else:
            w = 0.5                                  # no first-half games for this run (pre: Feb 20 on): an even blend
        blends[run] = w
        L.append(f"| {run} blended with the market, w={w:.2f} (fit on first half) | "
                 f"{logloss(test, lambda g, w=w, r=run: None if p_model(g, r) is None else w * p_model(g, r) + (1 - w) * g['p_mkt']):.4f} | |")
    L += ["\nIf a model alone loses to the market and its best blend weight is near 0, the market already has what it knows.\n",
          "## Single moneylines: bet the side whose EV at the open clears the bar (1 unit each)\n",
          "| source | EV bar | first half: n / hit / units / ROI | second half: n / hit / units / ROI / beat close |",
          "|---|---|---|---|"]
    fmt = lambda r: (f"{r['n']} / {r['hit']:.0%} / {r['units']:+.1f}u / {r['roi']:+.1%}" if r["n"] else "0")
    srcs = {f"{run} blend": (lambda g, w=blends[run], r=run: None if p_model(g, r) is None else w * p_model(g, r) + (1 - w) * g["p_mkt"])
            for run in runs}
    srcs.update({f"{run} alone": (lambda g, r=run: p_model(g, r)) for run in runs})
    table = []
    for name, f in srcs.items():
        for bar in (0.0, 0.02, 0.05, 0.10, 0.15, 0.20):
            a, b = single_roi(bets(train, f, bar)), single_roi(bets(test, f, bar))
            table.append((name, bar, a, b))
            L.append(f"| {name} | {bar:.0%} | {fmt(a)} | {fmt(b)}" + (f" / {b['clv']:.0%} |" if b["n"] else " |"))
    L += ["\n## Favourites only (price -150 or shorter), the 75%+ hit-rate zone\n",
          "| source | EV bar | first half | second half |", "|---|---|---|---|"]
    fav = lambda side, ml: ml <= -150
    for name in ("pit_nopt blend", "pit_nopt alone"):
        if name not in srcs:
            continue
        for bar in (-1.0, 0.0, 0.03, 0.06):
            a, b = single_roi(bets(train, srcs[name], bar, fav)), single_roi(bets(test, srcs[name], bar, fav))
            L.append(f"| {name} | {'any' if bar < -0.5 else f'{bar:.0%}'} | {fmt(a)} | {fmt(b)} |")
    L += ["\n## Parlays: each day's best legs at the bar, different games, 1 unit a parlay\n",
          "| source | EV bar | legs | first half: n / hit / units / ROI | second half: n / hit / units / ROI |", "|---|---|---|---|---|"]
    for name in [n for n in srcs if n.startswith(("pit_nopt", "pit ", "pre"))]:
        for bar in (0.02, 0.05, 0.10):
            for legs in (2, 3):
                a, b = parlays(bets(train, srcs[name], bar), legs), parlays(bets(test, srcs[name], bar), legs)
                L.append(f"| {name} | {bar:.0%} | {legs} | {fmt(a)} | {fmt(b)} |")
    open(os.path.join(args.out, "ml.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

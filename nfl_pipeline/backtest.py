#!/usr/bin/env python3
"""Strict walk-forward backtest of the NFL spread model vs the market.

No lookahead, by construction:
  * ratings for a game come from games with gameday < that game's gameday
    (model.ratings_at slices the committed tables by date);
  * the calibration (HFA, component weights) for season S is fit on seasons
    before S only;
  * the hyperparameters for season S are chosen by out-of-sample MAE on
    seasons before S (each of those seasons itself predicted walk-forward);
  * model selection uses MAE vs the actual margin, never ATS results.

Periods: 2017-2018 burn-in (calibration / selection history only),
DEV 2019-2024, HOLDOUT 2025 (not reported until --final), LIVE 2026 to date.

Tier rule (fixed before the holdout was run — see TIER_RULE): a publishing
tier exists only if an |edge| threshold beats -110 break-even in DEV with a
Bonferroni-corrected one-sided p < 0.05 AND is above break-even on HOLDOUT.

  python3 nfl_pipeline/backtest.py            # dev report only (2019-2024)
  python3 nfl_pipeline/backtest.py --final    # + holdout 2025 + live 2026, writes
                                              #   reports/nfl_backtest.{json,txt},
                                              #   nfl_pipeline/model_params.json, tiers.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (  # noqa: E402
    BACKTEST_JSON, BACKTEST_TXT, BREAK_EVEN, CACHE, ESPN_LINES_CSV, PKG, QB_GAMES_CSV,
    SCHEDULES_CSV, TEAM_GAMES_CSV, TIERS_JSON,
)
import model as M  # noqa: E402

FIRST_TARGET = 2017
DEV = list(range(2019, 2025))
HOLDOUT = [2025]
LIVE = [2026]
MODEL_PARAMS_JSON = os.path.join(PKG, "model_params.json")
THRESHOLDS = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
BUCKETS = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 7), (7, 99)]
WIN_PAYOUT = 100 / 110
TIER_RULE = (
    "Thresholds T in {1,2,3,4,5,6} points of |model margin - closing spread|. A threshold qualifies "
    "only if (1) DEV 2019-2024 has n >= 100 graded bets at |edge| >= T and the one-sided binomial "
    "p-value of its ATS record vs 52.38% (break-even at -110), multiplied by 6 (Bonferroni), is < 0.05; "
    "and (2) HOLDOUT 2025 at the same threshold has n >= 20 and a win rate above 52.38%. Qualifying "
    "thresholds, smallest first, become C8, C9, C10 (at most three). None qualifying = no tiers = "
    "nothing can be published."
)


# ── stats ──

def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c - h, c + h)


def binom_sf(k, n, p):
    """P(X >= k), X ~ Binomial(n, p) — exact, via log-space sum."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    lp, lq = math.log(p), math.log(1 - p)
    terms = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq
             for i in range(k, n + 1)]
    m = max(terms)
    return min(1.0, math.exp(m) * sum(math.exp(t - m) for t in terms))


def ats_summary(df):
    """df has columns cover (1 win, 0 loss, NaN push)."""
    graded = df["cover"].dropna()
    n, w = int(len(graded)), int(graded.sum())
    pushes = int(df["cover"].isna().sum())
    lo, hi = wilson(w, n)
    roi = ((w * WIN_PAYOUT - (n - w)) / n) if n else None
    return {
        "n": n, "w": w, "l": n - w, "push": pushes,
        "win_pct": round(w / n, 4) if n else None,
        "wilson95": [round(lo, 4), round(hi, 4)] if n else None,
        "p_vs_breakeven": round(binom_sf(w, n, BREAK_EVEN), 4) if n else None,
        "roi_at_110": round(roi, 4) if roi is not None else None,
        "units_at_110": round(w * WIN_PAYOUT - (n - w), 2),
    }


# ── components grid (cached outside the repo) ──

def _data_hash():
    h = hashlib.sha256()
    for p in (SCHEDULES_CSV, TEAM_GAMES_CSV, QB_GAMES_CSV):
        with open(p, "rb") as f:
            h.update(f.read())
    h.update(open(M.__file__, "rb").read())
    return h.hexdigest()[:16]


def _components_job(p: M.Params):
    d = M.Data()
    g = d.sched[d.sched["season"] >= FIRST_TARGET]
    return p.key(), M.raw_components(d, p, g)


def components_grid(grid, workers=None):
    tag = _data_hash()
    cdir = os.path.join(CACHE, "components", tag)
    os.makedirs(cdir, exist_ok=True)
    out, todo = {}, []
    for p in grid:
        path = os.path.join(cdir, f"{p.key()}.csv")
        if os.path.exists(path):
            out[p.key()] = pd.read_csv(path)
        else:
            todo.append(p)
    if todo:
        print(f"  computing components for {len(todo)} parameter sets (cache {cdir})")
        with ProcessPoolExecutor(max_workers=workers or max(1, (os.cpu_count() or 2) - 1)) as ex:
            for key, comp in ex.map(_components_job, todo):
                comp.to_csv(os.path.join(cdir, f"{key}.csv"), index=False)
                out[key] = comp
    return out


# ── walk-forward ──

def season_predictions(games, comp, season, features, fit_from=FIRST_TARGET):
    """Predict `season` with calibration fit on [fit_from, season-1] (completed games)."""
    m = games.merge(comp, on="game_id")
    prior = m[(m["season"] >= fit_from) & (m["season"] < season) & m["result"].notna()]
    cur = m[m["season"] == season].copy()
    if prior.empty or cur.empty:
        return None, None
    cal = M.fit_calibration(prior, prior["result"].values.astype(float), prior["season"].values, season,
                            features=features)
    cur["pred"] = cal.predict(cur)
    return cur, cal


def oos_mae(games, comp, upto, features):
    """Mean out-of-sample MAE over seasons [FIRST_TARGET+1, upto-1], each walk-forward."""
    errs = []
    for s in range(FIRST_TARGET + 1, upto):
        cur, _ = season_predictions(games, comp, s, features)
        if cur is None:
            continue
        cur = cur[cur["result"].notna()]
        errs.append(np.abs(cur["result"] - cur["pred"]).values)
    return float(np.concatenate(errs).mean()) if errs else float("inf")


def walk_forward(games, grid_comp, seasons):
    cands = [(k, fs) for k in grid_comp for fs in M.FEATURE_SETS]
    preds, chosen = [], {}
    for s in seasons:
        scores = {(k, fs): oos_mae(games, grid_comp[k], s, M.FEATURE_SETS[fs]) for k, fs in cands}
        bk, bfs = min(scores, key=scores.get)
        best = f"{bk}|{bfs}"
        cur, cal = season_predictions(games, grid_comp[bk], s, M.FEATURE_SETS[bfs])
        if cur is None:
            continue
        cur["params"] = best
        preds.append(cur)
        chosen[s] = {"params": best, "params_key": bk, "feature_set": bfs,
                     "selection_oos_mae": round(scores[(bk, bfs)], 4),
                     "calibration": cal.as_dict()}
        print(f"  {s}: params {best} (prior-season OOS MAE {scores[(bk, bfs)]:.3f}); "
              f"HFA {cal.coef['home']:+.2f}, sigma {cal.sigma:.2f}")
    return pd.concat(preds, ignore_index=True), chosen


def add_ats(df):
    df = df.copy()
    df["edge"] = df["pred"] - df["spread_line"]
    df["pick_home"] = df["edge"] > 0
    diff = df["result"] - df["spread_line"]         # > 0 home covered
    cover = np.where(diff == 0, np.nan, np.where(df["pick_home"], diff > 0, diff < 0).astype(float))
    df["cover"] = np.where(df["result"].isna() | df["spread_line"].isna() | (df["edge"] == 0), np.nan, cover)
    df["abs_edge"] = df["edge"].abs()
    return df


# ── reports ──

def per_season(df):
    out = []
    for s, g in df.groupby("season"):
        g = g[g["result"].notna() & g["spread_line"].notna()]
        if g.empty:
            continue
        out.append({
            "season": int(s), "games": int(len(g)),
            "mae_model": round(float(np.abs(g["result"] - g["pred"]).mean()), 3),
            "mae_market": round(float(np.abs(g["result"] - g["spread_line"]).mean()), 3),
            "rmse_model": round(float(np.sqrt(((g["result"] - g["pred"]) ** 2).mean())), 3),
            "rmse_market": round(float(np.sqrt(((g["result"] - g["spread_line"]) ** 2).mean())), 3),
            "mean_abs_model_minus_market": round(float(np.abs(g["pred"] - g["spread_line"]).mean()), 3),
            "ats_all": ats_summary(g),
        })
    return out


def bucket_table(df):
    rows = []
    for lo, hi in BUCKETS:
        b = df[(df["abs_edge"] >= lo) & (df["abs_edge"] < hi)]
        rows.append({"edge": f"{lo}-{hi if hi < 99 else '+'}", **ats_summary(b)})
    return rows


def threshold_table(df):
    return [{"min_edge": t, **ats_summary(df[df["abs_edge"] >= t])} for t in THRESHOLDS]


def encompassing(df):
    """OLS: result = a + b*market + c*(model - market). c > 0 (significant)
    would mean the model carries information the closing line lacks."""
    g = df[df["result"].notna() & df["spread_line"].notna()]
    X = np.column_stack([np.ones(len(g)), g["spread_line"], g["pred"] - g["spread_line"]])
    y = g["result"].values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    s2 = (resid ** 2).sum() / (len(y) - 3)
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    blend = 0.5 * g["pred"] + 0.5 * g["spread_line"]
    return {
        "n": int(len(g)),
        "intercept": [round(beta[0], 3), round(se[0], 3)],
        "market": [round(beta[1], 3), round(se[1], 3)],
        "model_minus_market": [round(beta[2], 3), round(se[2], 3)],
        "t_model_minus_market": round(beta[2] / se[2], 2),
        "mae_market": round(float(np.abs(y - g["spread_line"]).mean()), 3),
        "mae_50_50_blend": round(float(np.abs(y - blend).mean()), 3),
        "note": "coefficient [estimate, standard error]",
    }


def calibration_tables(df, chosen):
    g = df[df["result"].notna()].copy()
    g["sigma"] = g["season"].map(lambda s: chosen[s]["calibration"]["sigma"])
    g["p_home"] = [M.norm_cdf(p / s) for p, s in zip(g["pred"], g["sigma"])]
    g = g[g["result"] != 0]
    wp = []
    for lo in np.arange(0.0, 1.0, 0.1):
        b = g[(g["p_home"] >= lo) & (g["p_home"] < lo + 0.1)]
        if len(b):
            wp.append({"bin": f"{lo:.1f}-{lo + 0.1:.1f}", "n": int(len(b)),
                       "predicted": round(float(b["p_home"].mean()), 3),
                       "actual": round(float((b["result"] > 0).mean()), 3)})
    c = df[df["cover"].notna()].copy()
    c["sigma"] = c["season"].map(lambda s: chosen[s]["calibration"]["sigma"])
    c["p_cover_claimed"] = [M.norm_cdf(e / s) for e, s in zip(c["abs_edge"], c["sigma"])]
    cov = []
    for lo, hi in BUCKETS:
        b = c[(c["abs_edge"] >= lo) & (c["abs_edge"] < hi)]
        if len(b):
            cov.append({"edge": f"{lo}-{hi if hi < 99 else '+'}", "n": int(len(b)),
                        "claimed_cover": round(float(b["p_cover_claimed"].mean()), 3),
                        "actual_cover": round(float(b["cover"].mean()), 3)})
    brier = float(((g["p_home"] - (g["result"] > 0)) ** 2).mean())
    return {"win_prob": wp, "cover_prob": cov, "brier_win_prob": round(brier, 4),
            "note": "p_home = Phi(pred / sigma); claimed cover = Phi(|edge| / sigma) — what the model "
                    "would imply if the market added nothing. Ties/pushes excluded."}


def clv_table(df):
    """Open → close movement relative to the model's side at the open."""
    if not os.path.exists(ESPN_LINES_CSV):
        return None
    lines = pd.read_csv(ESPN_LINES_CSV).dropna(subset=["open_home_fav", "close_home_fav"])
    m = df.merge(lines[["game_id", "provider", "open_home_fav", "close_home_fav"]], on="game_id")
    if m.empty:
        return None
    out = {}
    m["edge_open"] = m["pred"] - m["open_home_fav"]
    m["move"] = (m["close_home_fav"] - m["open_home_fav"]) * np.sign(m["edge_open"])
    m["nflverse_vs_espn_close"] = m["spread_line"] - m["close_home_fav"]
    diff = m["result"] - m["open_home_fav"]
    m["cover_open"] = np.where(diff == 0, np.nan, np.where(m["edge_open"] > 0, diff > 0, diff < 0).astype(float))
    # The backtest uses the ACTUAL starting QB (nflverse schedule). Starter
    # news moves lines between open and close, so in games where a team's QB
    # differs from its previous game the open->close test is contaminated by
    # hindsight. Those games are reported separately; trust the no-change rows.
    m["qb_change"] = m["game_id"].map(qb_change_games()).fillna(False).astype(bool)

    def row(g, season):
        return {
            "season": season, "n": int(len(g)),
            "close_moved_toward_model": int((g["move"] > 0).sum()),
            "close_moved_away": int((g["move"] < 0).sum()),
            "unchanged": int((g["move"] == 0).sum()),
            "mean_move_pts_toward_model": round(float(g["move"].mean()), 3) if len(g) else None,
            "ats_vs_open_line": ats_summary(g.assign(cover=g["cover_open"])),
        }

    for th in (0, 2, 3):
        base = m[m["edge_open"].abs() >= th]
        label = "all" if th == 0 else f"edge_open>={th}"
        for season, g in base.groupby("season"):
            out.setdefault(label, []).append(row(g, int(season)))
        for qc, tag in ((False, "no_qb_change"), (True, "qb_change")):
            out.setdefault(f"{label}|{tag}", []).append(row(base[base["qb_change"] == qc], "pooled"))
    agree = m["nflverse_vs_espn_close"].abs()
    out["source_check"] = {
        "n": int(len(m)), "providers": m["provider"].value_counts().to_dict(),
        "nflverse_spread_line_equals_espn_close": int((agree == 0).sum()),
        "within_0.5": int((agree <= 0.5).sum()), "within_1.0": int((agree <= 1.0).sum()),
        "mean_abs_diff": round(float(agree.mean()), 3),
    }
    return out


def qb_change_games():
    """game_id -> True if either team's starting QB differs from its previous game."""
    s = pd.read_csv(SCHEDULES_CSV)
    parts = [s[["game_id", "gameday", f"{x}_team", f"{x}_qb_id"]].set_axis(["game_id", "gameday", "team", "qb"], axis=1)
             for x in ("home", "away")]
    t = pd.concat(parts).sort_values(["team", "gameday"])
    t["prev"] = t.groupby("team")["qb"].shift(1)
    t["chg"] = t["prev"].notna() & (t["qb"] != t["prev"])
    return t.groupby("game_id")["chg"].any()


def tier_decision(dev, hold):
    n_tests = len(THRESHOLDS)
    rows, tiers = [], []
    for t in THRESHOLDS:
        d = ats_summary(dev[dev["abs_edge"] >= t])
        h = ats_summary(hold[hold["abs_edge"] >= t]) if hold is not None else None
        p_adj = min(1.0, (d["p_vs_breakeven"] or 1.0) * n_tests) if d["n"] else 1.0
        dev_ok = d["n"] >= 100 and p_adj < 0.05
        hold_ok = bool(h and h["n"] >= 20 and h["win_pct"] is not None and h["win_pct"] > BREAK_EVEN)
        rows.append({"min_edge": t, "dev": d, "dev_p_bonferroni": round(p_adj, 4), "dev_qualifies": dev_ok,
                     "holdout": h, "holdout_confirms": hold_ok, "qualifies": dev_ok and hold_ok})
        if dev_ok and hold_ok:
            tiers.append(t)
    named = [{"conf": c, "min_edge": t} for c, t in zip((8, 9, 10), tiers[:3])]
    return {"rule": TIER_RULE, "thresholds": rows, "tiers": named,
            "verdict": ("tiers defined: " + ", ".join(f"C{x['conf']} |edge|>={x['min_edge']}" for x in named))
            if named else "NO edge bucket clears break-even out of sample — no publishing tiers."}


# ── text report ──

def fmt_ats(a):
    if not a or not a["n"]:
        return "n=0"
    lo, hi = a["wilson95"]
    return (f"{a['w']:>4}-{a['l']:<4} {100 * a['win_pct']:5.1f}%  CI [{100 * lo:4.1f}, {100 * hi:4.1f}]  "
            f"p={a['p_vs_breakeven']:.3f}  ROI {100 * a['roi_at_110']:+5.1f}%  ({a['units_at_110']:+.1f}u)")


def text_report(rep):
    L = []
    L.append(f"NFL SPREAD MODEL — WALK-FORWARD BACKTEST  (generated {rep['generated_at']})")
    L.append("Market = nflverse spread_line (final pre-game line). Break-even at -110 = 52.38%.")
    L.append("p = one-sided exact binomial P(>= wins | 52.38%). CI = Wilson 95%. Pushes excluded.\n")
    L.append("PER SEASON  (MAE / RMSE of home margin; ATS = every game, model side)")
    for s in rep["per_season"]:
        L.append(f"  {s['season']}  n={s['games']:>3}  MAE model {s['mae_model']:6.3f}  market {s['mae_market']:6.3f}  "
                 f"| RMSE {s['rmse_model']:6.3f} vs {s['rmse_market']:6.3f}  | ATS {fmt_ats(s['ats_all'])}")
    for period in ("dev", "holdout", "live"):
        P = rep["periods"].get(period)
        if not P:
            continue
        L.append(f"\n{P['label']}")
        L.append(f"  MAE model {P['mae_model']:.3f} vs market {P['mae_market']:.3f}  (n={P['games']})")
        L.append(f"  all games        {fmt_ats(P['ats_all'])}")
        L.append("  by |edge| bucket:")
        for b in P["buckets"]:
            L.append(f"    {b['edge']:>5} pts  {fmt_ats(b)}")
        L.append("  cumulative |edge| >= T:")
        for b in P["thresholds"]:
            L.append(f"    >= {b['min_edge']:<3}    {fmt_ats(b)}")
    e = rep["encompassing_dev"]
    L.append("\nDOES THE MODEL ADD INFORMATION TO THE CLOSING LINE?  (DEV, OLS)")
    L.append(f"  result = {e['intercept'][0]:+.2f} + {e['market'][0]:.3f}*market + {e['model_minus_market'][0]:+.3f}*(model-market)"
             f"   SE {e['model_minus_market'][1]:.3f}, t = {e['t_model_minus_market']:+.2f}")
    L.append(f"  MAE market {e['mae_market']:.3f}, 50/50 blend {e['mae_50_50_blend']:.3f}")
    if rep.get("encompassing_holdout"):
        e = rep["encompassing_holdout"]
        L.append(f"  HOLDOUT: coef {e['model_minus_market'][0]:+.3f} (SE {e['model_minus_market'][1]:.3f}, t {e['t_model_minus_market']:+.2f})")
    c = rep["calibration_dev"]
    L.append(f"\nCALIBRATION (DEV)  Brier win-prob {c['brier_win_prob']}")
    for b in c["win_prob"]:
        L.append(f"  P(home win) {b['bin']}: predicted {b['predicted']:.3f}  actual {b['actual']:.3f}  n={b['n']}")
    L.append("  cover claims vs reality:")
    for b in c["cover_prob"]:
        L.append(f"    |edge| {b['edge']:>5}: model implies {b['claimed_cover']:.3f}, actual {b['actual_cover']:.3f} (n={b['n']})")
    if rep.get("clv"):
        L.append("\nCLV-STYLE (ESPN open → close; model side picked at the OPEN line)")
        sc = rep["clv"].get("source_check")
        if sc:
            L.append(f"  source check: nflverse spread_line vs ESPN close on {sc['n']} games — exact {sc['nflverse_spread_line_equals_espn_close']}, "
                     f"within 0.5 {sc['within_0.5']}, within 1.0 {sc['within_1.0']}, mean |diff| {sc['mean_abs_diff']}")
        labels = [k for k in rep["clv"] if k != "source_check"]
        for label in labels:
            for r in rep["clv"].get(label, []):
                L.append(f"  {label:<27} {r['season']!s:>6}  n={r['n']:>3}  toward {r['close_moved_toward_model']:>3}  away {r['close_moved_away']:>3}  "
                         f"same {r['unchanged']:>3}  mean {r['mean_move_pts_toward_model']:+.2f} pts | ATS@open {fmt_ats(r['ats_vs_open_line'])}")
    t = rep.get("tiers")
    if t:
        L.append("\nPUBLISHING TIERS")
        L.append("  rule: " + t["rule"])
        for r in t["thresholds"]:
            L.append(f"  >= {r['min_edge']:<3} dev {fmt_ats(r['dev'])}  p_bonf {r['dev_p_bonferroni']:.3f}  "
                     f"| holdout {fmt_ats(r['holdout'])}  → {'QUALIFIES' if r['qualifies'] else 'no'}")
        L.append("  VERDICT: " + t["verdict"])
    L.append("\nPARAMETERS CHOSEN (walk-forward, by prior-season out-of-sample MAE)")
    for s, c in rep["chosen"].items():
        co = c["calibration"]["coef"]
        ws = "  ".join(f"{k} x{v:.2f}" for k, v in co.items() if k not in ("home", "rest_diff"))
        L.append(f"  {s}: {c['params']}  HFA {co['home']:+.2f}  {ws}  rest {co['rest_diff']:+.3f}/day  "
                 f"sigma {c['calibration']['sigma']:.2f}")
    return "\n".join(L) + "\n"


def period_block(df, label):
    g = df[df["result"].notna() & df["spread_line"].notna()]
    if g.empty:
        return None
    return {"label": label, "games": int(len(g)),
            "mae_model": round(float(np.abs(g["result"] - g["pred"]).mean()), 3),
            "mae_market": round(float(np.abs(g["result"] - g["spread_line"]).mean()), 3),
            "ats_all": ats_summary(g), "buckets": bucket_table(g), "thresholds": threshold_table(g)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true", help="include HOLDOUT 2025 + LIVE 2026 and write outputs")
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args()

    data = M.Data()
    games = data.sched[["game_id", "season", "week", "game_type", "gameday", "home_team", "away_team",
                        "result", "spread_line", "location"]].copy()
    grid = components_grid(M.GRID, a.workers)
    targets = DEV + (HOLDOUT + LIVE if a.final else [])
    preds, chosen = walk_forward(games, grid, targets)
    preds = add_ats(preds)

    rep = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "final": bool(a.final), "grid_size": len(M.GRID),
           "per_season": per_season(preds), "periods": {},
           "chosen": {str(k): v for k, v in chosen.items()}}
    dev = preds[preds["season"].isin(DEV)]
    rep["periods"]["dev"] = period_block(dev, "DEV 2019-2024 (walk-forward)")
    rep["encompassing_dev"] = encompassing(dev)
    rep["calibration_dev"] = calibration_tables(dev, chosen)
    hold = None
    if a.final:
        hold = preds[preds["season"].isin(HOLDOUT)]
        live = preds[preds["season"].isin(LIVE)]
        rep["periods"]["holdout"] = period_block(hold, "HOLDOUT 2025 (never used for any design choice)")
        rep["periods"]["live"] = period_block(live, "LIVE 2026 to date")
        rep["encompassing_holdout"] = encompassing(hold)
        rep["calibration_holdout"] = calibration_tables(hold, chosen)
    rep["clv"] = clv_table(preds if a.final else dev)
    rep["tiers"] = tier_decision(dev, hold) if a.final else None

    txt = text_report(rep)
    print(txt)
    if a.final:
        os.makedirs(os.path.dirname(BACKTEST_JSON), exist_ok=True)
        with open(BACKTEST_JSON, "w") as f:
            json.dump(rep, f, indent=1)
        with open(BACKTEST_TXT, "w") as f:
            f.write(txt)
        cols = ["game_id", "season", "week", "gameday", "home_team", "away_team", "result", "spread_line",
                "pred", "edge", "cover", "params", "home", "epa_margin", "pass_margin", "rush_margin",
                "st_diff", "qb_diff", "rest_diff", "qb_adj_home", "qb_adj_away"]
        out = preds[cols].copy()
        out["gameday"] = pd.to_datetime(out["gameday"]).dt.strftime("%Y-%m-%d")
        out.round(3).to_csv(os.path.join(PKG, "data", "backtest_games.csv"), index=False)
        # live config: parameters + calibration chosen for the current season
        cur = max(chosen)
        live_cfg = {"season": cur, "params": next(p.as_dict() for p in M.GRID if p.key() == chosen[cur]["params_key"]),
                    "params_key": chosen[cur]["params_key"], "feature_set": chosen[cur]["feature_set"],
                    "calibration": chosen[cur]["calibration"],
                    "frozen_at": rep["generated_at"],
                    "note": "Chosen walk-forward before the season from prior seasons only; frozen for the season."}
        with open(MODEL_PARAMS_JSON, "w") as f:
            json.dump(live_cfg, f, indent=1)
        with open(TIERS_JSON, "w") as f:
            json.dump({"generated_at": rep["generated_at"], "rule": TIER_RULE, "tiers": rep["tiers"]["tiers"],
                       "verdict": rep["tiers"]["verdict"]}, f, indent=1)
        print(f"wrote {BACKTEST_JSON}, {BACKTEST_TXT}, {MODEL_PARAMS_JSON}, {TIERS_JSON}")


if __name__ == "__main__":
    main()

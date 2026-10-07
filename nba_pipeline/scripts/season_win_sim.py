#!/usr/bin/env python3
"""season_win_sim.py — play the 2026-27 regular season thousands of times and
price every team's win total against the book.

Team strength comes from the same player model as the nightly picks (MOJO,
minutes-weighted into a team MOJI) on the NEW rosters:

  1. MOJI per team: every rostered player's MOJO (compute_mojo_score) weighted
     by his minutes, scaled to 240 a night. Players who missed most of last
     season (Achilles, ACL...) fall back to their 2024-25 line so a returning
     star isn't counted as gone. Rookies carry no line and play 0 minutes.
  2. MOJI -> net rating: fitted on 2025-26 (end-of-season rosters vs actual
     team net rating), so the scale is learned, not assumed.
  3. Projection = half "last season's net + roster change" and half "pure
     roster rating", regressed 30% to the mean (the year-to-year norm).
  4. Every game of the real schedule (ESPN): margin ~ N(strength gap + HCA
     - back-to-back, game sd measured from 2025-26). Each simulated season
     also draws each team's true strength around its projection, because a
     preseason number is never exact.

Output: data/win_totals/sim_2026-27.json and a printed board ranked by how
hard the sim disagrees with the book.

Usage: NBA_SEASON=2026-27 python scripts/season_win_sim.py [--n 20000]
"""

import argparse
import json
import math
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime

import numpy as np
import re
import unicodedata

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
os.environ.setdefault("NBA_SEASON", "2026-27")
import generate_frontend as gf  # noqa: E402
from config import DB_PATH  # noqa: E402

OUT_DIR = os.path.join(ROOT, "data", "win_totals")
NEW, OLD, OLDER = "2026-27", "2025-26", "2024-25"
REGRESS = 0.70          # keep 70% of the projection, regress 30% to league average
TEAM_SD = 4.3           # preseason miss on a team's true net rating (points): this method's
                        # 2025-26 backtest RMSE 4.6, less ~1.5 of in-season sampling noise
MIN_GP_FOR_LINE = 20    # fewer games than this last season -> use 2024-25 line
STAT_COLS = ("player_id, team_id, gp, pts_pg, ast_pg, reb_pg, stl_pg, blk_pg, ts_pct, "
             "usg_pct, net_rating, minutes_per_game, off_rating, def_rating")


def rows(con, sql, args=()):
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def player_lines(con, season):
    """{player_id: stat row} for a season; traded players keep their biggest-minutes row."""
    out = {}
    for r in rows(con, f"SELECT {STAT_COLS} FROM player_season_stats WHERE season_id = ?", [season]):
        pid = r["player_id"]
        if pid not in out or (r["gp"] or 0) * (r["minutes_per_game"] or 0) > (out[pid]["gp"] or 0) * (out[pid]["minutes_per_game"] or 0):
            out[pid] = r
    return out


def norm(name):
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    name = re.sub(r"[.'\-]", "", name)
    return " ".join(p for p in name.split() if p not in ("jr", "sr", "ii", "iii", "iv", "v"))


def rookie_prior(con, draft_last_year, line_season):
    """MOJO and expected minutes by draft slot, fitted on last year's rookies' actual first season.

    Expected minutes = mpg x share of games played, so rookies who sat count as sitting.
    Returns f(overall_pick) -> (mojo, minutes) and the fit sample size."""
    names = {norm(r["full_name"]): r["player_id"] for r in rows(con, "SELECT player_id, full_name FROM players")}
    lines = player_lines(con, line_season)
    pts = []
    for d in draft_last_year:
        pid = names.get(norm(d["name"]))
        if pid in lines and (lines[pid]["gp"] or 0) > 0:
            L = lines[pid]
            pts.append((math.log(d["overall"]), gf.compute_mojo_score(L)[0], (L["minutes_per_game"] or 0) * min(1, (L["gp"] or 0) / 82)))
    x = np.array([p[0] for p in pts])
    bm, am = np.polyfit(x, [p[1] for p in pts], 1)
    bn, an = np.polyfit(x, [p[2] for p in pts], 1)
    return (lambda pick: (int(round(am + bm * math.log(pick))), max(0.0, an + bn * math.log(pick)))), len(pts)


def availability(injuries, opener, finale):
    """{norm name: share of the season available} from ESPN's expected return dates."""
    out = {}
    o, f = datetime.strptime(opener, "%Y-%m-%d"), datetime.strptime(finale, "%Y-%m-%d")
    for i in injuries:
        ret = (i.get("return") or "")[:10]
        if i.get("fantasy") == "OFS":
            out[norm(i["name"])] = 0.0
        elif ret and ret > opener:
            r = datetime.strptime(ret, "%Y-%m-%d")
            out[norm(i["name"])] = max(0.0, min(1.0, (f - r).days / (f - o).days))
    return out


def team_moji(con, roster_season, line_seasons, rookies=None, avail=None):
    """{abbr: (moji, [(name, mojo, minutes, source)])} on `roster_season` rosters.

    rookies: {norm name: (mojo, minutes)} for players with no NBA line yet.
    avail:   {norm name: share of the season he's expected to play}."""
    rookies, avail = rookies or {}, avail or {}
    lines = [player_lines(con, s) for s in line_seasons]
    names = {r["player_id"]: r["full_name"] for r in rows(con, "SELECT player_id, full_name FROM players")}
    teams = {r["team_id"]: r["abbreviation"] for r in rows(con, "SELECT team_id, abbreviation FROM teams")}
    roster = defaultdict(list)
    for r in rows(con, "SELECT player_id, team_id FROM roster_assignments WHERE season_id = ?", [roster_season]):
        roster[teams[r["team_id"]]].append(r["player_id"])
    out = {}
    for abbr, pids in roster.items():
        players = []
        for pid in set(pids):
            line, src = None, None
            for s, L in zip(line_seasons, lines):
                if pid in L and (L[pid]["gp"] or 0) >= MIN_GP_FOR_LINE:
                    line, src = L[pid], s
                    break
            if line is None:
                for s, L in zip(line_seasons, lines):     # short sample beats nothing
                    if pid in L:
                        line, src = L[pid], s
                        break
            name = names.get(pid, str(pid))
            if line is None:
                if norm(name) not in rookies:
                    continue                             # undrafted / no NBA line: end of bench
                mojo, mpg = rookies[norm(name)]
                src = "rookie"
            else:
                mojo, _ = gf.compute_mojo_score(line)
                mpg = float(line["minutes_per_game"] or 0)
            share = avail.get(norm(name), 1.0)
            if share < 1.0:
                src = f"{src}, plays {share:.0%}"
            players.append([name, mojo, mpg * share, src])
        # minutes: the best players (by MOJO) play first, each up to last season's role
        # (max 36); the weakest give minutes back until the team plays 240 a night
        players.sort(key=lambda p: (-p[1], -p[2]))
        left = 240.0
        for p in players:
            p[2] = max(0.0, min(36.0, p[2], left))
            left -= p[2]
        players = [p for p in players if p[2] > 0]
        tot = sum(p[2] for p in players)
        if 0 < tot < 240:                                # thin roster: stretch everyone
            for p in players:
                p[2] *= 240.0 / tot
        moji = sum(p[1] * p[2] for p in players) / 240.0
        out[abbr] = (moji, players)
    return out


def espn_schedule(season_year=2027):
    """Regular-season games from ESPN team schedules: [(date, home, away)]."""
    teams = requests.get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams", timeout=20).json()
    teams = [t["team"] for t in teams["sports"][0]["leagues"][0]["teams"]]
    fix = {"GS": "GSW", "NY": "NYK", "NO": "NOP", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS"}
    games = {}
    for t in teams:
        d = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{t['id']}/schedule",
                         params={"season": season_year, "seasontype": 2}, timeout=20).json()
        for e in d.get("events", []):
            comp = e["competitions"][0]
            side = {c["homeAway"]: fix.get(c["team"]["abbreviation"], c["team"]["abbreviation"]) for c in comp["competitors"]}
            games[e["id"]] = (e["date"][:10], side["home"], side["away"])
    return sorted(games.values())


def no_vig(over, under):
    imp = lambda a: 100 / (a + 100) if a > 0 else -a / (-a + 100)  # noqa: E731
    po, pu = imp(over), imp(under)
    return po / (po + pu)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=20261020)
    args = ap.parse_args()
    con = sqlite3.connect(DB_PATH)

    # 1-2. fit MOJI -> net rating on last season
    old = team_moji(con, OLD, [OLD])
    teams = {r["abbreviation"]: r["team_id"] for r in rows(con, "SELECT team_id, abbreviation FROM teams")}
    net_old = {a: r["net_rating"] for a, r in ((a, rows(con, "SELECT net_rating FROM team_season_stats WHERE team_id=? AND season_id=?", [tid, OLD])[0]) for a, tid in teams.items())}
    A = sorted(teams)
    x = np.array([old[a][0] for a in A]); y = np.array([net_old[a] for a in A])
    b, a0 = np.polyfit(x, y, 1)
    r2 = np.corrcoef(x, y)[0, 1] ** 2
    print(f"fit 2025-26: net = {a0:+.1f} + {b:.2f} x MOJI   (R^2 {r2:.2f})")

    # 3. project on new rosters (2025-26 lines, 2024-25 for players who missed last season),
    #    with this year's rookies by draft slot and injured players' minutes cut to their return
    ctx = json.load(open(os.path.join(OUT_DIR, "espn_context_2026-27.json")))
    prior, n_fit = rookie_prior(con, ctx["drafts"]["2025"], OLD)
    rookies = {norm(d["name"]): prior(d["overall"]) for d in ctx["drafts"]["2026"]}
    print(f"rookie prior from {n_fit} 2025 draftees: #1 -> MOJO {prior(1)[0]}, {prior(1)[1]:.0f} min; "
          f"#10 -> {prior(10)[0]}, {prior(10)[1]:.0f}; #30 -> {prior(30)[0]}, {prior(30)[1]:.0f}")
    sched_path = os.path.join(OUT_DIR, "schedule_2026-27.json")
    sched_dates = [g[0] for g in json.load(open(sched_path))["games"]] if os.path.exists(sched_path) else ["2026-10-20", "2027-04-11"]
    avail = availability(ctx["injuries"], min(sched_dates), max(sched_dates))
    print("injured, share of season available:", ", ".join(f"{k} {v:.0%}" for k, v in sorted(avail.items(), key=lambda kv: kv[1])))
    new = team_moji(con, NEW, [OLD, OLDER], rookies, avail)
    proj = {}
    for t in A:
        roster_change = b * (new[t][0] - old[t][0])
        p = .5 * (net_old[t] + roster_change) + .5 * (a0 + b * new[t][0])
        proj[t] = REGRESS * p
    mean = np.mean(list(proj.values()))
    proj = {t: v - mean for t, v in proj.items()}

    # game-level noise, measured: margin around the season net-rating gap + HCA
    hca = gf._MOJI_CONSTANTS["HCA_MEASURED"]
    res = []
    reg = rows(con, "SELECT game_date d, home_team_id h, away_team_id a, home_score hs, away_score as_ FROM games WHERE season_id=? AND home_score IS NOT NULL", [OLD])
    per_day = defaultdict(int)
    for g in reg:
        per_day[g["d"]] += 1
    end = max(d for d, n in per_day.items() if n >= 10)          # last full regular-season day
    for g in (g for g in reg if g["d"] <= end):
        inv = {v: k for k, v in teams.items()}
        if g["h"] in inv and g["a"] in inv:
            res.append((g["hs"] - g["as_"]) - (net_old[inv[g["h"]]] - net_old[inv[g["a"]]] + hca))
    game_sd = float(np.std(res))
    print(f"game sd {game_sd:.1f} from {len(res)} games, HCA {hca}")

    # 4. the schedule
    sched_path = os.path.join(OUT_DIR, "schedule_2026-27.json")
    if os.path.exists(sched_path):
        sched = json.load(open(sched_path))["games"]
    else:
        sched = espn_schedule()
        json.dump({"source": "ESPN team schedules, seasontype=2", "captured": datetime.now().strftime("%Y-%m-%d"),
                   "games": sched}, open(sched_path, "w"))
    played = defaultdict(int)
    for _, h, aw in sched:
        played[h] += 1; played[aw] += 1
    print(f"schedule: {len(sched)} games; per team {min(played.values())}-{max(played.values())} (Cup knockout games added as neutral)")
    idx = {t: i for i, t in enumerate(A)}
    H = np.array([idx[h] for _, h, _ in sched]); W = np.array([idx[a] for _, _, a in sched])
    dates = [datetime.strptime(d, "%Y-%m-%d").toordinal() for d, _, _ in sched]
    last = {}
    b2b_h = np.zeros(len(sched)); b2b_a = np.zeros(len(sched))
    order = sorted(range(len(sched)), key=lambda i: dates[i])
    for i in order:
        _, h, aw = sched[i]
        if last.get(h) == dates[i] - 1: b2b_h[i] = 1
        if last.get(aw) == dates[i] - 1: b2b_a[i] = 1
        last[h] = dates[i]; last[aw] = dates[i]
    sit = hca - b2b_h * gf._MOJI_CONSTANTS["B2B_HOME"] + b2b_a * gf._MOJI_CONSTANTS["B2B_ROAD"]

    rng = np.random.default_rng(args.seed)
    P = np.array([proj[t] for t in A])
    wins = np.zeros((args.n, 30), dtype=np.int16)
    chunk = 2000
    for s in range(0, args.n, chunk):
        n = min(chunk, args.n - s)
        true = P + rng.normal(0, TEAM_SD, (n, 30))
        mu = true[:, H] - true[:, W] + sit
        home_win = rng.normal(mu, game_sd) > 0
        w = np.zeros((n, 30), dtype=np.int16)
        np.add.at(w.T, H, home_win.T.astype(np.int16)); np.add.at(w.T, W, (~home_win).T.astype(np.int16))
        # Cup knockout games still unscheduled: vs a league-average opponent, neutral floor
        for t in A:
            k = 82 - played[t]
            if k > 0:
                pw = 0.5 * (1 + np.vectorize(math.erf)(true[:, idx[t]] / (game_sd * math.sqrt(2))))
                w[:, idx[t]] += rng.binomial(k, pw).astype(np.int16)
        wins[s:s + n] = w

    market = json.load(open(os.path.join(OUT_DIR, "market_2026-27_betmgm.json")))
    board = []
    for t in A:
        line, o, u = market["lines"][t]
        wt = wins[:, idx[t]]
        p_over = float((wt > line).mean())
        mkt_over = no_vig(o, u)
        side = "OVER" if p_over >= .5 else "UNDER"
        p_side = p_over if side == "OVER" else 1 - p_over
        price = o if side == "OVER" else u
        dec = 1 + (price / 100 if price > 0 else 100 / -price)
        board.append({
            "team": t, "line": line, "over": o, "under": u,
            "sim_mean": round(float(wt.mean()), 1), "sim_median": float(np.median(wt)),
            "p10": int(np.percentile(wt, 10)), "p90": int(np.percentile(wt, 90)),
            "proj_net": round(proj[t], 1), "moji_new": round(new[t][0], 1), "moji_old": round(old[t][0], 1),
            "net_old": round(net_old[t], 1),
            "p_over": round(p_over, 3), "market_p_over": round(mkt_over, 3),
            "side": side, "p_side": round(p_side, 3), "price": price,
            "ev_per_unit": round(p_side * (dec - 1) - (1 - p_side), 3),
            "gap_wins": round(float(wt.mean()) - line, 1),
            "rotation": [{"name": p[0], "mojo": p[1], "min": round(p[2], 1), "line": p[3]} for p in new[t][1][:9]],
        })
    board.sort(key=lambda r: -abs(r["gap_wins"]))
    out = {"season": NEW, "run": datetime.now().isoformat(timespec="seconds"), "n_seasons": args.n,
           "fit": {"a": round(float(a0), 2), "b": round(float(b), 3), "r2": round(float(r2), 3)},
           "game_sd": round(game_sd, 2), "team_sd": TEAM_SD, "regress": REGRESS,
           "context": {"espn_captured": ctx["captured"], "rookie_fit_n": n_fit,
                       "injured": {k: round(v, 2) for k, v in avail.items()}},
           "market": market["source"], "market_captured": market["captured"], "board": board}
    json.dump(out, open(os.path.join(OUT_DIR, "sim_2026-27.json"), "w"), indent=1)
    # the public board for the site: lines, the sim's number and range, no model internals
    names = {r["abbreviation"]: (r["team_id"], r["full_name"]) for r in rows(con, "SELECT team_id, abbreviation, full_name FROM teams")}
    public = {"season": NEW, "run": out["run"][:10], "seasons_played": args.n,
              "book": "BetMGM", "book_date": market["captured"],
              "teams": [{"team": r["team"], "team_id": names[r["team"]][0], "name": names[r["team"]][1],
                         "line": r["line"], "sim": r["sim_mean"], "low": r["p10"], "high": r["p90"],
                         "side": r["side"], "price": r["price"]} for r in board]}
    json.dump(public, open(os.path.join(ROOT, "..", "ledger", "nba", "win-totals-2026-27.json"), "w"), indent=1)
    print(f"\n{'team':5}{'line':>6}{'sim':>7}{'gap':>6}  {'10-90%':>9}  {'side':6}{'P(side)':>8}{'mkt':>6}{'EV/u':>7}  net'26 -> proj")
    for r in board:
        mk = r["market_p_over"] if r["side"] == "OVER" else 1 - r["market_p_over"]
        print(f"{r['team']:5}{r['line']:>6}{r['sim_mean']:>7}{r['gap_wins']:>+6}  {r['p10']:>4}-{r['p90']:<4}  {r['side']:6}{r['p_side']:>8.0%}{mk:>6.0%}{r['ev_per_unit']:>+7.2f}  {r['net_old']:+5.1f} -> {r['proj_net']:+5.1f}")


if __name__ == "__main__":
    main()

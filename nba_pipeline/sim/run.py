"""Run the possession sim on tonight's slate and print it next to the book.

  cd nba_pipeline && python3 -m sim.run [--sims 5000] [--json out.json]

Rosters and OUT/starters come from the same RotoWire scrape the dashboard
uses; book lines from the same merge (RotoWire, then the Odds API).
"""

import argparse
import json
import logging
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.WARNING)

import generate_frontend as gf  # noqa: E402
from config import CURRENT_SEASON  # noqa: E402
from sim import engine, players  # noqa: E402

# NBA results scatter about 13 points around a good pregame line; the engine's
# independent possessions run wider (~16.5), so its margins are narrowed to this
# around their mean before any chance is read. To be refit on the backtest.
MARGIN_SD = 13.0
LOGGED = {}                       # "AWY@HOM" -> (side, line) for a printed cover chance; filled by --picks


def team(abbr, lineups, lg, con):
    roster = gf._get_full_roster(abbr)
    info = lineups.get(abbr, {})
    out_ids, _ = gf._resolve_out_ids(info, roster, abbr, "possession sim")
    starters = []
    for name, _pos, status in info.get("starters", []):
        pid = gf._match_player_name(name, roster)
        if pid is not None and status != "OUT":
            starters.append(int(pid))
    return players.team_inputs(roster, out_ids, starters, lg, con), roster


def pace_of(con, abbr):
    r = con.execute("SELECT c.pace_value FROM coaching_profiles c JOIN teams t ON t.team_id=c.team_id "
                    "WHERE t.abbreviation=? AND c.season_id=?", (abbr, CURRENT_SEASON)).fetchone()
    return r[0] if r and r[0] else None


def calibrate(lg, con, sims=1500):
    """Scale so the league's 30 offenses, against an average defense, average the
    league's offensive rating."""
    avg = engine.average_team(lg)
    ratings = []
    for abbr in [r[0] for r in con.execute("SELECT abbreviation FROM teams")]:
        roster = gf._get_full_roster(abbr)
        if roster.empty:
            continue
        o = players.team_inputs(roster, set(), (), lg, con)
        res = engine.simulate(o, avg, lg, sims=sims, hca=0.0)
        ratings.append(res["home_pts"].mean() / lg["pace"] * 100)
    return lg["ortg"] / float(np.mean(ratings))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=5000)
    ap.add_argument("--impact", type=float, default=0.5)
    ap.add_argument("--json")
    ap.add_argument("--picks", help='JSON {"AWY@HOM": ["SIDE", line]} to print a cover chance')
    args = ap.parse_args()
    logged = json.loads(args.picks) if args.picks else LOGGED
    con = players._db()
    lg = players.league(con)
    scale = calibrate(lg, con)
    lineups, lines, pairs, _date, _times = gf.scrape_rotowire()
    rows = []
    for home, away in pairs:
        h, hr = team(home, lineups, lg, con)
        a, ar = team(away, lineups, lg, con)
        pace = np.mean([p for p in (pace_of(con, home), pace_of(con, away)) if p] or [lg["pace"]])
        res = engine.simulate(h, a, lg, sims=args.sims, pace=pace, impact_w=args.impact, scale=scale)
        raw = res["margin"]
        mg = raw.mean() + (raw - raw.mean()) * MARGIN_SD / raw.std()
        book = lines.get((home, away), {})
        g = f"{away}@{home}"
        row = {"game": g, "sim_home_spread": round(-float(np.mean(mg)) * 2) / 2,
               "sim_total": round(float(np.mean(res["home_pts"] + res["away_pts"])), 1),
               "home_win": round(float(np.mean(mg > 0)), 3), "sd": round(float(np.std(raw)), 1),
               "book_home_spread": book.get("spread"), "book_total": book.get("total"),
               "home_top": sorted(zip(h["names"], res["home_box"].mean(0).round(1), h["min"].round(1)), key=lambda x: -x[1])[:5],
               "away_top": sorted(zip(a["names"], res["away_box"].mean(0).round(1), a["min"].round(1)), key=lambda x: -x[1])[:5]}
        if g in logged:
            side, line = logged[g]
            m = mg if side == home else -mg
            row["logged"] = f"{side} {line:+g}"
            row["cover"] = round(float(np.mean(m + line > 0) + 0.5 * np.mean(m + line == 0)), 3)
        rows.append(row)
    print(f"scale {scale:.3f} · league ORtg {lg['ortg']:.1f} · pace {lg['pace']:.1f}")
    for r in rows:
        line = f"{r['game']:9} book {r['book_home_spread']!s:>6}  sim {r['sim_home_spread']:+6.1f} (sd {r['sd']})  " \
               f"total book {r['book_total']!s:>6} sim {r['sim_total']:6.1f}  home win {r['home_win']:.0%}"
        if "logged" in r:
            line += f"   logged {r['logged']}: covers {r['cover']:.0%}"
        print(line)
    if args.json:
        json.dump(rows, open(args.json, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

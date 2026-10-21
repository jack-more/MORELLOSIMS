"""Engine check: every team's offense against a league-average defense; each
player's simulated points per 36 against his actual season line.

  cd nba_pipeline && python3 -m sim.validate
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generate_frontend as gf  # noqa: E402
from config import previous_season, CURRENT_SEASON  # noqa: E402
from sim import engine, players  # noqa: E402


def main(sims=1500):
    con = players._db()
    lg = players.league(con)
    avg = engine.average_team(lg)
    rows, team_ortg = [], []
    for (abbr,) in con.execute("SELECT abbreviation FROM teams"):
        roster = gf._get_full_roster(abbr)
        if roster.empty:
            continue
        o = players.team_inputs(roster, set(), (), lg, con, abbr=abbr)
        res = engine.simulate(o, avg, lg, sims=sims, hca=0.0)
        team_ortg.append((abbr, res["home_pts"].mean() / lg["pace"] * 100))
        for i, pid in enumerate(o["pids"]):
            r = con.execute("SELECT pts_per36, minutes_per_game, gp FROM player_season_stats "
                            "WHERE player_id=? AND season_id=?", (pid, previous_season(CURRENT_SEASON))).fetchone()
            if r and r[0] and (r[2] or 0) >= 20 and (r[1] or 0) >= 15:
                rows.append((o["names"][i], abbr, res["home_box"][:, i].mean() / o["min"][i] * 36, r[0], o["usg"][i]))
    sim36 = np.array([r[2] for r in rows]); act36 = np.array([r[3] for r in rows])
    print(f"{len(rows)} players · pts/36 sim vs actual: r={np.corrcoef(sim36, act36)[0, 1]:.2f}  "
          f"bias {np.mean(sim36 - act36):+.2f}  MAE {np.mean(abs(sim36 - act36)):.2f}")
    u = np.array([r[4] for r in rows])
    for lo, hi in ((0, 0.18), (0.18, 0.24), (0.24, 0.30), (0.30, 1)):
        k = (u >= lo) & (u < hi)
        print(f"  usage {lo:.2f}-{hi:.2f}: {k.sum():3d} players, bias {np.mean(sim36[k] - act36[k]):+.2f}")
    top = sorted(rows, key=lambda r: -r[3])[:12]
    for n, t, s, a, _u in top:
        print(f"  {n:24} {t}  sim {s:5.1f}  actual {a:5.1f}")
    o = sorted(team_ortg, key=lambda x: -x[1])
    print("ORtg vs average D, best/worst:", [(a, round(v, 1)) for a, v in o[:4]], [(a, round(v, 1)) for a, v in o[-4:]])


if __name__ == "__main__":
    main()

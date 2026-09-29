#!/usr/bin/env python3
"""measure_hca.py — home-court advantage and back-to-back effects from nba_sim.db.

Regular season = games on or before the last date of the season with 10+
games (the final regular-season day has all 30 teams; playoff days never
exceed 8 games). Prints, per season:
  * raw mean home margin (the HCA_MEASURED constant in generate_frontend.py)
  * OLS: margin ~ HCA + home_b2b + away_b2b + team strength dummies

Usage: python scripts/measure_hca.py [--db path]
"""

import argparse
import os
import sqlite3
import sys
from collections import Counter
from datetime import date, timedelta

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import DB_PATH  # noqa: E402


def regular_season_games(con, season):
    rows = con.execute(
        "SELECT game_date, home_team_id, away_team_id, home_score, away_score FROM games "
        "WHERE season_id = ? AND home_score IS NOT NULL", [season]).fetchall()
    per_day = Counter(r[0] for r in rows)
    big_days = [d for d, n in per_day.items() if n >= 10]
    if not big_days:
        return []
    end = max(big_days)
    return [r for r in rows if r[0] <= end]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_PATH)
    args = ap.parse_args()
    con = sqlite3.connect(args.db)
    seasons = [r[0] for r in con.execute("SELECT DISTINCT season_id FROM games ORDER BY season_id")]
    pooled = []
    for season in seasons:
        rows = regular_season_games(con, season)
        if len(rows) < 200:
            continue
        played = {(r[0], r[1]) for r in rows} | {(r[0], r[2]) for r in rows}
        teams = sorted({r[1] for r in rows} | {r[2] for r in rows})
        ti = {t: i for i, t in enumerate(teams)}
        X, y = [], []
        for d, h, a, hs, as_ in rows:
            prev = (date.fromisoformat(d) - timedelta(days=1)).isoformat()
            x = np.zeros(3 + len(teams))
            x[0], x[1], x[2] = 1.0, (prev, h) in played, (prev, a) in played
            x[3 + ti[h]] += 1
            x[3 + ti[a]] -= 1
            X.append(x)
            y.append(hs - as_)
        X, y = np.array(X)[:, :-1], np.array(y, dtype=float)
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        pooled.extend(y)
        print(f"{season}: n={len(y)} mean home margin {y.mean():+.2f} | OLS HCA {beta[0]:+.2f}, "
              f"home B2B {beta[1]:+.2f}, road B2B {-beta[2]:+.2f} (effect on the road team)")
    if pooled:
        print(f"pooled mean home margin: {np.mean(pooled):+.2f} (n={len(pooled)})")


if __name__ == "__main__":
    main()

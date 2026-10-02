#!/usr/bin/env python3
"""backfill_espn_lineups.py — one-off: rebuild a finished season's lineup tables
from ESPN play-by-play and re-derive the next season's seeded priors from them.

2025-26: stats.nba.com lineup_stats froze after the games of 2026-02-12 (56 GP),
so the 2026-27 seeds (lineups, pair synergy, value scores) were built from
two-thirds of a season. This:

  1. re-parses every --season game from ESPN (--cache recommended: ~1,300
     summaries) so espn_lineup_games holds its five-man units, and rebuilds
     lineup_stats / lineup_players for the season (collectors/espn_lineups.py);
  2. recomputes the season's pair_synergy and player_value_scores;
  3. if the next season has no games yet (its lineup / synergy rows can only
     be seeds), clears its lineup_stats / lineup_players / pair_synergy and
     rebuilds them the way the daily jobs do: seed_season.py, then the
     trends refresh's pair synergy + value scores, then seed_season.py again.

  python scripts/backfill_espn_lineups.py --season 2025-26 --start 2025-10-21 --end 2026-06-30 [--cache DIR]
"""

import argparse
import logging
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DB_PATH  # noqa: E402
from analysis.synergy import PairSynergyCalculator  # noqa: E402
from analysis.value_scores import ValueScoreCalculator  # noqa: E402
from espn_stats_sync import sync  # noqa: E402
from seed_season import seed  # noqa: E402


def next_season(season):
    start = int(season[:4]) + 1
    return f"{start}-{(start + 1) % 100:02d}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--season", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--cache")
    ap.add_argument("--db", default=DB_PATH)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    res = sync(args.db, args.season, args.start, args.end, cache=args.cache, refetch=True)
    print(f"{args.season}: {res['games']} games re-parsed; lineup_stats: {res.get('lineup_stats')}")
    PairSynergyCalculator(args.db).compute_pair_synergies(args.season)
    ValueScoreCalculator(args.db).compute_all(args.season)

    nxt = next_season(args.season)
    con = sqlite3.connect(args.db)
    played = con.execute("SELECT COUNT(*) FROM games WHERE season_id = ? AND home_score IS NOT NULL", [nxt]).fetchone()[0]
    if played:
        print(f"{nxt} has {played} scored games: its rows are real data, seeds left alone")
        return 0
    for t in ("lineup_players", "lineup_stats", "pair_synergy"):
        n = con.execute(f"DELETE FROM {t} WHERE season_id = ?", [nxt]).rowcount
        print(f"{nxt}: cleared {n} seeded/derived {t} rows")
    con.commit()
    con.close()
    print(f"{nxt} seeds:", seed(args.db, nxt, args.season))
    PairSynergyCalculator(args.db).compute_pair_synergies(nxt)
    ValueScoreCalculator(args.db).compute_all(nxt)
    print(f"{nxt} seeds (after synergy):", seed(args.db, nxt, args.season))
    return 0


if __name__ == "__main__":
    sys.exit(main())

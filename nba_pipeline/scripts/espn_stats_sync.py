#!/usr/bin/env python3
"""espn_stats_sync.py — keep box scores and season stats current from ESPN.

stats.nba.com blocks GitHub Actions IPs, so this is the path that guarantees
player_game_stats, player_season_stats, team_season_stats and lineup_stats /
lineup_players (2-5 man groups from play-by-play stints,
collectors/espn_lineups.py) stay current.

Daily (no dates given): every scored game of the season in `games` that has
no ESPN box score yet, plus the last --days days (catches games the games
table hasn't seen), then the season aggregates.

Backfill: --start/--end walk the ESPN scoreboard day by day.

  python scripts/espn_stats_sync.py                         # daily, CURRENT_SEASON
  python scripts/espn_stats_sync.py --season 2025-26 --start 2026-02-24 --end 2026-06-30
  python scripts/espn_stats_sync.py --no-pgs                # espn_* tables only
  python scripts/espn_stats_sync.py --stats-only            # just rebuild aggregates

Exit code 1 only when there were games to fetch and ESPN answered none of
them; partial failures are logged and retried on the next run.
"""

import argparse
import logging
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import DB_PATH, CURRENT_SEASON  # noqa: E402
from collectors.espn_boxscores import ESPNBoxScoreCollector, SCHEMA  # noqa: E402
from collectors.espn_season_stats import write_season_stats, coverage_gaps  # noqa: E402
from collectors.espn_lineups import write_lineup_stats  # noqa: E402

logger = logging.getLogger("espn_stats_sync")


def daily_dates(db_path, season, days):
    """Dates of scored games without an ESPN box score, plus the last `days` days."""
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    gaps = coverage_gaps(conn, season)
    dates = set()
    if gaps:
        ph = ",".join("?" * len(gaps))
        dates |= {r[0] for r in conn.execute(f"SELECT DISTINCT game_date FROM games WHERE game_id IN ({ph})", gaps)}
    conn.close()
    today = datetime.now(timezone.utc).date()
    dates |= {(today - timedelta(days=i)).isoformat() for i in range(days)}
    return sorted(dates), len(gaps)


def sync(db_path=DB_PATH, season=CURRENT_SEASON, start=None, end=None, days=4, cache=None,
         fill_pgs=True, season_stats=True, refetch=False) -> dict:
    """Fetch/store ESPN box scores, then rebuild season stats. Returns a summary."""
    if start:
        s = datetime.strptime(start, "%Y-%m-%d")
        e = datetime.strptime(end, "%Y-%m-%d") if end else datetime.now(timezone.utc).replace(tzinfo=None)
        dates = [(s + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((e - s).days + 1)]
        gaps = None
    else:
        dates, gaps = daily_dates(db_path, season, days)
        logger.info(f"{season}: {gaps} scored games without an ESPN box score; checking {len(dates)} date(s)")
    col = ESPNBoxScoreCollector(db_path, cache_dir=cache)
    tot = {"games": 0, "failed": 0, "pgs_rows": 0, "games_inserted": 0}
    for d in dates:
        r = col.collect_date(datetime.strptime(d, "%Y-%m-%d"), season, fill_pgs=fill_pgs, refetch=refetch)
        for k in tot:
            tot[k] += r.get(k, 0)
        if r.get("games") or r.get("pgs_rows"):
            logger.info(f"  {d}: {r.get('games', 0)} games, {r.get('pgs_rows', 0)} player_game_stats rows")
    logger.info(f"ESPN box scores: {tot['games']} games stored, {tot['pgs_rows']} player_game_stats rows, "
                f"{tot['games_inserted']} games added to `games`, {tot['failed']} failed")
    if col.pbp_fallbacks:
        logger.info(f"  {len(col.pbp_fallbacks)} game(s) used box minutes (play-by-play did not reconcile)")
    if col.unmatched:
        logger.warning(f"  {len(col.unmatched)} new ESPN athlete(s) without an NBA id -> synthetic ids: "
                       + ", ".join(n for n, _ in list(col.unmatched.values())[:40]))
    tot["unmatched"] = [n for n, _ in col.unmatched.values()]
    tot["gaps_before"] = gaps
    if season_stats:
        tot["season_stats"] = write_season_stats(db_path, season)
        tot["lineup_stats"] = write_lineup_stats(db_path, season)
    return tot


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--season", default=CURRENT_SEASON)
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--days", type=int, default=4, help="daily mode: also re-check the last N days")
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--cache", help="gzip cache dir for ESPN summaries (backfills)")
    ap.add_argument("--no-pgs", action="store_true", help="do not fill player_game_stats")
    ap.add_argument("--no-season-stats", action="store_true")
    ap.add_argument("--stats-only", action="store_true")
    ap.add_argument("--refetch", action="store_true", help="re-parse games already stored")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if args.stats_only:
        write_season_stats(args.db, args.season)
        write_lineup_stats(args.db, args.season)
        return 0
    tot = sync(args.db, args.season, args.start, args.end, args.days, args.cache,
               fill_pgs=not args.no_pgs, season_stats=not args.no_season_stats, refetch=args.refetch)
    if tot["failed"] and not tot["games"] and tot.get("gaps_before"):
        logger.error("ESPN returned nothing for any missing game")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

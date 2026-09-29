#!/usr/bin/env python3
"""Fail the NBA pipeline when the model's inputs lag the games being played.

2025-26: stats.nba.com blocks GitHub Actions IPs, so box scores stopped at
2026-02-23 and team/player season stats at 62-65 GP, while ESPN kept the
`games` table current through the Finals. The old check only printed a
::warning:: and the model priced ~4 months of games, the whole tracked
playoff run included, on early-March numbers. Now: if completed games
exist that the stats haven't caught up to, fail loudly.

Offseason (no completed game in the last LOOKBACK_DAYS) passes.
"""
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CURRENT_SEASON, DB_PATH  # noqa: E402

MAX_LAG_DAYS = 3      # box scores may trail the latest final by this much
MAX_GP_LAG = 3        # team season stats may trail games played by this many
LOOKBACK_DAYS = 10    # "in season" = a counted game finished this recently
REGULAR_SEASON_GAMES = 82


def main():
    conn = sqlite3.connect(DB_PATH)
    today = datetime.now(timezone.utc).date()
    latest_game = conn.execute(
        "SELECT MAX(game_date) FROM games WHERE home_score IS NOT NULL AND season_id = ?",
        [CURRENT_SEASON]).fetchone()[0]
    if not latest_game or latest_game < (today - timedelta(days=LOOKBACK_DAYS)).isoformat():
        print(f"Offseason for {CURRENT_SEASON} (latest final: {latest_game}); freshness not enforced")
        return 0

    errors = []
    latest_box = conn.execute(
        "SELECT MAX(g.game_date) FROM player_game_stats p JOIN games g ON g.game_id = p.game_id "
        "WHERE g.season_id = ?", [CURRENT_SEASON]).fetchone()[0]
    lag = (datetime.fromisoformat(latest_game) - datetime.fromisoformat(latest_box)).days if latest_box else None
    if lag is None or lag > MAX_LAG_DAYS:
        errors.append(f"box scores end {latest_box}, games run through {latest_game}")

    played = dict(conn.execute(
        "SELECT team_id, COUNT(*) FROM (SELECT home_team_id AS team_id FROM games WHERE season_id = ? "
        "AND home_score IS NOT NULL UNION ALL SELECT away_team_id FROM games WHERE season_id = ? "
        "AND home_score IS NOT NULL) GROUP BY team_id", [CURRENT_SEASON, CURRENT_SEASON]).fetchall())
    gp = dict(conn.execute("SELECT team_id, gp FROM team_season_stats WHERE season_id = ?",
                           [CURRENT_SEASON]).fetchall())
    # games also holds play-in/playoff games (ESPN ids carry no season type)
    # while team_season_stats is regular season only: cap at 82.
    played = {t: min(n, REGULAR_SEASON_GAMES) for t, n in played.items()}
    behind = [(t, gp.get(t, 0), n) for t, n in played.items() if n - (gp.get(t) or 0) > MAX_GP_LAG]
    if behind:
        errors.append(f"team season stats behind games for {len(behind)} teams "
                      f"(e.g. team {behind[0][0]}: {behind[0][1]} GP in stats vs {behind[0][2]} played)")

    if errors:
        for e in errors:
            print(f"::error title=NBA model inputs are stale::{e}")
        print("Refusing to price picks on stale inputs.")
        return 1
    print(f"Freshness OK: box scores through {latest_box}, games through {latest_game}, "
          f"team stats within {MAX_GP_LAG} GP")
    return 0


if __name__ == "__main__":
    sys.exit(main())

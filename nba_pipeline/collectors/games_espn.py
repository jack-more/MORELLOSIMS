"""Collect game schedule and results from ESPN's public scoreboard API.

Primary source for game scores. When ESPN cannot be reached (it has answered
GitHub Actions runners with HTTP 403), grading falls back to the `games` table
in nba_sim.db.

Uses the ESPN scoreboard endpoint:
  https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard

Provides:
  - ESPNGameCollector class for DB upserts (used by the pipeline)
  - fetch_espn_events()         all events for a date (season type, tip time)
  - fetch_scores_for_grading()  for scripts/grade_picks.py (ESPN + DB fallback)
  - fetch_single_game_score()   for scripts/inject_pick.py
"""

import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

import pandas as pd

from db.connection import read_query, execute, save_dataframe, load_team_map
from config import DB_PATH
from utils.constants import ESPN_ABBR_MAP

logger = logging.getLogger(__name__)

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

# ESPN's edge answers some header sets with HTTP 403 (bot management).
# Measured 2026-09-29 from a residential IP: urllib's default UA and curl's UA
# get 200; the old "Mozilla/5.0 (compatible; NBASIM/1.0)" UA gets 403 unless an
# Accept header is sent; a bare desktop-Chrome UA (without the rest of a real
# browser's headers) gets 403 every time. Try the plain profiles first and
# rotate on 403/429, ending with the browser-like profiles.
ESPN_HEADER_PROFILES = [
    {"Accept": "application/json"},
    {"Accept": "application/json, text/plain, */*", "User-Agent": "curl/8.7.1"},
    {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.espn.com/",
        "Origin": "https://www.espn.com",
        "User-Agent": "Mozilla/5.0 (compatible; NBASIM/1.0)",
    },
    {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.espn.com/nba/scoreboard",
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    },
]

# ESPN season types: 1 preseason, 2 regular season, 3 postseason, 5 play-in.
# Preseason games are never stored, priced, or graded.
COUNTED_SEASON_TYPES = {2, 3, 5}


def _normalize_abbr(espn_abbr: str) -> str:
    """Convert ESPN team abbreviation to standard 3-letter NBA abbreviation."""
    return ESPN_ABBR_MAP.get(espn_abbr, espn_abbr)


def espn_get_json(url: str, timeout: int = 15) -> dict | None:
    """GET an ESPN JSON endpoint, rotating header profiles on 403/429.

    Returns parsed JSON, or None if every profile failed.
    """
    last_err = None
    for headers in ESPN_HEADER_PROFILES:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (403, 429):
                continue
            break
        except Exception as e:  # timeouts, DNS, bad JSON
            last_err = e
            continue
    logger.warning(f"ESPN fetch failed for {url}: {last_err}")
    return None


def fetch_espn_events(date: datetime) -> list[dict] | None:
    """All NBA events ESPN lists for one date (any status, any season type).

    Returns None when ESPN could not be reached (callers fall back to the DB),
    else a list of dicts with keys: game_date, home_abbr, away_abbr,
    home_score, away_score, completed, state, season_type, tip_utc (ISO UTC).
    """
    data = espn_get_json(f"{SCOREBOARD_URL}?dates={date.strftime('%Y%m%d')}")
    if data is None:
        return None

    events = []
    for event in data.get("events", []):
        competition = event.get("competitions", [{}])[0]
        status = competition.get("status", {}).get("type", {})
        home = away = None
        for team_entry in competition.get("competitors", []):
            if team_entry.get("homeAway") == "home":
                home = team_entry
            else:
                away = team_entry
        if not home or not away:
            continue

        tip = event.get("date") or competition.get("date") or ""
        try:
            tip_utc = datetime.strptime(tip, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            tip_utc = None
        season_type = (event.get("season") or {}).get("type")
        try:
            home_score = int(home.get("score", 0) or 0)
            away_score = int(away.get("score", 0) or 0)
        except (TypeError, ValueError):
            home_score = away_score = 0

        events.append({
            "game_date": date.strftime("%Y-%m-%d"),
            "home_abbr": _normalize_abbr(home["team"]["abbreviation"]),
            "away_abbr": _normalize_abbr(away["team"]["abbreviation"]),
            "home_score": home_score,
            "away_score": away_score,
            "completed": bool(status.get("completed", False)),
            "state": status.get("state", ""),
            "season_type": int(season_type) if season_type is not None else None,
            "tip_utc": tip_utc,
        })
    return events


def _fetch_espn_day(date: datetime) -> list[dict]:
    """Completed, counted (regular / post / play-in) games for one date.

    Returns [] when ESPN is unreachable; use fetch_espn_events() to tell
    "no games" from "fetch failed".
    """
    events = fetch_espn_events(date)
    if not events:
        return []
    return [
        e for e in events
        if e["completed"] and (e["season_type"] is None or e["season_type"] in COUNTED_SEASON_TYPES)
    ]


# ── Standalone convenience functions ────────────────────────────────


def score_key(date_iso: str, matchup: str) -> str:
    """Compose the canonical (date, matchup) lookup key.
    NBA teams meet 3-4 times per season; without the date, a March BKN @ CLE
    pick could be graded against the April BKN @ CLE result."""
    return f"{date_iso}|{matchup}"


def db_scores_for_dates(dates: list[str], db_path: str = DB_PATH) -> dict:
    """Final scores from nba_sim.db `games`, keyed like fetch_scores_for_grading."""
    if not dates:
        return {}
    placeholders = ",".join("?" for _ in dates)
    df = read_query(
        f"""SELECT g.game_date, h.abbreviation AS home_abbr, a.abbreviation AS away_abbr,
                   g.home_score, g.away_score
            FROM games g
            JOIN teams h ON h.team_id = g.home_team_id
            JOIN teams a ON a.team_id = g.away_team_id
            WHERE g.game_date IN ({placeholders})
              AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL""",
        db_path, list(dates),
    )
    out = {}
    for _, r in df.iterrows():
        matchup = f"{r['away_abbr']} @ {r['home_abbr']}"
        out[score_key(r["game_date"], matchup)] = {
            "home_abbr": r["home_abbr"],
            "away_abbr": r["away_abbr"],
            "home_score": int(r["home_score"]),
            "away_score": int(r["away_score"]),
            "game_date": r["game_date"],
            "tip_utc": None,
            "source": "nba_sim.db",
        }
    return out


def fetch_scores_for_grading(days: int = 7, dates: list[str] | None = None,
                             db_fallback: bool = True) -> dict:
    """Final scores keyed by (date, matchup) for pick grading.

    ESPN first. Dates ESPN could not serve (HTTP 403 on Actions runners,
    timeouts) and games ESPN did not return are filled from nba_sim.db.

    Returns: {"YYYY-MM-DD|AWAY @ HOME": {home_abbr, away_abbr, home_score,
              away_score, game_date, tip_utc, source}}
    Used by: scripts/grade_picks.py — callers MUST use score_key(pick_date, matchup).
    """
    if dates is None:
        today = datetime.now(timezone.utc)
        dates = [(today - timedelta(days=o)).strftime("%Y-%m-%d") for o in range(days)]
    dates = sorted(set(dates))
    scores = {}
    tips = {}
    failed = []

    for iso in dates:
        events = fetch_espn_events(datetime.strptime(iso, "%Y-%m-%d"))
        if events is None:
            failed.append(iso)
            continue
        for game in events:
            key = score_key(game["game_date"], f"{game['away_abbr']} @ {game['home_abbr']}")
            tips[key] = game["tip_utc"]
            if not game["completed"]:
                continue
            if game["season_type"] is not None and game["season_type"] not in COUNTED_SEASON_TYPES:
                continue
            scores[key] = {
                "home_abbr": game["home_abbr"],
                "away_abbr": game["away_abbr"],
                "home_score": game["home_score"],
                "away_score": game["away_score"],
                "game_date": game["game_date"],
                "tip_utc": game["tip_utc"],
                "source": "espn",
            }

    if db_fallback:
        try:
            db_scores = db_scores_for_dates(dates)
        except Exception as e:  # DB unavailable — ESPN results still stand
            logger.warning(f"DB score fallback failed: {e}")
            db_scores = {}
        filled = 0
        for key, game in db_scores.items():
            if key not in scores:
                scores[key] = dict(game, tip_utc=tips.get(key))
                filled += 1
        if failed or filled:
            logger.info(f"DB fallback: ESPN failed for {len(failed)} date(s); "
                        f"{filled} game(s) filled from nba_sim.db")

    logger.info(f"Grading scores: {len(scores)} completed games across {len(dates)} date(s)")
    return scores


def fetch_single_game_score(matchup: str, date_str: str) -> dict | None:
    """Final score (or current status) for one specific game.

    Args:
        matchup: "AWAY @ HOME" format, e.g. "BOS @ CLE"
        date_str: "YYYY-MM-DD"

    Returns: {home_score, away_score, status: "final", tip_utc, season_type}
             when final, {status, tip_utc, season_type} when not final, or
             None if not found.
    Used by: scripts/inject_pick.py
    """
    date = datetime.strptime(date_str, "%Y-%m-%d")
    away_team, home_team = [t.strip() for t in matchup.split(" @ ")]

    events = fetch_espn_events(date)
    for game in events or []:
        if game["home_abbr"] == home_team and game["away_abbr"] == away_team:
            if game["completed"]:
                return {
                    "home_score": game["home_score"],
                    "away_score": game["away_score"],
                    "status": "final",
                    "tip_utc": game["tip_utc"],
                    "season_type": game["season_type"],
                }
            return {"status": game["state"] or "scheduled", "tip_utc": game["tip_utc"],
                    "season_type": game["season_type"]}

    if events is None:
        db = db_scores_for_dates([date_str]).get(score_key(date_str, f"{away_team} @ {home_team}"))
        if db:
            return {"home_score": db["home_score"], "away_score": db["away_score"],
                    "status": "final", "tip_utc": None, "season_type": None}
    return None


def teams_played_on(date_iso: str, db_path: str = DB_PATH) -> set[str] | None:
    """Team abbreviations with a non-preseason game on date_iso.

    ESPN schedule first (covers games not yet in the DB), then nba_sim.db.
    Returns None only if neither source could answer.
    """
    events = fetch_espn_events(datetime.strptime(date_iso, "%Y-%m-%d"))
    if events is not None:
        return {
            abbr
            for e in events
            if e["season_type"] is None or e["season_type"] in COUNTED_SEASON_TYPES
            for abbr in (e["home_abbr"], e["away_abbr"])
        }
    try:
        df = read_query(
            """SELECT h.abbreviation AS home, a.abbreviation AS away FROM games g
               JOIN teams h ON h.team_id = g.home_team_id
               JOIN teams a ON a.team_id = g.away_team_id
               WHERE g.game_date = ?""",
            db_path, [date_iso],
        )
    except Exception as e:
        logger.warning(f"B2B schedule lookup failed for {date_iso}: {e}")
        return None
    return set(df["home"]) | set(df["away"])


# ── Class for pipeline DB operations ────────────────────────────────


class ESPNGameCollector:
    """Fetch game results from ESPN and upsert into the games table."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def fetch_date(self, date: datetime) -> list[dict]:
        """Completed regular/post-season games for a single date (no preseason)."""
        return _fetch_espn_day(date)

    def fetch_range(self, start_date: datetime, end_date: datetime) -> list[dict]:
        """Fetch completed games for a date range (inclusive)."""
        all_games = []
        current = start_date
        while current <= end_date:
            games = self.fetch_date(current)
            if games:
                logger.info(f"  {current.strftime('%Y-%m-%d')}: {len(games)} games")
            all_games.extend(games)
            current += timedelta(days=1)

        logger.info(f"ESPN: fetched {len(all_games)} completed games total")
        return all_games

    def fetch_recent(self, days: int = 7) -> list[dict]:
        """Fetch completed games for the last N days."""
        today = datetime.now(timezone.utc)
        start = today - timedelta(days=days - 1)
        return self.fetch_range(start, today)

    def update_games_table(self, season_id: str, days: int = 21) -> int:
        """Upsert recent games into the DB. Returns count of new/updated games.

        Args:
            season_id: e.g. '2025-26'
            days: How many days back to look (default 21 = 3 weeks)
        """
        team_map = load_team_map(self.db_path)
        scraped = self.fetch_recent(days)

        if not scraped:
            logger.warning("ESPN returned zero completed games")
            return 0

        # Load existing games for this season
        existing = read_query(
            "SELECT game_id, game_date, home_team_id, away_team_id, "
            "home_score, away_score FROM games WHERE season_id = ?",
            self.db_path, [season_id],
        )
        existing_lookup = {}
        for _, row in existing.iterrows():
            key = (row["game_date"], int(row["home_team_id"]),
                   int(row["away_team_id"]))
            existing_lookup[key] = {
                "game_id": row["game_id"],
                "home_score": row["home_score"],
                "away_score": row["away_score"],
            }

        new_games = []
        updated = 0
        skipped_teams = set()

        for game in scraped:
            home_id = team_map.get(game["home_abbr"])
            away_id = team_map.get(game["away_abbr"])

            if not home_id or not away_id:
                missing = []
                if not home_id:
                    missing.append(game["home_abbr"])
                if not away_id:
                    missing.append(game["away_abbr"])
                skipped_teams.update(missing)
                continue

            key = (game["game_date"], home_id, away_id)

            if key in existing_lookup:
                rec = existing_lookup[key]
                # Update scores if they were NULL
                if pd.isna(rec["home_score"]) or pd.isna(rec["away_score"]):
                    execute(
                        "UPDATE games SET home_score = ?, away_score = ? "
                        "WHERE game_id = ?",
                        self.db_path,
                        [game["home_score"], game["away_score"],
                         rec["game_id"]],
                    )
                    updated += 1
            else:
                # New game — generate synthetic ID
                game_id = (
                    f"espn_{game['game_date'].replace('-', '')}"
                    f"_{game['away_abbr']}_{game['home_abbr']}"
                )
                new_games.append({
                    "game_id": game_id,
                    "season_id": season_id,
                    "game_date": game["game_date"],
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                    "home_score": game["home_score"],
                    "away_score": game["away_score"],
                })

        if skipped_teams:
            logger.warning(
                f"Skipped games with unknown teams: {skipped_teams}"
            )

        # Insert new games
        if new_games:
            df = pd.DataFrame(new_games)
            save_dataframe(df, "games", self.db_path, if_exists="append")

        total = len(new_games) + updated
        logger.info(
            f"ESPN games update: {len(new_games)} inserted, "
            f"{updated} scores updated, "
            f"{len(scraped) - len(new_games) - updated} already current"
        )
        return total

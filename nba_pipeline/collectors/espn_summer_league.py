"""NBA Summer League box scores from ESPN (Las Vegas, Salt Lake City, California Classic, Sacramento).

utils/priors.py reads them for the players last season can't describe
(rookies, two-way players, anyone back from a lost season). Stored per
player-game in `summer_league_games`, keyed by ESPN ids. player_id is the
NBA id where one is known (espn_player_map, then a name match against
`players`); summer-only players stay NULL, and nothing here creates a
player row or a mapping, so a summer roster can't leak into the NBA tables.

  python -m collectors.espn_summer_league 2025 2026
"""

import logging
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from collectors.espn_boxscores import parse_box
from collectors.espn_ids import ESPNPlayerMapper, norm_name
from collectors.games_espn import espn_get_json

logger = logging.getLogger(__name__)

LEAGUES = ("nba-summer-las-vegas", "nba-summer-utah", "nba-summer-california", "nba-summer-sacramento")
SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/{}/scoreboard?dates={}"
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/{}/summary?event={}"
WINDOW = ((6, 25), (7, 31))   # summer league runs early July to the Las Vegas final (~July 20)
STATS = ("min", "pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb", "ast", "stl",
         "blk", "tov", "pf", "plus_minus")

SCHEMA = f"""CREATE TABLE IF NOT EXISTS summer_league_games (
    year INTEGER NOT NULL, league TEXT NOT NULL, event_id TEXT NOT NULL, game_date TEXT,
    espn_id TEXT NOT NULL, player_id INTEGER, name TEXT, team TEXT, started INTEGER,
    {", ".join(f"{s} REAL" for s in STATS)},
    PRIMARY KEY (event_id, espn_id))"""


def events(year):
    """[(league, event_id, date)] for every completed summer league game of `year`."""
    (m0, d0), (m1, d1) = WINDOW
    days = []
    d, end = date(year, m0, d0), date(year, m1, d1)
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    jobs = [(lg, d) for lg in LEAGUES for d in days]

    def scan(job):
        lg, d = job
        data = espn_get_json(SCOREBOARD.format(lg, d.strftime("%Y%m%d")), timeout=20) or {}
        return [(lg, e["id"], e["date"][:10]) for e in data.get("events", [])
                if ((e.get("status") or {}).get("type") or {}).get("completed")]

    with ThreadPoolExecutor(8) as ex:
        found = {ev[1]: ev for evs in ex.map(scan, jobs) for ev in evs}
    return sorted(found.values(), key=lambda e: (e[2], e[1]))


def collect(db_path, year):
    """Fetch and store every completed game of `year`'s summer league. Returns games stored."""
    con = sqlite3.connect(db_path)
    con.execute(SCHEMA)
    have = {r[0] for r in con.execute("SELECT DISTINCT event_id FROM summer_league_games WHERE year = ?", [year])}
    todo = [e for e in events(year) if e[1] not in have]
    logger.info(f"Summer league {year}: {len(have)} games stored, {len(todo)} to fetch")
    mapper = ESPNPlayerMapper(con)
    known = dict(con.execute("SELECT espn_id, player_id FROM espn_player_map"))  # ESPN ids are league-wide
    by_name = {}                                   # rostered players, synthetic ids included
    for pid, name in con.execute("SELECT DISTINCT p.player_id, p.full_name FROM players p "
                                 "JOIN roster_assignments ra ON ra.player_id = p.player_id"):
        by_name.setdefault(norm_name(name), set()).add(pid)

    def fetch(ev):
        return ev, espn_get_json(SUMMARY.format(ev[0], ev[1]), timeout=30)

    n = 0
    with ThreadPoolExecutor(6) as ex:
        for (lg, eid, gdate), summary in ex.map(fetch, todo):
            if not summary or "boxscore" not in summary:
                continue
            try:
                box = parse_box(summary)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"  {lg} {eid}: unparseable box ({e})")
                continue
            rows = []
            for p in box["players"].values():
                if p["dnp"] or not p["box_min"]:
                    continue
                same = by_name.get(norm_name(p["name"]), set())
                pid = (known.get(p["espn_id"]) or (next(iter(same)) if len(same) == 1 else None)
                       or mapper.lookup_real(p["name"])[0])
                team = box["teams"].get(p["espn_team"], {}).get("abbr")
                vals = {**p, "min": p["box_min"]}
                rows.append([year, lg, eid, gdate, p["espn_id"], pid, p["name"], team, p["started"]]
                            + [vals.get(s) for s in STATS])
            con.executemany(f"INSERT OR REPLACE INTO summer_league_games VALUES ({','.join('?' * (9 + len(STATS)))})",
                            rows)
            n += 1
    con.commit()
    con.close()
    logger.info(f"Summer league {year}: stored {n} games")
    return n


if __name__ == "__main__":
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import DB_PATH
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    for y in sys.argv[1:] or [date.today().year]:
        collect(DB_PATH, int(y))

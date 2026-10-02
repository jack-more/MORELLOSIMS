"""lineup_stats / lineup_players built from ESPN play-by-play stints.

stats.nba.com (LeagueDashLineups) is blocked on GitHub Actions, so the 2-5
man lineup tables froze in Feb 2026. collectors/espn_boxscores.py already
reconstructs who is on the floor from ESPN play-by-play; parse_pbp() also
tallies every five-man unit (seconds, points, possessions, shooting) and
_store_game() keeps them per game in `espn_lineup_games`. This module
aggregates those units into the 2/3/4/5-man rows collectors/lineups.py
writes, in the same units:

  * regular season only (LeagueDashLineups is called with "Regular Season")
  * PerGame mode: minutes, fgm/fga/fg3m/fg3a/ftm/fta and plus_minus are
    per game played by the group, 1 decimal; gp = games in which the group
    shared the floor
  * fg/fg3/ft pct as fractions, 3 decimals; fg3a_rate = fg3a / fga (per-game values)
  * off/def/net rating per 100 possessions, 1 decimal (see RATING_POSS)
  * possessions = minutes_per_game / 48 * team pace (team_season_stats),
    exactly as collectors/lineups.py estimates it
  * lineup_id "-pid-pid-...-" (sorted NBA ids), player_ids JSON list
  * the stats.nba.com row caps, which shape what the model sees: rows are
    the top MAX_ROWS (2,000) groups per size by per-game minutes (the Base
    call), and only groups that are also in the top 2,000 by TOTAL minutes
    carry off/def/net ratings (the Advanced call returns a different 2,000;
    collectors/lineups.py merges it by lineup id, the rest stay NULL). Every
    consumer filters on net_rating IS NOT NULL, which keeps one-game groups
    with extreme ratings out of synergy; reproduced here on purpose.

Units are stored with ESPN athlete ids and mapped to NBA ids at aggregation
time through espn_player_map, so a synthetic id that later resolves to the
real one is picked up automatically.

Verified against the stats.nba.com tables frozen in Feb 2026:
scripts/verify_espn_lineups.py.
"""

import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations

import pandas as pd

logger = logging.getLogger(__name__)

LINEUP_SCHEMA = """
CREATE TABLE IF NOT EXISTS espn_lineup_games (
    game_id   TEXT NOT NULL,
    team_id   INTEGER NOT NULL,
    e1 INTEGER NOT NULL, e2 INTEGER NOT NULL, e3 INTEGER NOT NULL,
    e4 INTEGER NOT NULL, e5 INTEGER NOT NULL,      -- ESPN athlete ids, ascending
    sec REAL,
    pts INTEGER, opp_pts INTEGER,
    poss INTEGER, opp_poss INTEGER,                -- possessions started with the unit on the floor
    fgm INTEGER, fga INTEGER, fg3m INTEGER, fg3a INTEGER, ftm INTEGER, fta INTEGER,
    opp_fgm INTEGER, opp_fga INTEGER, opp_fta INTEGER,
    PRIMARY KEY (game_id, team_id, e1, e2, e3, e4, e5)
) WITHOUT ROWID;
"""

UNIT_COLUMNS = ("sec", "pts", "opp_pts", "poss", "opp_poss",
                "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "opp_fgm", "opp_fga", "opp_fta")
SUM_COLUMNS = UNIT_COLUMNS
MAX_ROWS = 2000
GROUP_SIZES = (5, 4, 3, 2)


def store_units(conn, game_id: str, units: list, espn_to_nba_team: dict, periods: int = 4) -> int:
    """Replace the stored five-man units of one game (parse_pbp()['units']).

    A team's units are stored only when they account for the whole game
    (every second has five known players on the floor). Games whose
    play-by-play does not fully reconcile with the box score are kept when
    that holds: stats.nba.com's lineups include them, and dropping them
    cost every group from those games a GP (2025-26: 4 games)."""
    conn.executescript(LINEUP_SCHEMA)
    conn.execute("DELETE FROM espn_lineup_games WHERE game_id = ?", [game_id])
    game_sec = 2880 + 300 * max(0, (periods or 4) - 4)
    covered = defaultdict(float)
    for espn_team, _, tl in units:
        covered[espn_team] += tl.get("sec", 0)
    rows = []
    for espn_team, members, tl in units:
        tid = espn_to_nba_team.get(espn_team)
        if tid is None or abs(covered[espn_team] - game_sec) > 1:
            continue
        if tl.get("sec", 0) <= 0 and not any(tl.get(k) for k in UNIT_COLUMNS[1:]):
            continue
        ids = sorted(int(m) for m in members)
        rows.append([game_id, tid, *ids, round(float(tl["sec"]), 1)] + [int(tl.get(k, 0)) for k in UNIT_COLUMNS[1:]])
    n_cols = 7 + len(UNIT_COLUMNS)
    conn.executemany(f"INSERT OR REPLACE INTO espn_lineup_games VALUES ({','.join('?' * n_cols)})", rows)
    return len(rows)


def load_units(conn, season: str, through_date: str | None = None, regular_only: bool = True) -> pd.DataFrame:
    """Stored units of the season, with NBA player ids (espn_player_map)."""
    conn.executescript(LINEUP_SCHEMA)
    q = f"""SELECT u.*, t.game_date FROM espn_lineup_games u
            JOIN espn_team_games t ON t.game_id = u.game_id AND t.team_id = u.team_id
            WHERE t.season_id = ?"""
    args = [season]
    if regular_only:
        q += " AND t.counts_regular = 1"
    if through_date:
        q += " AND t.game_date <= ?"
        args.append(through_date)
    df = pd.read_sql_query(q, conn, params=args)
    if df.empty:
        return df
    emap = {int(e): int(p) for e, p in conn.execute("SELECT espn_id, player_id FROM espn_player_map")}
    for c in ("e1", "e2", "e3", "e4", "e5"):
        df[c] = df[c].map(lambda e: emap.get(int(e), 0))
    return df


def aggregate_groups(units: pd.DataFrame, sizes=GROUP_SIZES) -> dict:
    """{n: DataFrame(team_id, pids tuple, gp, totals...)} for every group of n
    players that shared the floor (n in sizes)."""
    out = {}
    vals = units[list(SUM_COLUMNS)].to_numpy(dtype=float)
    pids = units[["e1", "e2", "e3", "e4", "e5"]].to_numpy()
    gids = units["game_id"].to_numpy()
    tids = units["team_id"].to_numpy()
    for n in sizes:
        tot = defaultdict(lambda: [0.0] * len(SUM_COLUMNS))
        games = defaultdict(set)
        for i in range(len(units)):
            members = sorted(int(p) for p in pids[i])
            if 0 in members:
                continue
            v = vals[i]
            for combo in combinations(members, n):
                key = (int(tids[i]), combo)
                acc = tot[key]
                for j in range(len(SUM_COLUMNS)):
                    acc[j] += v[j]
                if v[0] > 0:
                    games[key].add(gids[i])
        rows = []
        for (tid, combo), acc in tot.items():
            gp = len(games.get((tid, combo), ()))
            if gp == 0:
                continue
            rows.append({"team_id": tid, "pids": combo, "gp": gp, **dict(zip(SUM_COLUMNS, acc))})
        out[n] = pd.DataFrame(rows)
    return out


def _r(v, n):
    return None if v is None or pd.isna(v) else round(float(v), n)


def _div(a, b):
    return a / b if b else 0.0


# Lineup ratings: offensive rating per 100 offensive possessions, defensive
# per 100 defensive possessions (stats.nba.com counts the two ends separately
# for lineups: its implied offensive and defensive counts differ), net = the
# unrounded difference. stats.nba.com credits a possession to every group on
# the floor for any part of it, so mid-possession substitutions (mostly
# between free throws) add to the start-of-possession counts stored per unit;
# POSS_SCALE is that share, measured on 2025-26 (scripts/verify_espn_lineups.py:
# ORtg/DRtg bias +2.6 unscaled, ~0 at 1.024; net rating is unaffected).
POSS_SCALE = 1.024


def lineup_rows(groups: dict, season: str, pace: dict, max_rows: int = MAX_ROWS,
                poss_scale: float = POSS_SCALE) -> tuple[pd.DataFrame, pd.DataFrame]:
    """lineup_stats + lineup_players rows (collectors/lineups.py units)."""
    ls_rows, lp_rows = [], []
    for n, g in groups.items():
        if g.empty:
            continue
        g = g.copy()
        g["mpg"] = (g["sec"] / 60.0 / g["gp"]).round(1)
        g["tot_min"] = g["sec"] / 60.0
        rated = set(g.sort_values(["tot_min", "gp"], ascending=False).head(max_rows).index)
        # LeagueDashLineups (PerGame) returns the top 2,000 by per-game minutes;
        # ties broken by total minutes so the cut is deterministic
        g = g.sort_values(["mpg", "tot_min"], ascending=False).head(max_rows)
        for r in g.itertuples():
            gp = int(r.gp)
            pg = lambda v: _r(v / gp, 1)  # noqa: E731
            ok = r.Index in rated
            ortg = 100 * r.pts / (r.poss * poss_scale) if ok and r.poss > 0 else None
            drtg = 100 * r.opp_pts / (r.opp_poss * poss_scale) if ok and r.opp_poss > 0 else None
            fga_pg, fg3a_pg = pg(r.fga), pg(r.fg3a)
            mpg = float(r.mpg)
            lineup_id = "-" + "-".join(str(p) for p in r.pids) + "-"
            ls_rows.append({
                "lineup_id": lineup_id, "team_id": int(r.team_id), "season_id": season,
                "group_quantity": n, "player_ids": json.dumps(list(r.pids)), "gp": gp,
                "minutes": mpg,
                "possessions": (mpg / 48.0) * pace.get(int(r.team_id), 100.0) if mpg > 0 else 0,
                "off_rating": _r(ortg, 1), "def_rating": _r(drtg, 1),
                "net_rating": _r(ortg - drtg, 1) if ortg is not None and drtg is not None else None,
                "fg_pct": _r(_div(r.fgm, r.fga), 3), "fg3_pct": _r(_div(r.fg3m, r.fg3a), 3),
                "ft_pct": _r(_div(r.ftm, r.fta), 3),
                "fg3a_rate": _div(fg3a_pg or 0, fga_pg or 0) if fga_pg else 0,
                "fgm": pg(r.fgm), "fga": fga_pg, "fg3m": pg(r.fg3m), "fg3a": fg3a_pg,
                "ftm": pg(r.ftm), "fta": pg(r.fta),
                "plus_minus": pg(r.pts - r.opp_pts),
            })
            lp_rows.extend({"lineup_id": lineup_id, "season_id": season, "player_id": int(p)} for p in r.pids)
    ls = pd.DataFrame(ls_rows)
    if not ls.empty:
        # lineup_stats is keyed (lineup_id, season_id): a group that played
        # together on two teams keeps its larger sample, as drop_duplicates
        # on the stats.nba.com rows (sorted by minutes) does
        ls = ls.drop_duplicates(subset=["lineup_id", "season_id"], keep="first")
    lp = pd.DataFrame(lp_rows).drop_duplicates() if lp_rows else pd.DataFrame()
    return ls, lp


def team_pace(conn, season) -> dict:
    return {int(t): float(p) for t, p in conn.execute(
        "SELECT team_id, pace FROM team_season_stats WHERE season_id = ? AND pace IS NOT NULL", [season])}


def build_lineup_stats(conn, season: str, through_date: str | None = None, **kw):
    units = load_units(conn, season, through_date)
    if units.empty:
        return pd.DataFrame(), pd.DataFrame(), units
    groups = aggregate_groups(units)
    ls, lp = lineup_rows(groups, season, team_pace(conn, season), **kw)
    return ls, lp, units


def write_lineup_stats(db_path: str, season: str, force: bool = False) -> dict:
    """Rebuild lineup_stats / lineup_players for the season from ESPN units.

    Write policy: the season's rows are rebuilt from ESPN on every run
    (a few seconds; picks up newly resolved synthetic player ids), except
    when they hold stats.nba.com rows at least as current as ESPN (it got
    through, e.g. a local run). Seeded priors (seed_season.py: last season's
    lineups, GP above anything played this season) are replaced as soon as
    the season has ESPN units; seed_season.py re-adds seeds only for groups
    that have no row yet, as it does for every other season table.
    """
    conn = sqlite3.connect(db_path)
    conn.executescript(LINEUP_SCHEMA)
    try:
        ls, lp, units = build_lineup_stats(conn, season)
        if ls.empty:
            logger.info(f"ESPN lineups: no {season} regular-season units yet")
            return {"written": False, "reason": "no ESPN units"}
        espn_games = int(units["game_id"].nunique())
        as_of = str(units["game_date"].max())
        espn_max_gp = int(ls["gp"].max())
        src = conn.execute("SELECT source FROM stats_source WHERE season_id = ? AND table_name = 'lineup_stats'",
                           [season]).fetchone() if _has_table(conn, "stats_source") else None
        stored = conn.execute("SELECT COUNT(*), MAX(gp) FROM lineup_stats WHERE season_id = ?", [season]).fetchone()
        team_gp = [r[0] for r in conn.execute("SELECT COUNT(*) FROM espn_team_games WHERE season_id = ? "
                                              "AND counts_regular = 1 GROUP BY team_id", [season])]
        seeded = bool(stored[0]) and (stored[1] or 0) > max(team_gp or [0])
        if not force and stored[0] and src is None and not seeded and (stored[1] or 0) >= espn_max_gp:
            logger.info(f"ESPN lineups: stored stats.nba.com {season} rows (max GP {stored[1]}) are at least "
                        f"as current as ESPN (max GP {espn_max_gp}) — kept")
            return {"written": False, "reason": "stored rows current"}
        conn.execute("DELETE FROM lineup_players WHERE season_id = ?", [season])
        conn.execute("DELETE FROM lineup_stats WHERE season_id = ?", [season])
        ls.to_sql("lineup_stats", conn, if_exists="append", index=False)
        lp.to_sql("lineup_players", conn, if_exists="append", index=False)
        conn.execute("""CREATE TABLE IF NOT EXISTS stats_source (season_id TEXT NOT NULL, table_name TEXT NOT NULL,
                        source TEXT NOT NULL, as_of TEXT, max_gp INTEGER, written_at TEXT,
                        PRIMARY KEY (season_id, table_name))""")
        conn.execute("INSERT OR REPLACE INTO stats_source VALUES (?, 'lineup_stats', 'espn', ?, ?, ?)",
                     [season, as_of, espn_max_gp, datetime.now(timezone.utc).isoformat(timespec="seconds")])
        conn.commit()
        by_n = ls.groupby("group_quantity").size().to_dict()
        logger.info(f"ESPN lineups: wrote {len(ls)} {season} lineup rows through {as_of} from {espn_games} games "
                    f"({', '.join(f'{n}-man {by_n.get(n, 0)}' for n in GROUP_SIZES)}; replaced "
                    f"{stored[0]} {'seeded' if seeded else 'stored'} rows)")
        return {"written": True, "rows": len(ls), "games": espn_games, "as_of": as_of, "by_n": by_n}
    finally:
        conn.close()


def _has_table(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", [name]).fetchone() is not None

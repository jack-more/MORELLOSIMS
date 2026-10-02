"""player_season_stats / team_season_stats built from ESPN box scores.

Replaces LeagueDashPlayerStats / LeagueDashTeamStats (stats.nba.com, blocked
on GitHub Actions) with aggregates of espn_player_games / espn_team_games
(collectors/espn_boxscores.py). Same rows, same units as
collectors/players.py writes:

  * regular season only (ESPN season type 2, NBA Cup final excluded) — the
    LeagueDash calls use season_type_all_star="Regular Season"
  * per-game values rounded to 1 decimal, percentages as fractions to 3
    decimals, ratings per 100 possessions to 1 decimal, pace to 2 decimals
  * minutes_total = minutes_per_game * gp (as the LeagueDash path stores it)
  * team fg3a_rate / ft_rate from the 1-decimal per-game averages (ditto)
  * one row per player; team_id = team of his latest game (LeagueDash
    reports a traded player under his current team)

Write policy (write_season_stats): the season's rows are replaced from ESPN
when ESPN is ahead of what's stored for any team (stale stats.nba.com data)
or when the stored rows are seeded priors (stored GP above what the team has
actually played while ESPN covers every scored game). When stored GP equals
ESPN's for every team the stored rows (stats.nba.com, when it got through)
are kept.
"""

import logging
import sqlite3
from datetime import datetime, timezone

import pandas as pd

from collectors.espn_boxscores import SCHEMA

logger = logging.getLogger(__name__)

PROVENANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS stats_source (
    season_id   TEXT NOT NULL,
    table_name  TEXT NOT NULL,
    source      TEXT NOT NULL,     -- espn | stats.nba.com
    as_of       TEXT,              -- last game date included
    max_gp      INTEGER,
    written_at  TEXT,
    PRIMARY KEY (season_id, table_name)
);
"""


def _round(v, n):
    return None if v is None or pd.isna(v) else round(float(v), n)


def _div(a, b):
    return a / b if b else 0.0


def load_player_games(conn, season, through_date=None, regular_only=True) -> pd.DataFrame:
    q = """SELECT p.*, t.pbp_ok
           FROM espn_player_games p
           JOIN espn_team_games t ON t.game_id = p.game_id AND t.team_id = p.team_id
           WHERE p.season_id = ?"""
    args = [season]
    if regular_only:
        q += " AND p.counts_regular = 1"
    if through_date:
        q += " AND p.game_date <= ?"
        args.append(through_date)
    df = pd.read_sql_query(q, conn, params=args)
    if df.empty:
        return df
    df["min"] = df["sec"] / 60.0
    use_box = df["pbp_ok"] == 0
    df.loc[use_box, "min"] = df.loc[use_box, "box_min"].astype(float)
    df.loc[df["dnp"] == 1, "min"] = 0.0
    return df


def load_team_games(conn, season, through_date=None, regular_only=True) -> pd.DataFrame:
    q = "SELECT * FROM espn_team_games WHERE season_id = ?"
    args = [season]
    if regular_only:
        q += " AND counts_regular = 1"
    if through_date:
        q += " AND game_date <= ?"
        args.append(through_date)
    df = pd.read_sql_query(q, conn, params=args)
    if df.empty:
        return df
    keep = ["pts", "poss", "oreb", "dreb", "team_oreb", "team_dreb"]
    opp = df[["game_id", "team_id"] + keep].rename(
        columns={"team_id": "opp_team_id", **{k: f"opp_{k}" for k in keep}})
    return df.merge(opp, on=["game_id", "opp_team_id"], how="left")


def current_teams(conn, season) -> dict:
    """player_id -> team_id for players with exactly one roster assignment
    this season (the daily roster pull: stats.nba.com or its ESPN fallback)."""
    rows = conn.execute("SELECT player_id, MIN(team_id), COUNT(DISTINCT team_id) FROM roster_assignments "
                        "WHERE season_id = ? GROUP BY player_id", [season]).fetchall()
    return {int(p): int(t) for p, t, n in rows if n == 1}


def build_player_season_stats(pg: pd.DataFrame, season: str, roster_team: dict | None = None) -> pd.DataFrame:
    """roster_team: current team per player (current_teams()). LeagueDash
    reports a traded player under his current team even before he has played
    for it (2025-26: Anthony Davis under WAS with all 20 games for DAL), so
    the roster team wins; players without one get the team of their latest game."""
    if pg.empty:
        return pd.DataFrame()   # new season before its first game (load_player_games returns no columns)
    played = pg[pg["min"] > 0].copy()
    if played.empty:
        return pd.DataFrame()
    latest_team = (played.sort_values(["game_date", "game_id"])
                   .groupby("player_id")["team_id"].last()).to_dict()
    if roster_team:
        latest_team.update({p: t for p, t in roster_team.items() if p in latest_team})
    cols = ["min", "pts", "reb", "ast", "stl", "blk", "tov", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta",
            "on_pts", "on_opp_pts", "off_poss", "def_poss", "on_fgm", "on_fga", "on_fta", "on_tov",
            "on_oreb", "on_dreb", "on_opp_oreb", "on_opp_dreb", "on_team_reb", "on_opp_team_reb"]
    sums = played.groupby("player_id")[cols].sum()
    sums["gp"] = played.groupby("player_id")["game_id"].nunique()
    rows = []
    for pid, s in sums.iterrows():
        gp = int(s["gp"])
        mpg = _round(s["min"] / gp, 1)
        # on-court ratings per 100 of the average of both teams' possessions,
        # as stats.nba.com's team ratings are (see build_team_season_stats)
        poss = (s["off_poss"] + s["def_poss"]) / 2
        ortg = 100 * _div(s["on_pts"], poss)
        drtg = 100 * _div(s["on_opp_pts"], poss)
        tsa = 2 * (s["fga"] + 0.44 * s["fta"])
        reb_chances = (s["on_oreb"] + s["on_dreb"] + s["on_opp_oreb"] + s["on_opp_dreb"]
                       + s["on_team_reb"] + s["on_opp_team_reb"])
        per36 = lambda k: _round(36 * _div(s[k], s["min"]), 1)  # noqa: E731
        rows.append({
            "player_id": int(pid), "team_id": int(latest_team[pid]), "season_id": season,
            "gp": gp, "minutes_total": mpg * gp, "minutes_per_game": mpg,
            "pts_pg": _round(s["pts"] / gp, 1), "reb_pg": _round(s["reb"] / gp, 1),
            "ast_pg": _round(s["ast"] / gp, 1), "stl_pg": _round(s["stl"] / gp, 1),
            "blk_pg": _round(s["blk"] / gp, 1), "tov_pg": _round(s["tov"] / gp, 1),
            "fg_pct": _round(_div(s["fgm"], s["fga"]), 3), "fg3_pct": _round(_div(s["fg3m"], s["fg3a"]), 3),
            "ft_pct": _round(_div(s["ftm"], s["fta"]), 3),
            "fg3a_pg": _round(s["fg3a"] / gp, 1), "fta_pg": _round(s["fta"] / gp, 1),
            "usg_pct": _round(_div(s["fga"] + 0.44 * s["fta"] + s["tov"],
                                   s["on_fga"] + 0.44 * s["on_fta"] + s["on_tov"]), 3),
            "ast_pct": _round(_div(s["ast"], s["on_fgm"] - s["fgm"]), 3),
            "reb_pct": _round(_div(s["reb"], reb_chances), 3),
            "ts_pct": _round(_div(s["pts"], tsa), 3),
            "efg_pct": _round(_div(s["fgm"] + 0.5 * s["fg3m"], s["fga"]), 3),
            "off_rating": _round(ortg, 1), "def_rating": _round(drtg, 1), "net_rating": _round(ortg - drtg, 1),
            "pie": None,   # not reproducible from ESPN data; nothing reads it (see espn_boxscores.pgs_row)
            "pace": _round(48 * _div(poss, s["min"]), 2),
            "pts_per36": per36("pts"), "reb_per36": per36("reb"), "ast_per36": per36("ast"),
            "stl_per36": per36("stl"), "blk_per36": per36("blk"), "tov_per36": per36("tov"),
            "fg3a_per36": per36("fg3a"), "fta_per36": per36("fta"),
        })
    return pd.DataFrame(rows)


def build_team_season_stats(tg: pd.DataFrame, season: str) -> pd.DataFrame:
    if tg.empty:
        return pd.DataFrame()
    rows = []
    for tid, g in tg.groupby("team_id"):
        gp = len(g)
        s = g.sum(numeric_only=True)
        fga_pg, fg3a_pg, fta_pg = (round(s[k] / gp, 1) for k in ("fga", "fg3a", "fta"))
        # stats.nba.com rates both ends per 100 of the game's average possessions
        # (measured: net rating MAE 0.11 vs 0.24 with each team's own count)
        poss = (s["poss"] + s["opp_poss"]) / 2
        ortg = 100 * _div(s["pts"], poss)
        drtg = 100 * _div(s["opp_pts"], poss)
        oreb, dreb = s["oreb"] + s["team_oreb"], s["dreb"] + s["team_dreb"]
        opp_oreb, opp_dreb = s["opp_oreb"] + s["opp_team_oreb"], s["opp_dreb"] + s["opp_team_dreb"]
        rows.append({
            "team_id": int(tid), "season_id": season, "gp": gp,
            "pace": _round(48 * _div(poss, s["minutes"] / 5), 2),
            "off_rating": _round(ortg, 1), "def_rating": _round(drtg, 1), "net_rating": _round(ortg - drtg, 1),
            "fg_pct": _round(_div(s["fgm"], s["fga"]), 3), "fg3_pct": _round(_div(s["fg3m"], s["fg3a"]), 3),
            "fg3a_rate": _div(fg3a_pg, fga_pg), "ft_rate": _div(fta_pg, fga_pg),
            # rebound percentages count team rebounds, as stats.nba.com's do
            "oreb_pct": _round(_div(oreb, oreb + opp_dreb), 3),
            "dreb_pct": _round(_div(dreb, dreb + opp_oreb), 3),
            "ast_pct": _round(_div(s["ast"], s["fgm"]), 3),
            "tov_pct": _round(_div(s["tov"], s["poss"]), 3),     # turnovers per possession
            "ast_tov_ratio": _round(_div(s["ast"], s["tov"]), 2),
        })
    return pd.DataFrame(rows)


def coverage_gaps(conn, season) -> list[str]:
    """Scored games in `games` for the season with no ESPN box score stored."""
    return [r[0] for r in conn.execute(
        """SELECT g.game_id FROM games g
           WHERE g.season_id = ? AND g.home_score IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM espn_team_games e WHERE e.game_id = g.game_id)""", [season])]


def write_season_stats(db_path: str, season: str, force: bool = False) -> dict:
    """Rebuild and (per the write policy above) store the season aggregates."""
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.executescript(PROVENANCE_SCHEMA)
    try:
        tg = load_team_games(conn, season)
        pg = load_player_games(conn, season)
        tss = build_team_season_stats(tg, season)
        pss = build_player_season_stats(pg, season, current_teams(conn, season))
        if tss.empty or pss.empty:
            logger.info(f"ESPN season stats: no {season} regular-season box scores yet")
            return {"written": False, "reason": "no ESPN games"}
        espn_gp = dict(zip(tss["team_id"], tss["gp"]))
        stored_gp = dict(conn.execute("SELECT team_id, MAX(gp) FROM team_season_stats WHERE season_id = ? "
                                      "GROUP BY team_id", [season]).fetchall())
        gaps = coverage_gaps(conn, season)
        ahead = [t for t, n in espn_gp.items() if n > (stored_gp.get(t) or 0)]
        seeded = [t for t, n in espn_gp.items() if (stored_gp.get(t) or 0) > n] if not gaps else []
        missing_teams = [t for t in stored_gp if t not in espn_gp]
        if not (force or ahead or seeded or not stored_gp):
            logger.info(f"ESPN season stats: stored {season} rows are as current as ESPN "
                        f"({len(espn_gp)} teams, max GP {max(espn_gp.values())}) — kept")
            return {"written": False, "reason": "stored rows current"}
        if missing_teams and not force:
            logger.warning(f"ESPN season stats: {len(missing_teams)} stored teams have no ESPN games yet")
        as_of = str(tg["game_date"].max())
        conn.execute("DELETE FROM team_season_stats WHERE season_id = ?", [season])
        tss.to_sql("team_season_stats", conn, if_exists="append", index=False)
        conn.execute("DELETE FROM player_season_stats WHERE season_id = ?", [season])
        pss.to_sql("player_season_stats", conn, if_exists="append", index=False)
        backfilled = _backfill_roster_assignments(conn, pss, season)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for table, df in (("team_season_stats", tss), ("player_season_stats", pss)):
            conn.execute("INSERT OR REPLACE INTO stats_source VALUES (?, ?, 'espn', ?, ?, ?)",
                         [season, table, as_of, int(df["gp"].max()), now])
        conn.commit()
        logger.info(f"ESPN season stats: wrote {len(tss)} teams / {len(pss)} players for {season} "
                    f"through {as_of} (GP {int(tss['gp'].min())}-{int(tss['gp'].max())}; "
                    f"{len(ahead)} teams were behind, {len(seeded)} seeded; "
                    f"{backfilled} roster assignments backfilled; {len(gaps)} scored games without ESPN box)")
        return {"written": True, "teams": len(tss), "players": len(pss), "as_of": as_of,
                "gaps": gaps, "ahead": len(ahead), "seeded": len(seeded)}
    finally:
        conn.close()


def _backfill_roster_assignments(conn, pss: pd.DataFrame, season: str) -> int:
    """Players with season stats but no roster assignment for the season
    (rookies, call-ups, trades the roster fetch missed) — same patch the
    LeagueDash path applies in PlayerCollector._backfill_from_league_stats."""
    have = {r[0] for r in conn.execute("SELECT player_id FROM roster_assignments WHERE season_id = ?", [season])}
    pos = dict(conn.execute("SELECT player_id, position FROM players").fetchall())
    rows = [(int(r.player_id), int(r.team_id), season, "", pos.get(int(r.player_id)) or "")
            for r in pss.itertuples() if int(r.player_id) not in have]
    conn.executemany("INSERT OR IGNORE INTO roster_assignments (player_id, team_id, season_id, jersey_number, "
                     "listed_position) VALUES (?, ?, ?, ?, ?)", rows)
    return len(rows)

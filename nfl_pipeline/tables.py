#!/usr/bin/env python3
"""Reduce nflverse raw data to the compact tables the model reads.

  schedules.csv   every game 2016+ (scores, spread_line, rest, starting QBs)
  team_games.csv  one row per team-game: offensive EPA by play type, special
                  teams EPA (net), play counts — from play-by-play
  qb_games.csv    one row per QB-game: dropbacks and EPA on them

Raw pbp is ~20 MB/season and is never committed; these tables are < 3 MB.
Past seasons are frozen once built (the pipeline only rebuilds the current
season), so the backtest is reproducible from the committed tables alone.

  python3 nfl_pipeline/tables.py                  # current season only
  python3 nfl_pipeline/tables.py --all            # 2016..current (Actions smoke run)
  python3 nfl_pipeline/tables.py --check          # rebuild all in memory, diff vs committed
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (  # noqa: E402
    CURRENT_SEASON, FIRST_SEASON, QB_GAMES_CSV, SCHEDULES_CSV, TEAM_GAMES_CSV,
)
import sources  # noqa: E402

# Franchise continuity across relocations (nflverse uses the abbreviation of
# the season: OAK through 2019, SD in 2016, STL never after 2015).
FRANCHISE = {"OAK": "LV", "SD": "LAC", "STL": "LA"}

SCHED_COLS = [
    "game_id", "season", "game_type", "week", "gameday", "weekday", "gametime",
    "away_team", "away_score", "home_team", "home_score", "location", "result", "total",
    "overtime", "espn", "away_rest", "home_rest", "spread_line", "away_spread_odds",
    "home_spread_odds", "total_line", "away_moneyline", "home_moneyline", "div_game",
    "roof", "surface", "away_qb_id", "home_qb_id", "away_qb_name", "home_qb_name",
    "stadium_id", "stadium",
]

PBP_COLS = [
    "game_id", "season", "week", "game_date", "posteam", "defteam", "home_team", "away_team",
    "play_type", "epa", "pass", "rush", "qb_dropback", "success", "down", "wp", "special",
    "id", "name", "two_point_attempt",
]

TEAM_COLS = ["game_id", "season", "week", "gameday", "team", "opp", "is_home", "plays", "epa",
             "pass_plays", "pass_epa", "rush_plays", "rush_epa", "success", "plays_c", "epa_c",
             "st_epa"]
QB_COLS = ["game_id", "season", "week", "gameday", "team", "qb_id", "qb_name", "dropbacks", "qb_epa"]


def norm_team(s):
    return s.replace(FRANCHISE)


def build_schedules(refresh=False):
    g = pd.read_csv(sources.schedules_path(refresh=refresh), low_memory=False)
    g = g[g["season"] >= FIRST_SEASON][SCHED_COLS].copy()
    for c in ("away_team", "home_team"):
        g[c] = norm_team(g[c])
    return g.sort_values(["season", "gameday", "gametime", "game_id"]).reset_index(drop=True)


def team_games_from_pbp(p):
    """Per team-game offensive aggregates from one season of play-by-play."""
    p = p[[c for c in PBP_COLS if c in p.columns]].copy()
    for c in ("posteam", "defteam", "home_team", "away_team"):
        p[c] = norm_team(p[c])
    scrim = p[((p["pass"] == 1) | (p["rush"] == 1)) & p["epa"].notna() & p["down"].notna()
              & (p["two_point_attempt"].fillna(0) != 1)].copy()
    scrim["is_pass"] = (scrim["pass"] == 1).astype(int)
    scrim["comp"] = scrim["wp"].between(0.10, 0.90).astype(int)
    scrim["pass_epa"] = scrim["epa"] * scrim["is_pass"]
    scrim["rush_epa"] = scrim["epa"] * (1 - scrim["is_pass"])
    scrim["epa_c"] = scrim["epa"] * scrim["comp"]
    off = scrim.groupby(["game_id", "posteam"]).agg(
        season=("season", "first"), week=("week", "first"), gameday=("game_date", "first"),
        opp=("defteam", "first"), home_team=("home_team", "first"),
        plays=("epa", "size"), epa=("epa", "sum"), pass_plays=("is_pass", "sum"),
        pass_epa=("pass_epa", "sum"), rush_epa=("rush_epa", "sum"), success=("success", "sum"),
        plays_c=("comp", "sum"), epa_c=("epa_c", "sum"),
    ).reset_index().rename(columns={"posteam": "team"})
    off["rush_plays"] = off["plays"] - off["pass_plays"]
    off["is_home"] = (off["team"] == off["home_team"]).astype(int)

    st = p[(p["special"] == 1) & p["epa"].notna() & p["posteam"].notna()]
    st_for = st.groupby(["game_id", "posteam"])["epa"].sum()
    st_against = st.groupby(["game_id", "defteam"])["epa"].sum()
    st_for.index.names = st_against.index.names = ["game_id", "team"]
    st_net = st_for.sub(st_against, fill_value=0.0).rename("st_epa").reset_index()
    off = off.merge(st_net, on=["game_id", "team"], how="left")
    off["st_epa"] = off["st_epa"].fillna(0.0)
    return off[TEAM_COLS]


def qb_games_from_pbp(p):
    db = p[(p["qb_dropback"] == 1) & p["epa"].notna() & p["down"].notna() & p["id"].notna()
           & (p["two_point_attempt"].fillna(0) != 1)].copy()
    db["posteam"] = norm_team(db["posteam"])
    q = db.groupby(["game_id", "posteam", "id"]).agg(
        season=("season", "first"), week=("week", "first"), gameday=("game_date", "first"),
        qb_name=("name", "first"), dropbacks=("epa", "size"), qb_epa=("epa", "sum"),
    ).reset_index().rename(columns={"posteam": "team", "id": "qb_id"})
    return q[QB_COLS]


def build_season(season, refresh=False):
    p = pd.read_parquet(sources.pbp_path(season, refresh=refresh), columns=PBP_COLS)
    return team_games_from_pbp(p), qb_games_from_pbp(p)


def _round(df):
    out = df.copy()
    for c in out.columns:
        if out[c].dtype.kind == "f":
            out[c] = out[c].round(5)
    return out


def write(df, path, key):
    _round(df).sort_values(key).to_csv(path, index=False)


def load_existing(path):
    return pd.read_csv(path) if os.path.exists(path) else None


def merge_season(existing, new, season):
    if existing is None:
        return new
    return pd.concat([existing[existing["season"] != season], new], ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="rebuild every season from raw pbp")
    ap.add_argument("--seasons", default="", help="comma list of seasons to rebuild")
    ap.add_argument("--check", action="store_true", help="rebuild all seasons and diff vs committed tables")
    ap.add_argument("--refresh", action="store_true", help="re-download even if cached")
    a = ap.parse_args()

    sched = build_schedules(refresh=True)
    if a.check:
        seasons = list(range(FIRST_SEASON, CURRENT_SEASON + 1))
    elif a.all:
        seasons = list(range(FIRST_SEASON, CURRENT_SEASON + 1))
    elif a.seasons:
        seasons = [int(s) for s in a.seasons.split(",")]
    else:
        seasons = [CURRENT_SEASON]

    tg, qg = load_existing(TEAM_GAMES_CSV), load_existing(QB_GAMES_CSV)
    built_t, built_q = [], []
    for s in seasons:
        refresh = a.refresh or s == CURRENT_SEASON
        t, q = build_season(s, refresh=refresh)
        print(f"  {s}: {t['game_id'].nunique()} games, {len(t)} team-games, {len(q)} QB-games")
        built_t.append(t)
        built_q.append(q)
        if not a.check:
            tg, qg = merge_season(tg, t, s), merge_season(qg, q, s)

    if a.check:
        new_t = _round(pd.concat(built_t)).sort_values(["game_id", "team"]).reset_index(drop=True)
        old_t = pd.read_csv(TEAM_GAMES_CSV).sort_values(["game_id", "team"]).reset_index(drop=True)
        frozen = new_t["season"] < CURRENT_SEASON
        a_ = new_t[frozen].reset_index(drop=True)
        b_ = old_t[old_t["season"] < CURRENT_SEASON].reset_index(drop=True)
        same = len(a_) == len(b_) and np.allclose(a_["epa"].values, b_["epa"].values, atol=1e-3)
        print(f"check: past-season team_games {'MATCH' if same else 'DIFFER'} "
              f"(rebuilt {len(a_)} rows vs committed {len(b_)})")
        if not same:
            raise SystemExit(1)
        return

    old_sched = load_existing(SCHEDULES_CSV)
    if old_sched is not None and not a.all:
        # past seasons stay exactly as committed (the backtest's frozen market
        # lines); only the rebuilt seasons take the fresh nflverse rows
        sched = pd.concat([old_sched[~old_sched["season"].isin(seasons)], sched[sched["season"].isin(seasons)]],
                          ignore_index=True)
    write(sched, SCHEDULES_CSV, ["season", "gameday", "game_id"])
    write(tg, TEAM_GAMES_CSV, ["game_id", "team"])
    write(qg, QB_GAMES_CSV, ["game_id", "team", "qb_id"])
    print(f"wrote {SCHEDULES_CSV} ({len(sched)}), {TEAM_GAMES_CSV} ({len(tg)}), {QB_GAMES_CSV} ({len(qg)})")


if __name__ == "__main__":
    main()

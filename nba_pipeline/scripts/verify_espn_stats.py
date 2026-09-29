#!/usr/bin/env python3
"""verify_espn_stats.py — ESPN-built stats vs the stats.nba.com data in the DB.

Evidence for switching player_game_stats / player_season_stats /
team_season_stats to ESPN (collectors/espn_boxscores.py + espn_season_stats.py).
Run against a COPY of nba_sim.db that holds ESPN box scores for 2025-26
(espn_stats_sync.py --no-pgs --no-season-stats) next to the untouched
stats.nba.com rows (player_game_stats through 2026-02-23; season tables
frozen at 62-65 GP).

  python scripts/verify_espn_stats.py report --db /tmp/verify.db [--json out.json]
      1. id mapping: name-based ESPN->NBA ids vs ids implied by identical
         stat lines in the same game/team
      2. per player-game: minutes, pts, reb, ast, FG/3P/FT made-att, tov, +/-
         (+ advanced: ratings, usage, TS, pace)
      3. season aggregates at the frozen GP: player and team
  python scripts/verify_espn_stats.py spreads --db /tmp/verify.db --work DIR
      4. compute_moji_spread on 2025-26 games with official vs ESPN tables
         (identical inputs otherwise), with and without re-deriving value
         scores / pair synergy from each set of tables.
"""

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from collectors.espn_boxscores import pgs_rows_for_game  # noqa: E402
from collectors.espn_season_stats import (  # noqa: E402
    load_player_games, load_team_games, build_player_season_stats, build_team_season_stats, current_teams)

SEASON = "2025-26"
KEY = ("pts", "reb", "ast", "stl", "blk", "tov", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "pf")


def q(conn, sql, args=()):
    return pd.read_sql_query(sql, conn, params=list(args))


def dist(x):
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if not len(x):
        return {}
    a = np.abs(x)
    return {"n": int(len(x)), "mean": round(float(x.mean()), 4), "mae": round(float(a.mean()), 4),
            "p50": round(float(np.percentile(a, 50)), 4), "p90": round(float(np.percentile(a, 90)), 4),
            "p99": round(float(np.percentile(a, 99)), 4), "max": round(float(a.max()), 4)}


# ── 1. id mapping ──

def statline_map(conn):
    """ESPN id -> NBA id from identical stat lines (same game, same team)."""
    off = q(conn, "SELECT p.* FROM player_game_stats p JOIN games g ON g.game_id = p.game_id "
                  "WHERE g.season_id = ? AND p.minutes > 0", [SEASON])
    esp = q(conn, "SELECT * FROM espn_player_games WHERE season_id = ? AND dnp = 0", [SEASON])
    esp = esp[esp["game_id"].isin(set(off["game_id"]))]
    votes = defaultdict(Counter)
    ok = defaultdict(set)
    off_idx = defaultdict(list)
    for r in off.itertuples():
        off_idx[(r.game_id, r.team_id, tuple(getattr(r, k) for k in KEY))].append(r.player_id)
    for r in esp.itertuples():
        cands = off_idx.get((r.game_id, r.team_id, tuple(getattr(r, k) for k in KEY)), [])
        if len(cands) == 1:
            votes[r.espn_id][int(cands[0])] += 1
    out = {}
    for eid, c in votes.items():
        (pid, n), total = c.most_common(1)[0], sum(c.values())
        out[eid] = (pid, n, total)
    return out


def check_ids(conn):
    sl = statline_map(conn)
    names = dict(conn.execute("SELECT espn_id, espn_name FROM espn_player_map"))
    prod = {e: (p, m) for e, p, m in conn.execute("SELECT espn_id, player_id, method FROM espn_player_map")}
    agree, disagree, synth_resolved = 0, [], []
    for eid, (pid, n, total) in sl.items():
        mp, method = prod.get(eid, (None, None))
        if mp == pid:
            agree += 1
        elif method == "synthetic":
            synth_resolved.append((eid, names.get(eid), pid, n, total))
        else:
            disagree.append((eid, names.get(eid), mp, method, pid, n, total))
    return {"statline_mapped": len(sl), "agree": agree, "disagree": disagree,
            "synthetic_but_statline_known": synth_resolved,
            "methods": dict(Counter(m for _, m in prod.values()))}


# ── 2. player-game ──

def check_games(conn):
    off = q(conn, "SELECT p.* FROM player_game_stats p JOIN games g ON g.game_id = p.game_id "
                  "WHERE g.season_id = ?", [SEASON])
    gids = sorted(set(off["game_id"]) & {r[0] for r in conn.execute("SELECT DISTINCT game_id FROM espn_team_games")})
    esp = pd.DataFrame([r for g in gids for r in pgs_rows_for_game(conn, g)])
    pbp_ok = dict(conn.execute("SELECT game_id, MIN(pbp_ok) FROM espn_team_games GROUP BY game_id"))
    off = off[off["game_id"].isin(gids)]
    m = off.merge(esp, on=["game_id", "player_id"], how="outer", suffixes=("_o", "_e"), indicator=True)
    played_o = m["minutes_o"].fillna(0) > 0
    played_e = m["minutes_e"].fillna(0) > 0
    both = m[(m["_merge"] == "both") & (played_o | played_e)]
    only_o = m[(m["_merge"] == "left_only") & played_o]
    only_e = m[(m["_merge"] == "right_only") & played_e]
    res = {"games": len(gids), "official_player_games_played": int(played_o.sum()),
           "matched_rows": len(both), "official_only_played": len(only_o), "espn_only_played": len(only_e),
           "games_pbp_fallback": sum(1 for g in gids if not pbp_ok.get(g)),
           "exact_match_rate": {}, "diff": {}}
    for k in ("pts", "reb", "ast", "stl", "blk", "tov", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta",
              "oreb", "dreb", "pf", "plus_minus"):
        res["exact_match_rate"][k] = round(float((both[f"{k}_o"] == both[f"{k}_e"]).mean()), 5)
    both = both.assign(min_diff=both["minutes_e"] - both["minutes_o"])
    res["diff"]["minutes"] = dist(both["min_diff"])
    res["minutes_within"] = {s: round(float((both["min_diff"].abs() <= s / 60).mean()), 4) for s in (1, 6, 30, 60)}
    live = both[(both["minutes_o"] >= 10)]
    for k in ("off_rating", "def_rating", "net_rating", "usg_pct", "ts_pct", "efg_pct", "ast_pct",
              "reb_pct", "pace", "pie"):
        res["diff"][k + " (>=10 min)"] = dist(live[f"{k}_e"] - live[f"{k}_o"])
    res["examples_official_only"] = only_o[["game_id", "player_id", "minutes_o", "pts_o"]].head(15).values.tolist()
    res["examples_espn_only"] = only_e[["game_id", "player_id", "minutes_e", "pts_e"]].head(15).values.tolist()
    return res


# ── 3. season aggregates at the frozen GP ──

def snapshot_date(conn):
    """Last game date at which ESPN regular-season GP equals the stored GP per team."""
    tss = dict(conn.execute("SELECT team_id, MAX(gp) FROM team_season_stats WHERE season_id = ? GROUP BY team_id",
                            [SEASON]))
    tg = q(conn, "SELECT team_id, game_date FROM espn_team_games WHERE season_id = ? AND counts_regular = 1",
           [SEASON])
    best = None
    for d in sorted(tg["game_date"].unique()):
        gp = tg[tg["game_date"] <= d].groupby("team_id").size()
        err = sum(abs(int(gp.get(t, 0)) - n) for t, n in tss.items())
        if best is None or err < best[1]:
            best = (d, err)
    return best


def check_season(conn, through):
    pg = load_player_games(conn, SEASON, through_date=through)
    tg = load_team_games(conn, SEASON, through_date=through)
    epss = build_player_season_stats(pg, SEASON, current_teams(conn, SEASON))
    etss = build_team_season_stats(tg, SEASON)
    opss = q(conn, "SELECT * FROM player_season_stats WHERE season_id = ?", [SEASON])
    otss = q(conn, "SELECT * FROM team_season_stats WHERE season_id = ?", [SEASON])
    out = {"through": through}
    t = otss.merge(etss, on="team_id", suffixes=("_o", "_e"))
    out["teams"] = {"n": len(t), "gp_equal": int((t["gp_o"] == t["gp_e"]).sum())}
    for k in ("pace", "off_rating", "def_rating", "net_rating", "fg_pct", "fg3_pct", "fg3a_rate", "ft_rate",
              "oreb_pct", "dreb_pct", "ast_pct", "tov_pct", "ast_tov_ratio"):
        out["teams"][k] = dist(t[f"{k}_e"] - t[f"{k}_o"])
    out["teams"]["table"] = t[["team_id", "gp_o", "gp_e", "pace_o", "pace_e", "off_rating_o", "off_rating_e",
                               "def_rating_o", "def_rating_e", "net_rating_o", "net_rating_e"]].values.tolist()
    p = opss.merge(epss, on="player_id", suffixes=("_o", "_e"), how="outer", indicator=True)
    both = p[p["_merge"] == "both"]
    out["players"] = {"official": len(opss), "espn": len(epss), "matched": len(both),
                      "official_only": p[p["_merge"] == "left_only"][["player_id", "gp_o", "minutes_per_game_o"]].values.tolist(),
                      "espn_only": p[p["_merge"] == "right_only"][["player_id", "gp_e", "minutes_per_game_e"]].values.tolist()[:30],
                      "gp_equal_rate": round(float((both["gp_o"] == both["gp_e"]).mean()), 4),
                      "team_equal_rate": round(float((both["team_id_o"] == both["team_id_e"]).mean()), 4)}
    rot = both[both["minutes_per_game_o"] > 5]   # the model's rotation filter
    out["players"]["rotation_n"] = len(rot)
    for k in ("gp", "minutes_per_game", "pts_pg", "reb_pg", "ast_pg", "stl_pg", "blk_pg", "tov_pg", "fg_pct",
              "fg3_pct", "ft_pct", "usg_pct", "ts_pct", "efg_pct", "ast_pct", "reb_pct", "off_rating",
              "def_rating", "net_rating", "pie", "pace", "pts_per36"):
        out["players"][k] = dist(rot[f"{k}_e"] - rot[f"{k}_o"])
    big = both[both["minutes_per_game_o"] >= 20]
    for k in ("off_rating", "def_rating", "net_rating", "usg_pct", "pace"):
        out["players"][k + " (>=20 mpg)"] = dist(big[f"{k}_e"] - big[f"{k}_o"])
    return out, epss, etss


def cmd_report(args):
    conn = sqlite3.connect(args.db)
    res = {"ids": check_ids(conn), "games": check_games(conn)}
    snap = snapshot_date(conn)
    res["snapshot"] = {"date": snap[0], "team_gp_abs_error": snap[1]}
    res["season"], _, _ = check_season(conn, snap[0])
    txt = json.dumps(res, indent=1, default=str)
    if args.json:
        open(args.json, "w").write(txt)
    print(txt)


# ── 4. spreads ──

def build_variant(src_db, dst_db, espn, through, rederive):
    shutil.copy(src_db, dst_db)
    conn = sqlite3.connect(dst_db)
    if espn:
        pg = load_player_games(conn, SEASON, through_date=through)
        tg = load_team_games(conn, SEASON, through_date=through)
        epss = build_player_season_stats(pg, SEASON, current_teams(conn, SEASON))
        etss = build_team_season_stats(tg, SEASON)
        conn.execute("DELETE FROM player_season_stats WHERE season_id = ?", [SEASON])
        epss.to_sql("player_season_stats", conn, if_exists="append", index=False)
        conn.execute("DELETE FROM team_season_stats WHERE season_id = ?", [SEASON])
        etss.to_sql("team_season_stats", conn, if_exists="append", index=False)
        # box scores: ESPN rows for the same games the official table holds
        gids = [r[0] for r in conn.execute("SELECT DISTINCT game_id FROM player_game_stats")]
        conn.execute("DELETE FROM player_game_stats")
        from collectors.espn_boxscores import write_pgs_from_espn
        for g in gids:
            write_pgs_from_espn(conn, g)
        have = {r[0] for r in conn.execute("SELECT player_id FROM roster_assignments WHERE season_id = ?", [SEASON])}
        conn.executemany("INSERT OR IGNORE INTO roster_assignments VALUES (?, ?, ?, '', '')",
                         [(int(r.player_id), int(r.team_id), SEASON) for r in epss.itertuples()
                          if int(r.player_id) not in have])
    conn.commit()
    conn.close()
    if rederive:
        code = ("import sys; sys.path.insert(0, %r); import logging; logging.disable(logging.WARNING)\n"
                "from analysis.synergy import PairSynergyCalculator\n"
                "from analysis.value_scores import ValueScoreCalculator\n"
                "PairSynergyCalculator(%r).compute_pair_synergies(%r)\n"
                "ValueScoreCalculator(%r).compute_all(%r)\n") % (ROOT, dst_db, SEASON, dst_db, SEASON)
        subprocess.run([sys.executable, "-c", code], check=True, cwd=ROOT)


def slate(conn, start, end):
    """(date, home, away, out names per team) for regular-season games in [start, end]."""
    games = q(conn, """SELECT e.game_id, e.game_date, h.abbreviation home, a.abbreviation away,
                              e.team_id home_id, e.opp_team_id away_id
                       FROM espn_team_games e JOIN teams h ON h.team_id = e.team_id
                       JOIN teams a ON a.team_id = e.opp_team_id
                       WHERE e.season_id = ? AND e.is_home = 1 AND e.counts_regular = 1
                         AND e.game_date BETWEEN ? AND ?""", [SEASON, start, end])
    names = dict(conn.execute("SELECT player_id, full_name FROM players"))
    rot = q(conn, "SELECT player_id, team_id FROM player_season_stats WHERE season_id = ? AND minutes_per_game > 5",
            [SEASON])
    rot_by_team = rot.groupby("team_id")["player_id"].apply(set).to_dict()
    played = q(conn, "SELECT game_id, player_id FROM espn_player_games WHERE season_id = ? AND dnp = 0 AND sec > 0",
               [SEASON]).groupby("game_id")["player_id"].apply(set).to_dict()
    out = []
    for g in games.itertuples():
        pl = played.get(g.game_id, set())
        outs = {}
        for abbr, tid in ((g.home, g.home_id), (g.away, g.away_id)):
            outs[abbr] = sorted(names[p] for p in rot_by_team.get(tid, set()) - pl if p in names)
        out.append({"date": g.game_date, "home": g.home, "away": g.away, "out": outs})
    return out


def cmd_price(args):
    """Subprocess: price a slate file with the DB given (fresh module state)."""
    import config
    config.DB_PATH = args.db
    import logging
    logging.disable(logging.WARNING)
    import generate_frontend as gf
    games = json.load(open(args.games))
    teams = gf.read_query(f"""SELECT t.team_id, t.abbreviation, t.full_name, ts.pace, ts.off_rating,
                                     ts.def_rating, ts.net_rating, ts.fg3a_rate
                              FROM team_season_stats ts JOIN teams t ON ts.team_id = t.team_id
                              WHERE ts.season_id = '{gf.CURRENT_SEASON}'""", args.db)
    team_map = {r["abbreviation"]: r for _, r in teams.iterrows()}
    res = []
    for g in games:
        gf._SLATE_DATE_ISO = g["date"]
        rw = {abbr: {"out": names, "starters": []} for abbr, names in g["out"].items()}
        spread, total, bd = gf.compute_moji_spread(team_map[g["home"]], team_map[g["away"]], rw, team_map)
        res.append({**g, "spread": spread, "total": total, "raw_power": bd["raw_power"],
                    "moji_diff": bd["moji_diff"], "nrtg_diff": bd["nrtg_diff"], "syn_pts": bd["syn_pts"]})
    json.dump(res, open(args.out, "w"))


def cmd_spreads(args):
    os.makedirs(args.work, exist_ok=True)
    conn = sqlite3.connect(args.db)
    through = args.through or snapshot_date(conn)[0]
    games = slate(conn, args.start, args.end)
    conn.close()
    gfile = os.path.join(args.work, "slate.json")
    json.dump(games, open(gfile, "w"))
    env = dict(os.environ, NBA_SEASON=SEASON)
    results = {}
    for rederive in (False, True):
        for espn in (False, True):
            name = f"{'espn' if espn else 'official'}{'_rederived' if rederive else ''}"
            db = os.path.join(args.work, f"{name}.db")
            build_variant(args.db, db, espn, through, rederive)
            out = os.path.join(args.work, f"{name}.json")
            subprocess.run([sys.executable, os.path.abspath(__file__), "price", "--db", db, "--games", gfile,
                            "--out", out], check=True, cwd=ROOT, env=env)
            results[name] = json.load(open(out))
    report = {"through": through, "games": len(games)}
    for tag in ("", "_rederived"):
        o, e = results["official" + tag], results["espn" + tag]
        d_spread = [b["spread"] - a["spread"] for a, b in zip(o, e)]
        d_raw = [b["raw_power"] - a["raw_power"] for a, b in zip(o, e)]
        d_total = [b["total"] - a["total"] for a, b in zip(o, e)]
        side_flip = sum(1 for a, b in zip(o, e) if np.sign(a["raw_power"]) != np.sign(b["raw_power"]))
        report["variant" + (tag or "_fixed_derived")] = {
            "spread_diff": dist(d_spread), "raw_power_diff": dist(d_raw), "total_diff": dist(d_total),
            "spread_identical_rate": round(float(np.mean([x == 0 for x in d_spread])), 4),
            "favorite_flips": side_flip,
            "largest": sorted(({"game": f"{a['away']}@{a['home']} {a['date']}", "official": a["spread"],
                                "espn": b["spread"]} for a, b in zip(o, e)),
                              key=lambda r: -abs(r["espn"] - r["official"]))[:8],
        }
    txt = json.dumps(report, indent=1, default=str)
    open(os.path.join(args.work, "spreads_report.json"), "w").write(txt)
    print(txt)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report")
    r.add_argument("--db", required=True)
    r.add_argument("--json")
    s = sub.add_parser("spreads")
    s.add_argument("--db", required=True)
    s.add_argument("--work", required=True)
    s.add_argument("--start", default="2026-02-24")
    s.add_argument("--end", default="2026-04-12")
    s.add_argument("--through")
    p = sub.add_parser("price")
    p.add_argument("--db", required=True)
    p.add_argument("--games", required=True)
    p.add_argument("--out", required=True)
    args = ap.parse_args()
    {"report": cmd_report, "spreads": cmd_spreads, "price": cmd_price}[args.cmd](args)


if __name__ == "__main__":
    main()

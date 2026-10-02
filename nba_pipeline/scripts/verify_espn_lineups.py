#!/usr/bin/env python3
"""verify_espn_lineups.py — ESPN-built lineup_stats vs the stats.nba.com rows.

Evidence for building lineup_stats / lineup_players from ESPN play-by-play
stints (collectors/espn_lineups.py) now that stats.nba.com is blocked on
GitHub Actions. Run against a COPY of nba_sim.db that still holds the
stats.nba.com 2025-26 lineup rows (frozen after the games of 2026-02-12;
the backfill commit "NBA: backfill 2025-26 lineup_stats from ESPN" replaced
them, so take the DB from its parent commit) after
`espn_stats_sync.py --db COPY --season 2025-26 --start 2025-10-21
--end 2026-06-30 --refetch --no-season-stats --cache DIR` has stored the
five-man units (espn_lineup_games).

  python scripts/verify_espn_lineups.py report --db /tmp/v.db [--json out.json]
      per group size: row coverage, selection overlap, GP / minutes /
      plus-minus / shooting / ratings / possessions-column errors
  python scripts/verify_espn_lineups.py calibrate --db /tmp/v.db --cache DIR
      rating conventions (possession credit, one vs two counts) and the
      POSS_SCALE that makes start-of-possession counts match stats.nba.com's
  python scripts/verify_espn_lineups.py spreads --db /tmp/v.db --work DIR
      pair synergy, value scores and compute_moji_spread on 2025-26 games
      with official vs ESPN lineup tables (everything else identical; pair
      synergy and value scores re-derived from each)
"""

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from collections import defaultdict
from itertools import combinations

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collectors.espn_lineups import (  # noqa: E402
    load_units, aggregate_groups, lineup_rows, MAX_ROWS)
from collectors.espn_season_stats import load_team_games, build_team_season_stats  # noqa: E402
from verify_espn_stats import dist, slate  # noqa: E402

SEASON = "2025-26"
SIZES = (2, 3, 4, 5)


def q(conn, sql, args=()):
    return pd.read_sql_query(sql, conn, params=list(args))


def official(conn):
    o = q(conn, "SELECT * FROM lineup_stats WHERE season_id = ?", [SEASON])
    o["key"] = o["lineup_id"] + "|" + o["team_id"].astype(str)
    return o


def snapshot_date(conn, off):
    """Game date through which ESPN 2-man GP best matches the stored rows."""
    units = load_units(conn, SEASON)
    o2 = off[off["group_quantity"] == 2]
    want = {(int(t), lid): int(gp) for t, lid, gp in o2[["team_id", "lineup_id", "gp"]].itertuples(index=False)}
    dates = defaultdict(set)   # (team, lineup_id) -> game dates played together
    for r in units[units["sec"] > 0].itertuples():
        for a, b in combinations(sorted((r.e1, r.e2, r.e3, r.e4, r.e5)), 2):
            k = (int(r.team_id), f"-{a}-{b}-")
            if k in want:
                dates[k].add(r.game_date)
    best = None
    for d in sorted(units["game_date"].unique()):
        err = sum(abs(n - sum(1 for x in dates.get(k, ()) if x <= d)) for k, n in want.items())
        if best is None or err < best[1]:
            best = (d, err)
    return best


def pace_through(conn, through):
    t = build_team_season_stats(load_team_games(conn, SEASON, through_date=through), SEASON)
    return dict(zip(t["team_id"].astype(int), t["pace"]))


def espn_tables(conn, through, **kw):
    units = load_units(conn, SEASON, through)
    groups = aggregate_groups(units)
    ls, lp = lineup_rows(groups, SEASON, pace_through(conn, through), **kw)
    ls["key"] = ls["lineup_id"] + "|" + ls["team_id"].astype(str)
    return ls, lp, groups


def cmd_report(args):
    conn = sqlite3.connect(args.db)
    off = official(conn)
    through = args.through or snapshot_date(conn, off)[0]
    ls, _, groups = espn_tables(conn, through)
    res = {"through": through, "games": int(load_units(conn, SEASON, through)["game_id"].nunique())}
    for n in SIZES:
        o = off[off["group_quantity"] == n]
        e = ls[ls["group_quantity"] == n]
        g = groups[n]
        allkeys = set(g["pids"].map(lambda p: "-" + "-".join(map(str, p)) + "-") + "|" + g["team_id"].astype(str))
        m = o.merge(e, on="key", suffixes=("_o", "_e"))
        rated_o, rated_e = set(o[o["net_rating"].notna()]["key"]), set(e[e["net_rating"].notna()]["key"])
        mr = m[m["net_rating_o"].notna() & m["net_rating_e"].notna()]
        big = mr[mr["minutes_o"] * mr["gp_o"] >= 100]
        r = {
            "official_rows": len(o), "official_rows_found_in_espn_groups": len(set(o["key"]) & allkeys),
            "espn_groups_total": len(allkeys), "espn_rows": len(e),
            "row_set_overlap": len(set(o["key"]) & set(e["key"])),
            "rated_official": len(rated_o), "rated_espn": len(rated_e), "rated_overlap": len(rated_o & rated_e),
            "gp": dist(m["gp_e"] - m["gp_o"]),
            "gp_exact": round(float((m["gp_e"] == m["gp_o"]).mean()), 4),
            "minutes_pg": dist(m["minutes_e"] - m["minutes_o"]),
            "minutes_pg_exact": round(float((m["minutes_e"] == m["minutes_o"]).mean()), 4),
            "plus_minus_pg": dist(m["plus_minus_e"] - m["plus_minus_o"]),
            "plus_minus_pg_exact": round(float((m["plus_minus_e"] == m["plus_minus_o"]).mean()), 4),
            "fga_pg": dist(m["fga_e"] - m["fga_o"]), "fg_pct": dist(m["fg_pct_e"] - m["fg_pct_o"]),
            "fg3_pct": dist(m["fg3_pct_e"] - m["fg3_pct_o"]),
            "possessions_col": dist(m["possessions_e"] - m["possessions_o"]),
            "net_rating": dist(mr["net_rating_e"] - mr["net_rating_o"]),
            "net_rating_100min+": dist(big["net_rating_e"] - big["net_rating_o"]),
            "off_rating": dist(mr["off_rating_e"] - mr["off_rating_o"]),
            "def_rating": dist(mr["def_rating_e"] - mr["def_rating_o"]),
            "net_rating_official_spread": dist(mr["net_rating_o"] - mr["net_rating_o"].mean()),
            "net_rating_corr": round(float(np.corrcoef(mr["net_rating_o"], mr["net_rating_e"])[0, 1]), 4),
        }
        res[f"{n}-man"] = r
    txt = json.dumps(res, indent=1, default=str)
    if args.json:
        open(args.json, "w").write(txt)
    print(txt)


def cmd_calibrate(args):
    """Rating conventions vs stats.nba.com (needs cached ESPN summaries)."""
    from collectors.espn_boxscores import fetch_summary, parse_box, parse_pbp
    conn = sqlite3.connect(args.db)
    off = official(conn)
    through = args.through or "2026-02-12"
    by_abbr = {a: int(t) for t, a in conn.execute("SELECT team_id, abbreviation FROM teams")}
    emap = {str(e): int(p) for e, p in conn.execute("SELECT espn_id, player_id FROM espn_player_map")}
    games = conn.execute("SELECT DISTINCT game_id, espn_event_id FROM espn_team_games WHERE season_id = ? "
                         "AND counts_regular = 1 AND game_date <= ?", [SEASON, through]).fetchall()
    acc = defaultdict(lambda: defaultdict(float))
    for gid, ev in games:
        s = fetch_summary(ev, args.cache)
        box = parse_box(s)
        pbp = parse_pbp(s, box, track_possessions=True)
        tm = {et: by_abbr[t["abbr"]] for et, t in box["teams"].items()}
        ids = lambda u: tuple(sorted(emap.get(a, 0) for a in u))  # noqa: E731
        for et, members, tl in pbp["units"]:
            for n in SIZES:
                for g in combinations(ids(members), n):
                    a = acc[(tm[et], n, g)]
                    for k in ("pts", "opp_pts", "poss", "opp_poss"):
                        a[k] += tl[k]
        for off_t, units in pbp["possessions"]:
            for et, ulist in units.items():
                side = "o" if et == off_t else "d"
                for n in SIZES:
                    for g in set().union(*[set(combinations(ids(u), n)) for u in ulist]):
                        acc[(tm[et], n, g)][side + "_any"] += 1
    rows = []
    for r in off[off["net_rating"].notna()].itertuples():
        k = (r.team_id, r.group_quantity, tuple(sorted(json.loads(r.player_ids))))
        if k in acc:
            rows.append({"n": r.group_quantity, "o": r.off_rating, "d": r.def_rating, "net": r.net_rating, **acc[k]})
    df = pd.DataFrame(rows)
    df = df[(df["poss"] > 0) & (df["opp_poss"] > 0)]
    res = {"through": through, "rated_rows": len(df),
           "any_over_start_possessions": round(float(((df["o_any"] + df["d_any"]) / (df["poss"] + df["opp_poss"])).median()), 4)}
    variants = {
        "start, one count": lambda s: ((df["poss"] + df["opp_poss"]) / 2 * s,) * 2,
        "start, two counts": lambda s: (df["poss"] * s, df["opp_poss"] * s),
        "any-part, one count": lambda s: ((df["o_any"] + df["d_any"]) / 2,) * 2,
        "any-part, two counts": lambda s: (df["o_any"], df["d_any"]),
    }
    for name, f in variants.items():
        for scale in ((1.0, 1.024) if name.startswith("start") else (1.0,)):
            po, pd_ = f(scale)
            o, d = 100 * df["pts"] / po, 100 * df["opp_pts"] / pd_
            for n in (2, 3, 4):
                m = df["n"] == n
                res[f"{name} x{scale} {n}-man"] = {
                    "off_rating": dist((o.round(1) - df["o"])[m]), "def_rating": dist((d.round(1) - df["d"])[m]),
                    "net_rating": dist(((o - d).round(1) - df["net"])[m])}
    txt = json.dumps(res, indent=1)
    if args.json:
        open(args.json, "w").write(txt)
    print(txt)


# ── spreads ──

def build_variant(src_db, dst_db, espn, through):
    shutil.copy(src_db, dst_db)
    conn = sqlite3.connect(dst_db)
    if espn:
        ls, lp, _ = espn_tables(conn, through)
        conn.execute("DELETE FROM lineup_players WHERE season_id = ?", [SEASON])
        conn.execute("DELETE FROM lineup_stats WHERE season_id = ?", [SEASON])
        ls.drop(columns=["key"]).to_sql("lineup_stats", conn, if_exists="append", index=False)
        lp.to_sql("lineup_players", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()
    code = ("import sys; sys.path.insert(0, %r); import logging; logging.disable(logging.WARNING)\n"
            "from analysis.synergy import PairSynergyCalculator\n"
            "from analysis.value_scores import ValueScoreCalculator\n"
            "PairSynergyCalculator(%r).compute_pair_synergies(%r)\n"
            "ValueScoreCalculator(%r).compute_all(%r)\n") % (ROOT, dst_db, SEASON, dst_db, SEASON)
    subprocess.run([sys.executable, "-c", code], check=True, cwd=ROOT)


def compare_derived(db_o, db_e):
    co, ce = sqlite3.connect(db_o), sqlite3.connect(db_e)
    ps_o = q(co, "SELECT * FROM pair_synergy WHERE season_id = ?", [SEASON])
    ps_e = q(ce, "SELECT * FROM pair_synergy WHERE season_id = ?", [SEASON])
    m = ps_o.merge(ps_e, on=["player_a_id", "player_b_id", "team_id"], suffixes=("_o", "_e"))
    out = {"pair_synergy": {"official": len(ps_o), "espn": len(ps_e), "matched": len(m),
                            "synergy_score": dist(m["synergy_score_e"] - m["synergy_score_o"]),
                            "net_rating_shrunk": dist(m["net_rating_e"] - m["net_rating_o"]),
                            "corr": round(float(np.corrcoef(m["synergy_score_o"], m["synergy_score_e"])[0, 1]), 4)}}
    vs_o = q(co, "SELECT * FROM player_value_scores WHERE season_id = ?", [SEASON])
    vs_e = q(ce, "SELECT * FROM player_value_scores WHERE season_id = ?", [SEASON])
    v = vs_o.merge(vs_e, on="player_id", suffixes=("_o", "_e"))
    out["value_scores"] = {"matched": len(v)}
    for k in ("two_man_synergy", "three_man_synergy", "four_man_synergy", "five_man_synergy",
              "archetype_fit_score", "composite_value"):
        out["value_scores"][k] = dist(v[f"{k}_e"] - v[f"{k}_o"])
    return out


def cmd_spreads(args):
    os.makedirs(args.work, exist_ok=True)
    conn = sqlite3.connect(args.db)
    through = args.through or "2026-02-12"
    games = slate(conn, args.start, args.end)
    conn.close()
    gfile = os.path.join(args.work, "slate.json")
    json.dump(games, open(gfile, "w"))
    env = dict(os.environ, NBA_SEASON=SEASON)
    results, dbs = {}, {}
    for espn in (False, True):
        name = "espn" if espn else "official"
        db = dbs[name] = os.path.join(args.work, f"lineups_{name}.db")
        build_variant(args.db, db, espn, through)
        out = os.path.join(args.work, f"lineups_{name}.json")
        subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_espn_stats.py"),
                        "price", "--db", db, "--games", gfile, "--out", out], check=True, cwd=ROOT, env=env)
        results[name] = json.load(open(out))
    o, e = results["official"], results["espn"]
    d_spread = [b["spread"] - a["spread"] for a, b in zip(o, e)]
    report = {"lineups_through": through, "slate": f"{args.start}..{args.end}", "games": len(games),
              **compare_derived(dbs["official"], dbs["espn"]),
              "syn_pts_diff": dist([b["syn_pts"] - a["syn_pts"] for a, b in zip(o, e)]),
              "raw_power_diff": dist([b["raw_power"] - a["raw_power"] for a, b in zip(o, e)]),
              "spread_diff": dist(d_spread),
              "spread_identical_rate": round(float(np.mean([x == 0 for x in d_spread])), 4),
              "spread_within_one_step_rate": round(float(np.mean([abs(x) <= 0.5 for x in d_spread])), 4),
              "total_diff": dist([b["total"] - a["total"] for a, b in zip(o, e)]),
              "favorite_flips": sum(1 for a, b in zip(o, e) if np.sign(a["raw_power"]) != np.sign(b["raw_power"])),
              "largest": sorted(({"game": f"{a['away']}@{a['home']} {a['date']}", "official": a["spread"],
                                  "espn": b["spread"], "syn_pts": [a["syn_pts"], b["syn_pts"]]}
                                 for a, b in zip(o, e)), key=lambda r: -abs(r["espn"] - r["official"]))[:10]}
    txt = json.dumps(report, indent=1, default=str)
    open(os.path.join(args.work, "lineup_spreads_report.json"), "w").write(txt)
    print(txt)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report")
    r.add_argument("--db", required=True)
    r.add_argument("--through")
    r.add_argument("--json")
    c = sub.add_parser("calibrate")
    c.add_argument("--db", required=True)
    c.add_argument("--cache", required=True)
    c.add_argument("--through")
    c.add_argument("--json")
    s = sub.add_parser("spreads")
    s.add_argument("--db", required=True)
    s.add_argument("--work", required=True)
    s.add_argument("--through")
    s.add_argument("--start", default="2026-02-19")
    s.add_argument("--end", default="2026-04-12")
    args = ap.parse_args()
    {"report": cmd_report, "calibrate": cmd_calibrate, "spreads": cmd_spreads}[args.cmd](args)


if __name__ == "__main__":
    main()

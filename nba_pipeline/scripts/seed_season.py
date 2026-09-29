#!/usr/bin/env python3
"""seed_season.py — carry last season's player/team priors into a new season.

On opening night every season-scoped table is empty for the new season, so
MOJI (player_value_scores), synergy (pair_synergy / lineup_stats), rosters,
team ratings and coaching schemes would all read as zero. This script seeds
the new season from the previous one, mapped onto the NEW rosters:

  * player tables (value scores, season stats, archetypes, play types):
    last season's row for every player on a new-season roster, team_id set
    to his new team. Rookies get no seed (the model's defaults apply).
  * pair_synergy / lineup_stats / lineup_players: only pairs and lineups whose
    players are all still teammates on the same new team.
  * team tables (team_season_stats, coaching_profiles, team_playtypes):
    last season's row per team.

Idempotent and non-destructive: a seed row is inserted only where the new
season has no row for that key yet, so real new-season data (written by the
collectors) always wins and re-running changes nothing. Seeded rows are
logged by count.

If no new-season rosters exist (roster fetch failed everywhere), last
season's roster assignments are carried over with a warning so the slate
still prices.

Usage:
  python scripts/seed_season.py                       # to = CURRENT_SEASON
  python scripts/seed_season.py --to 2026-27 --from 2025-26 [--db path]
"""

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import DB_PATH, CURRENT_SEASON, previous_season  # noqa: E402

PLAYER_TABLES = [
    # (table, key columns besides season_id)
    ("player_value_scores", ("player_id",)),
    ("player_season_stats", ("player_id",)),
    ("player_archetypes", ("player_id",)),
    ("player_playtypes", ("player_id", "play_type", "type_grouping")),
]
TEAM_TABLES = [
    ("team_season_stats", ("team_id",)),
    ("coaching_profiles", ("team_id",)),
    ("team_playtypes", ("team_id", "play_type", "type_grouping")),
]


def cols(con, table):
    return [r[1] for r in con.execute(f"PRAGMA table_info('{table}')")]


def existing_keys(con, table, keys, season):
    q = f"SELECT {', '.join(keys)} FROM {table} WHERE season_id = ?"
    return {tuple(r) for r in con.execute(q, [season])}


def insert_rows(con, table, columns, rows):
    if not rows:
        return 0
    ph = ",".join("?" for _ in columns)
    con.executemany(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({ph})", rows)
    return len(rows)


def seed(db_path, to_season, from_season):
    con = sqlite3.connect(db_path)
    report = {}

    roster = dict(con.execute(
        "SELECT player_id, team_id FROM roster_assignments WHERE season_id = ?", [to_season]).fetchall())
    if not roster:
        prev = con.execute(
            "SELECT player_id, team_id, jersey_number, listed_position FROM roster_assignments WHERE season_id = ?",
            [from_season]).fetchall()
        print(f"WARNING: no {to_season} rosters in DB; carrying over {len(prev)} {from_season} assignments")
        con.executemany(
            "INSERT INTO roster_assignments (player_id, team_id, season_id, jersey_number, listed_position) "
            "VALUES (?, ?, ?, ?, ?)", [(p, t, to_season, j, lp) for p, t, j, lp in prev])
        report["roster_assignments (carried over)"] = len(prev)
        roster = {p: t for p, t, _, _ in prev}

    # ── player-level priors, remapped to new teams ──
    for table, keys in PLAYER_TABLES:
        c = cols(con, table)
        have = existing_keys(con, table, keys, to_season)
        rows = []
        for r in con.execute(f"SELECT {', '.join(c)} FROM {table} WHERE season_id = ?", [from_season]):
            rec = dict(zip(c, r))
            pid = rec["player_id"]
            if pid not in roster:
                continue  # retired / unsigned: no prior on a roster
            if tuple(rec[k] for k in keys) in have:
                continue
            rec["season_id"] = to_season
            if "team_id" in rec:
                rec["team_id"] = roster[pid]
            if "updated_at" in rec:
                rec["updated_at"] = f"seed:{from_season}"
            rows.append([rec[k] for k in c])
        report[table] = insert_rows(con, table, c, rows)

    # ── team-level priors ──
    for table, keys in TEAM_TABLES:
        c = cols(con, table)
        have = existing_keys(con, table, keys, to_season)
        rows = []
        seen = set()
        for r in con.execute(f"SELECT {', '.join(c)} FROM {table} WHERE season_id = ? ORDER BY rowid DESC",
                             [from_season]):
            rec = dict(zip(c, r))
            k = tuple(rec[x] for x in keys)
            if k in have or k in seen:
                continue  # newest row per key only (team_season_stats has duplicates)
            seen.add(k)
            rec["season_id"] = to_season
            rows.append([rec[x] for x in c])
        report[table] = insert_rows(con, table, c, rows)

    # ── pair synergy: both players still teammates ──
    c = cols(con, "pair_synergy")
    have = {(a, b) for a, b in con.execute(
        "SELECT player_a_id, player_b_id FROM pair_synergy WHERE season_id = ?", [to_season])}
    rows = []
    for r in con.execute(f"SELECT {', '.join(c)} FROM pair_synergy WHERE season_id = ?", [from_season]):
        rec = dict(zip(c, r))
        a, b = rec["player_a_id"], rec["player_b_id"]
        if roster.get(a) is None or roster.get(a) != roster.get(b) or (a, b) in have:
            continue
        rec.update(season_id=to_season, team_id=roster[a])
        rows.append([rec[k] for k in c])
    report["pair_synergy"] = insert_rows(con, "pair_synergy", c, rows)

    # ── lineups: every player still on the same new team ──
    c = cols(con, "lineup_stats")
    have = {r[0] for r in con.execute("SELECT lineup_id FROM lineup_stats WHERE season_id = ?", [to_season])}
    rows, members = [], []
    for r in con.execute(f"SELECT {', '.join(c)} FROM lineup_stats WHERE season_id = ?", [from_season]):
        rec = dict(zip(c, r))
        try:
            pids = [int(x) for x in json.loads(rec["player_ids"])]
        except (ValueError, TypeError):
            continue
        teams = {roster.get(p) for p in pids}
        if len(teams) != 1 or None in teams or rec["lineup_id"] in have:
            continue
        rec.update(season_id=to_season, team_id=teams.pop())
        rows.append([rec[k] for k in c])
        members.extend((rec["lineup_id"], to_season, p) for p in pids)
    report["lineup_stats"] = insert_rows(con, "lineup_stats", c, rows)
    con.executemany("INSERT OR IGNORE INTO lineup_players (lineup_id, season_id, player_id) VALUES (?, ?, ?)",
                    members)
    report["lineup_players"] = len(members)

    con.commit()
    con.close()
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--to", dest="to_season", default=CURRENT_SEASON)
    ap.add_argument("--from", dest="from_season", default=None)
    ap.add_argument("--db", default=DB_PATH)
    args = ap.parse_args()
    from_season = args.from_season or previous_season(args.to_season)

    con = sqlite3.connect(args.db)
    have_prior = con.execute("SELECT COUNT(*) FROM player_value_scores WHERE season_id = ?",
                             [from_season]).fetchone()[0]
    con.close()
    if not have_prior:
        print(f"No {from_season} player values to seed from; nothing to do")
        return

    report = seed(args.db, args.to_season, from_season)
    print(f"Seeded {args.to_season} from {from_season} (rows inserted; 0 = already present):")
    for table, n in report.items():
        print(f"  {table:34s} {n}")


if __name__ == "__main__":
    main()

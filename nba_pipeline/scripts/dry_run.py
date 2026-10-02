#!/usr/bin/env python3
"""dry_run.py — opening-week rehearsal of the daily NBA pipeline on a scratch copy.

Runs the update-lines steps (plus the trends refresh and grading) exactly as
the workflow does, but inside a COPY of the repo, with NBA_DRY_RUN=1 so ESPN
reports preseason games as regular season (collectors/games_espn.py). One
preseason slate then exercises everything opening night will: ESPN
scoreboard + per-game summaries from wherever this runs, box/season/lineup
stats replacing seeded priors, freshness, RotoWire lineups and lines,
line snapshots (closing-line source), the dashboard, pick capture, ledger
checks, picks/nba.json, the public pages and grading.

Safety: nothing outside the scratch copy is written. The real ledger
(nba_pipeline/data/picks.csv, pick_log.json, picks/nba.json) is hashed before
and after and the run fails if it changed. Nothing is committed or posted
(the workflow's dry-run job has no commit / bot step and read-only
permissions).

  python nba_pipeline/scripts/dry_run.py stage --out /tmp/nba-dry
  python nba_pipeline/scripts/dry_run.py probe --dates 2025-10-04,2025-10-05 --json /tmp/probe.json
  python nba_pipeline/scripts/dry_run.py run --root /tmp/nba-dry [--date 2026-10-04]
      [--sync-dates 2026-10-03] [--only "step name" ...]

`run` writes <root>/dry_run_report.json and a markdown summary (also to
$GITHUB_STEP_SUMMARY on Actions). Exit 1 when a required step failed or the
real ledger changed.
"""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

THIS = os.path.abspath(__file__)
PIPELINE = os.path.dirname(os.path.dirname(THIS))
REPO = os.path.dirname(PIPELINE)

# repo-root scripts/ (page builders, seal-mode store / unseal) and ops/config
# (seal-mode switch) are used by the NBA steps too
STAGE_DIRS = ["nba_pipeline", "picks", "nbasim", "sim", "scripts", "ops"]
STAGE_FILES = []
LEDGER = ["nba_pipeline/data/picks.csv", "nba_pipeline/data/pick_log.json", "picks/nba.json"]
PY = sys.executable

GAMES_CODE = """
import sys, os, logging
sys.path.insert(0, os.getcwd())
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
from config import DB_PATH, CURRENT_SEASON
from collectors.games_espn import ESPNGameCollector
n = ESPNGameCollector(DB_PATH).update_games_table(CURRENT_SEASON, days=21)
print(f'ESPN: {n} games added/updated')
"""
ROSTER_CODE = """
import sys, os, logging
sys.path.insert(0, os.getcwd())
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
from config import DB_PATH, CURRENT_SEASON
from collectors.players import PlayerCollector
pc = PlayerCollector(DB_PATH)
pc.collect_teams()
for f in (pc.collect_rosters, pc.collect_player_season_stats, pc.collect_team_season_stats):
    try: f(CURRENT_SEASON)
    except Exception as e: print(f'{f.__name__} failed (using cached): {e}')
"""

# (name, cwd relative to root, argv, timeout seconds, required)
# Mirrors .github/workflows/nba-pipeline.yml update-lines (and refresh-trends /
# grade-picks); "required" = the workflow step has no continue-on-error.
STEPS = [
    ("Unseal tipped NBA picks", ".", [PY, "scripts/unseal_picks.py", "--sport", "nba"], 120, True),
    ("ESPN game scores", "nba_pipeline", [PY, "-c", GAMES_CODE], 180, False),
    ("Rosters + player stats (stats.nba.com)", "nba_pipeline", [PY, "-c", ROSTER_CODE], 480, False),
    ("ESPN box scores + season + lineup stats", "nba_pipeline", [PY, "scripts/espn_stats_sync.py"], 720, False),
    ("Trends refresh (synergy from lineups)", "nba_pipeline", [PY, "scripts/refresh_trends.py"], 900, True),
    ("Seed priors", "nba_pipeline", [PY, "scripts/seed_season.py"], 120, True),
    ("Freshness check", "nba_pipeline", [PY, "scripts/check_freshness.py"], 60, True),
    ("Generate dashboard", "nba_pipeline", [PY, "generate_frontend.py"], 900, True),
    ("Intelligence snapshot", "nba_pipeline", [PY, "scripts/snapshot_daily.py"], 300, False),
    ("Capture picks", "nba_pipeline", [PY, "scripts/capture_picks.py"], 120, True),
    ("Ledger integrity", "nba_pipeline", [PY, "scripts/check_ledger.py"], 60, True),
    ("Blog entry", "nba_pipeline", [PY, "scripts/generate_blog_entry.py"], 120, True),
    ("Sync picks/nba.json", ".", [PY, "nba_pipeline/scripts/sync_to_picks_json.py"], 60, True),
    ("Build /nbasim/", ".", [PY, "scripts/build_nbasim_app.py"], 60, True),
    ("Build /sim/", ".", [PY, "scripts/build_sim_app.py"], 60, True),
    ("Grade picks", "nba_pipeline", [PY, "scripts/grade_picks.py"], 300, True),
]


def sha(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def cmd_stage(args):
    out = os.path.abspath(args.out)
    if out == REPO or out.startswith(REPO + os.sep) and not args.allow_inside:
        sys.exit(f"refusing to stage inside the repo ({REPO})")
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.db-shm", "*.db-wal", ".env")
    for d in STAGE_DIRS:
        if os.path.isdir(os.path.join(REPO, d)):
            shutil.copytree(os.path.join(REPO, d), os.path.join(out, d), ignore=ignore)
    for f in STAGE_FILES:
        os.makedirs(os.path.dirname(os.path.join(out, f)), exist_ok=True)
        shutil.copy2(os.path.join(REPO, f), os.path.join(out, f))
    with open(os.path.join(out, "DRY_RUN"), "w") as f:
        f.write(f"staged from {REPO} at {datetime.now(timezone.utc).isoformat()}\n")
    print(f"Staged scratch copy at {out}")


def cmd_probe(args):
    """ESPN scoreboard + per-game summary for every completed game on the dates
    (any season type): reachability, latency, and whether the play-by-play
    reconstruction (minutes, points, five-man units) holds. No DB writes."""
    sys.path.insert(0, PIPELINE)
    from collectors.games_espn import fetch_espn_events
    from collectors.espn_boxscores import fetch_summary, parse_box, parse_pbp
    res = {"dates": {}, "summaries": 0, "summary_failures": 0, "pbp_ok": 0}
    for d in [x for x in args.dates.split(",") if x]:
        t0 = time.time()
        ev = fetch_espn_events(datetime.strptime(d, "%Y-%m-%d"))
        day = {"scoreboard_ok": ev is not None, "scoreboard_sec": round(time.time() - t0, 2), "games": []}
        for e in ev or []:
            g = {"game": f"{e['away_abbr']}@{e['home_abbr']}", "season_type": e["season_type"],
                 "completed": e["completed"]}
            if e["completed"]:
                t1 = time.time()
                s = fetch_summary(e["event_id"])
                g["summary_sec"] = round(time.time() - t1, 2)
                res["summaries"] += 1
                if not s or "boxscore" not in s:
                    g["summary_ok"] = False
                    res["summary_failures"] += 1
                else:
                    box = parse_box(s)
                    pbp = parse_pbp(s, box)
                    g.update(summary_ok=True, plays=len(s.get("plays") or []), players=len(box["players"]),
                             pbp_ok=pbp["ok"], units=len(pbp["units"]), issues=pbp["issues"][:3])
                    res["pbp_ok"] += 1 if pbp["ok"] else 0
            day["games"].append(g)
        res["dates"][d] = day
    txt = json.dumps(res, indent=1)
    if args.json:
        with open(args.json, "w") as f:
            f.write(txt)
    print(txt)
    return 1 if res["summary_failures"] or any(not v["scoreboard_ok"] for v in res["dates"].values()) else 0


def tail(text, n=25):
    lines = (text or "").strip().splitlines()
    return "\n".join(lines[-n:])


def collect_outputs(root, before_db_stats):
    """What the rehearsal produced, read from the scratch copy."""
    sys.path.insert(0, os.path.join(root, "nba_pipeline"))
    out = {}
    dp = os.path.join(root, "nba_pipeline", "data", "daily_picks.json")
    if os.path.exists(dp):
        d = json.load(open(dp))
        out["slate"] = {"slate_date": d.get("slate_date"), "slate_date_iso": d.get("slate_date_iso"),
                        "games": [{k: g.get(k) for k in ("matchup", "season_type", "tip_at", "book_spread",
                                                          "book_total", "sim_spread", "sim_total", "pick_text",
                                                          "conf_label")} for g in d.get("games", [])]}
    snap = os.path.join(root, "nba_pipeline", "data", "line_snapshots.csv")
    if os.path.exists(snap):
        rows = open(snap).read().strip().splitlines()
        out["line_snapshots"] = {"rows": max(0, len(rows) - 1), "last": rows[-3:]}
    else:
        out["line_snapshots"] = {"rows": 0}
    for rel in LEDGER:
        p = os.path.join(root, rel)
        orig = os.path.join(REPO, rel)
        if rel.endswith(".csv") and os.path.exists(p):
            n_new, n_old = len(open(p).read().splitlines()), len(open(orig).read().splitlines()) if os.path.exists(orig) else 0
            out.setdefault("scratch_ledger", {})[rel] = {"rows_added": n_new - n_old,
                                                         "new_rows": open(p).read().splitlines()[n_old:][:20]}
        else:
            out.setdefault("scratch_ledger", {})[rel] = {"changed": sha(p) != sha(orig)}
    db = os.path.join(root, "nba_pipeline", "db", "nba_sim.db")
    con = sqlite3.connect(db)
    season = os.environ.get("NBA_SEASON") or _season()
    q = lambda s, a=(): con.execute(s, a).fetchall()  # noqa: E731
    out["db"] = {
        "season": season,
        "size_mb": round(os.path.getsize(db) / 1e6, 2),
        "size_mb_before": before_db_stats.get("size_mb"),
        "games_scored": q("SELECT COUNT(*) FROM games WHERE season_id = ? AND home_score IS NOT NULL", [season])[0][0],
        "espn_games": q("SELECT COUNT(DISTINCT game_id) FROM espn_team_games WHERE season_id = ?", [season])[0][0],
        "espn_lineup_units": q("SELECT COUNT(*) FROM espn_lineup_games u JOIN espn_team_games t ON "
                               "t.game_id = u.game_id AND t.team_id = u.team_id WHERE t.season_id = ?", [season])[0][0]
        if q("SELECT 1 FROM sqlite_master WHERE name = 'espn_lineup_games'") else 0,
        "stats_source": q("SELECT table_name, source, as_of, max_gp FROM stats_source WHERE season_id = ?", [season]),
        "team_season_stats_gp": q("SELECT gp, COUNT(*) FROM team_season_stats WHERE season_id = ? GROUP BY gp", [season]),
        "lineup_stats_rows": q("SELECT group_quantity, COUNT(*), SUM(net_rating IS NOT NULL), MAX(gp) FROM lineup_stats "
                               "WHERE season_id = ? GROUP BY group_quantity", [season]),
        "pair_synergy_rows": q("SELECT COUNT(*) FROM pair_synergy WHERE season_id = ?", [season])[0][0],
        "teams_with_real_stats": q("SELECT t.abbreviation, s.gp, s.net_rating, s.pace FROM team_season_stats s JOIN teams t "
                                   "USING(team_id) WHERE s.season_id = ? AND s.gp < 82 ORDER BY 1", [season]),
    }
    return out


def _season():
    d = datetime.now(timezone.utc).date()
    start = d.year if d.month >= 10 else d.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def cmd_run(args):
    root = os.path.abspath(args.root)
    if root == REPO or not os.path.exists(os.path.join(root, "DRY_RUN")):
        sys.exit(f"{root} is not a staged dry-run copy (run `stage` first); refusing to run on the real repo")
    ledger_before = {rel: sha(os.path.join(REPO, rel)) for rel in LEDGER}
    db = os.path.join(root, "nba_pipeline", "db", "nba_sim.db")
    before = {"size_mb": round(os.path.getsize(db) / 1e6, 2)}
    env = dict(os.environ, NBA_DRY_RUN="1", PYTHONUNBUFFERED="1")
    if args.date:
        env["NBA_DRY_RUN_DATE"] = args.date
    steps = list(STEPS)
    if args.sync_dates:
        ds = sorted(args.sync_dates.split(","))
        steps.insert(4, ("ESPN box scores for --sync-dates", "nba_pipeline",
                         [PY, "scripts/espn_stats_sync.py", "--start", ds[0], "--end", ds[-1]], 720, False))
    if args.only:
        steps = [s for s in steps if s[0] in args.only]
    results = []
    for name, cwd, argv, timeout, required in steps:
        t0 = time.time()
        try:
            p = subprocess.run(argv, cwd=os.path.join(root, cwd), env=env, capture_output=True, text=True,
                               timeout=timeout)
            rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
            status = "ok" if rc == 0 else ("FAILED" if required else "failed (continue-on-error)")
        except subprocess.TimeoutExpired as e:
            rc, out = None, ((e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")) \
                + ((e.stderr or b"").decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or ""))
            status = f"TIMEOUT after {timeout}s" + ("" if required else " (continue-on-error)")
        dur = round(time.time() - t0, 1)
        results.append({"step": name, "status": status, "rc": rc, "sec": dur, "required": required,
                        "log_tail": tail(out, 40)})
        with open(os.path.join(root, f"log_{len(results):02d}_{name.split()[0].lower()}.txt"), "w") as f:
            f.write(out or "")
        print(f"[{status:>28s}] {name} ({dur}s)", flush=True)
    ledger_after = {rel: sha(os.path.join(REPO, rel)) for rel in LEDGER}
    report = {"date": args.date, "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "root": root, "steps": results,
              "real_ledger_unchanged": ledger_before == ledger_after}
    try:
        report["outputs"] = collect_outputs(root, before)
    except Exception as e:  # noqa: BLE001 — the report must still be written
        report["outputs_error"] = repr(e)
    with open(os.path.join(root, "dry_run_report.json"), "w") as f:
        json.dump(report, f, indent=1, default=str)
    md = markdown(report)
    print(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(md + "\n")
    bad = [r for r in results if r["required"] and r["status"] != "ok"]
    if not report["real_ledger_unchanged"]:
        print("::error::dry run changed the REAL ledger")
        return 1
    return 1 if bad else 0


def markdown(r):
    lines = [f"## NBA dry run — {r.get('date') or 'today'} ({r['ran_at']})", "",
             "| step | status | sec |", "|---|---|---|"]
    lines += [f"| {s['step']} | {s['status']} | {s['sec']} |" for s in r["steps"]]
    o = r.get("outputs") or {}
    sl = o.get("slate") or {}
    lines += ["", f"Slate: {sl.get('slate_date')} ({sl.get('slate_date_iso')}), {len(sl.get('games') or [])} games"]
    for g in sl.get("games") or []:
        lines.append(f"- {g['matchup']}: type {g['season_type']}, book {g['book_spread']}/{g['book_total']}, "
                     f"sim {g['sim_spread']}/{g['sim_total']}, {g['conf_label']} {g['pick_text']}")
    lines.append(f"Line snapshots: {(o.get('line_snapshots') or {}).get('rows')}")
    for k, v in (o.get("scratch_ledger") or {}).items():
        lines.append(f"Scratch {k}: {v.get('rows_added', v.get('changed'))}")
    dbs = o.get("db") or {}
    lines.append(f"DB: {dbs.get('size_mb_before')} -> {dbs.get('size_mb')} MB; {dbs.get('espn_games')} ESPN games, "
                 f"{dbs.get('espn_lineup_units')} lineup units; sources {dbs.get('stats_source')}")
    lines.append(f"Real ledger unchanged: {r['real_ledger_unchanged']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--out", required=True)
    s.add_argument("--allow-inside", action="store_true", help=argparse.SUPPRESS)
    p = sub.add_parser("probe")
    p.add_argument("--dates", required=True)
    p.add_argument("--json")
    r = sub.add_parser("run")
    r.add_argument("--root", required=True)
    r.add_argument("--date", help="the preseason date being rehearsed (default: today)")
    r.add_argument("--sync-dates", help="extra comma-separated dates to sync ESPN box scores for")
    r.add_argument("--only", nargs="*")
    args = ap.parse_args()
    return {"stage": cmd_stage, "probe": cmd_probe, "run": cmd_run}[args.cmd](args) or 0


if __name__ == "__main__":
    sys.exit(main())

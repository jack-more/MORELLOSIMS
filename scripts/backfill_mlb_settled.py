#!/usr/bin/env python3
"""
Backfill historical settled MLB picks.

Strategy:
  1. Walk all `MLB SIM —` commits in git history.
  2. For each commit, extract C:10 picks from mlbsim/index.html at that snapshot.
  3. Also ingest mlbsim/picks_log.csv (current working log).
  4. Dedupe by (date, away, home, pick_team) — keep latest odds.
  5. Apply current odds filter (|odds| < 350).
  6. Hit statsapi.mlb.com to settle each pick against the actual final score.
  7. Output mlbsim/settled_picks.csv with full W/L + P&L history.
"""
import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
HTML_PATH = "mlbsim/index.html"
CSV_PATH = os.path.join(REPO, "mlbsim", "picks_log.csv")
OUT_PATH = os.path.join(REPO, "mlbsim", "settled_picks.csv")
RECORD_PATH = os.path.join(REPO, "mlbsim", "record.json")

UNIT_SIZE = 50  # $PP per C:10 pick
ODDS_CAP = 350  # |odds| < 350 (matches current MAX_FAV_BY_CONF[10])


def run(cmd, **kw):
    return subprocess.check_output(cmd, cwd=REPO, text=True, **kw)


# ── 1) Git: list all MLB SIM commits ──────────────────────────────────────────
def list_mlb_sim_commits():
    out = run(["git", "log", "--all", "--pretty=format:%H\t%s"])
    commits = []
    for line in out.strip().split("\n"):
        if "\t" not in line:
            continue
        h, msg = line.split("\t", 1)
        if msg.startswith("MLB SIM —") and "NO PLAYS" not in msg:
            commits.append((h, msg))
    return commits


# ── 2) Parse C:10 picks from a snapshot of mlbsim/index.html ──────────────────
GAME_CARD_RE = re.compile(
    r'<div class="game-card"\s+data-conf="(\d+)"[^>]*>(.*?)(?=<div class="game-card"|</main>|$)',
    re.DOTALL,
)

def parse_picks_from_html(html, sim_date):
    """Extract C:10 picks: (date, away, home, away_ml, home_ml, pick_team, pick_ml, conf)."""
    picks = []
    for m in GAME_CARD_RE.finditer(html):
        conf = int(m.group(1))
        if conf < 10:
            continue
        body = m.group(2)
        teams = re.findall(r'<div class="team-abbr">([^<]+)</div>\s*<div class="team-ml">([+-]?\d+)</div>', body)
        if len(teams) < 2:
            continue
        away_abbr, away_ml = teams[0]
        home_abbr, home_ml = teams[1]
        pick_m = re.search(r'<span class="pick-type-label">ML</span>\s*([A-Z]{2,4})\s+ML\s*\(([+-]?\d+)\)', body)
        if not pick_m:
            continue
        pick_team = pick_m.group(1)
        pick_ml = int(pick_m.group(2))
        if abs(pick_ml) >= ODDS_CAP:
            continue
        picks.append({
            "date": sim_date,
            "away": away_abbr,
            "home": home_abbr,
            "away_ml": int(away_ml),
            "home_ml": int(home_ml),
            "pick_team": pick_team,
            "pick_ml": pick_ml,
            "conf": conf,
        })
    return picks


def commit_date_to_iso(msg):
    """Convert 'MLB SIM — Apr 30 06:55 PM ET' → '2026-04-30'."""
    m = re.search(r"—\s+(\w{3})\s+(\d{1,2})", msg)
    if not m:
        return None
    months = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,"Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
    mo = months.get(m.group(1))
    if not mo:
        return None
    return f"2026-{mo:02d}-{int(m.group(2)):02d}"


# ── 3) Ingest picks_log.csv (most current) ────────────────────────────────────
def parse_csv():
    picks = []
    if not os.path.exists(CSV_PATH):
        return picks
    with open(CSV_PATH) as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            try:
                conf = int(r["conf"])
            except (ValueError, KeyError):
                continue
            if conf < 10:
                continue
            try:
                away_ml = int(r["away_ml"])
                home_ml = int(r["home_ml"])
            except (ValueError, KeyError):
                continue
            pick_team = r["pick"]
            pick_ml = away_ml if pick_team == r["away"] else home_ml
            if abs(pick_ml) >= ODDS_CAP:
                continue
            picks.append({
                "date": r["date"],
                "away": r["away"],
                "home": r["home"],
                "away_ml": away_ml,
                "home_ml": home_ml,
                "pick_team": pick_team,
                "pick_ml": pick_ml,
                "conf": conf,
            })
    return picks


# ── 4) Dedupe ─────────────────────────────────────────────────────────────────
def dedupe(picks):
    """Keep latest entry per (date, away, home, pick_team) — assumes input order is chronological."""
    seen = {}
    for p in picks:
        key = (p["date"], p["away"], p["home"], p["pick_team"])
        seen[key] = p  # last write wins
    return list(seen.values())


# ── 5) MLB Stats API ──────────────────────────────────────────────────────────
TEAM_ALIAS = {
    "ATH": "OAK", "AZ": "ARI", "CWS": "CHW", "TB": "TBR", "WSH": "WSN", "SF": "SFG",
    "KC": "KCR", "SD": "SDP",
}

def normalize(abbr):
    return TEAM_ALIAS.get(abbr, abbr)


def fetch_schedule(date_iso):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_iso}&hydrate=linescore,team"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def settle_date(date_iso, picks_for_date, schedule_cache):
    if date_iso not in schedule_cache:
        try:
            schedule_cache[date_iso] = fetch_schedule(date_iso)
        except Exception as e:
            print(f"  [WARN] API fetch failed for {date_iso}: {e}")
            schedule_cache[date_iso] = None
            return
        time.sleep(0.2)  # be polite to the API

    data = schedule_cache[date_iso]
    if not data or "dates" not in data or not data["dates"]:
        return

    games = []
    for d in data["dates"]:
        for g in d.get("games", []):
            games.append(g)

    for p in picks_for_date:
        match = find_game(games, p["away"], p["home"])
        if not match:
            p["result"] = "—"
            p["pl"] = 0
            p["away_score"] = ""
            p["home_score"] = ""
            continue
        ls = match.get("linescore", {})
        away_runs = ls.get("teams", {}).get("away", {}).get("runs")
        home_runs = ls.get("teams", {}).get("home", {}).get("runs")
        status = match.get("status", {}).get("abstractGameState")
        if away_runs is None or home_runs is None or status != "Final":
            p["result"] = "PENDING" if status != "Final" else "—"
            p["pl"] = 0
            p["away_score"] = away_runs if away_runs is not None else ""
            p["home_score"] = home_runs if home_runs is not None else ""
            continue

        winner = p["away"] if away_runs > home_runs else p["home"]
        is_win = winner == p["pick_team"]
        p["result"] = "W" if is_win else "L"
        p["away_score"] = away_runs
        p["home_score"] = home_runs

        ml = p["pick_ml"]
        if is_win:
            if ml > 0:
                p["pl"] = round(UNIT_SIZE * ml / 100, 2)
            else:
                p["pl"] = round(UNIT_SIZE * 100 / abs(ml), 2)
        else:
            p["pl"] = -UNIT_SIZE


def find_game(games, away_abbr, home_abbr):
    """Find an MLB API game matching the (away, home) abbreviation pair."""
    away_n = normalize(away_abbr)
    home_n = normalize(home_abbr)
    for g in games:
        a = normalize(g.get("teams", {}).get("away", {}).get("team", {}).get("abbreviation", ""))
        h = normalize(g.get("teams", {}).get("home", {}).get("team", {}).get("abbreviation", ""))
        if a == away_n and h == home_n:
            return g
    return None


# ── 6) Main ───────────────────────────────────────────────────────────────────
def main():
    all_picks = []

    print("Walking git for MLB SIM commits…")
    commits = list_mlb_sim_commits()
    print(f"  Found {len(commits)} MLB SIM commits with picks.")

    for h, msg in commits:
        sim_date = commit_date_to_iso(msg)
        if not sim_date:
            continue
        try:
            html = run(["git", "show", f"{h}:{HTML_PATH}"], stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            continue
        picks = parse_picks_from_html(html, sim_date)
        all_picks.extend(picks)

    print(f"  Picks extracted from git: {len(all_picks)}")

    csv_picks = parse_csv()
    print(f"  Picks from picks_log.csv: {len(csv_picks)}")
    all_picks.extend(csv_picks)

    deduped = dedupe(all_picks)
    print(f"  After dedupe: {len(deduped)}")

    # Group by date for batched API calls
    by_date = defaultdict(list)
    for p in deduped:
        by_date[p["date"]].append(p)

    print(f"\nSettling against MLB Stats API ({len(by_date)} unique dates)…")
    schedule_cache = {}
    for date_iso in sorted(by_date.keys()):
        settle_date(date_iso, by_date[date_iso], schedule_cache)
        wins = sum(1 for p in by_date[date_iso] if p.get("result") == "W")
        losses = sum(1 for p in by_date[date_iso] if p.get("result") == "L")
        pending = sum(1 for p in by_date[date_iso] if p.get("result") in ("PENDING", "—"))
        print(f"  {date_iso}: {wins}-{losses} ({pending} pending/unmatched)")

    # ── Sort & write CSV ──────────────────────────────────────────────────────
    deduped.sort(key=lambda p: (p["date"], p["away"], p["home"]))

    with open(OUT_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "away", "home", "pick_team", "conf", "pick_ml", "result", "pl", "away_score", "home_score"])
        for p in deduped:
            w.writerow([
                p["date"], p["away"], p["home"], p["pick_team"], p["conf"], p["pick_ml"],
                p.get("result", "—"), p.get("pl", 0),
                p.get("away_score", ""), p.get("home_score", ""),
            ])

    # ── Aggregate record ──────────────────────────────────────────────────────
    settled = [p for p in deduped if p.get("result") in ("W", "L")]
    wins = sum(1 for p in settled if p["result"] == "W")
    losses = sum(1 for p in settled if p["result"] == "L")
    risked = len(settled) * UNIT_SIZE
    pl = sum(p.get("pl", 0) for p in settled)
    roi = (pl / risked * 100) if risked else 0

    print(f"\n══════════════════════════════════════════")
    print(f"  RECORD: {wins}-{losses}")
    print(f"  RISKED: ${risked:,.0f}")
    print(f"  P&L:    ${pl:+,.2f}")
    print(f"  ROI:    {roi:+.1f}%")
    print(f"══════════════════════════════════════════")

    record = {
        "wins": wins, "losses": losses,
        "roi_pct": round(roi, 1),
        "risked": risked,
        "pl": round(pl, 2),
        "criteria": f"C:10 only · |odds| < {ODDS_CAP}",
        "as_of": datetime.now().strftime("%Y-%m-%d"),
        "settled_count": len(settled),
        "total_picks": len(deduped),
    }
    with open(RECORD_PATH, "w") as f:
        json.dump(record, f, indent=2)

    print(f"\n  Wrote {OUT_PATH}")
    print(f"  Wrote {RECORD_PATH}")


if __name__ == "__main__":
    main()

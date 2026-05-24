#!/usr/bin/env python3
"""
Settle yesterday's pending MLB picks against the MLB Stats API.

Reads picks/mlb.json. For each pending pick from yesterday, fetches the actual
final score and updates the pick in place (status, result, pl, settled_at).
Append-only: never touches already-settled rows.

Run before build_mlb_sim.py in the morning settle workflow.
"""
import json
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PICKS_JSON = os.path.join(REPO, "picks", "mlb.json")
UNIT_SIZE = 50

ET = timezone(timedelta(hours=-4))
YESTERDAY = (datetime.now(ET) - timedelta(days=1)).strftime("%Y-%m-%d")

TEAM_ALIAS = {"ATH":"OAK","AZ":"ARI","CWS":"CHW","TB":"TBR","WSH":"WSN","SF":"SFG","KC":"KCR","SD":"SDP"}
VOID_STATES = {"Postponed", "Cancelled", "Canceled"}

def normalize(abbr):
    return TEAM_ALIAS.get(abbr, abbr)


def fetch_schedule(date_iso):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_iso}&hydrate=linescore,team"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def find_game(games, away, home):
    a = normalize(away); h = normalize(home)
    for g in games:
        ga = normalize(g.get("teams", {}).get("away", {}).get("team", {}).get("abbreviation", ""))
        gh = normalize(g.get("teams", {}).get("home", {}).get("team", {}).get("abbreviation", ""))
        if ga == a and gh == h:
            return g
    return None


def get_final_runs(game):
    """Return (away_runs, home_runs), falling back to schedule team scores.

    MLB's schedule API can mark a game Final while omitting `linescore`.
    For completed games, `teams.away.score` / `teams.home.score` is the
    sturdier source.
    """
    ls = game.get("linescore") or {}
    away_runs = ls.get("teams", {}).get("away", {}).get("runs")
    home_runs = ls.get("teams", {}).get("home", {}).get("runs")
    if away_runs is None:
        away_runs = game.get("teams", {}).get("away", {}).get("score")
    if home_runs is None:
        home_runs = game.get("teams", {}).get("home", {}).get("score")
    return away_runs, home_runs


def main():
    if not os.path.exists(PICKS_JSON):
        print("  picks/mlb.json missing — nothing to settle.")
        return

    with open(PICKS_JSON) as f:
        picks = json.load(f)

    pending = [p for p in picks if p["status"] == "pending" and p["date"] <= YESTERDAY]
    if not pending:
        print(f"  No pending picks to settle (yesterday: {YESTERDAY})")
        return

    print(f"  Settling {len(pending)} pending pick(s) from {YESTERDAY} or earlier…")

    schedule_cache = {}
    settled_count = 0
    today_iso = datetime.now(ET).strftime("%Y-%m-%d")

    for p in pending:
        if p["date"] not in schedule_cache:
            try:
                schedule_cache[p["date"]] = fetch_schedule(p["date"])
            except Exception as e:
                print(f"    [WARN] API fetch failed for {p['date']}: {e}")
                continue
            time.sleep(0.2)

        data = schedule_cache[p["date"]]
        if not data or not data.get("dates"):
            continue
        games = [g for d in data["dates"] for g in d.get("games", [])]
        match = find_game(games, p["away"], p["home"])
        if not match:
            print(f"    [WARN] No MLB API match for {p['matchup']} on {p['date']}")
            continue

        status_info = match.get("status", {})
        status = status_info.get("abstractGameState")
        detailed_status = status_info.get("detailedState")
        away_runs, home_runs = get_final_runs(match)
        if detailed_status in VOID_STATES and away_runs is None and home_runs is None:
            p["status"] = "push"
            p["result"] = detailed_status.upper()
            p["pl"] = 0
            p["settled_at"] = today_iso
            settled_count += 1
            print(f"    {p['matchup']} {p['date']} {p['pick_text']:<10} VOID  +0 ({detailed_status})")
            continue

        if status != "Final" or away_runs is None or home_runs is None:
            print(f"    {p['matchup']} {p['date']} — not final yet (status={status}, detailed={detailed_status}), skipping")
            continue

        winner = p["away"] if away_runs > home_runs else p["home"]
        is_win = winner == p["side"]
        # picks/mlb.json stores odds as strings like "-326" or "+150"; coerce to int.
        try:
            ml = int(str(p.get("odds") or -110).replace("+", ""))
        except (ValueError, TypeError):
            ml = -110
        if is_win:
            pl = round(UNIT_SIZE * (ml / 100 if ml > 0 else 100 / abs(ml)), 2)
        else:
            pl = -UNIT_SIZE

        p["status"] = "win" if is_win else "loss"
        p["result"] = f"{away_runs}-{home_runs}"
        p["pl"] = pl
        p["settled_at"] = today_iso
        settled_count += 1
        print(f"    {p['matchup']} {p['date']} {p['pick_text']:<10} {p['status'].upper():<5} {pl:+g} ({away_runs}-{home_runs})")

    if settled_count:
        with open(PICKS_JSON, "w") as f:
            json.dump(picks, f, indent=2)
        print(f"\n  Settled {settled_count} pick(s) → {PICKS_JSON}")
    else:
        print("\n  Nothing settled this run.")


if __name__ == "__main__":
    main()

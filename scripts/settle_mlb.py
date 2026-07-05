#!/usr/bin/env python3
"""
Settle yesterday's pending MLB picks against the MLB Stats API.

Reads picks/mlb.json. For each pending pick from yesterday, fetches the actual
final score and updates the pick in place (status, result, pl, settled_at).
Append-only: never touches already-settled rows.

Run before build_mlb_sim.py in the morning settle workflow.
"""
import csv
import json
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PICKS_JSON = os.path.join(REPO, "picks", "mlb.json")
ODDS_SNAPSHOTS = os.path.join(REPO, "mlbsim", "odds_snapshots.csv")
STAKE_BY_CONF = {
    10: 100,
    9: 50,
    8: 30,
}

ET = timezone(timedelta(hours=-4))
YESTERDAY = (datetime.now(ET) - timedelta(days=1)).strftime("%Y-%m-%d")

TEAM_ALIAS = {"ATH":"OAK","AZ":"ARI","CWS":"CHW","TB":"TBR","WSH":"WSN","SF":"SFG","KC":"KCR","SD":"SDP"}
VOID_STATES = {"Postponed", "Cancelled", "Canceled"}

def stake_for_conf(conf):
    """Return $PP risk by confidence grade."""
    return STAKE_BY_CONF.get(int(conf or 0), 0)

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


def find_pick_game(games, pick):
    game_pk = pick.get("game_pk")
    if game_pk:
        try:
            game_pk = int(game_pk)
        except (TypeError, ValueError):
            game_pk = None
        if game_pk is not None:
            for g in games:
                if g.get("gamePk") == game_pk:
                    return g
    return find_game(games, pick["away"], pick["home"])


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


def load_closing_lines():
    """Last odds snapshot per game. build_mlb_sim.py appends snapshots
    chronologically, so the final row per key is the closing-line proxy.

    Returns {key: row} keyed by both (date, game_pk) and (date, away, home).
    """
    closing = {}
    if not os.path.exists(ODDS_SNAPSHOTS):
        return closing
    try:
        with open(ODDS_SNAPSHOTS, newline="") as f:
            for row in csv.DictReader(f):
                if row.get("game_pk"):
                    closing[(row["date"], str(row["game_pk"]))] = row
                closing[(row["date"], row.get("away"), row.get("home"))] = row
    except Exception as e:
        print(f"  [WARN] Could not read odds snapshots: {e}")
    return closing


def attach_closing_odds(pick, closing):
    """Set closing_odds (price for the side taken) on a pick, if captured.

    Used by report_calibration.py to compute closing line value.
    """
    row = None
    if pick.get("game_pk"):
        row = closing.get((pick["date"], str(pick["game_pk"])))
    if row is None:
        row = closing.get((pick["date"], pick.get("away"), pick.get("home")))
    if row is None:
        return
    side_ml = row.get("away_ml") if pick.get("side") == pick.get("away") else row.get("home_ml")
    if side_ml in (None, ""):
        return
    pick["closing_odds"] = side_ml
    pick["closing_ts"] = row.get("ts_utc")


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
    closing_lines = load_closing_lines()

    for p in pending:
        attach_closing_odds(p, closing_lines)
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
        match = find_pick_game(games, p)
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
        units = p.get("units") or stake_for_conf(p.get("conf")) or 50
        p["units"] = units
        # picks/mlb.json stores odds as strings like "-326" or "+150"; coerce to int.
        try:
            ml = int(str(p.get("odds") or -110).replace("+", ""))
        except (ValueError, TypeError):
            ml = -110
        if is_win:
            pl = round(units * (ml / 100 if ml > 0 else 100 / abs(ml)), 2)
        else:
            pl = -units

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

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
# Fallback only (used when a pick row is missing `units`). Flat 50u across
# published tiers as of MODEL V2 (2026-07-15): the old ladder {8:30, 9:50,
# 10:100} put the biggest stake on C10, the tier with the worst realized
# edge. Must stay in sync with scripts/mlb_model_gates.py.
STAKE_BY_CONF = {
    10: 50,
    9: 50,
    8: 50,
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
    """Last odds snapshot per game (and per book). build_mlb_sim.py appends
    snapshots chronologically — since 2026-07-15 one row PER BOOK per run,
    with the display/pick book written last in each batch — so the final row
    per key is the closing-line proxy for the pick's own book, and per-book
    closers are kept alongside for book-exact CLV.

    Returns {key: {"": last_row_any_book, book_name: last_row_for_book}}
    keyed by both (date, game_pk) and (date, away, home).
    """
    closing = {}
    if not os.path.exists(ODDS_SNAPSHOTS):
        return closing
    try:
        with open(ODDS_SNAPSHOTS, newline="") as f:
            for row in csv.DictReader(f):
                keys = [(row["date"], row.get("away"), row.get("home"))]
                if row.get("game_pk"):
                    keys.append((row["date"], str(row["game_pk"])))
                for key in keys:
                    per_book = closing.setdefault(key, {})
                    per_book[""] = row  # last row overall (pick's book)
                    if row.get("book"):
                        per_book[row["book"]] = row
    except Exception as e:
        print(f"  [WARN] Could not read odds snapshots: {e}")
    return closing


def attach_closing_odds(pick, closing):
    """Set closing_odds (price for the side taken) on a pick, if captured.

    Prefers the closing row from the book the pick was priced at
    (pick["odds_book"], stamped by build_mlb_sim.py since 2026-07-15);
    otherwise the last snapshot row for the game.
    Used by report_calibration.py to compute closing line value.
    """
    per_book = None
    if pick.get("game_pk"):
        per_book = closing.get((pick["date"], str(pick["game_pk"])))
    if per_book is None:
        per_book = closing.get((pick["date"], pick.get("away"), pick.get("home")))
    if not per_book:
        return
    row = per_book.get(pick.get("odds_book") or "") or per_book.get("")
    if row is None:
        return
    side_ml = row.get("away_ml") if pick.get("side") == pick.get("away") else row.get("home_ml")
    if side_ml in (None, ""):
        return
    pick["closing_odds"] = side_ml
    pick["closing_ts"] = row.get("ts_utc")
    if row.get("book"):
        pick["closing_book"] = row.get("book")


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

        # Picks are updated in place, so build-time fields (model_version,
        # model_mode, model_wp_raw/calibrated, odds_book, …) are preserved
        # through settlement by construction — never strip or rewrite them.
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


SHADOW_LEDGER = os.path.join(REPO, "reports", "shadow_mlb.json")

def settle_shadow_ledger():
    """Attach final scores to every unsettled shadow-ledger row. The ledger
    logs ALL evaluated games (not just published picks) so the gates can be
    calibrated against full-slate outcomes."""
    try:
        with open(SHADOW_LEDGER) as f:
            ledger = json.load(f)
    except Exception:
        return
    rows = ledger.get("rows") or {}
    todo = [r for r in rows.values() if not r.get("result")]
    if not todo:
        return
    print(f"\n  Shadow ledger: settling up to {len(todo)} row(s)…")
    cache = {}
    n = 0
    for r in sorted(todo, key=lambda x: x["date"]):
        d = r["date"]
        if d not in cache:
            try:
                cache[d] = fetch_schedule(d)
            except Exception as e:
                print(f"    [WARN] schedule fetch failed for {d}: {e}")
                cache[d] = None
        sched = cache[d]
        if not sched:
            continue
        game = None
        for day in sched.get("dates", []):
            for gg in day.get("games", []):
                if gg.get("gamePk") == r.get("game_pk"):
                    game = gg
                    break
        if not game:
            continue
        state = game.get("status", {}).get("abstractGameState", "")
        if state != "Final":
            continue
        ls = game.get("linescore", {}).get("teams", {})
        try:
            ar = int(ls.get("away", {}).get("runs"))
            hr = int(ls.get("home", {}).get("runs"))
        except (TypeError, ValueError):
            continue
        winner = r["away"] if ar > hr else r["home"]
        r["result"] = {
            "away_runs": ar, "home_runs": hr,
            "winner": winner,
            "pick_won": winner == r.get("pick_team"),
        }
        n += 1
    if n:
        with open(SHADOW_LEDGER, "w") as f:
            json.dump(ledger, f, separators=(",", ":"))
        print(f"  Shadow ledger: settled {n} row(s) → {SHADOW_LEDGER}")


HR_LEDGER = os.path.join(REPO, "reports", "hr_board_ledger.json")

def settle_hr_board_ledger():
    """Grade the HR board: did each listed bat actually homer that day?"""
    try:
        with open(HR_LEDGER) as f:
            ledger = json.load(f)
    except Exception:
        return
    rows = ledger.get("rows") or {}
    todo = [r for r in rows.values() if not r.get("result")]
    if not todo:
        return
    print(f"\n  HR board ledger: grading up to {len(todo)} row(s)…")
    box_cache = {}
    n = 0
    for r in sorted(todo, key=lambda x: x["date"]):
        pk = r.get("game_pk")
        if not pk:
            continue
        if pk not in box_cache:
            try:
                url = f"https://statsapi.mlb.com/api/v1/game/{pk}/boxscore"
                with urllib.request.urlopen(url, timeout=20) as resp:
                    box_cache[pk] = json.loads(resp.read())
            except Exception:
                box_cache[pk] = None
        box = box_cache[pk]
        if not box:
            continue
        found = None
        for side in ("away", "home"):
            pl = (box.get("teams", {}).get(side, {}).get("players", {})
                  .get(f"ID{r['batter']}"))
            if pl:
                bat = (pl.get("stats", {}) or {}).get("batting", {}) or {}
                # allStarStatus etc aside — batting stats only exist post-game
                if bat:
                    found = {"hr": int(bat.get("homeRuns") or 0),
                             "pa": int(bat.get("plateAppearances") or 0),
                             "homered": int(bat.get("homeRuns") or 0) > 0}
                break
        if found and found["pa"] > 0:
            r["result"] = found
            n += 1
    if n:
        with open(HR_LEDGER, "w") as f:
            json.dump(ledger, f, separators=(",", ":"))
        print(f"  HR board ledger: graded {n} row(s)")


if __name__ == "__main__":
    main()
    settle_shadow_ledger()
    settle_hr_board_ledger()

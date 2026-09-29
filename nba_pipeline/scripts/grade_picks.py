#!/usr/bin/env python3
"""
grade_picks.py — CSV-based pick tracker with auto-grading.

Reads picks from data/picks.csv, fetches final scores (ESPN first, nba_sim.db
`games` table when ESPN is unreachable), grades pending picks W/L/P and
updates the CSV in place. A pick whose capture time is missing or not before
tip-off is voided (result "V", with a reason) instead of graded. Rows are
never deleted.

Usage:
  python scripts/grade_picks.py                          # Grade pending picks
  python scripts/grade_picks.py --add "2026-02-26,OKC @ LAL,LAL +3.5,spread,50"
  python scripts/grade_picks.py --summary                # Just print record
  python scripts/grade_picks.py --check-stale [--days 3] # Guardrail: exit 1 if
                                                         # any pick is still pending
                                                         # more than N days after its date
"""

import csv
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

# ── Paths ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
PICKS_CSV = os.path.join(PROJECT_ROOT, "data", "picks.csv")
RESULTS_JSON = os.path.join(PROJECT_ROOT, "data", "settlement_results.json")
LINE_SNAPSHOTS = os.path.join(PROJECT_ROOT, "data", "line_snapshots.csv")

sys.path.insert(0, PROJECT_ROOT)
from config import STARTING_BANKROLL
from collectors.games_espn import fetch_scores_for_grading, score_key
from utils.ledger import (
    CSV_FIELDS, VOID, SETTLED, read_rows, write_rows, capture_check,
    compute_profit, row_odds,
)

STALE_PENDING_DAYS = 3


# ── CSV I/O ──────────────────────────────────────────────────────────

def read_picks():
    """Read all picks from CSV. Returns list of dicts."""
    if not os.path.exists(PICKS_CSV):
        print(f"No picks file at {PICKS_CSV}")
        return []
    return read_rows(PICKS_CSV)


def write_picks(picks):
    """Write picks back to CSV."""
    write_rows(PICKS_CSV, picks)


def add_pick(raw_str):
    """Append a pick from CLI string: 'date,matchup,side,type,risk'.

    The capture time is now; grading voids it if that is not before tip.
    """
    parts = [p.strip() for p in raw_str.split(",")]
    if len(parts) < 5:
        print("Format: date,matchup,side,type,risk")
        print('Example: "2026-02-26,OKC @ LAL,LAL +3.5,spread,50"')
        sys.exit(1)

    new_pick = {k: "" for k in CSV_FIELDS}
    new_pick.update({
        "date": parts[0],
        "matchup": parts[1],
        "side": parts[2],
        "type": parts[3],
        "risk": parts[4],
        "captured_at": datetime.now(timezone.utc).isoformat(),
    })

    picks = read_picks()
    picks.append(new_pick)
    write_picks(picks)
    print(f"Added: {new_pick['date']} | {new_pick['matchup']} | {new_pick['side']} | risk {new_pick['risk']}")


# ── Grading Logic ────────────────────────────────────────────────────

def parse_side(side_str):
    """Parse 'CLE -16.0' or 'BOS +4.5' into (team_abbr, line_float) or None."""
    m = re.match(r"([A-Z]{2,3})\s+([+-]?[\d.]+)", side_str.strip())
    if not m:
        return None
    return m.group(1), float(m.group(2))


def _game_for(pick, scores):
    """Date-keyed lookup only: a matchup-only fallback grades rematches wrong
    (it graded 03-19 DET @ WAS against 03-17 and 03-27 MIA @ CLE against 03-25)."""
    return scores.get(score_key(pick.get("date"), pick.get("matchup")))


def grade_spread(matchup, side_str, scores, pick_date=None):
    """Grade a spread pick. Returns 'W' | 'L' | 'P' or None."""
    game = scores.get(score_key(pick_date, matchup)) if pick_date else None
    if game is None:
        return None
    parsed = parse_side(side_str)
    if parsed is None:
        return None

    team, line = parsed
    actual_margin = game["home_score"] - game["away_score"]
    if team == game["home_abbr"]:
        cover_margin = actual_margin + line
    elif team == game["away_abbr"]:
        cover_margin = -actual_margin + line
    else:
        return None

    if cover_margin > 0:
        return "W"
    if cover_margin == 0:
        return "P"
    return "L"


def grade_ml(matchup, side_str, scores, pick_date=None):
    """Grade a moneyline pick. Side is like 'GSW ML'."""
    game = scores.get(score_key(pick_date, matchup)) if pick_date else None
    if game is None:
        return None
    m = re.match(r"([A-Z]{2,3})\s+ML", side_str.strip())
    if not m:
        return None

    team = m.group(1)
    hs, as_ = game["home_score"], game["away_score"]
    if team == game["home_abbr"]:
        return "W" if hs > as_ else ("P" if hs == as_ else "L")
    if team == game["away_abbr"]:
        return "W" if as_ > hs else ("P" if hs == as_ else "L")
    return None


# ── Closing lines (for CLV) ──────────────────────────────────────────

def load_closing_snapshots():
    """Last line snapshot per (date, matchup). generate_frontend.py appends
    snapshots chronologically, so the final row is the closing-line proxy.
    """
    closing = {}
    if not os.path.exists(LINE_SNAPSHOTS):
        return closing
    with open(LINE_SNAPSHOTS, newline="") as f:
        for row in csv.DictReader(f):
            closing[(row["date"], row["matchup"])] = row
    return closing


def attach_closing_line(pick, closing):
    """Set closing_line / closing_odds on a pick from the last pre-game
    snapshot. Spread lines are stored from the picked side's perspective
    so CLV is simply pick line minus closing line.
    """
    row = closing.get((pick.get("date"), pick.get("matchup")))
    if not row:
        return
    pick_type = pick.get("type", "spread")
    away = (pick.get("matchup") or "").split(" @ ")[0].strip()
    if pick_type == "spread" and row.get("book_spread_home") not in (None, ""):
        parsed = parse_side(pick.get("side", ""))
        if parsed is None:
            return
        team, _line = parsed
        home_spread = float(row["book_spread_home"])
        pick["closing_line"] = str(-home_spread if team == away else home_spread)
    elif pick_type == "ml":
        m = re.match(r"([A-Z]{2,3})\s+ML", (pick.get("side") or "").strip())
        if not m:
            return
        ml = row.get("away_ml") if m.group(1) == away else row.get("home_ml")
        if ml not in (None, ""):
            pick["closing_odds"] = str(ml)
    elif pick_type == "total" and row.get("book_total") not in (None, ""):
        pick["closing_line"] = str(row["book_total"])


# ── Main ─────────────────────────────────────────────────────────────

def grade_all():
    """Grade all pending picks from CSV."""
    picks = read_picks()
    if not picks:
        print("No picks in CSV")
        return

    pending = [p for p in picks if not p["result"]]
    if not pending:
        print("All picks already graded")
        print_summary(picks)
        return

    print(f"\n{len(pending)} pending picks to grade\n")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dates = sorted({p["date"] for p in pending if p["date"] <= today})
    print(f"Fetching scores for {len(dates)} slate date(s): {', '.join(dates)}")
    scores = fetch_scores_for_grading(dates=dates)
    closing = load_closing_snapshots()

    graded = 0
    for pick in picks:
        if pick["result"]:
            continue
        attach_closing_line(pick, closing)

        matchup = pick["matchup"]
        side = pick["side"]
        pick_type = pick.get("type") or "spread"
        risk = float(pick.get("risk") or 0)

        if pick_type == "spread":
            result = grade_spread(matchup, side, scores, pick_date=pick.get("date"))
        elif pick_type == "ml":
            result = grade_ml(matchup, side, scores, pick_date=pick.get("date"))
        else:
            result = None  # TODO: total/prop grading

        if result is None:
            print(f"  PENDING: {pick['date']} | {matchup} | {side}")
            continue

        game = _game_for(pick, scores)
        pick["home_score"] = str(game["home_score"])
        pick["away_score"] = str(game["away_score"])
        if game.get("tip_utc") and not pick.get("tip_at"):
            pick["tip_at"] = game["tip_utc"]

        void_reason = capture_check(pick, game.get("tip_utc"))
        if void_reason:
            would = compute_profit(result, risk, odds=row_odds(pick))
            pick["result"] = VOID
            pick["profit"] = "0"
            pick["void_reason"] = f"{void_reason}; would have graded {result} {would:+.2f}"
            graded += 1
            print(f"  V VOID: {matchup} | {side} | {pick['void_reason']}")
            continue

        profit = compute_profit(result, risk, odds=row_odds(pick))
        pick["result"] = result
        pick["profit"] = str(profit)
        graded += 1
        marker = {"W": "+", "L": "-", "P": "="}[result]
        print(f"  {marker} {result}: {matchup} | {side} | {profit:+.2f} $PP "
              f"[{game['away_abbr']} {game['away_score']} @ {game['home_abbr']} {game['home_score']}, {game.get('source')}]")

    write_picks(picks)
    print(f"\nGraded {graded} picks")
    print_summary(picks)


def check_stale(days=STALE_PENDING_DAYS):
    """Guardrail: exit 1 if any pick is still pending > `days` after its date."""
    picks = read_picks()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    stale = [p for p in picks if not p["result"] and p["date"] < cutoff]
    if stale:
        for p in stale:
            print(f"::error::NBA pick still pending {days}+ days after its date: "
                  f"{p['date']} {p['matchup']} {p['side']}")
        sys.exit(1)
    print(f"Stale-pending guardrail OK: no pick pending more than {days} days")


def print_summary(picks):
    """Print running record and bankroll; write settlement_results.json."""
    record = {"W": 0, "L": 0, "P": 0}
    total_profit = 0.0
    pending = 0
    voided = 0

    for p in picks:
        r = p.get("result", "").strip()
        if r in SETTLED:
            record[r] += 1
            total_profit += float(p.get("profit", 0) or 0)
        elif r == VOID:
            voided += 1
        else:
            pending += 1

    bankroll = STARTING_BANKROLL + total_profit

    print(f"\n{'='*50}")
    print(f"  RECORD:   {record['W']}-{record['L']}-{record['P']}")
    print(f"  P/L:      {total_profit:+.2f} $PP")
    print(f"  BANKROLL: {STARTING_BANKROLL:.0f} -> {bankroll:.0f} $PP")
    if pending:
        print(f"  PENDING:  {pending} picks")
    if voided:
        print(f"  VOID:     {voided} picks (kept, not counted)")
    print(f"{'='*50}")

    results_list = []
    for p in picks:
        r = p.get("result", "").strip()
        if r:
            entry = {
                "date": p["date"],
                "matchup": p["matchup"],
                "side": p["side"],
                "type": p.get("type", "spread"),
                "risk": float(p.get("risk", 0) or 0),
                "result": r,
                "profit": float(p.get("profit", 0) or 0),
            }
            if p.get("home_score"):
                entry["home_score"] = int(p["home_score"])
            if p.get("away_score"):
                entry["away_score"] = int(p["away_score"])
            if r == VOID:
                entry["void_reason"] = p.get("void_reason", "")
            results_list.append(entry)

    settlement = {
        "graded_at": datetime.now(timezone.utc).isoformat(),
        "picks": results_list,
        "pending_count": pending,
        "void_count": voided,
        "record": record,
        "total_profit": round(total_profit, 2),
        "starting_bankroll": STARTING_BANKROLL,
        "new_bankroll": round(bankroll, 2),
        "status": "SETTLED" if pending == 0 else "PARTIAL",
    }

    os.makedirs(os.path.dirname(RESULTS_JSON), exist_ok=True)
    with open(RESULTS_JSON, "w") as f:
        json.dump(settlement, f, indent=2)


def main():
    print("=== NBA SIM Pick Tracker ===\n")

    if len(sys.argv) > 1:
        if sys.argv[1] == "--add" and len(sys.argv) > 2:
            add_pick(sys.argv[2])
            return
        if sys.argv[1] == "--summary":
            picks = read_picks()
            if picks:
                print_summary(picks)
            return
        if sys.argv[1] == "--check-stale":
            days = STALE_PENDING_DAYS
            if "--days" in sys.argv:
                days = int(sys.argv[sys.argv.index("--days") + 1])
            check_stale(days)
            return
        print(f"Unknown flag: {sys.argv[1]}")
        print("Usage:")
        print('  python scripts/grade_picks.py                  # Grade pending')
        print('  python scripts/grade_picks.py --add "..."      # Add a pick')
        print('  python scripts/grade_picks.py --summary        # Print record')
        print('  python scripts/grade_picks.py --check-stale    # Pending >3 days guardrail')
        sys.exit(1)

    grade_all()


if __name__ == "__main__":
    main()

"""picks.csv ledger: one schema, one set of integrity rules.

Rules (brand promise: nothing is deleted, nothing is restated after the fact):
  * A row is never removed. A pick that must not count is kept with
    result "V" (void) and a `void_reason`; its real outcome stays in the
    scores and the reason text.
  * `risk` is the stake at capture. It is written once by capture_picks.py /
    inject_pick.py and is never recomputed from confidence later.
  * A pick counts only if `captured_at` is before tip-off. Grading voids any
    pick whose capture time is missing or not before tip.
"""

import csv
import os
from datetime import datetime, timezone

CSV_FIELDS = [
    "date", "matchup", "side", "type", "risk", "result", "profit", "odds",
    "home_score", "away_score", "closing_line", "closing_odds",
    "captured_at", "tip_at", "void_reason",
]

VOID = "V"
SETTLED = ("W", "L", "P")


def read_rows(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        rows = []
        for row in csv.DictReader(f):
            rows.append({k: (row.get(k) or "").strip() for k in CSV_FIELDS})
        return rows


def write_rows(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") if r.get(k) is not None else "" for k in CSV_FIELDS})


def append_rows(path: str, rows: list[dict]) -> None:
    existing = read_rows(path)
    write_rows(path, existing + rows)


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def latest_safe_tip(date_iso: str) -> datetime:
    """Conservative tip-off bound when the real tip time is unknown: noon ET
    (16:00 UTC) on the slate date, earlier than any regular NBA tip."""
    return datetime.strptime(date_iso, "%Y-%m-%d").replace(hour=16, tzinfo=timezone.utc)


def capture_check(row: dict, tip_utc: str | None = None) -> str | None:
    """None if the pick was captured before tip-off, else the void reason."""
    cap = parse_ts(row.get("captured_at"))
    if cap is None:
        return "no pregame capture record (captured_at missing)"
    tip = parse_ts(tip_utc) or parse_ts(row.get("tip_at"))
    if tip is None:
        tip = latest_safe_tip(row["date"])
        if cap >= tip:
            return f"captured_at {row['captured_at']} not before {tip.isoformat()} (tip time unknown; noon-ET bound)"
        return None
    if cap >= tip:
        return f"captured_at {row['captured_at']} not before tip {tip.isoformat()}"
    return None


def compute_profit(result: str, risk: float, odds: int | None = -110) -> float:
    """Profit at American odds (spreads default to -110)."""
    if result == "W":
        o = odds if odds not in (None, 0) else -110
        return round(risk * (o / 100), 2) if o > 0 else round(risk * (100 / abs(o)), 2)
    if result == "L":
        return round(-risk, 2)
    return 0.0


def row_odds(row: dict) -> int:
    raw = (row.get("odds") or "").replace("+", "").strip()
    if row.get("type", "spread") == "ml" and raw:
        try:
            return int(float(raw))
        except ValueError:
            pass
    return -110

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


# Seal mode (scripts/picks_store.py): a pending row whose game has not tipped
# is written with side "SEALED", odds blank and the full row encrypted in a
# trailing `sealed_blob` column (present only while some row is sealed, so the
# file is byte-identical to before when nothing is). Readers get plaintext back
# when PICKS_SEAL_KEY is set (marked `_sealed`); without it the sealed row is
# passed through untouched.
BLOB_COL = "sealed_blob"
SEALED_KEEP = (
    "date", "matchup", "type", "risk", "result", "profit", "home_score", "away_score",
    "closing_line", "closing_odds", "captured_at", "tip_at", "void_reason",
)


def _open_row(row: dict) -> dict:
    if not row.get(BLOB_COL):
        return row
    from utils.seal import store
    return store.open_csv_row(row, CSV_FIELDS)


def rows_from_reader(reader) -> list[dict]:
    rows = []
    for row in reader:
        r = {k: (row.get(k) or "").strip() for k in CSV_FIELDS}
        if (row.get(BLOB_COL) or "").strip():
            r[BLOB_COL] = row[BLOB_COL].strip()
            r = _open_row(r)
        rows.append(r)
    return rows


def read_rows(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return rows_from_reader(csv.DictReader(f))


def _seal_rows(rows: list[dict]) -> list[dict]:
    """Seal pending pre-tip rows when seal mode is on; pass sealed rows we
    could not open (no key) through untouched; plaintext everything else."""
    if not any(r.get(BLOB_COL) or r.get("_sealed") for r in rows):
        from utils.seal import store
        if not store.seal_mode():
            return rows
    from utils.seal import store
    on = store.seal_mode()
    out = []
    for r in rows:
        if r.get(BLOB_COL) and not r.get("_sealed"):
            out.append(r)                      # still-sealed row we could not open
            continue
        plain = {k: r.get(k) for k in CSV_FIELDS}
        if on and not (plain.get("result") or "") and store.before_start(plain):
            out.append(store.seal_csv_row(plain, CSV_FIELDS, SEALED_KEEP, {"side": store.SEALED_SIDE}))
        else:
            out.append(plain)
    return out


def write_rows(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = _seal_rows(rows)
    fields = CSV_FIELDS + ([BLOB_COL] if any(r.get(BLOB_COL) for r in rows) else [])
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") if r.get(k) is not None else "" for k in fields})


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


# ── pick_log.json / daily_picks.json under seal mode ─────────────────────────
# Public fields of a sealed pick_log entry / daily_picks game. Everything that
# reveals the side (side, line, direction, raw confidence, sim numbers,
# conf_label "TAKE X", pick_text, ou_*) lives only in the encrypted blob.
LOG_KEEP = (
    "slate_date", "matchup", "pick_type", "conf_1_10", "risk", "captured_at", "tip_at",
    "season_type", "generated_at", "book_spread", "book_total",
)
DAILY_KEEP = (
    "season_type", "tip_at", "matchup", "home", "away", "book_spread", "book_total",
    "home_ml", "away_ml",
)


def open_entries(entries: list) -> list:
    """Plaintext entries (sealed ones opened when PICKS_SEAL_KEY is set)."""
    if not any(isinstance(e, dict) and e.get("sealed") is True for e in entries or []):
        return entries
    from utils.seal import store
    return store.open_records(entries)


def seal_entries(entries: list, keep=LOG_KEEP, should_seal=None) -> list:
    """Seal entries whose game has not tipped (seal mode on). `should_seal`
    narrows which entries are picks (default: all). Identity when seal mode
    is off (already-sealed entries stay as they are until they tip)."""
    from utils.seal import store
    if not store.seal_mode():
        return entries
    out = []
    for e in entries:
        if not isinstance(e, dict) or store.is_raw_sealed(e):
            out.append(e)
        elif (should_seal is None or should_seal(e)) and store.before_start(e):
            out.append(store.seal_record(e, keep, kind="nba_entry"))
        else:
            out.append(e)
    return out

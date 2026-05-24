#!/usr/bin/env python3
"""
sync_to_picks_json.py — Bridge nba_pipeline/data → MORELLOSIMS/picks/nba.json.

Reads:
  - data/picks.csv          (settled history: date, matchup, side, type, risk,
                              result, profit, odds, home_score, away_score)
  - data/pick_log.json      (rich metadata per pick: confidence, edge, sim_*)
  - data/daily_picks.json   (today's pending slate)

Writes:
  - ../picks/nba.json       (canonical picks-contract format consumed by
                              scripts/render_dispatch.py)

Idempotent: rebuilds picks/nba.json from scratch each run, so re-running
never doubles entries. Pre-tracking-era totals live in picks/baselines.json
and are added to the auto-tracked picks at render time.
"""
import csv
import json
import os
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
NBA_PIPELINE = THIS_DIR.parent
MORELLOSIMS = NBA_PIPELINE.parent
DATA = NBA_PIPELINE / "data"
PICKS_OUT = MORELLOSIMS / "picks" / "nba.json"

PICKS_CSV = DATA / "picks.csv"
PICK_LOG = DATA / "pick_log.json"
DAILY = DATA / "daily_picks.json"

UNIT_SIZE_DEFAULT = 50  # used when CSV row has no `risk` value
MIN_TRACKED_CONF = 8


def parse_matchup(s: str) -> tuple[str, str]:
    """'BKN @ CLE' -> ('BKN', 'CLE'). Returns ('','') on parse failure."""
    if not s:
        return "", ""
    parts = s.split(" @ ")
    if len(parts) != 2:
        return "", ""
    return parts[0].strip(), parts[1].strip()


def parse_side(s: str) -> tuple[str, float | None, str]:
    """'CLE -8.5' -> ('CLE', -8.5, 'CLE -8.5')
       'CLE ML'   -> ('CLE', None, 'CLE ML')
    """
    s = (s or "").strip()
    if not s:
        return "", None, s
    parts = s.split()
    side_team = parts[0]
    line: float | None = None
    if len(parts) > 1 and parts[1] != "ML":
        try:
            line = float(parts[1])
        except ValueError:
            line = None
    return side_team, line, s


def normalize_slate_date(raw: str) -> str:
    """pick_log entries can have slate_date='MAR 2' or '2026-03-02'.
    Always return YYYY-MM-DD or '' if unparseable."""
    if not raw:
        return ""
    if "-" in raw and len(raw) >= 10:
        return raw[:10]
    for fmt in ("%b %d", "%B %d"):
        try:
            year = datetime.now().year
            dt = datetime.strptime(f"{raw} {year}", f"{fmt} %Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def make_id(date: str, away: str, home: str, bet_type: str, side: str) -> str:
    """Stable unique ID. Includes side so spread + ML on same matchup don't collide."""
    return f"{date}-nba-{away}-{home}-{bet_type}-{side}".lower().replace(" ", "")


def status_from_result(r: str) -> str:
    return {"W": "win", "L": "loss", "P": "push"}.get(r, "pending")


def build_pick_log_index(pick_log: list) -> dict:
    """Index pick_log by (date, matchup, side) -> rich metadata.
    Allows looking up confidence/edge/sim_spread for picks listed in the CSV."""
    idx = {}
    for p in pick_log:
        date = normalize_slate_date(p.get("slate_date", ""))
        key = (date, p.get("matchup", "").strip(), p.get("side", "").strip())
        idx[key] = p
    return idx


def csv_row_to_pick(row: dict, meta_idx: dict) -> dict | None:
    """Translate a picks.csv row into the contract format."""
    date = (row.get("date") or "").strip()
    matchup = (row.get("matchup") or "").strip()
    side_raw = (row.get("side") or "").strip()
    bet_type = (row.get("type") or "spread").strip()

    if not (date and matchup and side_raw):
        return None

    away, home = parse_matchup(matchup)
    side_team, line, pick_text = parse_side(side_raw)

    try:
        risk = int(float(row.get("risk") or 0)) or UNIT_SIZE_DEFAULT
    except (ValueError, TypeError):
        risk = UNIT_SIZE_DEFAULT

    result_letter = (row.get("result") or "").strip()
    status = status_from_result(result_letter)
    if status == "pending":
        result = None
        pl = None
    else:
        try:
            pl = float(row.get("profit") or 0)
        except (ValueError, TypeError):
            pl = 0.0
        hs = (row.get("home_score") or "").strip()
        as_ = (row.get("away_score") or "").strip()
        result = f"{hs}-{as_}" if hs and as_ else None

    odds_raw = (row.get("odds") or "").strip()
    odds: int | None
    if odds_raw:
        try:
            odds = int(odds_raw.replace("+", ""))
        except ValueError:
            odds = -110
    else:
        odds = -110 if bet_type in ("spread", "total") else None

    # Rich metadata from pick_log
    meta = meta_idx.get((date, matchup, side_raw), {})
    conf = int(meta.get("conf_1_10") or 0)

    # If pick_log has no entry (manual injection, direct CSV append, or
    # legacy rows with no metadata), derive a sensible conf floor from the
    # risk amount. Mirrors capture_picks.py's risk_amount() ladder:
    #   risk 50 -> C:8+   (premium plays)
    #   risk 30 -> C:5-7  (mid-tier, not tracked)
    #   risk 20 -> C:1-4  (light, not tracked)
    if conf == 0 and risk:
        if risk >= 50: conf = 8
        elif risk >= 30: conf = 5
        elif risk > 0:   conf = 1

    if conf < MIN_TRACKED_CONF:
        return None

    sim_spread = meta.get("sim_spread")
    sim_edge = meta.get("spread_edge")
    sim_projection: str | None = None
    if sim_spread is not None:
        sign = "+" if sim_spread > 0 else ""
        sim_projection = f"{side_team} {sign}{sim_spread}"

    return {
        "id": make_id(date, away, home, bet_type, side_team),
        "sport": "nba",
        "date": date,
        "away": away,
        "home": home,
        "matchup": matchup,
        "bet_type": bet_type,
        "side": side_team,
        "line": line,
        "odds": odds,
        "pick_text": pick_text,
        "conf": conf,
        "units": risk,
        "sim_projection": sim_projection,
        "sim_edge": float(sim_edge) if sim_edge is not None else 0.0,
        "status": status,
        "result": result,
        "pl": pl,
    }


def load_csv(path: Path) -> list:
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def load_json(path: Path):
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def main():
    csv_rows = load_csv(PICKS_CSV)
    pick_log = load_json(PICK_LOG) or []
    meta_idx = build_pick_log_index(pick_log)

    # Respect picks/baselines.json's tracking_started cutoff. Anything before
    # that date is already counted in the baseline; including it here would
    # double-count when render_dispatch adds picks/nba.json on top of baseline.
    cutoff = "2026-05-01"
    baselines_path = MORELLOSIMS / "picks" / "baselines.json"
    if baselines_path.exists():
        try:
            cutoff = json.loads(baselines_path.read_text()).get("tracking_started", cutoff)
        except (json.JSONDecodeError, OSError):
            pass

    contract: list[dict] = []
    seen: set[str] = set()

    for row in csv_rows:
        cp = csv_row_to_pick(row, meta_idx)
        if not cp:
            continue
        if cp["date"] < cutoff:
            continue  # already in baseline — skip to prevent double-counting
        if cp["id"] in seen:
            continue
        contract.append(cp)
        seen.add(cp["id"])

    # Sort newest first (matches picks/SCHEMA.md contract)
    contract.sort(key=lambda p: p["date"], reverse=True)

    PICKS_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(PICKS_OUT, "w") as f:
        json.dump(contract, f, indent=2)

    settled = sum(1 for p in contract if p["status"] in ("win", "loss", "push"))
    pending = sum(1 for p in contract if p["status"] == "pending")
    wins = sum(1 for p in contract if p["status"] == "win")
    losses = sum(1 for p in contract if p["status"] == "loss")
    pl = sum((p.get("pl") or 0) for p in contract if p["status"] in ("win", "loss"))

    print(f"[sync] Wrote {PICKS_OUT}")
    print(f"  Total: {len(contract)} picks ({settled} settled, {pending} pending)")
    print(f"  Settled record: {wins}-{losses}, P/L {pl:+.2f}")


if __name__ == "__main__":
    main()

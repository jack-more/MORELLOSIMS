#!/usr/bin/env python3
"""NFL public picks — OFF until the owner turns it on. Two locks:

  1. ops/config/monetization.json "nfl_publish": true   (owner flag; default false)
  2. nfl_pipeline/tiers.json has at least one tier       (written by the backtest
     only when an edge bucket clears break-even out of sample — today: none)

With either lock closed this writes nothing, sends nothing and exits 0.

When both are open, every OPEN shadow row whose latest pre-kickoff capture
meets a tier becomes a pick in picks/nfl.json through scripts/picks_store.py
(so seal mode seals it until kickoff, exactly like MLB/NBA). Picks are
append-only: an existing id is never re-staked or rewritten (stake frozen at
capture); settlement fills status/result/pl only.

  python3 nfl_pipeline/publish.py            # publish (if allowed) + settle published picks
"""

from __future__ import annotations

import json
import os
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PICKS_JSON, REPO, SHADOW_LEDGER, TIERS_JSON  # noqa: E402
from shadow import load_ledger, pick_id, save_ledger  # noqa: E402

sys.path.insert(0, os.path.join(REPO, "scripts"))
import picks_store  # noqa: E402

ET = ZoneInfo("America/New_York")
DEFAULT_UNITS = {8: 50, 9: 75, 10: 100}   # $PP stake per tier, frozen into the pick at capture


def publish_enabled() -> bool:
    return picks_store.config().get("nfl_publish") is True


def load_tiers(path=TIERS_JSON) -> list:
    try:
        with open(path) as f:
            return list(json.load(f).get("tiers") or [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def tier_for(edge, tiers):
    best = None
    for t in sorted(tiers, key=lambda t: t["min_edge"]):
        if abs(edge) >= t["min_edge"]:
            best = t
    return best


def published_pending_ids(path=PICKS_JSON) -> set:
    """Public ids of published picks still pending. NFL ids name both teams,
    never the side, so they are readable even while sealed (no key needed);
    their shadow rows must be sealed under seal mode."""
    if not os.path.exists(path):
        return set()
    return {p.get("id") for p in picks_store._read_raw(path) if p.get("status") == "pending" and p.get("id")}


def build_pick(row, tier, units):
    c = row["last"]
    ko = picks_store.parse_ts(row["kickoff_utc"]).astimezone(ET)
    line = c["side_line"]
    return {
        "id": pick_id(row), "sport": "nfl", "date": ko.strftime("%Y-%m-%d"),
        "away": row["away"], "home": row["home"], "matchup": f"{row['away']} @ {row['home']}",
        "bet_type": "spread", "side": c["side"], "line": line, "odds": -110,
        "pick_text": f"{c['side']} {line:+.1f}" if line else f"{c['side']} PK",
        "conf": tier["conf"], "units": units,
        "sim_projection": f"{c['side']} {c['side_margin']:+.1f}", "sim_edge": round(abs(c["edge"]), 2),
        "game_id": row["game_id"], "game_time": ko.strftime("%-I:%M %p ET"),
        "unlocks_at": row["kickoff_utc"],
        "published_at": c["captured_at"], "captured_at": c["captured_at"],
        "closing_line": None, "status": "pending", "result": None, "pl": None,
    }


def settle_picks(picks, ledger):
    rows = ledger.get("rows", {})
    for p in picks:
        if p.get("status") != "pending" or picks_store.is_raw_sealed(p):
            continue
        r = rows.get(p.get("game_id")) or {}
        res = r.get("result")
        if r.get("status") != "final" or not res:
            continue
        home_side = p["side"] == p["home"]
        line_home_fav = -p["line"] if home_side else p["line"]
        d = res["home_margin"] - line_home_fav
        status = "push" if d == 0 else ("win" if (d > 0) == home_side else "loss")
        p["status"] = status
        p["result"] = f"{res['away_score']}-{res['home_score']}"
        p["pl"] = picks_store_profit(status, p["units"])
        p["closing_line"] = res.get("closing_line_home_fav")
        p["settled_at"] = res.get("settled_at")
    return picks


def picks_store_profit(status, units):
    if status == "win":
        return round(units * 100 / 110, 2)
    if status == "loss":
        return round(-units, 2)
    return 0.0


def run(ledger_path=SHADOW_LEDGER, picks_path=PICKS_JSON, tiers_path=TIERS_JSON, now=None):
    if not publish_enabled():
        print("nfl publish: OFF (ops/config/monetization.json nfl_publish is not true) — nothing written")
        return []
    tiers = load_tiers(tiers_path)
    if not tiers:
        print("nfl publish: flag is on but nfl_pipeline/tiers.json has no tier (the backtest found no "
              "bucket that clears break-even out of sample) — nothing written")
        return []
    now = now or picks_store.now_utc()
    ledger = load_ledger(ledger_path)
    picks = picks_store.load_picks(picks_path) if os.path.exists(picks_path) else []
    have = {p.get("id") for p in picks} | {p.get("sealed_id") for p in picks}
    units_cfg = {int(k): v for k, v in (picks_store.config().get("nfl_units_by_conf") or DEFAULT_UNITS).items()}
    new = []
    for gid, row in ledger["rows"].items():
        c = row.get("last") or {}
        if row.get("status") != "open" or c.get("edge") is None:
            continue
        if now >= picks_store.parse_ts(row["kickoff_utc"]):
            continue
        t = tier_for(c["edge"], tiers)
        if not t or pick_id(row) in have:
            continue
        pick = build_pick(row, t, units_cfg.get(t["conf"], DEFAULT_UNITS.get(t["conf"], 50)))
        picks.append(pick)
        new.append(pick)
        row["published"] = True
        row["pick_id"] = pick["id"]
    picks = settle_picks(picks, ledger)
    os.makedirs(os.path.dirname(picks_path), exist_ok=True)
    picks_store.save_picks(picks_path, picks, now=now)
    # shadow rows of pending published picks are sealed too (seal mode)
    save_ledger(ledger, ledger_path, published_pending=published_pending_ids(picks_path))
    print(f"nfl publish: {len(new)} new pick(s), {len(picks)} total in {os.path.relpath(picks_path, REPO)}")
    return new


if __name__ == "__main__":
    run()

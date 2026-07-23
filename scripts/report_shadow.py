#!/usr/bin/env python3
"""
report_shadow.py — the shadow ledger's learning loop.

Reads reports/shadow_mlb.json (every evaluated game, every gate verdict,
settled results) and answers the questions the public record can't:

  1. Calibration: does the calibrated model probability match reality
     across the FULL slate, not just published picks?
  2. Gate opportunity cost: what did each gate's rejections actually return
     at the posted price (flat 50u)?
  3. Signal shootout: does run-diff or price-edge better separate winners?

Usage: python3 scripts/report_shadow.py
"""

import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(REPO, "reports", "shadow_mlb.json")
STAKE = 50.0


def profit(odds, won):
    if not won:
        return -STAKE
    if odds > 0:
        return STAKE * odds / 100.0
    return STAKE * 100.0 / abs(odds)


def line(rows, label):
    done = [r for r in rows if r.get("result") and r.get("odds")]
    if not done:
        print(f"  {label:42s} —")
        return
    w = sum(1 for r in done if r["result"]["pick_won"])
    l = len(done) - w
    pl = sum(profit(r["odds"], r["result"]["pick_won"]) for r in done)
    roi = 100 * pl / (STAKE * len(done))
    print(f"  {label:42s} {w:>3}-{l:<3} net {pl:+9.1f}u  ROI {roi:+6.1f}%  (n={len(done)})")


def main():
    try:
        with open(LEDGER) as f:
            rows = list(json.load(f)["rows"].values())
    except Exception:
        print("No shadow ledger yet.")
        return

    settled = [r for r in rows if r.get("result")]
    dates = sorted({r["date"] for r in rows})
    print(f"SHADOW LEDGER — {len(rows)} rows, {len(settled)} settled, "
          f"{dates[0] if dates else '—'} → {dates[-1] if dates else '—'}\n")

    # 1. Calibration buckets (calibrated model prob vs actual win rate)
    print("CALIBRATION (model prob → actual, full slate):")
    buckets = [(0.50, 0.55), (0.55, 0.60), (0.60, 0.65), (0.65, 0.75), (0.75, 1.01)]
    for lo, hi in buckets:
        b = [r for r in settled if r.get("model_prob") and lo <= r["model_prob"] < hi]
        if not b:
            continue
        act = sum(1 for r in b if r["result"]["pick_won"]) / len(b)
        avg = sum(r["model_prob"] for r in b) / len(b)
        print(f"  {lo:.2f}–{hi:.2f}: predicted {avg:.3f}  actual {act:.3f}  (n={len(b)})")

    # 2. Gate opportunity cost
    print("\nGATE OPPORTUNITY COST (what each slice returned at posted price):")
    line([r for r in settled if r.get("published")], "PUBLISHED (all gates passed)")
    line([r for r in settled if not r["gates"]["conf_c8plus"] and int(r.get("conf") or 0) == 7],
         "rejected: C7 (run-diff tier)")
    line([r for r in settled if r["gates"]["conf_c8plus"] and not r["gates"]["price_and_edge"]],
         "rejected: price/edge margin (C8+)")
    line([r for r in settled if not r["gates"]["plausible"]],
         "rejected: plausibility window")
    line([r for r in settled if r.get("vector_gate") in ("FAIL", "UNAVAILABLE")
          and r["gates"]["conf_c8plus"]],
         "rejected: vector gate (C8+)")

    # 3. Signal shootout
    print("\nSIGNAL SHOOTOUT:")
    for label, keyfn, cuts in (
        ("run_diff", lambda r: r.get("run_diff") or 0, (0.5, 1.0, 1.5, 2.0)),
        ("price_edge", lambda r: r.get("price_edge") if r.get("price_edge") is not None else -9,
         (0.0, 0.03, 0.055, 0.10)),
    ):
        print(f"  by {label}:")
        prev = None
        for cut in cuts:
            b = [r for r in settled if keyfn(r) >= cut]
            if not b:
                continue
            w = sum(1 for r in b if r["result"]["pick_won"])
            pl = sum(profit(r["odds"], r["result"]["pick_won"]) for r in b if r.get("odds"))
            print(f"    >= {cut:<5} win% {100*w/len(b):5.1f}  net {pl:+9.1f}u  (n={len(b)})")


def hr_board():
    """HR board hit rates vs claims (reports/hr_board_ledger.json)."""
    path = os.path.join(REPO, "reports", "hr_board_ledger.json")
    try:
        with open(path) as f:
            rows = [r for r in json.load(f)["rows"].values() if r.get("result")]
    except Exception:
        return
    if not rows:
        return
    print("\nHR BOARD (graded rows):")
    for tier in ("core", "watch"):
        t = [r for r in rows if r.get("tier") == tier and not r.get("captured_live")]
        if not t:
            continue
        hit = sum(1 for r in t if r["result"]["homered"])
        # implied per-game prob from the per-AB rate over ~3.9 AB
        imp = sum(1 - (1 - min(r.get("hr_rate") or 0, .5)) ** 3.9 for r in t) / len(t)
        print(f"  {tier:5s}: {hit}/{len(t)} homered ({100*hit/len(t):.0f}%)  "
              f"board-implied {100*imp:.0f}%")
    lanes = {}
    for r in rows:
        lanes.setdefault(r.get("lane") or "?", []).append(r)
    for lane, lr in sorted(lanes.items()):
        hit = sum(1 for r in lr if r["result"]["homered"])
        print(f"    lane {lane:10s} {hit}/{len(lr)}")


if __name__ == "__main__":
    main()
    hr_board()

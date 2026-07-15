#!/usr/bin/env python3
"""
test_mlb_model_gates.py — assertions on the MLB sim's calibration + gate
functions (scripts/mlb_model_gates.py, imported by build_mlb_sim.py).

Run: python3 scripts/test_mlb_model_gates.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mlb_model_gates import (
    MAX_PUBLISHABLE_FAV_ODDS,
    WP_CALIBRATION_PATH,
    calibrate_win_prob,
    confidence_cap_from_market_edge,
    display_wp_pair,
    load_wp_calibration,
    stake_for_conf,
)


def test_calibration_monotonic():
    curve = load_wp_calibration()
    assert curve, f"expected a fresh fitted curve at {WP_CALIBRATION_PATH}"
    grid = [0.30 + i * 0.005 for i in range(121)]  # 0.30 .. 0.90
    cal = [calibrate_win_prob(p, curve) for p in grid]
    for i in range(1, len(cal)):
        assert cal[i] >= cal[i - 1] - 1e-12, (
            f"calibration not monotonic at raw={grid[i]:.3f}: "
            f"{cal[i - 1]:.4f} -> {cal[i]:.4f}"
        )
    assert all(0.0 < c < 1.0 for c in cal)
    # The fix's whole point: stated heavy probabilities calibrate way down.
    c75 = calibrate_win_prob(0.75, curve)
    assert c75 < 0.62, f"calibrated(0.75)={c75:.4f} should sit near ~0.55, not near raw"
    print(f"  ok  calibration monotonic; calibrated(0.62)={calibrate_win_prob(0.62, curve):.4f}, "
          f"calibrated(0.75)={c75:.4f}, calibrated(0.82)={calibrate_win_prob(0.82, curve):.4f}")


def test_calibration_identity_fallback():
    assert calibrate_win_prob(0.615, None) == 0.615
    assert calibrate_win_prob(0.615, []) == 0.615
    print("  ok  identity fallback when curve missing")


def test_price_ceiling_caps_to_c7():
    assert MAX_PUBLISHABLE_FAV_ODDS == -160
    # -200 favorite: capped to <=7 regardless of how big the stated edge is.
    for edge in (0.055, 0.080, 0.130, 0.170):
        cap = confidence_cap_from_market_edge(edge, pick_odds=-200)
        assert cap <= 7, f"-200 at edge {edge} gave cap {cap}, expected <=7"
    for odds in (-161, -175, -250, -320):
        assert confidence_cap_from_market_edge(0.14, pick_odds=odds) <= 7
    # Exactly -160 and longer prices keep their edge-based tier.
    assert confidence_cap_from_market_edge(0.14, pick_odds=-160) == 10
    assert confidence_cap_from_market_edge(0.09, pick_odds=-120) == 9
    assert confidence_cap_from_market_edge(0.06, pick_odds=150) == 8
    # Pre-existing behavior intact: plausibility window + None edge.
    assert confidence_cap_from_market_edge(0.19, pick_odds=110) == 7
    assert confidence_cap_from_market_edge(None) == 0
    assert confidence_cap_from_market_edge(0.14) == 10  # no odds passed
    print("  ok  odds shorter than -160 cap confidence to C7")


def test_flat_staking():
    assert stake_for_conf(8) == 50
    assert stake_for_conf(9) == 50
    assert stake_for_conf(10) == 50
    assert stake_for_conf(7) == 20  # board-only tier unchanged
    assert stake_for_conf(0) == 0
    print("  ok  flat 50u stake for C8/C9/C10")


def test_display_cap():
    assert display_wp_pair(72.4, 27.6) == (65.0, 35.0)
    assert display_wp_pair(27.6, 72.4) == (35.0, 65.0)
    assert display_wp_pair(58.0, 42.0) == (58.0, 42.0)
    print("  ok  displayed win% capped at 65")


if __name__ == "__main__":
    test_calibration_monotonic()
    test_calibration_identity_fallback()
    test_price_ceiling_caps_to_c7()
    test_flat_staking()
    test_display_cap()
    print("ALL TESTS PASSED")

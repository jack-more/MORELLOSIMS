#!/usr/bin/env python3
"""
mlb_model_gates.py — pure pick-gating, staking, and win-probability
calibration helpers for the MLB sim.

Extracted from build_mlb_sim.py so the gate/calibration logic can be imported
and unit-tested without executing the full live builder (which fetches
schedules, lineups, and odds at import time). build_mlb_sim.py imports
everything here; behavior is identical to having the code inline.
"""

import json
import os
from datetime import datetime, timezone

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_SCRIPT_DIR)

# ─── Staking ────────────────────────────────────────────────────────────────
# FLAT STAKING (2026-07-15). The tiered ladder {8:30, 9:50, 10:100} was
# inverted relative to realized edge: on 300 settled ML picks, C10 — the
# biggest stake — had the WORST realized edge (~-3.2pp vs price, -4.8% ROI)
# while C8/C9 carried the profit. Flat 50u per published pick removes the
# confidence-ladder leverage on exactly the picks the model is worst at,
# and roughly halves historical drawdown in replay. C7 stays board-only.
STAKE_BY_CONF = {
    10: 50,
    9: 50,
    8: 50,
    7: 20,
}

MAX_FAV_BY_CONF = {
    # Emergency cap only. The real price gate compares model win
    # probability against the sportsbook break-even probability.
    8: -180,
    9: -200,
    10: -220,
}

MIN_MODEL_EDGE_BY_CONF = {
    # Required model probability over market break-even. When the tracked
    # season is near flat, C8 cannot be a barely-over-juice play.
    8: 0.055,
    9: 0.080,
    10: 0.130,
}

# Upper bound of the plausibility window. When the model's win probability
# beats the market break-even by this much, history says the model is wrong,
# not the market: May-Jul 2026 settled picks with edge >= 0.18 ran well below
# their prices (0.20+ bucket: 12-17, -15% ROI) while the market's Brier score
# beat the model's (0.251 vs 0.268) on the model's own picks. Such games stay
# on the board at C7 but do not qualify as tracked picks.
MAX_PLAUSIBLE_EDGE = 0.18

# Hard price ceiling (2026-07-15). Heavy favorites are where the model's
# stated probabilities are least honest: settled picks at -200 or shorter
# went 12-9 (57.1%) but needed 70.4% to break even and ran -22.4% ROI.
# No published (tracked, C8+) pick may be priced shorter than -160; such
# games stay visible on the board at C7 — same untracked-but-visible
# pattern as the MAX_PLAUSIBLE_EDGE window above.
MAX_PUBLISHABLE_FAV_ODDS = -160


def stake_for_conf(conf):
    """Return $PP risk by confidence grade."""
    return STAKE_BY_CONF.get(int(conf or 0), 0)


def moneyline_break_even(odds):
    """Return implied break-even probability for American odds."""
    try:
        odds = int(odds)
    except (TypeError, ValueError):
        return None
    if odds == 0:
        return None
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)


def confidence_cap_from_market_edge(price_edge, pick_odds=None):
    """Cap confidence from the model-vs-market price edge, plus the hard
    -160 favorite ceiling (see MAX_PUBLISHABLE_FAV_ODDS above)."""
    if price_edge is None:
        return 0
    if price_edge >= MAX_PLAUSIBLE_EDGE:
        cap = 7
    elif price_edge >= 0.130:
        cap = 10
    elif price_edge >= 0.080:
        cap = 9
    elif price_edge >= 0.055:
        cap = 8
    elif price_edge >= 0.035:
        cap = 7
    else:
        cap = 6
    if pick_odds is not None:
        try:
            odds_int = int(pick_odds)
        except (TypeError, ValueError):
            odds_int = 0
        if odds_int != 0 and odds_int < MAX_PUBLISHABLE_FAV_ODDS:
            cap = min(cap, 7)
    return cap


# ─── Win-probability recalibration ──────────────────────────────────────────
# The raw Pythagorean WP is well calibrated at 55-65% (+8.5% ROI on settled
# picks) but collapses above 65%: stated 67-82% picks won ~51-55% flat.
# fit_wp_calibration.py fits a monotonic raw→actual curve from settled picks
# in picks/mlb.json; we pass pick_model_prob through it BEFORE the edge gates
# so MIN_MODEL_EDGE_BY_CONF and the 0.18 plausibility window operate on
# honest probabilities.
WP_CALIBRATION_PATH = os.path.join(REPO_ROOT, "reports", "wp_calibration.json")
WP_CALIBRATION_MAX_AGE_DAYS = 60

# Displayed win% honesty cap: the model has never demonstrated real >65%
# skill, so the rendered WIN PROB is clamped to 65/35. Display only — raw
# and calibrated probabilities are kept in the pick record for refits.
WP_DISPLAY_CAP = 65.0


def load_wp_calibration(path=WP_CALIBRATION_PATH, max_age_days=WP_CALIBRATION_MAX_AGE_DAYS, now=None):
    """Load the fitted calibration curve.

    Returns a list of [raw_p, calibrated_p] points sorted by raw_p, or None
    (→ identity calibration) if the file is missing, malformed, or stale.
    """
    try:
        with open(path) as f:
            data = json.load(f)
        curve = data.get("curve") or []
        curve = sorted(
            [[float(x), float(y)] for x, y in curve if x is not None and y is not None],
            key=lambda pt: pt[0],
        )
        if len(curve) < 2:
            print(f"  WARN: wp_calibration.json has <2 curve points; using identity")
            return None
        fitted_at = data.get("fitted_at")
        if fitted_at and max_age_days:
            try:
                ts = datetime.fromisoformat(str(fitted_at).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                now = now or datetime.now(timezone.utc)
                age_days = (now - ts).total_seconds() / 86400
                if age_days > max_age_days:
                    print(
                        f"  WARN: wp_calibration.json is {age_days:.0f}d old "
                        f"(>{max_age_days}d); using identity — rerun fit_wp_calibration.py"
                    )
                    return None
            except (ValueError, TypeError):
                pass
        return curve
    except FileNotFoundError:
        print("  WARN: reports/wp_calibration.json missing; using identity calibration")
        return None
    except Exception as e:
        print(f"  WARN: could not load wp calibration ({e}); using identity")
        return None


def calibrate_win_prob(raw_p, curve):
    """Map a raw model win probability (0-1) through the fitted curve by
    linear interpolation. Clips to curve endpoints outside the fitted range
    (conservative: a raw 0.90 calibrates no higher than the max observed).
    Identity if curve is None."""
    try:
        p = float(raw_p)
    except (TypeError, ValueError):
        return raw_p
    if not curve:
        return p
    if p <= curve[0][0]:
        return curve[0][1]
    if p >= curve[-1][0]:
        return curve[-1][1]
    for i in range(1, len(curve)):
        x0, y0 = curve[i - 1]
        x1, y1 = curve[i]
        if p <= x1:
            if x1 == x0:
                return y1
            return y0 + (y1 - y0) * (p - x0) / (x1 - x0)
    return curve[-1][1]


def display_wp_pair(away_wp, home_wp):
    """Display-only clamp of the rendered win% pair to WP_DISPLAY_CAP."""
    try:
        a = float(away_wp)
        h = float(home_wp)
    except (TypeError, ValueError):
        return away_wp, home_wp
    if a > WP_DISPLAY_CAP:
        return round(WP_DISPLAY_CAP, 1), round(100 - WP_DISPLAY_CAP, 1)
    if h > WP_DISPLAY_CAP:
        return round(100 - WP_DISPLAY_CAP, 1), round(WP_DISPLAY_CAP, 1)
    return a, h

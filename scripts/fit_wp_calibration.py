#!/usr/bin/env python3
"""
fit_wp_calibration.py — fit a monotonic recalibration of the MLB sim's raw
model win probability against realized win rate.

Motivation (2026-07-15 audit of 300 settled ML picks): the raw Pythagorean WP
is well calibrated at 55-65% (+8.5% ROI) but collapses above 65% — picks
stated at 67-82% won only ~51-55% flat. This script fits raw_p → actual win
rate and writes reports/wp_calibration.json, which build_mlb_sim.py applies
to pick_model_prob BEFORE the edge gates (via scripts/mlb_model_gates.py).

Data:
  picks/mlb.json         settled ML picks (status win/loss)
  mlbsim/picks_log.csv   model WP per pick (join on date/away/home[/game_pk])

Method: 5pp bins → empirical-Bayes shrinkage toward the global win rate
(m=50 pseudo-samples; a raw isotonic fit on individual outcomes let a noisy
n=20 bin at raw ~0.77 that ran 70% map calibrated(0.80)→0.70, exactly the
overconfident tail this fix exists to kill) → isotonic regression on the
shrunk bin means (sklearn when available, else hand-rolled
pool-adjacent-violators — the two are equivalent on binned data).

Usage: python3 scripts/fit_wp_calibration.py
"""

import csv
import json
import os
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SCRIPT_DIR)
PICKS_JSON = os.path.join(REPO, "picks", "mlb.json")
PICKS_LOG = os.path.join(REPO, "mlbsim", "picks_log.csv")
OUT_PATH = os.path.join(REPO, "reports", "wp_calibration.json")


def load_settled_with_model_wp():
    """Join settled ML picks with the raw model WP for the picked side."""
    with open(PICKS_JSON) as f:
        picks = json.load(f)
    settled = [
        p for p in picks
        if p.get("sport") == "mlb"
        and p.get("bet_type") == "ml"
        and p.get("status") in ("win", "loss")
    ]

    log_by_key = {}
    with open(PICKS_LOG, newline="") as f:
        for row in csv.DictReader(f):
            pk_key = (row.get("date"), row.get("away"), row.get("home"), str(row.get("game_pk") or ""))
            log_by_key[pk_key] = row
            # matchup-only fallback for legacy rows without game_pk
            log_by_key.setdefault((row.get("date"), row.get("away"), row.get("home")), row)

    samples = []  # (raw_prob, won)
    missed = 0
    for p in settled:
        key = (p.get("date"), p.get("away"), p.get("home"), str(p.get("game_pk") or ""))
        row = log_by_key.get(key) or log_by_key.get((p.get("date"), p.get("away"), p.get("home")))
        if row is None:
            missed += 1
            continue
        # If the pick record itself carries the raw WP (post-2026-07-15
        # builds write model_wp_raw), prefer it — it is the exact pregame
        # number. Otherwise use the logged WP for the picked side.
        raw_wp = p.get("model_wp_raw")
        if raw_wp is None:
            side = p.get("side")
            wp_field = "away_wp" if side == p.get("away") else "home_wp"
            try:
                raw_wp = float(row.get(wp_field) or 0)
            except (TypeError, ValueError):
                raw_wp = 0
        try:
            raw_p = float(raw_wp) / 100.0
        except (TypeError, ValueError):
            continue
        if not (0 < raw_p < 1):
            continue
        samples.append((raw_p, 1 if p.get("status") == "win" else 0))
    return samples, missed


def pava(values, weights):
    """Pool-adjacent-violators: weighted monotonic (non-decreasing) fit."""
    vals = list(values)
    wts = list(weights)
    # blocks of (value, weight, count)
    blocks = [[v, w, 1] for v, w in zip(vals, wts)]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] > blocks[i + 1][0] + 1e-12:
            v0, w0, n0 = blocks[i]
            v1, w1, n1 = blocks[i + 1]
            merged_w = w0 + w1
            merged_v = (v0 * w0 + v1 * w1) / merged_w
            blocks[i] = [merged_v, merged_w, n0 + n1]
            del blocks[i + 1]
            if i > 0:
                i -= 1
        else:
            i += 1
    out = []
    for v, _, n in blocks:
        out.extend([v] * n)
    return out


SHRINKAGE_M = 50  # pseudo-samples of prior (global win rate) per bin


def bin_samples(samples, bin_width=0.05):
    """5pp bins → list of (mean_raw_p, actual_win_rate, n), sorted by raw_p."""
    bins = {}
    for p, won in samples:
        b = int(p / bin_width)
        bins.setdefault(b, []).append((p, won))
    out = []
    for k in sorted(bins):
        pts = bins[k]
        out.append((
            sum(p for p, _ in pts) / len(pts),
            sum(w for _, w in pts) / len(pts),
            len(pts),
        ))
    return out


def fit_curve(samples):
    """Shrunk-bin isotonic fit. Returns (curve, method, bin_table)."""
    bin_table = bin_samples(samples)
    global_rate = sum(w for _, w in samples) / len(samples)
    xs = [x for x, _, _ in bin_table]
    ns = [n for _, _, n in bin_table]
    ys_shrunk = [
        (y * n + global_rate * SHRINKAGE_M) / (n + SHRINKAGE_M)
        for _, y, n in bin_table
    ]
    try:
        from sklearn.isotonic import IsotonicRegression
        iso = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds="clip")
        fitted = iso.fit_transform(xs, ys_shrunk, sample_weight=ns)
        method = "shrunk_bins_isotonic_sklearn"
    except ImportError:
        fitted = pava(ys_shrunk, ns)
        method = "shrunk_bins_pava"
    curve = [[round(x, 4), round(float(y), 4)] for x, y in zip(xs, fitted)]
    return curve, method, bin_table


def main():
    samples, missed = load_settled_with_model_wp()
    n = len(samples)
    print(f"Settled ML picks with model WP joined: {n} (unjoined: {missed})")
    if n < 50:
        raise SystemExit(f"Refusing to fit on n={n} < 50 samples")

    curve, method, bin_table = fit_curve(samples)
    print(f"Method: {method}, curve points: {len(curve)}")

    print("\nRaw 5pp bins (mean raw_p, actual win rate, n):")
    for x, y, w in bin_table:
        print(f"  {x:.3f} -> {y:.3f}  (n={w})")

    out = {
        "fitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n": n,
        "method": method,
        "source": ["picks/mlb.json", "mlbsim/picks_log.csv"],
        "curve": curve,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
        f.write("\n")
    print(f"\nWrote {OUT_PATH}")

    # Sanity readout at key raw probabilities.
    import sys
    sys.path.insert(0, SCRIPT_DIR)
    from mlb_model_gates import calibrate_win_prob
    for raw in (0.55, 0.58, 0.62, 0.65, 0.70, 0.75, 0.80):
        print(f"  calibrated({raw:.2f}) = {calibrate_win_prob(raw, curve):.4f}")


if __name__ == "__main__":
    main()

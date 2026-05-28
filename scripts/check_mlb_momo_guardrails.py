#!/usr/bin/env python3
"""Fail the MLB pipeline if MOMO/MOMI regress to misleading player scores."""

import re
import sys
from pathlib import Path

from mlb_momo import matchup_swing_to_momo, momentum_to_momi

REPO_ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = REPO_ROOT / "mlbsim" / "index.html"


def _decimal_from_dot(value):
    return float(f"0.{value}")


def _first(pattern, text):
    match = re.search(pattern, text, re.S)
    return match.group(1) if match else None


def check_formula_guardrails():
    scenarios = [
        {
            "name": "elite hitter, playable archetype downgrade",
            "base_woba": 0.417,
            "vs_woba": 0.325,
            "min_momo": 55,
            "max_momo": 75,
        },
        {
            "name": "good hitter, near-neutral archetype",
            "base_woba": 0.338,
            "vs_woba": 0.336,
            "min_momo": 55,
            "max_momo": 75,
        },
        {
            "name": "elite hitter, poor archetype still not single-digit",
            "base_woba": 0.375,
            "vs_woba": 0.242,
            "min_momo": 35,
            "max_momo": 55,
        },
    ]

    errors = []
    for scenario in scenarios:
        score = matchup_swing_to_momo(scenario["base_woba"], scenario["vs_woba"])
        if not scenario["min_momo"] <= score <= scenario["max_momo"]:
            errors.append(
                f'{scenario["name"]}: MOMO {score} outside '
                f'{scenario["min_momo"]}-{scenario["max_momo"]}'
            )

    momi_scenarios = [
        {
            "name": "no active streak keeps MOMI at MOMO",
            "momo": 64,
            "streak": 0,
            "last7_avg": 0.120,
            "direction": "flat",
        },
        {
            "name": "cold active form can push MOMO down",
            "momo": 64,
            "streak": 1,
            "last7_avg": 0.120,
            "direction": "down",
        },
        {
            "name": "neutral active form keeps MOMI close to MOMO",
            "momo": 64,
            "streak": 1,
            "last7_avg": 0.250,
            "direction": "flat",
        },
        {
            "name": "hot streak pushes MOMO up",
            "momo": 64,
            "streak": 7,
            "last7_avg": 0.375,
            "direction": "up",
        },
    ]

    for scenario in momi_scenarios:
        momi = momentum_to_momi(scenario["momo"], scenario["streak"], scenario["last7_avg"])
        delta = momi - scenario["momo"]
        if scenario["direction"] == "down" and delta >= 0:
            errors.append(f'{scenario["name"]}: MOMI {momi} did not move below MOMO {scenario["momo"]}')
        if scenario["direction"] == "up" and delta <= 0:
            errors.append(f'{scenario["name"]}: MOMI {momi} did not move above MOMO {scenario["momo"]}')
        if scenario["direction"] == "flat" and abs(delta) > 3:
            errors.append(f'{scenario["name"]}: MOMI {momi} drifted too far from MOMO {scenario["momo"]}')
    return errors


def iter_batter_rows(html):
    for block in html.split('<div class="batter-row">')[1:]:
        name = _first(r'<span class="batter-name">([^<]+)</span>', block)
        momo = _first(r'MOMO</span>(\d+)', block)
        momi = _first(r'MOMI</span>(\d+)', block)
        base = _first(r'WOBA</span>\.([0-9]+)', block)
        arch = _first(r'ARCH</span>\.([0-9]+)', block)
        run_value = _first(r'batter-range">\+([0-9.]+) R', block)
        if not all([name, momo, momi, base, arch]):
            continue
        yield {
            "name": name,
            "momo": int(momo),
            "momi": int(momi),
            "base_woba": _decimal_from_dot(base),
            "vs_woba": _decimal_from_dot(arch),
            "run_value": float(run_value or 0),
        }


def check_generated_page():
    html = HTML_PATH.read_text()
    rows = list(iter_batter_rows(html))
    errors = []

    if not rows:
        return [f"No batter rows found in {HTML_PATH}"]

    for row in rows:
        name = row["name"]
        momo = row["momo"]
        momi = row["momi"]
        base = row["base_woba"]
        vs = row["vs_woba"]
        run_value = row["run_value"]

        if not 1 <= momo <= 99:
            errors.append(f"{name}: MOMO {momo} outside 1-99")
        if not 1 <= momi <= 99:
            errors.append(f"{name}: MOMI {momi} outside 1-99")
        if vs >= 0.310 and momo < 50:
            errors.append(f"{name}: .{int(vs * 1000):03d} ARCH cannot produce MOMO {momo}")
        if base >= 0.370 and vs >= 0.300 and momo < 55:
            errors.append(
                f"{name}: elite base .{int(base * 1000):03d} with playable ARCH "
                f".{int(vs * 1000):03d} cannot produce MOMO {momo}"
            )
        if base >= 0.370 and vs >= 0.300 and momi < 45:
            errors.append(
                f"{name}: elite/playable matchup cannot produce MOMI {momi}"
            )
        if run_value >= 0.50 and base >= 0.370 and momo < 55:
            errors.append(
                f"{name}: +{run_value:.2f}R elite bat cannot produce MOMO {momo}"
            )
        if max(base, vs) >= 0.300 and min(momo, momi) <= 9:
            errors.append(
                f"{name}: playable wOBA context cannot produce single-digit "
                f"MOMO/MOMI ({momo}/{momi})"
            )

    print(f"Checked {len(rows)} MLB batter MOMO/MOMI rows.")
    return errors


def main():
    errors = check_formula_guardrails()
    errors.extend(check_generated_page())

    if errors:
        print("MLB MOMO guardrails failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("MLB MOMO guardrails passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

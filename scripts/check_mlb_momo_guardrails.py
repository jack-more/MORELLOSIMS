#!/usr/bin/env python3
"""Fail the MLB pipeline if MOMO/MOMI regress to misleading player scores."""

import re
import sys
from pathlib import Path

from mlb_momo import matchup_swing_to_momo, momentum_to_momi

REPO_ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = REPO_ROOT / "mlbsim" / "index.html"
SIM_SCRIPT_PATH = REPO_ROOT / "scripts" / "build_mlb_sim.py"
REFRESH_SCRIPT_PATH = REPO_ROOT / "scripts" / "refresh_atlas_2026.py"
VERIFY_SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_mlb_publish.py"
MLB_PIPELINE_PATH = REPO_ROOT / ".github" / "workflows" / "mlb-pipeline.yml"
MLB_HEALTHCHECK_PATH = REPO_ROOT / ".github" / "workflows" / "mlb-healthcheck.yml"


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
            "name": "no streak and no density keeps MOMI at MOMO",
            "momo": 64,
            "streak": 0,
            "last7_avg": 0.120,
            "hit_games_last5": 2,
            "games_last5": 5,
            "hit_games_last7": 3,
            "games_last7": 7,
            "direction": "flat",
        },
        {
            "name": "four of last five hit games pushes MOMO up",
            "momo": 64,
            "streak": 0,
            "last7_avg": 0.320,
            "hit_games_last5": 4,
            "games_last5": 5,
            "hit_games_last7": 5,
            "games_last7": 7,
            "direction": "up",
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
        momi = momentum_to_momi(
            scenario["momo"],
            scenario["streak"],
            scenario["last7_avg"],
            scenario.get("hit_games_last5", 0),
            scenario.get("games_last5", 0),
            scenario.get("hit_games_last7", 0),
            scenario.get("games_last7", 0),
            scenario.get("hit_games_last10", 0),
            scenario.get("games_last10", 0),
        )
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
    critical = []
    warnings = []

    if not rows:
        return [f"No batter rows found in {HTML_PATH}"], []

    for row in rows:
        name = row["name"]
        momo = row["momo"]
        momi = row["momi"]
        base = row["base_woba"]
        vs = row["vs_woba"]
        run_value = row["run_value"]

        if not 1 <= momo <= 99:
            critical.append(f"{name}: MOMO {momo} outside 1-99")
        if not 1 <= momi <= 99:
            critical.append(f"{name}: MOMI {momi} outside 1-99")
        if vs >= 0.310 and momo < 45:
            critical.append(f"{name}: .{int(vs * 1000):03d} ARCH cannot produce MOMO {momo}")
        elif vs >= 0.310 and momo < 50:
            warnings.append(f"{name}: .{int(vs * 1000):03d} ARCH produced low MOMO {momo}")
        if base >= 0.370 and vs >= 0.300 and momo < 45:
            critical.append(
                f"{name}: elite base .{int(base * 1000):03d} with playable ARCH "
                f".{int(vs * 1000):03d} cannot produce MOMO {momo}"
            )
        elif base >= 0.370 and vs >= 0.300 and momo < 55:
            warnings.append(
                f"{name}: elite base .{int(base * 1000):03d} with playable ARCH "
                f".{int(vs * 1000):03d} produced low MOMO {momo}"
            )
        if base >= 0.370 and vs >= 0.300 and momi < 35:
            critical.append(
                f"{name}: elite/playable matchup cannot produce MOMI {momi}"
            )
        elif base >= 0.370 and vs >= 0.300 and momi < 45:
            warnings.append(
                f"{name}: elite/playable matchup produced low MOMI {momi}"
            )
        if run_value >= 0.50 and base >= 0.370 and vs >= 0.285 and momo < 40:
            critical.append(
                f"{name}: +{run_value:.2f}R elite bat cannot produce MOMO {momo}"
            )
        elif run_value >= 0.50 and base >= 0.370 and vs >= 0.285 and momo < 50:
            warnings.append(
                f"{name}: +{run_value:.2f}R elite bat produced low MOMO {momo}"
            )
        if run_value >= 0.50 and base >= 0.370 and momo < 35:
            critical.append(
                f"{name}: +{run_value:.2f}R elite bat cannot be buried at MOMO {momo}"
            )
        if max(base, vs) >= 0.300 and min(momo, momi) <= 9:
            critical.append(
                f"{name}: playable wOBA context cannot produce single-digit "
                f"MOMO/MOMI ({momo}/{momi})"
            )

    print(f"Checked {len(rows)} MLB batter MOMO/MOMI rows.")
    return critical, warnings


def check_hr_lotto_guardrails():
    errors = []
    source = SIM_SCRIPT_PATH.read_text()

    required_source_markers = [
        ("HR_LONGSHOT_MAX_ROWS = 8", "HR Watchlist must stay wide enough for damage and stack lanes"),
        ("def hr_damage_score", "HR Lotto must keep the dedicated damage score"),
        ("def hr_damage_lane_ok", "HR Lotto must keep pure HR-damage overrides"),
        ("def fetch_live_pitcher_h2h", "HR Lotto must fetch live direct H2H instead of relying on stale atlas H2H"),
        ("historical batter-vs-starter context", "Live direct H2H must stay populated after first pitch"),
        ("def hr_h2h_lane_ok", "HR Lotto must keep direct H2H power overrides"),
        ("HR_CORE_H2H_ROWS", "HR Lotto must reserve primary-card H2H override slots"),
        ("HR_CORE_STACK_ROWS", "HR Lotto must reserve primary-card stack-pressure override slots"),
        ("def hr_primary_stack_lane_ok", "HR Lotto must promote near-core stack-pressure bats into the primary card"),
        ("def hr_selection_score", "HR Lotto must rank by H2H, damage, stack pressure, and HR rate together"),
        ("HR_LONGSHOT_H2H_ROWS", "HR Watchlist must reserve H2H override slots"),
        ("def team_stack_pressure", "HR Lotto must keep team stack-pressure scoring"),
        ("def hr_stack_lane_ok", "HR Lotto must keep stack-pressure watchlist qualifiers"),
        ("HR_LONGSHOT_STANDARD_ROWS", "HR Watchlist must reserve standard-lane slots"),
        ("HR_LONGSHOT_DAMAGE_ROWS", "HR Watchlist must reserve damage-override slots"),
        ("HR_LONGSHOT_STACK_ROWS", "HR Watchlist must reserve stack-pressure slots"),
        ("H2H {int(bm.get(\"h2h_hr\", 0))}HR", "Rendered HR rows must expose direct H2H HR history"),
        ("for batter_id in batter_ids", "Live direct H2H fetch must check every lineup batter"),
        ("pair_key = (pitcher_id, batter_id)", "Live direct H2H fetch must cache by pitcher-batter pair"),
        ("vsPlayerTotal", "Live direct H2H fetch must prefer official total rows when MLB returns them"),
        ("matching_splits", "Live direct H2H fetch must aggregate split rows when total rows are absent"),
        ("ThreadPoolExecutor(max_workers=max_workers)", "Live direct H2H pair fetch must stay bounded-concurrent"),
        ("max_workers = min(8", "Live direct H2H pair fetch must keep a safe concurrency cap"),
        ("DMG {round(hr_damage_score(bm))}", "Rendered HR rows must show DMG score"),
        ("stack pressure", "Rendered HR Watchlist copy must expose stack pressure"),
        ("direct H2H", "Rendered HR Watchlist copy must expose direct H2H criteria"),
    ]
    for marker, message in required_source_markers:
        if marker not in source:
            errors.append(f"{message}: missing `{marker}`")
    if "anchor_id = batter_ids[0]" in source:
        errors.append("Live direct H2H fetch must not cache one leadoff-batter lookup as the whole pitcher table")
    if "away_direct_h2h = {}" in source or "home_direct_h2h = {}" in source:
        errors.append("Late MLB refreshes must not blank historical direct H2H after first pitch")

    max_rows = _first(r"HR_LONGSHOT_MAX_ROWS\s*=\s*(\d+)", source)
    if max_rows is None or int(max_rows) < 8:
        errors.append("HR Watchlist must allow at least 8 rows after June 4 audit")

    html = HTML_PATH.read_text()
    required_html_markers = [
        ("damage score", "HR Lotto page must show damage score criteria"),
        ("direct H2H", "HR Lotto page must show direct H2H criteria"),
        ("stack pressure", "HR Watchlist page must show stack pressure criteria"),
    ]
    for marker, message in required_html_markers:
        if marker not in html:
            errors.append(f"{message}: missing `{marker}`")

    hr_rows = re.findall(r'<div class="hr-row [^"]+">.*?</div>\s*</div>', html, re.S)
    if hr_rows and "DMG " not in html:
        errors.append("Rendered HR rows exist but do not show DMG score")

    return errors


def check_mlb_pick_gate_guardrails():
    errors = []
    source = SIM_SCRIPT_PATH.read_text()

    expected_hard_caps = {
        8: -180,
        9: -200,
        10: -220,
    }
    block = _first(r"MAX_FAV_BY_CONF\s*=\s*\{(.*?)\}", source)
    if block is None:
        return ["Missing MAX_FAV_BY_CONF emergency price caps"]

    for conf, expected in expected_hard_caps.items():
        match = re.search(rf"\b{conf}\s*:\s*(-?\d+)", block)
        if not match:
            errors.append(f"Missing C{conf} emergency favorite cap")
            continue
        actual = int(match.group(1))
        if actual < expected:
            errors.append(
                f"C{conf} emergency favorite cap is too loose: {actual}, expected {expected} or shorter"
            )

    required_markers = [
        ("MIN_MODEL_EDGE_BY_CONF", "MLB price gate must keep confidence-based EV margins"),
        ("def moneyline_break_even", "MLB price gate must compare odds to market break-even"),
        ("pick_model_prob", "MLB price gate must store model win probability"),
        ("pick_break_even", "MLB price gate must store sportsbook break-even"),
        ("pick_price_edge", "MLB price gate must store model-vs-market price edge"),
        ("pick_price_edge < min_price_edge", "MLB price gate must block only when edge misses the margin"),
        ("unstarted_game_pks", "Pregame pending stale-pick pruning must stay enabled"),
        ("odds_feed_has_lines", "Pregame pending pruning must be disabled when every odds source is down"),
        ("preserving pending MLB picks", "Odds outage path must preserve pending MLB picks"),
        ("pick_id not in qualified_ids", "Pending picks must be removable when current gates say no play"),
    ]
    for marker, message in required_markers:
        if marker not in source:
            errors.append(f"{message}: missing `{marker}`")

    return errors


def check_atlas_refresh_guardrails():
    errors = []
    source = REFRESH_SCRIPT_PATH.read_text()
    required_markers = [
        ("def compute_hitter_vs_pitcher", "Atlas refresh must compute direct batter-vs-pitcher H2H"),
        ("def merge_hitter_vs_pitcher", "Atlas refresh must merge direct H2H idempotently"),
        ("save_atlas(\"hitter_vs_pitcher.json\"", "Atlas refresh must save hitter_vs_pitcher.json"),
        ("baseline_pa", "Direct H2H merge must snapshot pre-2026 baseline to avoid double-counting"),
        ("hvp_records = compute_hitter_vs_pitcher", "Atlas refresh must run the direct H2H compute step"),
        ("n_hvp = merge_hitter_vs_pitcher", "Atlas refresh must run the direct H2H merge step"),
    ]
    for marker, message in required_markers:
        if marker not in source:
            errors.append(f"{message}: missing `{marker}`")
    return errors


def check_publish_freshness_guardrails():
    errors = []
    verify_source = VERIFY_SCRIPT_PATH.read_text()
    pipeline = MLB_PIPELINE_PATH.read_text()
    healthcheck = MLB_HEALTHCHECK_PATH.read_text()
    required_markers = [
        (verify_source, "--max-age-minutes", "Publish verifier must support max-age checks"),
        (verify_source, "--require-hr-h2h-lane", "Publish verifier must require HR H2H lane when requested"),
        (verify_source, "age_minutes > args.max_age_minutes", "Publish verifier must fail stale generated pages"),
        (verify_source, "direct H2H", "Publish verifier must detect stale HR-card logic"),
        (pipeline, "0 23 * * *", "MLB pipeline must keep 7 PM ET late-slate refresh"),
        (pipeline, "0 0 * * *", "MLB pipeline must keep 8 PM ET West Coast refresh"),
        (pipeline, "--max-age-minutes 90 --require-hr-h2h-lane", "MLB pipeline must enforce fresh H2H HR-card publish checks"),
        (healthcheck, "--max-age-minutes 100 --require-hr-h2h-lane", "Live MLB healthcheck must enforce fresh H2H HR-card checks"),
    ]
    for text, marker, message in required_markers:
        if marker not in text:
            errors.append(f"{message}: missing `{marker}`")
    return errors


def main():
    errors = check_formula_guardrails()
    page_errors, warnings = check_generated_page()
    errors.extend(page_errors)
    errors.extend(check_hr_lotto_guardrails())
    errors.extend(check_mlb_pick_gate_guardrails())
    errors.extend(check_atlas_refresh_guardrails())
    errors.extend(check_publish_freshness_guardrails())

    if warnings:
        print("MLB MOMO guardrail warnings:")
        for warning in warnings:
            print(f"  - {warning}")

    if errors:
        print("MLB MOMO guardrails failed with critical errors:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("MLB MOMO and HR Lotto guardrails passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

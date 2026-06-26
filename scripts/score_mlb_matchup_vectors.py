#!/usr/bin/env python3
"""
Score hitter inverse vectors against one pitcher vector.

This is an inspection tool for the new vector layer. It does not publish picks.

Examples:
  python3 scripts/score_mlb_matchup_vectors.py --pitcher 650911 --hitters 656941,607208,547180
  python3 scripts/score_mlb_matchup_vectors.py --pitcher 650911 --lineup-json /tmp/phi_lineup.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
ATLAS_DIR = REPO_ROOT / "atlas"

sys.path.insert(0, str(SCRIPT_DIR))
from mlb_vector_features import score_lineup_matchup  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score pitcher vector against hitter inverse vectors.")
    parser.add_argument("--pitcher", required=True, help="Pitcher MLBAM id.")
    parser.add_argument(
        "--hitters",
        help="Comma-separated hitter MLBAM ids. Example: 656941,607208,547180",
    )
    parser.add_argument(
        "--lineup-json",
        help="JSON file with either a list of ids or {'hitters': [ids]}.",
    )
    parser.add_argument(
        "--pitcher-vectors",
        default=str(ATLAS_DIR / "pitcher_vectors.json"),
        help="Pitcher vector JSON path.",
    )
    parser.add_argument(
        "--hitter-vectors",
        default=str(ATLAS_DIR / "hitter_inverse_vectors.json"),
        help="Hitter inverse vector JSON path.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=9,
        help="Number of hitter rows to print.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON payload.",
    )
    return parser.parse_args()


def load_json(path: str | Path) -> Any:
    with Path(path).open() as f:
        return json.load(f)


def parse_hitters(args: argparse.Namespace) -> list[str]:
    hitters: list[str] = []
    if args.hitters:
        hitters.extend([item.strip() for item in args.hitters.split(",") if item.strip()])
    if args.lineup_json:
        payload = load_json(args.lineup_json)
        if isinstance(payload, dict):
            payload = payload.get("hitters", [])
        hitters.extend([str(item) for item in payload])
    if not hitters:
        raise SystemExit("Supply --hitters or --lineup-json")
    return hitters


def print_summary(score: dict[str, Any], top: int) -> None:
    print(f"Pitcher: {score.get('pitcher_name') or score.get('pitcher')}")
    print(f"Hitters scored: {score['hitters_scored']}")
    if score["missing_hitters"]:
        print(f"Missing hitters: {', '.join(score['missing_hitters'])}")
    print(f"Average matchup delta: {score['avg_matchup_delta']:+.5f}")
    print(f"Average projected xwOBA: {score['avg_projected_xwoba']:.5f}")
    print()
    print("hitter     baseline   delta    projected   family   velo    move    loc     hand    recent")
    print("-" * 92)
    rows = sorted(
        score["hitter_scores"],
        key=lambda row: row.get("matchup_delta") or 0,
        reverse=True,
    )
    for row in rows[:top]:
        comp = row["components"]
        print(
            f"{str(row['batter']):<10}"
            f"{row['baseline_xwoba'] or 0:>8.3f} "
            f"{row['matchup_delta'] or 0:>+8.4f} "
            f"{row['projected_xwoba'] or 0:>10.4f} "
            f"{comp['pitch_family']:>+8.4f} "
            f"{comp['velocity']:>+7.4f} "
            f"{comp['movement']:>+7.4f} "
            f"{comp['location']:>+7.4f} "
            f"{comp['handedness']:>+7.4f} "
            f"{comp['recent_form']:>+8.4f}"
        )


def main() -> None:
    args = parse_args()
    pitcher_vectors = load_json(args.pitcher_vectors)
    hitter_vectors = load_json(args.hitter_vectors)
    hitters = parse_hitters(args)
    score = score_lineup_matchup(args.pitcher, hitters, pitcher_vectors, hitter_vectors)
    if args.json:
        print(json.dumps(score, indent=2))
    else:
        print_summary(score, args.top)


if __name__ == "__main__":
    main()


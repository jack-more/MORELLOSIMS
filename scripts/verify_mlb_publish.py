#!/usr/bin/env python3
"""Verify that MLB SIM artifacts are fresh enough to publish."""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[1]


def today_et():
    return datetime.now(ZoneInfo("America/New_York")).date().isoformat()


def now_et():
    return datetime.now(ZoneInfo("America/New_York"))


def read_url(url):
    request = urllib.request.Request(
        url,
        headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "MorelloSimsHealthcheck/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


def read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def load_sources(base_url):
    if base_url:
        root = base_url.rstrip("/")
        cache_buster = datetime.now(ZoneInfo("UTC")).timestamp()
        html = read_url(f"{root}/mlbsim/?v=health-{cache_buster}")
        picks_raw = read_url(f"{root}/picks/mlb.json?v=health-{cache_buster}")
    else:
        html = read_text(REPO_ROOT / "mlbsim" / "index.html")
        picks_raw = read_text(REPO_ROOT / "picks" / "mlb.json")
    return html, json.loads(picks_raw)


def main():
    parser = argparse.ArgumentParser(description="Verify fresh MLB SIM publish artifacts.")
    parser.add_argument("--base-url", help="Optional live site root, for example https://morellosims.com")
    parser.add_argument("--date", default=today_et(), help="Expected ET slate date, YYYY-MM-DD")
    parser.add_argument(
        "--max-age-minutes",
        type=int,
        help="Fail if the generated MLB page timestamp is older than this many minutes.",
    )
    parser.add_argument(
        "--require-hr-h2h-lane",
        action="store_true",
        help="Fail if the HR card was generated without direct H2H lane copy/metadata support.",
    )
    parser.add_argument(
        "--require-today-picks",
        action="store_true",
        help="Fail if picks/mlb.json has no pending picks for the expected date.",
    )
    args = parser.parse_args()

    errors = []
    html, picks = load_sources(args.base_url)

    if not isinstance(picks, list):
        errors.append("picks/mlb.json is not a JSON list")
        picks = []

    generated_match = re.search(r"Generated\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})\s+ET", html)
    generated_date = generated_match.group(1) if generated_match else None
    if generated_date != args.date:
        errors.append(f"MLB page generated date is {generated_date or 'missing'}, expected {args.date}")
    if args.max_age_minutes is not None:
        if not generated_match:
            errors.append("MLB page generated timestamp is missing")
        else:
            generated_dt = datetime.strptime(
                f"{generated_match.group(1)} {generated_match.group(2)}",
                "%Y-%m-%d %H:%M",
            ).replace(tzinfo=ZoneInfo("America/New_York"))
            age_minutes = (now_et() - generated_dt).total_seconds() / 60
            if age_minutes < -5:
                errors.append(f"MLB page generated timestamp is in the future: {generated_dt.isoformat()}")
            elif age_minutes > args.max_age_minutes:
                errors.append(
                    f"MLB page is stale: generated {age_minutes:.0f} minutes ago, "
                    f"max allowed {args.max_age_minutes}"
                )

    if args.require_hr_h2h_lane and "direct H2H" not in html:
        errors.append("MLB HR card missing direct H2H lane copy; generated page is from stale HR logic")

    todays = [
        p for p in picks
        if p.get("sport") == "mlb"
        and p.get("date") == args.date
        and p.get("bet_type") == "ml"
        and p.get("status") == "pending"
    ]
    if args.require_today_picks and not todays:
        errors.append(f"picks/mlb.json has no pending MLB picks for {args.date}")

    stale_pending = [
        p for p in picks
        if p.get("sport") == "mlb"
        and p.get("status") == "pending"
        and str(p.get("date") or "") < args.date
    ]
    if stale_pending:
        names = ", ".join(f'{p.get("date")} {p.get("matchup")}' for p in stale_pending[:5])
        errors.append(f"stale pending MLB picks before {args.date}: {names}")

    if errors:
        print("MLB publish verification failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    board = " | ".join(f'{p.get("side")} C:{p.get("conf")}' for p in todays) or "NO PENDING PICKS"
    print(f"MLB publish verification passed for {args.date}: {board}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

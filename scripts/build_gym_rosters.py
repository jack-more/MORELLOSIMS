#!/usr/bin/env python3
"""Build atlas/gym_rosters.json: each MLB team as a 'gym' with its top-9
2026 lineup drawn from atlas/batters.json, ordered by difficulty (mean wOBA).

Usage: python3 scripts/build_gym_rosters.py
"""
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MLB_API = "https://statsapi.mlb.com/api/v1"
SEASON = 2026
MIN_PA = 100
LINEUP_SIZE = 9


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "morellosims-atlas/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main():
    batters = json.load(open(ROOT / "atlas" / "batters.json"))
    by_id = {int(b["batter"]): b for b in batters if (b.get("season_PA_2026") or 0) >= MIN_PA}

    teams_meta = json.load(open(ROOT / "atlas" / "teams_2026.json"))["teams"]

    teams = fetch_json(f"{MLB_API}/teams?sportId=1&season={SEASON}")["teams"]
    gyms = []
    for team in teams:
        abbr = team.get("abbreviation")
        meta = teams_meta.get(abbr, {})
        try:
            roster = fetch_json(
                f"{MLB_API}/teams/{team['id']}/roster/active?season={SEASON}"
            ).get("roster", [])
        except Exception as err:
            print(f"skip {abbr}: {err}")
            continue
        hitters = []
        for slot in roster:
            pos = (slot.get("position") or {}).get("abbreviation", "")
            if pos == "P":
                continue
            pid = int(slot["person"]["id"])
            b = by_id.get(pid)
            if b:
                hitters.append(b)
        hitters.sort(key=lambda b: -(b.get("season_wOBA_2026") or 0))
        lineup = hitters[:LINEUP_SIZE]
        if len(lineup) < 6:
            print(f"skip {abbr}: only {len(lineup)} eligible hitters")
            continue
        avg_woba = sum(b["season_wOBA_2026"] for b in lineup) / len(lineup)
        gyms.append({
            "abbr": abbr,
            "name": meta.get("name", team.get("name")),
            "lg": meta.get("lg", ""),
            "div": meta.get("div", ""),
            "avg_woba": round(avg_woba, 4),
            "leader": {"batter": int(lineup[0]["batter"]), "name": lineup[0]["batter_name"]},
            "lineup": [int(b["batter"]) for b in lineup],
        })
        print(f"{abbr}: {len(lineup)} hitters, avg wOBA {avg_woba:.3f}, leader {lineup[0]['batter_name']}")
        time.sleep(0.3)

    gyms.sort(key=lambda g: g["avg_woba"])
    out = {"updated": time.strftime("%Y-%m-%d"), "season": SEASON, "gyms": gyms}
    out_path = ROOT / "atlas" / "gym_rosters.json"
    json.dump(out, open(out_path, "w"), indent=1)
    print(f"\nwrote {out_path} with {len(gyms)} gyms")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""fetch_season_context.py — the preseason facts the win-total sim needs, from ESPN.

  * every team's current roster (name, years of experience, injury status)
  * the injury report (status, expected return date, ESPN's note)
  * the 2025 and 2026 drafts (overall pick -> player), to project rookies

Writes data/win_totals/espn_context_<season>.json with the capture date.
Usage: python scripts/fetch_season_context.py [--season 2026-27]
"""

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
CORE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"
FIX = {"GS": "GSW", "NY": "NYK", "NO": "NOP", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS"}


def get(url, **params):
    r = requests.get(url, params=params, timeout=25)
    r.raise_for_status()
    return r.json()


def rosters():
    teams = [t["team"] for t in get(f"{SITE}/teams")["sports"][0]["leagues"][0]["teams"]]
    out = {}
    for t in teams:
        abbr = FIX.get(t["abbreviation"], t["abbreviation"])
        out[abbr] = [{"name": a["fullName"], "espn_id": a["id"], "years": (a.get("experience") or {}).get("years"),
                      "injury": [i.get("status") for i in a.get("injuries", [])]}
                     for a in get(f"{SITE}/teams/{t['id']}/roster")["athletes"]]
    return out


def injuries():
    out = []
    for t in get(f"{SITE}/injuries").get("injuries", []):
        for i in t.get("injuries", []):
            ath = i.get("athlete") or {}
            det = i.get("details") or {}
            out.append({"name": ath.get("displayName"), "team": FIX.get((ath.get("team") or {}).get("abbreviation", ""), (ath.get("team") or {}).get("abbreviation")),
                        "status": i.get("status"), "fantasy": (det.get("fantasyStatus") or {}).get("abbreviation"),
                        "return": det.get("returnDate"), "note": i.get("shortComment"), "date": i.get("date")})
    return out


def draft(year):
    picks = []
    for rnd in get(f"{CORE}/seasons/{year}/draft/rounds")["items"]:
        picks += [p for p in rnd["picks"] if p.get("athlete")]

    def name(p):
        a = requests.get(p["athlete"]["$ref"], timeout=25).json()
        return {"overall": p["overall"], "name": a.get("displayName") or a.get("fullName")}
    with ThreadPoolExecutor(8) as ex:
        return sorted(ex.map(name, picks), key=lambda x: x["overall"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="2026-27")
    args = ap.parse_args()
    start = int(args.season[:4])
    ctx = {"source": "ESPN site + core APIs", "captured": datetime.now().isoformat(timespec="minutes"),
           "rosters": rosters(), "injuries": injuries(),
           "drafts": {str(start - 1): draft(start - 1), str(start): draft(start)}}
    path = os.path.join(ROOT, "data", "win_totals", f"espn_context_{args.season}.json")
    json.dump(ctx, open(path, "w"), indent=1)
    print(path, {k: len(v) for k, v in ctx.items() if isinstance(v, (list, dict))},
          "players", sum(len(v) for v in ctx["rosters"].values()))


if __name__ == "__main__":
    main()

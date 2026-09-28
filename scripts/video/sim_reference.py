#!/usr/bin/env python3
"""Sourced facts for the sim video and card back: park dimensions and lineups.

Everything here comes from the MLB Stats API and is cached as a dated snapshot
under data/reference/ with its source URL. Nothing is typed from memory; a
missing key fails loudly instead of falling back to a guess.

  python3 scripts/video/sim_reference.py --pick-id 2026-09-26-mlb-TB-PHI-ml   # warm both caches
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from render_cards_v2 import REPO  # noqa: E402

REF = os.path.join(REPO, "data", "reference")
TEAMS_SNAPSHOT = os.path.join(REF, "mlb_teams_2026.json")
VENUES_CACHE = os.path.join(REF, "mlb_venues_fieldinfo_2026.json")
LINEUP_DIR = os.path.join(REF, "mlb_lineups")

VENUE_URL = "https://statsapi.mlb.com/api/v1/venues/{venue_id}?hydrate=location,fieldInfo"
SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date}&hydrate=lineups,probablePitcher"
BOXSCORE_URL = "https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"

FENCE_KEYS = ("leftLine", "left", "leftCenter", "center", "rightCenter", "right", "rightLine")


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "morellosims-video/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def teams():
    snap = json.load(open(TEAMS_SNAPSHOT))
    return snap["teams"]


def team(abbr):
    t = teams().get(abbr)
    if not t:
        raise SystemExit(f"{abbr} not in {TEAMS_SNAPSHOT}; refresh the snapshot")
    return t


# ── park dimensions ────────────────────────────────────────────────────────

def _fetch_venue(venue_id):
    url = VENUE_URL.format(venue_id=venue_id)
    v = _get(url)["venues"][0]
    fi = v.get("fieldInfo") or {}
    # Some parks publish a partial set (e.g. no left/right alley). Keep what
    # the API gives and record the gap; drawing code needs at least the two
    # foul lines and center, and never invents the others.
    missing = [k for k in FENCE_KEYS if k not in fi]
    loc = v.get("location") or {}
    return {
        "id": v["id"], "name": v["name"], "source": url,
        "city": loc.get("city"), "state": loc.get("stateAbbrev"),
        "azimuthAngle": loc.get("azimuthAngle"),
        "fieldInfo": {k: fi[k] for k in FENCE_KEYS + ("turfType", "roofType", "capacity") if k in fi},
        "missing": missing,
    }


def venues(refresh=False):
    """All 30 home parks' fence distances, cached as one dated snapshot."""
    if os.path.exists(VENUES_CACHE) and not refresh:
        return json.load(open(VENUES_CACHE))["venues"]
    out = {}
    for abbr, t in sorted(teams().items()):
        vid = t.get("venue_id")
        if vid is None:
            raise SystemExit(f"{abbr} has no venue_id in {TEAMS_SNAPSHOT}")
        out[str(vid)] = _fetch_venue(vid)
    snap = {"_source": VENUE_URL, "_fetched": date.today().isoformat(),
            "_venue_ids_from": "data/reference/mlb_teams_2026.json", "venues": out}
    os.makedirs(REF, exist_ok=True)
    json.dump(snap, open(VENUES_CACHE, "w"), indent=1, ensure_ascii=False)
    return out


def venue_for_team(abbr):
    vid = str(team(abbr)["venue_id"])
    v = venues().get(vid)
    if not v:
        raise SystemExit(f"venue {vid} ({abbr}) not in {VENUES_CACHE}; refresh it (--refresh)")
    return v


# ── lineups ────────────────────────────────────────────────────────────────

def lineups(pick, refresh=False):
    """Starting lineups (batting order, position, name) and starting pitchers.

    Schedule `hydrate=lineups` gives the posted order pre-game; the boxscore
    adds positions. Starters are the boxscore rows whose battingOrder ends in
    00 (x01+ are substitutes). The two sources must agree on names."""
    pk = pick.get("game_pk")
    if not pk:
        raise SystemExit(f"{pick['id']} has no game_pk; cannot source lineups")
    path = os.path.join(LINEUP_DIR, f"{pick['date']}_{pk}.json")
    if os.path.exists(path) and not refresh:
        return json.load(open(path))

    s_url = SCHEDULE_URL.format(date=pick["date"])
    sched = _get(s_url)
    game = next((g for d in sched.get("dates", []) for g in d["games"] if g["gamePk"] == pk), None)
    if not game:
        raise SystemExit(f"gamePk {pk} not on the {pick['date']} schedule ({s_url})")
    posted = game.get("lineups") or {}
    if not posted.get("awayPlayers") or not posted.get("homePlayers"):
        raise SystemExit(f"lineups not posted yet for {pk} ({s_url})")

    b_url = BOXSCORE_URL.format(game_pk=pk)
    box = _get(b_url)
    out = {"_source": [s_url, b_url], "_fetched": date.today().isoformat(),
           "game_pk": pk, "date": pick["date"], "venue": game["venue"]}
    for side, key in (("away", "awayPlayers"), ("home", "homePlayers")):
        t = box["teams"][side]
        starters = sorted((p for p in t["players"].values() if str(p.get("battingOrder", "")).endswith("00")),
                          key=lambda p: int(p["battingOrder"]))
        by_id = {p["person"]["id"]: p for p in starters}
        rows = []
        for i, pp in enumerate(posted[key], 1):
            bp = by_id.get(pp["id"])
            pos = ((bp.get("allPositions") or [bp.get("position")])[0]["abbreviation"] if bp
                   else (pp.get("primaryPosition") or {}).get("abbreviation"))
            rows.append({"order": i, "id": pp["id"], "name": pp["fullName"], "pos": pos})
        if starters and [p["person"]["id"] for p in starters] != [r["id"] for r in rows]:
            raise SystemExit(f"{side} lineup mismatch between schedule and boxscore for {pk}")
        prob = (game["teams"][side].get("probablePitcher") or {})
        out[side] = {"abbr": t["team"]["abbreviation"], "team": t["team"]["name"], "lineup": rows,
                     "sp": {"id": prob.get("id"), "name": prob.get("fullName")}}
    os.makedirs(LINEUP_DIR, exist_ok=True)
    json.dump(out, open(path, "w"), indent=1, ensure_ascii=False)
    return out


if __name__ == "__main__":
    from render_series_card import load_picks
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick-id", required=True)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    pick = next((p for p in load_picks() if p["id"] == a.pick_id), None)
    if not pick:
        raise SystemExit(f"pick id not found: {a.pick_id}")
    if a.refresh:
        venues(refresh=True)
    print(json.dumps(venue_for_team(pick["home"]), indent=1))
    print(json.dumps(lineups(pick, a.refresh), indent=1, ensure_ascii=False)[:1500])

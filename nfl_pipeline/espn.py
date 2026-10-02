#!/usr/bin/env python3
"""ESPN public NFL API: this week's games / odds, and open-close lines.

Sign convention everywhere in nfl_pipeline: a spread is stated the nflverse
way, from the HOME side as "points the home team is favored by" (home -3.5
→ +3.5; home +2.5 underdog → -2.5). ESPN's homeTeamOdds.pointSpread is the
bettor's line for the home team (+4.5 = home gets 4.5), so
home_favored_by = -pointSpread.

  python3 nfl_pipeline/espn.py lines --seasons 2024,2025,2026   # open/close table
  python3 nfl_pipeline/espn.py week                             # print this week's board
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import ESPN_CORE, ESPN_LINES_CSV, ESPN_SITE, SCHEDULES_CSV  # noqa: E402
import sources  # noqa: E402

# Provider preference for open/close (ids from ESPN's odds feed):
#   58 ESPN BET (2023-2025), 100 DraftKings (2026 scoreboard default),
#   40 DraftKings (older id), 31 Caesars. "Live Odds" feeds are skipped.
PROVIDER_PREF = ["100", "58", "40", "31", "47"]
LINE_FIELDS = ["game_id", "espn", "provider_id", "provider", "open_home_fav", "close_home_fav",
               "open_total", "close_total", "fetched_at"]


def _num(v):
    try:
        return float(str(v).replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def _side_spread(o, which):
    h = (o.get("homeTeamOdds") or {}).get(which) or {}
    ps = h.get("pointSpread") or {}
    v = ps.get("american") if isinstance(ps, dict) else None
    v = _num(v)
    return None if v is None else -v


def _total(o, which):
    t = ((o.get(which) or {}).get("total") or {})
    return _num(t.get("american") if isinstance(t, dict) else None)


def event_lines(event_id):
    """(provider_id, provider, open_home_fav, close_home_fav, open_total, close_total) or None."""
    data = sources.get_json(f"{ESPN_CORE}/events/{event_id}/competitions/{event_id}/odds")
    items = [i for i in data.get("items", []) if "Live" not in ((i.get("provider") or {}).get("name") or "")]
    best = None
    for it in items:
        pid = str((it.get("provider") or {}).get("id"))
        op, cl = _side_spread(it, "open"), _side_spread(it, "close")
        if op is None or cl is None:
            continue
        rank = PROVIDER_PREF.index(pid) if pid in PROVIDER_PREF else len(PROVIDER_PREF)
        cand = (rank, pid, it["provider"].get("name"), op, cl, _total(it, "open"), _total(it, "close"))
        if best is None or cand[0] < best[0]:
            best = cand
    return best[1:] if best else None


def collect_lines(seasons, only_final=True):
    import pandas as pd
    s = pd.read_csv(SCHEDULES_CSV)
    s = s[s["season"].isin(seasons) & s["espn"].notna()]
    if only_final:
        s = s[s["result"].notna()]
    have = {}
    if os.path.exists(ESPN_LINES_CSV):
        with open(ESPN_LINES_CSV) as f:
            have = {r["game_id"]: r for r in csv.DictReader(f)}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n_new = 0
    for _, g in s.iterrows():
        if g["game_id"] in have and have[g["game_id"]].get("close_home_fav"):
            continue
        try:
            res = event_lines(int(g["espn"]))
        except Exception as e:
            print(f"  WARN {g['game_id']}: {e}")
            continue
        time.sleep(0.15)
        if not res:
            have[g["game_id"]] = {"game_id": g["game_id"], "espn": int(g["espn"]), "fetched_at": now}
            continue
        pid, pname, op, cl, ot, ct = res
        have[g["game_id"]] = {"game_id": g["game_id"], "espn": int(g["espn"]), "provider_id": pid,
                              "provider": pname, "open_home_fav": op, "close_home_fav": cl,
                              "open_total": ot, "close_total": ct, "fetched_at": now}
        n_new += 1
    rows = sorted(have.values(), key=lambda r: r["game_id"])
    with open(ESPN_LINES_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LINE_FIELDS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in LINE_FIELDS})
    print(f"espn lines: {n_new} new, {len(rows)} total → {ESPN_LINES_CSV}")


def week_board(dates=None):
    """This week's games from the ESPN scoreboard: id, kickoff (UTC), teams,
    status, neutral flag, venue, current spread (home-favored convention)."""
    url = f"{ESPN_SITE}/scoreboard" + (f"?dates={dates}" if dates else "")
    sb = sources.get_json(url)
    out = []
    for e in sb.get("events", []):
        c = e["competitions"][0]
        teams = {t["homeAway"]: t for t in c["competitors"]}
        odds = (c.get("odds") or [{}])[0]
        spread = None
        h_odds = odds.get("homeTeamOdds") or {}
        a_odds = odds.get("awayTeamOdds") or {}
        if odds.get("spread") is not None:
            sp = _num(odds.get("spread"))
            # scoreboard "spread" is the favorite's magnitude; favorite flags tell the side
            if sp is not None:
                if h_odds.get("favorite"):
                    spread = abs(sp)
                elif a_odds.get("favorite"):
                    spread = -abs(sp)
                else:
                    spread = 0.0 if sp == 0 else None
        out.append({
            "espn": e["id"], "kickoff_utc": e["date"], "name": e.get("name"),
            "season": (sb.get("season") or {}).get("year"), "season_type": (sb.get("season") or {}).get("type"),
            "week": (sb.get("week") or {}).get("number"),
            "home": teams["home"]["team"]["abbreviation"], "away": teams["away"]["team"]["abbreviation"],
            "home_score": teams["home"].get("score"), "away_score": teams["away"].get("score"),
            "status": c["status"]["type"]["name"], "completed": bool(c["status"]["type"].get("completed")),
            "neutral": bool(c.get("neutralSite")), "venue": (c.get("venue") or {}).get("fullName"),
            "spread_home_fav": spread, "spread_details": odds.get("details"),
            "total": _num(odds.get("overUnder")), "provider": (odds.get("provider") or {}).get("name"),
        })
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["lines", "week"])
    ap.add_argument("--seasons", default="2024,2025,2026")
    ap.add_argument("--dates", default="")
    a = ap.parse_args()
    if a.cmd == "lines":
        collect_lines([int(x) for x in a.seasons.split(",")])
    else:
        for g in week_board(a.dates or None):
            print(g)

#!/usr/bin/env python3
"""The data side: /nbasim/ — tonight's slate and a report for every game.

Writes nbasim/slate.json (data) and nbasim/index.html (template). Public and
free, so it follows one rule: the sim's number IS the pick, so a game's sim
line and total are written ONLY once that game has tipped. Before tip the
report shows the book's line, both teams' ratings and rotations, and "sealed".

Sources:
  ESPN scoreboard            schedule, tip times, venue, book line, scores
  nba_pipeline/db/nba_sim.db team ratings (team_season_stats), player
                             ratings + minutes (latest mojo_snapshots)
  nba_pipeline/data/daily_picks.json  the sim's spread/total (after tip only)
  picks/nba.json             published picks (after tip only, via picks_store)

  python3 scripts/build_data_page.py [--date YYYY-MM-DD]
"""

import argparse
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "nba_pipeline"))
sys.path.insert(0, HERE)
from utils.constants import ESPN_ABBR_MAP  # noqa: E402

ET = timezone(timedelta(hours=-4))
SEASON_START = date(2026, 10, 20)          # 2026-27 opening night (ESPN schedule)
OUT = os.path.join(REPO, "nbasim")
DB = os.path.join(REPO, "nba_pipeline", "db", "nba_sim.db")
TEAMS_REF = json.load(open(os.path.join(REPO, "data", "reference", "nba_teams_espn_2026.json")))["teams"]
NBA = lambda a: ESPN_ABBR_MAP.get(a, a)   # noqa: E731
REF = {NBA(k): v for k, v in TEAMS_REF.items()}


def scoreboard(d):
    u = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={d:%Y%m%d}"
    try:
        events = json.loads(urllib.request.urlopen(u, timeout=20).read()).get("events", [])
    except Exception as e:  # noqa: BLE001
        print(f"ESPN scoreboard {d}: {e}")
        return []
    games = []
    for e in events:
        if (e.get("season") or {}).get("type") not in (None, 2, 3):   # regular season + playoffs only
            continue
        c = e["competitions"][0]
        t = {x["homeAway"]: x for x in c["competitors"]}
        odds = (c.get("odds") or [{}])[0]
        st = c["status"]["type"]
        games.append({
            "away": NBA(t["away"]["team"]["abbreviation"]), "home": NBA(t["home"]["team"]["abbreviation"]),
            "tip": e["date"], "venue": (c.get("venue") or {}).get("fullName", ""),
            # ESPN writes "NY -5.5"; use the NBA codes the rest of the site uses
            "line": " ".join([NBA(odds["details"].split()[0])] + odds["details"].split()[1:]) if odds.get("details") else None,
            "total": odds.get("overUnder"),
            "state": st.get("state", "pre"), "detail": st.get("shortDetail", ""),
            "away_score": t["away"].get("score"), "home_score": t["home"].get("score"),
        })
    return sorted(games, key=lambda g: g["tip"])


def pick_slate(forced=None):
    if forced:
        d = date.fromisoformat(forced)
        return d, scoreboard(d)
    today = datetime.now(ET).date()
    start = max(today, SEASON_START)
    for k in range(8):
        d = start + timedelta(days=k)
        g = scoreboard(d)
        if g:
            return d, g
    return start, []


def teams_block(abbrs):
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    snap = c.execute("SELECT MAX(snapshot_date) FROM mojo_snapshots").fetchone()[0]
    out = {}
    for ab in abbrs:
        r = c.execute("SELECT team_id, full_name FROM teams WHERE abbreviation=?", (ab,)).fetchone()
        if not r:
            continue
        ts = c.execute("""SELECT gp, pace, off_rating, def_rating, net_rating, fg3a_rate, tov_pct
                          FROM team_season_stats WHERE team_id=? ORDER BY season_id DESC LIMIT 1""", (r["team_id"],)).fetchone()
        ps = c.execute("""SELECT p.full_name AS name, ROUND(m.mojo_score) AS rating, ROUND(m.minutes_per_game, 1) AS mpg
                          FROM mojo_snapshots m JOIN players p USING (player_id)
                          WHERE m.team_id=? AND m.snapshot_date=? ORDER BY m.minutes_per_game DESC LIMIT 5""",
                       (r["team_id"], snap)).fetchall()
        out[ab] = {"name": r["full_name"], "nick": REF.get(ab, {}).get("name", ab),
                   "stats": dict(ts) if ts else None, "players": [dict(p) for p in ps]}
    return snap, out


def sims_after_tip(slate_day, games):
    """The sim's numbers for games that have tipped. Nothing for games that haven't."""
    path = os.path.join(REPO, "nba_pipeline", "data", "daily_picks.json")
    try:
        dp = json.load(open(path))
    except (OSError, ValueError):
        return {}, {}
    if dp.get("slate_date_iso") != slate_day.isoformat():
        return {}, {}
    now = datetime.now(timezone.utc)
    tipped = {(g["away"], g["home"]) for g in games
              if datetime.fromisoformat(g["tip"].replace("Z", "+00:00")) <= now or g["state"] != "pre"}
    sims = {}
    for g in dp.get("games", []):
        key = tuple(x.strip() for x in g["matchup"].split("@"))
        if key in tipped and g.get("sim_spread") is not None:
            sims[key] = {"spread_home": g["sim_spread"], "total": g.get("sim_total")}
    picks = {}
    try:
        import picks_store
        for p in picks_store.load_picks("nba"):
            key = (p["away"], p["home"])
            if p["date"] == slate_day.isoformat() and key in tipped:
                picks[key] = {"text": p["pick_text"], "status": p.get("status")}
    except Exception as e:  # noqa: BLE001
        print(f"picks: {e}")
    return sims, picks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    a = ap.parse_args()
    d, games = pick_slate(a.date)
    snap, teams = teams_block(sorted({x for g in games for x in (g["away"], g["home"])}))
    sims, picks = sims_after_tip(d, games)
    for g in games:
        k = (g["away"], g["home"])
        g["sim"] = sims.get(k)
        g["pick"] = picks.get(k)
    title = "Opening night" if d == SEASON_START else ("Tonight" if d == datetime.now(ET).date() else f"{d:%A}")
    data = {
        "generated": datetime.now(ET).strftime("%Y-%m-%d %H:%M ET"),
        "date": d.isoformat(), "title": title,
        # until the new season has a few weeks of games, the team table is last season's
        "ratings_label": "last season" if datetime.now(ET).date() < SEASON_START + timedelta(days=21) else "this season",
        "snap": snap, "games": games, "teams": teams,
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "slate.json"), "w") as f:
        json.dump(data, f, separators=(",", ":"))
    with open(os.path.join(HERE, "templates", "data_page.html")) as f:
        tpl = f.read()
    with open(os.path.join(OUT, "index.html"), "w") as f:
        f.write(tpl)
    sealed = sum(1 for g in games if not g["sim"])
    print(f"nbasim: {d} {title} · {len(games)} games · {sealed} sealed · ratings {snap}")


if __name__ == "__main__":
    main()

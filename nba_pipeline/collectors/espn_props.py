"""Tonight's NBA player-prop lines from ESPN's public odds API (DraftKings): the
over/under markets on points, rebounds, assists, threes and their combos, each
with its opening and current line and prices.

  cd nba_pipeline && python3 -m collectors.espn_props --out data/props/2026-27.csv [--date YYYY-MM-DD]

ESPN keeps prop lines only while a game is upcoming, so this runs every pipeline
pass: the first sighting of a (game, player, market) keeps its morning line and
the latest keeps the last line before tip (the close). In each over/under pair
DraftKings lists the over first (checked against its milestone prices).
"""

import argparse
import csv
import datetime as dt
import os
import sqlite3
import sys
import time
from collections import defaultdict

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH  # noqa: E402

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
PROPS = ("https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/{e}/competitions/{e}"
         "/odds/100/propBets")
MARKETS = {"Total Points": "pts", "Total Rebounds": "reb", "Total Assists": "ast",
           "Total 3-Point Field Goals": "fg3m", "Total Points and Rebounds": "pr",
           "Total Points and Assists": "pa", "Total Assists and Rebounds": "ra",
           "Total Points, Rebounds, and Assists": "pra"}
FIELDS = ["date", "event_id", "matchup", "tip_utc", "espn_id", "player_id", "player", "market",
          "line_open", "over_open", "under_open", "line_am", "over_am", "under_am", "seen_am",
          "line_last", "over_last", "under_last", "seen_last"]


def _num(x):
    try:
        return float(str(x).replace("+", ""))
    except (TypeError, ValueError):
        return None


def events(session, date):
    data = session.get(SCOREBOARD, params={"dates": date.replace("-", "")}, timeout=20).json()
    out = []
    for ev in data.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        if comp.get("status", {}).get("type", {}).get("state") != "pre":
            continue
        teams = {c.get("homeAway"): c["team"]["abbreviation"] for c in comp.get("competitors", [])}
        out.append((ev["id"], f"{teams.get('away')} @ {teams.get('home')}", ev.get("date")))
    return out


def props(session, eid):
    """{(espn_id, market): (line_open, over_open, under_open, line_now, over_now, under_now)}."""
    items, page = [], 1
    while True:
        r = session.get(PROPS.format(e=eid), params={"limit": 1000, "page": page}, timeout=30)
        if r.status_code != 200:
            break
        d = r.json()
        items += d.get("items", [])
        if page >= d.get("pageCount", 1):
            break
        page += 1
    pairs = defaultdict(list)
    for it in items:
        m = MARKETS.get((it.get("type") or {}).get("name"))
        ref = (it.get("athlete") or {}).get("$ref", "")
        if not m or "/athletes/" not in ref:
            continue
        pairs[(ref.split("/athletes/")[1].split("?")[0], m)].append(it)
    out = {}
    for k, its in pairs.items():
        if len(its) != 2:
            continue
        over, under = its                      # DraftKings: the over first
        o, u = over.get("odds") or {}, under.get("odds") or {}
        out[k] = ((over.get("open") or {}).get("target", {}).get("value"),
                  _num((o.get("american") or {}).get("open")), _num((u.get("american") or {}).get("open")),
                  (over.get("current") or {}).get("target", {}).get("value"),
                  _num((o.get("american") or {}).get("value")), _num((u.get("american") or {}).get("value")))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--date", default=dt.datetime.now(dt.timezone(dt.timedelta(hours=-4))).strftime("%Y-%m-%d"))
    args = ap.parse_args()
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    emap = {str(e): int(p) for e, p in con.execute("SELECT espn_id, player_id FROM espn_player_map")}
    names = dict(con.execute("SELECT player_id, full_name FROM players"))
    rows = {}
    if os.path.exists(args.out):
        for r in csv.DictReader(open(args.out)):
            rows[(r["event_id"], r["espn_id"], r["market"])] = r
    s = requests.Session()
    s.headers["User-Agent"] = "morellosims-research/1.0"
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n_new = n_upd = 0
    for eid, matchup, tip in events(s, args.date):
        for (aid, m), (lo, oo, uo, ln, on, un) in props(s, eid).items():
            if ln is None:
                continue
            k = (eid, aid, m)
            pid = emap.get(aid)
            r = rows.get(k)
            if r is None:
                r = {"date": args.date, "event_id": eid, "matchup": matchup, "tip_utc": tip, "espn_id": aid,
                     "player_id": pid or "", "player": names.get(pid, ""), "market": m,
                     "line_open": lo, "over_open": oo, "under_open": uo,
                     "line_am": ln, "over_am": on, "under_am": un, "seen_am": now}
                rows[k] = r
                n_new += 1
            else:
                n_upd += 1
            r.update(line_last=ln, over_last=on, under_last=un, seen_last=now)
        time.sleep(0.3)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in sorted(rows.values(), key=lambda r: (r["date"], r["event_id"], r["player"], r["market"])):
            w.writerow({k: r.get(k, "") for k in FIELDS})
    print(f"props {args.date}: {n_new} new, {n_upd} updated, {len(rows)} in {args.out}")


if __name__ == "__main__":
    main()

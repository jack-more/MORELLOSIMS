"""Opening and closing NBA odds from ESPN's public odds API (the pregame book it
carried: ESPN BET early in 2025-26, DraftKings after): moneyline, spread and total,
each with its price, for every game of a season.

  cd nba_pipeline && python3 -m collectors.espn_odds --season 2025-26 --out data/odds_2025-26.csv
  cd nba_pipeline && python3 -m collectors.espn_odds --season 2024-25 --out data/odds_2024-25.csv

Events come from the ESPN scoreboard, one request per date; then one odds request
per game (live in-game providers skipped). Resumable: games already in --out are skipped. Polite: about 4 requests a second.
"""

import argparse
import csv
import datetime as dt
import os
import time

import requests

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
ODDS = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/{e}/competitions/{e}/odds"
SEASONS = {"2024-25": ("2024-10-22", "2025-06-22"), "2025-26": ("2025-10-21", "2026-06-20"),
           "2026-27": ("2026-10-20", "2027-06-20")}
FIELDS = ["date", "event_id", "season_type", "home", "away", "home_score", "away_score", "provider",
          "ml_home_open", "ml_away_open", "ml_home_close", "ml_away_close",
          "spread_home_open", "spread_home_open_odds", "spread_away_open_odds",
          "spread_home_close", "spread_home_close_odds", "spread_away_close_odds",
          "total_open", "over_open_odds", "under_open_odds", "total_close", "over_close_odds", "under_close_odds"]
PAUSE = 0.25


def _get(session, url, params, tries=4):
    for k in range(tries):
        try:
            r = session.get(url, params=params, timeout=20)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** (k + 1))
                continue
            return None
        except (requests.RequestException, ValueError):
            time.sleep(2 ** (k + 1))
    return None


def events(session, start, end):
    """[(date, event_id, season_type, home, away, home_score, away_score)] of finished games."""
    out = []
    d = dt.date.fromisoformat(start)
    while d <= min(dt.date.fromisoformat(end), dt.date.today()):
        data = _get(session, SCOREBOARD, {"dates": d.strftime("%Y%m%d"), "limit": 50}) or {}
        for ev in data.get("events", []):
            comp = (ev.get("competitions") or [{}])[0]
            if not comp.get("status", {}).get("type", {}).get("completed"):
                continue
            teams = {c.get("homeAway"): c for c in comp.get("competitors", [])}
            if "home" not in teams or "away" not in teams:
                continue
            out.append((d.isoformat(), ev["id"], ev.get("season", {}).get("type"),
                        teams["home"]["team"]["abbreviation"], teams["away"]["team"]["abbreviation"],
                        teams["home"].get("score"), teams["away"].get("score")))
        d += dt.timedelta(days=1)
        time.sleep(PAUSE)
    return out


def _num(x):
    if x in (None, "", "OFF", "EVEN"):
        return 100.0 if x == "EVEN" else None
    try:
        return float(str(x).lstrip("ou").replace("+", ""))
    except ValueError:
        return None


def odds(data):
    """The pregame book's open and close (the first provider that isn't live odds)."""
    items = [it for it in (data or {}).get("items") or []
             if "live" not in str((it.get("provider") or {}).get("name", "")).lower()]
    if not items:
        return None
    it = sorted(items, key=lambda x: (x.get("provider") or {}).get("priority", 99))[0]
    h, a = it.get("homeTeamOdds") or {}, it.get("awayTeamOdds") or {}
    am = lambda blk, when, key, field="american": _num(((blk.get(when) or {}).get(key) or {}).get(field))
    return {
        "provider": (it.get("provider") or {}).get("name"),
        "ml_home_open": am(h, "open", "moneyLine"), "ml_away_open": am(a, "open", "moneyLine"),
        "ml_home_close": am(h, "close", "moneyLine") or _num(h.get("moneyLine")),
        "ml_away_close": am(a, "close", "moneyLine") or _num(a.get("moneyLine")),
        "spread_home_open": am(h, "open", "pointSpread"), "spread_home_open_odds": am(h, "open", "spread"),
        "spread_away_open_odds": am(a, "open", "spread"),
        "spread_home_close": am(h, "close", "pointSpread") if am(h, "close", "pointSpread") is not None else _num(it.get("spread")),
        "spread_home_close_odds": am(h, "close", "spread"), "spread_away_close_odds": am(a, "close", "spread"),
        "total_open": am(it, "open", "total", "alternateDisplayValue"), "over_open_odds": am(it, "open", "over"),
        "under_open_odds": am(it, "open", "under"),
        "total_close": am(it, "close", "total", "alternateDisplayValue") or _num(it.get("overUnder")),
        "over_close_odds": am(it, "close", "over"), "under_close_odds": am(it, "close", "under"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", required=True, choices=sorted(SEASONS))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    have = set()
    if os.path.exists(args.out):
        have = {r["event_id"] for r in csv.DictReader(open(args.out))}
    s = requests.Session()
    s.headers["User-Agent"] = "morellosims-research/1.0"
    evs = events(s, *SEASONS[args.season])
    print(f"{args.season}: {len(evs)} finished games, {len(have)} already saved", flush=True)
    new = not os.path.exists(args.out)
    with open(args.out, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        missing = 0
        for i, (d, eid, st, home, away, hs, as_) in enumerate(evs):
            if eid in have:
                continue
            o = odds(_get(s, ODDS.format(e=eid), {"limit": 10}))
            time.sleep(PAUSE)
            if o is None:
                missing += 1
                o = {}
            w.writerow({"date": d, "event_id": eid, "season_type": st, "home": home, "away": away,
                        "home_score": hs, "away_score": as_, **o})
            if i % 100 == 0:
                f.flush()
                print(f"  {i}/{len(evs)} ({missing} without odds)", flush=True)
    print(f"done: {args.out} ({missing} games without odds)")


if __name__ == "__main__":
    main()

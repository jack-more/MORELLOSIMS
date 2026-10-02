#!/usr/bin/env python3
"""NBA season ledger page: every itemized pick, in units, clickable by day.

Writes ledger/nba/2025-26.json (data) and ledger/nba/index.html (page):
  - season stats in units (1u = 50 $PP, the standard stake)
  - running-units chart; tap a point to open that day
  - calendar heat map; tap a day to see every pick with its units, the
    final score, the sim's line vs the book's, and when it was logged
Only SETTLED picks are published (seal-safe: a pick appears here after its
game is final). Rows the owner reinstated after a late log keep a visible
"logged late" tag — the ledger hides nothing.

  python3 scripts/build_nba_ledger_page.py
"""

import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "nba_pipeline"))
from utils.constants import ESPN_ABBR_MAP  # noqa: E402

UNIT = 50.0                       # $PP per unit (standard stake)

def season_of(d):
    """NBA season label for a game date: Oct-Dec → that year's season."""
    y, m = int(d[:4]), int(d[5:7])
    start = y if m >= 10 else y - 1
    return f"{start}-{str(start + 1)[2:]}"
ET = timezone(timedelta(hours=-4))
OUT_DIR = os.path.join(REPO, "ledger", "nba")
NBA_TO_ESPN = {v: k for k, v in ESPN_ABBR_MAP.items()}


def _log_index():
    idx = {}
    path = os.path.join(REPO, "nba_pipeline", "data", "pick_log.json")
    for p in json.load(open(path)) if os.path.exists(path) else []:
        sd = p.get("slate_date", "")
        try:
            d = sd[:10] if sd[:1].isdigit() else datetime.strptime(
                f"{sd} {p.get('captured_at', '')[:4]}", "%b %d %Y").strftime("%Y-%m-%d")
        except ValueError:
            continue
        idx[(d, p["matchup"].strip(), p["side"].strip())] = p
    return idx


def _et(ts):
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(ET).strftime("%-I:%M %p ET")
    except (TypeError, ValueError):
        return None


def build():
    teams = json.load(open(os.path.join(REPO, "data", "reference", "nba_teams_espn_2026.json")))["teams"]
    colors = {}
    for espn, t in teams.items():
        nba = ESPN_ABBR_MAP.get(espn, espn)
        colors[nba] = {"c": t["color"], "name": t["name"]}
    logs = _log_index()
    rows = []
    for r in csv.DictReader(open(os.path.join(REPO, "nba_pipeline", "data", "picks.csv"))):
        if r["result"] not in ("W", "L", "P"):
            continue                                   # pending/void never published here
        away, home = [x.strip() for x in r["matchup"].split("@")]
        lg = logs.get((r["date"], r["matchup"].strip(), r["side"].strip()), {})
        risk = float(r["risk"] or 0)
        profit = float(r["profit"] or 0)
        try:
            final = f"{away} {int(float(r['away_score']))} – {home} {int(float(r['home_score']))}"
        except (TypeError, ValueError):
            final = ""
        rows.append({
            "date": r["date"], "away": away, "home": home,
            "pick": r["side"], "type": r["type"],
            "odds": r.get("odds") or ("-110" if r["type"] == "spread" else ""),
            "result": r["result"], "stake_u": round(risk / UNIT, 2), "units": round(profit / UNIT, 2),
            "final": final, "logged": _et(r.get("captured_at")),
            "late": (r.get("void_reason") or "").startswith("REINSTATED"),
            "conf": lg.get("conf_1_10"),
            # sim margin for the picked side = edge - line (verified on every
            # logged pick: NYK +5.0 with 6.0 edge -> sim NYK by 1.0)
            "edge": lg.get("spread_edge"),
            "sim_margin": (round(float(lg["spread_edge"]) - float(lg["line_value"]), 1)
                           if r["type"] == "spread" and lg.get("spread_edge") is not None
                           and lg.get("line_value") is not None else None),
        })
    rows.sort(key=lambda x: (x["date"], x["away"]))
    os.makedirs(OUT_DIR, exist_ok=True)
    seasons = sorted({season_of(r["date"]) for r in rows})
    for season in seasons:
        rs = [r for r in rows if season_of(r["date"]) == season]
        w = sum(x["result"] == "W" for x in rs)
        l = sum(x["result"] == "L" for x in rs)
        p = sum(x["result"] == "P" for x in rs)
        risked = sum(x["stake_u"] for x in rs if x["result"] != "P")
        units = sum(x["units"] for x in rs)
        data = {
            "season": season, "unit_pp": UNIT,
            "generated": datetime.now(ET).strftime("%Y-%m-%d %H:%M ET"),
            "summary": {"w": w, "l": l, "p": p, "units": round(units, 2), "risked_u": round(risked, 2),
                        "roi": round(100 * units / risked, 1) if risked else 0, "picks": len(rs),
                        "first": rs[0]["date"], "last": rs[-1]["date"]},
            "teams": colors, "picks": rs,
        }
        with open(os.path.join(OUT_DIR, f"{season}.json"), "w") as f:
            json.dump(data, f, separators=(",", ":"))
        print(f"ledger/nba/{season}: {len(rs)} picks, {w}-{l}-{p}, {units:+.1f}u on {risked:.1f}u")
    with open(os.path.join(OUT_DIR, "seasons.json"), "w") as f:
        json.dump(seasons, f)
    tpl = open(os.path.join(HERE, "templates", "nba_ledger.html")).read()
    with open(os.path.join(OUT_DIR, "index.html"), "w") as f:
        f.write(tpl.replace("__SEASON__", seasons[-1] if seasons else ""))


if __name__ == "__main__":
    build()

#!/usr/bin/env python3
"""Score-order guardrail. picks/nba.json stores result HOME-AWAY; MLB stores
AWAY-HOME. On 2026-10-02 an NBA card printed "NYK 90 – SAS 94" for a game the
Knicks won 94-90. This checks every settled NBA pick's labeled final (as the
slip caption builds it) against picks.csv's explicit home/away columns."""
import csv, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import slips  # noqa: E402

csv_rows = {(r["date"], r["matchup"].strip()): r for r in csv.DictReader(open(os.path.join(REPO, "nba_pipeline", "data", "picks.csv")))}
bad = 0
for p in json.load(open(os.path.join(REPO, "picks", "nba.json"))):
    if p.get("status") not in ("win", "loss", "push") or not p.get("result"):
        continue
    r = csv_rows.get((p["date"], p["matchup"]))
    if not r or not r.get("home_score"):
        continue
    want = f"{p['away']} {int(float(r['away_score']))} – {p['home']} {int(float(r['home_score']))}"
    got = slips._caption(dict(p, sport="nba")).splitlines()[0]
    if want not in got:
        bad += 1
        print(f"FAIL {p['id']}: expected '{want}' in '{got}'")
print("score order OK" if not bad else f"{bad} score-order failures")
sys.exit(1 if bad else 0)

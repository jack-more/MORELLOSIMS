#!/usr/bin/env python3
"""One-time ledger repair (2026-10-02): April 2026 NBA picks.

MORELLOSIMS's nba_pipeline/data/picks.csv was copied from the original
jack-more/nbasim ledger around Apr 1, so nearly all of April never reached
it (the owner asked "why is april empty"). The nbasim repo's data/picks.csv
holds them, and its data/pick_log.json holds the capture record for each.

For every nbasim row whose GAME is not already in our ledger:
  - grade it against the ESPN final (the nbasim grades had known
    date-matching bugs), at the logged line and stake;
  - captured_at = the pick_log capture time (or, if absent, the first nbasim
    commit containing the row); tip_at = ESPN's scheduled start;
  - captured before tip -> a normal row; otherwise it is counted under the
    owner's "keep them all in" decision with the REINSTATED marker and the
    evidence spelled out (check_ledger.py accepts exactly that marker).
Nothing existing is modified or deleted.

  python3 scripts/restore_nba_april.py --nbasim /path/to/nbasim/checkout [--dry-run]
"""

import argparse
import csv
import io
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "nba_pipeline"))
from utils.ledger import compute_profit, read_rows, write_rows  # noqa: E402
from utils.constants import ESPN_ABBR_MAP  # noqa: E402

PICKS = os.path.join(REPO, "nba_pipeline", "data", "picks.csv")
_cache = {}


def espn_day(d):
    if d not in _cache:
        u = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={d.replace('-', '')}"
        s = json.loads(urllib.request.urlopen(u, timeout=20).read())
        out = {}
        for e in s.get("events", []):
            c = e["competitions"][0]
            if not c["status"]["type"]["completed"]:
                continue
            t = {x["homeAway"]: (ESPN_ABBR_MAP.get(x["team"]["abbreviation"], x["team"]["abbreviation"]), int(x["score"]))
                 for x in c["competitors"]}
            out[(t["away"][0], t["home"][0])] = (t["away"][1], t["home"][1], e["date"])
        _cache[d] = out
        time.sleep(0.12)
    return _cache[d]


def find_final(date, away, home):
    """Logged date can be a day off for late tips (UTC); try d, d+1, d-1."""
    base = datetime.strptime(date, "%Y-%m-%d")
    for delta in (0, 1, -1):
        d = (base + timedelta(days=delta)).strftime("%Y-%m-%d")
        f = espn_day(d).get((away, home))
        if f:
            return f
    return None


def git(repo, *a):
    return subprocess.check_output(["git", "-C", repo, *a], stderr=subprocess.DEVNULL).decode()


def capture_index(nbasim):
    idx = {}
    for p in json.loads(git(nbasim, "show", "HEAD:data/pick_log.json")):
        sd = str(p.get("slate_date", ""))
        try:
            d = sd[:10] if sd[:1].isdigit() else datetime.strptime(f"{sd} {p.get('captured_at', '')[:4]}", "%b %d %Y").strftime("%Y-%m-%d")
        except ValueError:
            continue
        idx[(d, p["matchup"].strip(), p["side"].strip())] = p.get("captured_at")
    return idx


def first_commit_times(nbasim):
    """(date, matchup, side) -> first nbasim commit time that contains the row."""
    first = {}
    for line in git(nbasim, "log", "--reverse", "--format=%H %cI", "--", "data/picks.csv").splitlines():
        h, ts = line.split()
        try:
            rows = csv.DictReader(io.StringIO(git(nbasim, "show", f"{h}:data/picks.csv")))
        except subprocess.CalledProcessError:
            continue
        for r in rows:
            first.setdefault((r["date"], r["matchup"].strip(), r["side"].strip()), ts)
    return first


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nbasim", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    ours = read_rows(PICKS)

    def game_key(date, matchup):
        # one pick per game: normalize ESPN codes (SA, NY, GS...) and team order
        teams = frozenset(ESPN_ABBR_MAP.get(x.strip(), x.strip()) for x in matchup.split("@"))
        return date, teams

    have_games = {game_key(r["date"], r["matchup"]) for r in ours}
    src = list(csv.DictReader(io.StringIO(git(a.nbasim, "show", "HEAD:data/picks.csv"))))
    caps = capture_index(a.nbasim)
    commits = first_commit_times(a.nbasim)

    add, skipped, unmatched = [], [], []
    for r in src:
        key = (r["date"], r["matchup"].strip(), r["side"].strip())
        if game_key(r["date"], r["matchup"]) in have_games:
            skipped.append(key)
            continue
        away, home = [x.strip() for x in r["matchup"].split("@")]
        f = find_final(r["date"], away, home)
        if not f:
            unmatched.append(key)
            continue
        a_pts, h_pts, tip = f
        side_team = r["side"].split()[0]
        side_pts, opp_pts = (a_pts, h_pts) if side_team == away else (h_pts, a_pts)
        typ = r.get("type") or "spread"
        if typ == "spread":
            margin = side_pts - opp_pts + float(r["side"].split()[-1])
            res = "W" if margin > 0 else "L" if margin < 0 else "P"
        else:
            res = "W" if side_pts > opp_pts else "L"
        odds = int(r["odds"]) if (r.get("odds") or "").lstrip("+-").isdigit() else None
        risk = float(r["risk"] or 50)
        profit = compute_profit(res, risk, odds if odds else -110)
        cap = caps.get(key) or commits.get(key)
        source = "pick_log capture" if caps.get(key) else "first nbasim commit"
        tip_dt = datetime.fromisoformat(tip.replace("Z", "+00:00"))
        cap_ok = False
        if cap:
            try:
                cap_ok = datetime.fromisoformat(cap.replace("Z", "+00:00")) < tip_dt
            except ValueError:
                cap_ok = False
        note = "" if cap_ok else (
            f"REINSTATED (owner decision 2026-09-29): restored from the jack-more/nbasim ledger 2026-10-02; "
            f"{source} {cap or 'unknown'} is not before tip {tip}")
        add.append({
            "date": r["date"], "matchup": r["matchup"].strip(), "side": r["side"].strip(), "type": typ,
            "risk": str(int(risk)), "result": res, "profit": f"{profit:.2f}", "odds": r.get("odds") or "",
            "home_score": str(h_pts), "away_score": str(a_pts), "closing_line": "", "closing_odds": "",
            "captured_at": cap if cap_ok else (cap or ""), "tip_at": tip, "void_reason": note,
        })

    w = sum(x["result"] == "W" for x in add); l = sum(x["result"] == "L" for x in add); p = sum(x["result"] == "P" for x in add)
    u = sum(float(x["profit"]) for x in add) / 50
    clean = sum(1 for x in add if not x["void_reason"])
    print(f"restore: {len(add)} rows ({w}-{l}-{p}, {u:+.1f}u); captured before tip: {clean}; tagged late: {len(add) - clean}")
    print(f"skipped (game already in ledger): {len(skipped)}; unmatched on ESPN: {len(unmatched)} {unmatched}")
    if a.dry_run:
        return
    rows = sorted(ours + add, key=lambda x: (x["date"], x["matchup"]))
    write_rows(PICKS, rows)


if __name__ == "__main__":
    main()

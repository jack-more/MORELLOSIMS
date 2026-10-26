"""Everything the sim did for a game, step by step, as JSON (for the walkthrough page).

  cd nba_pipeline && python3 -m sim.explain --games MIN@MIA,UTA@MEM --out walk.json
  cd nba_pipeline && python3 -m sim.explain --slate --out walk.json

Per game: the rotations it played (minutes, usage, efficiency, play types,
shooting gravity, impact, role WOWY changes, who is out), the possession
environment (pace, each offense against this defense), what each layer moved
the margin, the 5,000-game margin distribution against the book line, and the
projected box score.
"""

import argparse
import collections
import itertools
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import context, engine, players, run  # noqa: E402  (run sets up generate_frontend and logging)
from sim.run import MARGIN_SD, gf  # noqa: E402
from config import CURRENT_SEASON  # noqa: E402

PAIR_MIN, TRIO_MIN = 20.0, 15.0   # minutes together this season before a pair / trio is listed
_STINTS = {}

LABEL = {"PRBallHandler": "P&R handler", "Isolation": "Isolation", "Spotup": "Spot-up", "Transition": "Transition",
         "Cut": "Cut", "PRRollMan": "Roll man", "Postup": "Post-up", "Handoff": "Handoff", "OffScreen": "Off screen",
         "OffRebound": "Putback", "Misc": "Other"}
LAYER_NAME = {"lineups": "Lineup plan", "load": "Usage load", "spacing": "Spacing", "pairs": "Chemistry", "scheme": "Scheme vs play type",
              "fatigue": "Fatigue"}


def _stints(con):
    """({team_id: [(sorted five, seconds, points margin, possessions)]} this regular season,
    {2|3|5: combos that shared the floor in the seasons before (context.SEASONS)}) from ESPN
    five-man stints."""
    if not _STINTS:
        emap = {str(e): int(p) for e, p in con.execute("SELECT espn_id, player_id FROM espn_player_map")}
        q = ("SELECT l.team_id, l.e1, l.e2, l.e3, l.e4, l.e5, l.sec, l.pts, l.opp_pts, l.poss, l.opp_poss "
             "FROM espn_lineup_games l JOIN espn_team_games g ON g.game_id=l.game_id AND g.team_id=l.team_id "
             "WHERE g.season_id=? AND g.season_type=2")
        now, last = collections.defaultdict(list), {k: set() for k in (2, 3, 5)}
        for season, sink in [(CURRENT_SEASON, now)] + [(s, None) for s in context.SEASONS[1:]]:
            for tid, *es, sec, pts, opp, poss, oposs in con.execute(q, (season,)):
                five = [emap.get(str(e)) for e in es]
                if None in five:
                    continue
                five = tuple(sorted(five))
                if sink is not None:
                    sink[tid].append((five, sec or 0, (pts or 0) - (opp or 0), ((poss or 0) + (oposs or 0)) / 2))
                else:
                    for k in (2, 3, 5):
                        last[k].update(itertools.combinations(five, k) if k < 5 else [five])
        _STINTS.update(now=now, last=last)
    return _STINTS["now"], _STINTS["last"]


def _season(con, abbr, t):
    """This season's real record of every combo in tonight's rotation: ({sorted five:
    {min, net}}, {"pairs": [...], "trios": [...]}), the lists the best three and worst two
    with enough minutes together, each with the sim's own pair value where it has one."""
    tid = con.execute("SELECT team_id FROM teams WHERE abbreviation=?", (abbr,)).fetchone()
    now, last = _stints(con)
    pids = [int(p) for p in t["pids"]]
    idx, nm = {p: i for i, p in enumerate(pids)}, dict(zip(pids, t["names"]))
    short = lambda p: nm[p].split()[-1] if nm[p].split()[-1] not in ("Jr.", "II", "III") else nm[p].split()[-2]
    agg = {k: collections.defaultdict(lambda: np.zeros(3)) for k in (2, 3, 5)}
    for five, sec, diff, poss in now.get(tid[0] if tid else None, []):
        for k in (2, 3, 5):
            for cb in (itertools.combinations(five, k) if k < 5 else [five]):
                if all(p in idx for p in cb):            # every player of the combo plays tonight
                    agg[k][cb] += (sec, diff, poss)
    rec = lambda v: {"min": round(float(v[0]) / 60, 1), "net": round(float(100 * v[1] / v[2]), 1) if v[2] > 0 else 0.0}
    fives = {cb: rec(v) for cb, v in agg[5].items()}
    lists = {}
    for k, key, floor in ((2, "pairs", PAIR_MIN), (3, "trios", TRIO_MIN)):
        rows = []
        for cb, v in agg[k].items():
            r = rec(v)
            if r["min"] < floor:
                continue
            sim = round(float(t["V"][idx[cb[0]], idx[cb[1]]]), 1) if k == 2 else None
            rows.append(dict(r, who=[short(p) for p in cb], pids=list(cb), new=cb not in last[k], sim=sim))
        rows.sort(key=lambda r: -r["net"])
        best = [r for r in rows if r["net"] > 0][:3]
        worst = [r for r in rows[::-1] if r["net"] < 0 and r not in best][:2]
        lists[key] = best + worst[::-1]
    return fives, lists


def _team_detail(t, roster, info, abbr=None):
    names = dict(zip(roster.player_id.astype(int), roster.full_name))
    out_ids, _ = gf._resolve_out_ids(info, roster, "", "walkthrough")
    starters = {int(p) for p in (gf._match_player_name(n, roster) for n, _pos, st in info.get("starters", [])
                                 if st != "OUT") if p is not None}
    rows = []
    for i, pid in enumerate(t["pids"]):
        mix = t["mix"][i]
        top = [LABEL[players.TYPES[j]] for j in np.argsort(-mix)[:2]]
        role = t.get("role", {}).get(pid)
        rows.append({"name": t["names"][i], "pid": int(pid), "starter": pid in starters, "min": round(float(t["min"][i]), 1),
                     "usg": round(float(t["usg"][i]) * 100, 1),
                     "per_use": round(float((1 - t["tov"][i]) * (mix @ t["ppp"][i])), 2),
                     "plays": top, "gravity": round(float(t["g"][i]), 2),
                     "off": round(float(t["off"][i]), 1), "def": round(float(t["def"][i]), 1),
                     "role": ({"usg": round(role[0] * 100, 1), "eff": round(role[1], 2)} if role else None)})
    rows.sort(key=lambda r: (not r["starter"], -r["min"]))
    units, lineup = [], None
    fives, combos = _season(players._db(), abbr, t) if abbr else ({}, {})
    if t.get("plan"):
        p = t["plan"]
        short = lambda n: n.split()[-1] if n.split()[-1] not in ("Jr.", "II", "III") else n.split()[-2]
        last = lambda i: short(t["names"][i])
        everyone = dict(zip(roster.player_id.astype(int), roster.full_name))
        who = lambda pid: short(everyone.get(pid) or _name(pid))
        lineup = {"mix": p.get("mix", {}), "thin": p.get("thin", False)}
        for five, mins, net, imp, chem in p["units"][:6]:
            sw = p.get("swap", {}).get(five)
            units.append({"five": [last(i) for i in five], "pids": [int(t["pids"][i]) for i in five],
                          "min": round(mins, 1), "played": round(p.get("played", {}).get(five, 0.0), 1),
                          "kind": p.get("kind", {}).get(five, "new"),
                          "swap": f"{who(sw[1])} for {who(sw[0])}" if sw else None,
                          "net": round(net, 1),
                          "impact": round(imp, 1), "chem": round(chem, 1),
                          "season": fives.get(tuple(sorted(int(t["pids"][i]) for i in five))),
                          "start": five == t["plan"]["start"], "close": five == t["plan"]["close"]})
    return {"rotation": rows, "out": sorted(names.get(p, str(p)) for p in out_ids), "units": units, "lineup": lineup,
            "combos": combos}


def _name(pid):
    """A player's name from nba_sim.db (one who has left the team)."""
    r = players._db().execute("SELECT full_name FROM players WHERE player_id=?", (int(pid),)).fetchone()
    return r[0] if r else str(pid)


def _narrow(raw):
    return raw.mean() + (raw - raw.mean()) * MARGIN_SD / raw.std()


def explain(home, away, lineups, lines, lg, con, scale, sims):
    h, hr = run.team(home, lineups, lg, con)
    a, ar = run.team(away, lineups, lg, con)
    pace = float(np.mean([p for p in (run.pace_of(con, home), run.pace_of(con, away)) if p] or [lg["pace"]]))
    b2b = {"home_b2b": gf.is_back_to_back(home), "away_b2b": gf.is_back_to_back(away)}
    kw = dict(sims=sims, pace=pace, scale=scale, **b2b)
    full = engine.simulate(h, a, lg, **kw)
    base = engine.simulate(h, a, lg, **dict(kw, home_b2b=False, away_b2b=False), hca=0.0, off=engine.LAYERS)
    court = engine.simulate(h, a, lg, **kw, off=engine.LAYERS)
    steps = [{"step": "Players on a neutral court", "pts": round(float(base["margin"].mean()), 2)},
             {"step": "Home court" + (" and back-to-backs" if any(b2b.values()) else ""),
              "pts": round(float(court["margin"].mean() - base["margin"].mean()), 2)}]
    for layer in engine.LAYERS:
        r = engine.simulate(h, a, lg, **kw, off=(layer,))
        steps.append({"step": LAYER_NAME[layer], "pts": round(float(full["margin"].mean() - r["margin"].mean()), 2)})
    total = float(full["margin"].mean())
    steps.append({"step": "How the layers combine", "pts": round(total - sum(s["pts"] for s in steps), 2)})
    mg = _narrow(full["margin"])
    book = lines.get((home, away), {})
    edges = np.arange(-40, 42, 2)
    hist = np.histogram(np.clip(mg, -39.9, 39.9), bins=edges)[0]
    box = lambda t, b: sorted(({"name": n, "pid": int(pid), "pts": round(float(p), 1), "min": round(float(m), 1)}
                               for n, pid, p, m in zip(t["names"], t["pids"], b.mean(0), t["min"])), key=lambda x: -x["pts"])[:6]
    return {
        "game": f"{away}@{home}", "home": home, "away": away,
        "home_name": gf.TEAM_FULL_NAMES.get(home, home), "away_name": gf.TEAM_FULL_NAMES.get(away, away),
        "home_color": gf.TEAM_COLORS.get(home, "#333"), "away_color": gf.TEAM_COLORS.get(away, "#333"),
        "book_home_spread": book.get("spread"), "book_total": book.get("total"),
        "pace": round(pace, 1), "b2b": b2b,
        "home_ortg": round(float(full["home_pts"].mean() / pace * 100), 1),
        "away_ortg": round(float(full["away_pts"].mean() / pace * 100), 1),
        "home_pts": round(float(full["home_pts"].mean()), 1), "away_pts": round(float(full["away_pts"].mean()), 1),
        "spacing": {"home": round(full["home_spacing"], 2), "away": round(full["away_spacing"], 2)},
        "chemistry": {"home": round(full["home_syn"], 2), "away": round(full["away_syn"], 2)},
        "margin": round(total, 2), "home_win": round(float(np.mean(mg > 0)), 3),
        "hist": {"edges": edges.tolist(), "counts": hist.tolist()},
        "steps": steps,
        "teams": {home: _team_detail(h, hr, lineups.get(home, {}), home),
                  away: _team_detail(a, ar, lineups.get(away, {}), away)},
        "box": {home: box(h, full["home_box"]), away: box(a, full["away_box"])},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", help="AWY@HOM,AWY@HOM")
    ap.add_argument("--slate", action="store_true", help="every game on tonight's slate")
    ap.add_argument("--sims", type=int, default=5000)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    con = players._db()
    lg = players.league(con)
    scale = run.calibrate(lg, con)
    lineups, lines, pairs, _d, times = gf.scrape_rotowire()
    want = [[a, h] for h, a in pairs] if args.slate else [g.split("@") for g in (args.games or "").split(",") if g]
    out = []
    for away, home in want:
        if (home, away) not in set(pairs):
            print(f"{away}@{home}: not on tonight's slate")
            continue
        out.append(explain(home, away, lineups, lines, lg, con, scale, args.sims))
        print(f"{away}@{home}: margin {out[-1]['margin']:+.1f}")
    json.dump({"generated": __import__("datetime").datetime.utcnow().isoformat() + "Z", "games": out},
              open(args.out, "w"), indent=1)


if __name__ == "__main__":
    main()

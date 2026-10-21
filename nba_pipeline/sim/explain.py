"""Everything the sim did for a game, step by step, as JSON (for the walkthrough page).

  cd nba_pipeline && python3 -m sim.explain --games MIN@MIA,UTA@MEM --out walk.json

Per game: the rotations it played (minutes, usage, efficiency, play types,
shooting gravity, impact, role WOWY changes, who is out), the possession
environment (pace, each offense against this defense), what each layer moved
the margin, the 5,000-game margin distribution against the book line, and the
projected box score.
"""

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import engine, players, run  # noqa: E402  (run sets up generate_frontend and logging)
from sim.run import MARGIN_SD, gf  # noqa: E402

LABEL = {"PRBallHandler": "P&R handler", "Isolation": "Isolation", "Spotup": "Spot-up", "Transition": "Transition",
         "Cut": "Cut", "PRRollMan": "Roll man", "Postup": "Post-up", "Handoff": "Handoff", "OffScreen": "Off screen",
         "OffRebound": "Putback", "Misc": "Other"}
LAYER_NAME = {"lineups": "Lineup plan", "load": "Usage load", "spacing": "Spacing", "pairs": "Chemistry", "scheme": "Scheme vs play type",
              "fatigue": "Fatigue"}


def _team_detail(t, roster, info):
    names = dict(zip(roster.player_id.astype(int), roster.full_name))
    out_ids, _ = gf._resolve_out_ids(info, roster, "", "walkthrough")
    starters = {int(p) for p in (gf._match_player_name(n, roster) for n, _pos, st in info.get("starters", [])
                                 if st != "OUT") if p is not None}
    rows = []
    for i, pid in enumerate(t["pids"]):
        mix = t["mix"][i]
        top = [LABEL[players.TYPES[j]] for j in np.argsort(-mix)[:2]]
        role = t.get("role", {}).get(pid)
        rows.append({"name": t["names"][i], "starter": pid in starters, "min": round(float(t["min"][i]), 1),
                     "usg": round(float(t["usg"][i]) * 100, 1),
                     "per_use": round(float((1 - t["tov"][i]) * (mix @ t["ppp"][i])), 2),
                     "plays": top, "gravity": round(float(t["g"][i]), 2),
                     "off": round(float(t["off"][i]), 1), "def": round(float(t["def"][i]), 1),
                     "role": ({"usg": round(role[0] * 100, 1), "eff": round(role[1], 2)} if role else None)})
    rows.sort(key=lambda r: (not r["starter"], -r["min"]))
    units = []
    if t.get("plan"):
        last = lambda i: t["names"][i].split()[-1] if t["names"][i].split()[-1] not in ("Jr.", "II", "III") else t["names"][i].split()[-2]
        for five, mins, net, imp, chem in t["plan"]["units"][:6]:
            units.append({"five": [last(i) for i in five], "min": round(mins, 1), "net": round(net, 1),
                          "impact": round(imp, 1), "chem": round(chem, 1),
                          "start": five == t["plan"]["start"], "close": five == t["plan"]["close"]})
    return {"rotation": rows, "out": sorted(names.get(p, str(p)) for p in out_ids), "units": units}


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
    box = lambda t, b: sorted(({"name": n, "pts": round(float(p), 1), "min": round(float(m), 1)}
                               for n, p, m in zip(t["names"], b.mean(0), t["min"])), key=lambda x: -x["pts"])[:6]
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
        "teams": {home: _team_detail(h, hr, lineups.get(home, {})), away: _team_detail(a, ar, lineups.get(away, {}))},
        "box": {home: box(h, full["home_box"]), away: box(a, full["away_box"])},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", required=True, help="AWY@HOM,AWY@HOM")
    ap.add_argument("--sims", type=int, default=5000)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    con = players._db()
    lg = players.league(con)
    scale = run.calibrate(lg, con)
    lineups, lines, pairs, _d, times = gf.scrape_rotowire()
    want = [g.split("@") for g in args.games.split(",")]
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

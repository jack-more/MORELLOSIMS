"""The possession sim as it runs live, replayed on 2025-26 with nothing it couldn't
have known that morning.

Runs (all from sim/backtest.py's point-in-time inputs: rates, minutes, priors,
pace, lineup history, role WOWY, chemistry from games before the date):
  main      player impact off (the first backtest's run, for comparison)
  pit       player impact from sim/pit_rapm.py fit on stints before the date, at
            the live weight; pair and unit chemistry scored against those impacts
  pit_nopt  pit without the 2025-26 play-type mix (the only full-season input
            left), so everything is point-in-time
  pre       pit_nopt, and who plays from the morning's injury report (the saved
            dashboards' OUT lists, --pregame) instead of the box score; starters
            from the dashboard where marked, else the previous game's
Output: results.json (per game: every run's margin, the inputs' notes) for
sim/backtest_ats.py, which joins the morning book lines.

  cd nba_pipeline && python3 -m sim.backtest_pit --out DIR [--pregame outs.json]
"""

import argparse
import collections
import datetime as dt
import json
import multiprocessing as mp
import os
import re
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import engine  # noqa: E402
from sim.backtest import (BASE_HCA, HCA, IMPACT_W, MIN_TEAM_GAMES, Chemistry, Season,  # noqa: E402
                          _connect, _day_before, _lean, _sim_task)
from sim.pit_rapm import PitRapm  # noqa: E402

SKIP_DAYS = 5          # the first days have almost no stints; still early-season games are kept
RUNS = {               # name: (play types, point-in-time impacts, pregame availability)
    "main": (True, False, False),
    "pit": (True, True, False),
    "pit_nopt": (False, True, False),
    "pre": (False, True, True),
}


def _key(name):
    """'T. Maxey' / 'Tyrese Maxey' / 'Nikola Jokić' -> ('t', 'maxey')."""
    s = re.sub(r"[^a-z .'-]", "", name.lower().replace("ć", "c").replace("č", "c").replace("é", "e")
               .replace("ö", "o").replace("ü", "u").replace("ģ", "g").replace("ņ", "n").replace("š", "s"))
    parts = [p for p in s.replace(".", ". ").split() if p not in ("jr", "jr.", "sr.", "ii", "iii", "iv")]
    return (parts[0][:1], parts[-1].strip(".")) if parts else ("", "")


def map_names(names, pids, full):
    """Player ids among pids for dashboard names (first initial + last name)."""
    idx = collections.defaultdict(list)
    for p in pids:
        idx[_key(full.get(p, ""))].append(p)
    out, miss = [], []
    for n in names:
        hit = idx.get(_key(n))
        (out.extend(hit) if hit else miss.append(n))
    return out, miss


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--pregame", help="outs.json from the saved dashboards")
    ap.add_argument("--sims", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--cal-every", type=int, default=7)
    ap.add_argument("--cal-sims", type=int, default=600)
    ap.add_argument("--max-dates", type=int, default=0, help="debug: stop after this many game dates")
    ap.add_argument("--runs", default="", help="comma list of runs (default: all)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    logf = open(os.path.join(args.out, "progress.log"), "a")
    t_start = time.time()

    def log(msg):
        line = f"[{time.time() - t_start:7.1f}s] {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    con = _connect()
    S = Season(con, log)
    R = PitRapm(con)
    outs = json.load(open(args.pregame)) if args.pregame else {}
    runs = {k: v for k, v in RUNS.items() if (outs or not v[2]) and (not args.runs or k in args.runs.split(","))}
    if "pit" not in runs:                       # the thin flag reads the pit run's plan
        runs["pit"] = RUNS["pit"]
    abbr_id = {a: t for t, a in S.abbr.items()}
    team_games = collections.defaultdict(list)                   # tid -> [(date, game_id)]
    for g in S.games.itertuples():
        team_games[int(g.home)].append((g.game_date, g.game_id))
        team_games[int(g.away)].append((g.game_date, g.game_id))

    def last_starters(tid, D):
        prev = [gid for d, gid in team_games[tid] if d < D]
        return [p for p, s in S.box[prev[-1]][tid] if s] if prev else []

    dates = sorted(S.games.game_date.unique())
    start = (dt.date.fromisoformat(dates[0]) + dt.timedelta(days=SKIP_DAYS)).isoformat()
    chem = Chemistry(S.arch)
    game_tasks, cal_tasks, meta, skipped, unmatched = [], [], [], collections.Counter(), collections.Counter()
    cal_dates, cal_lg, next_cal = [], {}, start
    for di, D in enumerate(dates):
        if args.max_dates and di >= args.max_dates:
            break
        todays = S.games[S.games.game_date == D]
        if D < start:
            skipped["first days"] += len(todays)
            chem.add(S.stints.get(D, []))
            continue
        lg = S.league(D)
        imp = R.fit(D)
        beta = {p: o + d for p, (o, d) in imp.items()}
        ctx = {"zero": chem.state(False)[0], "pit": chem.state(False, beta)[0]}
        lg_small = {k: lg[k] for k in ("pace", "ortg", "spacing", "off_ppp", "tov", "oreb", "dreb")}

        def finish(base, run):
            pt, pit, _ = runs[run]
            return S.finish(base, ctx["pit" if pit else "zero"], False, impacts=imp if pit else None)

        if D >= next_cal:
            cal_dates.append(D)
            cal_lg[D] = lg["ortg"]
            avg = engine.average_team(lg)
            for tid in sorted(S.abbr):
                if not S.roster(tid, D):
                    continue
                bases = {True: S.base_team(tid, D, lg), False: S.base_team(tid, D, lg, playtypes=False)}
                for run, (pt, pit, _) in runs.items():
                    kw = {"sims": args.cal_sims, "hca": 0.0, "impact_w": IMPACT_W if pit else 0.0,
                          "seed": 11 + tid % 1000}
                    cal_tasks.append(("cal", (D, run, tid), _lean(finish(bases[pt], run)), avg, lg_small, kw))
            next_cal = (dt.date.fromisoformat(D) + dt.timedelta(days=args.cal_every)).isoformat()
        for g in todays.itertuples():
            h, a = int(g.home), int(g.away)
            if min(S.team_games_before(h, D), S.team_games_before(a, D)) < MIN_TEAM_GAMES:
                skipped["team with too few games"] += 1
                continue
            bx = S.box[g.game_id]
            teams, notes = {}, {}
            for tid in (h, a):
                box_tonight = [p for p, _ in bx[tid]]
                box_start = [p for p, s in bx[tid] if s]
                base = {pt: S.base_team(tid, D, lg, box_tonight, box_start, playtypes=pt) for pt in (True, False)}
                teams[tid] = {}
                for run, (pt, pit, pre) in runs.items():
                    if not pre:
                        teams[tid][run] = finish(base[pt], run)
                        continue
                    rep = outs.get(D, {}).get(S.abbr[tid])
                    if rep is None:
                        continue
                    roster = S.roster(tid, D)
                    out_ids, miss = map_names(rep.get("out", []), roster, S.names)
                    unmatched["out"] += len(miss)
                    tonight = [p for p in roster if p not in set(out_ids)]
                    st, miss_s = map_names(rep.get("starters", []), tonight, S.names)
                    unmatched["starters"] += len(miss_s)
                    if len(st) != 5:
                        st = [p for p in last_starters(tid, D) if p in tonight]
                    teams[tid][run] = finish(S.base_team(tid, D, lg, tonight, st, playtypes=pt), run)
                    notes[S.abbr[tid]] = {"out": [S.names.get(p, p) for p in out_ids], "missed": miss,
                                          "box_not_on_report": [S.names.get(p, p) for p in box_tonight if p not in tonight]}
            pace = (S.pace(h, D, lg) + S.pace(a, D, lg)) / 2
            b2b = {"home_b2b": (h, _day_before(D)) in S.sched, "away_b2b": (a, _day_before(D)) in S.sched}
            gi = len(meta)
            for run, (pt, pit, pre) in runs.items():
                if run not in teams[h] or run not in teams[a]:
                    continue
                kw = {"sims": args.sims, "pace": pace, "hca": HCA, "seed": 1000 + gi,
                      "impact_w": IMPACT_W if pit else 0.0, **b2b}
                game_tasks.append(("game", (gi, run), _lean(teams[h][run]), _lean(teams[a][run]), lg_small, kw))
            nr_h, nr_a = S.nrtg(h, D), S.nrtg(a, D)
            thin = {S.abbr[t]: bool((teams[t]["pit"]["plan"] or {}).get("thin")) for t in (h, a)}
            meta.append({"game_id": g.game_id, "date": D, "home": S.abbr[h], "away": S.abbr[a],
                         "actual_margin": int(g.home_pts - g.away_pts), "actual_total": int(g.home_pts + g.away_pts),
                         "pace": round(pace, 2), **b2b, "base_nrtg": (nr_h - nr_a) * pace / 100.0 + BASE_HCA,
                         "thin": thin, "pregame": notes, "cal_date": cal_dates[-1]})
        chem.add(S.stints.get(D, []))
        if len(meta) % 100 < len(todays):
            log(f"built {D}: {len(meta)} games")
    log(f"inputs: {len(meta)} games, {len(game_tasks)} game sims, {len(cal_tasks)} calibration sims; "
        f"skipped {dict(skipped)}; unmatched report names {dict(unmatched)}")

    with mp.get_context("fork").Pool(args.workers) as pool:
        cal = collections.defaultdict(list)
        for _k, (D, run, tid), ortg in pool.imap_unordered(_sim_task, cal_tasks, chunksize=4):
            cal[(D, run)].append(ortg)
        scale = {k: cal_lg[k[0]] / float(np.mean(v)) for k, v in cal.items()}
        log("calibration: " + ", ".join(f"{D} {run} {s:.3f}" for (D, run), s in sorted(scale.items())[:8]) + " ...")
        for task in game_tasks:
            gi, run = task[1]
            task[5]["scale"] = scale[(meta[gi]["cal_date"], run)]
        done, t0 = 0, time.time()
        for _k, (gi, run), r in pool.imap_unordered(_sim_task, game_tasks, chunksize=2):
            meta[gi][f"{run}_margin"] = round(r["margin"], 3)
            meta[gi][f"{run}_sd_raw"] = round(r["sd_raw"], 3)
            meta[gi][f"{run}_total"] = round(r["home_pts"] + r["away_pts"], 2)
            done += 1
            if done % 500 == 0:
                el = time.time() - t0
                log(f"simulated {done}/{len(game_tasks)} (eta {el / done * (len(game_tasks) - done):.0f}s)")
    json.dump({"generated": dt.datetime.now(dt.timezone.utc).isoformat(), "runs": list(runs), "games": meta},
              open(os.path.join(args.out, "results.json"), "w"), indent=1, default=str)
    log(f"wrote {args.out}/results.json in {(time.time() - t_start) / 60:.1f} min")


if __name__ == "__main__":
    main()

"""Point-in-time backtest of the possession sim over the 2025-26 regular season.

  cd nba_pipeline && python3 -m sim.backtest --sims 2000 --out <dir>

Every 2025-26 regular-season game (counts_regular=1; the NBA Cup final is not one)
on date D is simulated from inputs built only from 2025-26 games dated before D,
2024-25 season lines, or nothing. The builder (Season.base_team / finish) returns
the same dict players.team_inputs does, so sim/engine.py runs unchanged.

Point-in-time (built from games before D)
  who plays      the players who played in that game (dnp=0, sec>0); starters are
                 that game's `started` flag (lineups are public before tip)
  minutes        each player's average over his last 10 games played before D
                 (under 3 games: topped up with his 2024-25 mpg, else 12), then
                 players.rotation (starters 28-36, bench fills to 240, top 10)
  out players    the roster is inferred: everyone whose most recent 2025-26 game
                 before D was for this team, within the team's last 25 games
                 (injured players are absent from ESPN boxes, and the season-end
                 roster_assignments would leak trades). Roster players not in
                 tonight's box are OUT: they drive role WOWY and the load norm
  box rates      usage, TOV per use, 3PA share, OREB/DREB shares, points per use
                 and 3P% / 3PA per 36 (gravity) from espn_player_games before D,
                 shrunk with players.py's constants toward a 2024-25 prior
                 (player_season_stats, itself shrunk to its league, expressed
                 relative to the league so it rides on the league rate before D),
                 else toward the league rate before D
  pairs / units  context.pairs / context.units recomputed from espn_lineup_games
                 stints before D (cumulative sums by date); the method-of-moments
                 signal variances (tau2) are re-estimated at every date from the
                 stints before D, so nothing is fixed from later data. With
                 backtest_pit --prior-chem, 2024-25's stints (playoffs included)
                 are in from opening night, as the live sim reads the seasons
                 before this one, a combo's older season at Chemistry.older_w
  role WOWY      context.role_wowy's rule on espn_player_games before D, for the
                 regulars OUT tonight
  pace           each team's possessions per 48 before D, shrunk to the league
                 (10 games); the game's pace is the two teams' average
  league         league rates, ORtg, pace and an average five's gravity from games
                 before D; league play-type PPP from 2024-25 team_playtypes
  scheme         team defense per play type from 2024-25 team_playtypes
                 (context.team_defense's formula with the season pinned)
  B2B / HCA      back-to-backs from the schedule; HCA 1.68 (engine default)
  scale          run.calibrate's method made point-in-time: every 7 days, the 30
                 teams' full-strength offenses (inputs as of that day) against
                 engine.average_team; scale = league ORtg of games before that
                 day / their mean simulated ORtg. Separate scale per run
  baselines      home court (+1.7), and team net rating before D (difference x
                 pace / 100 + 1.7)

Leaks (stated, not hidden)
  play types     player_playtypes exists only as 2025-26 season totals. Used for
                 each player's mix and his relative PPP across types (the shape);
                 the level is set by his point-in-time points per use (players.py
                 levels every player this way). The shrink weight uses 2025-26 gp.
  positions      the 2025-26 archetype position_group (else 2024-25's, else the
                 listed position), as the live sim reads the current season's: a
                 PG/SG/SF/PF/C label used only by the lineup plan's guard/big
                 constraints. With 2024-25 labels first, lineups.plan's LP is
                 infeasible for 18% of rotations instead of 11% (the engine then
                 draws fives at random by minutes)
  who plays      knowing who logged minutes is slightly post hoc (a player hurt in
                 the first minute still gets his full projection; a deep-bench
                 player can make a short-handed ten)
  leaky run      the second run turns on player_rapm (RAPM/LEBRON snapshot that
                 includes 2025-26) exactly as players.py/context.py use it:
                 impact_w 0.5, off/def per player, and the snapshot impacts
                 subtracted from stint residuals in pairs/units. Labeled
                 "leaky (end-of-season RAPM)"
  (check run)    a third run, "nopt", is the main run with no 2025-26 play-type
                 data at all (every player gets the 2024-25 league mix and per-type
                 PPP, then the same point-in-time leveling): fully point-in-time,
                 it measures what the play-type leak is worth

Neutralised instead of leaked
  player defensive play-type PPP -> 1.0 (season-level only); load curves
  (player_potential is a current snapshot) -> the default slope for everyone;
  impacts in the main run -> 0. With impacts 0 the pair/unit residual is the raw
  on-court net against the team's own average, so within-team quality reaches the
  main run only through that layer.

Market: full-season closing lines are not in the DB. The only lines are the old
model's spread picks (nba_pipeline/data/picks.csv via utils.ledger.read_rows,
cross-checked with pick_log.json book_spread); the new sim is scored at those
same lines. The database is opened read-only; nothing outside --out is written.
"""

import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse  # noqa: E402
import collections  # noqa: E402
import datetime as dt  # noqa: E402
import itertools  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import multiprocessing as mp  # noqa: E402
import sqlite3  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH  # noqa: E402
from sim import context, engine, lineups, players  # noqa: E402
from sim.context import NOISE, SYN_SHARE  # noqa: E402
from sim.players import (CURVE_DEFAULT, CURVE_HI, CURVE_LO, CURVE_SHRINK, K_BOX, K_PLAYTYPE,  # noqa: E402
                         THREE_SHAPE, TYPE_TOV, TYPES, USG_POWER)

SEASON, PRIOR = "2025-26", "2024-25"
HCA = 1.68                  # engine.simulate default
BASE_HCA = 1.7              # the baselines' home edge
MARGIN_SD = 15.0            # sim/run.py's narrowing (not imported: run.py pulls in generate_frontend)
IMPACT_W = 0.5              # sim/run.py's --impact default, for the leaky run
SKIP_DAYS = 10
MIN_TEAM_GAMES = 3          # and each team needs this many games before D
ROSTER_WINDOW = 25          # team games a player stays on the inferred roster after his last one
MIN_GAMES_PROJ = 3          # projected minutes: fewer games than this are topped up with the prior
LEAGUE_MIN = 12.0           # minutes prior for a player with no 2024-25 line
PACE_K = 10.0               # games of league pace behind a team's pace
K_3PCT, K_3RATE = 100.0, 300.0   # 3PA and minutes behind 3P% and 3PA/36 (gravity)
CHANCES_PER_MIN = 0.9       # rebound chances per player-minute, to weigh a 2024-25 reb% prior
POSS_PER_MIN = 2.08         # offensive possessions per player-minute, to weigh a 2024-25 usage prior
SLOPE = min(CURVE_HI, max(CURVE_LO, CURVE_SHRINK * CURVE_DEFAULT))
BOX = ["fga", "fta", "tov", "fg3a", "fg3m", "off_poss", "oreb", "dreb", "och", "dch", "pts", "used", "min"]
MONTHS = (("Oct-Nov", (10, 11)), ("Dec-Jan", (12, 1)), ("Feb-Mar", (2, 3)), ("Apr", (4,)))
RUNS = ("main", "leaky", "nopt")
# the main run with one piece taken out, to see what each is worth: (inputs, engine layers off)
ABLATIONS = {"no_lineups": ("main", ("lineups",)),       # fives drawn by minutes alone
             "no_history": ("nohist", ()),               # lineup plan without the coach's real fives
             "no_pairs": ("main", ("pairs",)),           # no pair or unit chemistry on the floor
             "no_wowy": ("nowowy", ()),                  # no role WOWY for missing regulars
             "no_load": ("main", ("load",)),
             "no_spacing": ("main", ("spacing",)),
             "no_scheme": ("main", ("scheme",)),
             "no_fatigue": ("main", ("fatigue",))}       # fatigue and back-to-backs
LABEL = {"main": "sim (point-in-time, impact 0)", "leaky": "sim leaky (end-of-season RAPM)",
         "nopt": "sim, no play-type data (fully point-in-time)",
         "base_home": "baseline: home court +1.7", "base_nrtg": "baseline: net rating to date + 1.7"}


def _shrink(x, n, prior, k):
    return players._shrink(x, n, prior, k)


def _connect():
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def _day_before(d):
    return (dt.date.fromisoformat(d) - dt.timedelta(days=1)).isoformat()


class Season:
    """2025-26 logs, 2024-25 priors and the static tables, loaded once."""

    def __init__(self, con, log, prior_lineups=False):
        """prior_lineups: the lineup plan also reads 2024-25's fives (regular season), as the
        live sim reads the seasons before this one."""
        self.con, self.log = con, log
        self.prior_lineups = prior_lineups
        q = lambda sql, *a: pd.read_sql_query(sql, con, params=a)  # noqa: E731
        pg = q("SELECT game_id, team_id, player_id, game_date, started, dnp, sec, fga, fta, tov, fg3a, fg3m, "
               "pts, off_poss, oreb, dreb, on_oreb, on_opp_dreb, on_dreb, on_opp_oreb FROM espn_player_games "
               "WHERE season_id=? AND counts_regular=1", SEASON)
        num = [c for c in pg.columns if c not in ("game_id", "game_date")]
        pg[num] = pg[num].fillna(0)
        box = (pg.dnp == 0).astype(float)
        pg["played"] = (pg.dnp == 0) & (pg.sec > 0)
        pg["min"] = pg.sec / 60.0
        pg["used"] = pg.fga + 0.44 * pg.fta + pg.tov
        pg["och"] = pg.on_oreb + pg.on_opp_dreb
        pg["dch"] = pg.on_dreb + pg.on_opp_oreb
        for c in BOX:
            pg[c] = pg[c] * box
        self.pg = pg
        # per-player logs: dates, cumulative box sums (row k = before his k-th game), team, minutes played
        self.plog = {}
        for pid, g in pg.sort_values(["player_id", "game_date"]).groupby("player_id"):
            vals = g[BOX].to_numpy(float)
            pl = g[g.played]
            self.plog[int(pid)] = {"dates": g.game_date.to_numpy(), "team": g.team_id.to_numpy(),
                                   "cum": np.vstack([np.zeros(len(BOX)), np.cumsum(vals, 0)]),
                                   "pdates": pl.game_date.to_numpy(), "pmin": pl["min"].to_numpy()}
        self.team_players = {int(t): set(map(int, g.player_id.unique())) for t, g in pg.groupby("team_id")}
        self.team_rows = {int(t): g.sort_values("game_date").reset_index(drop=True) for t, g in pg.groupby("team_id")}
        # league box sums by date (cumulative, before the date)
        daily = pg.groupby("game_date")[BOX].sum().sort_index()
        self.lg_dates = daily.index.to_numpy()
        self.lg_cum = np.vstack([np.zeros(len(BOX)), np.cumsum(daily.to_numpy(float), 0)])
        # team games
        tg = q("SELECT t.game_id, t.team_id, t.opp_team_id, t.is_home, t.game_date, t.pts, t.poss, t.minutes, "
               "o.pts AS opp_pts, o.poss AS opp_poss FROM espn_team_games t JOIN espn_team_games o "
               "ON o.game_id=t.game_id AND o.team_id=t.opp_team_id WHERE t.season_id=? AND t.counts_regular=1", SEASON)
        tg["p48"] = tg.poss * 240.0 / tg.minutes.where(tg.minutes > 0, 240.0)
        self.tg = tg
        self.tlog = {}
        for tid, g in tg.sort_values("game_date").groupby("team_id"):
            v = g[["pts", "opp_pts", "poss", "opp_poss", "p48"]].to_numpy(float)
            self.tlog[int(tid)] = {"dates": g.game_date.to_numpy(), "cum": np.vstack([np.zeros(5), np.cumsum(v, 0)])}
        tgd = tg.groupby("game_date")[["pts", "poss", "p48"]].sum().sort_index()
        tgn = tg.groupby("game_date").size().sort_index()
        self.tg_dates = tgd.index.to_numpy()
        self.tg_cum = np.vstack([np.zeros(4), np.cumsum(np.column_stack([tgd.to_numpy(float), tgn.to_numpy(float)]), 0)])
        # the games to predict
        home = tg[tg.is_home == 1]
        self.games = home[["game_id", "game_date", "team_id", "opp_team_id", "pts", "opp_pts"]].rename(
            columns={"team_id": "home", "opp_team_id": "away", "pts": "home_pts", "opp_pts": "away_pts"}
        ).sort_values(["game_date", "game_id"]).reset_index(drop=True)
        self.box = collections.defaultdict(lambda: collections.defaultdict(list))   # game -> team -> [(pid, started)]
        for r in pg[pg.played].itertuples():
            self.box[r.game_id][int(r.team_id)].append((int(r.player_id), bool(r.started)))
        # schedule (all 2025-26 games, for back-to-backs)
        self.sched = set()
        for d, h, a in con.execute("SELECT game_date, home_team_id, away_team_id FROM games WHERE season_id=?", (SEASON,)):
            self.sched |= {(int(h), d), (int(a), d)}
        self.abbr = {int(t): a for t, a in con.execute("SELECT team_id, abbreviation FROM teams")}
        self.names = {int(p): n for p, n in con.execute("SELECT player_id, full_name FROM players")}
        for e, p, n in con.execute("SELECT espn_id, player_id, espn_name FROM espn_player_map"):
            self.names.setdefault(int(p), n)
        self._priors(con)
        self._static(con)
        self._stints(con)

    # ---------------------------------------------------------------- static inputs
    def _priors(self, con):
        """2024-25 season lines as rates relative to the 2024-25 league, each shrunk toward 1
        by its own volume with players.py's constant."""
        ps = pd.read_sql_query(
            "SELECT player_id, gp, minutes_total, minutes_per_game, pts_pg, tov_pg, fta_pg, fg3a_pg, ts_pct, "
            "usg_pct, reb_pct, fg3_pct, fg3a_per36 FROM player_season_stats WHERE season_id=?", con, params=(PRIOR,))
        ps = ps.fillna(0)
        ps["fga_pg"] = np.where(ps.ts_pct > 0, ps.pts_pg / (2 * ps.ts_pct.where(ps.ts_pct > 0, 1)) - 0.44 * ps.fta_pg, 0)
        ps["fga_pg"] = ps.fga_pg.clip(lower=0)
        ps["used_pg"] = ps.fga_pg + 0.44 * ps.fta_pg + ps.tov_pg
        ok = ps[ps.ts_pct > 0]
        w = lambda col, wt: float((ok[col] * ok[wt]).sum() / ok[wt].sum())  # noqa: E731
        tot = lambda col: float((ok[col] * ok.gp).sum())  # noqa: E731
        lg = {"usg": w("usg_pct", "minutes_total"), "reb": w("reb_pct", "minutes_total"),
              "tov": tot("tov_pg") / tot("used_pg"), "share3": tot("fg3a_pg") / tot("fga_pg"),
              "ppu": tot("pts_pg") / tot("used_pg"), "f3": float((ok.fg3_pct * ok.fg3a_pg * ok.gp).sum() / tot("fg3a_pg")),
              "a36": tot("fg3a_pg") / float(ok.minutes_total.sum()) * 36}
        self.lg_prior = lg
        self.prior = {}
        for r in ps.itertuples():
            p = {"mpg": float(r.minutes_per_game or 0) or None}
            if r.ts_pct > 0 and r.used_pg > 0:
                used, fga, f3a = r.used_pg * r.gp, r.fga_pg * r.gp, r.fg3a_pg * r.gp
                p["usg"] = _shrink(r.usg_pct / lg["usg"], r.minutes_total * POSS_PER_MIN, 1.0, K_BOX)
                p["tov"] = _shrink(r.tov_pg / r.used_pg / lg["tov"], used, 1.0, K_BOX / 4)
                p["ppu"] = _shrink(r.pts_pg / r.used_pg / lg["ppu"], used, 1.0, K_BOX)
                p["share3"] = _shrink((r.fg3a_pg / r.fga_pg if r.fga_pg > 0 else lg["share3"]) / lg["share3"],
                                      fga, 1.0, K_BOX / 4)
                p["reb"] = _shrink(r.reb_pct / lg["reb"], r.minutes_total * CHANCES_PER_MIN, 1.0, K_BOX / 4)
                p["f3"] = _shrink((r.fg3_pct or lg["f3"]) / lg["f3"], f3a, 1.0, K_3PCT)
                p["a36"] = _shrink(r.fg3a_per36 / lg["a36"], r.minutes_total, 1.0, K_3RATE)
            self.prior[int(r.player_id)] = p

    def _static(self, con):
        # play types: 2025-26 season totals (the stated leak), weight = per-game possessions x 2025-26 gp
        self.offpt = collections.defaultdict(dict)
        for pid, t, s, p, n in con.execute(
                "SELECT pt.player_id, pt.play_type, pt.poss_pct, pt.ppp, pt.possessions * COALESCE(ps.gp, 1) "
                "FROM player_playtypes pt LEFT JOIN player_season_stats ps "
                "ON ps.player_id=pt.player_id AND ps.season_id=pt.season_id "
                "WHERE pt.season_id=? AND pt.type_grouping='Offensive'", (SEASON,)):
            self.offpt[int(pid)][t] = (s or 0.0, p or 0.0, n or 0.0)
        nba = tuple(self.abbr)
        mark = ",".join("?" * len(nba))
        self.off_ppp = {t: p for t, p in con.execute(
            f"SELECT play_type, SUM(ppp*possessions)/SUM(possessions) FROM team_playtypes WHERE season_id=? "
            f"AND type_grouping='Offensive' AND team_id IN ({mark}) GROUP BY play_type", (PRIOR, *nba))}
        mix = {t: s for t, s in con.execute(
            f"SELECT play_type, AVG(poss_pct) FROM team_playtypes WHERE season_id=? AND type_grouping='Offensive' "
            f"AND team_id IN ({mark}) GROUP BY play_type", (PRIOR, *nba))}
        self.lg_mix = np.array([mix.get(t, 0.0) for t in TYPES]) + 0.01
        self.lg_mix = self.lg_mix / self.lg_mix.sum()       # the no-play-type run's mix for everyone (2024-25 league)
        self.lg_def = context.league_team_defense(con, PRIOR)
        # scheme: context.team_defense's formula, season pinned to 2024-25 (no leak)
        self.tdef = {}
        for tid in self.abbr:
            rows = con.execute("SELECT play_type, ppp, possessions FROM team_playtypes WHERE team_id=? AND "
                               "season_id=? AND type_grouping='Defensive'", (tid, PRIOR)).fetchall()
            out = {}
            for t, ppp, n in rows:
                base = self.lg_def.get(t) or np.mean([r[1] for r in rows])
                n = (n or 0) * 82
                out[t] = ((ppp or base) * n + base * 300) / (n + 300) / base
            self.tdef[tid] = out
        # archetypes for the pair prior: 2024-25 labels only
        self.arch = {int(p): a for p, a in con.execute(
            "SELECT player_id, archetype_label FROM player_archetypes WHERE season_id=?", (PRIOR,))}
        # positions, as the live sim reads them: the season's archetype position_group (a label
        # for the lineup plan's guard/big constraints only), else 2024-25's, else the listed position.
        # 2024-25 first would be leak-free but leaves 18% of plans infeasible against 11% (see docstring)
        grp = {int(p): g for p, g in con.execute(
            "SELECT player_id, position_group FROM player_archetypes WHERE season_id=? AND position_group<>''", (PRIOR,))}
        grp.update({int(p): g for p, g in con.execute(
            "SELECT player_id, position_group FROM player_archetypes WHERE season_id=? AND position_group<>''", (SEASON,))})
        listed = {int(p): x for p, x in con.execute("SELECT player_id, position FROM players") if x}
        listed.update({int(p): x for p, x in con.execute(
            "SELECT player_id, listed_position FROM roster_assignments WHERE season_id=? AND listed_position<>''", (SEASON,))})
        self.grp, self.listed = grp, listed
        # the leaky run's impacts: players.py's read of player_rapm
        self.impact = {int(p): players._impact(con, int(p)) for (p,) in con.execute("SELECT player_id FROM player_rapm")}
        self.imp_sum = context.impacts(con)

    def pos(self, pid):
        return self.grp.get(pid) or {"G": "SG", "F": "SF", "C": "C"}.get((self.listed.get(pid) or "F")[:1], "SF")

    def _stints(self, con):
        emap = {str(e): int(p) for e, p in con.execute("SELECT espn_id, player_id FROM espn_player_map")}
        st = pd.read_sql_query(
            "SELECT g.game_date, l.team_id, l.e1, l.e2, l.e3, l.e4, l.e5, l.pts, l.opp_pts, l.poss, l.opp_poss "
            "FROM espn_lineup_games l JOIN espn_team_games g ON g.game_id=l.game_id AND g.team_id=l.team_id "
            "WHERE g.season_id=? AND g.counts_regular=1", con, params=(SEASON,))
        self.stints = collections.defaultdict(list)
        skipped = 0
        for r in st.itertuples(index=False):
            ps = tuple(sorted(p for p in (emap.get(str(e)) for e in r[2:7]) if p))
            n = (r.poss or 0) + (r.opp_poss or 0)
            if len(ps) < 5 or n <= 0:
                skipped += 1
                continue
            raw = 200.0 * ((r.pts or 0) - (r.opp_pts or 0))            # residual x n, before impacts
            imp = n * sum(self.imp_sum.get(p, 0.0) for p in ps)       # the leaky run subtracts this
            self.stints[r.game_date].append((int(r.team_id), ps, raw, imp, float(n)))
        self.stint_rows, self.stint_skipped = len(st), skipped
        # 2024-25's stints, playoffs included (live chemistry reads every stored game of its
        # seasons): Chemistry.add(..., season=1) seeds the chemistry with them before opening night
        pr = pd.read_sql_query(
            "SELECT l.team_id, l.e1, l.e2, l.e3, l.e4, l.e5, l.pts, l.opp_pts, l.poss, l.opp_poss "
            "FROM espn_lineup_games l JOIN espn_team_games g ON g.game_id=l.game_id AND g.team_id=l.team_id "
            "WHERE g.season_id=?", con, params=(PRIOR,))
        self.prior_stints = []
        for r in pr.itertuples(index=False):
            ps = tuple(sorted(p for p in (emap.get(str(e)) for e in r[1:6]) if p))
            n = (r.poss or 0) + (r.opp_poss or 0)
            if len(ps) == 5 and n > 0:
                self.prior_stints.append((int(r.team_id), ps, 200.0 * ((r.pts or 0) - (r.opp_pts or 0)),
                                          n * sum(self.imp_sum.get(p, 0.0) for p in ps), float(n)))
        # the fives each coach played, game by game (context.lineup_history's rows), for the lineup plan
        lh = collections.defaultdict(lambda: collections.defaultdict(float))
        ldate = {}
        lh_seasons = (PRIOR, SEASON) if self.prior_lineups else (SEASON, SEASON)
        for gid, tid, date, *es, sec in con.execute(
                "SELECT l.game_id, l.team_id, g.game_date, l.e1, l.e2, l.e3, l.e4, l.e5, l.sec "
                "FROM espn_lineup_games l JOIN espn_team_games g ON g.game_id=l.game_id AND g.team_id=l.team_id "
                "WHERE g.season_id IN (?,?) AND g.counts_regular=1", lh_seasons):
            ps = tuple(sorted(p for p in (emap.get(str(e)) for e in es) if p))
            if len(ps) == 5 and sec:
                lh[(int(tid), gid)][ps] += sec / 60
                ldate[(int(tid), gid)] = date
        hist = collections.defaultdict(list)
        for (tid, gid), fives in lh.items():
            total = sum(fives.values())
            hist[tid].append((ldate[(tid, gid)], frozenset(p for f in fives for p in f),
                              {f: m * 48.0 / total for f, m in fives.items()}))
        self.lhist = {}
        for tid, g in hist.items():
            g.sort(key=lambda x: x[0])
            self.lhist[tid] = (np.array([x[0] for x in g]), g)

    # ---------------------------------------------------------------- point-in-time reads
    def _k(self, dates, D):
        return int(np.searchsorted(dates, D, "left"))

    def team_games_before(self, tid, D):
        t = self.tlog.get(tid)
        return self._k(t["dates"], D) if t else 0

    def league(self, D):
        """League averages from games before D (players.league's keys)."""
        b = dict(zip(BOX, self.lg_cum[self._k(self.lg_dates, D)]))
        t = self.tg_cum[self._k(self.tg_dates, D)]
        lg = {"off_ppp": self.off_ppp, "def_ppp": self.lg_def, "team_def": self.lg_def,
              "fg3_share": b["fg3a"] / b["fga"], "tov": b["tov"] / b["used"], "oreb": b["oreb"] / b["och"],
              "dreb": b["dreb"] / b["dch"], "pts_per_use": b["pts"] / b["used"], "usg": b["used"] / b["off_poss"],
              "fg3_pct": b["fg3m"] / b["fg3a"], "a36": b["fg3a"] / b["min"] * 36,
              "ortg": 100.0 * t[0] / t[1], "pace": t[2] / t[3]}
        # an average five's gravity, from everyone's point-in-time gravity, minutes-weighted
        gs, ms = 0.0, 0.0
        for pid in self.plog:
            r = self.rates(pid, D, lg, grav_only=True)
            if r is not None:
                gs, ms = gs + r[0] * r[1], ms + r[1]
        lg["spacing"] = 5 * gs / ms
        return lg

    def rates(self, pid, D, lg, grav_only=False):
        lp = self.plog.get(pid)
        b = dict(zip(BOX, lp["cum"][self._k(lp["dates"], D)])) if lp else dict.fromkeys(BOX, 0.0)
        pr = self.prior.get(pid, {})
        f3 = _shrink(b["fg3m"] / b["fg3a"] if b["fg3a"] else 0, b["fg3a"], lg["fg3_pct"] * pr.get("f3", 1.0), K_3PCT)
        a36 = _shrink(b["fg3a"] / b["min"] * 36 if b["min"] else 0, b["min"], lg["a36"] * pr.get("a36", 1.0), K_3RATE)
        g = context.gravity(f3, a36)
        if grav_only:
            return (g, b["min"]) if b["min"] > 0 else None
        u0 = lg["usg"] * pr.get("usg", 1.0)
        t0 = lg["tov"] * pr.get("tov", 1.0)
        s0 = lg["fg3_share"] * pr.get("share3", 1.0)
        o0, d0 = lg["oreb"] * pr.get("reb", 1.0), lg["dreb"] * pr.get("reb", 1.0)
        p0 = lg["pts_per_use"] * pr.get("ppu", 1.0)
        used, poss = b["used"], b["off_poss"]
        return {"usg": _shrink(used / poss if poss else 0, poss, u0, K_BOX),
                "tov": _shrink(b["tov"] / used if used else 0, used, t0, K_BOX / 4),
                "share3": _shrink(b["fg3a"] / b["fga"] if b["fga"] else 0, b["fga"], s0, K_BOX / 4),
                "oreb": _shrink(b["oreb"] / b["och"] if b["och"] else 0, b["och"], o0, K_BOX / 4),
                "dreb": _shrink(b["dreb"] / b["dch"] if b["dch"] else 0, b["dch"], d0, K_BOX / 4),
                "per_use": _shrink(b["pts"] / used if used else 0, used, p0, K_BOX),
                "g": g, "games": int(self._k(lp["pdates"], D)) if lp else 0, "prior": bool(pr.get("usg"))}

    def proj_min(self, pid, D):
        lp = self.plog.get(pid)
        last = np.array([])
        if lp is not None:
            k = self._k(lp["pdates"], D)
            last = lp["pmin"][max(0, k - 10):k]
        if len(last) >= MIN_GAMES_PROJ:
            return float(last.mean())
        prior = self.prior.get(pid, {}).get("mpg") or LEAGUE_MIN
        return float((last.sum() + prior * (MIN_GAMES_PROJ - len(last))) / MIN_GAMES_PROJ)

    def roster(self, tid, D):
        """Players whose latest game before D was for this team, within its last ROSTER_WINDOW games."""
        t = self.tlog.get(tid)
        if not t:
            return set()
        k = self._k(t["dates"], D)
        if k == 0:
            return set()
        start = t["dates"][max(0, k - ROSTER_WINDOW)]
        out = set()
        for pid in self.team_players.get(tid, ()):
            lp = self.plog[pid]
            j = self._k(lp["dates"], D)
            if j and lp["team"][j - 1] == tid and lp["dates"][j - 1] >= start:
                out.add(pid)
        return out

    def pace(self, tid, D, lg):
        t = self.tlog.get(tid)
        k = self._k(t["dates"], D) if t else 0
        return _shrink(t["cum"][k][4] / k if k else 0, k, lg["pace"], PACE_K)

    def nrtg(self, tid, D):
        t = self.tlog[tid]
        c = t["cum"][self._k(t["dates"], D)]
        return 100.0 * (c[0] / c[2] - c[1] / c[3]) if c[2] > 0 else 0.0

    def wowy(self, tid, D, mates, xs):
        """context.role_wowy's rule, on this team's games before D, for (mate, x) pairs only."""
        df = self.team_rows[tid]
        df = df.iloc[:self._k(df.game_date.to_numpy(), D)]
        games = dict(zip(df.game_id, df.game_date))
        played, mins = collections.defaultdict(dict), collections.defaultdict(float)
        for r in df[df.played].itertuples():
            played[int(r.player_id)][r.game_id] = (r.used, r.pts, r.off_poss)
            mins[int(r.player_id)] += r.min
        out = {}
        for x in xs:
            xg = played.get(x, {})
            if len(xg) < 20 or mins[x] / len(xg) < 20:
                continue
            first, last = min(games[g] for g in xg), max(games[g] for g in xg)
            span = {g for g, d in games.items() if first <= d <= last}
            for a in mates:
                ag = played.get(a)
                if a == x or not ag:
                    continue
                w_ = [ag[g] for g in ag if g in xg]
                wo = [ag[g] for g in ag if g in span and g not in xg]
                if len(w_) < 10 or len(wo) < 3:
                    continue
                uw, pw, nw = map(sum, zip(*w_))
                uo, po, no = map(sum, zip(*wo))
                if nw <= 0 or no <= 0 or uw <= 0 or uo <= 0:
                    continue
                out[(a, x)] = (uo / no - uw / nw, po / uo - pw / uw, len(wo) / (len(wo) + 5.0), uo / (uo + 300.0))
        return out

    # ---------------------------------------------------------------- the team dict
    def base_team(self, tid, D, lg, tonight=None, starters=(), playtypes=True, use_wowy=True):
        """Everything players.team_inputs builds except the impact-dependent keys
        (off, def, V, U, plan), from data before D. tonight=None: everyone available.
        playtypes=False: no 2025-26 play-type data at all (2024-25 league mix and per-type PPP)."""
        roster = self.roster(tid, D)
        playing = set(tonight) if tonight is not None else set(roster)
        roster |= playing
        proj = {p: self.proj_min(p, D) for p in sorted(roster)}
        rdf = pd.DataFrame({"player_id": list(proj), "minutes_per_game": list(proj.values())})
        out_ids = roster - playing
        mins = players.rotation(rdf, out_ids, starters)
        full = players.rotation(rdf, set(), ())
        pids = list(mins)
        n, T = len(pids), len(TYPES)
        rate = {p: self.rates(p, D, lg) for p in set(pids) | set(full)}
        gone = [x for x in out_ids if full.get(x, 0) >= 20]
        wowy = self.wowy(tid, D, pids, gone) if gone and use_wowy else {}
        role = {}
        for pid in pids:
            du = de = w = 0.0
            for x in gone:
                r = wowy.get((pid, x))
                if r:
                    du, de, w = du + r[0] * r[2], de + r[1] * r[3], max(w, r[2])
            role[pid] = (du, de, w)
        out = {"pids": pids, "names": [self.names.get(p, str(p)) for p in pids], "tid": tid,
               "min": np.array([mins[p] for p in pids]), "usg": np.zeros(n), "tov": np.zeros(n),
               "mix": np.zeros((n, T)), "ppp": np.zeros((n, T)), "p3": np.zeros((n, T)),
               "dppp": np.ones((n, T)), "dwt": np.ones((n, T)), "oreb": np.zeros(n), "dreb": np.zeros(n),
               "per_use": np.zeros(n)}
        for i, pid in enumerate(pids):
            r = rate[pid]
            out["usg"][i] = max(0.05, r["usg"] + role[pid][0])
            out["tov"][i] = r["tov"]
            out["oreb"][i], out["dreb"][i] = r["oreb"], r["dreb"]
            offpt = self.offpt.get(pid, {}) if playtypes else {}
            mix = np.array([offpt.get(t, (0, 0, 0))[0] for t in TYPES]) + 0.01
            out["mix"][i] = mix / mix.sum() if playtypes else self.lg_mix
            for j, t in enumerate(TYPES):
                s, p, k = offpt.get(t, (0, 0, 0))
                out["ppp"][i, j] = _shrink(p, k, lg["off_ppp"].get(t, 1.0), K_PLAYTYPE) / (1 - TYPE_TOV[t])
                out["p3"][i, j] = min(0.95, THREE_SHAPE[t] * r["share3"] / lg["fg3_share"])
            per_use = r["per_use"] + role[pid][1]
            model = (1 - out["tov"][i]) * float(out["mix"][i] @ out["ppp"][i])
            if model > 0:
                out["ppp"][i] *= per_use / model
            out["per_use"][i] = per_use
        out["uw"] = out["usg"] ** USG_POWER
        full_uw = {p: rate[p]["usg"] ** USG_POWER for p in full}
        floor_uw = sum(full_uw[p] * m / 48.0 for p, m in full.items())
        floor_tonight = float((out["uw"] * out["min"] / 48.0).sum())
        w = np.array([role[p][2] for p in pids])
        out["s_norm"] = w * out["uw"] / floor_tonight + (1 - w) * out["uw"] / floor_uw
        out["role"] = {p: role[p] for p in pids if role[p][2] > 0}
        out["slope"] = np.full(n, SLOPE)
        out["g"] = np.array([rate[p]["g"] for p in pids])
        out["pos"] = [self.pos(p) for p in pids]
        out["starters"] = [i for i, p in enumerate(pids) if p in set(starters)]
        ld, lg_rows = self.lhist.get(tid, (np.array([]), []))
        out["H"], out["SW"] = lineups.history(lg_rows[:self._k(ld, D)], pids, out["min"], gone, self.pos)
        out["tdef"] = np.array([self.tdef.get(tid, {}).get(t, 1.0) for t in TYPES])
        out["out"] = sorted(out_ids)
        out["gone"] = gone
        out["n_prior"] = sum(rate[p]["prior"] for p in pids)
        out["n_pt"] = sum(p in self.offpt for p in pids)
        out["games_before"] = [rate[p]["games"] for p in pids]
        return out

    def finish(self, base, ctx, leaky, impacts=None):
        """Add the impact-dependent keys: off/def, pair matrix V, unit values U, the lineup plan.
        impacts: {player: (off, def)} to use instead (the point-in-time RAPM run)."""
        t = dict(base)
        pids = t["pids"]
        n = len(pids)
        syn, prior, units = ctx
        src = impacts if impacts is not None else (self.impact if leaky else {})
        imp = [src.get(p, (0.0, 0.0)) for p in pids]
        t["off"] = np.array([x[0] for x in imp])
        t["def"] = np.array([x[1] for x in imp])
        V = np.zeros((n, n))
        known = 0
        for a, b in itertools.combinations(range(n), 2):
            k = (min(pids[a], pids[b]), max(pids[a], pids[b]))
            v = syn.get(k)
            if v is None:
                v = prior.get(tuple(sorted((self.arch.get(pids[a], ""), self.arch.get(pids[b], "")))), 0.0)
            else:
                known += 1
            V[a, b] = V[b, a] = v
        t["V"] = V
        idx = {p: i for i, p in enumerate(pids)}
        U = np.zeros(1 << n)
        for ps, v in units.get(t["tid"], {}).items():
            if all(p in idx for p in ps):
                U[sum(1 << idx[p] for p in ps)] = v
        t["U"] = U
        t["plan"] = lineups.plan(t)
        t["pairs_known"] = known
        return t


def _season(team_key):
    """Seasons back of a Chemistry team key: tid (this season) or (tid, seasons back)."""
    return team_key[1] if isinstance(team_key, tuple) else 0


class Chemistry:
    """context.pairs / context.units on stints before D, kept as cumulative sums by date.
    Sums per key: [raw residual x n, snapshot impact x n, n]; the main run's residual is
    the raw one, the leaky run's subtracts the snapshot impacts (as context.py does)."""

    def __init__(self, arch, pair_min=200, unit_min=100, tau_x=1.0, chem_w=1.0, tau_pair_min=0, tau_unit_min=0,
                 older_w=1.0):
        """pair_min / unit_min: possessions (both ends) before a pair / five gets its own value;
        tau_pair_min / tau_unit_min: only combos with this many possessions measure the signal
        variance (tau2) that every combo is shrunk with (0: all of them, as live);
        tau_x: multiplies the measured signal variances (more trust in small samples);
        chem_w: scales every chemistry value (0 = no chemistry);
        older_w: a combo's seasons before the last one it played count as this many
        possessions per possession (context.SEASON_W). Defaults are the live sim's."""
        self.arch = arch
        self.pair_min, self.unit_min, self.tau_x, self.chem_w = pair_min, unit_min, tau_x, chem_w
        self.tau_pair_min, self.tau_unit_min = tau_pair_min, tau_unit_min
        self.older_w = older_w
        self.team = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
        self.pair = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
        self.unit = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
        # possessions each player shared with each team / pair: residuals against any
        # set of impacts (the point-in-time RAPM run) without keeping every stint
        self.tco = collections.defaultdict(collections.Counter)
        self.pco = collections.defaultdict(collections.Counter)

    def add(self, stints, season=0):
        """season: 0 for this season's stints, 1 for the season before (its own team averages)."""
        for tid, ps, raw, imp, n in stints:
            tid = (tid, season) if season else tid
            for acc in [self.team[tid], self.unit[(tid, ps)]] + [self.pair[(a, b, tid)] for a, b in itertools.combinations(ps, 2)]:
                acc[0] += raw
                acc[1] += imp
                acc[2] += n
            for p in ps:
                self.tco[tid][p] += n
            for a, b in itertools.combinations(ps, 2):
                co = self.pco[(a, b, tid)]
                for p in ps:
                    co[p] += n

    @staticmethod
    def _tau2(est, nz, floor):
        return context._tau2(est, nz, floor) if len(est) else floor

    def _pool(self, entries):
        """(estimate, noise) from one combo's (estimate, noise, season) rows, one per team-season:
        inverse-noise weighted, a season older than the combo's latest counting older_w per step."""
        last = min(s for _, _, s in entries)
        sw = sz = 0.0
        for ex, z, s in entries:
            k = self.older_w ** (s - last)
            if k > 0:
                sw += ex * k / z
                sz += k / z
        return sw / sz, 1 / sz

    def state(self, leaky, beta=None):
        """beta: {player: net impact per 100} to score stints against (point-in-time RAPM)."""
        if beta is None:
            res = (lambda v: v[0] - v[1]) if leaky else (lambda v: v[0])
            tavg = {t: res(v) / v[2] for t, v in self.team.items() if v[2] > 0}
            pres = lambda key, v: res(v)
        else:
            res = None
            tavg = {t: (v[0] - sum(beta.get(p, 0.0) * n for p, n in self.tco[t].items())) / v[2]
                    for t, v in self.team.items() if v[2] > 0}
            pres = lambda key, v: v[0] - sum(beta.get(p, 0.0) * n for p, n in self.pco[key].items())
        seen = collections.defaultdict(list)
        for (a, b, tid), v in self.pair.items():
            n = v[2]
            if n < max(self.pair_min, 1):
                continue
            seen[(a, b)].append((pres((a, b, tid), v) / n - tavg[tid], NOISE / n, _season(tid)))
        raw = {k: self._pool(v) for k, v in seen.items()}
        arch = self.arch
        big = [(e, z) for e, z in raw.values() if NOISE / z >= self.tau_pair_min]
        tau2 = self.tau_x * self._tau2(np.array([e for e, _ in big]), np.array([z for _, z in big]), 0.25)
        pool = collections.defaultdict(lambda: [0.0, 0.0])
        for (a, b), (ex, z) in raw.items():
            if a in arch and b in arch:
                k = tuple(sorted((arch[a], arch[b])))
                pool[k][0] += ex / z
                pool[k][1] += 1 / z
        cm = {k: (s / w, 1 / w) for k, (s, w) in pool.items()}
        ctau2 = self._tau2(np.array([m for m, _ in cm.values()]), np.array([z for _, z in cm.values()]), 0.04)
        prior = {k: m * ctau2 / (ctau2 + z) for k, (m, z) in cm.items()}
        syn = {}
        for (a, b), (ex, z) in raw.items():
            p0 = prior.get(tuple(sorted((arch.get(a, ""), arch.get(b, "")))), 0.0)
            syn[(a, b)] = p0 + (ex - p0) * tau2 / (tau2 + z)
        useen = collections.defaultdict(list)
        for (tid, ps), v in self.unit.items():
            n = v[2]
            if n < max(self.unit_min, 1):
                continue
            chem = SYN_SHARE * sum(syn.get(ab, 0.0) for ab in itertools.combinations(ps, 2))
            r = res(v) if beta is None else v[0] - v[2] * sum(beta.get(p, 0.0) for p in ps)
            useen[(tid[0] if isinstance(tid, tuple) else tid, ps)].append((r / n - tavg[tid] - chem, NOISE / n, _season(tid)))
        uraw = {k: self._pool(v) for k, v in useen.items()}
        ubig = [(e, z) for e, z in uraw.values() if NOISE / z >= self.tau_unit_min]
        utau2 = self.tau_x * self._tau2(np.array([e for e, _ in ubig]), np.array([z for _, z in ubig]), 0.25)
        units = collections.defaultdict(dict)
        for (tid, ps), (ex, z) in uraw.items():
            units[tid][ps] = self.chem_w * ex * utau2 / (utau2 + z)
        if self.chem_w != 1.0:
            syn = {k: self.chem_w * v for k, v in syn.items()}
            prior = {k: self.chem_w * v for k, v in prior.items()}
        notes = {"pairs": len(raw), "pair_sd": round(math.sqrt(tau2), 2), "fit_sd": round(math.sqrt(ctau2), 2),
                 "units": len(uraw), "unit_sd": round(math.sqrt(utau2), 2)}
        return (syn, prior, dict(units)), notes


# -------------------------------------------------------------------- workers
def _lean(t):
    keep = ("min", "usg", "uw", "tov", "mix", "ppp", "p3", "dppp", "dwt", "tdef", "oreb", "dreb", "off", "def",
            "s_norm", "slope", "g", "V", "U", "pos", "starters", "plan", "names", "pids")
    return {k: t[k] for k in keep}


def _sim_task(task):
    kind, key, h, a, lg, kw = task
    res = engine.simulate(h, a, lg, **kw)
    if kind == "cal":
        return kind, key, float(res["home_pts"].mean() / lg["pace"] * 100)
    m = res["margin"]
    mu, sd = float(m.mean()), float(m.std())
    mg = mu + (m - mu) * MARGIN_SD / sd
    return kind, key, {"margin": mu, "sd_raw": sd, "home_pts": float(res["home_pts"].mean()),
                       "away_pts": float(res["away_pts"].mean()), "p_home_raw": float(np.mean(m > 0)),
                       "p_home_13": float(np.mean(mg > 0) + 0.5 * np.mean(mg == 0))}


# -------------------------------------------------------------------- metrics
def _metrics(pred, act):
    pred, act = np.asarray(pred, float), np.asarray(act, float)
    e = act - pred
    n = len(e)
    if n == 0:
        return {"n": 0}
    win = np.where(pred == 0, 0.5, (np.sign(pred) == np.sign(act)).astype(float))
    spread = np.ptp(pred) > 1e-9                      # the home-court baseline is a constant
    out = {"n": n, "mae": float(np.mean(np.abs(e))), "rmse": float(np.sqrt(np.mean(e ** 2))),
           "bias": float(np.mean(e)), "resid_sd": float(np.std(e, ddof=1)) if n > 1 else float("nan"),
           "corr": float(np.corrcoef(pred, act)[0, 1]) if spread else float("nan"),
           "winner": float(np.mean(win))}
    if spread:
        b, a = np.polyfit(pred, act, 1)
        out["ols_slope"], out["ols_int"] = float(b), float(a)
    return out


def _phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _brier(pred, act, sd):
    p = np.array([_phi(m / sd) for m in pred])
    y = (np.asarray(act) > 0).astype(float)
    return float(np.mean((p - y) ** 2))


def _record(results):
    w = sum(r == "W" for r in results)
    l_ = sum(r == "L" for r in results)
    p = sum(r == "P" for r in results)
    pct = w / (w + l_) if w + l_ else float("nan")
    return {"w": w, "l": l_, "p": p, "pct": pct}


def _fmt_rec(r):
    return f"{r['w']}-{r['l']}-{r['p']} ({r['pct']:.1%})" if r["w"] + r["l"] else f"{r['w']}-{r['l']}-{r['p']}"


def _ats(margin, home_line):
    x = margin + home_line
    return "home" if x > 0 else ("away" if x < 0 else "push")


def picks_analysis(rows_by_key, log):
    """Old model's 2025-26 regular-season spread picks vs the new sim at the same lines."""
    from utils.ledger import read_rows
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rows = read_rows(os.path.join(here, "data", "picks.csv"))
    try:
        plog = json.load(open(os.path.join(here, "data", "pick_log.json")))
    except Exception:  # noqa: BLE001
        plog = []
    booklog = {}
    for e in plog:
        if e.get("pick_type") == "spread" and e.get("book_spread") is not None:
            booklog[(e.get("slate_date"), e.get("matchup"))] = float(e["book_spread"])
    picks, skipped = [], collections.Counter()
    for r in rows:
        if not ("2025-10-01" <= r["date"] <= "2026-06-30"):
            continue                                     # another season
        if r.get("_sealed") or r.get("sealed_blob") or r.get("side") == "SEALED":
            skipped["sealed (no key)"] += 1
            continue
        if r["type"] != "spread":
            continue
        key = (r["date"], r["matchup"])
        if key not in rows_by_key:
            skipped["not a simulated regular-season game (play-in/playoffs or skipped)"] += 1
            continue
        if r["result"] not in ("W", "L", "P"):
            skipped[f"result {r['result'] or 'blank'}"] += 1
            continue
        team, line = r["side"].rsplit(" ", 1)
        line = float(line)
        g = rows_by_key[key]
        home_line = line if team == g["home"] else -line
        old_side = "home" if team == g["home"] else "away"
        actual = _ats(g["actual_margin"], home_line)
        check = "P" if actual == "push" else ("W" if actual == old_side else "L")
        bl = booklog.get(key)
        picks.append({"date": r["date"], "matchup": r["matchup"], "old_side": r["side"], "home_line": home_line,
                      "old_result": r["result"], "regraded": check, "pick_log_book_spread": bl,
                      "reinstated": r.get("void_reason", "").startswith("REINSTATED"), "game": g})
    out = {"n": len(picks), "skipped": dict(skipped),
           "regrade_mismatch": sum(p["old_result"] != p["regraded"] for p in picks),
           "pick_log_checked": sum(p["pick_log_book_spread"] is not None for p in picks),
           "pick_log_mismatch": sum(p["pick_log_book_spread"] is not None and abs(p["pick_log_book_spread"] - p["home_line"]) > 0.01
                                    for p in picks),
           "reinstated": sum(p["reinstated"] for p in picks),
           "old": _record([p["old_result"] for p in picks])}
    for run in ("main", "leaky", "nopt", "base_nrtg"):
        res, agree, disagree, edge3 = [], [], [], []
        for p in picks:
            g = p["game"]
            m = g[f"{run}_margin"] if run != "base_nrtg" else g["base_nrtg"]
            side = _ats(m, p["home_line"])
            act = _ats(g["actual_margin"], p["home_line"])
            rr = "P" if act == "push" else ("W" if act == side else "L")
            p[f"{run}_side"], p[f"{run}_result"] = side, rr
            res.append(rr)
            old = "home" if p["old_side"].rsplit(" ", 1)[0] == g["home"] else "away"
            (agree if side == old else disagree).append(rr)
            if abs(m + p["home_line"]) >= 3:
                edge3.append(rr)
        out[run] = {"all": _record(res), "agree": _record(agree), "disagree": _record(disagree),
                    "edge3": _record(edge3)}
    for p in picks:
        p.pop("game")
    out["rows"] = picks
    return out


# -------------------------------------------------------------------- the run
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sims", type=int, default=2000)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--skip-days", type=int, default=SKIP_DAYS)
    ap.add_argument("--cal-every", type=int, default=7, help="days between scale calibrations")
    ap.add_argument("--cal-sims", type=int, default=600)
    ap.add_argument("--max-dates", type=int, default=0, help="debug: stop after this many game dates")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    logf = open(os.path.join(args.out, "progress.log"), "a")
    t_start = time.time()

    def log(msg):
        line = f"[{time.time() - t_start:7.1f}s] {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    log(f"backtest start: sims={args.sims} workers={args.workers} skip_days={args.skip_days}")
    con = _connect()
    S = Season(con, log)
    log(f"loaded: {len(S.games)} games, {len(S.plog)} players, {sum(map(len, S.stints.values()))} stints "
        f"({S.stint_skipped} of {S.stint_rows} skipped: <5 mapped players or 0 possessions)")
    dates = sorted(S.games.game_date.unique())
    first = dates[0]
    start = (dt.date.fromisoformat(first) + dt.timedelta(days=args.skip_days)).isoformat()
    chem = Chemistry(S.arch)
    game_tasks, cal_tasks, meta_games, skipped = [], [], [], collections.Counter()
    cal_dates, cal_lg, chem_notes, plan_fail = [], {}, {}, collections.Counter()
    next_cal = start
    t_build = time.time()
    for di, D in enumerate(dates):
        if args.max_dates and di >= args.max_dates:
            break
        todays = S.games[S.games.game_date == D]
        if D < start:
            skipped[f"first {args.skip_days} days ({first} to {_day_before(start)})"] += len(todays)
            chem.add(S.stints.get(D, []))
            continue
        lg = S.league(D)
        ctxs, notes = {}, {}
        for run in ("main", "leaky"):
            ctxs[run], notes[run] = chem.state(run == "leaky")
        ctxs["nopt"] = ctxs["main"]
        chem_notes[D] = notes
        lg_small = {k: lg[k] for k in ("pace", "ortg", "spacing", "off_ppp", "tov", "oreb", "dreb")}
        if D >= next_cal:
            cal_dates.append(D)
            cal_lg[D] = lg["ortg"]
            avg = engine.average_team(lg)
            for tid in sorted(S.abbr):
                if not S.roster(tid, D):
                    continue
                bases = {True: S.base_team(tid, D, lg), False: S.base_team(tid, D, lg, playtypes=False)}
                for run in RUNS:
                    t = _lean(S.finish(bases[run != "nopt"], ctxs[run], run == "leaky"))
                    kw = {"sims": args.cal_sims, "hca": 0.0, "impact_w": IMPACT_W if run == "leaky" else 0.0,
                          "seed": 11 + tid % 1000}
                    cal_tasks.append(("cal", (D, run, tid), t, avg, lg_small, kw))
            next_cal = (dt.date.fromisoformat(D) + dt.timedelta(days=args.cal_every)).isoformat()
        for g in todays.itertuples():
            h, a = int(g.home), int(g.away)
            nh, na = S.team_games_before(h, D), S.team_games_before(a, D)
            if min(nh, na) < MIN_TEAM_GAMES:
                skipped[f"a team with < {MIN_TEAM_GAMES} games before the date"] += 1
                continue
            bx = S.box[g.game_id]
            teams = {}
            for tid in (h, a):
                tonight = [p for p, _ in bx[tid]]
                starters = [p for p, s in bx[tid] if s]
                base = S.base_team(tid, D, lg, tonight, starters)
                base_np = S.base_team(tid, D, lg, tonight, starters, playtypes=False)
                teams[tid] = {run: S.finish(base if run != "nopt" else base_np, ctxs[run], run == "leaky")
                              for run in RUNS}
                teams[tid]["base"] = base
                teams[tid]["nowowy"] = S.finish(S.base_team(tid, D, lg, tonight, starters, use_wowy=False),
                                                ctxs["main"], False)
                teams[tid]["nohist"] = S.finish(dict(base, H={}, SW={}), ctxs["main"], False)
            pace = (S.pace(h, D, lg) + S.pace(a, D, lg)) / 2
            b2b = {"home_b2b": (h, _day_before(D)) in S.sched, "away_b2b": (a, _day_before(D)) in S.sched}
            gi = len(meta_games)
            for run in RUNS:
                for tid in (h, a):
                    if teams[tid][run]["plan"] is None:
                        plan_fail[run] += 1
                kw = {"sims": args.sims, "pace": pace, "hca": HCA, "seed": 1000 + gi,
                      "impact_w": IMPACT_W if run == "leaky" else 0.0, **b2b}
                game_tasks.append(("game", (gi, run), _lean(teams[h][run]), _lean(teams[a][run]), lg_small, kw))
            for name, (inp, off) in ABLATIONS.items():
                kw = {"sims": args.sims, "pace": pace, "hca": HCA, "seed": 1000 + gi, "impact_w": 0.0, "off": off, **b2b}
                game_tasks.append(("game", (gi, name), _lean(teams[h][inp]), _lean(teams[a][inp]), lg_small, kw))
            nr_h, nr_a = S.nrtg(h, D), S.nrtg(a, D)

            def rot(t):
                return [[n_, round(float(m_), 1), round(float(u_), 3), round(float(pu), 3), gb]
                        for n_, m_, u_, pu, gb in zip(t["names"], t["min"], t["usg"], t["per_use"], t["games_before"])]
            meta_games.append({
                "game_id": g.game_id, "date": D, "home": S.abbr[h], "away": S.abbr[a],
                "matchup": f"{S.abbr[a]} @ {S.abbr[h]}", "actual_margin": int(g.home_pts - g.away_pts),
                "actual_total": int(g.home_pts + g.away_pts), "pace": round(pace, 2), **b2b,
                "base_home": BASE_HCA, "nrtg_home": round(nr_h, 2), "nrtg_away": round(nr_a, 2),
                "base_nrtg": (nr_h - nr_a) * pace / 100.0 + BASE_HCA,
                "team_games_before": [nh, na],
                "home_out": [S.names.get(p, str(p)) for p in teams[h]["base"]["gone"]],
                "away_out": [S.names.get(p, str(p)) for p in teams[a]["base"]["gone"]],
                "inputs": {"home_rot": rot(teams[h]["base"]), "away_rot": rot(teams[a]["base"]),
                           "home_no_prior": len(teams[h]["base"]["pids"]) - teams[h]["base"]["n_prior"],
                           "away_no_prior": len(teams[a]["base"]["pids"]) - teams[a]["base"]["n_prior"],
                           "home_no_playtypes": len(teams[h]["base"]["pids"]) - teams[h]["base"]["n_pt"],
                           "away_no_playtypes": len(teams[a]["base"]["pids"]) - teams[a]["base"]["n_pt"],
                           "home_pairs_known": teams[h]["main"]["pairs_known"],
                           "away_pairs_known": teams[a]["main"]["pairs_known"],
                           "home_syn_plan_start": round(float(lineups.strength(teams[h]["main"], teams[h]["main"]["plan"]["start"])[2]), 2) if teams[h]["main"]["plan"] else None,
                           "away_syn_plan_start": round(float(lineups.strength(teams[a]["main"], teams[a]["main"]["plan"]["start"])[2]), 2) if teams[a]["main"]["plan"] else None},
                "lg_ortg": round(lg["ortg"], 2), "lg_pace": round(lg["pace"], 2), "cal_date": cal_dates[-1]})
        chem.add(S.stints.get(D, []))
        if di % 10 == 0:
            log(f"built {D}: {len(meta_games)} games so far; chemistry main {notes['main']} leaky {notes['leaky']}")
    log(f"inputs built in {time.time() - t_build:.0f}s: {len(meta_games)} games, {len(cal_tasks)} calibration sims, "
        f"skipped {dict(skipped)}")

    ctx = mp.get_context("fork")
    with ctx.Pool(args.workers) as pool:
        t0 = time.time()
        cal = collections.defaultdict(list)
        for kind, (D, run, tid), ortg in pool.imap_unordered(_sim_task, cal_tasks, chunksize=4):
            cal[(D, run)].append(ortg)
        # scale = league ORtg of games before the calibration date / the 30 offenses' mean sim ORtg
        scales = {(D, run): {"lg_ortg": cal_lg[D], "mean_sim_ortg": float(np.mean(v)), "teams": len(v),
                             "scale": cal_lg[D] / float(np.mean(v))} for (D, run), v in cal.items()}
        log(f"calibration done in {time.time() - t0:.0f}s: " + ", ".join(
            f"{D} {run} {v['scale']:.3f}" for (D, run), v in sorted(scales.items())))
        for task in game_tasks:
            gi, run = task[1]
            task[5]["scale"] = scales[(meta_games[gi]["cal_date"], run if run in RUNS else "main")]["scale"]
        t0 = time.time()
        done = 0
        for kind, (gi, run), r in pool.imap_unordered(_sim_task, game_tasks, chunksize=2):
            g = meta_games[gi]
            g[f"{run}_margin"] = r["margin"]
            g[f"{run}_sd_raw"] = r["sd_raw"]
            g[f"{run}_total"] = r["home_pts"] + r["away_pts"]
            g[f"{run}_p_home_13"] = r["p_home_13"]
            g[f"{run}_scale"] = scales[(g["cal_date"], run if run in RUNS else "main")]["scale"]
            done += 1
            if done % 100 == 0:
                el = time.time() - t0
                log(f"simulated {done}/{len(game_tasks)} ({el:.0f}s, eta {el / done * (len(game_tasks) - done):.0f}s)")
    log(f"simulation done in {time.time() - t0:.0f}s")

    # ---------------------------------------------------------------- results
    rows_by_key = {(g["date"], g["matchup"]): g for g in meta_games}
    picks = picks_analysis(rows_by_key, log)
    for g in meta_games:
        g["book_home_line"] = None
    for p in picks["rows"]:
        g = rows_by_key[(p["date"], p["matchup"])]
        g["book_home_line"] = p["home_line"]
        g["old_pick"] = p["old_side"]
        g["old_result"] = p["old_result"]
    preds = ("main", "leaky", "nopt", "base_home", "base_nrtg")
    col = {"main": "main_margin", "leaky": "leaky_margin", "nopt": "nopt_margin", "base_home": "base_home",
           "base_nrtg": "base_nrtg"}
    act = np.array([g["actual_margin"] for g in meta_games], float)
    summary = {"overall": {}, "by_month": {}, "brier": {}, "totals": {}}
    for p in preds:
        summary["overall"][p] = _metrics([g[col[p]] for g in meta_games], act)
    for name, months in MONTHS:
        sel = [g for g in meta_games if int(g["date"][5:7]) in months]
        a = np.array([g["actual_margin"] for g in sel], float)
        summary["by_month"][name] = {p: _metrics([g[col[p]] for g in sel], a) for p in preds}
    for p in preds:
        pr = [g[col[p]] for g in meta_games]
        rsd = summary["overall"][p]["resid_sd"]
        summary["brier"][p] = {"sd13": _brier(pr, act, 13.0), "sd_fit": _brier(pr, act, rsd), "sd_fit_value": rsd}
    tot = np.array([g["actual_total"] for g in meta_games], float)
    for run in RUNS:
        st = np.array([g[f"{run}_total"] for g in meta_games])
        summary["totals"][run] = {"bias_actual_minus_sim": float(np.mean(tot - st)), "mae": float(np.mean(np.abs(tot - st))),
                                  "corr": float(np.corrcoef(st, tot)[0, 1]),
                                  "mean_raw_sd": float(np.mean([g[f"{run}_sd_raw"] for g in meta_games]))}
    summary["corr_main_vs_nrtg"] = float(np.corrcoef([g["main_margin"] for g in meta_games],
                                                     [g["base_nrtg"] for g in meta_games])[0, 1])
    summary["corr_main_vs_leaky"] = float(np.corrcoef([g["main_margin"] for g in meta_games],
                                                      [g["leaky_margin"] for g in meta_games])[0, 1])
    summary["corr_main_vs_nopt"] = float(np.corrcoef([g["main_margin"] for g in meta_games],
                                                     [g["nopt_margin"] for g in meta_games])[0, 1])
    summary["actual"] = {"margin_sd": float(np.std(act, ddof=1)), "margin_mean": float(np.mean(act)),
                         "home_win": float(np.mean(act > 0)), "total_mean": float(np.mean(tot))}
    summary["pred_sd"] = {p: float(np.std([g[col[p]] for g in meta_games])) for p in preds}
    summary["plan_fail_rate"] = {run: plan_fail[run] / (2 * len(meta_games)) for run in RUNS}
    summary["b2b_resid"] = {}
    for run in RUNS:
        for k in ("home_b2b", "away_b2b"):
            e = [g["actual_margin"] - g[f"{run}_margin"] for g in meta_games if g[k]]
            summary["b2b_resid"][f"{run}|{k}"] = {"n": len(e), "mean": float(np.mean(e)),
                                                  "se": float(np.std(e, ddof=1) / math.sqrt(len(e)))}
    m = np.array([g["main_margin"] for g in meta_games])
    edges = np.quantile(m, np.linspace(0, 1, 6))
    summary["quintiles_main"] = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        k = (m >= lo) & (m <= hi)
        summary["quintiles_main"].append({"lo": float(lo), "hi": float(hi), "n": int(k.sum()),
                                          "pred": float(m[k].mean()), "actual": float(act[k].mean())})
    flags = collections.Counter()
    for g in meta_games:
        for s in ("home_rot", "away_rot"):
            rot_ = g["inputs"][s]
            flags["player-games in a rotation"] += len(rot_)
            flags["debuts (no 2025-26 game before D)"] += sum(r[4] == 0 for r in rot_)
            flags["team-games with < 9 rotation players"] += len(rot_) < 9
        flags["players without a 2024-25 prior"] += g["inputs"]["home_no_prior"] + g["inputs"]["away_no_prior"]
        flags["players without 2025-26 play types"] += g["inputs"]["home_no_playtypes"] + g["inputs"]["away_no_playtypes"]
    summary["input_flags"] = dict(flags)
    runtime = time.time() - t_start
    meta = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(), "season": SEASON, "sims": args.sims,
            "workers": args.workers, "runtime_sec": round(runtime, 1), "games": len(meta_games),
            "skipped": dict(skipped), "first_date": start, "plan_failures": dict(plan_fail),
            "calibration": {f"{D}|{run}": v for (D, run), v in sorted(scales.items())},
            "chemistry_by_date": chem_notes, "lg_prior_2024_25": S.lg_prior, "summary": summary,
            "picks": {k: v for k, v in picks.items() if k != "rows"}}
    for g in meta_games:
        for k in list(g):
            if isinstance(g[k], float):
                g[k] = round(g[k], 3)
    json.dump({"meta": meta, "games": meta_games, "picks": picks["rows"]},
              open(os.path.join(args.out, "results.json"), "w"), indent=1, default=str)
    open(os.path.join(args.out, "summary.md"), "w").write(_summary_md(meta, summary, picks, meta_games))
    log(f"wrote {args.out}/results.json and summary.md; total runtime {runtime / 60:.1f} min")


def _summary_md(meta, s, picks, games):
    L = []
    w = L.append
    w("# Possession sim: point-in-time backtest, 2025-26 regular season\n")
    w(f"{meta['games']} games simulated ({meta['sims']} sims each), from {meta['first_date']} on. "
      f"Skipped: {', '.join(f'{v} ({k})' for k, v in meta['skipped'].items()) or 'none'}. "
      f"Runtime {meta['runtime_sec'] / 60:.1f} min on {meta['workers']} workers.\n")
    w("Predicted margin = mean simulated home margin. `leaky` turns on the end-of-season RAPM/LEBRON snapshot; "
      "everything else is identical. See sim/backtest.py's docstring for exactly what is point-in-time.\n")
    f3 = lambda x: "n/a" if x is None or x != x else f"{x:.3f}"  # noqa: E731
    f2 = lambda x: "n/a" if x is None or x != x else f"{x:.2f}"  # noqa: E731
    a = s["actual"]
    w("## Overall\n")
    w("| model | n | MAE | RMSE | corr | winner % | bias (act-pred) | resid SD | OLS slope | pred SD |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for p, m in s["overall"].items():
        w(f"| {LABEL[p]} | {m['n']} | {m['mae']:.2f} | {m['rmse']:.2f} | {f3(m['corr'])} | {m['winner']:.1%} | "
          f"{m['bias']:+.2f} | {m['resid_sd']:.2f} | {f2(m.get('ols_slope'))} | {s['pred_sd'][p]:.2f} |")
    w(f"\nActual home margin: mean {a['margin_mean']:+.2f}, SD {a['margin_sd']:.2f}, home teams won {a['home_win']:.1%}. "
      "OLS slope = actual regressed on predicted (1 = spreads the right width, < 1 = too wide). "
      "The home-court baseline is a constant, so it has no corr or slope; its winner % is the home win rate.\n")
    w(f"**Residual SD** of actual minus sim margin: main **{s['overall']['main']['resid_sd']:.2f}**, "
      f"leaky {s['overall']['leaky']['resid_sd']:.2f}, no-play-type {s['overall']['nopt']['resid_sd']:.2f}. "
      f"run.py narrows the engine's margins to MARGIN_SD = 13.0; on this season the point-in-time sim's errors "
      f"are ~{s['overall']['main']['resid_sd']:.1f} wide. The engine's own per-game margin SD averages "
      f"{s['totals']['main']['mean_raw_sd']:.1f} before narrowing.\n")
    w("## By month\n")
    w("| months | model | n | MAE | RMSE | corr | winner % | bias |")
    w("|---|---|---|---|---|---|---|---|")
    for name, d in s["by_month"].items():
        for p, m in d.items():
            if m["n"]:
                w(f"| {name} | {LABEL[p]} | {m['n']} | {m['mae']:.2f} | {m['rmse']:.2f} | "
                  f"{f3(m['corr'])} | {m['winner']:.1%} | {m['bias']:+.2f} |")
    w("\n## Main sim by predicted-margin quintile\n")
    w("| predicted range | n | mean predicted | mean actual |")
    w("|---|---|---|---|")
    for q in s["quintiles_main"]:
        w(f"| {q['lo']:+.1f} to {q['hi']:+.1f} | {q['n']} | {q['pred']:+.2f} | {q['actual']:+.2f} |")
    w("\n## Back-to-backs (actual minus predicted, mean +- SE)\n")
    for k, v in s["b2b_resid"].items():
        run, side = k.split("|")
        w(f"- {run}, {side.replace('_', ' ')}: n {v['n']}, {v['mean']:+.2f} +- {v['se']:.2f}")
    w("\n(The engine charges a back-to-back team 2.0 at home / 2.5 on the road plus extra fatigue; a negative "
      "away-B2B residual means the road B2B penalty is too big.)\n")
    w("\n## Win probability (Brier, normal around the predicted margin)\n")
    w("| model | SD 13 | SD = its residual SD |")
    w("|---|---|---|")
    for p, b in s["brier"].items():
        w(f"| {LABEL[p]} | {b['sd13']:.4f} | {b['sd_fit']:.4f} (SD {b['sd_fit_value']:.2f}) |")
    w("\n## Totals (scale check)\n")
    for run, t in s["totals"].items():
        w(f"- {LABEL[run]}: actual minus sim total {t['bias_actual_minus_sim']:+.2f}, MAE {t['mae']:.2f}, corr {t['corr']:.3f}")
    w(f"\nCorrelation of main sim margin with the net-rating baseline: {s['corr_main_vs_nrtg']:.3f}; "
      f"with the leaky sim: {s['corr_main_vs_leaky']:.3f}; with the no-play-type sim: {s['corr_main_vs_nopt']:.3f}.\n")
    w("## Against the market (old model's spread picks only)\n")
    pk = {k: v for k, v in picks.items() if k != "rows"}
    w(f"{pk['n']} regular-season spread picks with a book line (picks.csv side line; "
      f"{pk['pick_log_checked']} also in pick_log.json, {pk['pick_log_mismatch']} disagreeing). "
      f"Skipped: {pk['skipped'] or 'none'}. {pk['reinstated']} of the {pk['n']} carry a 'REINSTATED (owner decision)' note. "
      f"Re-grading the old picks from DB scores disagrees with picks.csv on {pk['regrade_mismatch']}.\n")
    w(f"- Old model, its own picks: **{_fmt_rec(pk['old'])}**")
    for run in ("main", "leaky", "nopt", "base_nrtg"):
        r = pk[run]
        w(f"- {LABEL[run]} at the same lines: **{_fmt_rec(r['all'])}**; agrees with old pick on "
          f"{r['agree']['w'] + r['agree']['l'] + r['agree']['p']} games: {_fmt_rec(r['agree'])}; disagrees on "
          f"{r['disagree']['w'] + r['disagree']['l'] + r['disagree']['p']}: {_fmt_rec(r['disagree'])}; "
          f"edge >= 3 pts: {_fmt_rec(r['edge3'])}")
    w("\nWhen the sim disagrees, its record is the old pick's record mirrored. Break-even at -110 is 52.4%. "
      "These are only the games the old model chose to bet, Feb 19 to Apr 12, not a random sample of lines.\n")
    w("## Inputs and engine checks\n")
    w(f"- lineups.plan LP infeasible (engine falls back to random fives by minutes): "
      + ", ".join(f"{run} {v:.1%} of team-games" for run, v in s["plan_fail_rate"].items())
      + ". Cause: archetype position labels put > 144 guard-minutes or < 48 big-minutes in a rotation, and the LP "
        "holds each player to his projection + 0.5 minutes as a hard cap. The live sim uses the same LP and "
        "labels, so it can fall back the same way.")
    for k, v in s["input_flags"].items():
        w(f"- {k}: {v}")
    w("\n## What is point-in-time and what leaks\n")
    w("- Point-in-time (games before the date only, or 2024-25): who plays and starts (that game's box: public "
      "lineups), projected minutes (last 10 games), usage / TOV / 3PA / rebounding / points per use / gravity "
      "(shrunk to 2024-25 priors), pair synergy, five-man units and their shrink variances (re-estimated each "
      "date), role WOWY, pace, league averages, calibration scale, team scheme (2024-25 team play types), "
      "both baselines.")
    om, on_ = s["overall"]["main"], s["overall"]["nopt"]
    w("- Leaks in the main run: player play-type mix and relative per-type PPP are 2025-26 season totals (level "
      "is point-in-time); position labels are 2025-26 archetype groups. The no-play-type run removes the first "
      f"leak entirely: MAE {on_['mae']:.2f} vs main {om['mae']:.2f}, corr {on_['corr']:.3f} vs {om['corr']:.3f}.")
    w("- Neutralised: player defensive play-type PPP = 1.0, load curves = default slope, RAPM/LEBRON = 0.")
    w("- Leaky run: player_rapm snapshot (includes 2025-26) as impacts, impact_w 0.5 and in the pair/unit "
      "residuals. The snapshot was fit on the very games being predicted, so its gain over the main run is "
      "optimistic for anything a point-in-time impact read could deliver.")
    w("- With impacts at 0 the main sim has almost no team-defense signal: defense enters only through the "
      "2024-25 scheme fingerprint (30% weight), defensive rebounding, and pair/unit on-court net (which is "
      "measured against each team's own average, so it carries no between-team strength).\n")
    w("## Calibration scale (point-in-time)\n")
    cal = meta["calibration"]
    w("| date | run | league ORtg before date | mean sim ORtg (scale 1) | scale |")
    w("|---|---|---|---|---|")
    for k, v in cal.items():
        D, run = k.split("|")
        w(f"| {D} | {run} | {v['lg_ortg']:.2f} | {v['mean_sim_ortg']:.2f} | {v['scale']:.3f} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()

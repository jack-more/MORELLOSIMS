"""NFL spread model — transparent, every number traceable.

For a game on date D, using ONLY games played before D (gameday < D):

1. Team EPA ratings (points per play). Weighted ridge regression over every
   team-game offense row:
       EPA/play(offense O vs defense X) = mu + off[O] + def[X] + h * home
   weight = plays * 0.5 ** (age_weeks / half_life), and previous-season games
   are multiplied by `carry` (the offseason discount). Ridge pulls off/def
   toward 0 (league average) with strength `ridge` (in plays). Early in a
   season the solve is dominated by last season's games, discounted and
   regressed — that is the prior.

2. Components of the projected home margin (points):
       epa_margin = P * [(off[H] + def[A]) - (off[A] + def[H])]
                    (P = league plays per team-game in the window)
       st_diff    = special-teams net EPA per game, H minus A (shrunk mean)
       qb_diff    = QB adjustment H minus A: (starter's EPA/dropback - the
                    team's recent dropback-weighted QB mix) * dropbacks/game.
                    Starter = nflverse schedule's QB for the game. QB values
                    shrink toward a replacement level measured from QBs with
                    few dropbacks in prior seasons.
       rest_diff  = home rest days - away rest days, clipped to [-7, 7]
       home       = 1 unless the game is at a neutral site

3. Calibration (fit on PRIOR seasons only, by OLS):
       margin = a*home + b1*epa_margin + b2*st_diff + b3*qb_diff + c*rest_diff
   `a` is the measured home-field advantage — not assumed.

The edge is margin - spread_line (nflverse convention: spread_line > 0 means
the home team is favored by that many points, same sign as the result).
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import QB_GAMES_CSV, SCHEDULES_CSV, TEAM_GAMES_CSV  # noqa: E402

DROPBACKS_PER_GAME = 36.0     # replaced by the measured window value in ratings_at
QB_SHRINK = 200.0             # dropbacks of prior for a QB's EPA/dropback
QB_HALF_LIFE = 52.0           # weeks of game time (QB skill is persistent)
ST_SHRINK = 8.0               # games of prior (0) for special-teams net EPA
REST_CLIP = 7.0
FEATURE_SETS = {
    "combined": ["home", "epa_margin", "st_diff", "qb_diff", "rest_diff"],
    "split": ["home", "pass_margin", "rush_margin", "st_diff", "qb_diff", "rest_diff"],
}
FEATURES = FEATURE_SETS["combined"]


@dataclass(frozen=True)
class Params:
    half_life: float = 10.0   # weeks of game time
    carry: float = 0.6        # weight multiplier per season back
    ridge: float = 600.0      # plays-equivalent prior strength toward league average
    competitive: bool = False  # use only plays with 10% <= win prob <= 90%

    def key(self):
        return f"hl{self.half_life:g}_c{self.carry:g}_r{self.ridge:g}_{'comp' if self.competitive else 'all'}"

    def as_dict(self):
        return asdict(self)


# competitive-only plays lost to all plays in every season of an earlier
# grid run (2019-2024 selection), so the grid keeps all plays.
GRID = [Params(h, c, r, False)
        for h in (10.0, 16.0, 26.0, 40.0)
        for c in (0.4, 0.6, 0.8)
        for r in (600.0, 1500.0, 3000.0, 6000.0)]


class Data:
    """Committed derived tables, indexed for fast as-of-date slicing."""

    def __init__(self, schedules=None, team_games=None, qb_games=None):
        self.sched = schedules if schedules is not None else pd.read_csv(SCHEDULES_CSV)
        tg = team_games if team_games is not None else pd.read_csv(TEAM_GAMES_CSV)
        qg = qb_games if qb_games is not None else pd.read_csv(QB_GAMES_CSV)
        self.sched = self.sched.copy()
        self.sched["gameday"] = pd.to_datetime(self.sched["gameday"])
        self.teams = sorted(set(self.sched["home_team"]) | set(self.sched["away_team"]))
        self.tix = {t: i for i, t in enumerate(self.teams)}
        # season calendar (first / last game day) for game-time ages
        cal = self.sched.groupby("season")["gameday"].agg(["min", "max"])
        self.season_start = cal["min"].to_dict()
        self.season_end = cal["max"].to_dict()

        tg = tg.copy()
        tg["gameday"] = pd.to_datetime(tg["gameday"])
        tg = tg[tg["team"].isin(self.tix) & tg["opp"].isin(self.tix)].sort_values("gameday")
        self.tg = tg.reset_index(drop=True)
        qg = qg.copy()
        qg["gameday"] = pd.to_datetime(qg["gameday"])
        self.qg = qg.sort_values("gameday").reset_index(drop=True)
        self._tg_days = self.tg["gameday"].values
        self._qg_days = self.qg["gameday"].values
        self._repl = {}

    # ── as-of slices ──
    def tg_before(self, day):
        return self.tg.iloc[: np.searchsorted(self._tg_days, np.datetime64(day), side="left")]

    def qg_before(self, day):
        return self.qg.iloc[: np.searchsorted(self._qg_days, np.datetime64(day), side="left")]

    def game_weeks_ago(self, days, seasons, day, season):
        """Age in weeks of game time: offseason gaps are not counted (the
        `carry` multiplier is the only offseason discount)."""
        days = pd.to_datetime(days)
        age = np.empty(len(days))
        start_now = self.season_start.get(season, day)
        in_season = (day - start_now).days / 7.0 if day >= start_now else 0.0
        for s in np.unique(seasons):
            m = seasons == s
            if s == season:
                age[m] = (day - days[m]).days / 7.0
            else:
                # weeks from the game to that season's end + the in-season
                # weeks of every later season up to now (full seasons ≈ 22 weeks)
                end = self.season_end[s]
                full = sum(((self.season_end[x] - self.season_start[x]).days / 7.0)
                           for x in range(s + 1, season) if x in self.season_end)
                age[m] = (end - days[m]).days / 7.0 + full + in_season
        return age

    def replacement_qb(self, season):
        """EPA/dropback of QBs with < 200 dropbacks in a season, pooled over
        every season before `season` (measured, walk-forward)."""
        if season not in self._repl:
            q = self.qg[self.qg["season"] < season]
            if q.empty:
                self._repl[season] = -0.10
            else:
                per = q.groupby(["season", "qb_id"]).agg(db=("dropbacks", "sum"), e=("qb_epa", "sum"))
                low = per[per["db"] < 200]
                self._repl[season] = float(low["e"].sum() / max(low["db"].sum(), 1.0))
        return self._repl[season]


@dataclass
class Ratings:
    day: pd.Timestamp
    season: int
    off: np.ndarray
    dfn: np.ndarray
    mu: float
    h_epa: float
    plays: float
    st: np.ndarray
    qb_mix: np.ndarray            # team's recent dropback-weighted QB value
    qb_value: dict                # qb_id -> shrunk EPA/dropback
    qb_name: dict
    dropbacks: float
    replacement: float
    n_obs: int
    off_p: np.ndarray = None      # pass / rush split ratings (EPA per play)
    def_p: np.ndarray = None
    off_r: np.ndarray = None
    def_r: np.ndarray = None
    pass_plays: float = 38.0


def _ridge(epa, plays, w_time, ti, oi, home, n_t, ridge):
    """Weighted ridge: EPA/play = mu + off[team] + def[opp] + h*home.
    Returns (mu, h, off[n_t], def[n_t]); off/def shrink toward 0 with
    strength `ridge` (plays-equivalent)."""
    ok = plays > 0
    y = np.where(ok, epa / np.maximum(plays, 1), 0.0)
    w = w_time * plays * ok
    n = len(y)
    k = 2 + 2 * n_t
    X = np.zeros((n, k))
    X[:, 0] = 1.0
    X[:, 1] = home
    X[np.arange(n), 2 + ti] = 1.0
    X[np.arange(n), 2 + n_t + oi] = 1.0
    XtW = X.T * w
    A = XtW @ X
    A[2:, 2:] += np.eye(2 * n_t) * ridge
    sol = np.linalg.solve(A + np.eye(k) * 1e-9, XtW @ y)
    return float(sol[0]), float(sol[1]), sol[2:2 + n_t], sol[2 + n_t:]


def ratings_at(data: Data, day, season: int, p: Params) -> Ratings:
    day = pd.Timestamp(day)
    tg = data.tg_before(day)
    tg = tg[tg["season"] >= season - 2]
    n_t = len(data.teams)
    if tg.empty:
        z = np.zeros(n_t)
        return Ratings(day, season, z, z.copy(), 0.0, 0.0, 64.0, z.copy(), z.copy(), {}, {},
                       DROPBACKS_PER_GAME, data.replacement_qb(season), 0,
                       z.copy(), z.copy(), z.copy(), z.copy(), 38.0)
    seasons = tg["season"].values
    age = data.game_weeks_ago(tg["gameday"].values, seasons, day, season)
    w_time = 0.5 ** (age / p.half_life) * (p.carry ** (season - seasons))
    ti = tg["team"].map(data.tix).values
    oi = tg["opp"].map(data.tix).values
    home = tg["is_home"].values.astype(float)

    plays = (tg["plays_c"] if p.competitive else tg["plays"]).values.astype(float)
    epa = (tg["epa_c"] if p.competitive else tg["epa"]).values.astype(float)
    ok = plays > 0
    mu, h, off, dfn = _ridge(epa, plays, w_time, ti, oi, home, n_t, p.ridge)
    # pass / rush split (all plays): separate ratings, combined later by the calibration
    _, _, off_p, def_p = _ridge(tg["pass_epa"].values.astype(float), tg["pass_plays"].values.astype(float),
                                w_time, ti, oi, home, n_t, p.ridge)
    _, _, off_r, def_r = _ridge(tg["rush_epa"].values.astype(float), tg["rush_plays"].values.astype(float),
                                w_time, ti, oi, home, n_t, p.ridge)
    n = len(tg)
    pw = w_time * ok
    plays_pg = float((tg["plays"].values * pw).sum() / max(pw.sum(), 1e-9))
    pass_pg = float((tg["pass_plays"].values * pw).sum() / max(pw.sum(), 1e-9))

    # special teams: shrunk decayed mean of net EPA per game
    st = np.zeros(n_t)
    st_num = np.bincount(ti, weights=w_time * tg["st_epa"].values, minlength=n_t)
    st_den = np.bincount(ti, weights=w_time, minlength=n_t)
    st = st_num / (st_den + ST_SHRINK)

    # QBs
    repl = data.replacement_qb(season)
    qg = data.qg_before(day)
    qg = qg[qg["season"] >= season - 3]
    qb_value, qb_name = {}, {}
    qb_mix = np.full(n_t, repl)
    db_pg = DROPBACKS_PER_GAME
    if not qg.empty:
        q_age = data.game_weeks_ago(qg["gameday"].values, qg["season"].values, day, season)
        qw = 0.5 ** (q_age / QB_HALF_LIFE)
        g = pd.DataFrame({"qb": qg["qb_id"].values, "db": qw * qg["dropbacks"].values,
                          "e": qw * qg["qb_epa"].values, "name": qg["qb_name"].values})
        agg = g.groupby("qb").agg(db=("db", "sum"), e=("e", "sum"), name=("name", "last"))
        vals = (agg["e"] + QB_SHRINK * repl) / (agg["db"] + QB_SHRINK)
        qb_value = vals.to_dict()
        qb_name = agg["name"].to_dict()
        # team mix uses the TEAM rating's decay, so it describes the QBs whose
        # plays are inside the team's offense rating
        tq = qg[qg["season"] >= season - 2]
        t_age = data.game_weeks_ago(tq["gameday"].values, tq["season"].values, day, season)
        tw = 0.5 ** (t_age / p.half_life) * (p.carry ** (season - tq["season"].values)) * tq["dropbacks"].values
        m = pd.DataFrame({"team": tq["team"].values, "qb": tq["qb_id"].values, "w": tw})
        m["v"] = m["qb"].map(qb_value).fillna(repl)
        for team, grp in m.groupby("team"):
            if team in data.tix and grp["w"].sum() > 0:
                qb_mix[data.tix[team]] = float((grp["w"] * grp["v"]).sum() / grp["w"].sum())
        # dropbacks per team-game in the window (game count from team rows)
        tgw = data.tg_before(day)
        tgw = tgw[tgw["season"] >= season - 1]
        if len(tgw):
            db_pg = float(qg[qg["season"] >= season - 1]["dropbacks"].sum() / len(tgw))
    return Ratings(day, season, off, dfn, float(mu), float(h), plays_pg, st, qb_mix, qb_value, qb_name,
                   db_pg, repl, n, off_p, def_p, off_r, def_r, pass_pg)


def starter_value(r: Ratings, qb_id):
    if qb_id is None or (isinstance(qb_id, float) and math.isnan(qb_id)) or qb_id == "":
        return None
    return r.qb_value.get(qb_id, r.replacement)


def components(data: Data, r: Ratings, g) -> dict:
    """Raw components for one schedule row (home perspective)."""
    H, A = data.tix[g["home_team"]], data.tix[g["away_team"]]
    epa_margin = r.plays * ((r.off[H] + r.dfn[A]) - (r.off[A] + r.dfn[H]))
    rush_pg = r.plays - r.pass_plays
    pass_margin = r.pass_plays * ((r.off_p[H] + r.def_p[A]) - (r.off_p[A] + r.def_p[H]))
    rush_margin = rush_pg * ((r.off_r[H] + r.def_r[A]) - (r.off_r[A] + r.def_r[H]))
    st_diff = float(r.st[H] - r.st[A])
    qb = {}
    for side, ti in (("home", H), ("away", A)):
        v = starter_value(r, g.get(f"{side}_qb_id"))
        qb[side] = 0.0 if v is None else (v - r.qb_mix[ti]) * r.dropbacks
    rest = 0.0
    if pd.notna(g.get("home_rest")) and pd.notna(g.get("away_rest")):
        rest = float(np.clip(g["home_rest"] - g["away_rest"], -REST_CLIP, REST_CLIP))
    return {
        "home": 0.0 if str(g.get("location")) == "Neutral" else 1.0,
        "epa_margin": float(epa_margin),
        "pass_margin": float(pass_margin),
        "rush_margin": float(rush_margin),
        "st_diff": st_diff,
        "qb_diff": float(qb["home"] - qb["away"]),
        "qb_adj_home": float(qb["home"]),
        "qb_adj_away": float(qb["away"]),
        "rest_diff": rest,
        "off_home": float(r.off[H]), "def_home": float(r.dfn[H]),
        "off_away": float(r.off[A]), "def_away": float(r.dfn[A]),
    }


def raw_components(data: Data, p: Params, games: pd.DataFrame) -> pd.DataFrame:
    """Components for every game in `games`, each from ratings as of its own
    game day (strictly earlier games only)."""
    rows = []
    for (season, day), grp in games.groupby(["season", "gameday"], sort=True):
        r = ratings_at(data, day, int(season), p)
        for _, g in grp.iterrows():
            c = components(data, r, g)
            c["game_id"] = g["game_id"]
            c["n_obs"] = r.n_obs
            rows.append(c)
    return pd.DataFrame(rows)


# ── calibration ──

@dataclass
class Calibration:
    coef: dict
    sigma: float            # residual SD of margin (points)
    n: int
    seasons: list

    @property
    def features(self):
        return list(self.coef)

    def predict(self, comp: pd.DataFrame | dict) -> np.ndarray | float:
        if isinstance(comp, dict):
            return float(sum(self.coef[f] * comp[f] for f in self.features))
        return comp[self.features].values @ np.array([self.coef[f] for f in self.features])

    def as_dict(self):
        return {"coef": {k: round(v, 6) for k, v in self.coef.items()}, "sigma": round(self.sigma, 4),
                "n": self.n, "seasons": self.seasons}

    @classmethod
    def from_dict(cls, d):
        return cls(dict(d["coef"]), float(d["sigma"]), int(d["n"]), list(d["seasons"]))


def fit_calibration(comp: pd.DataFrame, margin: np.ndarray, seasons: np.ndarray, target_season: int,
                    decay: float = 0.75, features=None) -> Calibration:
    """Weighted OLS of actual home margin on the components, no intercept
    (the `home` column is the measured home-field advantage). Seasons further
    back get weight decay**(target - 1 - season)."""
    features = features or FEATURES
    X = comp[features].values
    w = decay ** (target_season - 1 - seasons)
    XtW = X.T * w
    beta = np.linalg.solve(XtW @ X + np.eye(len(features)) * 1e-6, XtW @ margin)
    resid = margin - X @ beta
    sigma = float(np.sqrt((w * resid ** 2).sum() / w.sum()))
    return Calibration({f: float(b) for f, b in zip(features, beta)}, sigma, int(len(margin)),
                       sorted(int(s) for s in np.unique(seasons)))


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

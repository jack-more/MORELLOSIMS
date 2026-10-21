"""Tonight's lineup plan: which fives play, and for how long.

The plan starts from the fives this coach actually plays. For every five of
tonight's rotation that has shared the floor, its history is the minutes per
game the coach gave it in the games all five played (recent games count most,
and games the same regulars missed count triple). Those fives keep their real
minutes first. Only the minutes they cannot cover (a starter out, a new
signing) go to fives the coach has not used, and among those the strongest
(impact plus chemistry: pair values and the unit's own record, per 100
possessions) get them. The minutes are solved as a linear program subject to

  - every player's projected minutes (soft: a miss either way costs more than any five gains)
  - 48 minutes in all
  - the starters together long enough to open both halves, the closing five long enough to close
  - no unit beyond a realistic stint total (the starting five 20, any other 9) unless
    the coach plays it more
  - for fives the coach has never used: one to three guards, at least one big, at most
    two centers (relaxed step by step only if the rotation can't fill 48 minutes)

The engine then plays the plan: starters open each half, the closing five
finishes, and the other two-minute stretches draw from the remaining minutes.
"""

import collections
import itertools

import numpy as np
from scipy.optimize import linprog

from sim.context import SYN_SHARE

GUARDS, BIGS = {"PG", "SG"}, {"PF", "C"}
START_MIN, CLOSE_MIN = 12.0, 4.0          # starters open each half (6 + 6), the closers finish (4)
CAP_START, CAP_OTHER = 20.0, 9.0
SHORT_COST = 60.0                         # per minute a player misses his projection, either way
CLOSER_MIN = 20.0                         # closers come from players projected for 20+ minutes
REAL_BONUS = 25.0                         # per minute of a five's real minutes: the coach's own lineups first
NEW_COST = 8.0                            # per minute of a five the coach has never played
HALF_LIFE = 20                            # team games: the coach's recent lineups count most
LIKE_TONIGHT = 3.0                        # a game the same regulars missed tells most about tonight
SEEN_MIN = 0.5                            # minutes per game for a five to count as one the coach plays


def valid(pos, need_big=True):
    g = sum(p in GUARDS for p in pos)
    b = sum(p in BIGS for p in pos)
    c = sum(p == "C" for p in pos)
    return 1 <= g <= 3 and (b >= 1 or not need_big) and c <= 2


def history(games, pids, gone=()):
    """{bitmask of rotation indices: minutes per game} the coach has given each five of
    tonight's rotation, over the games all five played. games: context.lineup_history rows
    for this team (only games before tonight); gone: tonight's missing regulars."""
    idx = {p: i for i, p in enumerate(pids)}
    gone = set(gone)
    num = collections.defaultdict(float)
    den = collections.defaultdict(float)                 # weight by mask of rotation players who played
    k = len(games)
    for j, (_date, played, fives) in enumerate(games):
        w = 0.5 ** ((k - 1 - j) / HALF_LIFE) * (LIKE_TONIGHT if gone and not gone & played else 1.0)
        den[sum(1 << idx[p] for p in played if p in idx)] += w
        for f, m in fives.items():
            if all(p in idx for p in f):
                num[sum(1 << idx[p] for p in f)] += w * m
    out = {}
    for F, s in num.items():
        d = sum(w for M, w in den.items() if M & F == F)
        if d > 0 and s / d >= SEEN_MIN:
            out[F] = s / d
    return out


def strength(team, five):
    """(net per 100, impact part, chemistry part) of one five."""
    imp = float(sum(team["off"][i] + team["def"][i] for i in five))
    pairs = SYN_SHARE * float(sum(team["V"][a, b] for a, b in itertools.combinations(five, 2)))
    unit = float(team["U"][sum(1 << i for i in five)])
    return imp + pairs + unit, imp, pairs + unit


def plan(team):
    """{"units": [(five, minutes, net, impact, chemistry)], "start": five, "close": five,
    "played": {five: the coach's minutes per game}} or None (fewer than five players).
    The coach's own fives are always allowed; new fives must be position-balanced, then
    may be small, then anything, until the rotation fills 48 minutes."""
    return _plan(team, True) or _plan(team, False) or _plan(team, None)


def _plan(team, need_big):
    n = len(team["min"])
    if n < 5:
        return None
    H = team.get("H") or {}
    mask = lambda f: sum(1 << i for i in f)
    fives = [f for f in itertools.combinations(range(n), 5)
             if mask(f) in H or need_big is None or valid([team["pos"][i] for i in f], need_big)]
    st = tuple(sorted(team.get("starters") or []))
    if len(st) != 5:
        st = tuple(sorted(np.argsort(-team["min"])[:5].tolist()))
    if st not in fives:
        fives.append(st)
    scores = [strength(team, f) for f in fives]
    net = np.array([s[0] for s in scores])
    h = np.array([H.get(mask(f), 0.0) for f in fives])
    core = [k for k, f in enumerate(fives) if all(team["min"][i] >= CLOSER_MIN for i in f)]
    played_core = [k for k in core if h[k] > 0]
    close = fives[max(played_core or core, key=lambda k: net[k])] if core else st   # the best five of the regulars
    F = len(fives)
    cap = np.array([48.0 if need_big is None else max(h[k], CAP_START if f in (st, close) else CAP_OTHER)
                    for k, f in enumerate(fives)])
    # variables: each five's minutes within its history (F), beyond it (F), then each
    # player's shortfall (n) and excess (n) against his projection
    c = np.concatenate([-(net + REAL_BONUS), -(net - np.where(h > 0, 0.0, NEW_COST)),
                        np.full(2 * n, SHORT_COST)])
    A_eq = np.zeros((n + 1, 2 * F + 2 * n))
    b_eq = np.zeros(n + 1)
    A_eq[n, :2 * F] = 1
    b_eq[n] = 48.0
    for k, f in enumerate(fives):                        # each player's minutes + shortfall - excess = projection
        A_eq[list(f), k] = A_eq[list(f), F + k] = 1
    A_eq[np.arange(n), 2 * F + np.arange(n)] = 1
    A_eq[np.arange(n), 2 * F + n + np.arange(n)] = -1
    b_eq[:n] = team["min"]
    A_ub, b_ub = [], []
    for f, lo in ((st, START_MIN), (close, CLOSE_MIN)):
        k = fives.index(f)
        cap[k] = max(cap[k], START_MIN + CLOSE_MIN if st == close else lo)
        row = np.zeros(2 * F + 2 * n)
        row[k] = row[F + k] = -1
        A_ub.append(row); b_ub.append(-(START_MIN + CLOSE_MIN if st == close else lo))
    within = np.minimum(h, cap)
    bounds = ([(0, within[k]) for k in range(F)] + [(0, cap[k] - within[k]) for k in range(F)]
              + [(0, None)] * (2 * n))
    res = linprog(c, A_ub=np.array(A_ub), b_ub=np.array(b_ub), A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if not res.success:
        return None
    t = res.x[:F] + res.x[F:2 * F]
    units = sorted(((fives[k], float(t[k]), *scores[k]) for k in range(F) if t[k] > 0.05), key=lambda u: -u[1])
    return {"units": units, "start": st, "close": close,
            "played": {fives[k]: float(h[k]) for k in range(F) if h[k] > 0}}


def draw(rng, plan_, S, segments):
    """(S, segments, 5) lineups from the plan: starters open each half, the closers finish,
    the rest of the stretches draw from the minutes left."""
    half = segments // 2
    seg_min = 48.0 / segments
    fixed = {0: plan_["start"], 1: plan_["start"], 2: plan_["start"],
             half: plan_["start"], half + 1: plan_["start"], half + 2: plan_["start"],
             segments - 2: plan_["close"], segments - 1: plan_["close"]}
    left = {}
    for f, m, *_ in plan_["units"]:
        left[f] = m
    for f in fixed.values():
        left[f] = left.get(f, 0.0) - seg_min
    pool = [f for f, m in left.items() if m > 0.01]
    w = np.array([left[f] for f in pool]); w = w / w.sum() if w.sum() > 0 else np.ones(len(pool)) / len(pool)
    out = np.empty((S, segments, 5), dtype=int)
    free = [k for k in range(segments) if k not in fixed]
    picks = rng.choice(len(pool), size=(S, len(free)), p=w)
    arr = np.array(pool)
    for j, k in enumerate(free):
        out[:, k] = arr[picks[:, j]]
    for k, f in fixed.items():
        out[:, k] = np.array(f)
    return out

"""Tonight's lineup plan: which fives play, and for how long.

Coaches stack minutes on their best units and break them up only as the
rotation demands. So every valid five from the ten-man rotation is scored
(the five's impact plus its chemistry: pair values and the unit's own track
record, per 100 possessions) and the minutes are solved as a linear program:
put the most minutes on the strongest fives, subject to

  - every player's projected minutes (soft: a shortfall costs more than any five gains)
  - 48 minutes in all
  - the starters together long enough to open both halves, the best five long enough to close
  - no unit beyond a realistic stint total (the starting five 20, any other 9)
  - position balance: one to three guards, at least one big, at most two centers

The engine then plays the plan: starters open each half, the closing five
finishes, and the other two-minute stretches draw from the remaining minutes.
"""

import itertools

import numpy as np
from scipy.optimize import linprog

from sim.context import SYN_SHARE

GUARDS, BIGS = {"PG", "SG"}, {"PF", "C"}
START_MIN, CLOSE_MIN = 12.0, 4.0          # starters open each half (6 + 6), the closers finish (4)
CAP_START, CAP_OTHER = 20.0, 9.0
SHORT_COST = 60.0                         # per minute a player misses his projection
CLOSER_MIN = 20.0                         # closers come from players projected for 20+ minutes


def valid(pos, need_big=True):
    g = sum(p in GUARDS for p in pos)
    b = sum(p in BIGS for p in pos)
    c = sum(p == "C" for p in pos)
    return 1 <= g <= 3 and (b >= 1 or not need_big) and c <= 2


def strength(team, five):
    """(net per 100, impact part, chemistry part) of one five."""
    imp = float(sum(team["off"][i] + team["def"][i] for i in five))
    pairs = SYN_SHARE * float(sum(team["V"][a, b] for a, b in itertools.combinations(five, 2)))
    unit = float(team["U"][sum(1 << i for i in five)])
    return imp + pairs + unit, imp, pairs + unit


def plan(team):
    """{"units": [(five, minutes, net, impact, chemistry)], "start": five, "close": five} or None.
    A rotation without 48 minutes of bigs gets small-ball fives too."""
    return _plan(team, True) or _plan(team, False)


def _plan(team, need_big):
    n = len(team["min"])
    if n < 5:
        return None
    fives = [f for f in itertools.combinations(range(n), 5) if valid([team["pos"][i] for i in f], need_big)]
    if not fives:
        return None
    st = tuple(sorted(team.get("starters") or []))
    if len(st) != 5:
        st = tuple(sorted(np.argsort(-team["min"])[:5].tolist()))
    if st not in fives:
        fives.append(st)
    scores = [strength(team, f) for f in fives]
    net = np.array([s[0] for s in scores])
    core = [k for k, f in enumerate(fives) if all(team["min"][i] >= CLOSER_MIN for i in f)]
    close = fives[max(core, key=lambda k: net[k])] if core else st      # the best five of the regulars
    F = len(fives)
    # variables: minutes per five (F), then each player's shortfall (n)
    c = np.concatenate([-net, np.full(n, SHORT_COST)])
    A_eq = np.zeros((1, F + n)); A_eq[0, :F] = 1
    b_eq = [48.0]
    A_ub, b_ub = [], []
    for p in range(n):                                   # minutes(p) + shortfall(p) >= projection, minutes(p) <= projection
        row = np.zeros(F + n)
        for k, f in enumerate(fives):
            if p in f:
                row[k] = 1
        lo = -row.copy(); lo[F + p] = -1
        A_ub.append(lo); b_ub.append(-float(team["min"][p]))
        A_ub.append(row); b_ub.append(float(team["min"][p]) + 0.5)
    bounds = []
    for f in fives:
        lo = (START_MIN if f == st else 0.0) + (CLOSE_MIN if f == close else 0.0)
        hi = max(lo, CAP_START if f in (st, close) else CAP_OTHER)
        bounds.append((lo, hi))
    bounds += [(0, None)] * n
    res = linprog(c, A_ub=np.array(A_ub), b_ub=np.array(b_ub), A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if not res.success:
        return None
    t = res.x[:F]
    units = sorted(((fives[k], float(t[k]), *scores[k]) for k in range(F) if t[k] > 0.05), key=lambda u: -u[1])
    return {"units": units, "start": st, "close": close}


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

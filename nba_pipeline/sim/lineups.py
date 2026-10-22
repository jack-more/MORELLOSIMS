"""Tonight's lineup plan: which fives play, and for how long.

The plan is the coach's real lineups, as close to how he plays them as tonight's
roster allows:

  real      a five of tonight's rotation that has shared the floor keeps the minutes
            per game the coach gave it in the games all five played (recent games
            count most, games the same regulars missed count triple)
  swap      a real five with one player who isn't in tonight's rotation (out, traded,
            cut) is played with the teammate who actually took his minutes in the
            games he missed in that player's place; with no such games (he left
            before the newcomer arrived), the same-position teammate with the most
            minutes tonight
  starters  tonight's announced starting five
  new       only the minutes the three above cannot cover inside each player's
            projected minutes, and never for looking strong on paper

The minutes are solved as a linear program: real minutes first, then swaps,
then new fives only where player minutes demand them, subject to

  - every player's projected minutes (soft: a miss either way costs more than any five gains)
  - 48 minutes in all
  - the starters together long enough to open both halves, the closing five (the
    strongest real or swap five of the regulars) long enough to close
  - no unit beyond a realistic stint total (the starting five 20, any other 9) unless
    the coach plays it more
  - new fives: one to three guards, at least one big, at most two centers (relaxed
    only if the rotation can't fill 48 minutes otherwise)

A team whose real fives and starters cover under THIN_MIN minutes is flagged thin:
too little lineup history to price, so no pick on it.

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
REAL_BONUS = 25.0                         # per minute of a real five's own minutes
SWAP_BONUS = 15.0                         # per minute of a swap five's (its real five's) minutes
NEW_COST = 8.0                            # per minute of a five the coach has never played
NEW_TIE = 0.1                             # new fives: strength only breaks ties
HALF_LIFE = 20                            # team games: the coach's recent lineups count most
LIKE_TONIGHT = 3.0                        # a game the same regulars missed tells most about tonight
SEEN_MIN = 0.5                            # minutes per game for a five to count as one the coach plays
TOOK_MIN = 2.0                            # minutes a teammate gained in a player's absences to count as his replacement
THIN_MIN = 24.0                           # real plus starters minutes below this: too thin to price


def valid(pos, need_big=True):
    g = sum(p in GUARDS for p in pos)
    b = sum(p in BIGS for p in pos)
    c = sum(p == "C" for p in pos)
    return 1 <= g <= 3 and (b >= 1 or not need_big) and c <= 2


def _replacements(games, pids, minutes, pos_of):
    """{player not in tonight's rotation: [rotation players, likeliest replacement first]}:
    measured by the minutes each teammate gained in the games he missed (both on the
    team, at least 2 such games); else same-position teammates, most minutes tonight first."""
    mins = [collections.defaultdict(float) for _ in games]
    for g, (_d, _played, fives) in zip(mins, games):
        for f, m in fives.items():
            for p in f:
                g[p] += m
    span = {}
    for j, (_d, played, _f) in enumerate(games):
        for p in played:
            span[p] = (span[p][0], j) if p in span else (j, j)
    rot = set(pids)
    tonight = dict(zip(pids, minutes))
    out = {}
    for x in span.keys() - rot:
        took = {}
        for r in pids:
            if r not in span:
                continue
            lo, hi = max(span[x][0], span[r][0]), min(span[x][1], span[r][1])
            if lo > hi:
                continue
            gone = [mins[j][r] for j in range(lo, hi + 1) if x not in games[j][1]]
            here = [mins[j][r] for j in range(lo, hi + 1) if x in games[j][1]]
            if len(gone) >= 2 and len(here) >= 3:
                took[r] = np.mean(gone) - np.mean(here)
        ranked = sorted((r for r in took if took[r] >= TOOK_MIN), key=lambda r: -took[r])
        px = pos_of(x)
        ranked += sorted((r for r in pids if r not in ranked and px and pos_of(r) == px), key=lambda r: -tonight[r])
        out[x] = ranked
    return out


def history(games, pids, minutes, gone=(), pos_of=lambda p: ""):
    """(real, swaps) for tonight's rotation from this team's lineup history (context.
    lineup_history rows, only games before tonight).
      real:  {bitmask of rotation indices: minutes per game} the coach gave each five in
             the games all five played
      swaps: {bitmask: (minutes per game, missing player, replacement)} a real five with
             one player not in tonight's rotation, played with his replacement instead
    gone: tonight's missing regulars; minutes: tonight's projected minutes (pids order)."""
    idx = {p: i for i, p in enumerate(pids)}
    gone = set(gone)
    allp = {}                                             # every player in the history: a bit each
    for _d, played, _f in games:
        for p in played:
            allp.setdefault(p, len(allp))
    num = collections.defaultdict(float)                  # five (bits over allp) -> weighted minutes
    den = collections.defaultdict(float)                  # players who played (bits over allp) -> weight
    k = len(games)
    for j, (_date, played, fives) in enumerate(games):
        w = 0.5 ** ((k - 1 - j) / HALF_LIFE) * (LIKE_TONIGHT if gone and not gone & played else 1.0)
        den[sum(1 << allp[p] for p in played)] += w
        for f, m in fives.items():
            if sum(p not in idx for p in f) <= 1:
                num[f] += w * m
    rep = None
    real, swaps = {}, collections.defaultdict(lambda: [0.0, None, None])
    for f, s in num.items():
        F = sum(1 << allp[p] for p in f)
        d = sum(w for M, w in den.items() if M & F == F)
        if d <= 0 or s / d < SEEN_MIN:
            continue
        miss = [p for p in f if p not in idx]
        if not miss:
            real[sum(1 << idx[p] for p in f)] = s / d
            continue
        if rep is None:
            rep = _replacements(games, pids, minutes, pos_of)
        x = miss[0]
        four = [p for p in f if p != x]
        r = next((r for r in rep.get(x, []) if r not in four), None)
        if r is None:
            continue
        sw = swaps[sum(1 << idx[p] for p in four + [r])]
        sw[0] += s / d
        if sw[1] is None or s / d > sw[0] / 2:            # name the swap after its biggest source
            sw[1], sw[2] = x, r
    return real, {m: tuple(v) for m, v in swaps.items() if m not in real}


def strength(team, five):
    """(net per 100, impact part, chemistry part) of one five."""
    imp = float(sum(team["off"][i] + team["def"][i] for i in five))
    pairs = SYN_SHARE * float(sum(team["V"][a, b] for a, b in itertools.combinations(five, 2)))
    unit = float(team["U"][sum(1 << i for i in five)])
    return imp + pairs + unit, imp, pairs + unit


def plan(team):
    """{"units": [(five, minutes, net, impact, chemistry)], "start": five, "close": five,
    "kind": {five: real / swap / starters / new}, "played": {five: the coach's minutes per
    game (a swap: its real five's)}, "swap": {five: (missing player, replacement)},
    "mix": {kind: minutes}, "thin": bool} or None (fewer than five players)."""
    return _plan(team, True) or _plan(team, False) or _plan(team, None)


def _plan(team, need_big):
    n = len(team["min"])
    if n < 5:
        return None
    H, SW = team.get("H") or {}, team.get("SW") or {}
    mask = lambda f: sum(1 << i for i in f)
    st = tuple(sorted(team.get("starters") or []))
    if len(st) != 5:
        st = tuple(sorted(np.argsort(-team["min"])[:5].tolist()))
    kind = {}
    for f in itertools.combinations(range(n), 5):
        m = mask(f)
        if m in H:
            kind[f] = "real"
        elif m in SW:
            kind[f] = "swap"
        elif f == st:
            kind[f] = "starters"
        elif need_big is None or valid([team["pos"][i] for i in f], need_big):
            kind[f] = "new"
    fives = list(kind)
    scores = [strength(team, f) for f in fives]
    net = np.array([s[0] for s in scores])
    h = np.array([H.get(mask(f), SW.get(mask(f), (0.0,))[0] if mask(f) in SW else 0.0) for f in fives])
    core = [k for k, f in enumerate(fives) if all(team["min"][i] >= CLOSER_MIN for i in f)]
    known = [k for k in core if kind[fives[k]] in ("real", "swap")]
    close = fives[max(known, key=lambda k: net[k])] if known else st     # the strongest real five of the regulars
    F = len(fives)
    cap = np.array([48.0 if need_big is None else max(h[k], CAP_START if f in (st, close) else CAP_OTHER)
                    for k, f in enumerate(fives)])
    # variables: each five's minutes within its history (F), beyond it (F), then each
    # player's shortfall (n) and excess (n) against his projection
    within_r = np.array([{"real": REAL_BONUS, "swap": SWAP_BONUS}.get(kind[f], 0.0) for f in fives])
    beyond = np.array([net[k] if kind[f] in ("real", "starters") else
                       net[k] - NEW_COST / 2 if kind[f] == "swap" else NEW_TIE * net[k] - NEW_COST
                       for k, f in enumerate(fives)])
    c = np.concatenate([-(net + within_r), -beyond, np.full(2 * n, SHORT_COST)])
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
    mix = collections.Counter()
    for f, m, *_ in units:
        mix["real" if kind[f] == "starters" else kind[f]] += m
    return {"units": units, "start": st, "close": close,
            "kind": {f: kind[f] for f, *_ in units},
            "played": {fives[k]: float(h[k]) for k in range(F) if h[k] > 0},
            "swap": {f: SW[mask(f)][1:] for f, *_ in units if kind[f] == "swap"},
            "mix": {k_: round(v, 1) for k_, v in mix.items()}, "thin": mix["real"] < THIN_MIN}


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

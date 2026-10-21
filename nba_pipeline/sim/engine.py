"""The game: 5,000 simulations of every possession, run side by side with numpy.

Each possession, for the team with the ball:
  1. the five on the floor: tonight's rotation, sampled per two-minute segment
     so each player plays his projected minutes on average
  2. who ends it: one of the five, by usage
  3. turnover? his own rate
  4. how: a play type from his own mix (PnR ball handler, spot-up, cut, ...)
  5. what it's worth: his PPP on that play type, times what the five defenders
     allow on it (the ones who usually guard that action weigh most), plus the
     on-floor impact edge (offense RAPM/LEBRON of the five minus the defense's)
  6. a two or a three, made or missed; a miss can be rebounded by the offense
     (its five's OREB share against the defense's DREB share) for a putback
Home court is added per possession. A tie goes to overtime.
"""

import numpy as np

from sim.players import TYPES

SEGMENTS = 24                 # two-minute stretches; the floor five is re-drawn each one
OT_POSS = 10                  # possessions per team in an overtime
TO_OREB = TYPES.index("OffRebound")


def _lineups(rng, minutes, S, iters=4):
    """(S, SEGMENTS, 5) player indices on the floor. Gumbel top-5 draws, with the
    weights tuned so each player's share of segments matches his minutes / 48."""
    target = np.clip(minutes / 48.0, 1e-3, 0.999)
    logw = np.log(target)
    n = len(minutes)
    for _ in range(iters):
        g = logw + rng.gumbel(size=(4000, n))
        top = np.argsort(-g, axis=1)[:, :5]
        share = np.bincount(top.ravel(), minlength=n) / 4000.0
        logw += np.log(target / np.clip(share, 1e-3, None))
    g = logw + rng.gumbel(size=(S, SEGMENTS, n))
    return np.argsort(-g, axis=2)[:, :, :5]


def _pick(rng, probs):
    """One index per row of a (S, k) probability array."""
    c = np.cumsum(probs, axis=1)
    r = rng.random(len(probs))[:, None] * c[:, -1:]
    return np.minimum((c < r).sum(axis=1), probs.shape[1] - 1)


def _possession(rng, o, d, on, dn, active, mult, impact_w, lg, pts, box):
    """One possession for every sim where `active`; adds into pts (S,) and box (S, n)."""
    S = len(on)
    rows = np.arange(S)
    j = _pick(rng, o["uw"][on])
    who = on[rows, j]
    tov = rng.random(S) < o["tov"][who]
    t = _pick(rng, o["mix"][who])
    edge = (o["off"][on].sum(1) - d["def"][dn].sum(1)) * impact_w / 100.0
    oreb = o["oreb"][on].sum(1)
    dreb = d["dreb"][dn].sum(1)
    p_or = oreb / (oreb + dreb)
    live = active & ~tov
    for attempt in range(3):                              # the shot, then up to two putbacks
        wt, dp = d["dwt"][dn, t[:, None]], d["dppp"][dn, t[:, None]]
        guard = (wt * dp).sum(1) / wt.sum(1)
        e = o["ppp"][who, t] * guard * mult + edge
        three = rng.random(S) < o["p3"][who, t]
        make = np.clip(np.where(three, e / 3.0, e / 2.0), 0.02, 0.98)
        made = live & (rng.random(S) < make)
        got = np.where(three, 3, 2) * made
        pts += got
        np.add.at(box, (rows, who), got)
        live = live & ~made & (rng.random(S) < p_or)      # offensive rebound: go again
        if not live.any():
            break
        who = on[rows, _pick(rng, o["oreb"][on])]          # the rebounder puts it back
        t = np.full(S, TO_OREB)


def simulate(home, away, lg, sims=5000, seed=7, pace=None, hca=1.68, impact_w=0.5, scale=1.0):
    """{margin, home_pts, away_pts, home_box, away_box}; margin = home - away."""
    rng = np.random.default_rng(seed)
    S = sims
    pace = pace or lg["pace"]
    poss = np.maximum(80, np.rint(rng.normal(pace, 3.0, S))).astype(int)
    lh, la = _lineups(rng, home["min"], S), _lineups(rng, away["min"], S)
    # home court: points per game split evenly across both teams' possessions
    hm = scale * (1 + hca / 2 / (pace * lg["ortg"] / 100))
    am = scale * (1 - hca / 2 / (pace * lg["ortg"] / 100))
    hp, ap = np.zeros(S), np.zeros(S)
    hbox, abox = np.zeros((S, len(home["min"]))), np.zeros((S, len(away["min"])))
    rows = np.arange(S)
    for k in range(poss.max()):
        seg = np.minimum(k * SEGMENTS // poss, SEGMENTS - 1)
        act = k < poss
        on_h, on_a = lh[rows, seg], la[rows, seg]
        _possession(rng, home, away, on_h, on_a, act, hm, impact_w, lg, hp, hbox)
        _possession(rng, away, home, on_a, on_h, act, am, impact_w, lg, ap, abox)
    for _ in range(3):                                    # overtime, closing lineups
        tied = hp == ap
        if not tied.any():
            break
        on_h, on_a = lh[:, -1], la[:, -1]
        for _ in range(OT_POSS):
            _possession(rng, home, away, on_h, on_a, tied, hm, impact_w, lg, hp, hbox)
            _possession(rng, away, home, on_a, on_h, tied, am, impact_w, lg, ap, abox)
    still = hp == ap                                      # a third OT tie: coin flip
    hp += still * (rng.random(S) < 0.5)
    ap += still & ~(hp > ap)
    return {"margin": hp - ap, "home_pts": hp, "away_pts": ap, "home_box": hbox, "away_box": abox}


def average_team(lg, n=10):
    """A league-average five-deep-twice: the opponent for calibration."""
    T = len(TYPES)
    mix = np.array([0.20, 0.08, 0.22, 0.16, 0.07, 0.05, 0.04, 0.04, 0.04, 0.05, 0.05])
    ppp = np.array([lg["off_ppp"].get(t, 1.0) for t in TYPES])
    from sim.players import THREE_SHAPE, TYPE_TOV
    return {"min": np.full(n, 24.0), "usg": np.full(n, 0.2), "uw": np.full(n, 0.2), "tov": np.full(n, lg["tov"]),
            "mix": np.tile(mix / mix.sum(), (n, 1)),
            "ppp": np.tile(ppp / (1 - np.array([TYPE_TOV[t] for t in TYPES])), (n, 1)),
            "p3": np.tile([THREE_SHAPE[t] for t in TYPES], (n, 1)),
            "dppp": np.ones((n, T)), "dwt": np.ones((n, T)),
            "oreb": np.full(n, lg["oreb"]), "dreb": np.full(n, lg["dreb"]),
            "off": np.zeros(n), "def": np.zeros(n)}

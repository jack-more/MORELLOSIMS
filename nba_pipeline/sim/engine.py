"""The game: 5,000 simulations of every possession, run side by side with numpy.

Each possession, for the team with the ball:
  1. the five on the floor: tonight's rotation, sampled per two-minute segment
     so each player plays his projected minutes on average
  2. who ends it: one of the five, by usage
  3. turnover? his own rate
  4. how: a play type from his own mix (PnR ball handler, spot-up, cut, ...)
  5. what it's worth: his PPP on that play type, times
       - defense: what the five defenders allow on it (the ones who usually
         guard that action weigh most), blended with what the defending
         team's scheme allows on that play type
       - spacing: the five's shooting gravity against an average five, on
         the plays that need room (cuts, rolls, posts, drives)
       - load: his share of the floor's possessions against his full-strength
         share, along his own usage-efficiency curve
       - fatigue: heavy minutes cost efficiency, more on a back-to-back
     plus the impact edge (offense RAPM/LEBRON of the five minus the
     defense's) and the pair synergy edge (WOWY / archetype fit of each five)
  6. a two or a three, made or missed; a miss can be rebounded by the offense
     (its five's OREB share against the defense's DREB share) for a putback
Home court and back-to-backs are added per possession. A tie goes to overtime.
"""

import itertools

import numpy as np

from sim import lineups
from sim.context import SYN_SHARE
from sim.players import TYPES

SEGMENTS = 24                 # two-minute stretches; the floor five is re-drawn each one
OT_POSS = 10                  # possessions per team in an overtime
TO_OREB = TYPES.index("OffRebound")
PAIRS = list(itertools.combinations(range(5), 2))

# spacing: PPP change per unit of floor gravity above an average five (one
# high-volume shooter is ~1 unit). Priors from the old model's 1-MOJO-per-shooter
# penalty on rim runners and cutters; the backtest refits them.
SPACING = {"Cut": 0.04, "PRRollMan": 0.04, "Postup": 0.03, "PRBallHandler": 0.025,
           "Isolation": 0.025, "Handoff": 0.015, "Transition": 0.01}
BETA = np.array([SPACING.get(t, 0.0) for t in TYPES])
SCHEME_W = 0.30               # team scheme's share of the defense read; the five defenders carry the rest
LOAD_TS = 57.0                # league TS%, to turn TS points into an efficiency ratio
LOAD_LO, LOAD_HI = 0.88, 1.05
FATIGUE_FROM, FATIGUE_PER_MIN, B2B_FATIGUE_FROM = 34.0, 0.01, 32.0
# back-to-back: points per game on top of the fatigue layer's B2B legs. Home from the old
# model's OLS (generate_frontend._MOJI_CONSTANTS); road refit on the 2025-26 point-in-time
# backtest, where 2.5 left road B2B teams 1.76 better than the sim had them (214 games)
B2B_HOME, B2B_ROAD = 2.0, 0.75
LAYERS = ("lineups", "load", "spacing", "pairs", "scheme", "fatigue")   # simulate(off=...) switches any of them off


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


def _floor(team, lineups, lg):
    """Per (sim, segment): the five's spacing over average, and its synergy (points per 100)."""
    space = team["g"][lineups].sum(-1) - lg["spacing"]
    V = team["V"]
    syn = sum(V[lineups[..., a], lineups[..., b]] for a, b in PAIRS) * SYN_SHARE
    syn = syn + team["U"][(1 << lineups).sum(-1)]          # the unit's own track record
    return space, syn


def _possession(rng, o, d, on, dn, ctx, active, mult, impact_w, pts, box):
    """One possession for every sim where `active`; adds into pts (S,) and box (S, n).
    ctx: (spacing of the offense's five, its synergy, the defense's synergy), each (S,)."""
    space, syn_o, syn_d = ctx
    S = len(on)
    rows = np.arange(S)
    uw = o["uw"][on]
    j = _pick(rng, uw)
    who = on[rows, j]
    # load: tonight's share of the floor's possessions vs his full-strength share
    extra = (uw[rows, j] / uw.sum(1) - o["s_norm"][who]) * 100
    load = np.clip(1 + o["slope"][who] * extra / LOAD_TS, LOAD_LO, LOAD_HI)
    tov = rng.random(S) < o["tov"][who]
    t = _pick(rng, o["mix"][who])
    edge = ((o["off"][on].sum(1) - d["def"][dn].sum(1)) * impact_w + (syn_o - syn_d) / 2) / 100.0
    oreb = o["oreb"][on].sum(1)
    dreb = d["dreb"][dn].sum(1)
    p_or = oreb / (oreb + dreb)
    live = active & ~tov
    for attempt in range(3):                              # the shot, then up to two putbacks
        wt, dp = d["dwt"][dn, t[:, None]], d["dppp"][dn, t[:, None]]
        guard = (1 - d["scheme_w"]) * (wt * dp).sum(1) / wt.sum(1) + d["scheme_w"] * d["tdef"][t]
        e = o["ppp"][who, t] * guard * (1 + BETA[t] * space) * load * o["fat"][who] * mult + edge
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
        load = 1.0


def _fatigue(team, b2b):
    start = B2B_FATIGUE_FROM if b2b else FATIGUE_FROM
    return 1 - FATIGUE_PER_MIN * np.maximum(0.0, team["min"] - start)


def simulate(home, away, lg, sims=5000, seed=7, pace=None, hca=1.68, impact_w=0.5, scale=1.0,
             home_b2b=False, away_b2b=False, off=()):
    """{margin, home_pts, away_pts, home_box, away_box}; margin = home - away.
    off: layers to switch off (LAYERS), to see what each one is worth."""
    rng = np.random.default_rng(seed)
    S = sims
    pace = pace or lg["pace"]
    ppg = pace * lg["ortg"] / 100
    poss = np.maximum(80, np.rint(rng.normal(pace, 3.0, S))).astype(int)
    # the lineup plan (sim/lineups.py): the coach's own fives; only with the layer switched
    # off (to measure it) are fives drawn by minutes alone
    def fives(team):
        if team.get("plan") and "lineups" not in off:
            return lineups.draw(rng, team["plan"], S, SEGMENTS)
        return _lineups(rng, team["min"], S)
    lh, la = fives(home), fives(away)
    sp_h, syn_h = _floor(home, lh, lg)
    sp_a, syn_a = _floor(away, la, lg)
    if "spacing" in off:
        sp_h, sp_a = sp_h * 0, sp_a * 0
    if "pairs" in off:
        syn_h, syn_a = syn_h * 0, syn_a * 0
    if "fatigue" in off:
        home_b2b = away_b2b = False
    def ready(team, b2b):
        return dict(team, fat=np.ones(len(team["min"])) if "fatigue" in off else _fatigue(team, b2b),
                    slope=team["slope"] * 0 if "load" in off else team["slope"],
                    scheme_w=0.0 if "scheme" in off else SCHEME_W)
    home, away = ready(home, home_b2b), ready(away, away_b2b)
    # home court and back-to-backs: points per game, half on each end, spread over possessions
    swing = hca - (B2B_HOME if home_b2b else 0.0) + (B2B_ROAD if away_b2b else 0.0)
    hm = scale * (1 + swing / 2 / ppg)
    am = scale * (1 - swing / 2 / ppg)
    hp, ap = np.zeros(S), np.zeros(S)
    hbox, abox = np.zeros((S, len(home["min"]))), np.zeros((S, len(away["min"])))
    rows = np.arange(S)
    for k in range(poss.max()):
        seg = np.minimum(k * SEGMENTS // poss, SEGMENTS - 1)
        act = k < poss
        on_h, on_a = lh[rows, seg], la[rows, seg]
        ch = (sp_h[rows, seg], syn_h[rows, seg], syn_a[rows, seg])
        ca = (sp_a[rows, seg], syn_a[rows, seg], syn_h[rows, seg])
        _possession(rng, home, away, on_h, on_a, ch, act, hm, impact_w, hp, hbox)
        _possession(rng, away, home, on_a, on_h, ca, act, am, impact_w, ap, abox)
    for _ in range(3):                                    # overtime, closing lineups
        tied = hp == ap
        if not tied.any():
            break
        on_h, on_a = lh[:, -1], la[:, -1]
        ch = (sp_h[:, -1], syn_h[:, -1], syn_a[:, -1])
        ca = (sp_a[:, -1], syn_a[:, -1], syn_h[:, -1])
        for _ in range(OT_POSS):
            _possession(rng, home, away, on_h, on_a, ch, tied, hm, impact_w, hp, hbox)
            _possession(rng, away, home, on_a, on_h, ca, tied, am, impact_w, ap, abox)
    still = hp == ap                                      # a third OT tie: coin flip
    hp += still * (rng.random(S) < 0.5)
    ap += still & ~(hp > ap)
    return {"margin": hp - ap, "home_pts": hp, "away_pts": ap, "home_box": hbox, "away_box": abox,
            "home_lineups": lh, "away_lineups": la, "home_syn_grid": syn_h, "away_syn_grid": syn_a,
            "home_spacing": float(sp_h.mean()), "away_spacing": float(sp_a.mean()),
            "home_syn": float(syn_h.mean()), "away_syn": float(syn_a.mean())}


def average_team(lg, n=10):
    """A league-average ten-man rotation: the opponent for calibration."""
    T = len(TYPES)
    mix = np.array([0.20, 0.08, 0.22, 0.16, 0.07, 0.05, 0.04, 0.04, 0.04, 0.05, 0.05])
    ppp = np.array([lg["off_ppp"].get(t, 1.0) for t in TYPES])
    from sim.players import THREE_SHAPE, TYPE_TOV
    return {"min": np.full(n, 24.0), "usg": np.full(n, 0.2), "uw": np.full(n, 0.2), "tov": np.full(n, lg["tov"]),
            "mix": np.tile(mix / mix.sum(), (n, 1)),
            "ppp": np.tile(ppp / (1 - np.array([TYPE_TOV[t] for t in TYPES])), (n, 1)),
            "p3": np.tile([THREE_SHAPE[t] for t in TYPES], (n, 1)),
            "dppp": np.ones((n, T)), "dwt": np.ones((n, T)), "tdef": np.ones(T),
            "oreb": np.full(n, lg["oreb"]), "dreb": np.full(n, lg["dreb"]),
            "off": np.zeros(n), "def": np.zeros(n),
            "s_norm": np.full(n, 0.2), "slope": np.zeros(n), "g": np.full(n, lg["spacing"] / 5),
            "V": np.zeros((n, n)), "U": np.zeros(1 << n)}

"""Player roles as continuous scores, the same on every team and every season.

The K-Means archetypes (analysis/archetypes.py) are refit per listed position
each season, so a label is a name for one season's cluster: 2024-25 had 75
"Stretch Forward" and no "3-and-D Wing", 2025-26 had 43 and 38. A label also
says nothing about how much of a role a player fills. The spread model needs
both: who replaces an OUT player's minutes, and whether tonight's rotation
still has someone to run the offense, space the floor and protect the rim.

Every player gets five scores from his per-36 / rate line, each a z-score
against the league's rotation players (or a 0-1 scale for size):

  creator  on-ball load: usage and assists
  spacer   three-point volume, with accuracy shrunk toward league average
  rim      shot blocking
  glass    rebounding
  size     0 (guard) to 1 (center): listed position blended with a stat
           read of where he plays (boards and blocks up, threes and assists
           down), so a G-F who rebounds like a forward reads as one

`project_minutes` uses size and creator similarity to decide who absorbs an
OUT player's minutes; `team_coverage` sums roles over tonight's projected
minutes. Both are checked in scripts/backtest_roles.py (2025-26 walk-forward).
Coverage is not in the spread: fit on games before Feb 1, its terms made
February-April margins worse (correlation with the talent model's misses
-0.16), and so did the role lost to absences (-0.08).
"""

import math

import pandas as pd

ROLES = ("creator", "spacer", "rim", "glass")

# Listed position -> size prior (rosters list G / F / C, older ones G-F etc.)
POSITION_SIZE = {
    "PG": 0.0, "G": 0.1, "SG": 0.2, "G-F": 0.3, "F-G": 0.4, "SF": 0.45,
    "F": 0.55, "PF": 0.7, "F-C": 0.8, "C-F": 0.85, "C": 1.0,
}

# Line columns the scores read (player_season_stats names)
FEATURES = ("usg_pct", "ast_per36", "fg3a_per36", "fg3_pct", "blk_per36", "reb_per36")

# 3P% shrinkage: attempts per 36 worth of a league-average prior
FG3_PRIOR_ATTEMPTS = 3.0

# Substitution, gridded on 2025-26 games before Feb 1 and checked after
# (scripts/backtest_roles.py): minutes go to teammates in proportion to their
# own minutes x (SUB_FLOOR + (1 - SUB_FLOOR) x role similarity).
SUB_SIZE_SCALE = 0.25    # size gap at which similarity falls to e^-1
SUB_CREATOR_SCALE = 3.0  # creator z gap at which similarity falls to e^-1
SUB_FLOOR = 0.0          # share of the weight that ignores role entirely
# Players picked up 0.2-0.26 of the minutes the old split handed them: a
# season average already carries the nights a teammate sat, and the bench
# outside the rotation takes the rest. Best of 0.15 / 0.25 / 0.35 / 0.5.
ABSORB = 0.25            # share of an OUT player's minutes the rotation picks up
MAX_MINUTES = 40.0


def _num(v, default=0.0):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(f) else f


def fit_reference(df: pd.DataFrame, min_minutes_pg: float = 12.0) -> dict:
    """League mean / sd of each feature over rotation players in `df`
    (one row per player, player_season_stats columns)."""
    pool = df[df["minutes_per_game"].fillna(0) >= min_minutes_pg]
    if len(pool) < 30:
        pool = df
    ref = {}
    for f in FEATURES:
        vals = pd.to_numeric(pool[f], errors="coerce").dropna()
        ref[f] = (float(vals.mean()), float(vals.std() or 1.0)) if len(vals) else (0.0, 1.0)
    return ref


def _z(line: dict, f: str, ref: dict) -> float:
    mu, sd = ref[f]
    return (_num(line.get(f), mu) - mu) / sd if sd else 0.0


def role_scores(line: dict, ref: dict) -> dict:
    """{creator, spacer, rim, glass, size} for one player line."""
    z = {f: _z(line, f, ref) for f in FEATURES}
    # 3P%: shrink toward league average by volume before it counts
    fg3a = _num(line.get("fg3a_per36"))
    mu3, sd3 = ref["fg3_pct"]
    w = fg3a / (fg3a + FG3_PRIOR_ATTEMPTS) if fg3a > 0 else 0.0
    fg3_shrunk = w * _num(line.get("fg3_pct"), mu3) + (1 - w) * mu3
    z_acc = (fg3_shrunk - mu3) / sd3 if sd3 else 0.0

    stat_big = (z["reb_per36"] + z["blk_per36"] - 0.5 * z["fg3a_per36"] - 0.5 * z["ast_per36"]) / 2.0
    stat_size = 1.0 / (1.0 + math.exp(-1.6 * stat_big))
    pos = str(line.get("listed_position") or "").strip().upper()
    size = 0.5 * POSITION_SIZE[pos] + 0.5 * stat_size if pos in POSITION_SIZE else stat_size

    return {
        "creator": 0.5 * z["usg_pct"] + 0.5 * z["ast_per36"],
        "spacer": 0.7 * z["fg3a_per36"] + 0.3 * z_acc,
        "rim": z["blk_per36"],
        "glass": z["reb_per36"],
        "size": size,
    }


def similarity(a: dict, b: dict) -> float:
    """0-1: how well player b fills player a's spot (size first, then on-ball load)."""
    ds = (a["size"] - b["size"]) / SUB_SIZE_SCALE
    dc = (a["creator"] - b["creator"]) / SUB_CREATOR_SCALE
    return math.exp(-(ds * ds + dc * dc))


def project_minutes(base_minutes: dict, out_ids, roles: dict,
                    floor: float = SUB_FLOOR, cap: float = MAX_MINUTES,
                    absorb: float = ABSORB, fresh: dict = None) -> dict:
    """{player_id: projected minutes} for the available players.

    Each OUT player's minutes go to available teammates in proportion to
    their own minutes x (floor + (1 - floor) x similarity to him), so a
    missing center's minutes land on the other bigs and a missing point
    guard's on the ball handlers. Minutes a player can't take past `cap`
    pass to the rest by the same weights. Players without role scores get
    similarity 0.5 (neutral). floor = 1, absorb = 1 is the old split.

    Only `absorb` x the OUT minutes are handed out, and of those only the
    `fresh` share (games he played of the team's recent games, default 1):
    a season average already carries the nights a teammate sat, and the
    deep bench outside the rotation takes some of the rest."""
    out_ids = set(out_ids)
    avail = {p: _num(m) for p, m in base_minutes.items() if p not in out_ids and _num(m) > 0}
    proj = dict(avail)
    if not avail:
        return {}
    for o in out_ids:
        m = _num(base_minutes.get(o)) * absorb * (fresh.get(o, 1.0) if fresh else 1.0)
        if m <= 0:
            continue
        ro = roles.get(o)
        w = {}
        for p, bm in avail.items():
            rp = roles.get(p)
            sim = similarity(ro, rp) if ro and rp else 0.5
            w[p] = bm * (floor + (1.0 - floor) * sim)
        left = m
        for _ in range(4):  # spill minutes past the cap to everyone else
            open_w = {p: wt for p, wt in w.items() if proj[p] < cap - 1e-9}
            tot = sum(open_w.values())
            if left <= 1e-9 or tot <= 0:
                break
            spill = 0.0
            for p, wt in open_w.items():
                add = left * wt / tot
                room = cap - proj[p]
                if add > room:
                    spill += add - room
                    add = room
                proj[p] += add
            left = spill
    return proj


def team_coverage(minutes: dict, roles: dict) -> dict:
    """Minutes-weighted role z-scores over the floor (240 player-minutes).

    Also the best creator's score among players getting 20+ minutes
    (`top_creator`): a rotation can average out fine and still have nobody
    to run the offense."""
    tot = sum(minutes.values()) or 1.0
    scale = 240.0 / tot if tot > 240.0 else 1.0
    cov = {r: 0.0 for r in ROLES}
    for p, m in minutes.items():
        rp = roles.get(p)
        if not rp:
            continue
        for r in ROLES:
            cov[r] += rp[r] * m * scale / 240.0
    starters = [roles[p]["creator"] for p, m in minutes.items() if m >= 20 and p in roles]
    cov["top_creator"] = max(starters) if starters else 0.0
    return cov


def roles_for_frame(df: pd.DataFrame, ref: dict) -> dict:
    """{player_id: role scores} for every row of a roster-like frame."""
    return {int(r["player_id"]): role_scores(r, ref) for r in df.to_dict("records")}


__all__ = [
    "ROLES", "fit_reference", "role_scores", "similarity", "project_minutes",
    "team_coverage", "roles_for_frame",
]

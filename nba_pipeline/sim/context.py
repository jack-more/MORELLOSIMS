"""League-wide context the possession sim reads, loaded once per run.

  pairs          pair synergy from ESPN five-man stints (real possession
                 counts): how much the stints a pair shares beat their five
                 players' own impacts, over the team's average, shrunk by how
                 much of it the data says is noise
  archetype fit  the same, pooled over every pair of the two archetypes: the
                 prior for teammates who have never shared the floor
  load curves    each player's TS change per point of extra usage
                 (player_potential, the curves the old model read)
  gravity        3PA volume x 3P%: what a shooter does to spacing
  team defense   each team's PPP allowed per play type over league (its scheme)
"""

import collections
import itertools
import re

import numpy as np

from config import CURRENT_SEASON, previous_season

# per-possession scoring variance of a margin: a net rating over n possessions
# (both ends) carries ~ NOISE / n of variance in points per 100
NOISE = 100 ** 2 * 5.2

_CACHE = {}


def _net(v):
    return 100 * (v[0] / v[2] - v[1] / v[3]) if v[2] > 0 and v[3] > 0 else 0.0


def _tau2(est, noise, floor):
    """Signal variance by method of moments: what the spread holds beyond noise."""
    return max(floor, float(np.mean(np.square(est) - noise)))


def impacts(con):
    """{player_id: offense + defense impact per 100}: RAPM and LEBRON averaged (players.py's read)."""
    if "impacts" not in _CACHE:
        out = {}
        for pid, ro, rd, lo, ld in con.execute(
                "SELECT player_id, rapm_offense, rapm_defense, lebron_offense, lebron_defense FROM player_rapm"):
            off = [x for x in (ro, lo) if x is not None]
            dfn = [x for x in (rd, ld) if x is not None]
            out[int(pid)] = (np.mean(off) if off else 0.0) + (np.mean(dfn) if dfn else 0.0)
        _CACHE["impacts"] = out
    return _CACHE["impacts"]


def pairs(con):
    """({(a, b): synergy per 100}, {(arch, arch): prior per 100}, {player: archetype}, notes).

    Every ESPN five-man stint is scored against what its five players' own
    impacts predict (net per 100 minus their summed RAPM/LEBRON) and against its
    team's average surplus, so team strength and teammate quality are out of it.
    A pair's synergy is the surplus of the stints it shares; an archetype
    pairing's is the same pooled over every such pair. Both are shrunk by how
    much of their spread the data says is noise (method of moments)."""
    if "pairs" in _CACHE:
        return _CACHE["pairs"]
    seasons = (CURRENT_SEASON, previous_season(CURRENT_SEASON))
    emap = {str(e): p for e, p in con.execute("SELECT espn_id, player_id FROM espn_player_map")}
    imp = impacts(con)
    team = collections.defaultdict(lambda: np.zeros(2))
    pair = collections.defaultdict(lambda: np.zeros(2))
    for r in con.execute(
            "SELECT l.team_id, l.e1, l.e2, l.e3, l.e4, l.e5, l.pts, l.opp_pts, l.poss, l.opp_poss "
            "FROM espn_lineup_games l JOIN espn_team_games g ON g.game_id=l.game_id AND g.team_id=l.team_id "
            "WHERE g.season_id IN (?,?)", seasons):
        ps = sorted(p for p in (emap.get(str(e)) for e in r[1:6]) if p)
        n = (r[8] or 0) + (r[9] or 0)
        if len(ps) < 5 or n <= 0:
            continue
        resid = 100 * ((r[6] or 0) - (r[7] or 0)) / (n / 2) - sum(imp.get(p, 0.0) for p in ps)
        team[r[0]] += (resid * n, n)
        for a, b in itertools.combinations(ps, 2):
            pair[(a, b, r[0])] += (resid * n, n)
    raw = {}
    for (a, b, tid), (s, n) in pair.items():
        if n < 200:
            continue
        ex = s / n - team[tid][0] / team[tid][1]
        z = NOISE / n
        if (a, b) in raw:                                # teammates on more than one team: pool
            e0, z0 = raw[(a, b)]
            w0, w1 = 1 / z0, 1 / z
            raw[(a, b)] = ((e0 * w0 + ex * w1) / (w0 + w1), 1 / (w0 + w1))
        else:
            raw[(a, b)] = (ex, z)
    arch = {int(p): a for p, a in con.execute(
        "SELECT player_id, archetype_label FROM player_archetypes WHERE season_id=?", (CURRENT_SEASON,))}
    est = np.array([e for e, _ in raw.values()])
    nz = np.array([z for _, z in raw.values()])
    tau2 = _tau2(est, nz, 0.25)
    pool = collections.defaultdict(lambda: [0.0, 0.0])
    for (a, b), (ex, z) in raw.items():
        if a in arch and b in arch:
            k = tuple(sorted((arch[a], arch[b])))
            pool[k][0] += ex / z
            pool[k][1] += 1 / z
    cm = {k: (s / w, 1 / w) for k, (s, w) in pool.items()}
    ctau2 = _tau2(np.array([m for m, _ in cm.values()]), np.array([z for _, z in cm.values()]), 0.04)
    prior = {k: m * ctau2 / (ctau2 + z) for k, (m, z) in cm.items()}
    syn = {}
    for (a, b), (ex, z) in raw.items():
        p0 = prior.get(tuple(sorted((arch.get(a, ""), arch.get(b, "")))), 0.0)
        syn[(a, b)] = p0 + (ex - p0) * tau2 / (tau2 + z)
    notes = {"pairs": len(raw), "pair_sd": round(float(np.sqrt(tau2)), 2),
             "fit_sd": round(float(np.sqrt(ctau2)), 2), "fit_pairings": len(prior)}
    _CACHE["pairs"] = (syn, prior, arch, notes)
    return _CACHE["pairs"]


def load_curves(con):
    """{player_id: TS points per usage point}, the old model's parse of player_potential."""
    if "curves" not in _CACHE:
        out = {}
        for pid, notes in con.execute(
                "SELECT player_id, notes FROM player_potential "
                "WHERE snapshot_date=(SELECT MAX(snapshot_date) FROM player_potential) AND notes IS NOT NULL"):
            m = re.search(r"TS ([+-]?\d+\.?\d*)%/USG%", notes or "")
            if m:
                out[int(pid)] = float(m.group(1))
        _CACHE["curves"] = out
    return _CACHE["curves"]


def gravity(fg3_pct, fg3a_per36):
    """0 for a non-shooter, ~1 for a high-volume 38% shooter, up to 1.4."""
    vol = min(1.0, (fg3a_per36 or 0) / 7.0)
    acc = min(1.4, max(0.0, ((fg3_pct or 0) - 0.31) / 0.07))
    return vol * acc


def team_defense(con, team_id, lg_def):
    """{play_type: team PPP allowed / league}, shrunk; the defending scheme's fingerprint."""
    key = ("tdef", team_id)
    if key not in _CACHE:
        out = {}
        for season in (CURRENT_SEASON, previous_season(CURRENT_SEASON)):
            rows = con.execute("SELECT play_type, ppp, possessions FROM team_playtypes "
                               "WHERE team_id=? AND season_id=? AND type_grouping='Defensive'",
                               (team_id, season)).fetchall()
            if rows:
                for t, ppp, n in rows:
                    base = lg_def.get(t) or np.mean([r[1] for r in rows])
                    n = (n or 0) * 82                            # per-game possessions over a season
                    out[t] = ((ppp or base) * n + base * 300) / (n + 300) / base
                break
        _CACHE[key] = out
    return _CACHE[key]


def league_team_defense(con, season):
    """League PPP allowed per play type, from the team table (covers every type)."""
    key = ("lgdef", season)
    if key not in _CACHE:
        _CACHE[key] = {t: p for t, p in con.execute(
            "SELECT play_type, AVG(ppp) FROM team_playtypes WHERE season_id=? AND type_grouping='Defensive' "
            "GROUP BY play_type", (season,))}
    return _CACHE[key]

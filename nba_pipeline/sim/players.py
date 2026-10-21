"""Player inputs for the possession sim, all from nba_sim.db.

Everything is per player and follows the player to his current team
(roster_assignments), so a rebuilt roster is priced from who is on it, not
from what last season's team did. Rates are shrunk toward the league by
sample size, so twelve possessions of a play type can't make a player elite.

  rotation      tonight's minutes: last season's role, OUT players removed,
                RotoWire's starters at a starter's load, scaled to 240
  usage         share of on-floor possessions he ends (ESPN boxes)
  tov           turnovers per possession he ends
  play types    his offensive mix and PPP per Synergy play type
  defense       PPP he allows per defensive play type (7 types)
  shooting      3PA share of his shots
  rebounding    his share of his team's OREB / DREB chances on the floor
  impact        steadied offense / defense impact: RAPM and LEBRON splits
  load          his usage-efficiency curve and his usage share at full strength
  gravity       what his shooting does to spacing (sim/context.py)
  pairs         WOWY synergy with each teammate, archetype fit when they never played
  scheme        the team's PPP allowed per play type (its defensive scheme)
"""

import itertools
import os
import sqlite3
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CURRENT_SEASON, DB_PATH, previous_season  # noqa: E402
from sim import context  # noqa: E402

# Synergy offensive play types; the order is the column order everywhere
TYPES = ["PRBallHandler", "Isolation", "Spotup", "Transition", "Cut", "PRRollMan",
         "Postup", "Handoff", "OffScreen", "OffRebound", "Misc"]
# defensive play types tracked per defender; offense types without one fall back to his average
DEF_OF = {"PRBallHandler": "PRBallHandler", "Isolation": "Isolation", "Spotup": "Spotup",
          "PRRollMan": "PRRollMan", "Postup": "Postup", "Handoff": "Handoff", "OffScreen": "OffScreen"}
# share of a play type's shots that are threes (league shape; the player's own 3PA rate scales it)
THREE_SHAPE = {"PRBallHandler": 0.38, "Isolation": 0.30, "Spotup": 0.70, "Transition": 0.33,
               "Cut": 0.0, "PRRollMan": 0.06, "Postup": 0.05, "Handoff": 0.45, "OffScreen": 0.55,
               "OffRebound": 0.08, "Misc": 0.15}
# turnover share inside a play type's PPP (Synergy counts the TOV in it); removed before the
# shot so the player's own turnover rate isn't counted twice
TYPE_TOV = {"PRBallHandler": 0.15, "Isolation": 0.09, "Spotup": 0.05, "Transition": 0.13,
            "Cut": 0.07, "PRRollMan": 0.10, "Postup": 0.12, "Handoff": 0.12, "OffScreen": 0.08,
            "OffRebound": 0.06, "Misc": 0.25}

K_PLAYTYPE = 60.0       # pseudo-possessions of league average behind every play-type PPP
K_BOX = 400.0           # pseudo-possessions behind usage / TOV / 3PA / rebounding rates
ROTATION = 10           # players who get minutes
STARTER_MIN = 28.0      # a RotoWire starter's floor
MAX_MIN = 38.0
# >1: the floor five defers to its high-usage players. 1.5 fits real scoring across usage tiers
# (sim.validate, 274 players: 1.0 left the 30%+ usage stars 4.3 pts/36 short, 1.6 is flat, 2.2 overshoots)
USG_POWER = float(os.environ.get("SIM_USG_POWER", "1.5"))
# usage curves are game-level slopes, noisy: half of each, held inside these bounds
# (TS points per usage point; the old model's default for a player without one was -0.5)
CURVE_SHRINK, CURVE_LO, CURVE_HI, CURVE_DEFAULT = 0.5, -1.25, 0.25, -0.5


def _db():
    return sqlite3.connect(DB_PATH)


def league(con=None):
    """League averages the shrinkage pulls toward."""
    con = con or _db()
    seasons = (CURRENT_SEASON, previous_season(CURRENT_SEASON))
    off, dfn = {}, {}
    for grouping, out in (("Offensive", off), ("Defensive", dfn)):
        for t, ppp, share in con.execute(
                "SELECT play_type, SUM(ppp*possessions)/SUM(possessions), SUM(possessions) "
                "FROM player_playtypes WHERE season_id IN (?,?) AND type_grouping=? GROUP BY play_type",
                (*seasons, grouping)):
            out[t] = ppp
    r = con.execute(
        "SELECT SUM(fg3a)*1.0/SUM(fga), SUM(tov)*1.0/SUM(fga+0.44*fta+tov), "
        "SUM(oreb)*1.0/SUM(on_oreb+on_opp_dreb), SUM(dreb)*1.0/SUM(on_dreb+on_opp_oreb), "
        "SUM(pts)*1.0/SUM(fga+0.44*fta+tov) "
        "FROM espn_player_games WHERE season_id IN (?,?) AND dnp=0", seasons).fetchone()
    ortg, pace = con.execute(
        "SELECT AVG(off_rating), AVG(pace) FROM team_season_stats WHERE season_id=?",
        (previous_season(CURRENT_SEASON),)).fetchone()
    g = [(context.gravity(f3, a36), m) for f3, a36, m in con.execute(
        "SELECT fg3_pct, fg3a_per36, minutes_total FROM player_season_stats "
        "WHERE season_id=? AND gp >= 20", (previous_season(CURRENT_SEASON),))]
    spacing = 5 * sum(x * m for x, m in g) / sum(m for _, m in g)      # an average five's gravity
    return {"off_ppp": off, "def_ppp": dfn, "fg3_share": r[0], "tov": r[1], "oreb": r[2],
            "dreb": r[3], "pts_per_use": r[4], "ortg": ortg, "pace": pace, "spacing": spacing,
            "team_def": context.league_team_defense(con, previous_season(CURRENT_SEASON))}


def _shrink(x, n, prior, k):
    return (x * n + prior * k) / (n + k) if n else prior


def _box(con, pid):
    """Usage, TOV, 3PA share and rebounding from every ESPN game since last season."""
    r = con.execute(
        "SELECT SUM(fga), SUM(fta), SUM(tov), SUM(fg3a), SUM(off_poss), SUM(oreb), SUM(dreb), "
        "SUM(on_oreb+on_opp_dreb), SUM(on_dreb+on_opp_oreb), SUM(pts) FROM espn_player_games "
        "WHERE player_id=? AND season_id IN (?,?) AND dnp=0",
        (pid, CURRENT_SEASON, previous_season(CURRENT_SEASON))).fetchone()
    return [x or 0 for x in r]


def _playtypes(con, pid, grouping):
    """{type: (share, ppp, total possessions)} from the newest season that has him."""
    for season in (CURRENT_SEASON, previous_season(CURRENT_SEASON)):
        rows = con.execute(
            "SELECT pt.play_type, pt.poss_pct, pt.ppp, pt.possessions * COALESCE(ps.gp, 1) "
            "FROM player_playtypes pt LEFT JOIN player_season_stats ps "
            "ON ps.player_id=pt.player_id AND ps.season_id=pt.season_id "
            "WHERE pt.player_id=? AND pt.season_id=? AND pt.type_grouping=?", (pid, season, grouping)).fetchall()
        if rows:
            return {t: (s or 0.0, p or 0.0, n or 0.0) for t, s, p, n in rows}
    return {}


def _impact(con, pid):
    """(offense, defense) points per 100 possessions: RAPM and LEBRON splits averaged,
    so one noisy RAPM season is half the read."""
    r = con.execute("SELECT rapm_offense, rapm_defense, lebron_offense, lebron_defense "
                    "FROM player_rapm WHERE player_id=?", (pid,)).fetchone()
    if not r:
        return 0.0, 0.0
    off = [x for x in (r[0], r[2]) if x is not None]
    dfn = [x for x in (r[1], r[3]) if x is not None]
    return (float(np.mean(off)) if off else 0.0, float(np.mean(dfn)) if dfn else 0.0)


def rotation(roster, out_ids, starters=()):
    """{player_id: minutes} for tonight: OUT players gone, starters at a starter's load,
    the top ROTATION by role, scaled to 240."""
    avail = [(int(r.player_id), float(r.minutes_per_game or 0)) for r in roster.itertuples()
             if int(r.player_id) not in out_ids]
    starters = set(starters)
    first = sorted([(p, max(m, STARTER_MIN)) for p, m in avail if p in starters], key=lambda x: -x[1])[:5]
    rest = sorted([(p, m) for p, m in avail if p not in starters], key=lambda x: -x[1])
    mins = dict(first + rest[:ROTATION - len(first)])
    for _ in range(4):                                   # scale to 240 with the cap holding
        free = [p for p, m in mins.items() if m < MAX_MIN]
        total = sum(mins.values())
        if abs(total - 240) < 0.01 or not free:
            break
        fixed = sum(m for p, m in mins.items() if p not in free)
        scale = (240 - fixed) / sum(mins[p] for p in free)
        for p in free:
            mins[p] = min(MAX_MIN, mins[p] * scale)
    return mins


def team_inputs(roster, out_ids, starters=(), lg=None, con=None, abbr=None):
    """Arrays the engine runs on, one row per rotation player."""
    con = con or _db()
    lg = lg or league(con)
    mins = rotation(roster, out_ids, starters)
    names = dict(zip(roster.player_id.astype(int), roster.full_name))
    usg = {int(p): float(u) for p, u in zip(roster.player_id, roster.usg_pct) if u and u == u}
    pids = list(mins)
    n, T = len(pids), len(TYPES)
    out = {"pids": pids, "names": [names.get(p, str(p)) for p in pids],
           "min": np.array([mins[p] for p in pids]), "usg": np.zeros(n), "tov": np.zeros(n),
           "mix": np.zeros((n, T)), "ppp": np.zeros((n, T)), "p3": np.zeros((n, T)),
           "dppp": np.zeros((n, T)), "dwt": np.zeros((n, T)), "oreb": np.zeros(n), "dreb": np.zeros(n),
           "off": np.zeros(n), "def": np.zeros(n)}
    for i, pid in enumerate(pids):
        fga, fta, tov, fg3a, poss, oreb, dreb, ochances, dchances, pts = _box(con, pid)
        used = fga + 0.44 * fta + tov
        # usage: the season line (this season's games over his multi-season prior), else his ESPN rate
        out["usg"][i] = usg.get(pid) or _shrink(used / poss if poss else 0.2, poss, 0.20, K_BOX)
        out["tov"][i] = _shrink(tov / used if used else lg["tov"], used, lg["tov"], K_BOX / 4)
        share3 = _shrink(fg3a / fga if fga else lg["fg3_share"], fga, lg["fg3_share"], K_BOX / 4)
        out["oreb"][i] = _shrink(oreb / ochances if ochances else lg["oreb"], ochances, lg["oreb"], K_BOX / 4)
        out["dreb"][i] = _shrink(dreb / dchances if dchances else lg["dreb"], dchances, lg["dreb"], K_BOX / 4)
        out["off"][i], out["def"][i] = _impact(con, pid)
        offpt = _playtypes(con, pid, "Offensive")
        defpt = _playtypes(con, pid, "Defensive")
        mix = np.array([offpt.get(t, (0, 0, 0))[0] for t in TYPES]) + 0.01
        out["mix"][i] = mix / mix.sum()
        dvals = []
        for j, t in enumerate(TYPES):
            s, p, k = offpt.get(t, (0, 0, 0))
            base = lg["off_ppp"].get(t, 1.0)
            out["ppp"][i, j] = _shrink(p, k, base, K_PLAYTYPE) / (1 - TYPE_TOV[t])
            out["p3"][i, j] = min(0.95, THREE_SHAPE[t] * share3 / lg["fg3_share"])
            d = DEF_OF.get(t)
            if d:
                ds, dp, dk = defpt.get(d, (0, 0, 0))
                dbase = lg["def_ppp"].get(d, 1.0)
                out["dppp"][i, j] = _shrink(dp, dk, dbase, K_PLAYTYPE) / dbase
                out["dwt"][i, j] = dk + 5.0                  # who usually guards this action
                dvals.append(out["dppp"][i, j])
        # level: the play-type mix sets how he scores; his box score sets how well
        # (points per possession he ends, shrunk toward the league)
        per_use = _shrink(pts / used if used else lg["pts_per_use"], used, lg["pts_per_use"], K_BOX)
        model = (1 - out["tov"][i]) * float(out["mix"][i] @ out["ppp"][i])
        if model > 0:
            out["ppp"][i] *= per_use / model
        avg = float(np.mean(dvals)) if dvals else 1.0
        for j, t in enumerate(TYPES):
            if t not in DEF_OF:
                out["dppp"][i, j], out["dwt"][i, j] = avg, 1.0
    out["uw"] = out["usg"] ** USG_POWER

    # load: his share of the floor's possessions at full strength, against which
    # tonight's share (a star out, a low-usage five) moves his efficiency along his curve
    full = rotation(roster, set(), ())
    full_uw = {p: (usg.get(p) or 0.2) ** USG_POWER for p in full}
    floor_uw = sum(full_uw[p] * m / 48.0 for p, m in full.items())
    curves = context.load_curves(con)
    out["s_norm"] = out["uw"] / floor_uw
    out["slope"] = np.array([min(CURVE_HI, max(CURVE_LO, CURVE_SHRINK * curves.get(p, CURVE_DEFAULT)))
                             for p in pids])
    # gravity
    shoot = {int(p): (f, a) for p, f, a in con.execute(
        f"SELECT player_id, fg3_pct, fg3a_per36 FROM player_season_stats WHERE season_id=? "
        f"AND player_id IN ({','.join('?' * n)})", (CURRENT_SEASON, *pids))}
    out["g"] = np.array([context.gravity(*shoot.get(p, (0, 0))) for p in pids])
    # pairs: WOWY synergy, archetype fit for teammates without a shared history
    syn, prior, arch, _ = context.pairs(con)
    V = np.zeros((n, n))
    for a, b in itertools.combinations(range(n), 2):
        k = (min(pids[a], pids[b]), max(pids[a], pids[b]))
        v = syn.get(k)
        if v is None:
            v = prior.get(tuple(sorted((arch.get(pids[a], ""), arch.get(pids[b], "")))), 0.0)
        V[a, b] = V[b, a] = v
    out["V"] = V
    # scheme: what this team allows per play type
    tid = con.execute("SELECT team_id FROM teams WHERE abbreviation=?", (abbr,)).fetchone() if abbr else None
    tdef = context.team_defense(con, tid[0], lg["team_def"]) if tid else {}
    out["tdef"] = np.array([tdef.get(t, 1.0) for t in TYPES])
    return out

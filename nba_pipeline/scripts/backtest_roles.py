"""Walk-forward backtest of the role layer (analysis/roles.py) on 2025-26.

Every regular-season game is replayed in date order with only what was known
before tip: each player's line is his 2024-25 season blended with his 2025-26
games so far (15-game prior, as generate_frontend does), and the night's OUT
list is every recent rotation player who didn't play (what RotoWire hands the
live model). Two questions:

1. Minutes. When rotation players sit, who gets their minutes? Compares the
   live split (in proportion to minutes, generate_frontend.project_minutes)
   with the role-aware split against the minutes players actually played.

2. Margin. Does tonight's role coverage (creation, spacing, rim protection,
   rebounding) explain final margins beyond player talent? Talent is
   sum(RAPM x projected minutes / 48) per side plus home court; the role
   terms are fit on games before FIT_CUTOFF and scored after it.

RAPM comes from player_rapm, a current snapshot that already includes
2025-26, so the talent baseline is stronger than anything known before those
games. That makes it harder, not easier, for the role terms to add anything.

Usage: python scripts/backtest_roles.py [--db path]
"""

import argparse
import os
import sqlite3
import sys
from collections import defaultdict, deque

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis import roles as R  # noqa: E402

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "nba_sim.db")
SEASON, PRIOR_SEASON = "2025-26", "2024-25"
PRIOR_GAMES = 15
RECENT_GAMES = 10       # a player is in the rotation pool if he played in the team's last 10
ROTATION_MPG = 5.0      # generate_frontend's rotation cut
OUT_MPG = 12.0          # an absence the injury report would carry (a 7-mpg DNP-CD isn't one)
MIN_OUT_MINUTES = 15.0  # minutes test: team-games missing at least this many rotation minutes
FIT_CUTOFF = "2026-02-01"
REPLACEMENT_RAPM = -2.0  # players with no RAPM row


def load(db):
    con = sqlite3.connect(db)
    box = pd.read_sql(
        """SELECT e.game_id, e.game_date, e.team_id, e.player_id, e.sec, e.dnp,
                  e.fga, e.fta, e.tov, e.ast, e.fg3a, e.fg3m, e.blk, e.reb, e.off_poss,
                  g.home_team_id, g.away_team_id, g.home_score, g.away_score
           FROM espn_player_games e JOIN games g USING (game_id)
           WHERE e.season_id = ? AND e.season_type = 2 AND g.home_score IS NOT NULL
           ORDER BY e.game_date, e.game_id""", con, params=[SEASON])
    prior = pd.read_sql("SELECT * FROM player_season_stats WHERE season_id = ?", con, params=[PRIOR_SEASON])
    pos = pd.read_sql(
        """SELECT player_id, listed_position, season_id FROM roster_assignments
           WHERE season_id IN (?, ?) AND listed_position IS NOT NULL AND listed_position != ''""",
        con, params=[SEASON, PRIOR_SEASON])
    rapm = pd.read_sql("SELECT player_id, rapm_total FROM player_rapm WHERE rapm_total IS NOT NULL", con)
    con.close()
    pos = pos.sort_values("season_id", ascending=False).drop_duplicates("player_id")
    return box, prior, dict(zip(pos.player_id, pos.listed_position)), dict(zip(rapm.player_id, rapm.rapm_total))


class Player:
    """Season-to-date totals; line() blends them with the prior."""

    __slots__ = ("gp", "min", "fga", "fta", "tov", "ast", "fg3a", "fg3m", "blk", "reb", "poss")

    def __init__(self):
        for s in self.__slots__:
            setattr(self, s, 0.0)

    def add(self, r):
        m = r.sec / 60.0
        if m <= 0:
            return
        self.gp += 1
        self.min += m
        for s in ("fga", "fta", "tov", "ast", "fg3a", "fg3m", "blk", "reb"):
            setattr(self, s, getattr(self, s) + (getattr(r, s) or 0))
        self.poss += r.off_poss or 0

    def line(self, prior):
        cur = None
        if self.gp and self.min > 0:
            p36 = 36.0 / self.min
            cur = {
                "minutes_per_game": self.min / self.gp,
                "usg_pct": (self.fga + 0.44 * self.fta + self.tov) / self.poss if self.poss else None,
                "ast_per36": self.ast * p36, "fg3a_per36": self.fg3a * p36,
                "fg3_pct": self.fg3m / self.fg3a if self.fg3a else None,
                "blk_per36": self.blk * p36, "reb_per36": self.reb * p36,
            }
        if prior is None:
            return cur
        if cur is None:
            return dict(prior)
        out = {}
        for k in cur:
            pv, cv = prior.get(k), cur[k]
            if pv is None or (isinstance(pv, float) and np.isnan(pv)):
                out[k] = cv
            elif cv is None:
                out[k] = pv
            elif k == "minutes_per_game":
                out[k] = (self.gp * cv + PRIOR_GAMES * pv) / (self.gp + PRIOR_GAMES)
            else:  # rates weigh by minutes
                wc, wp = self.min, PRIOR_GAMES * (prior.get("minutes_per_game") or 0)
                out[k] = (wc * cv + wp * pv) / (wc + wp) if wc + wp else cv
        return out


# name -> (floor, absorb, scale by fresh share). "live" is generate_frontend's split.
VARIANTS = {
    "none": (1.0, 0.0, False),
    "live": (1.0, 1.0, False),
    "prop": (1.0, R.ABSORB, True),
    "role": (R.SUB_FLOOR, R.ABSORB, True),
}
LABELS = {
    "none": "no redistribution (base minutes)",
    "live": "proportional, all minutes (live)",
    "prop": f"proportional, absorb {R.ABSORB}",
    "role": f"role-aware, absorb {R.ABSORB}",
}


def replay(box, prior_df, positions, rapm, variants=VARIANTS):
    """Walk the season. Returns (minutes rows, game rows)."""
    ref = R.fit_reference(prior_df)
    prior = {int(r["player_id"]): {k: r[k] for k in ("minutes_per_game",) + R.FEATURES}
             for r in prior_df.to_dict("records")}
    players = defaultdict(Player)
    last_team = {}
    team_recent = defaultdict(lambda: deque(maxlen=RECENT_GAMES))  # sets of player ids who played
    minute_rows, game_rows = [], []

    for gid, g in box.groupby("game_id", sort=False):
        g0 = g.iloc[0]
        sides = {}
        for tid, tg in g.groupby("team_id"):
            played = {int(r.player_id): r.sec / 60.0 for r in tg.itertuples() if r.sec > 0}
            pool = set().union(*team_recent[tid]) if team_recent[tid] else set()
            pool = {p for p in pool if last_team.get(p) == tid} | set(played)
            lines, roles, base = {}, {}, {}
            for p in pool:
                ln = players[p].line(prior.get(p)) if (p in players or p in prior) else None
                if not ln or not ln.get("minutes_per_game"):
                    continue
                ln = dict(ln, listed_position=positions.get(p))
                lines[p] = ln
                roles[p] = R.role_scores(ln, ref)
                base[p] = float(ln["minutes_per_game"])
            rot = {p: m for p, m in base.items() if m > ROTATION_MPG}
            out = [p for p in rot if p not in played and rot[p] >= OUT_MPG]
            rot = {p: m for p, m in rot.items() if p in played or p in out}  # bench DNPs drop out
            out_min = sum(rot[p] for p in out)
            recent = list(team_recent[tid])
            fresh = {p: (sum(p in s for s in recent) / len(recent) if recent else 1.0) for p in out}
            proj = {k: R.project_minutes(rot, out, roles, floor=fl, absorb=ab, fresh=fresh if fr else None)
                    for k, (fl, ab, fr) in variants.items()}
            if out_min >= MIN_OUT_MINUTES:
                for p in rot:
                    if p in played:
                        minute_rows.append(dict(game_id=gid, team_id=tid, player_id=p, date=g0.game_date,
                                                actual=played[p], base=rot[p], out_min=out_min,
                                                **{f"proj_{k}": proj[k].get(p, rot[p]) for k in proj}))
            full = R.team_coverage(rot, roles)  # everyone in, season minutes
            sides[tid] = dict(proj=proj, roles=roles, played=played, out_min=out_min, full=full)
            # update state after the game
            team_recent[tid].append(set(played))
            for r in tg.itertuples():
                players[int(r.player_id)].add(r)
                if r.sec > 0:
                    last_team[int(r.player_id)] = tid

        h, a = int(g0.home_team_id), int(g0.away_team_id)
        if h not in sides or a not in sides:
            continue
        row = dict(game_id=gid, date=g0.game_date, margin=float(g0.home_score - g0.away_score))
        for tag, side in (("h", sides[h]), ("a", sides[a])):
            for f in side["proj"]:
                mins = side["proj"][f]
                # minutes the rotation doesn't take go to the bench at replacement level
                bench = max(0.0, 240.0 - sum(mins.values()))
                scale = 240.0 / max(240.0, sum(mins.values()))
                row[f"{tag}_str_{f}"] = (sum(rapm.get(p, REPLACEMENT_RAPM) * m * scale for p, m in mins.items())
                                         + REPLACEMENT_RAPM * bench) / 48.0
                cov = R.team_coverage(mins, side["roles"])
                for k, v in cov.items():
                    row[f"{tag}_{k}_{f}"] = v
            act = side["played"]
            row[f"{tag}_str_actual"] = sum(rapm.get(p, REPLACEMENT_RAPM) * m / 48.0 * 240.0 / max(240.0, sum(act.values()))
                                           for p, m in act.items())
            row[f"{tag}_n"] = len(act)
            for k, v in side["full"].items():  # role lost to tonight's absences
                row[f"{tag}_{k}_loss"] = row[f"{tag}_{k}_role"] - v
            row[f"{tag}_out_min"] = side["out_min"]
        game_rows.append(row)
    return pd.DataFrame(minute_rows), pd.DataFrame(game_rows)


def minutes_report(m):
    n = m.groupby(["game_id", "team_id"]).ngroups
    print(f"\n== Minutes: {n} team-games missing >= {MIN_OUT_MINUTES:.0f} rotation minutes, "
          f"{len(m)} player-games of the players who did play ==")
    first = m.date < FIT_CUTOFF
    key = m.game_id + "_" + m.team_id.astype(str)
    gain = m.actual - m.base
    print(f"{'method':<36}{'MAE':>6}{'fit':>7}{'test':>7}   routing corr")
    for k, label in LABELS.items():
        pred = m[f"proj_{k}"]
        err = (pred - m.actual).abs()
        add = pred - m.base
        # routing: within a team-game, do the players handed the most minutes gain the most?
        a_dm, g_dm = add - add.groupby(key).transform("mean"), gain - gain.groupby(key).transform("mean")
        corr = f"{np.corrcoef(a_dm, g_dm)[0, 1]:+.3f}" if a_dm.std() > 0 else "   n/a"
        print(f"{label:<36}{err.mean():6.2f}{err[first].mean():7.2f}{err[~first].mean():7.2f}   {corr}")


def _fit(X, y, ridge=0.0):
    X1 = np.column_stack([np.ones(len(X)), X])
    pen = ridge * np.eye(X1.shape[1])
    pen[0, 0] = 0
    return np.linalg.solve(X1.T @ X1 + pen, X1.T @ y)


def _pred(beta, X):
    return np.column_stack([np.ones(len(X)), X]) @ beta


def margin_report(gm, ridge=50.0):
    keys = list(R.ROLES) + ["top_creator"]
    tr, te = gm[gm.date < FIT_CUTOFF], gm[gm.date >= FIT_CUTOFF]
    print(f"\n== Margin: fit {len(tr)} games before {FIT_CUTOFF}, test {len(te)} after ==")

    def feats(d, mk, with_roles):
        cols = [d[f"h_str_{mk}"] - d[f"a_str_{mk}"]]
        if with_roles:
            cols += [d[f"h_{k}_{mk}"] - d[f"a_{k}_{mk}"] for k in keys]
        return np.column_stack(cols)

    beta_roles = None
    for name, mk, wr in [("RAPM talent x live minutes", "live", False),
                         ("RAPM talent x role-aware minutes", "role", False),
                         ("  + role coverage terms", "role", True),
                         ("(oracle: minutes actually played)", "actual", False)]:
        beta = _fit(feats(tr, mk, wr), tr.margin.values, ridge if wr else 0.0)
        p = _pred(beta, feats(te, mk, wr))
        err = p - te.margin.values
        print(f"  {name:<36} MAE {np.abs(err).mean():6.3f}  RMSE {np.sqrt((err ** 2).mean()):6.3f}  "
              f"winner {np.mean(np.sign(p) == np.sign(te.margin.values)):.3f}")
        if wr:
            beta_roles = beta
    print("  role terms, points per unit of home-away gap: " +
          ", ".join(f"{k} {b:+.2f}" for k, b in zip(keys, beta_roles[2:])))
    # role terms' own out-of-sample value, on the residual of the talent model
    b0 = _fit(feats(tr, "role", False), tr.margin.values)
    res_tr = tr.margin.values - _pred(b0, feats(tr, "role", False))
    res_te = te.margin.values - _pred(b0, feats(te, "role", False))
    Xr_tr = np.column_stack([tr[f"h_{k}_role"] - tr[f"a_{k}_role"] for k in keys])
    Xr_te = np.column_stack([te[f"h_{k}_role"] - te[f"a_{k}_role"] for k in keys])
    br = _fit(Xr_tr, res_tr, ridge)
    print(f"  role terms on talent residual: test corr {np.corrcoef(_pred(br, Xr_te), res_te)[0, 1]:+.3f}")
    # role LOST to tonight's absences (tonight's coverage minus full strength)
    Xl_tr = np.column_stack([tr[f"h_{k}_loss"] - tr[f"a_{k}_loss"] for k in keys])
    Xl_te = np.column_stack([te[f"h_{k}_loss"] - te[f"a_{k}_loss"] for k in keys])
    bl = _fit(Xl_tr, res_tr, ridge)
    print(f"  role lost to absences on talent residual: test corr {np.corrcoef(_pred(bl, Xl_te), res_te)[0, 1]:+.3f}  "
          f"({', '.join(f'{k} {v:+.2f}' for k, v in zip(keys, bl[1:]))})")
    # paired: does role-aware routing beat the live split game by game?
    bl0 = _fit(feats(tr, "live", False), tr.margin.values)
    d = np.abs(_pred(b0, feats(te, "role", False)) - te.margin.values) - np.abs(_pred(bl0, feats(te, "live", False)) - te.margin.values)
    print(f"  role-aware minus live minutes, paired MAE gap {d.mean():+.3f} (se {d.std() / np.sqrt(len(d)):.3f})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB)
    args = ap.parse_args()
    box, prior_df, positions, rapm = load(args.db)
    m, gm = replay(box, prior_df, positions, rapm)
    minutes_report(m)
    margin_report(gm)


if __name__ == "__main__":
    main()

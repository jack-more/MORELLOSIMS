"""Point-in-time player impact (RAPM) for the backtest: offense and defense per 100
possessions, fit only on ESPN five-man stints played before the date.

Each game's five-man stint for a team gives two rows:
  offense  its points per 100 of its possessions  = c + sum(o_p) + opp defense + home
  defense  opponent points per 100 of theirs      = c - sum(d_p) + opp offense - home
weighted by possessions, ridge toward 0 for players (LAM) and lightly for the opponent
team effects, so a player's number is what his units did beyond the opponents they
faced. The sums are kept cumulative by date, so a fit at any date is one solve.

  python3 -m sim.pit_rapm --tune     # pick LAM on out-of-sample stints
"""

import argparse
import collections
import os
import sqlite3
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH  # noqa: E402

LAM = 3000.0          # possessions of shrinkage toward 0 per player (tuned: --tune)
LAM_TEAM = 300.0
SEASON = "2025-26"


class PitRapm:
    def __init__(self, con, season=SEASON):
        emap = {str(e): int(p) for e, p in con.execute("SELECT espn_id, player_id FROM espn_player_map")}
        rows = con.execute(
            "SELECT g.game_date, l.team_id, g.opp_team_id, g.is_home, l.e1, l.e2, l.e3, l.e4, l.e5, "
            "l.pts, l.opp_pts, l.poss, l.opp_poss FROM espn_lineup_games l JOIN espn_team_games g "
            "ON g.game_id=l.game_id AND g.team_id=l.team_id WHERE g.season_id=? AND g.counts_regular=1 "
            "ORDER BY g.game_date", (season,)).fetchall()
        self.players, self.teams = {}, {}
        self.by_date = collections.defaultdict(list)
        for d, tid, opp, home, *es, pts, opts, poss, oposs in rows:
            ps = [emap.get(str(e)) for e in es]
            if None in ps or not poss or not oposs:
                continue
            for p in ps:
                self.players.setdefault(p, len(self.players))
            for t in (tid, opp):
                self.teams.setdefault(t, len(self.teams))
            self.by_date[d].append((ps, opp, 1.0 if home else -1.0, pts or 0, opts or 0, poss, oposs))
        self.np_, self.nt = len(self.players), len(self.teams)
        self.k = self.np_ + self.nt + 2                     # players, opponent teams, home, intercept
        self.dates = sorted(self.by_date)
        self.A = {"o": np.zeros((self.k, self.k)), "d": np.zeros((self.k, self.k))}
        self.b = {"o": np.zeros(self.k), "d": np.zeros(self.k)}
        self.n_poss = collections.Counter()
        self._upto = 0                                      # dates [0, _upto) are in the sums

    def _add(self, d):
        for ps, opp, home, pts, opts, poss, oposs in self.by_date[d]:
            cols = [self.players[p] for p in ps] + [self.np_ + self.teams[opp], self.k - 2, self.k - 1]
            x = np.array([1.0] * 5 + [1.0, home, 1.0])
            for side, y, w in (("o", 100.0 * pts / poss, poss), ("d", 100.0 * opts / oposs, oposs)):
                xx = x.copy()
                if side == "d":
                    xx[6] = -home
                self.A[side][np.ix_(cols, cols)] += w * np.outer(xx, xx)
                self.b[side][cols] += w * y * xx
            for p in ps:
                self.n_poss[p] += poss + oposs

    def _advance(self, D):
        while self._upto < len(self.dates) and self.dates[self._upto] < D:
            self._add(self.dates[self._upto])
            self._upto += 1

    def fit(self, D, lam=LAM):
        """{player_id: (offense, defense)} per 100 from stints before D (defense: + is good)."""
        self._advance(D)
        reg = np.zeros(self.k)
        reg[:self.np_] = lam
        reg[self.np_:self.np_ + self.nt] = LAM_TEAM
        out = {}
        coef = {}
        for side in ("o", "d"):
            A = self.A[side] + np.diag(reg)
            coef[side] = np.linalg.solve(A + 1e-6 * np.eye(self.k), self.b[side])
        for p, i in self.players.items():
            if self.n_poss[p] > 0:
                out[p] = (float(coef["o"][i]), float(-coef["d"][i]))
        return out


def _tune():
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    r = PitRapm(con)
    # fit on games before each cut, score the next month's stints (net per 100, poss-weighted)
    for cut, end in (("2025-12-15", "2026-01-15"), ("2026-02-01", "2026-03-01"), ("2026-03-15", "2026-04-13")):
        held = [row for d in r.dates if cut <= d < end for row in r.by_date[d]]
        line = []
        for lam in (500, 1000, 2000, 3000, 5000, 8000, 15000):
            imp = PitRapm.fit(r, cut, lam)
            err = wsum = 0.0
            for ps, opp, home, pts, opts, poss, oposs in held:
                pred = sum(imp.get(p, (0, 0))[0] + imp.get(p, (0, 0))[1] for p in ps)
                act = 100.0 * pts / poss - 100.0 * opts / oposs
                w = (poss + oposs) / 2
                err += w * (act - pred) ** 2
                wsum += w
            line.append(f"lam {lam}: rmse {np.sqrt(err / wsum):.2f}")
        base = np.sqrt(sum((poss + oposs) / 2 * (100.0 * pts / poss - 100.0 * opts / oposs) ** 2
                           for ps, opp, home, pts, opts, poss, oposs in held) / sum((poss + oposs) / 2 for *_, poss, oposs in held))
        print(f"{cut}..{end} ({len(held)} stints, zero-impact rmse {base:.2f}): " + "; ".join(line))
        imp = PitRapm.fit(r, cut, LAM)
        top = sorted(imp.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:8]
        names = dict(con.execute("SELECT player_id, full_name FROM players"))
        print("   top:", ", ".join(f"{names.get(p, p)} {o + d:+.1f}" for p, (o, d) in top))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tune", action="store_true")
    if ap.parse_args().tune:
        _tune()

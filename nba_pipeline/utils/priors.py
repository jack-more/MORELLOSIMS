"""priors.py — a preseason line for every rostered player, in player_season_stats' columns.

The nightly model reads a player through his current-season line. Before he
has played, seed_season.py copied last season's line, and a player without
one (back from a lost season, a rookie, a signing from abroad) was simply
not in the rotation: Haliburton and VanVleet counted as gone. This builds a
prior line for everyone on a new-season roster:

  * a full last season (MIN_GP games or more): that line, unchanged;
  * otherwise a composite: every NBA line he has from the last two seasons,
    weighted by games x recency (last season 1.0, the one before 0.8), plus
    a draft-slot line worth DRAFT_GAMES games when he has fewer than MIN_GP
    real games behind him. Haliburton / VanVleet (no games last season) come
    out as their 2024-25 line; Tatum (16 games back from the Achilles) is
    about a quarter last season, three quarters 2024-25.
  * draft-slot line: each stat fitted on log(overall pick) over the previous
    class's rookie season (2025 picks in 2025-26 for the 2026 class), the way
    season_win_sim.py prices rookies. Minutes are expected minutes (mpg x
    share of games played), so rookies who sat count as sitting. Undrafted
    players and signings with no NBA line get the line of the last pick.
  * RAPM: MOJO scores a player with RAPM on its percentile scale and one
    without on box score alone, which lands ~25 points lower (every rookie
    hit the 33 floor). A player with no RAPM gets the ORAPM / DRAPM
    percentiles of his draft slot, fitted on the previous class's RAPM, in
    orapm_pctl / drapm_pctl; generate_frontend fills them in for him only.

In season, blend() weighs a player's real games against his prior:
(gp x current + PRIOR_GAMES x prior) / (gp + PRIOR_GAMES), so one opening-night
box score can't replace a season. Season stats on the site stay the real ones;
only the model reads the blend.
"""

import json
import math
import os
import re
import sqlite3
import unicodedata

import numpy as np

MIN_GP = 20          # a season with fewer games than this doesn't stand alone
RECENCY = (1.0, 0.8)  # weight per game: last season, the one before
DRAFT_GAMES = 20     # weight of the draft-slot line, in games
PRIOR_GAMES = 15     # weight of the prior against this season's real games
LAST_PICK = 60
ID_COLS = ("player_id", "team_id", "season_id")
# per-game averages combine by games; rates and ratings by minutes
PER_GAME = {"gp", "minutes_total", "minutes_per_game", "pts_pg", "reb_pg", "ast_pg", "stl_pg", "blk_pg",
            "tov_pg", "fg3a_pg", "fta_pg"}

HERE = os.path.dirname(os.path.abspath(__file__))
CONTEXT = os.path.join(HERE, "..", "data", "win_totals", "espn_context_{season}.json")


def _prev(season, k=1):
    start = int(season[:4]) - k
    return f"{start}-{(start + 1) % 100:02d}"


def norm(name):
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    name = re.sub(r"[.'\-]", "", name)
    return " ".join(p for p in name.split() if p not in ("jr", "sr", "ii", "iii", "iv", "v"))


def stat_cols(con):
    return [r[1] for r in con.execute("PRAGMA table_info(player_season_stats)") if r[1] not in ID_COLS]


def season_lines(con, season, cols):
    q = f"SELECT player_id, {', '.join(cols)} FROM player_season_stats WHERE season_id = ?"
    return {r[0]: dict(zip(cols, r[1:])) for r in con.execute(q, [season])}


def combine(parts, cols):
    """Weighted mean of stat lines. parts: [(line, weight_in_games)]."""
    out = {}
    for c in cols:
        num = den = 0.0
        for line, w in parts:
            v = line.get(c)
            if v is None:
                continue
            ww = w if c in PER_GAME else w * (line.get("minutes_per_game") or 0)
            num += ww * float(v)
            den += ww
        out[c] = num / den if den else None
    return out


def rapm_pctls(con):
    """({pid: ORAPM percentile}, {pid: DRAPM percentile}) on generate_frontend's 33-99 scale."""
    try:
        rows = con.execute("SELECT player_id, rapm_offense, rapm_defense FROM player_rapm "
                           "WHERE rapm_total IS NOT NULL").fetchall()
    except sqlite3.OperationalError:
        return {}, {}
    out = []
    for k in (1, 2):
        vals = sorted(((r[0], r[k] or 0) for r in rows), key=lambda x: x[1])
        n = len(vals)
        out.append({pid: int(33 + (i / (n - 1) if n > 1 else 0.5) * 66) for i, (pid, _) in enumerate(vals)})
    return out[0], out[1]


def draft_fit(con, draft_prev, line_season, cols):
    """f(overall pick) -> stat line, fitted on the previous class's rookie season."""
    names = {norm(n): pid for pid, n in con.execute("SELECT player_id, full_name FROM players")}
    lines = season_lines(con, line_season, cols)
    o_pct, d_pct = rapm_pctls(con)
    for d in draft_prev:
        pid = names.get(norm(d["name"]))
        if pid in lines:
            lines[pid] = dict(lines[pid], orapm_pctl=o_pct.get(pid), drapm_pctl=d_pct.get(pid))
    pts = [(math.log(d["overall"]), lines[names[norm(d["name"])]]) for d in draft_prev
           if names.get(norm(d["name"])) in lines and (lines[names[norm(d["name"])]]["gp"] or 0) > 0]
    if len(pts) < 10:
        return None, len(pts)
    x = np.array([p[0] for p in pts])
    fits = {}
    for c in cols + ["orapm_pctl", "drapm_pctl"]:
        if c in ("gp", "minutes_total"):
            continue
        if c == "minutes_per_game":
            y = np.array([(p[1]["minutes_per_game"] or 0) * min(1, (p[1]["gp"] or 0) / 82) for p in pts])
        else:
            y = np.array([np.nan if p[1].get(c) is None else float(p[1][c]) for p in pts])
        ok = ~np.isnan(y)
        if ok.sum() < 10:
            continue
        b, a = np.polyfit(x[ok], y[ok], 1)
        lo, hi = np.percentile(y[ok], 5), np.percentile(y[ok], 95)
        fits[c] = (a, b, lo, hi)

    def f(pick):
        lx = math.log(min(max(pick, 1), LAST_PICK))
        line = {c: float(min(hi, max(lo, a + b * lx))) for c, (a, b, lo, hi) in fits.items()}
        line["gp"] = DRAFT_GAMES
        line["minutes_total"] = line.get("minutes_per_game", 0) * DRAFT_GAMES
        return line
    return f, len(pts)


def build(con, season, context_path=None):
    """{player_id: {"line": {...}, "source": str, "games": float}} for every player on a `season` roster."""
    cols = stat_cols(con)
    old, older = _prev(season), _prev(season, 2)
    lines = [season_lines(con, old, cols), season_lines(con, older, cols)]
    roster = dict(con.execute("SELECT player_id, team_id FROM roster_assignments WHERE season_id = ?", [season]))
    names = dict(con.execute("SELECT player_id, full_name FROM players"))

    path = context_path or CONTEXT.format(season=season)
    drafts = json.load(open(path))["drafts"] if os.path.exists(path) else {}
    yr = int(season[:4])
    fit, n_fit = draft_fit(con, drafts.get(str(yr - 1), []), old, cols) if drafts else (None, 0)
    o_pct, _ = rapm_pctls(con)
    slot = {}
    for y in (yr, yr - 1):                     # this year's class and last year's (unplayed or barely)
        for d in drafts.get(str(y), []):
            slot.setdefault(norm(d["name"]), (y, d["overall"]))

    out = {}
    for pid in roster:
        L0, L1 = lines[0].get(pid), lines[1].get(pid)
        if L0 and (L0["gp"] or 0) >= MIN_GP:
            out[pid] = {"line": L0, "source": old, "games": float(L0["gp"])}
            continue
        parts, label = [], []
        for L, s, r in ((L0, old, RECENCY[0]), (L1, older, RECENCY[1])):
            if L and (L["gp"] or 0) > 0:
                parts.append((L, L["gp"] * r))
                label.append(f"{s} {L['gp']}g")
        real = sum(L["gp"] for L, _ in parts)
        y, pick = slot.get(norm(names.get(pid, "")), (None, LAST_PICK))
        if real < MIN_GP and fit:
            parts.append((fit(pick), DRAFT_GAMES))
            label.append(f"{y} draft #{pick}" if y else "undrafted (pick-60 line)")
        if not parts:
            continue                           # nothing to go on: end of bench, as before
        line = combine(parts, cols)
        if pid not in o_pct and fit:
            slot_line = fit(pick)
            line["orapm_pctl"], line["drapm_pctl"] = slot_line.get("orapm_pctl"), slot_line.get("drapm_pctl")
        line["gp"] = int(round(sum(w for _, w in parts)))
        line["minutes_total"] = (line.get("minutes_per_game") or 0) * line["gp"]
        out[pid] = {"line": line, "source": " + ".join(label), "games": float(sum(w for _, w in parts))}
    return out, {"draft_fit_n": n_fit}


def _num(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def blend(current, prior, prior_games=PRIOR_GAMES):
    """This season's line weighed against the prior: gp x current + prior_games x prior."""
    gp = _num(current.get("gp")) or 0.0
    out = dict(current)
    for c, pv in prior.items():
        cv = _num(current.get(c))
        if c in ("gp", "minutes_total") or c.endswith("_pctl") or pv is None:
            continue
        if cv is None:
            out[c] = pv
            continue
        w_cur = gp if c in PER_GAME else gp * (_num(current.get("minutes_per_game")) or 0)
        w_pri = prior_games if c in PER_GAME else prior_games * (prior.get("minutes_per_game") or 0)
        out[c] = (w_cur * float(cv) + w_pri * float(pv)) / (w_cur + w_pri) if (w_cur + w_pri) else cv
    return out


PRIORS_SCHEMA = """CREATE TABLE IF NOT EXISTS player_priors (
    player_id INTEGER NOT NULL, season_id TEXT NOT NULL, source TEXT, games REAL, line TEXT,
    PRIMARY KEY (player_id, season_id))"""


def store(con, season, priors):
    con.execute(PRIORS_SCHEMA)
    con.execute("DELETE FROM player_priors WHERE season_id = ?", [season])
    con.executemany("INSERT INTO player_priors VALUES (?, ?, ?, ?, ?)",
                    [(pid, season, p["source"], p["games"], json.dumps(p["line"])) for pid, p in priors.items()])


def load(db_path, season):
    """{player_id: prior line} from player_priors ({} when the table isn't there)."""
    con = sqlite3.connect(db_path)
    try:
        return {pid: json.loads(line) for pid, line in
                con.execute("SELECT player_id, line FROM player_priors WHERE season_id = ?", [season])}
    except sqlite3.OperationalError:
        return {}
    finally:
        con.close()

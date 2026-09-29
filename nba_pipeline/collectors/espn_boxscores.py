"""Box scores from ESPN (reachable from GitHub Actions; stats.nba.com is not).

For every completed regular-season / play-in / playoff game this reads ESPN's
game summary (box score + play-by-play) and stores:

  espn_team_games    one row per team-game: box totals, possessions, periods
  espn_player_games  one row per player-game: box line + on-court tallies
                     reconstructed from play-by-play substitutions (seconds on
                     court, team/opponent points, FGA, FTA, TOV, rebounds and
                     possessions while on the floor)
  player_game_stats  filled for games that have no stats.nba.com rows, in the
                     stats.nba.com units (see pgs_row)

espn_* tables are the source for season aggregates (collectors/espn_season_stats.py).
stats.nba.com rows in player_game_stats are never overwritten. player_id is
the NBA person id (collectors/espn_ids.py), team_id the NBA team id.

Units (match collectors/boxscores.py / BoxScoreTraditionalV3 + AdvancedV3):
  minutes     decimal minutes (32.25 = 32:15), from play-by-play seconds;
              ESPN's whole-minute box value when play-by-play is unusable
  ratings     points per 100 possessions (off/def/net), 1 decimal, one
              possession count for both ends (average of offense and defense)
  pct fields  fractions (0.275, not 27.5), 3 decimals; rebound % counts team
              rebounds in the chances, as stats.nba.com does
  pace        possessions per 48 minutes, 2 decimals
  possessions counted from play-by-play (parse_pbp), not the box estimate
  pie         NULL (see pgs_row)
Verified against stats.nba.com for 2025-26: scripts/verify_espn_stats.py.

ESPN season types: 2 regular, 3 postseason, 5 play-in; 1 (preseason) is never
stored. The NBA Cup final (competition type "CC") and All-Star games are
flagged/skipped exactly as stats.nba.com does: the Cup final is a real game
(kept in player_game_stats) but not part of regular-season stats.
"""

import gzip
import json
import logging
import os
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from collectors.games_espn import espn_get_json, fetch_espn_events, _normalize_abbr
from collectors.espn_ids import ESPNPlayerMapper

logger = logging.getLogger(__name__)

SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={}"
STORED_SEASON_TYPES = {2, 3, 5}
SKIP_COMPETITION_TYPES = {"ALLSTAR"}
NOT_REGULAR_SEASON_STATS = {"CC"}   # NBA Cup championship: excluded from season stats by the NBA

SCHEMA = """
CREATE TABLE IF NOT EXISTS espn_team_games (
    game_id       TEXT NOT NULL,
    team_id       INTEGER NOT NULL,
    opp_team_id   INTEGER NOT NULL,
    espn_event_id TEXT NOT NULL,
    season_id     TEXT NOT NULL,
    game_date     TEXT NOT NULL,
    season_type   INTEGER NOT NULL,     -- 2 regular, 3 playoffs, 5 play-in
    counts_regular INTEGER NOT NULL,    -- 1 = part of NBA regular-season stats
    is_home       INTEGER,
    periods       INTEGER,
    minutes       REAL,                 -- team minutes (240 + 25 per OT)
    pts INTEGER, fgm INTEGER, fga INTEGER, fg3m INTEGER, fg3a INTEGER,
    ftm INTEGER, fta INTEGER, oreb INTEGER, dreb INTEGER, reb INTEGER,
    ast INTEGER, stl INTEGER, blk INTEGER, tov INTEGER, team_tov INTEGER,
    pf INTEGER,
    team_oreb INTEGER, team_dreb INTEGER,   -- team (non-player) rebounds, play-by-play
    poss          REAL,                 -- offensive possessions (play-by-play count)
    pbp_ok        INTEGER,              -- 1 = play-by-play reconciled with the box
    fetched_at    TEXT,
    PRIMARY KEY (game_id, team_id)
);
CREATE INDEX IF NOT EXISTS idx_etg_season ON espn_team_games(season_id, team_id);

CREATE TABLE IF NOT EXISTS espn_player_games (
    game_id     TEXT NOT NULL,
    player_id   INTEGER NOT NULL,
    team_id     INTEGER NOT NULL,
    espn_id     TEXT NOT NULL,
    season_id   TEXT NOT NULL,
    game_date   TEXT NOT NULL,
    season_type INTEGER NOT NULL,
    counts_regular INTEGER NOT NULL,
    started     INTEGER,
    dnp         INTEGER,
    box_min     INTEGER,               -- ESPN whole minutes
    sec         REAL,                  -- play-by-play seconds on court
    pts INTEGER, fgm INTEGER, fga INTEGER, fg3m INTEGER, fg3a INTEGER,
    ftm INTEGER, fta INTEGER, oreb INTEGER, dreb INTEGER, reb INTEGER,
    ast INTEGER, stl INTEGER, blk INTEGER, tov INTEGER, pf INTEGER,
    plus_minus INTEGER,
    -- on-court tallies (team = player's team, opp = opponent)
    on_pts INTEGER, on_opp_pts INTEGER,
    on_fgm INTEGER, on_fga INTEGER, on_fta INTEGER, on_tov INTEGER,
    on_oreb INTEGER, on_dreb INTEGER, on_opp_oreb INTEGER, on_opp_dreb INTEGER,
    on_opp_fga INTEGER, on_opp_fta INTEGER, on_opp_tov INTEGER,
    on_team_reb INTEGER, on_opp_team_reb INTEGER,
    off_poss REAL, def_poss REAL,
    PRIMARY KEY (game_id, player_id)
);
CREATE INDEX IF NOT EXISTS idx_epg_season ON espn_player_games(season_id, player_id);
"""

TEAM_TALLIES = ("pts", "fga", "fgm", "fta", "tov", "oreb", "dreb", "team_oreb", "team_dreb", "poss")
PLAYER_TALLIES = ("sec",) + tuple(f"on_{k}" for k in TEAM_TALLIES) + tuple(f"on_opp_{k}" for k in TEAM_TALLIES)
# espn_player_games on-court columns
ON_COLUMNS = ("on_pts", "on_opp_pts", "on_fgm", "on_fga", "on_fta", "on_tov", "on_oreb", "on_dreb",
              "on_opp_oreb", "on_opp_dreb", "on_opp_fga", "on_opp_fta", "on_opp_tov",
              "on_team_reb", "on_opp_team_reb", "off_poss", "def_poss")

_PERIOD_SECONDS = lambda p: 720 if p <= 4 else 300  # noqa: E731
# A possession that changes hands on a make/turnover with this many seconds
# or more left in the period counts for the other team even if the period
# ends before it logs an action. 1.0s best matches stats.nba.com's 2025-26
# team pace (mean error -0.07 possessions/48 over 30 teams at 62-65 GP).
END_PERIOD_MIN_SECONDS = 1.0
# Plays whose participants can be on the bench (not evidence of being on court)
_BENCH_OK = re.compile(r"technical|ejection|delay|coach|timeout|challenge|review|instant replay", re.I)


def _clock_seconds(v: str) -> float:
    v = (v or "0").strip()
    if ":" in v:
        m, s = v.split(":", 1)
        return int(m) * 60 + float(s)
    try:
        return float(v)
    except ValueError:
        return 0.0


def _split_made_att(v: str):
    try:
        m, a = v.split("-")
        return int(m), int(a)
    except (ValueError, AttributeError):
        return 0, 0


def _int(v):
    try:
        return int(str(v).replace("+", ""))
    except (TypeError, ValueError):
        return 0


# ── fetching ────────────────────────────────────────────────────────


def fetch_summary(event_id: str, cache_dir: str | None = None) -> dict | None:
    """ESPN game summary JSON; optional gzip cache for backfills."""
    path = os.path.join(cache_dir, f"{event_id}.json.gz") if cache_dir else None
    if path and os.path.exists(path):
        with gzip.open(path, "rt") as f:
            return json.load(f)
    data = espn_get_json(SUMMARY_URL.format(event_id), timeout=30)
    if data and path:
        os.makedirs(cache_dir, exist_ok=True)
        with gzip.open(path, "wt") as f:
            json.dump(data, f)
    return data


# ── parsing ─────────────────────────────────────────────────────────


def parse_box(summary: dict) -> dict:
    """Player box lines + team totals from an ESPN summary (espn ids)."""
    teams = {}
    for t in summary["boxscore"]["teams"]:
        stats = {s["name"]: s.get("displayValue") for s in t.get("statistics", [])}
        fgm, fga = _split_made_att(stats.get("fieldGoalsMade-fieldGoalsAttempted"))
        fg3m, fg3a = _split_made_att(stats.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted"))
        ftm, fta = _split_made_att(stats.get("freeThrowsMade-freeThrowsAttempted"))
        teams[str(t["team"]["id"])] = {
            "abbr": _normalize_abbr(t["team"]["abbreviation"]),
            "is_home": 1 if t.get("homeAway") == "home" else 0,
            "fgm": fgm, "fga": fga, "fg3m": fg3m, "fg3a": fg3a, "ftm": ftm, "fta": fta,
            "oreb": _int(stats.get("offensiveRebounds")), "dreb": _int(stats.get("defensiveRebounds")),
            "reb": _int(stats.get("totalRebounds")), "ast": _int(stats.get("assists")),
            "stl": _int(stats.get("steals")), "blk": _int(stats.get("blocks")),
            "tov": _int(stats.get("totalTurnovers") or stats.get("turnovers")),
            "team_tov": _int(stats.get("teamTurnovers")),
            "pf": _int(stats.get("fouls")),
        }
    players = {}
    for block in summary["boxscore"].get("players", []):
        tid = str(block["team"]["id"])
        for st in block.get("statistics", []):
            keys = st.get("keys") or []
            for a in st.get("athletes", []):
                ath = a.get("athlete") or {}
                if not ath.get("id"):
                    continue
                vals = dict(zip(keys, a.get("stats") or []))
                fgm, fga = _split_made_att(vals.get("fieldGoalsMade-fieldGoalsAttempted"))
                fg3m, fg3a = _split_made_att(vals.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted"))
                ftm, fta = _split_made_att(vals.get("freeThrowsMade-freeThrowsAttempted"))
                dnp = bool(a.get("didNotPlay")) or not a.get("stats")
                players[str(ath["id"])] = {
                    "espn_id": str(ath["id"]), "name": ath.get("displayName", ""),
                    "position": (ath.get("position") or {}).get("abbreviation", ""),
                    "espn_team": tid, "started": 1 if a.get("starter") else 0, "dnp": 1 if dnp else 0,
                    "box_min": _int(vals.get("minutes")), "pts": _int(vals.get("points")),
                    "fgm": fgm, "fga": fga, "fg3m": fg3m, "fg3a": fg3a, "ftm": ftm, "fta": fta,
                    "oreb": _int(vals.get("offensiveRebounds")), "dreb": _int(vals.get("defensiveRebounds")),
                    "reb": _int(vals.get("rebounds")), "ast": _int(vals.get("assists")),
                    "stl": _int(vals.get("steals")), "blk": _int(vals.get("blocks")),
                    "tov": _int(vals.get("turnovers")), "pf": _int(vals.get("fouls")),
                    "plus_minus": _int(vals.get("plusMinus")),
                }
    header_pts = {}
    for c in ((summary.get("header") or {}).get("competitions") or [{}])[0].get("competitors", []):
        header_pts[str(c.get("id") or (c.get("team") or {}).get("id"))] = _int(c.get("score"))
    for tid, t in teams.items():
        t["pts"] = header_pts.get(tid) or sum(p["pts"] for p in players.values() if p["espn_team"] == tid)
    box = {"teams": teams, "players": players}
    _add_ghost_players(summary, box)
    return box


_NAME_RE = re.compile(r"^(.+?) (makes|misses|offensive|defensive|shooting|personal|lost|bad|blocks|loose|"
                      r"traveling|out of bounds|kicked|step|offensive|3-second|double dribble|discontinued)")


def _add_ghost_players(summary: dict, box: dict):
    """ESPN's box score occasionally omits a player who appears all over the
    play-by-play (2025-26: a CHI two-way forward in a handful of games).
    Rebuild his counting line from the play-by-play so on-court tracking and
    player totals stay whole; minutes and +/- come from the on-court pass."""
    known = box["players"]
    plays = summary.get("plays") or []
    votes = defaultdict(lambda: defaultdict(int))
    names = {}
    for p in plays:
        parts = [str(x["athlete"]["id"]) for x in p.get("participants", []) if x.get("athlete", {}).get("id")]
        team = str((p.get("team") or {}).get("id") or "")
        if team not in box["teams"] or _BENCH_OK.search(p["type"]["text"]):
            continue  # coaches' technicals etc. are not evidence of a player
        if "substitution" in p["type"]["text"].lower():
            m = re.match(r"^(.+?) enters the game for (.+)$", p.get("text") or "")
            for i, a in enumerate(parts[:2]):
                if a not in known:
                    votes[a][team] += 1
                    if m and a not in names:
                        names[a] = m.group(1 + i)
        elif parts and parts[0] not in known:
            votes[parts[0]][team] += 1
            m = _NAME_RE.match(p.get("text") or "")
            if m and parts[0] not in names:
                names[parts[0]] = m.group(1)
    for a, v in votes.items():
        line = {"espn_id": a, "name": names.get(a, a), "position": "", "espn_team": max(v, key=v.get),
                "started": 0, "dnp": 0, "box_min": 0, "ghost": 1, "plus_minus": 0,
                **dict.fromkeys(("pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb",
                                 "ast", "stl", "blk", "tov", "pf"), 0)}
        for p in plays:
            parts = [str(x["athlete"]["id"]) for x in p.get("participants", []) if x.get("athlete", {}).get("id")]
            if a not in parts:
                continue
            t = p["type"]["text"].lower()
            text = (p.get("text") or "").lower()
            first = parts[0] == a
            if "substitution" in t:
                continue
            if "free throw" in t:
                if first:
                    line["fta"] += 1
                    if p.get("scoringPlay"):
                        line["ftm"] += 1
                        line["pts"] += int(p.get("scoreValue") or 0)
            elif p.get("shootingPlay"):
                if first:
                    three = 1 if int(p.get("pointsAttempted") or 0) == 3 else 0
                    line["fga"] += 1
                    line["fg3a"] += three
                    if p.get("scoringPlay"):
                        line["fgm"] += 1
                        line["fg3m"] += three
                        line["pts"] += int(p.get("scoreValue") or 0)
                elif "assists" in text:
                    line["ast"] += 1
                elif "blocks" in text:
                    line["blk"] += 1
            if "rebound" in t and first:
                line["oreb" if "offensive" in t else "dreb"] += 1
                line["reb"] += 1
            if "turnover" in t:
                if first:
                    line["tov"] += 1
                elif "steals" in text:
                    line["stl"] += 1
            if "foul" in t and first and "technical" not in t and "turnover" not in t:
                line["pf"] += 1
        known[a] = line


def _poss(fga, fta, oreb, tov):
    return fga + 0.44 * fta - oreb + tov


_FT_RE = re.compile(r"free throw - (\d) of (\d)")
_FT_KEEP_BALL = re.compile(r"flagrant|clear path|technical", re.I)


def _classify(p: dict) -> dict:
    """What a play means for box tallies and possession tracking."""
    t = p["type"]["text"]
    tl = t.lower()
    c = {}
    if "free throw" in tl:
        c["ft"] = True
        c["made"] = bool(p.get("scoringPlay"))
        c["technical"] = "technical" in tl
        c["keeps_ball"] = bool(_FT_KEEP_BALL.search(tl))   # flagrant / clear path: shooters keep it
        m = _FT_RE.search(tl)
        c["ft_n"], c["ft_of"] = (int(m.group(1)), int(m.group(2))) if m else (1, 1)
    elif p.get("shootingPlay"):
        c["shot"] = True
        c["made"] = bool(p.get("scoringPlay"))
        # end-of-period heaves that miss are not field goal attempts in the box score
        c["fga"] = not ("heave" in tl and not c["made"])
    if ("turnover" in tl and tl != "no turnover") or tl == "traveling":
        c["tov"] = True
    if "rebound" in tl:
        c["reb"] = "off" if "offensive" in tl else "def"
    return c


def parse_pbp(summary: dict, box: dict) -> dict:
    """On-court reconstruction from play-by-play.

    Lineups: period 1 from the box-score starters; later periods from who
    acts before being subbed in (plus silent carry-overs); then every
    substitution. Possessions are counted from the play-by-play the way the
    NBA counts them: a team's possession starts with its first action after
    the other team's possession ended (made basket, made final free throw,
    turnover, defensive rebound); and-ones, technical free throws and
    offensive rebounds never start a new one. Each possession is credited to
    the ten players on the floor when it starts.

    Returns {"players": {espn_id: tallies}, "teams": {espn_team: tallies},
             "periods": n, "issues": [..], "ok": bool}.
    """
    plays = summary.get("plays") or []
    team_ids = list(box["teams"])
    team_of = {pid: p["espn_team"] for pid, p in box["players"].items()}
    issues = []
    if not plays or len(team_ids) != 2:
        return {"players": {}, "teams": {}, "periods": 0, "issues": ["no play-by-play"], "ok": False}
    opp = {team_ids[0]: team_ids[1], team_ids[1]: team_ids[0]}

    ptally = defaultdict(lambda: dict.fromkeys(PLAYER_TALLIES, 0))
    ttally = {t: dict.fromkeys(TEAM_TALLIES, 0) for t in team_ids}

    by_period = defaultdict(list)
    for p in plays:
        by_period[int((p.get("period") or {}).get("number") or 0)].append(p)
    periods = sorted(k for k in by_period if k > 0)

    def participants(p):
        return [str(x["athlete"]["id"]) for x in p.get("participants", []) if x.get("athlete", {}).get("id")]

    def is_sub(p):
        return "substitution" in p["type"]["text"].lower()

    on = {t: set() for t in team_ids}
    starters = {t: {pid for pid, pl in box["players"].items() if pl["espn_team"] == t and pl["started"]}
                for t in team_ids}

    def credit(team, key, n=1):
        """Add n to team tally `key` and to the matching on-court tallies of all ten players."""
        ttally[team][key] += n
        for a in on[team]:
            ptally[a]["on_" + key] += n
        for a in on[opp[team]]:
            ptally[a]["on_opp_" + key] += n

    for per in periods:
        pp = by_period[per]
        if per == 1:
            on = {t: set(starters[t]) for t in team_ids}
        else:
            first = {}
            for p in pp:
                parts = participants(p)
                if is_sub(p):
                    if len(parts) >= 1:
                        first.setdefault(parts[0], "in")
                    if len(parts) >= 2:
                        first.setdefault(parts[1], "active")
                elif not _BENCH_OK.search(p["type"]["text"]):
                    for a in parts:
                        first.setdefault(a, "active")
            prev = on
            on = {}
            for t in team_ids:
                # dict order = order of first appearance in the period
                s_list = [a for a, v in first.items() if v == "active" and team_of.get(a) == t]
                if len(s_list) > 5:
                    # someone entered on an unlogged substitution: keep the
                    # five who showed up first
                    issues.append(f"P{per} {box['teams'][t]['abbr']}: {len(s_list)} active, unlogged sub-in")
                    s_list = s_list[:5]
                s = set(s_list)
                if len(s) < 5:
                    # silent full-period players: carry over from the previous
                    # period's closing unit (no event, no substitution)
                    quiet = [a for a in prev.get(t, set()) if a not in first]
                    for a in quiet[:5 - len(s)]:
                        s.add(a)
                if len(s) != 5:
                    issues.append(f"P{per} {box['teams'][t]['abbr']}: {len(s)} on court at start")
                on[t] = s

        remaining = _PERIOD_SECONDS(per)
        ball = None          # team in possession; None = dead ball / up for grabs
        ended_by = None      # team whose possession just ended on a make / turnover
        ended_clock = 0.0    # seconds left when it ended
        in_poss = set()      # players credited with the current possession
        last_make = None     # (team, clock) of the last made field goal (and-one detection)
        ft_rebound_dead = None  # (team, clock) of a missed non-final free throw
        for p in pp:
            clock_txt = (p.get("clock") or {}).get("displayValue")
            clock = _clock_seconds(clock_txt)
            elapsed = remaining - clock
            if elapsed > 0:
                for t in team_ids:
                    for a in on[t]:
                        ptally[a]["sec"] += elapsed
                remaining = clock
            parts = participants(p)
            team = str((p.get("team") or {}).get("id") or "")
            if is_sub(p):
                if len(parts) >= 2:
                    ain, aout = parts[0], parts[1]
                    t = team_of.get(ain) or team_of.get(aout) or team
                    if t in on:
                        if aout not in on[t]:
                            issues.append(f"P{per} {clock_txt}: sub out of player not on court")
                        on[t].discard(aout)
                        on[t].add(ain)
                        # stats.nba.com credits a possession to everyone on the
                        # floor for any part of it: a mid-possession sub counts
                        if ball is not None and ain not in in_poss:
                            ptally[ain]["on_poss" if t == ball else "on_opp_poss"] += 1
                            in_poss.add(ain)
                continue
            c = _classify(p)
            if not c:
                continue
            actor = team_of.get(parts[0]) if parts else None
            actor = actor or (team if team in on else None)
            if actor is None:
                continue

            def start(t):
                nonlocal ball, ended_by, in_poss
                if ball != t:
                    credit(t, "poss")
                    ball, ended_by = t, None
                    in_poss = on[t] | on[opp[t]]

            if c.get("ft"):
                credit(actor, "fta")
                if c["made"]:
                    credit(actor, "pts", int(p.get("scoreValue") or 1))
                elif c["ft_n"] < c["ft_of"]:
                    ft_rebound_dead = (actor, clock)
                if c["technical"]:
                    pass                                  # never changes possession
                elif last_make == (actor, clock) and c["ft_of"] == 1 and not c["keeps_ball"]:
                    ball, ended_by = actor, None          # and-one: same possession
                    if c["made"]:
                        ball, ended_by, last_make = None, actor, None
                else:
                    start(actor)
                    if c["made"] and c["ft_n"] == c["ft_of"] and not c["keeps_ball"]:
                        ball, ended_by = None, actor
            elif c.get("shot"):
                start(actor)
                if c["fga"]:
                    credit(actor, "fga")
                if c["made"]:
                    credit(actor, "fgm")
                    credit(actor, "pts", int(p.get("scoreValue") or 0))
                    ball, ended_by, last_make = None, actor, (actor, clock)
            if c.get("tov"):
                start(actor)
                credit(actor, "tov")
                ball, ended_by = None, actor
            if c.get("reb"):
                if parts:
                    credit(actor, "oreb" if c["reb"] == "off" else "dreb")
                elif not (c["reb"] == "off" and ft_rebound_dead == (actor, clock)):
                    # team rebound (dead-ball ones between free throws are bookkeeping, not rebounds)
                    credit(actor, "team_oreb" if c["reb"] == "off" else "team_dreb")
                start(actor)                               # def rebound: new possession
            if ball is None and ended_by is not None:
                ended_clock = clock
        if ball is None and ended_by is not None and ended_clock >= END_PERIOD_MIN_SECONDS:
            # the other team had the ball when the period ran out (no action logged)
            credit(opp[ended_by], "poss")
        if remaining > 0:
            for t in team_ids:
                for a in on[t]:
                    ptally[a]["sec"] += remaining

    # Reconcile with the box score. Lineup notes above are informational;
    # the game counts as usable only if every point and every player's
    # minutes (ESPN whole minutes, +-1) are accounted for.
    ok = True
    for t in team_ids:
        bt = box["teams"][t]
        if ttally[t]["pts"] != bt["pts"]:
            issues.append(f"{bt['abbr']} pbp points {ttally[t]['pts']} != box {bt['pts']}")
            ok = False
    for a, pt in ptally.items():
        bp = box["players"].get(a)
        if bp is None or bp.get("ghost"):
            continue
        if abs(pt["sec"] / 60 - bp["box_min"]) > 1.0:
            issues.append(f"{bp['name']}: pbp {pt['sec']/60:.1f} min vs box {bp['box_min']}")
            ok = False
    for a, pt in ptally.items():
        pt["off_poss"] = pt["on_poss"]
        pt["def_poss"] = pt["on_opp_poss"]
        pt["on_team_reb"] = pt["on_team_oreb"] + pt["on_team_dreb"]
        pt["on_opp_team_reb"] = pt["on_opp_team_oreb"] + pt["on_opp_team_dreb"]
    return {"players": dict(ptally), "teams": ttally, "periods": len(periods), "issues": issues, "ok": ok}


# ── units: stats.nba.com player_game_stats row ──────────────────────


def _r(x, n):
    return round(x, n) if x is not None else None


def pgs_row(game_id, pid, team_id, p, on, minutes):
    """One player_game_stats row in stats.nba.com units (Traditional+Advanced V3)."""
    row = {
        "game_id": game_id, "player_id": pid, "team_id": team_id,
        "minutes": round(minutes, 2), "started": p["started"],
        "pts": p["pts"], "reb": p["reb"], "ast": p["ast"], "stl": p["stl"], "blk": p["blk"],
        "tov": p["tov"], "fgm": p["fgm"], "fga": p["fga"], "fg3m": p["fg3m"], "fg3a": p["fg3a"],
        "ftm": p["ftm"], "fta": p["fta"], "oreb": p["oreb"], "dreb": p["dreb"], "pf": p["pf"],
        "plus_minus": float(p["plus_minus"]),
    }
    adv = dict.fromkeys(("off_rating", "def_rating", "net_rating", "ast_pct", "reb_pct", "usg_pct",
                         "ts_pct", "efg_pct", "pace", "pie"), 0.0)
    if minutes > 0 and on:
        op, dp = on["off_poss"], on["def_poss"]
        # one possession count for both ends (average of the two), as stats.nba.com does
        poss = (op + dp) / 2
        ortg = 100 * on["on_pts"] / poss if poss > 0 else 0.0
        drtg = 100 * on["on_opp_pts"] / poss if poss > 0 else 0.0
        adv["off_rating"], adv["def_rating"] = _r(ortg, 1), _r(drtg, 1)
        adv["net_rating"] = _r(ortg - drtg, 1)
        denom_ast = on["on_fgm"] - p["fgm"]
        adv["ast_pct"] = _r(p["ast"] / denom_ast, 3) if denom_ast > 0 else 0.0
        # NBA rebound chances include team (non-player) rebounds
        reb_chances = (on["on_oreb"] + on["on_dreb"] + on["on_opp_oreb"] + on["on_opp_dreb"]
                       + on["on_team_reb"] + on["on_opp_team_reb"])
        adv["reb_pct"] = _r(p["reb"] / reb_chances, 3) if reb_chances > 0 else 0.0
        plays = on["on_fga"] + 0.44 * on["on_fta"] + on["on_tov"]
        adv["usg_pct"] = _r((p["fga"] + 0.44 * p["fta"] + p["tov"]) / plays, 3) if plays > 0 else 0.0
        tsa = 2 * (p["fga"] + 0.44 * p["fta"])
        adv["ts_pct"] = _r(p["pts"] / tsa, 3) if tsa > 0 else 0.0
        adv["efg_pct"] = _r((p["fgm"] + 0.5 * p["fg3m"]) / p["fga"], 3) if p["fga"] > 0 else 0.0
        adv["pace"] = _r(48 * poss / minutes, 2)
    # PIE: stats.nba.com's box-score PIE cannot be reproduced from ESPN data
    # (its per-game values do not follow the published formula) and nothing
    # reads it, so ESPN rows leave it NULL rather than store a look-alike.
    adv["pie"] = None
    row.update(adv)
    return row


# ── collector ───────────────────────────────────────────────────────


class ESPNBoxScoreCollector:
    """Fetch ESPN box scores + play-by-play and store them (see module doc)."""

    def __init__(self, db_path: str, cache_dir: str | None = None):
        self.db_path = db_path
        self.cache_dir = cache_dir
        self.unmatched = {}   # espn_id -> (name, team abbr) resolved to synthetic ids
        self.pbp_fallbacks = []

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.executescript(SCHEMA)
        return conn

    def _team_maps(self, conn):
        by_abbr = {a: int(t) for t, a in conn.execute("SELECT team_id, abbreviation FROM teams")}
        return by_abbr

    def _find_game(self, conn, game_date, home_id, away_id):
        """games.game_id for this matchup (date, then +-1 day for UTC/ET drift)."""
        for d in (game_date,
                  (datetime.strptime(game_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d"),
                  (datetime.strptime(game_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")):
            r = conn.execute("SELECT game_id, season_id, game_date FROM games WHERE game_date = ? AND "
                             "home_team_id = ? AND away_team_id = ?", [d, home_id, away_id]).fetchone()
            if r:
                return r
        return None

    def collect_date(self, date: datetime, season_id: str, fill_pgs: bool = True,
                     refetch: bool = False) -> dict:
        """Collect every completed counted game on one date. Returns counts."""
        events = fetch_espn_events(date)
        if events is None:
            logger.warning(f"ESPN scoreboard unavailable for {date:%Y-%m-%d}")
            return {"games": 0, "failed": 1}
        conn = self._conn()
        by_abbr = self._team_maps(conn)
        mapper = ESPNPlayerMapper(conn)
        stats = {"games": 0, "failed": 0, "pgs_rows": 0, "games_inserted": 0}
        try:
            for ev in events:
                if not ev["completed"] or ev.get("season_type") not in STORED_SEASON_TYPES:
                    continue
                if ev.get("competition_type") in SKIP_COMPETITION_TYPES:
                    continue
                home_id, away_id = by_abbr.get(ev["home_abbr"]), by_abbr.get(ev["away_abbr"])
                if not home_id or not away_id:
                    continue
                game = self._find_game(conn, ev["game_date"], home_id, away_id)
                if game is None:
                    game_id = f"espn_{ev['game_date'].replace('-', '')}_{ev['away_abbr']}_{ev['home_abbr']}"
                    conn.execute("INSERT OR IGNORE INTO games (game_id, season_id, game_date, home_team_id, "
                                 "away_team_id, home_score, away_score) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                 [game_id, season_id, ev["game_date"], home_id, away_id,
                                  ev["home_score"], ev["away_score"]])
                    game = (game_id, season_id, ev["game_date"])
                    stats["games_inserted"] += 1
                game_id, g_season, g_date = game
                if not refetch and conn.execute("SELECT 1 FROM espn_team_games WHERE game_id = ?",
                                                [game_id]).fetchone():
                    if fill_pgs:
                        stats["pgs_rows"] += self._fill_pgs(conn, game_id)
                    continue
                summary = fetch_summary(ev["event_id"], self.cache_dir)
                if not summary or "boxscore" not in summary:
                    stats["failed"] += 1
                    continue
                try:
                    self._store_game(conn, mapper, summary, ev, game_id, g_season, g_date, by_abbr)
                except Exception as e:
                    logger.error(f"  ESPN parse failed for {game_id} (event {ev['event_id']}): {e}")
                    stats["failed"] += 1
                    continue
                stats["games"] += 1
                if fill_pgs:
                    stats["pgs_rows"] += self._fill_pgs(conn, game_id)
            mapper.resolve_synthetic_ids()
            for espn_id, name, tid in mapper.new_synthetic:
                self.unmatched[espn_id] = (name, tid)
            conn.commit()
        finally:
            conn.close()
        return stats

    def _store_game(self, conn, mapper, summary, ev, game_id, season_id, game_date, by_abbr):
        box = parse_box(summary)
        pbp = parse_pbp(summary, box)
        if not pbp["ok"]:
            self.pbp_fallbacks.append((game_id, pbp["issues"][:3]))
            logger.info(f"  {game_id}: play-by-play did not reconcile ({'; '.join(pbp['issues'][:2])}) "
                        f"— whole-minute box minutes used")
        espn_to_nba = {et: by_abbr.get(t["abbr"]) for et, t in box["teams"].items()}
        counts_regular = 1 if (ev["season_type"] == 2 and
                               ev.get("competition_type") not in NOT_REGULAR_SEASON_STATS) else 0
        periods = pbp["periods"] or 4
        team_minutes = 240 + 25 * max(0, periods - 4)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        ets = list(box["teams"])
        conn.execute("DELETE FROM espn_team_games WHERE game_id = ?", [game_id])
        conn.execute("DELETE FROM espn_player_games WHERE game_id = ?", [game_id])
        for et in ets:
            t = box["teams"][et]
            o = box["teams"][ets[1] if et == ets[0] else ets[0]]
            pt = (pbp["teams"] or {}).get(et) or {}
            # play-by-play possession count; the box-score estimate only without play-by-play
            # (the estimate is +-7% per game; the two teams' counts agree within 1-2)
            poss = pt.get("poss") or _poss(t["fga"], t["fta"], t["oreb"], t["tov"])
            row = {
                "game_id": game_id, "team_id": espn_to_nba[et], "opp_team_id": by_abbr.get(o["abbr"]),
                "espn_event_id": ev["event_id"], "season_id": season_id, "game_date": game_date,
                "season_type": ev["season_type"], "counts_regular": counts_regular, "is_home": t["is_home"],
                "periods": periods, "minutes": team_minutes,
                **{k: t[k] for k in ("pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb",
                                     "ast", "stl", "blk", "tov", "team_tov", "pf")},
                "team_oreb": pt.get("team_oreb", 0), "team_dreb": pt.get("team_dreb", 0),
                "poss": poss, "pbp_ok": 1 if pbp["ok"] else 0, "fetched_at": now,
            }
            conn.execute(f"INSERT INTO espn_team_games ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})",
                         list(row.values()))
        for eid, p in box["players"].items():
            if p.get("ghost"):
                on = pbp["players"].get(eid)
                if not pbp["ok"] or not on or on["sec"] <= 0:
                    continue
                p["box_min"] = int(round(on["sec"] / 60))
                p["plus_minus"] = int(on["on_pts"] - on["on_opp_pts"])
            tid = espn_to_nba.get(p["espn_team"])
            pid = mapper.resolve(eid, p["name"], tid)
            mapper.ensure_player_row(pid, p["name"], p["position"])
            on = pbp["players"].get(eid)
            if on is None or not pbp["ok"]:
                on = self._prorated_on_court(p, box, pbp) if not p["dnp"] else None
            row = {
                "game_id": game_id, "player_id": pid, "team_id": tid, "espn_id": eid, "season_id": season_id,
                "game_date": game_date, "season_type": ev["season_type"], "counts_regular": counts_regular,
                "started": p["started"], "dnp": p["dnp"], "box_min": p["box_min"],
                "sec": on["sec"] if on else 0.0,
                **{k: p[k] for k in ("pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb",
                                     "ast", "stl", "blk", "tov", "pf", "plus_minus")},
                **{k: (on or {}).get(k, 0) for k in ON_COLUMNS},
            }
            conn.execute(f"INSERT OR REPLACE INTO espn_player_games ({', '.join(row)}) "
                         f"VALUES ({', '.join('?' * len(row))})", list(row.values()))

    @staticmethod
    def _prorated_on_court(p, box, pbp):
        """When play-by-play is unusable: the player's box minutes' share of
        his team's totals, with his own +/- carried exactly (points for and
        against split around the per-minute game scoring)."""
        tid = p["espn_team"]
        others = [t for t in box["teams"] if t != tid]
        if not others or p["box_min"] <= 0:
            return None
        t, o = box["teams"][tid], box["teams"][others[0]]
        pt = (pbp.get("teams") or {})
        share = p["box_min"] / 48.0
        on = {"sec": p["box_min"] * 60.0}
        for k, src, key in (("on_fgm", t, "fgm"), ("on_fga", t, "fga"), ("on_fta", t, "fta"),
                            ("on_tov", t, "tov"), ("on_oreb", t, "oreb"), ("on_dreb", t, "dreb"),
                            ("on_opp_oreb", o, "oreb"), ("on_opp_dreb", o, "dreb"), ("on_opp_fga", o, "fga"),
                            ("on_opp_fta", o, "fta"), ("on_opp_tov", o, "tov")):
            on[k] = src[key] * share
        own, oth = pt.get(tid) or {}, pt.get(others[0]) or {}
        on["on_team_reb"] = (own.get("team_oreb", 0) + own.get("team_dreb", 0)) * share
        on["on_opp_team_reb"] = (oth.get("team_oreb", 0) + oth.get("team_dreb", 0)) * share
        base = (t["pts"] + o["pts"]) / 2 * share
        on["on_pts"] = base + p["plus_minus"] / 2
        on["on_opp_pts"] = base - p["plus_minus"] / 2
        on["off_poss"] = (own.get("poss") or _poss(t["fga"], t["fta"], t["oreb"], t["tov"])) * share
        on["def_poss"] = (oth.get("poss") or _poss(o["fga"], o["fta"], o["oreb"], o["tov"])) * share
        return on


    def _fill_pgs(self, conn, game_id) -> int:
        """Write player_game_stats for game_id from espn_player_games, unless
        stats.nba.com rows already exist for the game."""
        if conn.execute("SELECT 1 FROM player_game_stats WHERE game_id = ? LIMIT 1", [game_id]).fetchone():
            return 0
        return write_pgs_from_espn(conn, game_id)


def espn_player_rows(conn, game_id):
    cur = conn.execute("SELECT * FROM espn_player_games WHERE game_id = ?", [game_id])
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def pgs_rows_for_game(conn, game_id) -> list[dict]:
    """player_game_stats rows (stats.nba.com units) for one stored ESPN game."""
    rows = espn_player_rows(conn, game_id)
    pbp_ok = conn.execute("SELECT MIN(pbp_ok) FROM espn_team_games WHERE game_id = ?", [game_id]).fetchone()[0]
    out = []
    for r in rows:
        minutes = r["sec"] / 60.0 if pbp_ok else float(r["box_min"] or 0)
        if r["dnp"]:
            minutes = 0.0
        on = {k: r[k] for k in ON_COLUMNS}
        out.append(pgs_row(game_id, r["player_id"], r["team_id"], r, on, minutes))
    return out


def write_pgs_from_espn(conn, game_id) -> int:
    rows = pgs_rows_for_game(conn, game_id)
    if not rows:
        return 0
    cols = list(rows[0])
    conn.executemany(
        f"INSERT OR REPLACE INTO player_game_stats ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        [[r[c] for c in cols] for r in rows])
    return len(rows)

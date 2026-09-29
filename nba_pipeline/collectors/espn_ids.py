"""ESPN athlete id -> NBA person id (player_id) mapping.

Every NBA table keys players by the NBA person id (stats.nba.com), and ESPN
has its own athlete ids. The mapping is resolved once per athlete and
persisted in `espn_player_map`, so later runs never re-guess a name.

Resolution order for an ESPN athlete not yet mapped:
  1. normalized full name against `players` (the model's own universe),
     ties broken by the team the athlete played for;
  2. normalized full name against nba_api's bundled static player list
     (offline; covers every NBA player up to the installed nba_api release);
  3. NAME_ALIASES (ESPN spelling -> NBA spelling) for known variants;
  4. otherwise a SYNTHETIC id.

Synthetic id policy (new players with no NBA id yet — rookies, two-way
call-ups, signings newer than the installed nba_api):
    player_id = SYNTHETIC_BASE + ESPN athlete id  (SYNTHETIC_BASE = 900,000,000)
Real NBA person ids are < 2,000,000 today (max in the DB: 1,643,257; the
series grows by ~1,000 per draft class), and ESPN athlete ids are < 100
million, so synthetic ids live in [900M, 1B) and can never collide with a
real id. They are deterministic (the same athlete always gets the same id,
on every machine and every run) and temporary: resolve_synthetic_ids()
runs on every sync and rewrites a synthetic id to the real one everywhere
as soon as the real id is known (stats.nba.com roster, a newer nba_api).
"""

import logging
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SYNTHETIC_BASE = 900_000_000
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

# ESPN display name (normalized) -> NBA name (normalized). Only for variants
# the normalizer cannot bridge; found by matching ESPN stat lines to
# stats.nba.com stat lines game-by-game for 2025-26 (scripts/verify_espn_stats.py).
NAME_ALIASES: dict[str, str] = {}

# Tables whose player_id columns are rewritten when a synthetic id resolves.
_PLAYER_ID_COLUMNS = [
    ("player_game_stats", "player_id"),
    ("espn_player_games", "player_id"),
    ("player_season_stats", "player_id"),
    ("roster_assignments", "player_id"),
]

MAP_SCHEMA = """
CREATE TABLE IF NOT EXISTS espn_player_map (
    espn_id     TEXT PRIMARY KEY,
    player_id   INTEGER NOT NULL,
    espn_name   TEXT,
    method      TEXT,        -- players | nba_static | alias | synthetic | manual
    updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_espn_map_pid ON espn_player_map(player_id);
"""


def norm_name(name: str) -> str:
    """'Nikola Jokić' -> 'nikola jokic'; 'P.J. Washington Jr.' -> 'pj washington'.

    Strips accents, punctuation and generational suffixes, and joins runs of
    single letters so 'P.J.' / 'PJ' / 'P. J.' all become 'pj'.
    """
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[.'`\-,]", " ", s)
    words = [w for w in s.split() if w not in _SUFFIXES]
    out, run = [], ""
    for w in words:
        if len(w) == 1:
            run += w
            continue
        if run:
            out.append(run)
            run = ""
        out.append(w)
    if run:
        out.append(run)
    return " ".join(out)


def is_synthetic(player_id) -> bool:
    try:
        return int(player_id) >= SYNTHETIC_BASE
    except (TypeError, ValueError):
        return False


def synthetic_id(espn_id) -> int:
    return SYNTHETIC_BASE + int(espn_id)


def _static_players():
    try:
        from nba_api.stats.static import players as static_players
        return static_players.get_players()
    except Exception as e:  # nba_api missing or broken: synthetic ids cover it
        logger.warning(f"nba_api static player list unavailable: {e}")
        return []


class ESPNPlayerMapper:
    """Resolve ESPN athletes to NBA player ids, persisting every decision."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        conn.executescript(MAP_SCHEMA)
        self.cache = {str(e): int(p) for e, p in conn.execute("SELECT espn_id, player_id FROM espn_player_map")}
        self._db_names = None
        self._static_names = None
        self.new_synthetic = []   # (espn_id, name, team_id) created this run

    # ── name indexes ──
    def _load_db_names(self):
        idx = {}
        for pid, name in self.conn.execute("SELECT player_id, full_name FROM players"):
            if is_synthetic(pid):
                continue
            idx.setdefault(norm_name(name), set()).add(int(pid))
        self._db_names = idx

    def _load_static_names(self):
        idx = {}
        for p in _static_players():
            idx.setdefault(norm_name(p["full_name"]), []).append(p)
        self._static_names = idx

    def _team_members(self, team_id):
        if team_id is None:
            return set()
        return {int(r[0]) for r in self.conn.execute(
            "SELECT DISTINCT player_id FROM roster_assignments WHERE team_id = ?", [int(team_id)])}

    def lookup_real(self, name: str, team_id=None):
        """(player_id, method) for a real NBA id, or (None, None)."""
        if self._db_names is None:
            self._load_db_names()
        if self._static_names is None:
            self._load_static_names()
        n = norm_name(name)
        for key, method in ((n, None), (NAME_ALIASES.get(n), "alias")):
            if not key:
                continue
            cands = self._db_names.get(key, set())
            if len(cands) == 1:
                return next(iter(cands)), method or "players"
            if len(cands) > 1:
                on_team = cands & self._team_members(team_id)
                if len(on_team) == 1:
                    return next(iter(on_team)), method or "players"
            stat = self._static_names.get(key, [])
            active = [p for p in stat if p.get("is_active")]
            pick = active if len(active) == 1 else (stat if len(stat) == 1 else [])
            if len(pick) == 1:
                return int(pick[0]["id"]), method or "nba_static"
        return None, None

    def resolve(self, espn_id, name: str, team_id=None) -> int:
        espn_id = str(espn_id)
        if espn_id in self.cache:
            return self.cache[espn_id]
        pid, method = self.lookup_real(name, team_id)
        if pid is None:
            pid, method = synthetic_id(espn_id), "synthetic"
            self.new_synthetic.append((espn_id, name, team_id))
        self._store(espn_id, pid, name, method)
        return pid

    def _store(self, espn_id, pid, name, method):
        self.conn.execute(
            "INSERT OR REPLACE INTO espn_player_map (espn_id, player_id, espn_name, method, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            [str(espn_id), int(pid), name, method, datetime.now(timezone.utc).isoformat(timespec="seconds")])
        self.cache[str(espn_id)] = int(pid)

    def ensure_player_row(self, pid: int, name: str, position: str = ""):
        """Make sure `players` has a row for pid (synthetic or a real id the
        roster fetch never delivered), like LeagueDash backfill used to."""
        if self.conn.execute("SELECT 1 FROM players WHERE player_id = ?", [pid]).fetchone():
            return False
        self.conn.execute(
            "INSERT INTO players (player_id, full_name, position, height_inches, weight_lbs, "
            "birth_date, experience, is_active) VALUES (?, ?, ?, NULL, NULL, '', NULL, 1)",
            [pid, name, position or ""])
        return True

    def resolve_synthetic_ids(self) -> list[tuple]:
        """Rewrite synthetic ids whose real NBA id is now known. Returns (old, new, name)."""
        self._db_names = None  # players may have changed since load
        rows = self.conn.execute(
            "SELECT espn_id, player_id, espn_name FROM espn_player_map WHERE method = 'synthetic'").fetchall()
        changed = []
        for espn_id, old, name in rows:
            new, method = self.lookup_real(name)
            if new is None:
                continue
            for table, col in _PLAYER_ID_COLUMNS:
                if not self._has_table(table):
                    continue
                # a real-id row may already exist for the same key: keep the real one
                self.conn.execute(f"UPDATE OR IGNORE {table} SET {col} = ? WHERE {col} = ?", [new, old])
                self.conn.execute(f"DELETE FROM {table} WHERE {col} = ?", [old])
            self.conn.execute("DELETE FROM players WHERE player_id = ?", [old])
            self._store(espn_id, new, name, method)
            changed.append((old, new, name))
        if changed:
            logger.info(f"Resolved {len(changed)} synthetic player ids to NBA ids: "
                        + ", ".join(f"{n} {o}->{w}" for o, w, n in changed[:20]))
        return changed

    def _has_table(self, name):
        return self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", [name]).fetchone() is not None

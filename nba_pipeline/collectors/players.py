"""Collect teams, rosters, and player/team season stats."""

import logging
import pandas as pd
from nba_api.stats.static import teams as nba_teams
from nba_api.stats.endpoints import (
    CommonTeamRoster,
    LeagueDashPlayerStats,
    LeagueDashTeamStats,
)

from collectors.base import BaseCollector
from db.connection import read_query, execute, save_dataframe

logger = logging.getLogger(__name__)


def _norm_name(name: str) -> str:
    """'Nikola Jokić' / 'Jaren Jackson Jr.' -> 'nikola jokic' / 'jaren jackson'."""
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[.'\-]", " ", s)
    words = [w for w in s.split() if w not in {"jr", "sr", "ii", "iii", "iv"}]
    return " ".join(words)


class PlayerCollector(BaseCollector):

    def collect_teams(self):
        """Populate teams table from static data (no API call)."""
        all_teams = nba_teams.get_teams()
        df = pd.DataFrame(all_teams)
        df = df.rename(columns={
            "id": "team_id",
            "abbreviation": "abbreviation",
            "full_name": "full_name",
        })
        # Add conference/division info
        east_teams = {
            "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DET", "IND",
            "MIA", "MIL", "NYK", "ORL", "PHI", "TOR", "WAS"
        }
        df["conference"] = df["abbreviation"].apply(
            lambda x: "East" if x in east_teams else "West"
        )
        df["division"] = ""  # Can be filled later if needed
        df = df[["team_id", "abbreviation", "full_name", "conference", "division"]]
        self._save(df, "teams", if_exists="replace")
        logger.info(f"Saved {len(df)} teams")
        return df

    def collect_rosters(self, season: str, passes: int = 2, timeout: int = 20):
        """Collect rosters for all teams. ~30 API calls.

        Timeout-tolerant: each team is saved as soon as it is fetched (a step
        timeout keeps everything fetched so far), teams that fail are retried
        in a second pass, and a team whose fetch fails keeps its cached
        roster instead of being wiped. Returns the team_ids that failed.
        """
        teams_df = read_query("SELECT team_id FROM teams", self.db_path)
        pending = [int(t) for t in teams_df["team_id"]]
        saved = 0
        blocked = False
        for pass_no in range(1, passes + 1):
            failed = []
            for i, team_id in enumerate(pending):
                if blocked:
                    failed.append(team_id)
                    continue
                try:
                    players, assignments = self._fetch_team_roster(team_id, season, timeout)
                except Exception as e:
                    logger.error(f"  Failed to get roster for team {team_id} (pass {pass_no}): {e}")
                    failed.append(team_id)
                    # stats.nba.com blocks datacenter IPs (GitHub Actions): the
                    # first teams all time out, so stop paying ~60s per team.
                    if saved == 0 and len(failed) >= self.ROSTER_BREAKER and len(failed) == i + 1:
                        logger.warning(f"  stats.nba.com unreachable ({len(failed)} straight roster "
                                       f"failures) — skipping it, using ESPN rosters")
                        blocked = True
                    continue
                if not assignments:
                    continue
                self._save_team_roster(team_id, season, players, assignments)
                saved += len(assignments)
            pending = failed
            if not pending or blocked:
                break
        if pending:
            pending = self.collect_rosters_espn(season, pending)
        logger.info(f"Saved {saved} roster assignments for {season} from stats.nba.com; "
                    f"{len(pending)} team(s) kept cached rosters: {pending}")
        return pending

    ROSTER_BREAKER = 3

    def collect_rosters_espn(self, season: str, team_ids: list[int]) -> list[int]:
        """Roster fallback from ESPN (reachable from Actions runners).

        Replaces only roster_assignments for each team. ESPN athletes are
        matched to existing NBA player_ids by normalized name; players we have
        no NBA id for (new signings/rookies) are logged and left out, since
        the model has no values for them anyway. Returns team_ids still failed.
        """
        from datetime import date
        from collectors.games_espn import espn_get_json, _normalize_abbr
        from config import season_for_date

        # ESPN only serves TODAY's rosters. Jul-Sep they belong to the coming
        # season while CURRENT_SEASON is still the finished one; writing them
        # there would overwrite last season's history (and its seeded priors).
        today = date.today()
        if season != season_for_date(today) or today.month in (7, 8, 9):
            logger.info(f"  ESPN roster fallback skipped: current rosters are not {season}'s")
            return team_ids
        base = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
        listing = espn_get_json(base)
        if not listing:
            logger.error("  ESPN roster fallback: team list unavailable")
            return team_ids
        espn_teams = {
            _normalize_abbr(x["team"]["abbreviation"]): x["team"]["id"]
            for x in listing["sports"][0]["leagues"][0]["teams"]
        }
        teams = read_query("SELECT team_id, abbreviation FROM teams", self.db_path)
        abbr_of = {int(r.team_id): r.abbreviation for r in teams.itertuples()}
        by_name = {}
        for r in read_query("SELECT player_id, full_name FROM players", self.db_path).itertuples():
            by_name.setdefault(_norm_name(r.full_name), int(r.player_id))
        # ESPN athlete -> NBA id, same resolver (and persisted map) as the ESPN
        # box scores; athletes with no NBA id yet get the deterministic
        # synthetic id (collectors/espn_ids.py) instead of being dropped.
        import sqlite3
        from collectors.espn_ids import ESPNPlayerMapper, is_synthetic
        map_conn = sqlite3.connect(self.db_path, timeout=30)
        mapper = ESPNPlayerMapper(map_conn)

        still_failed, unmatched, saved = [], [], 0
        for team_id in team_ids:
            espn_id = espn_teams.get(abbr_of.get(team_id))
            data = espn_get_json(f"{base}/{espn_id}/roster") if espn_id else None
            if not data or not data.get("athletes"):
                still_failed.append(team_id)
                continue
            rows = []
            for a in data["athletes"]:
                name = a.get("fullName", "")
                pos = (a.get("position") or {}).get("abbreviation", "")
                if a.get("id") and str(a["id"]) in mapper.cache:
                    pid = mapper.cache[str(a["id"])]
                elif by_name.get(_norm_name(name)) is not None:
                    pid = by_name[_norm_name(name)]
                    if a.get("id"):
                        mapper._store(a["id"], pid, name, "players")
                elif a.get("id"):
                    pid = mapper.resolve(a["id"], name, team_id)
                else:
                    unmatched.append(f"{abbr_of.get(team_id)}:{name}")
                    continue
                mapper.ensure_player_row(pid, name, pos)
                if is_synthetic(pid):
                    unmatched.append(f"{abbr_of.get(team_id)}:{name}")
                rows.append({
                    "player_id": pid, "team_id": team_id, "season_id": season,
                    "jersey_number": str(a.get("jersey") or ""),
                    "listed_position": (a.get("position") or {}).get("abbreviation", ""),
                })
            map_conn.commit()   # release the write lock before execute() below
            if not rows:
                still_failed.append(team_id)
                continue
            execute("DELETE FROM roster_assignments WHERE season_id = ? AND team_id = ?",
                    self.db_path, [season, team_id])
            # a traded player must not stay on his old team for this season
            ids = ",".join(str(r["player_id"]) for r in rows)
            execute(f"DELETE FROM roster_assignments WHERE season_id = ? AND player_id IN ({ids})",
                    self.db_path, [season])
            self._save(pd.DataFrame(rows).drop_duplicates(subset=["player_id"]), "roster_assignments")
            saved += len(rows)
        map_conn.commit()
        map_conn.close()
        logger.info(f"  ESPN roster fallback: {saved} assignments for {len(team_ids) - len(still_failed)} "
                    f"team(s); {len(unmatched)} players with no NBA id yet (synthetic ids)")
        if unmatched:
            logger.info(f"  no NBA id yet (new to the league or name variant): {', '.join(unmatched[:40])}")
        return still_failed

    def _save_team_roster(self, team_id: int, season: str, players: list, assignments: list):
        """Replace one team's roster for a season; upsert its players."""
        players_df = pd.DataFrame(players).drop_duplicates(subset=["player_id"])
        ids = ",".join(str(int(i)) for i in players_df["player_id"])
        try:
            execute(f"DELETE FROM players WHERE player_id IN ({ids})", self.db_path)
        except Exception:
            pass  # players table not created yet
        self._save(players_df, "players")
        execute(
            "DELETE FROM roster_assignments WHERE season_id = ? AND team_id = ?",
            self.db_path, [season, team_id],
        )
        self._save(pd.DataFrame(assignments), "roster_assignments")

    def _fetch_team_roster(self, team_id: int, season: str, timeout: int):
        """One team's roster -> (players rows, roster_assignments rows). Raises on failure."""
        dfs = self._call_endpoint(
            CommonTeamRoster,
            team_id=team_id,
            season=season,
            timeout=timeout,
        )
        roster = dfs[0]
        if roster.empty:
            return [], []

        all_players = []
        all_assignments = []
        for _, p in roster.iterrows():
            player_id = int(p["PLAYER_ID"])

            # Parse height to inches
            height_inches = None
            if pd.notna(p.get("HEIGHT")) and p["HEIGHT"]:
                parts = str(p["HEIGHT"]).split("-")
                if len(parts) == 2:
                    try:
                        height_inches = int(parts[0]) * 12 + int(parts[1])
                    except ValueError:
                        pass

            weight = None
            if pd.notna(p.get("WEIGHT")) and p["WEIGHT"]:
                try:
                    weight = int(p["WEIGHT"])
                except ValueError:
                    pass

            exp = None
            if pd.notna(p.get("EXP")) and p["EXP"] != "R":
                try:
                    exp = int(p["EXP"])
                except ValueError:
                    pass
            elif p.get("EXP") == "R":
                exp = 0

            all_players.append({
                "player_id": player_id,
                "full_name": p.get("PLAYER", ""),
                "position": p.get("POSITION", ""),
                "height_inches": height_inches,
                "weight_lbs": weight,
                "birth_date": p.get("BIRTH_DATE", ""),
                "experience": exp,
                "is_active": 1,
            })
            all_assignments.append({
                "player_id": player_id,
                "team_id": team_id,
                "season_id": season,
                "jersey_number": str(p.get("NUM", "")),
                "listed_position": p.get("POSITION", ""),
            })

        logger.info(f"  Roster for team {team_id}: {len(roster)} players")
        return all_players, all_assignments

    def collect_player_season_stats(self, season: str):
        """Collect per-game and advanced player stats for a season. ~4 API calls."""
        # Base stats (PerGame)
        dfs = self._call_endpoint(
            LeagueDashPlayerStats,
            season=season,
            per_mode_detailed="PerGame",
            season_type_all_star="Regular Season",
        )
        base = dfs[0]

        # Per36 stats
        dfs36 = self._call_endpoint(
            LeagueDashPlayerStats,
            season=season,
            per_mode_detailed="Per36",
            season_type_all_star="Regular Season",
        )
        per36 = dfs36[0]

        # Advanced stats
        dfs_adv = self._call_endpoint(
            LeagueDashPlayerStats,
            season=season,
            per_mode_detailed="PerGame",
            measure_type_detailed_defense="Advanced",
            season_type_all_star="Regular Season",
        )
        adv = dfs_adv[0]

        if base.empty:
            logger.warning(f"No player stats found for {season}")
            return

        # Build combined DataFrame
        rows = []
        for _, b in base.iterrows():
            pid = int(b["PLAYER_ID"])
            tid = int(b["TEAM_ID"])

            # Find matching per36 and advanced rows
            p36_row = per36[per36["PLAYER_ID"] == pid]
            adv_row = adv[adv["PLAYER_ID"] == pid]

            mpg = b.get("MIN", 0) or 0
            gp = b.get("GP", 0) or 0

            row = {
                "player_id": pid,
                "team_id": tid,
                "season_id": season,
                "gp": gp,
                "minutes_total": mpg * gp if mpg and gp else 0,
                "minutes_per_game": mpg,
                "pts_pg": b.get("PTS", 0),
                "reb_pg": b.get("REB", 0),
                "ast_pg": b.get("AST", 0),
                "stl_pg": b.get("STL", 0),
                "blk_pg": b.get("BLK", 0),
                "tov_pg": b.get("TOV", 0),
                "fg_pct": b.get("FG_PCT", 0),
                "fg3_pct": b.get("FG3_PCT", 0),
                "ft_pct": b.get("FT_PCT", 0),
                "fg3a_pg": b.get("FG3A", 0),
                "fta_pg": b.get("FTA", 0),
            }

            # Advanced
            if not adv_row.empty:
                a = adv_row.iloc[0]
                row.update({
                    "usg_pct": a.get("USG_PCT", 0),
                    "ast_pct": a.get("AST_PCT", 0),
                    "reb_pct": a.get("REB_PCT", 0),
                    "ts_pct": a.get("TS_PCT", 0),
                    "efg_pct": a.get("EFG_PCT", 0),
                    "off_rating": a.get("OFF_RATING", 0),
                    "def_rating": a.get("DEF_RATING", 0),
                    "net_rating": a.get("NET_RATING", 0),
                    "pie": a.get("PIE", 0),
                    "pace": a.get("PACE", 0),
                })
            else:
                row.update({
                    "usg_pct": 0, "ast_pct": 0, "reb_pct": 0,
                    "ts_pct": 0, "efg_pct": 0, "off_rating": 0,
                    "def_rating": 0, "net_rating": 0, "pie": 0, "pace": 0,
                })

            # Per36
            if not p36_row.empty:
                p = p36_row.iloc[0]
                row.update({
                    "pts_per36": p.get("PTS", 0),
                    "reb_per36": p.get("REB", 0),
                    "ast_per36": p.get("AST", 0),
                    "stl_per36": p.get("STL", 0),
                    "blk_per36": p.get("BLK", 0),
                    "tov_per36": p.get("TOV", 0),
                    "fg3a_per36": p.get("FG3A", 0),
                    "fta_per36": p.get("FTA", 0),
                })
            else:
                row.update({
                    "pts_per36": 0, "reb_per36": 0, "ast_per36": 0,
                    "stl_per36": 0, "blk_per36": 0, "tov_per36": 0,
                    "fg3a_per36": 0, "fta_per36": 0,
                })

            rows.append(row)

        df = pd.DataFrame(rows)
        from db.connection import execute
        execute("DELETE FROM player_season_stats WHERE season_id = ?", self.db_path, [season])
        self._save(df, "player_season_stats")
        logger.info(f"Saved {len(df)} player season stats for {season}")

        # ── Backfill players + roster_assignments from league-wide stats ──
        # CommonTeamRoster can miss rookies, mid-season additions, and
        # two-way players. LeagueDashPlayerStats returns EVERY player who
        # has logged minutes, so we use it as the authoritative source to
        # patch any gaps.
        self._backfill_from_league_stats(base, season)

    def _backfill_from_league_stats(self, base_df: pd.DataFrame, season: str):
        """Backfill players and roster_assignments from LeagueDashPlayerStats.

        CommonTeamRoster misses rookies, mid-season trades, two-way players,
        and late-season call-ups. This method patches any player who appears
        in league-wide stats but is missing from the players or
        roster_assignments tables — fixing the JOIN gap that made 71+ players
        invisible to the model.
        """


        # Get existing player IDs and roster assignments
        try:
            existing_players = set(
                read_query("SELECT player_id FROM players", self.db_path)
                ["player_id"].tolist()
            )
        except Exception:
            existing_players = set()

        try:
            existing_assignments = set(
                read_query(
                    "SELECT player_id FROM roster_assignments WHERE season_id = ?",
                    self.db_path, [season]
                )["player_id"].tolist()
            )
        except Exception:
            existing_assignments = set()

        new_players = []
        new_assignments = []

        for _, b in base_df.iterrows():
            pid = int(b["PLAYER_ID"])
            tid = int(b["TEAM_ID"])
            name = b.get("PLAYER_NAME", "") or ""

            # Backfill players table
            if pid not in existing_players:
                new_players.append({
                    "player_id": pid,
                    "full_name": name,
                    "position": "",
                    "height_inches": None,
                    "weight_lbs": None,
                    "birth_date": "",
                    "experience": None,
                    "is_active": 1,
                })
                existing_players.add(pid)

            # Backfill roster_assignments table
            if pid not in existing_assignments:
                new_assignments.append({
                    "player_id": pid,
                    "team_id": tid,
                    "season_id": season,
                    "jersey_number": "",
                    "listed_position": "",
                })
                existing_assignments.add(pid)

        if new_players:
            players_df = pd.DataFrame(new_players)
            save_dataframe(players_df, "players", self.db_path, if_exists="append")
            logger.info(
                f"  Backfilled {len(new_players)} missing players "
                f"(rookies/trades/two-way)"
            )

        if new_assignments:
            assign_df = pd.DataFrame(new_assignments)
            save_dataframe(assign_df, "roster_assignments", self.db_path, if_exists="append")
            logger.info(
                f"  Backfilled {len(new_assignments)} missing roster assignments"
            )

        if not new_players and not new_assignments:
            logger.info("  No backfill needed — all players accounted for")

    def collect_team_season_stats(self, season: str):
        """Collect team-level season stats. ~2 API calls."""
        # Base team stats
        dfs = self._call_endpoint(
            LeagueDashTeamStats,
            season=season,
            per_mode_detailed="PerGame",
            season_type_all_star="Regular Season",
        )
        base = dfs[0]

        # Advanced team stats
        dfs_adv = self._call_endpoint(
            LeagueDashTeamStats,
            season=season,
            per_mode_detailed="PerGame",
            measure_type_detailed_defense="Advanced",
            season_type_all_star="Regular Season",
        )
        adv = dfs_adv[0]

        if base.empty:
            logger.warning(f"No team stats found for {season}")
            return

        rows = []
        for _, b in base.iterrows():
            tid = int(b["TEAM_ID"])
            adv_row = adv[adv["TEAM_ID"] == tid]

            row = {
                "team_id": tid,
                "season_id": season,
                "gp": b.get("GP", 0),
                "fg_pct": b.get("FG_PCT", 0),
                "fg3_pct": b.get("FG3_PCT", 0),
            }

            # Compute fg3a_rate and ft_rate
            fga = b.get("FGA", 0) or 1
            row["fg3a_rate"] = (b.get("FG3A", 0) or 0) / fga if fga > 0 else 0
            row["ft_rate"] = (b.get("FTA", 0) or 0) / fga if fga > 0 else 0

            if not adv_row.empty:
                a = adv_row.iloc[0]
                row.update({
                    "pace": a.get("PACE", 0),
                    "off_rating": a.get("OFF_RATING", 0),
                    "def_rating": a.get("DEF_RATING", 0),
                    "net_rating": a.get("NET_RATING", 0),
                    "oreb_pct": a.get("OREB_PCT", 0),
                    "dreb_pct": a.get("DREB_PCT", 0),
                    "ast_pct": a.get("AST_PCT", 0),
                    "tov_pct": a.get("TM_TOV_PCT", 0),
                    "ast_tov_ratio": a.get("AST_TO", 0),
                })
            else:
                row.update({
                    "pace": 0, "off_rating": 0, "def_rating": 0, "net_rating": 0,
                    "oreb_pct": 0, "dreb_pct": 0, "ast_pct": 0, "tov_pct": 0,
                    "ast_tov_ratio": 0,
                })

            rows.append(row)

        df = pd.DataFrame(rows)
        from db.connection import execute
        execute("DELETE FROM team_season_stats WHERE season_id = ?", self.db_path, [season])
        self._save(df, "team_season_stats")
        logger.info(f"Saved {len(df)} team season stats for {season}")

    def collect_for_season(self, season: str):
        """Run all player/team collection for a season."""
        logger.info(f"=== Collecting player/team data for {season} ===")
        self.collect_teams()
        self.collect_rosters(season)
        self.collect_player_season_stats(season)
        self.collect_team_season_stats(season)

"""NFL pipeline paths and data sources (shadow mode — nothing here publishes).

Every input is downloaded from a public source and either cached outside the
repo (raw play-by-play, ~20 MB per season) or reduced to a compact derived
table under nfl_pipeline/data/ that is committed:

  nflverse (github.com/nflverse/nflverse-data releases, CC-BY 4.0)
    schedules/games.csv            schedule, scores, spread_line, total_line,
                                   rest days, starting QB ids, stadium
    pbp/play_by_play_{season}.parquet   play-by-play with EPA (nflfastR model)
    injuries/injuries_{season}.parquet  weekly injury reports
    depth_charts/depth_charts_{season}.parquet   depth charts (2025+: dated)
  ESPN public API (site.api.espn.com / sports.core.api.espn.com)
    scoreboard                     this week's games, kickoff, live odds
    events/{id}/competitions/{id}/odds   open / close spread per provider
"""

import os

PKG = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(PKG)
DATA = os.path.join(PKG, "data")
REPORTS = os.path.join(REPO, "reports")
REFERENCE = os.path.join(REPO, "data", "reference")

# Raw downloads live outside the repo (Actions: restored from actions/cache).
CACHE = os.environ.get("NFL_CACHE_DIR") or os.path.join(os.path.expanduser("~"), ".cache", "morellosims-nfl")

NFLVERSE = "https://github.com/nflverse/nflverse-data/releases/download"
SCHEDULES_URL = f"{NFLVERSE}/schedules/games.csv"
PBP_URL = NFLVERSE + "/pbp/play_by_play_{season}.parquet"
INJURIES_URL = NFLVERSE + "/injuries/injuries_{season}.parquet"
DEPTH_URL = NFLVERSE + "/depth_charts/depth_charts_{season}.parquet"

ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
ESPN_CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"

FIRST_SEASON = 2016          # first season of play-by-play we use
CURRENT_SEASON = 2026

# Derived, committed tables (each well under 20 MB).
SCHEDULES_CSV = os.path.join(DATA, "schedules.csv")      # 2016+ games, compact columns
TEAM_GAMES_CSV = os.path.join(DATA, "team_games.csv")    # one row per team-game: EPA sums
QB_GAMES_CSV = os.path.join(DATA, "qb_games.csv")        # one row per QB-game: dropbacks, EPA
ESPN_LINES_CSV = os.path.join(DATA, "espn_lines.csv")    # ESPN open / close spreads (2024+)

SHADOW_LEDGER = os.path.join(REPORTS, "shadow_nfl.json")
BACKTEST_JSON = os.path.join(REPORTS, "nfl_backtest.json")
BACKTEST_TXT = os.path.join(REPORTS, "nfl_backtest.txt")
TIERS_JSON = os.path.join(PKG, "tiers.json")             # written by the backtest; empty = no tier
PICKS_JSON = os.path.join(REPO, "picks", "nfl.json")     # public picks: only when nfl_publish is on

TEAMS_REF = os.path.join(REFERENCE, "nfl_teams_espn_2026.json")
FIELD_REF = os.path.join(REFERENCE, "nfl_field_dimensions.json")

BREAK_EVEN = 110 / 210       # win rate needed at -110 (52.38%)

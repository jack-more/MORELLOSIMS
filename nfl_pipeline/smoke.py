#!/usr/bin/env python3
"""Source smoke test: can this machine (e.g. a GitHub Actions runner) reach
every NFL data source, and does each return what the pipeline expects?

  python3 nfl_pipeline/smoke.py      # exit 1 if any source fails
"""

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (  # noqa: E402
    CURRENT_SEASON, DEPTH_URL, ESPN_CORE, ESPN_SITE, INJURIES_URL, PBP_URL, SCHEDULES_URL,
)
import sources  # noqa: E402


def check(name, fn):
    try:
        msg = fn()
        print(f"  PASS  {name}: {msg}")
        return True
    except Exception as e:
        print(f"  FAIL  {name}: {type(e).__name__}: {e}")
        return False


def schedules():
    import pandas as pd
    g = pd.read_csv(io.BytesIO(sources.fetch(SCHEDULES_URL)), low_memory=False)
    cur = g[g["season"] == CURRENT_SEASON]
    assert len(cur) >= 256, f"only {len(cur)} {CURRENT_SEASON} games"
    for c in ("spread_line", "result", "home_qb_id", "away_rest", "espn"):
        assert c in g.columns, f"missing column {c}"
    return f"{len(g)} games, {len(cur)} in {CURRENT_SEASON}, {int(cur['result'].notna().sum())} final"


def parquet(url, need):
    def f():
        import pandas as pd
        df = pd.read_parquet(io.BytesIO(sources.fetch(url)))
        miss = [c for c in need if c not in df.columns]
        assert not miss, f"missing columns {miss}"
        return f"{len(df)} rows"
    return f


def espn_scoreboard():
    sb = sources.get_json(f"{ESPN_SITE}/scoreboard")
    ev = sb.get("events", [])
    assert ev, "no events"
    return f"season {sb['season']['year']} week {sb['week']['number']}: {len(ev)} events"


def espn_odds():
    import pandas as pd
    from config import SCHEDULES_CSV
    s = pd.read_csv(SCHEDULES_CSV)
    g = s[(s["season"] == CURRENT_SEASON - 1) & s["espn"].notna()].iloc[0]
    import espn
    res = espn.event_lines(int(g["espn"]))
    assert res, f"no open/close for {g['game_id']}"
    return f"{g['game_id']}: {res[1]} open {res[2]} close {res[3]} (home-favored-by)"


def espn_teams():
    t = sources.get_json(f"{ESPN_SITE}/teams")["sports"][0]["leagues"][0]["teams"]
    assert len(t) == 32, f"{len(t)} teams"
    return "32 teams"


def wikipedia():
    from reference import FIELD_PAGE, STADIUM_PAGE, wiki
    a, ra = wiki(FIELD_PAGE)
    b, rb = wiki(STADIUM_PAGE)
    return f"field revid {ra}, stadiums revid {rb}"


def main():
    print(f"NFL source smoke test (season {CURRENT_SEASON})")
    ok = all([
        check("nflverse schedules", schedules),
        check("nflverse pbp", parquet(PBP_URL.format(season=CURRENT_SEASON), ["epa", "qb_dropback", "posteam", "wp"])),
        check("nflverse pbp (history)", parquet(PBP_URL.format(season=2019), ["epa", "qb_dropback"])),
        check("nflverse injuries", parquet(INJURIES_URL.format(season=CURRENT_SEASON), ["gsis_id", "report_status", "week"])),
        check("nflverse depth charts", parquet(DEPTH_URL.format(season=CURRENT_SEASON), ["pos_abb", "pos_rank", "dt"])),
        check("ESPN scoreboard", espn_scoreboard),
        check("ESPN core odds (open/close)", espn_odds),
        check("ESPN teams", espn_teams),
        check("Wikipedia (reference)", wikipedia),
    ])
    print("ALL SOURCES OK" if ok else "SOME SOURCES FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Reference snapshots for NFL cards — every fact fetched, never typed.

  data/reference/nfl_teams_espn_2026.json
      names, colors, logos: ESPN teams API
      venues: ESPN franchise.venue cross-checked against (a) the stadium nflverse
      records for each team's 2026 home games and (b) Wikipedia's list of
      current NFL stadiums. The card uses a venue only when at least two
      sources agree; disagreements are written into the snapshot.
      abbreviation map ESPN ↔ nflverse: joined on ESPN event ids that the
      nflverse schedule carries (no hand-typed table).
  data/reference/nfl_field_dimensions.json
      field geometry parsed from Wikipedia "American football field" (wikitext
      at a recorded revision); each value stores the sentence it came from.

  python3 nfl_pipeline/reference.py
"""

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import ESPN_SITE, FIELD_REF, SCHEDULES_CSV, TEAMS_REF  # noqa: E402
import sources  # noqa: E402

WIKI_API = "https://en.wikipedia.org/w/api.php?action=parse&format=json&formatversion=2&redirects=1&prop=wikitext|revid&page="
STADIUM_PAGE = "List_of_current_National_Football_League_stadiums"
FIELD_PAGE = "American_football_field"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def wiki(page):
    d = sources.get_json(WIKI_API + page)["parse"]
    return d["wikitext"], d.get("revid")


def wiki_stadiums():
    """team display name -> stadium name, from the 'Current' wikitable."""
    txt, rev = wiki(STADIUM_PAGE)
    table = txt[txt.find("{|"): txt.find("|}", txt.find("{|"))]
    out = {}
    for row in table.split("\n|-")[1:]:
        m = re.search(r'!\s*scope="row"\s*\|\s*\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', row)
        if not m:
            continue
        name = (m.group(2) or m.group(1)).strip()
        after = row[m.end():]
        teams_cell = after.split("\n|", 2)[1] if "\n|" in after else ""
        for t in re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", teams_cell):
            out[t.strip()] = name
    return out, rev


def nflverse_home_stadiums():
    import pandas as pd
    s = pd.read_csv(SCHEDULES_CSV)
    s = s[(s["season"] == s["season"].max()) & (s["location"] == "Home") & (s["game_type"] == "REG")]
    return {t: Counter(g["stadium"].dropna()).most_common(1)[0][0] for t, g in s.groupby("home_team")}


def espn_to_nflverse():
    """ESPN abbreviation -> nflverse abbreviation via shared ESPN event ids."""
    import pandas as pd
    s = pd.read_csv(SCHEDULES_CSV)
    s = s[(s["season"] == s["season"].max()) & s["espn"].notna()]
    m = {}
    for day in sorted(s["gameday"].unique())[:6]:
        sb = sources.get_json(f"{ESPN_SITE}/scoreboard?dates={day.replace('-', '')}")
        for e in sb.get("events", []):
            row = s[s["espn"].astype("int64").astype(str) == str(e["id"])]
            if row.empty:
                continue
            teams = {t["homeAway"]: t["team"]["abbreviation"] for t in e["competitions"][0]["competitors"]}
            m[teams["home"]] = row.iloc[0]["home_team"]
            m[teams["away"]] = row.iloc[0]["away_team"]
    return m


def build_teams():
    raw = sources.get_json(f"{ESPN_SITE}/teams")["sports"][0]["leagues"][0]["teams"]
    abbr = espn_to_nflverse()
    nv_stad = nflverse_home_stadiums()
    wk, rev = wiki_stadiums()
    teams, issues = {}, []
    for item in raw:
        t = item["team"]
        detail = sources.get_json(f"{ESPN_SITE}/teams/{t['id']}")["team"]
        venue = ((detail.get("franchise") or {}).get("venue") or {})
        nv = abbr.get(t["abbreviation"])
        if nv is None:
            issues.append(f"{t['abbreviation']}: no nflverse abbreviation match")
            continue
        cands = {"espn": venue.get("fullName"), "nflverse": nv_stad.get(nv), "wikipedia": wk.get(t["displayName"])}
        votes = Counter(norm(v) for v in cands.values() if v)
        best_norm, n = votes.most_common(1)[0] if votes else ("", 0)
        chosen = next((v for v in cands.values() if v and norm(v) == best_norm), None) if n >= 2 else None
        if n < 3:
            issues.append(f"{nv}: venue sources disagree {cands}" + ("" if chosen else " — no 2-source agreement, venue left blank"))
        logos = [l["href"] for l in t.get("logos", [])]
        teams[nv] = {
            "espn_id": t["id"], "espn_abbr": t["abbreviation"], "location": t["location"], "name": t["name"],
            "display": t["displayName"], "color": "#" + (t.get("color") or "000000"),
            "alt": "#" + (t.get("alternateColor") or "ffffff"),
            "logo": next((h for h in logos if "/500/" in h and "dark" not in h and "scoreboard" not in h), logos[0] if logos else None),
            "venue": chosen, "venue_city": (venue.get("address") or {}).get("city"),
            "venue_sources": cands,
        }
    snap = {
        "_source": f"{ESPN_SITE}/teams (+ /teams/{{id}} for franchise.venue)",
        "_venue_check": (f"venue = name agreed by >= 2 of: ESPN franchise.venue, nflverse schedule stadium for the "
                         f"team's latest-season home games, Wikipedia {STADIUM_PAGE} (revid {rev})"),
        "_abbr_map": "keys are nflverse abbreviations; ESPN's are in espn_abbr (joined on ESPN event ids in the nflverse schedule)",
        "_fetched": now(), "_issues": issues, "teams": dict(sorted(teams.items())),
    }
    with open(TEAMS_REF, "w") as f:
        json.dump(snap, f, indent=1)
    print(f"wrote {TEAMS_REF}: {len(teams)} teams, {len(issues)} venue notes")
    for i in issues:
        print("  ", i)


def _find(txt, pattern, label):
    m = re.search(pattern, txt, flags=re.S)
    if not m:
        raise SystemExit(f"field source no longer states {label!r}: pattern {pattern!r} not found")
    start = txt.rfind(". ", 0, m.start()) + 2
    end = txt.find(". ", m.end())
    return m, re.sub(r"\s+", " ", txt[max(0, start): end + 1]).strip()


def build_field():
    txt, rev = wiki(FIELD_PAGE)
    vals, quotes = {}, {}
    m, q = _find(txt, r"rectangle \{\{convert\|(\d+)\|ft\|m\}\} long by \{\{convert\|(\d+)\|ft\|m\}\} wide", "field size")
    vals["length_ft"], vals["width_ft"] = int(m.group(1)), int(m.group(2))
    quotes["length_ft"] = quotes["width_ft"] = q
    m, q = _find(txt, r"goal lines span the width of the field and run \{\{convert\|(\d+)\|yd\|m\}\} parallel to each end line", "end zone depth")
    vals["end_zone_yd"] = int(m.group(1))
    quotes["end_zone_yd"] = q
    m, q = _find(txt, r"at (\d+)-yard intervals from each goal line", "yard line spacing")
    vals["yard_line_interval_yd"] = int(m.group(1))
    quotes["yard_line_interval_yd"] = q
    m, q = _find(txt, r"hash marks are \{\{convert\|(\d+)\|ft\|(\d+)\|in\|m\}\} from each sideline", "NFL hash marks")
    vals["hash_from_sideline_ft"] = round(int(m.group(1)) + int(m.group(2)) / 12, 4)
    quotes["hash_from_sideline_ft"] = q
    m, q = _find(txt, r"Between the 5-yard lines they are marked with (\d+)-foot lines", "hash tick length")
    vals["hash_tick_ft"] = int(m.group(1))
    quotes["hash_tick_ft"] = q
    m, q = _find(txt, r"goal posts \(colloquially \"uprights\"\) at each end of the crossbar \{\{convert\|(\d+)\|ft\|(\d+)\|in\|m\}\} apart", "goalpost width")
    vals["goalpost_width_ft"] = round(int(m.group(1)) + int(m.group(2)) / 12, 4)
    quotes["goalpost_width_ft"] = q
    m, q = _find(txt, r"crossbar \{\{convert\|(\d+)\|ft\|m\}\} above the ground", "crossbar height")
    vals["crossbar_height_ft"] = int(m.group(1))
    quotes["crossbar_height_ft"] = q
    m, q = _find(txt, r"sidelines and end lines to be \{\{convert\|(\d+)\|ft\|m\}\} wide", "boundary width")
    vals["boundary_line_ft"] = int(m.group(1))
    quotes["boundary_line_ft"] = q
    m, q = _find(txt, r"bottom edge of each number to be (\d+) yards from the sideline", "numbers")
    vals["number_bottom_from_sideline_yd"] = int(m.group(1))
    quotes["number_bottom_from_sideline_yd"] = q
    m, q = _find(txt, r"a \{\{convert\|(\d+)\|ft\|m\|adj=on\}\} line is painted parallel to the goal line at the center of the (\d+)-yard line", "try line")
    vals["try_line_ft"], vals["try_line_yd"] = int(m.group(1)), int(m.group(2))
    quotes["try_line_ft"] = quotes["try_line_yd"] = q
    assert vals["length_ft"] == 300 + 2 * vals["end_zone_yd"] * 3, "length != 100 yd + two end zones"
    snap = {"_source": f"https://en.wikipedia.org/wiki/{FIELD_PAGE} (wikitext revid {rev}), fetched {now()}",
            "_note": "NFL values; each number was parsed from the quoted sentence (see _quotes).",
            **vals, "_quotes": quotes}
    with open(FIELD_REF, "w") as f:
        json.dump(snap, f, indent=1)
    print(f"wrote {FIELD_REF}: {vals}")


if __name__ == "__main__":
    build_field()
    build_teams()

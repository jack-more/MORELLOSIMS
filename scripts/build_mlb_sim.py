#!/usr/bin/env python3
"""
build_mlb_sim.py — Generate mlbsim/index.html from live MLB data + atlas.

Fetches today's schedule, lineups, probable pitchers from MLB Stats API,
runs the matchup model against atlas data, and renders the full page.

Usage: python3 scripts/build_mlb_sim.py
"""

import json, os, sys, math, requests, time as _time
import urllib.request  # used by _fetch_action_network_odds + _fetch_espn_scoreboard_odds
from datetime import datetime, timezone, timedelta
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
ATLAS_DIR = os.path.join(REPO_ROOT, "atlas")
OUTPUT = os.path.join(REPO_ROOT, "mlbsim", "index.html")
RECORD_PATH = os.path.join(REPO_ROOT, "mlbsim", "record.json")

# ─── Season record (single source of truth) ──────────────────────────────────
# Read from mlbsim/record.json so updating the record never requires editing
# this script. Falls back to a sane default if file is missing/malformed.
try:
    with open(RECORD_PATH) as _rf:
        _rec = json.load(_rf)
    SEASON_RECORD = f'{_rec["wins"]}-{_rec["losses"]}'
    _roi = _rec["roi_pct"]
    SEASON_ROI_VALUE = f'{"+" if _roi >= 0 else ""}{_roi:.1f}%'
    SEASON_ROI = f'{SEASON_ROI_VALUE} ROI'
except Exception as _e:
    print(f"  WARN record.json: {_e} — falling back to placeholder")
    SEASON_RECORD = "0-0"
    SEASON_ROI_VALUE = "+0.0%"
    SEASON_ROI = "+0.0% ROI"

MLB_API = "https://statsapi.mlb.com/api/v1"
ET = timezone(timedelta(hours=-4))
NOW = datetime.now(ET)
TODAY = NOW.strftime("%Y-%m-%d")
DATE_DISPLAY = NOW.strftime("%b %d").upper().replace(" 0", " ")  # "APR 3"
DATE_SHORT = NOW.strftime("%b %-d").upper()  # for slate

# ─── Team metadata ────────────────────────────────────────────────────────────
TEAMS = {
    "ARI":{"id":109,"color":"#A71930"},"AZ":{"id":109,"color":"#A71930"},
    "ATL":{"id":144,"color":"#CE1141"},
    "BAL":{"id":110,"color":"#DF4601"},"BOS":{"id":111,"color":"#BD3039"},
    "CHC":{"id":112,"color":"#0E3386"},"CIN":{"id":113,"color":"#C6011F"},
    "CLE":{"id":114,"color":"#00385D"},"COL":{"id":115,"color":"#333366"},
    "CWS":{"id":145,"color":"#27251F"},"DET":{"id":116,"color":"#0C2340"},
    "HOU":{"id":117,"color":"#002D62"},"KC": {"id":118,"color":"#004687"},
    "LAA":{"id":108,"color":"#BA0021"},"LAD":{"id":119,"color":"#005A9C"},
    "MIA":{"id":146,"color":"#00A3E0"},"MIL":{"id":158,"color":"#0C2C56"},
    "MIN":{"id":142,"color":"#002B5C"},"NYM":{"id":121,"color":"#002D72"},
    "NYY":{"id":147,"color":"#092C5C"},"OAK":{"id":133,"color":"#003831"},
    "ATH":{"id":133,"color":"#003831"},
    "PHI":{"id":143,"color":"#E81828"},"PIT":{"id":134,"color":"#27251F"},
    "SD": {"id":135,"color":"#2F241D"},"SEA":{"id":136,"color":"#0C2C56"},
    "SF": {"id":137,"color":"#FD5A1E"},"STL":{"id":138,"color":"#C41E3A"},
    "TB": {"id":139,"color":"#092C5C"},"TEX":{"id":140,"color":"#003278"},
    "TOR":{"id":141,"color":"#134A8E"},"WSH":{"id":120,"color":"#AB0003"},
    "WAS":{"id":120,"color":"#AB0003"},
}

def load_atlas(f):
    with open(os.path.join(ATLAS_DIR, f)) as fh:
        return json.load(fh)

def fetch(url):
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  WARN fetch {url}: {e}")
        return None

# ─── wOBA → MS ───────────────────────────────────────────────────────────────
def woba_to_ms(woba):
    if woba >= .400: return min(99, 90 + int((woba - .400) / .005))
    if woba >= .370: return 80 + int((woba - .370) / .003)
    if woba >= .340: return 70 + int((woba - .340) / .003)
    if woba >= .310: return 60 + int((woba - .310) / .003)
    if woba >= .270: return 50 + int((woba - .270) / .004)
    return max(40, 40 + int((woba - .200) / .007))

def ms_class(ms):
    if ms >= 85: return "ms-elite"
    if ms >= 70: return "ms-favorable"
    if ms >= 55: return "ms-neutral"
    return "ms-tough"

def woba_class(base, vs):
    diff = vs - base
    if diff > 0.03: return "hot"
    if diff < -0.03: return "cold"
    return "neutral"

def conf_color(c):
    if c >= 8: return "#00FF55"
    if c >= 6: return "#7FFF00"
    if c >= 4: return "#FFD600"
    if c >= 2: return "#FF8C00"
    return "#FF3333"

# ─── BaseRuns ─────────────────────────────────────────────────────────────────
def base_runs(pa, h, bb, hr, tb):
    if pa == 0: return 0
    a = h + bb - hr
    b = 1.02 * (1.4 * tb - 0.6 * h + 0.1 * bb)
    c = pa - h - bb
    d = hr
    if b + c == 0: return d
    return a * b / (b + c) + d


def pythagorean_wp(team_runs, opp_runs, exp=1.83):
    """Pythagorean Win% — standard sabermetric formula.
    exp=1.83 is the MLB-standard Pythagenpat exponent."""
    if team_runs <= 0 and opp_runs <= 0:
        return 50.0
    if opp_runs <= 0:
        return 95.0
    if team_runs <= 0:
        return 5.0
    tr = team_runs ** exp
    opp = opp_runs ** exp
    return round(tr / (tr + opp) * 100, 1)


def wp_to_ml(prob):
    """Convert win probability (0-100) to American moneyline odds."""
    if prob <= 0 or prob >= 100:
        return ""
    if prob >= 50:
        return f"{int(round(-(prob / (100 - prob)) * 100))}"
    else:
        return f"+{int(round(((100 - prob) / prob) * 100))}"


# ─── Park Factors (runs, 100 = neutral) ────────────────────────────────────
# Source: FanGraphs 5-year rolling park factors for runs scored.
# >100 = hitter-friendly, <100 = pitcher-friendly.
PARK_FACTOR = {
    "COL": 1.14, "BOS": 1.06, "CIN": 1.05, "TEX": 1.04, "ATL": 1.03,
    "AZ": 1.03, "PHI": 1.02, "CHC": 1.02, "MIN": 1.02, "MIL": 1.01,
    "TOR": 1.01, "NYY": 1.01, "BAL": 1.00, "LAA": 1.00, "WSH": 1.00,
    "DET": 0.99, "KC": 0.99, "HOU": 0.99, "PIT": 0.99, "SF": 0.98,
    "CLE": 0.98, "STL": 0.98, "CWS": 0.98, "TB": 0.97, "SD": 0.97,
    "LAD": 0.97, "MIA": 0.96, "SEA": 0.96, "NYM": 0.96, "ATH": 0.96,
    "OAK": 0.96,
}

# ─── Load atlas data ─────────────────────────────────────────────────────────
print("Loading atlas...")
hvc_data = load_atlas("hitter_vs_cluster.json")
pitcher_tiers = load_atlas("pitcher_tiers.json")
pitcher_seasons = load_atlas("pitcher_seasons.json")
clusters_meta = load_atlas("clusters.json")

# Build indexes
# pitcher_id → most recent pitcher_season record
pitcher_idx = {}
for ps in pitcher_seasons:
    pid = ps["pitcher"]
    yr = ps["game_year"]
    if pid not in pitcher_idx or yr > pitcher_idx[pid]["game_year"]:
        pitcher_idx[pid] = ps

# pitcher_id → most recent tier record
tier_idx = {}
for k, v in pitcher_tiers.items():
    pid = v["pitcher"]
    yr = v["game_year"]
    if pid not in tier_idx or yr > tier_idx[pid]["game_year"]:
        tier_idx[pid] = v

# (batter_id, cluster) → BLENDED hvc record across recent years (2025+2026)
# Weight 2026 at 1.5x to favor current form, but keep 2025 for sample size
YEAR_WEIGHT = {2026: 1.5, 2025: 1.0, 2024: 0.6, 2023: 0.4}
BLEND_YEARS = {2025, 2026}  # years to blend (keep last 2 seasons)

hvc_by_key = {}  # (batter, cluster) → list of records from blend years
for r in hvc_data:
    key = (r["batter"], r["cluster"])
    yr = r["game_year"]
    if yr in BLEND_YEARS:
        hvc_by_key.setdefault(key, []).append(r)

hvc_idx = {}
for key, records in hvc_by_key.items():
    total_wpa = 0; total_w = 0
    total_h = 0; total_bb = 0; total_hr = 0; total_tb = 0
    total_pa_raw = 0; total_singles = 0; total_doubles = 0; total_triples = 0
    for r in records:
        yr = r["game_year"]
        pa = r["PA"]
        if pa < 1: continue
        w = pa * YEAR_WEIGHT.get(yr, 0.5)
        total_wpa += w * r["wOBA"]
        total_w += w
        total_pa_raw += pa
        total_h += r["H"] * YEAR_WEIGHT.get(yr, 0.5)
        total_bb += r["BB"] * YEAR_WEIGHT.get(yr, 0.5)
        total_hr += r["HR"] * YEAR_WEIGHT.get(yr, 0.5)
        total_singles += r.get("singles", 0) * YEAR_WEIGHT.get(yr, 0.5)
        total_doubles += r.get("doubles", 0) * YEAR_WEIGHT.get(yr, 0.5)
        total_triples += r.get("triples", 0) * YEAR_WEIGHT.get(yr, 0.5)
        total_tb += (r.get("singles", 0) + r.get("doubles", 0)*2 + r.get("triples", 0)*3 + r["HR"]*4) * YEAR_WEIGHT.get(yr, 0.5)
    if total_w > 0:
        hvc_idx[key] = {
            "batter": key[0], "cluster": key[1],
            "game_year": max(r["game_year"] for r in records),
            "PA": total_pa_raw,
            "wOBA": total_wpa / total_w,
            "H": total_h, "BB": total_bb, "HR": total_hr,
            "singles": total_singles, "doubles": total_doubles,
            "triples": total_triples,
        }

# Also keep fallback for batters only in older years (pre-2025)
for r in hvc_data:
    key = (r["batter"], r["cluster"])
    if key not in hvc_idx:
        yr = r["game_year"]
        if key not in hvc_idx or yr > hvc_idx[key]["game_year"]:
            hvc_idx[key] = r

# batter overall wOBA + component rates (weighted avg across blend years)
# Used for thin-sample PA confidence blending — regress toward the BATTER'S
# own rates, not generic league averages.
batter_woba_accum = {}  # bid → (total_wpa, total_w)
batter_rates_accum = {}  # bid → {h, bb, hr, tb, pa_w} (year-weighted sums)
for r in hvc_data:
    bid = r["batter"]
    yr = r["game_year"]
    pa = r["PA"]
    if pa < 1: continue
    w = pa * YEAR_WEIGHT.get(yr, 0.3)
    if bid not in batter_woba_accum:
        batter_woba_accum[bid] = [0, 0]
    batter_woba_accum[bid][0] += w * r["wOBA"]
    batter_woba_accum[bid][1] += w
    # Accumulate component rates
    if bid not in batter_rates_accum:
        batter_rates_accum[bid] = {"h": 0, "bb": 0, "hr": 0, "tb": 0, "pa_w": 0}
    batter_rates_accum[bid]["h"] += r["H"] * YEAR_WEIGHT.get(yr, 0.3)
    batter_rates_accum[bid]["bb"] += r["BB"] * YEAR_WEIGHT.get(yr, 0.3)
    batter_rates_accum[bid]["hr"] += r["HR"] * YEAR_WEIGHT.get(yr, 0.3)
    s = r.get("singles", 0); d = r.get("doubles", 0); t = r.get("triples", 0)
    batter_rates_accum[bid]["tb"] += (s + d*2 + t*3 + r["HR"]*4) * YEAR_WEIGHT.get(yr, 0.3)
    batter_rates_accum[bid]["pa_w"] += w

def get_base_woba(bid):
    acc = batter_woba_accum.get(bid)
    if not acc or acc[1] == 0: return .310
    return acc[0] / acc[1]

# League-average fallbacks (used only when batter has zero data at all)
LG_H_RATE = 0.245; LG_BB_RATE = 0.08; LG_HR_RATE = 0.03; LG_TB_RATE = 0.40
MIN_CONF_PICK = 8  # C:8+ qualifies (8, 9, 10) — opens up the slate
MAX_FAV_BY_CONF = {
    # Per-confidence cap on max favorite odds (more negative = bigger fav).
    # Anything more favored than the cap gets filtered as odds_too_heavy.
    # Tuned 2026-05: all qualifying confidence levels can take -340 juice.
    8: -340,
    9: -340,
    10: -340,
}

def get_base_rates(bid):
    """Return batter's own H/BB/HR/TB rates for thin-sample regression."""
    acc = batter_rates_accum.get(bid)
    if not acc or acc["pa_w"] == 0:
        return LG_H_RATE, LG_BB_RATE, LG_HR_RATE, LG_TB_RATE
    pw = acc["pa_w"]
    return acc["h"] / pw, acc["bb"] / pw, acc["hr"] / pw, acc["tb"] / pw

print(f"  Pitchers indexed: {len(pitcher_idx)}")
print(f"  HVC records: {len(hvc_idx)}")

# ─── Build name → MLB ID index from atlas ───────────────────────────────────
# Used to map RotoWire player names to MLB IDs
name_to_mlb_id = {}
for r in hvc_data:
    name = r.get("batter_name", "")
    bid = r["batter"]
    if name and bid:
        name_to_mlb_id[name.lower().strip()] = bid
for ps in pitcher_seasons:
    name = ps.get("player_name", "")
    pid = ps["pitcher"]
    if name and pid:
        name_to_mlb_id[name.lower().strip()] = pid
print(f"  Name→ID index: {len(name_to_mlb_id)} players")

# ─── Scrape lineup sources (BaseballMonster + RotoWire) ─────────────────────
import re as _re
import csv as _csv
from io import StringIO as _StringIO

# Team abbreviation normalization
TEAM_ALIAS = {"ATH": "OAK", "AZ": "ARI", "ARI": "AZ", "CWS": "CHW", "CHW": "CWS", "TB": "TBR", "TBR": "TB",
              "SD": "SDP", "SDP": "SD", "SF": "SFG", "SFG": "SF", "KC": "KCR", "KCR": "KC",
              "WSH": "WAS", "WAS": "WSH"}

def normalize_abbr(abbr):
    """Normalize team abbreviation to match MLB API style."""
    return TEAM_ALIAS.get(abbr, abbr)

def fetch_baseballmonster_lineups():
    """Fetch structured CSV lineups from BaseballMonster — includes MLB IDs directly."""
    try:
        date_str = NOW.strftime("%-m/%-d/%Y")
        url = f"https://baseballmonster.com/Lineups.aspx?csv=1&d={date_str}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code != 200 or len(r.text) < 50:
            print(f"  WARN: BaseballMonster returned {r.status_code}")
            return {}

        reader = _csv.reader(_StringIO(r.text))
        header = next(reader, None)
        if not header:
            return {}

        # Group by team
        team_lineups = {}  # team_abbr → {"batters": [...], "sp_id": ..., "sp_name": ...}
        for row in reader:
            if len(row) < 7:
                continue
            team = row[0].strip()
            mlb_id = int(row[3].strip()) if row[3].strip().isdigit() else None
            name = row[4].strip()
            order = row[5].strip()
            # confirmed = row[6].strip()

            if not mlb_id:
                continue

            if team not in team_lineups:
                team_lineups[team] = {"batters": [], "sp_id": None, "sp_name": None}

            if order == "SP":
                team_lineups[team]["sp_id"] = mlb_id
                team_lineups[team]["sp_name"] = name
            elif order.isdigit():
                team_lineups[team]["batters"].append({
                    "id": mlb_id,
                    "fullName": name,
                    "order": int(order),
                    "primaryPosition": {"abbreviation": row[7].strip() if len(row) > 7 and row[7].strip() else "?"},
                    "batSide": {"code": "R"},  # BM doesn't give bat side, will be overridden if available
                })

        # Now pair teams into games — BM lists teams in away/home pairs
        teams_in_order = []
        seen = set()
        for row_text in r.text.strip().split("\n")[1:]:
            parts = row_text.split(",")
            if parts and parts[0].strip() not in seen:
                seen.add(parts[0].strip())
                teams_in_order.append(parts[0].strip())

        # Games: teams alternate away/home
        result = {}
        for i in range(0, len(teams_in_order) - 1, 2):
            away = teams_in_order[i]
            home = teams_in_order[i + 1]
            away_data = team_lineups.get(away, {})
            home_data = team_lineups.get(home, {})

            away_batters = sorted(away_data.get("batters", []), key=lambda x: x.get("order", 99))
            home_batters = sorted(home_data.get("batters", []), key=lambda x: x.get("order", 99))

            result[(away, home)] = {
                "away_sp_name": away_data.get("sp_name"),
                "home_sp_name": home_data.get("sp_name"),
                "away_sp_id": away_data.get("sp_id"),
                "home_sp_id": home_data.get("sp_id"),
                "away_lineup": away_batters,
                "home_lineup": home_batters,
            }
        return result
    except Exception as e:
        print(f"  WARN: BaseballMonster scrape failed: {e}")
        return {}

def fetch_rotowire_lineups():
    """Scrape projected/confirmed lineups from RotoWire — backup source."""
    try:
        r = requests.get("https://www.rotowire.com/baseball/daily-lineups.php",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code != 200:
            print(f"  WARN: RotoWire returned {r.status_code}")
            return {}

        all_teams = _re.findall(r'lineup__abbr[^>]*>([A-Z]+)<', r.text)
        visit_sections = _re.findall(r'<ul class="lineup__list is-visit">(.*?)</ul>', r.text, _re.DOTALL)
        home_sections = _re.findall(r'<ul class="lineup__list is-home">(.*?)</ul>', r.text, _re.DOTALL)

        def parse_section(html):
            pitcher = _re.search(r'lineup__player-highlight-name[^>]*>.*?<a[^>]*>([^<]+)</a>', html, _re.DOTALL)
            batters = _re.findall(
                r'<li class="lineup__player">\s*<div class="lineup__pos">([^<]+)</div>\s*'
                r'<a title="([^"]+)"[^>]*>[^<]+</a>\s*'
                r'<span class="lineup__bats">([^<]+)</span>',
                html, _re.DOTALL)
            return pitcher.group(1).strip() if pitcher else None, batters

        def resolve_id(name):
            if not name: return None
            key = name.lower().strip()
            if key in name_to_mlb_id:
                return name_to_mlb_id[key]
            last = key.split()[-1] if key else ""
            for k, v in name_to_mlb_id.items():
                if k.endswith(" " + last):
                    return v
            return None

        def build_lineup(batters):
            lineup = []
            for pos, name, bats in batters:
                pid = resolve_id(name)
                if pid:
                    lineup.append({
                        "id": pid, "fullName": name,
                        "primaryPosition": {"abbreviation": pos.strip()},
                        "batSide": {"code": bats.strip()},
                    })
            return lineup

        result = {}
        n_games = min(len(visit_sections), len(home_sections), len(all_teams) // 2)
        for i in range(n_games):
            away = all_teams[i * 2]
            home = all_teams[i * 2 + 1]
            v_sp, v_batters = parse_section(visit_sections[i])
            h_sp, h_batters = parse_section(home_sections[i])
            result[(away, home)] = {
                "away_sp_name": v_sp, "home_sp_name": h_sp,
                "away_sp_id": resolve_id(v_sp), "home_sp_id": resolve_id(h_sp),
                "away_lineup": build_lineup(v_batters), "home_lineup": build_lineup(h_batters),
            }
        return result
    except Exception as e:
        print(f"  WARN: RotoWire scrape failed: {e}")
        return {}

print("\nFetching external lineups...")
bm_lineups = fetch_baseballmonster_lineups()
print(f"  BaseballMonster games: {len(bm_lineups)}")
rw_lineups = fetch_rotowire_lineups()
print(f"  RotoWire games: {len(rw_lineups)}")
rw_used = 0; bm_used = 0

# ─── Fetch real sportsbook odds (ESPN) ──────────────────────────────────────
_ESPN_TEAM_MAP = {
    "Arizona Diamondbacks": "AZ", "Atlanta Braves": "ATL", "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS", "Chicago Cubs": "CHC", "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE", "Colorado Rockies": "COL",
    "Detroit Tigers": "DET", "Houston Astros": "HOU", "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD", "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL", "Minnesota Twins": "MIN", "New York Mets": "NYM",
    "New York Yankees": "NYY", "Oakland Athletics": "ATH", "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT", "San Diego Padres": "SD", "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA", "St. Louis Cardinals": "STL", "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX", "Toronto Blue Jays": "TOR", "Washington Nationals": "WSH",
}

# Action Network book IDs (we prefer DraftKings since that's what most
# users actually shop). Falls through this list per game until a real ML
# is found, so an absent DK price still gets filled by FD/Caesars/MGM.
ACTION_BOOK_PRIORITY = [
    (15,  "DraftKings"),
    (30,  "FanDuel"),
    (68,  "Caesars"),
    (71,  "BetMGM"),
    (75,  "PointsBet"),
    (123, "BetRivers"),
    (69,  "WynnBET"),
    (972, "ESPN BET"),
    (247, "Hard Rock"),
    (79,  "Unibet"),
]


def _fetch_action_network_odds():
    """Action Network public scoreboard — no auth, returns ML from up to 10
    sportsbooks per game. We pick the first book in ACTION_BOOK_PRIORITY
    that has a real moneyLine published. Returns
        {(away_abbr, home_abbr): {away_ml, home_ml, book}}.

    Action Network is the most reliable free MLB odds source — significantly
    better coverage than ESPN, and it returns 5+ books per game so any one
    book missing a line doesn't drop the game from the sim.
    """
    bookids = ",".join(str(b[0]) for b in ACTION_BOOK_PRIORITY)
    url = f"https://api.actionnetwork.com/web/v1/scoreboard/mlb?period=game&bookIds={bookids}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        })
        data = json.loads(urllib.request.urlopen(req, timeout=12).read())
    except Exception as e:
        print(f"  WARN: Action Network odds failed: {e}")
        return {}

    result = {}
    for g in data.get("games", []):
        teams = g.get("teams") or []
        if len(teams) != 2:
            continue
        # teams[0]/teams[1] order may vary; use away_team_id / home_team_id
        ht_id = g.get("home_team_id")
        at_id = g.get("away_team_id")
        by_id = {t.get("id"): t for t in teams}
        home = (by_id.get(ht_id) or {}).get("abbr")
        away = (by_id.get(at_id) or {}).get("abbr")
        if not (home and away):
            continue

        # Walk book priority — first book with a real ML wins
        odds_list = g.get("odds") or []
        odds_by_book = {o.get("book_id"): o for o in odds_list}
        for book_id, book_name in ACTION_BOOK_PRIORITY:
            o = odds_by_book.get(book_id)
            if not o:
                continue
            h_ml = o.get("ml_home")
            a_ml = o.get("ml_away")
            if h_ml is not None and a_ml is not None:
                result[(away, home)] = {
                    "away_ml": int(a_ml),
                    "home_ml": int(h_ml),
                    "book": book_name,
                }
                break
    return result


def _fetch_espn_scoreboard_odds(date_str):
    """ESPN's structured scoreboard JSON. Returns ONLY games where the book
    published a real moneyLine — never derives from spread or model.
    Returns {(away, home): {away_ml, home_ml, book}}.
    """
    try:
        url = f'https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates={date_str}'
        with urllib.request.urlopen(url, timeout=12) as r:
            data = json.loads(r.read())
        result = {}
        for ev in data.get('events', []):
            comp = ev.get('competitions', [{}])[0]
            ha_map = {}
            for t in comp.get('competitors', []):
                ha = t.get('homeAway')
                abbr = (t.get('team') or {}).get('abbreviation')
                if ha and abbr:
                    ha_map[ha] = abbr
            home, away = ha_map.get('home'), ha_map.get('away')
            if not (home and away):
                continue
            for o in comp.get('odds', []):
                home_ml = (o.get('homeTeamOdds') or {}).get('moneyLine')
                away_ml = (o.get('awayTeamOdds') or {}).get('moneyLine')
                # STRICT: require BOTH real MLs from the book. No spread→ML
                # derivation, no model fallback. If the book hasn't posted
                # ML yet, this game is excluded — better than fake numbers.
                if home_ml is not None and away_ml is not None:
                    result[(away, home)] = {
                        "away_ml": int(away_ml),
                        "home_ml": int(home_ml),
                        "book": (o.get('provider') or {}).get('name', 'ESPN'),
                    }
                    break
        return result
    except Exception as e:
        print(f"  WARN: ESPN scoreboard odds failed: {e}")
        return {}


def fetch_espn_odds():
    """Real-book ML odds — STRICT. Only returns prices the book actually
    published. Never derives, approximates, or invents.

    Source priority:
      1. Action Network public scoreboard (5+ books per game, very reliable)
      2. ESPN scoreboard JSON (hit or miss for ML)
      3. Legacy ESPN /mlb/odds HTML (browser-cookie-only — usually fails)
    """
    action_odds = _fetch_action_network_odds()
    print(f"  Action Network odds: {len(action_odds)} games (real book ML)")

    primary = _fetch_espn_scoreboard_odds(TODAY.replace("-", ""))
    print(f"  ESPN scoreboard odds: {len(primary)} games (real book ML only)")

    # Secondary: ESPN's HTML /mlb/odds page. Same rule — only when book
    # publishes a real ML number, never derived.
    legacy = {}
    try:
        r = requests.get("https://www.espn.com/mlb/odds",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code != 200:
            print(f"  WARN: ESPN /mlb/odds returned {r.status_code}")
        else:
            idx = r.text.find('"odds":[{"displayValue":"MLB Odds"')
            if idx >= 0:
                chunk = r.text[idx:idx+150000]
                line_blocks = _re.split(r'"id":"4018\d+","uid"', chunk)
                for block in line_blocks[1:]:
                    home_abbr = away_abbr = None
                    for ha, abbr in _re.findall(r'"homeAway":"(home|away)".*?"abbreviation":"([A-Z]+)"', block, _re.DOTALL):
                        if ha == "home": home_abbr = abbr
                        else: away_abbr = abbr
                    ml_match = _re.search(
                        r'"moneyline":\{"displayName":"Moneyline".*?"home":\{.*?"odds":"([^"]+)".*?"away":\{.*?"odds":"([^"]+)"',
                        block, _re.DOTALL,
                    )
                    if home_abbr and away_abbr and ml_match:
                        try:
                            legacy[(away_abbr, home_abbr)] = {
                                "away_ml": int(ml_match.group(2)),
                                "home_ml": int(ml_match.group(1)),
                                "book": "DraftKings",
                            }
                        except ValueError:
                            pass
    except Exception as e:
        print(f"  WARN: ESPN HTML odds fetch failed: {e}")

    # Merge order matters: lowest-priority source first, highest last
    # (later .update() calls overwrite). Action Network wins because it's
    # the most reliable; ESPN scoreboard / legacy fill any gaps.
    merged = dict(legacy)
    merged.update(primary)
    merged.update(action_odds)
    print(f"  Total real-book odds: {len(merged)} games  "
          f"(action {len(action_odds)} / espn-json {len(primary)} / espn-html {len(legacy)})")
    return merged

print("\nFetching sportsbook odds...")
real_odds = fetch_espn_odds()


# ─── Fetch team standings (current season W-L) ──────────────────────────────
def fetch_team_records():
    """Returns {team_id: "W-L"} for the current MLB season.
    Empty dict on any API failure — caller treats records as optional."""
    try:
        url = f"{MLB_API}/standings?leagueId=103,104&season={NOW.year}&standingsTypes=regularSeason"
        data = fetch(url) or {}
        out = {}
        for div in data.get("records", []):
            for tr in div.get("teamRecords", []):
                tid = (tr.get("team") or {}).get("id")
                w = tr.get("wins")
                l = tr.get("losses")
                if tid is not None and w is not None and l is not None:
                    out[int(tid)] = f"{w}-{l}"
        return out
    except Exception as e:
        print(f"  WARN: standings fetch failed: {e}")
        return {}

print("\nFetching team standings...")
team_records = fetch_team_records()
print(f"  Standings: {len(team_records)} teams")


# ─── Load bullpen table + SP innings table ───────────────────────────────────
# Built daily by scripts/07_fetch_bullpen.py. If files are missing, fall back
# to a pass-through (no bullpen adjustment). Never crash the build for this.
def _load_atlas_safe(filename: str, default):
    path = os.path.join(REPO_ROOT, "atlas", filename)
    try:
        with open(path) as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  WARN: {filename} not loaded ({e}); bullpen adjustment disabled")
        return default

_bullpen_data = _load_atlas_safe("team_bullpen.json", {"teams": {}, "league_avg_rp_runs_per_ip": 0.5, "league_avg_sp_ip_per_start": 5.5})
_sp_innings = _load_atlas_safe("sp_innings.json", {})
_LEAGUE_RP_RUNS_PER_IP = _bullpen_data.get("league_avg_rp_runs_per_ip", 0.5)
_LEAGUE_SP_IP = _bullpen_data.get("league_avg_sp_ip_per_start", 5.5)
_TEAM_BULLPEN = _bullpen_data.get("teams", {})

print(f"  Bullpen: {len(_TEAM_BULLPEN)} teams loaded (league avg {_LEAGUE_RP_RUNS_PER_IP:.3f} R/IP, SP avg {_LEAGUE_SP_IP:.2f} IP/start)")


def bullpen_run_delta(opp_team_id, sp_id):
    """Run-delta to ADD to the batting team's projection.
    Positive = opposing bullpen is below league average → batting team scores more.
    Negative = opposing bullpen is suppressive → batting team scores less.

      bp_ip       = max(0, 9 - sp_avg_ip_per_start)   # exposure to bullpen
      run_delta   = bp_ip * (opp_bp_runs_per_ip - league_avg)
    """
    opp_bp = _TEAM_BULLPEN.get(str(opp_team_id))
    if not opp_bp or opp_bp.get("rp_runs_per_ip") is None:
        return 0.0
    sp_data = _sp_innings.get(str(sp_id), {})
    sp_avg_ip = sp_data.get("avg_ip_per_start") or _LEAGUE_SP_IP
    bp_ip = max(0.0, 9.0 - sp_avg_ip)
    delta = bp_ip * (opp_bp["rp_runs_per_ip"] - _LEAGUE_RP_RUNS_PER_IP)
    return round(delta, 2)

# ─── Fetch schedule ──────────────────────────────────────────────────────────
print(f"\nFetching schedule for {TODAY}...")
sched = fetch(f"{MLB_API}/schedule?sportId=1&date={TODAY}&hydrate=probablePitcher,lineups,linescore,team,venue")
games_raw = sched.get("dates", [{}])[0].get("games", []) if sched else []
print(f"  Games: {len(games_raw)}")


# ─── Position lookup cache ──────────────────────────────────────────────────
# The schedule's `lineups` hydrate returns batters with id+fullName but
# usually NO primaryPosition. To avoid showing "?" for every player, we do
# ONE bulk call to /people?personIds=... covering every batter across every
# lineup, then process_lineup looks up positions from this cache.
_POS_CACHE: dict[int, str] = {}


def _bulk_fetch_positions(pids: list[int]) -> None:
    """Populate _POS_CACHE from a bulk /people request. Idempotent."""
    missing = [p for p in pids if p and p not in _POS_CACHE]
    if not missing:
        return
    # MLB Stats API tolerates ~100+ IDs per call comfortably; chunk to be safe.
    CHUNK = 75
    for i in range(0, len(missing), CHUNK):
        ids_csv = ",".join(str(p) for p in missing[i:i + CHUNK])
        try:
            data = fetch(f"{MLB_API}/people?personIds={ids_csv}")
            for person in (data or {}).get("people", []) or []:
                pid = person.get("id")
                pos = person.get("primaryPosition", {}).get("abbreviation")
                if pid and pos:
                    _POS_CACHE[int(pid)] = pos
        except Exception as e:
            print(f"  WARN: bulk position fetch failed for chunk {i}: {e}")


def lookup_position(pid, fallback_p: dict | None = None) -> str:
    """Return position string, or '' if unknown. Never returns '?'."""
    if not pid:
        return ""
    cached = _POS_CACHE.get(int(pid))
    if cached:
        return cached
    if fallback_p:
        v = fallback_p.get("primaryPosition", {}).get("abbreviation", "")
        if v and v != "?":
            return v
    return ""

# ─── Process each game ───────────────────────────────────────────────────────
games = []
all_batter_matchups = []  # for daily projections tab

for g in games_raw:
    away_team = g["teams"]["away"]["team"]
    home_team = g["teams"]["home"]["team"]
    away_abbr = away_team.get("abbreviation", "???")
    home_abbr = home_team.get("abbreviation", "???")
    venue = g.get("venue", {}).get("name", "")
    game_time_utc = g.get("gameDate", "")

    # Parse game time to ET
    try:
        gt = datetime.fromisoformat(game_time_utc.replace("Z", "+00:00")).astimezone(ET)
        time_str = gt.strftime("%-I:%M %p ET")
    except:
        time_str = "TBD"

    # Probable pitchers
    away_sp_data = g["teams"]["away"].get("probablePitcher", {})
    home_sp_data = g["teams"]["home"].get("probablePitcher", {})
    away_sp_id = away_sp_data.get("id")
    home_sp_id = home_sp_data.get("id")
    away_sp_name = away_sp_data.get("fullName", "TBD")
    home_sp_name = home_sp_data.get("fullName", "TBD")

    # Pitcher info from atlas
    away_ps = pitcher_idx.get(away_sp_id, {})
    home_ps = pitcher_idx.get(home_sp_id, {})
    away_cluster = away_ps.get("cluster", "R_UT")
    home_cluster = home_ps.get("cluster", "R_UT")
    away_arch = away_ps.get("archetype", "Unknown")
    home_arch = home_ps.get("archetype", "Unknown")
    away_hand = "LHP" if away_ps.get("is_rhp", 1) == 0 else "RHP"
    home_hand = "LHP" if home_ps.get("is_rhp", 1) == 0 else "RHP"

    # Tier info
    away_tier = tier_idx.get(away_sp_id, {})
    home_tier = tier_idx.get(home_sp_id, {})
    away_tier_name = away_tier.get("tier", "T3_Standard")
    home_tier_name = home_tier.get("tier", "T3_Standard")
    away_tier_mult = away_tier.get("effective_multiplier", 1.0)
    home_tier_mult = home_tier.get("effective_multiplier", 1.0)

    # Lineups — try MLB API first, then BaseballMonster (has MLB IDs), then RotoWire
    away_lineup_raw = g.get("lineups", {}).get("awayPlayers", [])
    home_lineup_raw = g.get("lineups", {}).get("homePlayers", [])
    has_lineups = len(away_lineup_raw) > 0 and len(home_lineup_raw) > 0
    lineup_source = "MLB API" if has_lineups else ""

    # Helper to find external lineup data with team alias handling
    def find_external(source, a, h):
        for aa in [a, TEAM_ALIAS.get(a, a)]:
            for hh in [h, TEAM_ALIAS.get(h, h)]:
                if (aa, hh) in source:
                    return source[(aa, hh)]
        return {}

    bm = find_external(bm_lineups, away_abbr, home_abbr)
    rw = find_external(rw_lineups, away_abbr, home_abbr)

    # BaseballMonster fallback (preferred — has MLB IDs directly)
    if not has_lineups and bm:
        away_lineup_raw = bm.get("away_lineup", [])
        home_lineup_raw = bm.get("home_lineup", [])
        has_lineups = len(away_lineup_raw) > 0 and len(home_lineup_raw) > 0
        if has_lineups:
            lineup_source = "BaseballMonster"
            bm_used += 1

    # RotoWire fallback
    if not has_lineups and rw:
        away_lineup_raw = rw.get("away_lineup", [])
        home_lineup_raw = rw.get("home_lineup", [])
        has_lineups = len(away_lineup_raw) > 0 and len(home_lineup_raw) > 0
        if has_lineups:
            lineup_source = "RotoWire"
            rw_used += 1

    # Fill in pitcher IDs from external sources if MLB API didn't have them
    ext = bm if bm.get("away_sp_id") else rw
    if not away_sp_id and ext.get("away_sp_id"):
        away_sp_id = ext["away_sp_id"]
        away_sp_name = ext.get("away_sp_name", away_sp_name)
        away_ps = pitcher_idx.get(away_sp_id, {})
        away_cluster = away_ps.get("cluster", "R_UT")
        away_arch = away_ps.get("archetype", "Unknown")
        away_hand = "LHP" if away_ps.get("is_rhp", 1) == 0 else "RHP"
        away_tier = tier_idx.get(away_sp_id, {})
        away_tier_name = away_tier.get("tier", "T3_Standard")
        away_tier_mult = away_tier.get("effective_multiplier", 1.0)
    if not home_sp_id and ext.get("home_sp_id"):
        home_sp_id = ext["home_sp_id"]
        home_sp_name = ext.get("home_sp_name", home_sp_name)
        home_ps = pitcher_idx.get(home_sp_id, {})
        home_cluster = home_ps.get("cluster", "R_UT")
        home_arch = home_ps.get("archetype", "Unknown")
        home_hand = "LHP" if home_ps.get("is_rhp", 1) == 0 else "RHP"
        home_tier = tier_idx.get(home_sp_id, {})
        home_tier_name = home_tier.get("tier", "T3_Standard")
        home_tier_mult = home_tier.get("effective_multiplier", 1.0)

    def process_lineup(lineup_raw, opp_gmm_proba, team_abbr):
        """Process a lineup using GMM-weighted multi-cluster matching.
        opp_gmm_proba: dict of {cluster: probability} from the opposing pitcher's GMM."""
        batters = []
        team_woba_sum = 0
        team_pa = 0
        team_h = 0; team_bb = 0; team_hr = 0; team_tb = 0

        for i, p in enumerate(lineup_raw):
            pid = p.get("id")
            name = p.get("fullName", "Unknown")
            pos = lookup_position(pid, p)  # '' if unknown — caller must handle
            bat_side = p.get("batSide", {}).get("code", "R")

            base_w = get_base_woba(pid)
            base_h, base_bb, base_hr, base_tb = get_base_rates(pid)

            # GMM-weighted lookup across ALL pitcher clusters
            # This thickens the dataset by using 2nd/3rd DNA clusterings
            w_woba = 0; w_h = 0; w_bb = 0; w_hr = 0; w_tb = 0
            total_weight = 0; total_pa = 0

            for cluster, prob in opp_gmm_proba.items():
                hvc = hvc_idx.get((pid, cluster))
                if hvc and hvc["PA"] >= 1:
                    hvc_pa = hvc["PA"]
                    w_woba += prob * hvc["wOBA"] * hvc_pa
                    w_h += prob * hvc["H"]
                    w_bb += prob * hvc["BB"]
                    w_hr += prob * hvc["HR"]
                    s = hvc.get("singles", 0)
                    d = hvc.get("doubles", 0)
                    t = hvc.get("triples", 0)
                    w_tb += prob * (s + d*2 + t*3 + hvc["HR"]*4)
                    total_weight += prob * hvc_pa
                    total_pa += hvc_pa

            if total_weight > 0:
                # GMM-weighted rates
                vs_woba = w_woba / total_weight
                h_rate = w_h / total_weight
                bb_rate = w_bb / total_weight
                hr_rate = w_hr / total_weight
                tb_rate = w_tb / total_weight

                # PA confidence blending: when sample is thin, blend toward
                # the BATTER'S OWN rates (not league avg).
                # At 50+ PA the archetype data dominates; under 15 PA, base dominates.
                PA_FULL_TRUST = 50
                if total_pa < PA_FULL_TRUST:
                    trust = total_pa / PA_FULL_TRUST  # 0.0 to 1.0
                    vs_woba = trust * vs_woba + (1 - trust) * base_w
                    h_rate = trust * h_rate + (1 - trust) * base_h
                    bb_rate = trust * bb_rate + (1 - trust) * base_bb
                    hr_rate = trust * hr_rate + (1 - trust) * base_hr
                    tb_rate = trust * tb_rate + (1 - trust) * base_tb

                vs_woba = max(0.050, min(0.600, vs_woba))
            else:
                # No archetype data at all — use batter's own rates
                vs_woba = base_w
                total_pa = 0
                h_rate = base_h; bb_rate = base_bb
                hr_rate = base_hr; tb_rate = base_tb

            # Per-game PA — empirical MLB league averages by lineup slot.
            # Leadoff gets ~4.62 PA, 9-hole ~3.80 PA; the structure of the
            # game (38ish team-PA spread across 9 slots) makes this stable
            # year over year. Index `i` is 0-based batting order position.
            LINEUP_PA = [4.62, 4.51, 4.40, 4.30, 4.20, 4.10, 4.00, 3.90, 3.80]
            pa = LINEUP_PA[i] if i < len(LINEUP_PA) else 3.80

            ms = woba_to_ms(vs_woba)
            ms_lo = max(40, ms - 4)
            ms_hi = min(99, ms + 4)

            proj_h = h_rate * pa
            proj_bb = bb_rate * pa
            proj_hr = hr_rate * pa
            proj_tb = tb_rate * pa

            team_pa += pa
            team_h += proj_h
            team_bb += proj_bb
            team_hr += proj_hr
            team_tb += proj_tb
            team_woba_sum += vs_woba

            batters.append({
                "order": i + 1,
                "name": name,
                "id": pid,
                "pos": pos,
                "bat_side": bat_side,
                "ms": ms,
                "ms_lo": ms_lo,
                "ms_hi": ms_hi,
                "base_woba": round(base_w, 3),
                "vs_woba": round(vs_woba, 3),
                "total_pa": round(total_pa),
                "hr_rate": round(hr_rate, 4),
            })
            all_batter_matchups.append({
                "id": pid,
                "name": name,
                "team": team_abbr,
                "ms": ms,
                "base_woba": round(base_w, 3),
                "vs_woba": round(vs_woba, 3),
                "hr_rate": round(hr_rate, 4),
                "opp_pitcher": "",  # filled later
                "opp_team": "",
            })

        team_avg_woba = team_woba_sum / max(len(lineup_raw), 1)
        runs = base_runs(team_pa, team_h, team_bb, team_hr, team_tb)
        return batters, round(runs, 1), round(team_avg_woba, 3), team_pa

    # Get GMM probabilities for opposing pitchers (multi-cluster DNA)
    home_gmm = home_ps.get("gmm_proba", {home_cluster: 1.0})
    away_gmm = away_ps.get("gmm_proba", {away_cluster: 1.0})

    if has_lineups:
        # Pre-fetch positions in one bulk call so render shows "C · R" not "? · R"
        _bulk_fetch_positions(
            [p.get("id") for p in away_lineup_raw if p.get("id")] +
            [p.get("id") for p in home_lineup_raw if p.get("id")]
        )
        away_batters, away_runs_raw, away_woba, away_pa = process_lineup(
            away_lineup_raw, home_gmm, away_abbr)
        home_batters, home_runs_raw, home_woba, home_pa = process_lineup(
            home_lineup_raw, away_gmm, home_abbr)

        # Apply tier multipliers (opposing SP's tier scales the batting team's runs)
        away_runs_tiered = away_runs_raw * home_tier_mult
        home_runs_tiered = home_runs_raw * away_tier_mult

        # Apply bullpen run-delta. The opposing team's bullpen (and their SP's
        # avg innings) determine how much late-inning exposure the batting
        # team gets. Positive delta = opposing bullpen below league average →
        # batting team scores MORE late.
        away_id = TEAMS.get(away_abbr, {}).get("id", 0)
        home_id = TEAMS.get(home_abbr, {}).get("id", 0)
        away_bp_delta = bullpen_run_delta(opp_team_id=home_id, sp_id=home_sp_id)
        home_bp_delta = bullpen_run_delta(opp_team_id=away_id, sp_id=away_sp_id)

        # Apply park factor (home team's park affects BOTH sides)
        pf = PARK_FACTOR.get(home_abbr, 1.00)
        away_runs = round((away_runs_tiered + away_bp_delta) * pf, 1)
        home_runs = round((home_runs_tiered + home_bp_delta) * pf, 1)

        # Fill opp info for daily tab
        for bm in all_batter_matchups[-len(away_lineup_raw)-len(home_lineup_raw):-len(home_lineup_raw)]:
            bm["opp_pitcher"] = home_sp_name
            bm["opp_team"] = home_abbr
        for bm in all_batter_matchups[-len(home_lineup_raw):]:
            bm["opp_pitcher"] = away_sp_name
            bm["opp_team"] = away_abbr
    else:
        away_batters = []
        home_batters = []
        away_runs = 0
        home_runs = 0
        away_woba = 0
        home_woba = 0

    # ─── Pure run-differential model ──────────────────────────────────────
    # Confidence is derived SOLELY from projected run differential.
    # No WP gap, no Pythagorean smoothing, no market edge. The only signal
    # the user sees is: how many runs does the model think each side scores,
    # and how big is the gap.
    #
    # Calibration note: prior system stamped C:10 on anything with raw WP gap
    # ≥15, which let 91 picks cluster at C:10 with a 44% actual win rate
    # (model claimed 70%). Run-diff buckets below are deliberately stingy —
    # the model must project a meaningful on-field margin to earn C:7+.
    run_diff = abs(away_runs - home_runs)
    if run_diff >= 2.5:   conf = 10
    elif run_diff >= 1.8: conf = 9
    elif run_diff >= 1.4: conf = 8
    elif run_diff >= 1.1: conf = 7
    elif run_diff >= 0.8: conf = 6
    elif run_diff >= 0.5: conf = 5
    elif run_diff >= 0.3: conf = 4
    elif run_diff >= 0.15: conf = 3
    elif run_diff >= 0.05: conf = 2
    elif run_diff > 0:     conf = 1
    else:                  conf = 0

    # MUST-PICK rule: any matchup with run_diff >= 1.8 AND both pitchers having
    # full stats (in atlas index, non-default archetype) qualifies regardless
    # of the C:10 confidence floor. Captures real edges the binary cutoff misses.
    away_has_full = bool(away_ps) and away_ps.get("archetype", "Unknown") != "Unknown"
    home_has_full = bool(home_ps) and home_ps.get("archetype", "Unknown") != "Unknown"
    must_pick = run_diff >= 1.8 and away_has_full and home_has_full

    # FULL COVERAGE rule: do NOT rate games where any batter in either lineup
    # lacks atlas data (pa_w == 0). Rookies, NPB imports, fresh call-ups all
    # fail this check. Such games are still rendered but excluded from picks
    # so the SIM never bets on a lineup it can't actually project.
    missing_coverage = []
    for p in list(away_lineup_raw) + list(home_lineup_raw):
        pid = p.get("id") if isinstance(p, dict) else None
        if pid is None:
            continue
        acc = batter_rates_accum.get(pid)
        if not acc or acc.get("pa_w", 0) <= 0:
            missing_coverage.append(p.get("fullName", f"id:{pid}") if isinstance(p, dict) else str(pid))
    has_full_coverage = len(missing_coverage) == 0 and away_has_full and home_has_full
    if missing_coverage:
        print(f"  [COVERAGE] {away_abbr} @ {home_abbr}: missing {len(missing_coverage)} batter(s): {', '.join(missing_coverage[:3])}{'...' if len(missing_coverage) > 3 else ''}")

    # Display WP (derived from run diff via Pythagorean, then home-field
    # adjusted). Shown for readability only — it does NOT drive picks.
    away_wp_raw = pythagorean_wp(away_runs, home_runs)
    home_wp_raw = 100 - away_wp_raw
    HFA_BUMP = 1.5
    if has_lineups:
        home_wp = min(95, round(home_wp_raw + HFA_BUMP, 1))
        away_wp = round(100 - home_wp, 1)
    else:
        away_wp = away_wp_raw
        home_wp = home_wp_raw

    # Legacy "value" field retained as alias of conf for back-compat with the
    # HTML template's data-value attribute. Single signal now.
    value = conf
    edge = round(run_diff, 1)
    if not has_lineups:
        conf = 0
        value = 0
        edge = 0

    # Real sportsbook odds — STRICT. We ONLY display prices the book actually
    # published. If the odds source doesn't have this game, we leave the line
    # blank ("—") and exclude the pick from picks/mlb.json. Tracking a pick
    # against a fabricated price is dishonest and breaks settlement math.
    game_odds = real_odds.get((away_abbr, home_abbr), {})
    if game_odds and game_odds.get("away_ml") and game_odds.get("home_ml"):
        away_ml = f"{game_odds['away_ml']:+d}"
        home_ml = f"{game_odds['home_ml']:+d}"
        odds_source = game_odds.get("book", "")
    else:
        away_ml = ""
        home_ml = ""
        odds_source = "NO_LINE"

    # Pick — team with higher projected runs. Pure run differential.
    if away_runs > home_runs:
        pick_team = away_abbr
    elif home_runs > away_runs:
        pick_team = home_abbr
    else:
        pick_team = home_abbr  # tiebreak to home on exact tie (HFA)

    # Odds filter — kill heavy favorites that bleed ROI
    # Check final ML (real or model-implied) for the picked side
    pick_ml_str = home_ml if pick_team == home_abbr else away_ml
    try:
        pick_odds_raw = int(pick_ml_str)
    except (ValueError, TypeError):
        pick_odds_raw = 0
    max_fav = MAX_FAV_BY_CONF.get(conf, -150)
    odds_too_heavy = pick_odds_raw < max_fav and pick_odds_raw != 0

    park_factor = PARK_FACTOR.get(home_abbr, 1.00)
    games.append({
        "away_abbr": away_abbr, "home_abbr": home_abbr,
        "away_id": TEAMS.get(away_abbr, {}).get("id", 0),
        "home_id": TEAMS.get(home_abbr, {}).get("id", 0),
        "away_color": TEAMS.get(away_abbr, {}).get("color", "#999"),
        "home_color": TEAMS.get(home_abbr, {}).get("color", "#999"),
        "away_sp": away_sp_name, "home_sp": home_sp_name,
        "away_arch": away_arch, "home_arch": home_arch,
        "away_hand": away_hand, "home_hand": home_hand,
        "away_tier": away_tier_name, "home_tier": home_tier_name,
        "away_tier_mult": away_tier_mult, "home_tier_mult": home_tier_mult,
        "away_runs": away_runs, "home_runs": home_runs,
        "away_wp": away_wp, "home_wp": home_wp,
        "away_ml": away_ml, "home_ml": home_ml, "odds_source": odds_source,
        "away_woba": away_woba, "home_woba": home_woba,
        "away_batters": away_batters, "home_batters": home_batters,
        "has_lineups": has_lineups,
        "park_factor": park_factor,
        "conf": conf, "value": value,
        "edge": round(edge, 1),
        "pick_team": pick_team,
        "odds_too_heavy": odds_too_heavy,
        "must_pick": must_pick,
        "has_full_coverage": has_full_coverage,
        "missing_coverage_count": len(missing_coverage),
        "pick_odds": pick_odds_raw,
        "venue": venue, "time_str": time_str,
        "total": round(away_runs + home_runs, 1),
    })

print(f"  Processed {len(games)} games")
print(f"  With lineups: {sum(1 for g in games if g['has_lineups'])}")
if bm_used > 0:
    print(f"  BaseballMonster fill-ins: {bm_used}")
if rw_used > 0:
    print(f"  RotoWire fill-ins: {rw_used}")

# ─── HTML Generation ──────────────────────────────────────────────────────────
print("\nGenerating HTML...")

def h(s):
    """HTML escape."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def render_batter(b):
    mc = ms_class(b["ms"])
    wc = woba_class(b["base_woba"], b["vs_woba"])
    pa_str = f'{b["total_pa"]}PA' if b["total_pa"] > 0 else "NEW"
    return f'''<div class="batter-row">
  <div class="batter-top">
    <span class="batter-order">{b["order"]}</span>
    <span class="batter-name">{h(b["name"])}</span>
    <span class="batter-ms {mc}">{b["ms"]}</span>
  </div>
  <div class="batter-bottom">
    <span class="batter-stats">{(h(b["pos"]) + " &middot; ") if b.get("pos") else ""}{b["bat_side"]}</span>
    <span class="batter-range">{b["ms_lo"]}-{b["ms_hi"]}</span>
  </div>
  <div class="batter-woba">
    <span class="woba-base">.{str(b["base_woba"])[2:]}</span>
    <span class="woba-dna">\U0001f9ec</span>
    <span class="woba-vs {wc}">.{str(b["vs_woba"])[2:]}</span>
    <span class="woba-pa">{pa_str}</span>
  </div>
</div>'''

def render_game(g, idx):
    aa = g["away_abbr"]; ha = g["home_abbr"]
    ac = g["away_color"]; hc = g["home_color"]
    ar = g["away_runs"]; hr_ = g["home_runs"]
    total = ar + hr_

    # Run bar widths
    if total > 0:
        aw = max(20, round(ar / total * 100))
        hw = 100 - aw
    else:
        aw = 50; hw = 50

    # Pick display — confidence-only, no edge/value clutter
    pick_html = ""
    if g["has_lineups"] and not g["odds_too_heavy"] and g.get("has_full_coverage") and g.get("odds_source") != "NO_LINE" and (g["conf"] >= MIN_CONF_PICK or g.get("must_pick")):
        cc = conf_color(g["conf"])
        pick_html = f'''<div class="sim-pick"><span class="pick-type-label">ML</span> {h(g["pick_team"])} ML <span class="mc-conf-num" style="color:{cc}" title="Confidence">C:{g["conf"]}</span></div>'''
    elif g["has_lineups"] and g["conf"] >= MIN_CONF_PICK and g.get("odds_source") == "NO_LINE":
        pick_html = '<div class="sim-pick" style="background:#FFA500;color:#000;border-color:#000">NO LINE — book has not posted ML</div>'
    elif g["has_lineups"] and g["conf"] >= MIN_CONF_PICK and g["odds_too_heavy"]:
        pick_html = f'<div class="sim-pick" style="background:#FF3333;color:#fff;border-color:#000">BAD PRICE ({g["pick_odds"]:+d})</div>'
    elif g["has_lineups"] and g["conf"] > 0:
        pick_html = '<div class="sim-pick" style="background:#333;color:#888;border-color:#555">NO PLAY</div>'

    # (Edge bar removed — picks are driven by model WP confidence only.)
    edge_html = ""

    # wOBA comparison
    woba_diff = g["away_woba"] - g["home_woba"]
    if abs(woba_diff) < 0.005:
        woba_edge = "EVEN"
    elif woba_diff > 0:
        woba_edge = f"{aa} +.{str(abs(round(woba_diff,3)))[2:]}"
    else:
        woba_edge = f"{ha} +.{str(abs(round(woba_diff,3)))[2:]}"

    # wOBA bar widths
    woba_total = g["away_woba"] + g["home_woba"]
    if woba_total > 0:
        woba_aw = round(g["away_woba"] / woba_total * 100)
        woba_hw = 100 - woba_aw
    else:
        woba_aw = 50; woba_hw = 50

    # Model formula
    formula = f'{aa} {ar} \u2014 {ha} {hr_}'

    # Lineup section
    if g["has_lineups"]:
        away_lu = "".join(render_batter(b) for b in g["away_batters"])
        home_lu = "".join(render_batter(b) for b in g["home_batters"])
        lineup_html = f'''<div class="lineup-toggle" onclick="toggleLineup({idx})">
  <span>LINEUP MATCHUPS</span>
  <span class="arrow" id="arrow-{idx}">\u25bc</span>
</div>
<div class="lineup-grid" id="lineup-{idx}">
  <div class="lineup-col">
    <div class="lineup-col-hdr">{aa} LINEUP</div>
    {away_lu}
  </div>
  <div class="lineup-col">
    <div class="lineup-col-hdr">{ha} LINEUP</div>
    {home_lu}
  </div>
</div>'''
    else:
        lineup_html = '<div class="tbd-block">LINEUPS TBD \u2014 WILL UPDATE WHEN RELEASED</div>'

    ou_line = f"O/U {g['total']}" if g["has_lineups"] else ""
    away_ml_display = g["away_ml"] if g["away_ml"] else "\u2014"
    home_ml_display = g["home_ml"] if g["home_ml"] else "\u2014"
    away_record = team_records.get(g["away_id"], "")
    home_record = team_records.get(g["home_id"], "")
    away_record_html = f'<div class="team-record">{away_record}</div>' if away_record else ""
    home_record_html = f'<div class="team-record">{home_record}</div>' if home_record else ""

    return f'''<div class="game-card" data-conf="{g["conf"]}" data-value="{g["value"]}" data-edge="{g["edge"]}">
  <div class="run-bar ma-premium">
  <div class="run-bar-seg" style="width:{aw}%;background:{ac}">{ar}</div>
  <div class="run-bar-seg" style="width:{hw}%;background:{hc}">{hr_}</div>
</div>
  <div class="card-header">
  <div class="team-block">
    <div class="team-logo"><img src="https://www.mlbstatic.com/team-logos/{g["away_id"]}.svg" alt="{aa}" style="width:100%;height:100%;object-fit:contain"></div>
    <div class="team-abbr">{aa}</div>
    {away_record_html}
    <div class="team-ml">{away_ml_display}</div>
  </div>
  <div class="card-center ma-premium">
    <div class="proj-label">WIN PROB</div>
    <div class="spread">{g["away_wp"]}% \u2014 {g["home_wp"]}%</div>
    <div class="ou-line">{ou_line}</div>
    {pick_html}
  </div>
  <div class="team-block">
    <div class="team-logo"><img src="https://www.mlbstatic.com/team-logos/{g["home_id"]}.svg" alt="{ha}" style="width:100%;height:100%;object-fit:contain"></div>
    <div class="team-abbr">{ha}</div>
    {home_record_html}
    <div class="team-ml">{home_ml_display}</div>
  </div>
</div>
  {edge_html}
  <div class="sp-block">
  <div class="sp-side">
      <div class="sp-name">{h(g["away_sp"])}</div>
      <span class="arch-badge">{h(g["away_arch"])}</span>
      <div class="sp-stats">{g["away_hand"]}</div>
    </div>
  <div class="sp-vs">VS</div>
  <div class="sp-side">
      <div class="sp-name">{h(g["home_sp"])}</div>
      <span class="arch-badge">{h(g["home_arch"])}</span>
      <div class="sp-stats">{g["home_hand"]}</div>
    </div>
</div>
  <div class="model-breakdown">
    <div class="model-row">
      <span class="model-label">wOBA</span>
      <span class="model-val">{aa} .{str(g["away_woba"])[2:] if g["away_woba"] else "000"}</span>
      <div class="model-bar-mini">
        <div class="model-bar-away" style="width:{woba_aw}%;background:{ac}"></div>
        <div class="model-bar-home" style="width:{woba_hw}%;background:{hc}"></div>
      </div>
      <span class="model-val">{ha} .{str(g["home_woba"])[2:] if g["home_woba"] else "000"}</span>
      <span class="model-edge-sm">{woba_edge}</span>
    </div>
    <div class="model-row">
      <span class="model-label">TIER</span>
      <span class="model-val">{g["away_tier"]} ({g["away_tier_mult"]:.2f}\u00d7)</span>
      <div class="model-mid-spacer"></div>
      <span class="model-val">{g["home_tier"]} ({g["home_tier_mult"]:.2f}\u00d7)</span>
      <span class="model-edge-sm"></span>
    </div>
    <div class="model-row model-formula-row ma-premium">
      <span class="model-label">MODEL</span>
      <span class="model-formula">BaseRuns\u00d7Tier\u00d7Park({g["park_factor"]:.2f}) \u2192 <strong>{formula}</strong> | Pyth WP</span>
    </div>
    <div class="model-row model-tags">
      <span class="model-tag tag-arch">vs {g["away_tier"]}</span><span class="model-tag tag-arch">vs {g["home_tier"]}</span>
    </div>
  </div>
  <div class="game-meta">{h(g["time_str"])} \u00b7 {h(g["venue"])}</div>
  <div class="affiliate-row">
  <a href="https://kalshi.com/sign-up/?referral=88acd325-1cbe-44b0-9358-f0cf92cf9fc7" target="_blank" rel="noopener" class="aff-btn aff-kalshi">
    <span class="aff-name">KALSHI</span><span class="aff-cta">TRADE NOW</span>
  </a>
  <a href="https://bethog.com/r/alphamale" target="_blank" rel="noopener" class="aff-btn aff-bethog">
    <span class="aff-name">BETHOG</span><span class="aff-cta">BET NOW</span>
  </a>
</div>
  {lineup_html}
</div>'''

# ─── Fetch hitting streaks for all batters in today's lineups ─────────────────
print("\nFetching hitting streaks...")
batter_streaks = {}  # pid -> {"streak": int, "last7_avg": float, "last7_ops": float}
all_lineup_pids = set()
for g in games:
    if g["has_lineups"]:
        for b in g["away_batters"] + g["home_batters"]:
            all_lineup_pids.add(b["id"])

for pid in all_lineup_pids:
    try:
        data = fetch(f"{MLB_API}/people/{pid}/stats?stats=gameLog&season={NOW.year}&group=hitting")
        if not data:
            continue
        stats_list = data.get("stats") or []
        if not stats_list:
            continue
        splits = stats_list[0].get("splits", [])
        if not splits:
            continue
        # Current consecutive hitting streak (walk backwards)
        streak = 0
        for s in reversed(splits):
            hits = s.get("stat", {}).get("hits", 0)
            if hits > 0:
                streak += 1
            else:
                break
        # Last 7 games rolling avg/OPS
        recent = splits[-7:] if len(splits) >= 7 else splits
        total_h = sum(s.get("stat", {}).get("hits", 0) for s in recent)
        total_ab = sum(s.get("stat", {}).get("atBats", 0) for s in recent)
        last7_avg = total_h / max(total_ab, 1)
        batter_streaks[pid] = {"streak": streak, "last7_avg": round(last7_avg, 3)}
    except Exception:
        continue

print(f"  Fetched streaks for {len(batter_streaks)} batters")
print(f"  Batters on 3+ game streaks: {sum(1 for v in batter_streaks.values() if v['streak'] >= 3)}")

# ─── Render HR Watch tab ─────────────────────────────────────────────────────
def render_hr_watch_tab():
    # Sort all batters by HR rate (highest probability of going yard)
    hr_candidates = sorted(
        [bm for bm in all_batter_matchups if bm.get("hr_rate", 0) > 0],
        key=lambda x: -x.get("hr_rate", 0)
    )[:25]

    hr_html = ""
    for i, bm in enumerate(hr_candidates):
        hr_pct = round(bm["hr_rate"] * 100, 1)
        mc = ms_class(bm["ms"])
        # Heat level based on HR rate
        if bm["hr_rate"] >= 0.06:
            heat = "hr-fire"
            heat_icon = "\U0001f525"
        elif bm["hr_rate"] >= 0.04:
            heat = "hr-hot"
            heat_icon = "\U0001f7e2"
        elif bm["hr_rate"] >= 0.025:
            heat = "hr-warm"
            heat_icon = "\U0001f7e1"
        else:
            heat = "hr-mild"
            heat_icon = "\u26aa"

        hr_html += f'''<div class="hr-row {heat}">
  <div class="hr-rank">{i+1}</div>
  <div class="hr-info">
    <div class="hr-name">{heat_icon} {h(bm["name"])}</div>
    <div class="hr-meta">{h(bm["team"])} vs {h(bm["opp_pitcher"])} ({h(bm["opp_team"])}) \u00b7 MS {bm["ms"]}</div>
  </div>
  <div class="hr-rate-col">
    <div class="hr-rate">{hr_pct}%</div>
    <div class="hr-rate-label">HR Rate</div>
  </div>
</div>'''

    # Heating Up: batters on real hitting streaks + favorable archetype matchup
    # Per SABR research: consecutive game hitting streaks are non-random signal
    # Compound signal = streak length * archetype wOBA advantage
    heating_candidates = []
    for bm in all_batter_matchups:
        pid = bm.get("id")
        streak_data = batter_streaks.get(pid, {})
        streak = streak_data.get("streak", 0)
        last7 = streak_data.get("last7_avg", 0)
        woba_bump = bm["vs_woba"] - bm["base_woba"]
        # Must be on at least a 2-game streak
        if streak >= 2:
            # Score: streak length weighted by archetype advantage
            # A 5-game streak + .050 wOBA bump >> a 2-game streak + .100 bump
            heat_score = streak * (1 + max(0, woba_bump) * 5)
            heating_candidates.append({
                **bm, "streak": streak, "last7_avg": last7,
                "woba_bump": woba_bump, "heat_score": heat_score
            })

    heating = sorted(heating_candidates, key=lambda x: -x["heat_score"])[:15]

    heat_html = ""
    for i, bm in enumerate(heating):
        mc = ms_class(bm["ms"])
        streak_str = f'{bm["streak"]}G streak'
        avg_str = f'.{str(bm["last7_avg"])[2:]}' if bm["last7_avg"] > 0 else ""
        bump = bm["woba_bump"]
        bump_str = f'+.{str(abs(round(bump,3)))[2:]}' if bump > 0 else ""
        # Streak fire icons
        if bm["streak"] >= 7:
            icon = "\U0001f525\U0001f525"
        elif bm["streak"] >= 4:
            icon = "\U0001f525"
        else:
            icon = "\U0001f7e2"
        heat_html += f'''<div class="trend-row">
  <div class="trend-rank">{i+1}</div>
  <div class="trend-info">
    <div class="trend-name">{icon} {h(bm["name"])}</div>
    <div class="trend-meta">{streak_str} &middot; L7 {avg_str} &middot; {h(bm["team"])} vs {h(bm["opp_pitcher"])} ({h(bm["opp_team"])}){"" if not bump_str else " &middot; wOBA " + bump_str}</div>
  </div>
  <div class="trend-right">
    <div class="trend-ms {mc}">{bm["ms"]}</div>
  </div>
</div>'''

    # Today's Picks column — ranked by confidence, heavy faves excluded
    edges = sorted(
        [g for g in games if g["has_lineups"] and not g["odds_too_heavy"] and g.get("has_full_coverage") and g.get("odds_source") != "NO_LINE" and (g["conf"] >= MIN_CONF_PICK or g.get("must_pick"))],
        key=lambda x: -x["conf"]
    )
    edges_html = ""
    for i, g in enumerate(edges[:12]):
        cc = conf_color(g["conf"])
        prem = ' ma-premium' if g["conf"] >= 8 else ''
        edges_html += f'''<div class="pick-row{prem}">
  <div class="pick-rank">{i+1}</div>
  <div class="pick-info">
    <div class="pick-label gp-pick-strong">{h(g["pick_team"])} ML <span class="mc-conf-num" style="color:{cc}">C:{g["conf"]}</span></div>
    <div class="pick-matchup">{g["away_abbr"]} @ {g["home_abbr"]}</div>
  </div>
</div>'''

    games_with_lu = sum(1 for g in games if g["has_lineups"])
    no_data = '<div class="empty-state">UPDATES WHEN LINEUPS ARE RELEASED</div>' if not hr_html else ''

    return f'''<div class="tab-content" id="tab-daily">
        <div style="padding-top:12px">
            <div class="section-title">DAILY DASHBOARD</div>
            <div class="section-sub">{DATE_SHORT} \u00b7 {games_with_lu} games with lineups</div>
        </div>
        {no_data}
        <div class="daily-grid">
            <div class="daily-col">
                <div class="section-title">\U0001f4a3 HR WATCH</div>
                <div class="section-sub">Most likely to go yard</div>
                <div class="picks-container">{hr_html}</div>
            </div>
            <div class="daily-col">
                <div class="section-title">\U0001f525 HEATING UP</div>
                <div class="section-sub">Active hitting streaks + archetype edge</div>
                <div class="picks-container">{heat_html}</div>
            </div>
            <div class="daily-col">
                <div class="section-title">\U0001f3af TODAY'S PICKS</div>
                <div class="section-sub">Best projected spreads</div>
                <div class="picks-container ma-premium">{edges_html}</div>
            </div>
        </div>
    </div>'''


# ─── Assemble full page ──────────────────────────────────────────────────────
game_cards = "".join(render_game(g, i) for i, g in enumerate(games))
gen_time = NOW.strftime("%Y-%m-%d %H:%M ET")

CSS = open(os.path.join(REPO_ROOT, "mlbsim", "index.html")).read()
# Extract just the CSS block (everything between <style> and </style>)
css_start = CSS.find("<style>")
css_end = CSS.find("</style>") + len("</style>")
css_block = CSS[css_start:css_end] if css_start >= 0 else ""

# Inject Daily tab CSS if missing
DAILY_CSS = """
/* ── Daily Dashboard ── */
.daily-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;padding:8px 0}
@media(max-width:900px){.daily-grid{grid-template-columns:1fr}}
.daily-col .section-title{font-family:'Anton',sans-serif;font-size:18px;letter-spacing:1px;margin-bottom:2px}
.daily-col .section-sub{font-size:11px;color:#888;margin-bottom:10px}
.hr-row{display:flex;align-items:center;gap:10px;padding:8px 10px;border-bottom:1px solid var(--color-border,#222);transition:background .15s}
.hr-row:hover{background:rgba(255,255,255,.03)}
.hr-fire{border-left:3px solid #ff4444}
.hr-hot{border-left:3px solid #00cc44}
.hr-warm{border-left:3px solid #ffcc00}
.hr-mild{border-left:3px solid #555}
.hr-rank{font-family:'JetBrains Mono',monospace;font-size:12px;color:#666;min-width:18px;text-align:center}
.hr-info{flex:1;min-width:0}
.hr-name{font-weight:600;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hr-meta{font-size:11px;color:#999;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hr-rate-col{text-align:right;min-width:55px}
.hr-rate{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:16px;color:#ff6644}
.hr-rate-label{font-size:9px;color:#666;text-transform:uppercase;letter-spacing:.5px}
.trend-row{display:flex;align-items:center;gap:10px;padding:8px 10px;border-bottom:1px solid var(--color-border,#222)}
.trend-row:hover{background:rgba(255,255,255,.03)}
.trend-rank{font-family:'JetBrains Mono',monospace;font-size:12px;color:#666;min-width:18px;text-align:center}
.trend-info{flex:1;min-width:0}
.trend-name{font-weight:600;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.trend-meta{font-size:11px;color:#999;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.trend-right{text-align:right}
.trend-ms{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:16px;padding:2px 6px;border-radius:4px}
.pick-row{display:flex;align-items:center;gap:10px;padding:8px 10px;border-bottom:1px solid var(--color-border,#222)}
.pick-row:hover{background:rgba(255,255,255,.03)}
.pick-rank{font-family:'JetBrains Mono',monospace;font-size:12px;color:#666;min-width:18px;text-align:center}
.pick-info{flex:1;min-width:0}
.pick-label{font-weight:700;font-size:14px}
.pick-matchup{font-size:11px;color:#999}
.pick-edge{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:16px;color:#00cc44;min-width:40px;text-align:right}
.mc-conf-num{font-size:12px;margin-left:4px}
.empty-state{text-align:center;padding:40px 20px;color:#666;font-size:13px}
.picks-container{max-height:500px;overflow-y:auto}

/* ── Team season record (sits between team abbr + moneyline) ── */
.team-record{font-family:'JetBrains Mono',monospace;font-size:10px;color:#888;letter-spacing:0.5px;margin-top:2px;text-align:center}
"""
if "daily-grid" not in css_block:
    css_block = css_block.replace("</style>", DAILY_CSS + "\n</style>")

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>MLB SIM \u2014 {DATE_DISPLAY}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
{css_block}
<link rel="stylesheet" href="https://morellosims.com/morello-auth.css">
    <link rel="stylesheet" href="../morello-auth.css">
</head>
<body data-ma-theme="mlb">

<!-- Header -->
<header class="header">
    <div class="brand-row">
        <div style="display:flex;align-items:baseline;gap:10px">
            <div class="logo">MLB SIM</div>
            <span class="byline">by Jack Morello</span>
        </div>
        <div class="status-indicators" style="display:flex;align-items:center;gap:6px">
            <div class="status-dot"></div>
        </div>
    </div>
</header>

<!-- ─── SEASON RECORD BOX ────────────────────────────────────── -->
<div style="max-width:560px;margin:14px auto 18px;padding:0 12px;">
  <div style="background:#0a0a0a;border:2px solid #FFEA00;border-radius:6px;padding:16px 22px;box-shadow:5px 5px 0 #FFEA00;">
    <div style="display:flex;justify-content:space-between;align-items:center;font-family:'JetBrains Mono',monospace;gap:18px;">
      <div style="text-align:left;flex:1;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">SEASON</div>
        <div style="font-size:30px;color:#00FF55;font-weight:700;line-height:1;margin-top:4px;font-family:'Anton',sans-serif;letter-spacing:1px;">{SEASON_RECORD}</div>
      </div>
      <div style="text-align:center;border-left:1px solid #2a2a2a;border-right:1px solid #2a2a2a;padding:2px 22px;flex:1;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">ROI</div>
        <div style="font-size:30px;color:#FFEA00;font-weight:700;line-height:1;margin-top:4px;font-family:'Anton',sans-serif;letter-spacing:1px;">{SEASON_ROI_VALUE}</div>
      </div>
      <div style="text-align:right;flex:1;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">FILTER</div>
        <div style="font-size:11px;color:#fff;font-weight:700;line-height:1.3;margin-top:6px;letter-spacing:0.5px;">C:8+<br><span style="color:#888;">|ODDS|&lt;340</span></div>
      </div>
    </div>
  </div>
</div>

<!-- FILTER BAR (DESKTOP) -->
<div class="filter-bar">
    <div class="filter-bar-inner">
        <button class="filter-btn active" data-tab="lines">Lines</button>
        <button class="filter-btn" data-tab="daily">Daily</button>
        <button class="filter-btn" data-tab="info">Info</button>
    </div>
</div>

<!-- Main -->
<div class="container">

    <!-- LINES TAB -->
    <div class="tab-content active" id="tab-lines">
        <div class="chips">
            <div class="chip active" onclick="sortGames('time', this)">Time</div>
            <div class="chip" onclick="sortGames('run_diff', this)">Run Diff</div>
        </div>
        <div class="slate-info">
            <span>{DATE_SHORT} SLATE</span>
            <span>{len(games)} GAMES</span>
        </div>
        {game_cards}
        <div class="gen-badge">Generated {gen_time} \u00b7 Powered by ATLAS Pitcher DNA</div>
    </div>

    <!-- HR WATCH TAB -->
    {render_hr_watch_tab()}

    <!-- INFO TAB -->
    <div class="tab-content" id="tab-info">
        <div style="padding-top:12px">
            <div class="info-card">
                <h2>HOW MLB SIM WORKS</h2>
                <p>MLB SIM uses the <strong>Pitcher DNA</strong> system (Gaussian Mixture Model clustering) to classify every pitcher into one of 26 archetypes (15 RHP + 11 LHP) based on their pitch mix, velocity, movement, and approach. Every batter has historical performance data against each archetype \u2014 because baseball is fundamentally a 1v1 sport, the specific pitcher a batter faces defines their expected performance.</p>
                <p>When lineups are released, MLB SIM projects every batter's performance based on how they've historically hit against the opposing pitcher's archetype. This produces per-game <strong>Matchup Scores</strong> that change daily depending on the starter.</p>
            </div>
            <div class="info-card">
                <h2>MATCHUP SCORE (MS) \u2014 40 TO 99</h2>
                <p>MS is a context-dependent metric that changes each game based on the specific pitcher archetype a batter faces.</p>
                <table class="tier-table">
                    <tr><td class="tier-label" style="color:var(--color-elite)">85-99</td><td>Elite Matchup \u2014 historically dominant vs this archetype</td></tr>
                    <tr><td class="tier-label" style="color:var(--color-favorable)">70-84</td><td>Favorable \u2014 above-average performance expected</td></tr>
                    <tr><td class="tier-label" style="color:var(--color-neutral)">55-69</td><td>Neutral \u2014 roughly league-average</td></tr>
                    <tr><td class="tier-label" style="color:var(--color-tough)">40-54</td><td>Tough Matchup \u2014 historically struggles vs this archetype</td></tr>
                </table>
                <div class="formula-block ma-premium">MS FORMULA (wOBA-based):
wOBA >= .400  \u2192  MS 90-99
wOBA .370-.399 \u2192  MS 80-89
wOBA .340-.369 \u2192  MS 70-79
wOBA .310-.339 \u2192  MS 60-69
wOBA .270-.309 \u2192  MS 50-59
wOBA < .270    \u2192  MS 40-49

H2H BONUS: +0-5 pts when PA >= 10
vs specific pitcher (not just archetype)</div>
            </div>
            <div class="info-card">
                <h2>PROJECTION METHODOLOGY</h2>
                <p>Team runs are projected using the <strong>BaseRuns</strong> formula, a context-neutral run estimator:</p>
                <div class="formula-block ma-premium">A = H + BB - HR
B = 1.02 \u00d7 (1.4\u00d7TB - 0.6\u00d7H + 0.1\u00d7BB)
C = PA - H - BB
D = HR
Runs = A\u00d7B / (B+C) + D

Spread = Home Runs \u2212 Away Runs
O/U Total = Home Runs + Away Runs</div>
                <p>Batter projections use archetype-specific wOBA with head-to-head adjustments when sufficient plate appearance history exists.</p>
            </div>
            <div class="info-card">
                <h2>BULLPEN PREDICTIONS</h2>
                <p>MLB SIM predicts bullpen deployment using three layers:</p>
                <p><strong>Layer 1 \u2014 Availability:</strong> Tracks reliever workload history to determine who CAN pitch.</p>
                <p><strong>Layer 2 \u2014 Usage Order:</strong> Estimates starter expected innings, then ranks available relievers by role hierarchy.</p>
                <p><strong>Layer 3 \u2014 Matchup Integration:</strong> For each predicted reliever, computes MS against the lineup slots they'll likely face.</p>
            </div>
        </div>
    </div>

</div>

<!-- BOTTOM NAV -->
<nav class="bottom-nav">
    <button class="nav-btn active" data-tab="lines">
        <span class="nav-icon">\U0001f4ca</span>
        <span>LINES</span>
    </button>
    <button class="nav-btn" data-tab="daily">
        <span class="nav-icon">\U0001f4a3</span>
        <span>HR WATCH</span>
    </button>
    <button class="nav-btn" data-tab="info">
        <span class="nav-icon">\u2139\ufe0f</span>
        <span>INFO</span>
    </button>
</nav>

<!-- Firebase SDK -->
<script src="https://www.gstatic.com/firebasejs/10.8.0/firebase-app-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.8.0/firebase-auth-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore-compat.js"></script>
<!-- Auth -->
<script src="https://morellosims.com/morello-auth.js" data-ma-theme="mlb"></script>

<script>

// TAB SWITCHING
function switchTab(target) {{
  document.querySelectorAll('.nav-btn').forEach(t => t.classList.toggle('active', t.getAttribute('data-tab') === target));
  document.querySelectorAll('.filter-btn').forEach(t => t.classList.toggle('active', t.getAttribute('data-tab') === target));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  const el = document.getElementById('tab-' + target);
  if (el) el.classList.add('active');
  window.scrollTo(0, 0);
}}
document.querySelectorAll('.nav-btn').forEach(tab => {{
  tab.addEventListener('click', () => switchTab(tab.getAttribute('data-tab')));
}});
document.querySelectorAll('.filter-btn').forEach(tab => {{
  tab.addEventListener('click', () => switchTab(tab.getAttribute('data-tab')));
}});

// LINEUP TOGGLE
function toggleLineup(idx) {{
  const grid = document.getElementById('lineup-' + idx);
  const arrow = document.getElementById('arrow-' + idx);
  const toggle = arrow?.closest('.lineup-toggle');
  if (grid) {{
    grid.classList.toggle('open');
    if (toggle) toggle.classList.toggle('open');
  }}
}}

// SORT GAMES
const originalCardOrder = Array.from(document.querySelectorAll('#tab-lines .game-card'));

function sortGames(mode, el) {{
  const container = document.querySelector('#tab-lines');
  if (!container) return;
  const cards = Array.from(container.querySelectorAll('.game-card'));
  if (!cards.length) return;

  document.querySelectorAll('.chips .chip').forEach(c => c.classList.remove('active'));
  el.classList.add('active');

  let sorted;
  if (mode === 'run_diff') {{
    sorted = [...cards].sort((a, b) => (parseFloat(b.dataset.edge) || 0) - (parseFloat(a.dataset.edge) || 0));
  }} else {{
    sorted = [...originalCardOrder];
  }}

  const parent = cards[0].parentNode;
  sorted.forEach(card => parent.appendChild(card));
}}

</script>
</body></html>'''

with open(OUTPUT, "w") as f:
    f.write(html)

# ─── Picks log — append today's C:7+ picks to CSV ──────────────────────────
PICKS_LOG = os.path.join(REPO_ROOT, "mlbsim", "picks_log.csv")
qualified_picks = [g for g in games if g["has_lineups"] and not g["odds_too_heavy"] and g.get("has_full_coverage") and g.get("odds_source") != "NO_LINE" and (g["conf"] >= MIN_CONF_PICK or g.get("must_pick"))]
skipped_heavy = [g for g in games if g["has_lineups"] and g["conf"] >= MIN_CONF_PICK and g["odds_too_heavy"]]
if skipped_heavy:
    print(f"  Skipped {len(skipped_heavy)} heavy faves: " + ", ".join(f'{g["pick_team"]} ({g["pick_odds"]:+d})' for g in skipped_heavy))

# Write header if file doesn't exist
if not os.path.exists(PICKS_LOG):
    with open(PICKS_LOG, "w") as f:
        f.write("date,time,pick,conf,value,away,home,away_runs,home_runs,away_wp,home_wp,away_ml,home_ml,away_sp,home_sp,result\n")

with open(PICKS_LOG, "a") as f:
    for g in qualified_picks:
        f.write(f'{TODAY},{g["time_str"]},{g["pick_team"]},{g["conf"]},{g["value"]},{g["away_abbr"]},{g["home_abbr"]},{g["away_runs"]},{g["home_runs"]},{g["away_wp"]},{g["home_wp"]},{g["away_ml"]},{g["home_ml"]},{g["away_sp"]},{g["home_sp"]},\n')

# ─── Picks JSON contract — upsert today's picks into picks/mlb.json ────────
# This is the source of truth read by scripts/render_dispatch.py.
import json as _json
PICKS_JSON = os.path.join(REPO_ROOT, "picks", "mlb.json")
os.makedirs(os.path.dirname(PICKS_JSON), exist_ok=True)
existing = []
if os.path.exists(PICKS_JSON):
    try:
        with open(PICKS_JSON) as f:
            existing = _json.load(f)
    except Exception:
        existing = []
by_id = {p["id"]: p for p in existing}
for g in qualified_picks:
    pick_team = g["pick_team"]
    pick_ml = g["away_ml"] if pick_team == g["away_abbr"] else g["home_ml"]
    pick_id = f'{TODAY}-mlb-{g["away_abbr"]}-{g["home_abbr"]}-ml'
    if pick_id in by_id and by_id[pick_id]["status"] != "pending":
        continue  # Never mutate settled picks; renderer reads what's there.
    by_id[pick_id] = {
        "id": pick_id,
        "sport": "mlb",
        "date": TODAY,
        "away": g["away_abbr"],
        "home": g["home_abbr"],
        "matchup": f'{g["away_abbr"]} @ {g["home_abbr"]}',
        "bet_type": "ml",
        "side": pick_team,
        "line": None,
        "odds": pick_ml,
        "pick_text": f'{pick_team} ML',
        "conf": g["conf"],
        "units": 50,
        "sim_projection": f'{g["away_abbr"]} {g["away_runs"]} - {g["home_abbr"]} {g["home_runs"]}',
        "sim_edge": g.get("value"),
        "status": "pending",
        "result": None,
        "pl": None,
        "settled_at": None,
    }
merged = sorted(by_id.values(), key=lambda p: (p["date"], p["matchup"]), reverse=True)
with open(PICKS_JSON, "w") as f:
    _json.dump(merged, f, indent=2)
print(f"  picks/mlb.json: {len(merged)} total picks ({sum(1 for p in merged if p['status'] == 'pending')} pending)")

# Print picks summary to stdout (used by commit message)
picks_summary = " | ".join(f'{g["pick_team"]} ML (C:{g["conf"]})' for g in qualified_picks)
if not picks_summary:
    picks_summary = "NO PLAYS"
print(f"\n  PICKS: {picks_summary}")

size = os.path.getsize(OUTPUT)
print(f"\n{'='*60}")
print(f"  DONE: {OUTPUT}")
print(f"  Size: {size:,} bytes")
print(f"  Games: {len(games)} ({sum(1 for g in games if g['has_lineups'])} with lineups)")
print(f"  Generated: {gen_time}")
print(f"{'='*60}")

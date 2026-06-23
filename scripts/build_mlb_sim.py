#!/usr/bin/env python3
"""
build_mlb_sim.py — Generate mlbsim/index.html from live MLB data + atlas.

Fetches today's schedule, lineups, probable pitchers from MLB Stats API,
runs the matchup model against atlas data, and renders the full page.

Usage: python3 scripts/build_mlb_sim.py
"""

import csv, json, os, sys, math, re, requests, time as _time
import urllib.request  # used by _fetch_action_network_odds + _fetch_espn_scoreboard_odds
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from mlb_momo import matchup_swing_to_momo, momentum_to_momi, ms_class, woba_class

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
ATLAS_DIR = os.path.join(REPO_ROOT, "atlas")
OUTPUT = os.path.join(REPO_ROOT, "mlbsim", "index.html")
PICKS_DIR = os.path.join(REPO_ROOT, "picks")
BASELINES_PATH = os.path.join(PICKS_DIR, "baselines.json")
MLB_PICKS_PATH = os.path.join(PICKS_DIR, "mlb.json")
MLB_TRACKED_MIN_CONF = 8


def load_season_record():
    """Use the same baseline + picks contract as the homepage dispatch."""
    try:
        from render_dispatch import aggregate as dispatch_aggregate, official_picks, load_baselines

        baseline = load_baselines().get("mlb", {})
        picks = []
        if os.path.exists(MLB_PICKS_PATH):
            with open(MLB_PICKS_PATH) as f:
                picks = json.load(f)
        agg = dispatch_aggregate(official_picks(picks, "mlb"), baseline=baseline)
        return f'{agg["wins"]}-{agg["losses"]}', f'{agg["roi"]:+.1f}%', agg.get("streak") or "-"
    except Exception as _e:
        print(f"  WARN tracked picks card contract: {_e}; using local fallback")

        try:
            with open(BASELINES_PATH) as f:
                baseline = json.load(f).get("mlb", {})
            wins = baseline.get("wins") or 0
            losses = baseline.get("losses") or 0
            risked = baseline.get("risked") or 0
            pl = baseline.get("pl") or 0
            settled_for_streak = []

            if os.path.exists(MLB_PICKS_PATH):
                with open(MLB_PICKS_PATH) as f:
                    picks = json.load(f)
                for p in picks:
                    try:
                        conf = int(p.get("conf") or 0)
                    except (TypeError, ValueError):
                        conf = 0
                    if conf < MLB_TRACKED_MIN_CONF:
                        continue
                    status = p.get("status")
                    if status not in ("win", "loss", "push"):
                        continue
                    wins += 1 if status == "win" else 0
                    losses += 1 if status == "loss" else 0
                    risked += p.get("units") or 0
                    pl += p.get("pl") or 0
                    if status in ("win", "loss"):
                        settled_for_streak.append(p)

            settled_for_streak.sort(key=lambda p: p.get("date", ""), reverse=True)
            streak = 0
            streak_type = ""
            if settled_for_streak:
                streak_type = settled_for_streak[0].get("status", "")
                for p in settled_for_streak:
                    if p.get("status") == streak_type:
                        streak += 1
                    else:
                        break
            streak_label = f'{"W" if streak_type == "win" else "L"}{streak}' if streak else "-"
            roi = (pl / risked * 100) if risked else 0
            return f"{wins}-{losses}", f'{"+" if roi >= 0 else ""}{roi:.1f}%', streak_label
        except Exception as fallback_error:
            print(f"  WARN tracked picks fallback: {fallback_error}; falling back to placeholder")
            return "0-0", "+0.0%", "-"


SEASON_RECORD, SEASON_ROI_VALUE, SEASON_STREAK = load_season_record()
SEASON_ROI = f"{SEASON_ROI_VALUE} ROI"

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
batters_atlas = load_atlas("batters.json")

# Build indexes
# pitcher_id → most recent pitcher_season record
pitcher_idx = {}
current_pitcher_idx = {}
recent_pitcher_idx = {}
for ps in pitcher_seasons:
    pid = ps["pitcher"]
    yr = ps["game_year"]
    if yr == 2026:
        current_pitcher_idx[pid] = ps
    if yr in {2025, 2026} and (
        pid not in recent_pitcher_idx or yr > recent_pitcher_idx[pid]["game_year"]
    ):
        recent_pitcher_idx[pid] = ps
    if pid not in pitcher_idx or yr > pitcher_idx[pid]["game_year"]:
        pitcher_idx[pid] = ps

batter_profile_idx = {
    int(b["batter"]): b
    for b in batters_atlas
    if b.get("batter") is not None
}

CURRENT_YEAR = int(TODAY[:4])


def atlas_current_enough_for_picks():
    """Block official picks if the matchup atlas is not current-season aware."""
    hvc_year = max((int(r.get("game_year") or 0) for r in hvc_data), default=0)
    pitcher_year = max((int(r.get("game_year") or 0) for r in pitcher_seasons), default=0)
    season_pa_key = f"season_PA_{CURRENT_YEAR}"
    current_batter_rows = sum(1 for b in batters_atlas if float(b.get(season_pa_key) or 0) > 0)
    ok = (
        hvc_year >= CURRENT_YEAR
        and pitcher_year >= CURRENT_YEAR
        and current_batter_rows >= 200
    )
    if not ok:
        print(
            "  WARN: Atlas freshness gate failed "
            f"(hvc_year={hvc_year}, pitcher_year={pitcher_year}, "
            f"{season_pa_key}_rows={current_batter_rows}); no official MLB picks"
        )
    return ok


ATLAS_CURRENT_FOR_PICKS = atlas_current_enough_for_picks()

# pitcher_id/year → tier record
tier_by_pid_year = {}
tier_idx = {}
for k, v in pitcher_tiers.items():
    pid = v["pitcher"]
    yr = v["game_year"]
    tier_by_pid_year[(pid, yr)] = v
    if pid not in tier_idx or yr > tier_idx[pid]["game_year"]:
        tier_idx[pid] = v


def get_pitcher_info(pid):
    """Return a recent atlas classification; never fall back before 2025."""
    current = current_pitcher_idx.get(pid)
    if current:
        return {**current, "has_recent_atlas": True, "sample_year": 2026}

    recent = recent_pitcher_idx.get(pid)
    if recent:
        sample_year = recent.get("game_year")
        return {**recent, "has_recent_atlas": True, "sample_year": sample_year}

    historical = pitcher_idx.get(pid, {})
    is_rhp = historical.get("is_rhp", 1)
    return {
        "pitcher": pid,
        "game_year": 2026,
        "is_rhp": is_rhp,
        "cluster": "R_UT" if is_rhp else "L_UT",
        "archetype": "No 2026/25 Sample",
        "gmm_proba": {"R_UT" if is_rhp else "L_UT": 1.0},
        "has_recent_atlas": False,
        "sample_year": None,
    }


def get_pitcher_tier(pid, sample_year):
    """Match tier to the atlas sample year; avoid stale quality fallbacks."""
    if sample_year:
        return tier_by_pid_year.get((pid, sample_year), {})
    return {}

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
MIN_CONF_PICK = MLB_TRACKED_MIN_CONF  # C:8+ qualifies as an official pick.
MAX_MISSING_BATTERS_FOR_PICK = 0
STAKE_BY_CONF = {
    10: 100,
    9: 50,
    8: 30,
    7: 20,
}
MAX_FAV_BY_CONF = {
    # Emergency cap only. The real price gate below compares model win
    # probability against the sportsbook break-even probability.
    8: -180,
    9: -200,
    10: -220,
}
MIN_MODEL_EDGE_BY_CONF = {
    # Required model probability over market break-even. When the tracked
    # season is near flat, C8 cannot be a barely-over-juice play.
    8: 0.055,
    9: 0.080,
    10: 0.130,
}


def moneyline_break_even(odds):
    """Return implied break-even probability for American odds."""
    try:
        odds = int(odds)
    except (TypeError, ValueError):
        return None
    if odds == 0:
        return None
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)


def confidence_cap_from_market_edge(price_edge):
    if price_edge is None:
        return 0
    if price_edge >= 0.130:
        return 10
    if price_edge >= 0.080:
        return 9
    if price_edge >= 0.055:
        return 8
    if price_edge >= 0.035:
        return 7
    return 6

def stake_for_conf(conf):
    """Return $PP risk by confidence grade."""
    return STAKE_BY_CONF.get(int(conf or 0), 0)

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

HR_REPEAT_BLOCKLIST = {
    "brandon lowe",
    "nathaniel lowe",
    "spencer horwitz",
    "spencer horowitz",
}


def normalize_hr_name(value):
    value = str(value or "").replace(" (H)", "")
    value = _re.sub(r"[^a-zA-Z\s]", " ", value)
    return _re.sub(r"\s+", " ", value).strip().lower()


def hr_name_blocked(value):
    return normalize_hr_name(value) in HR_REPEAT_BLOCKLIST


# Team abbreviation normalization
TEAM_ALIAS = {"ATH": "OAK", "AZ": "ARI", "ARI": "AZ", "CWS": "CHW", "CHW": "CWS", "TB": "TBR", "TBR": "TB",
              "SD": "SDP", "SDP": "SD", "SF": "SFG", "SFG": "SF", "KC": "KCR", "KCR": "KC",
              "WSH": "WAS", "WAS": "WSH"}

def normalize_abbr(abbr):
    """Normalize team abbreviation to match MLB API style."""
    return TEAM_ALIAS.get(abbr, abbr)

def team_key_variants(abbr):
    """Return acceptable abbrev variants for cross-source matching.

    Some providers use ARI where MLB renders AZ, CHW where we render CWS, etc.
    This keeps odds joins strict to real-book lines without dropping games on
    provider abbreviation drift.
    """
    variants = []
    for value in (abbr, TEAM_ALIAS.get(abbr, abbr)):
        if value and value not in variants:
            variants.append(value)
    return variants

def lookup_game_odds(odds_map, away_abbr, home_abbr):
    """Find a game's real-book odds across known team abbreviation variants."""
    for away_key in team_key_variants(away_abbr):
        for home_key in team_key_variants(home_abbr):
            game_odds = odds_map.get((away_key, home_key))
            if game_odds:
                return game_odds
    return {}

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
odds_feed_has_lines = bool(real_odds)


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


_LIVE_H2H_BY_PITCHER: dict[int, dict[int, dict]] = {}
_LIVE_H2H_FETCHED_PAIRS: set[tuple[int, int]] = set()


def _stat_int(stat, key):
    try:
        return int(stat.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _stat_rate(stat, key, fallback=0.0):
    value = stat.get(key)
    if value in (None, "", ".---", "-.--"):
        return fallback
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return fallback


def fetch_live_pitcher_h2h(pitcher_id, batter_ids):
    """Fetch live direct batter-vs-pitcher history from MLB StatsAPI.

    atlas/hitter_vs_pitcher.json can lag behind the public MLB endpoint, so
    today's HR card uses this live table for direct H2H power overrides.
    """
    batter_ids = [int(bid) for bid in batter_ids if bid]
    if not pitcher_id or not batter_ids:
        return {}

    pitcher_id = int(pitcher_id)
    rows = _LIVE_H2H_BY_PITCHER.setdefault(pitcher_id, {})

    missing_batter_ids = []
    for batter_id in batter_ids:
        pair_key = (pitcher_id, batter_id)
        if pair_key in _LIVE_H2H_FETCHED_PAIRS:
            continue
        _LIVE_H2H_FETCHED_PAIRS.add(pair_key)
        missing_batter_ids.append(batter_id)

    def fetch_pair(batter_id):
        url = (
            f"{MLB_API}/people/{batter_id}/stats"
            f"?stats=vsPlayer&group=hitting&opposingPlayerId={pitcher_id}&gameType=R"
        )
        data = fetch(url) or {}
        matching_splits = []
        for bucket in data.get("stats", []) or []:
            bucket_type = (bucket.get("type") or {}).get("displayName", "")
            for split in bucket.get("splits", []) or []:
                batter = split.get("batter") or {}
                pitcher = split.get("pitcher") or {}
                if pitcher.get("id") != pitcher_id:
                    continue
                split_batter_id = int(batter.get("id") or batter_id)
                if split_batter_id != batter_id:
                    continue
                stat = split.get("stat") or {}
                if _stat_int(stat, "plateAppearances") > 0:
                    matching_splits.append((bucket_type, stat))
        if not matching_splits:
            return batter_id, None

        total_stat = next((stat for bucket_type, stat in matching_splits if bucket_type == "vsPlayerTotal"), None)
        if total_stat:
            pa = _stat_int(total_stat, "plateAppearances")
            ab = _stat_int(total_stat, "atBats")
            hits = _stat_int(total_stat, "hits")
            hr = _stat_int(total_stat, "homeRuns")
            bb = _stat_int(total_stat, "baseOnBalls")
            k = _stat_int(total_stat, "strikeOuts")
            tb = _stat_int(total_stat, "totalBases")
            sf = _stat_int(total_stat, "sacFlies")
        else:
            stats = [stat for _bucket_type, stat in matching_splits]
            pa = sum(_stat_int(stat, "plateAppearances") for stat in stats)
            ab = sum(_stat_int(stat, "atBats") for stat in stats)
            hits = sum(_stat_int(stat, "hits") for stat in stats)
            hr = sum(_stat_int(stat, "homeRuns") for stat in stats)
            bb = sum(_stat_int(stat, "baseOnBalls") for stat in stats)
            k = sum(_stat_int(stat, "strikeOuts") for stat in stats)
            tb = sum(_stat_int(stat, "totalBases") for stat in stats)
            sf = sum(_stat_int(stat, "sacFlies") for stat in stats)
        if pa <= 0:
            return batter_id, None
        avg = hits / ab if ab else 0.0
        obp_den = ab + bb + sf
        obp = (hits + bb) / obp_den if obp_den else (total_stat and _stat_rate(total_stat, "obp")) or 0.0
        slg = tb / ab if ab else (total_stat and _stat_rate(total_stat, "slg")) or 0.0
        ops = obp + slg
        return batter_id, {
            "h2h_pa": pa,
            "h2h_ab": ab,
            "h2h_h": hits,
            "h2h_hr": hr,
            "h2h_bb": bb,
            "h2h_k": k,
            "h2h_tb": tb,
            "h2h_avg": round(avg, 3),
            "h2h_obp": round(obp, 3),
            "h2h_slg": round(slg, 3),
            "h2h_ops": round(ops, 3),
            "h2h_hr_rate": round(hr / pa, 4) if pa else 0.0,
        }

    if missing_batter_ids:
        max_workers = min(8, len(missing_batter_ids))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(fetch_pair, batter_id) for batter_id in missing_batter_ids]
            for future in as_completed(futures):
                batter_id, row = future.result()
                if row:
                    rows[batter_id] = row

    return {bid: rows[bid] for bid in batter_ids if bid in rows}

# ─── Process each game ───────────────────────────────────────────────────────
games = []
all_batter_matchups = []  # for daily projections tab

for g in games_raw:
    game_pk = g.get("gamePk")
    away_team = g["teams"]["away"]["team"]
    home_team = g["teams"]["home"]["team"]
    away_abbr = away_team.get("abbreviation", "???")
    home_abbr = home_team.get("abbreviation", "???")
    venue = g.get("venue", {}).get("name", "")
    game_time_utc = g.get("gameDate", "")
    game_status = g.get("status", {})

    # Parse game time to ET
    starts_at = None
    try:
        gt = datetime.fromisoformat(game_time_utc.replace("Z", "+00:00")).astimezone(ET)
        starts_at = gt
        time_str = gt.strftime("%-I:%M %p ET")
    except:
        time_str = "TBD"
    state = game_status.get("abstractGameState", "")
    detailed_state = game_status.get("detailedState", "")
    has_started = bool((starts_at and NOW >= starts_at) or state in {"Live", "Final"} or detailed_state in {"In Progress", "Final"})

    # Probable pitchers
    away_sp_data = g["teams"]["away"].get("probablePitcher", {})
    home_sp_data = g["teams"]["home"].get("probablePitcher", {})
    away_sp_id = away_sp_data.get("id")
    home_sp_id = home_sp_data.get("id")
    away_sp_name = away_sp_data.get("fullName", "TBD")
    home_sp_name = home_sp_data.get("fullName", "TBD")

    # Pitcher info from atlas
    away_ps = get_pitcher_info(away_sp_id)
    home_ps = get_pitcher_info(home_sp_id)
    away_cluster = away_ps.get("cluster", "R_UT")
    home_cluster = home_ps.get("cluster", "R_UT")
    away_arch = away_ps.get("archetype", "Unknown")
    home_arch = home_ps.get("archetype", "Unknown")
    away_hand = "LHP" if away_ps.get("is_rhp", 1) == 0 else "RHP"
    home_hand = "LHP" if home_ps.get("is_rhp", 1) == 0 else "RHP"

    # Tier info
    away_tier = get_pitcher_tier(away_sp_id, away_ps.get("sample_year"))
    home_tier = get_pitcher_tier(home_sp_id, home_ps.get("sample_year"))
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
        away_ps = get_pitcher_info(away_sp_id)
        away_cluster = away_ps.get("cluster", "R_UT")
        away_arch = away_ps.get("archetype", "Unknown")
        away_hand = "LHP" if away_ps.get("is_rhp", 1) == 0 else "RHP"
        away_tier = get_pitcher_tier(away_sp_id, away_ps.get("sample_year"))
        away_tier_name = away_tier.get("tier", "T3_Standard")
        away_tier_mult = away_tier.get("effective_multiplier", 1.0)
    if not home_sp_id and ext.get("home_sp_id"):
        home_sp_id = ext["home_sp_id"]
        home_sp_name = ext.get("home_sp_name", home_sp_name)
        home_ps = get_pitcher_info(home_sp_id)
        home_cluster = home_ps.get("cluster", "R_UT")
        home_arch = home_ps.get("archetype", "Unknown")
        home_hand = "LHP" if home_ps.get("is_rhp", 1) == 0 else "RHP"
        home_tier = get_pitcher_tier(home_sp_id, home_ps.get("sample_year"))
        home_tier_name = home_tier.get("tier", "T3_Standard")
        home_tier_mult = home_tier.get("effective_multiplier", 1.0)

    def process_lineup(lineup_raw, opp_gmm_proba, team_abbr, opp_h2h=None):
        """Process a lineup using GMM-weighted multi-cluster matching.
        opp_gmm_proba: dict of {cluster: probability} from the opposing pitcher's GMM."""
        opp_h2h = opp_h2h or {}
        batters = []
        team_woba_sum = 0
        team_pa = 0
        team_h = 0; team_bb = 0; team_hr = 0; team_tb = 0

        for i, p in enumerate(lineup_raw):
            pid = p.get("id")
            name = p.get("fullName", "Unknown")
            pos = lookup_position(pid, p)  # '' if unknown — caller must handle

            base_w = get_base_woba(pid)
            base_h, base_bb, base_hr, base_tb = get_base_rates(pid)
            profile = batter_profile_idx.get(int(pid), {}) if pid is not None else {}
            season_pa = float(profile.get("season_PA_2026") or 0)
            season_hr = float(profile.get("season_HR_2026") or 0)
            baseline_pa = float(profile.get("baseline_PA") or 0)
            player_total_pa = float(profile.get("total_PA") or 0)
            season_hr_rate = season_hr / season_pa if season_pa > 0 else 0.0
            direct_h2h = opp_h2h.get(int(pid), {}) if pid is not None else {}

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

            momo_score = matchup_swing_to_momo(base_w, vs_woba)

            batters.append({
                "order": i + 1,
                "name": name,
                "id": pid,
                "pos": pos,
                # MOMO: optimized matchup output from pitcher-DNA wOBA swing.
                "ms": momo_score,
                "run_contrib": 0.0,
                # MOMI starts at MOMO, then moves up/down with live momentum.
                "momi": momo_score,
                "woba_delta": round(vs_woba - base_w, 3),
                "base_woba": round(base_w, 3),
                "vs_woba": round(vs_woba, 3),
                "total_pa": round(total_pa),
                "hr_rate": round(hr_rate, 4),
                "base_hr_rate": round(base_hr, 4),
                "hr_lift": round(hr_rate - base_hr, 4),
                "season_pa": round(season_pa),
                "season_hr": round(season_hr),
                "season_hr_rate": round(season_hr_rate, 4),
                "baseline_pa": round(baseline_pa),
                "player_total_pa": round(player_total_pa),
                "h2h_pa": direct_h2h.get("h2h_pa", 0),
                "h2h_ab": direct_h2h.get("h2h_ab", 0),
                "h2h_h": direct_h2h.get("h2h_h", 0),
                "h2h_hr": direct_h2h.get("h2h_hr", 0),
                "h2h_bb": direct_h2h.get("h2h_bb", 0),
                "h2h_k": direct_h2h.get("h2h_k", 0),
                "h2h_tb": direct_h2h.get("h2h_tb", 0),
                "h2h_avg": direct_h2h.get("h2h_avg", 0.0),
                "h2h_obp": direct_h2h.get("h2h_obp", 0.0),
                "h2h_slg": direct_h2h.get("h2h_slg", 0.0),
                "h2h_ops": direct_h2h.get("h2h_ops", 0.0),
                "h2h_hr_rate": direct_h2h.get("h2h_hr_rate", 0.0),
                "proj_pa": pa,
                "proj_h": proj_h,
                "proj_bb": proj_bb,
                "proj_hr": proj_hr,
                "proj_tb": proj_tb,
            })

        team_avg_woba = team_woba_sum / max(len(lineup_raw), 1)
        runs = base_runs(team_pa, team_h, team_bb, team_hr, team_tb)

        for b in batters:
            without_runs = base_runs(
                max(0.0, team_pa - b["proj_pa"]),
                max(0.0, team_h - b["proj_h"]),
                max(0.0, team_bb - b["proj_bb"]),
                max(0.0, team_hr - b["proj_hr"]),
                max(0.0, team_tb - b["proj_tb"]),
            )
            run_contrib = max(0.0, runs - without_runs)
            b["run_contrib"] = round(run_contrib, 2)

            all_batter_matchups.append({
                "id": b["id"],
                "name": b["name"],
                "team": team_abbr,
                "ms": b["ms"],
                "run_contrib": b["run_contrib"],
                "momi": b["momi"],
                "woba_delta": b["woba_delta"],
                "base_woba": b["base_woba"],
                "vs_woba": b["vs_woba"],
                "total_pa": b["total_pa"],
                "hr_rate": b["hr_rate"],
                "base_hr_rate": b["base_hr_rate"],
                "hr_lift": b["hr_lift"],
                "season_pa": b["season_pa"],
                "season_hr": b["season_hr"],
                "season_hr_rate": b["season_hr_rate"],
                "baseline_pa": b["baseline_pa"],
                "player_total_pa": b["player_total_pa"],
                "h2h_pa": b["h2h_pa"],
                "h2h_ab": b["h2h_ab"],
                "h2h_h": b["h2h_h"],
                "h2h_hr": b["h2h_hr"],
                "h2h_bb": b["h2h_bb"],
                "h2h_k": b["h2h_k"],
                "h2h_tb": b["h2h_tb"],
                "h2h_avg": b["h2h_avg"],
                "h2h_obp": b["h2h_obp"],
                "h2h_slg": b["h2h_slg"],
                "h2h_ops": b["h2h_ops"],
                "h2h_hr_rate": b["h2h_hr_rate"],
                "order": b["order"],
                "pos": b["pos"],
                "proj_hr": round(b["proj_hr"], 3),
                "opp_pitcher": "",  # filled later
                "opp_team": "",
            })

        return batters, round(runs, 1), round(team_avg_woba, 3), team_pa

    # Get GMM probabilities for opposing pitchers (multi-cluster DNA)
    home_gmm = home_ps.get("gmm_proba", {home_cluster: 1.0})
    away_gmm = away_ps.get("gmm_proba", {away_cluster: 1.0})

    if has_lineups:
        away_batter_ids = [p.get("id") for p in away_lineup_raw if p.get("id")]
        home_batter_ids = [p.get("id") for p in home_lineup_raw if p.get("id")]
        # Direct H2H is historical batter-vs-starter context, not in-game stat
        # leakage, so keep it populated after first pitch for late refreshes.
        away_direct_h2h = fetch_live_pitcher_h2h(home_sp_id, away_batter_ids)
        home_direct_h2h = fetch_live_pitcher_h2h(away_sp_id, home_batter_ids)

        # Pre-fetch positions in one bulk call so render shows "C · R" not "? · R"
        _bulk_fetch_positions(
            away_batter_ids + home_batter_ids
        )
        away_batters, away_runs_raw, away_woba, away_pa = process_lineup(
            away_lineup_raw, home_gmm, away_abbr, away_direct_h2h)
        home_batters, home_runs_raw, home_woba, home_pa = process_lineup(
            home_lineup_raw, away_gmm, home_abbr, home_direct_h2h)

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
        away_matchups = all_batter_matchups[-len(away_lineup_raw)-len(home_lineup_raw):-len(home_lineup_raw)]
        home_matchups = all_batter_matchups[-len(home_lineup_raw):]
        for bm in away_matchups:
            bm["opp_pitcher"] = home_sp_name
            bm["opp_team"] = home_abbr
            bm["opp_tier"] = home_tier_name
            bm["opp_tier_mult"] = home_tier_mult
            bm["park_factor"] = pf
            bm["team_total"] = away_runs
            bm["opp_bp_delta"] = away_bp_delta
        for bm in home_matchups:
            bm["opp_pitcher"] = away_sp_name
            bm["opp_team"] = away_abbr
            bm["opp_tier"] = away_tier_name
            bm["opp_tier_mult"] = away_tier_mult
            bm["park_factor"] = pf
            bm["team_total"] = home_runs
            bm["opp_bp_delta"] = home_bp_delta
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

    away_has_full = bool(away_ps) and away_ps.get("has_recent_atlas") is True
    home_has_full = bool(home_ps) and home_ps.get("has_recent_atlas") is True

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
    pick_coverage_ok = (
        len(missing_coverage) <= MAX_MISSING_BATTERS_FOR_PICK
        and away_has_full
        and home_has_full
        and ATLAS_CURRENT_FOR_PICKS
    )
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

    edge = round(run_diff, 1)
    if not has_lineups:
        conf = 0
        edge = 0

    # Real sportsbook odds — STRICT. We ONLY display prices the book actually
    # published. If the odds source doesn't have this game, we leave the line
    # blank ("—") and exclude the pick from picks/mlb.json. Tracking a pick
    # against a fabricated price is dishonest and breaks settlement math.
    game_odds = lookup_game_odds(real_odds, away_abbr, home_abbr)
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

    # Odds filter: require model probability to clear sportsbook break-even.
    pick_ml_str = home_ml if pick_team == home_abbr else away_ml
    try:
        pick_odds_raw = int(pick_ml_str)
    except (ValueError, TypeError):
        pick_odds_raw = 0
    pick_model_prob = (home_wp if pick_team == home_abbr else away_wp) / 100
    pick_break_even = moneyline_break_even(pick_odds_raw)
    pick_price_edge = None
    odds_too_heavy = False
    if pick_break_even is not None:
        pick_price_edge = pick_model_prob - pick_break_even
        market_conf_cap = confidence_cap_from_market_edge(pick_price_edge)
        if pick_odds_raw < -180 and pick_price_edge < 0.130:
            market_conf_cap = min(market_conf_cap, 8)
        conf = min(conf, market_conf_cap)
        if not ATLAS_CURRENT_FOR_PICKS:
            conf = 0
        min_price_edge = MIN_MODEL_EDGE_BY_CONF.get(conf, 0.030)
        hard_favorite_cap = MAX_FAV_BY_CONF.get(conf, -200)
        odds_too_heavy = (
            pick_odds_raw < hard_favorite_cap
            or pick_price_edge < min_price_edge
        )
    else:
        min_price_edge = MIN_MODEL_EDGE_BY_CONF.get(conf, 0.030)
        hard_favorite_cap = MAX_FAV_BY_CONF.get(conf, -200)

    # Legacy "value" field retained as alias of conf for back-compat with the
    # HTML template's data-value attribute. Single signal now.
    value = conf

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
        "pick_model_prob": round(pick_model_prob, 4),
        "pick_break_even": round(pick_break_even, 4) if pick_break_even is not None else None,
        "pick_price_edge": round(pick_price_edge, 4) if pick_price_edge is not None else None,
        "min_price_edge": min_price_edge,
        "has_full_coverage": has_full_coverage,
        "pick_coverage_ok": pick_coverage_ok,
        "missing_coverage_count": len(missing_coverage),
        "pick_odds": pick_odds_raw,
        "venue": venue, "time_str": time_str, "game_pk": game_pk,
        "has_started": has_started,
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

def load_published_mlb_picks():
    try:
        with open(MLB_PICKS_PATH) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

_PUBLISHED_TODAY_PICK_KEYS = None
_PUBLISHED_TODAY_BY_GAME = None

def published_today_pick_keys():
    global _PUBLISHED_TODAY_PICK_KEYS
    if _PUBLISHED_TODAY_PICK_KEYS is None:
        _PUBLISHED_TODAY_PICK_KEYS = {
            (p.get("away"), p.get("home"), p.get("side"))
            for p in load_published_mlb_picks()
            if p.get("sport") == "mlb" and p.get("date") == TODAY and p.get("bet_type") == "ml"
        }
    return _PUBLISHED_TODAY_PICK_KEYS

def published_today_by_game():
    global _PUBLISHED_TODAY_BY_GAME
    if _PUBLISHED_TODAY_BY_GAME is None:
        _PUBLISHED_TODAY_BY_GAME = {
            (p.get("away"), p.get("home")): p
            for p in load_published_mlb_picks()
            if p.get("sport") == "mlb" and p.get("date") == TODAY and p.get("bet_type") == "ml"
        }
    return _PUBLISHED_TODAY_BY_GAME

def published_pick_for_game(g):
    return published_today_by_game().get((g.get("away_abbr"), g.get("home_abbr")))

def is_published_pick(g):
    return (g.get("away_abbr"), g.get("home_abbr"), g.get("pick_team")) in published_today_pick_keys()

def load_locked_hr_lotto_column():
    """Keep today's posted HR board stable after any game has started."""
    if os.environ.get("MLB_FORCE_HR_RESELECT") == "1":
        return ""
    if not any(g.get("has_started") for g in games):
        return ""
    try:
        with open(os.path.join(REPO_ROOT, "mlbsim", "index.html"), encoding="utf-8") as f:
            html = f.read()
    except Exception:
        return ""
    generated = _re.search(r"Generated\s+(\d{4}-\d{2}-\d{2})\s+\d{1,2}:\d{2}\s+ET", html)
    if not generated or generated.group(1) != TODAY:
        return ""
    start_marker = '<div class="daily-col daily-center daily-hr-lotto">'
    end_marker = '<div class="daily-col daily-side daily-hot-side">'
    start = html.find(start_marker)
    if start < 0:
        return ""
    end = html.find(end_marker, start)
    if end < 0:
        return ""
    snippet = html[start:end].rstrip()
    if "hr-name" not in snippet:
        return ""
    snippet_lower = snippet.lower()
    if any(name in snippet_lower for name in HR_REPEAT_BLOCKLIST):
        print("  HR Go-Yard: locked card has blocked repeat names, reselecting")
        return ""
    print("  HR Go-Yard: preserving posted card after first pitch")
    return snippet

def qualifies_as_pick(g):
    if not g.get("has_lineups"):
        return False
    if g.get("odds_too_heavy") or g.get("odds_source") == "NO_LINE":
        return False
    if not g.get("pick_coverage_ok"):
        return False
    if g.get("has_started") and not is_published_pick(g):
        return False
    return g.get("conf", 0) >= MIN_CONF_PICK

def render_batter(b):
    mc = ms_class(b["ms"])
    mic = ms_class(b.get("momi", 50))
    wc = woba_class(b["base_woba"], b["vs_woba"])
    pos = h(b["pos"]) if b.get("pos") else "UTIL"
    total_pa = int(round(float(b.get("total_pa") or 0)))
    pa_html = f'<span class="batter-pa">{total_pa}PA</span>'
    return f'''<div class="batter-row">
  <div class="batter-top">
    <span class="batter-order">{b["order"]}</span>
    <span class="batter-name">{h(b["name"])}</span>
  </div>
  <div class="batter-bottom">
    <span class="batter-detail">
      <span class="batter-stats">{pos}</span>
      {pa_html}
      <span class="batter-range">+{b.get("run_contrib", 0):.2f} R</span>
    </span>
    <span class="batter-metrics">
      <span class="batter-metric {mc}"><span>MOMO</span>{b["ms"]}</span>
      <span class="batter-metric {mic}"><span>MOMI</span>{b.get("momi", 50)}</span>
    </span>
  </div>
  <div class="batter-woba">
    <span class="woba-base"><span>WOBA</span>.{str(b["base_woba"])[2:]}</span>
    <span class="woba-dna">\U0001f9ec</span>
    <span class="woba-vs {wc}"><span>ARCH</span>.{str(b["vs_woba"])[2:]}</span>
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
    published_pick = published_pick_for_game(g)
    if published_pick:
        conf = int(published_pick.get("conf") or g["conf"])
        cc = conf_color(conf)
        side = published_pick.get("side") or g["pick_team"]
        pick_html = f'''<div class="sim-pick"><span class="pick-type-label">ML</span> {h(side)} ML <span class="mc-conf-num" style="color:{cc}" title="Confidence">C:{conf}</span></div>'''
    elif qualifies_as_pick(g):
        cc = conf_color(g["conf"])
        pick_html = f'''<div class="sim-pick"><span class="pick-type-label">ML</span> {h(g["pick_team"])} ML <span class="mc-conf-num" style="color:{cc}" title="Confidence">C:{g["conf"]}</span></div>'''
    elif g["has_lineups"] and g["conf"] >= MIN_CONF_PICK and g.get("odds_source") == "NO_LINE":
        pick_html = '<div class="sim-pick" style="background:#FFA500;color:#000;border-color:#000">NO LINE — book has not posted ML</div>'
    elif g["has_lineups"] and g["conf"] >= MIN_CONF_PICK and g["odds_too_heavy"]:
        model_pct = (g.get("pick_model_prob") or 0) * 100
        be_pct = (g.get("pick_break_even") or 0) * 100
        need_pct = (g.get("min_price_edge") or 0) * 100
        price_label = "MODEL EDGE CLOSE TO JUICE" if g.get("conf") == 8 else "BAD PRICE"
        price_title = (
            f'Model {model_pct:.1f}%, break-even {be_pct:.1f}%, '
            f'needs +{need_pct:.1f}% edge'
        )
        pick_html = f'<div class="sim-pick" style="background:#FF3333;color:#fff;border-color:#000" title="{h(price_title)}">{price_label} ({g["pick_odds"]:+d})</div>'
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
  <a href="https://www.bovada.lv/welcome/P1BXDI3/join?extcmpid=rafcopy" target="_blank" rel="noopener" class="aff-btn aff-bovada">
    <span class="aff-name">BOVADA</span><span class="aff-cta">JOIN NOW</span>
  </a>
</div>
  {lineup_html}
</div>'''

# ─── Fetch hitting streaks for all batters in today's lineups ─────────────────
print("\nFetching hitting streaks...")
batter_streaks = {}  # pid -> {"streak": int, "last7_avg": float}
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
        streak = 0
        for s in reversed(splits):
            hits = s.get("stat", {}).get("hits", 0)
            if hits > 0:
                streak += 1
            else:
                break
        recent = splits[-7:] if len(splits) >= 7 else splits
        recent5 = splits[-5:] if len(splits) >= 5 else splits
        recent10 = splits[-10:] if len(splits) >= 10 else splits
        total_h = sum(s.get("stat", {}).get("hits", 0) for s in recent)
        total_ab = sum(s.get("stat", {}).get("atBats", 0) for s in recent)
        last7_avg = total_h / max(total_ab, 1)
        batter_streaks[pid] = {
            "streak": streak,
            "last7_avg": round(last7_avg, 3),
            "hit_games_5": sum(1 for s in recent5 if s.get("stat", {}).get("hits", 0) > 0),
            "games_5": len(recent5),
            "hit_games_7": sum(1 for s in recent if s.get("stat", {}).get("hits", 0) > 0),
            "games_7": len(recent),
            "hit_games_10": sum(1 for s in recent10 if s.get("stat", {}).get("hits", 0) > 0),
            "games_10": len(recent10),
        }
    except Exception:
        continue

print(f"  Fetched streaks for {len(batter_streaks)} batters")
print(f"  Batters on 3+ game streaks: {sum(1 for v in batter_streaks.values() if v['streak'] >= 3)}")
print(f"  Batters with hits in 4 of last 5: {sum(1 for v in batter_streaks.values() if v.get('games_5', 0) >= 5 and v.get('hit_games_5', 0) >= 4)}")

for g in games:
    if not g["has_lineups"]:
        continue
    for b in g["away_batters"] + g["home_batters"]:
        streak_data = batter_streaks.get(b["id"], {})
        b["streak"] = streak_data.get("streak", 0)
        b["last7_avg"] = streak_data.get("last7_avg", 0)
        b["hit_games_5"] = streak_data.get("hit_games_5", 0)
        b["games_5"] = streak_data.get("games_5", 0)
        b["hit_games_7"] = streak_data.get("hit_games_7", 0)
        b["games_7"] = streak_data.get("games_7", 0)
        b["hit_games_10"] = streak_data.get("hit_games_10", 0)
        b["games_10"] = streak_data.get("games_10", 0)
        b["momi"] = momentum_to_momi(
            b["ms"], b["streak"], b["last7_avg"],
            b["hit_games_5"], b["games_5"],
            b["hit_games_7"], b["games_7"],
            b["hit_games_10"], b["games_10"],
        )

for bm in all_batter_matchups:
    streak_data = batter_streaks.get(bm.get("id"), {})
    bm["streak"] = streak_data.get("streak", 0)
    bm["last7_avg"] = streak_data.get("last7_avg", 0)
    bm["hit_games_5"] = streak_data.get("hit_games_5", 0)
    bm["games_5"] = streak_data.get("games_5", 0)
    bm["hit_games_7"] = streak_data.get("hit_games_7", 0)
    bm["games_7"] = streak_data.get("games_7", 0)
    bm["hit_games_10"] = streak_data.get("hit_games_10", 0)
    bm["games_10"] = streak_data.get("games_10", 0)
    bm["momi"] = momentum_to_momi(
        bm["ms"], bm["streak"], bm["last7_avg"],
        bm["hit_games_5"], bm["games_5"],
        bm["hit_games_7"], bm["games_7"],
        bm["hit_games_10"], bm["games_10"],
    )


def render_hr_watch_tab():
    HR_CORE_MIN = 0.085
    HR_LONGSHOT_MIN = 0.065
    HR_CORE_MAX_ROWS = 6
    HR_CORE_H2H_ROWS = 1
    HR_CORE_STACK_ROWS = 1
    HR_CORE_NEAR_MIN = 0.078
    HR_LONGSHOT_MAX_ROWS = 8
    HR_LONGSHOT_STANDARD_ROWS = 2
    HR_LONGSHOT_H2H_ROWS = 0
    HR_LONGSHOT_DAMAGE_ROWS = 4
    HR_LONGSHOT_SURGE_ROWS = 3
    HR_LONGSHOT_FORM_ROWS = 1
    HR_LONGSHOT_STACK_ROWS = 1
    HR_HEAT_MAX_ROWS = 10
    HR_MIN_MATCHUP_PA = 30
    HR_MIN_PLAYER_PA = 100
    HR_MIN_RUN_CONTRIB = 0.90
    HR_MIN_LIFT = 0.008

    def hr_batter_allowed(bm):
        return not hr_name_blocked(bm.get("name"))

    def has_power_profile(bm):
        baseline_pa = bm.get("baseline_pa", 0) or 0
        season_pa = bm.get("season_pa", 0) or 0
        season_hr = bm.get("season_hr", 0) or 0
        base_hr = bm.get("base_hr_rate", 0) or 0
        season_hr_rate = bm.get("season_hr_rate", 0) or 0
        established_power = baseline_pa >= 450 and base_hr >= 0.036
        current_power = season_pa >= 150 and season_hr >= 7 and season_hr_rate >= 0.035
        high_impact_sample = season_pa >= 100 and season_hr >= 6 and season_hr_rate >= 0.045
        elite_track_record = baseline_pa >= 1000 and base_hr >= 0.033 and season_hr_rate >= 0.030
        return established_power or current_power or high_impact_sample or elite_track_record

    def has_reliable_hr_context(bm):
        if bm.get("total_pa", 0) < HR_MIN_MATCHUP_PA:
            return False
        if bm.get("player_total_pa", 0) < HR_MIN_PLAYER_PA:
            return False
        if bm.get("order", 9) > 6 and bm.get("base_hr_rate", 0) < 0.045:
            return False
        if bm.get("park_factor", 1.0) < 0.96:
            return False
        return True

    def pitcher_context_ok(bm, core=True):
        tier = bm.get("opp_tier", "")
        if tier == "T1_Apex":
            return (
                bm.get("hr_rate", 0) >= (0.105 if core else 0.090)
                and bm.get("base_hr_rate", 0) >= 0.045
            )
        if tier == "T2_Core" and not core:
            return bm.get("hr_rate", 0) >= 0.078
        return True

    def all_around_heat_ok(bm, core=True):
        return (
            bm.get("ms", 0) >= (75 if core else 82)
            and bm.get("momi", 50) >= (72 if core else 82)
        )

    def hr_damage_score(bm):
        tier_penalty = {"T1_Apex": 1.2, "T2_Core": 0.45}.get(bm.get("opp_tier", ""), 0.0)
        lineup_bonus = max(0, 7 - int(bm.get("order", 7) or 7)) * 0.18
        return (
            bm.get("proj_hr", 0) * 100
            + bm.get("base_hr_rate", 0) * 90
            + max(0, bm.get("hr_lift", 0)) * 150
            + bm.get("run_contrib", 0) * 1.6
            + max(0, bm.get("momi", 50) - 70) * 0.02
            + max(0, bm.get("ms", 50) - 70) * 0.015
            + max(0, bm.get("park_factor", 1.0) - 1.0) * 12
            + lineup_bonus
            - tier_penalty
        )

    def hr_damage_lane_ok(bm, core=True):
        """Pure HR fit can override all-around MOMO/MOMI for Go-Yard eligibility."""
        min_rate = 0.078 if core else HR_LONGSHOT_MIN
        min_lift = 0.020 if core else 0.012
        min_proj = 0.320 if core else 0.250
        min_run = 0.85 if core else 0.70
        min_base = 0.038 if core else 0.034
        min_score = 44.0 if core else 40.0
        return (
            bm.get("order", 9) <= 6
            and bm.get("hr_rate", 0) >= min_rate
            and bm.get("base_hr_rate", 0) >= min_base
            and bm.get("hr_lift", 0) >= min_lift
            and bm.get("proj_hr", 0) >= min_proj
            and bm.get("run_contrib", 0) >= min_run
            and hr_damage_score(bm) >= min_score
        )

    def team_stack_pressure(bm):
        peers = [
            other for other in all_batter_matchups
            if other.get("id") != bm.get("id")
            and other.get("team") == bm.get("team")
            and other.get("opp_pitcher") == bm.get("opp_pitcher")
            and other.get("opp_team") == bm.get("opp_team")
        ]
        pressure = 0.0
        for other in peers:
            if other.get("order", 9) > 6 and other.get("base_hr_rate", 0) < 0.040:
                continue
            pressure += max(0, other.get("hr_rate", 0) - 0.045) * 100
            pressure += max(0, other.get("base_hr_rate", 0) - 0.032) * 40
            pressure += max(0, other.get("hr_lift", 0)) * 45
        return pressure

    def h2h_power_score(bm):
        pa = bm.get("h2h_pa", 0) or 0
        hr = bm.get("h2h_hr", 0) or 0
        if pa < 8 or hr <= 0:
            return 0.0
        return min(
            55.0,
            hr * 11
            + min(pa, 24) * 0.45
            + max(0, bm.get("h2h_slg", 0) - 0.550) * 18
            + max(0, bm.get("h2h_ops", 0) - 0.900) * 16,
        )

    def h2h_direct_hr_fit(bm, core=True):
        pa = bm.get("h2h_pa", 0) or 0
        hr = bm.get("h2h_hr", 0) or 0
        if hr <= 0 or pa < 8:
            return False
        direct_hr_rate = hr / pa if pa else 0.0
        min_pa = 14 if core else 8
        min_hr = 2 if core else 1
        return (
            pa >= min_pa
            and hr >= min_hr
            and direct_hr_rate >= (0.050 if core else 0.040)
            and bm.get("h2h_slg", 0) >= (0.560 if core else 0.500)
            and bm.get("h2h_ops", 0) >= (0.850 if core else 0.780)
        )

    def h2h_has_model_support(bm, core=True):
        return (
            bm.get("hr_rate", 0) >= (0.075 if core else 0.055)
            and bm.get("base_hr_rate", 0) >= (0.038 if core else 0.034)
            and bm.get("proj_hr", 0) >= (0.300 if core else 0.220)
            and bm.get("run_contrib", 0) >= (0.70 if core else 0.55)
            and hr_damage_score(bm) >= (42.0 if core else 34.0)
        )

    def recent_power_score(bm):
        hit5 = bm.get("hit_games_5", 0) if bm.get("games_5", 0) >= 5 else 0
        hit7 = bm.get("hit_games_7", 0) if bm.get("games_7", 0) >= 7 else 0
        hit10 = bm.get("hit_games_10", 0) if bm.get("games_10", 0) >= 10 else 0
        density = max(hit5 * 1.4, hit7, hit10 * 0.7)
        return (
            bm.get("hr_rate", 0) * 120
            + bm.get("base_hr_rate", 0) * 90
            + bm.get("season_hr_rate", 0) * 45
            + max(0, bm.get("momi", 50) - 70) * 0.28
            + max(0, bm.get("streak", 0)) * 0.55
            + density
            + min(16.0, team_stack_pressure(bm)) * 0.55
            + max(0, bm.get("team_total", 0) - 4.5) * 2.2
        )

    def surge_power_score(bm):
        hit5 = bm.get("hit_games_5", 0) if bm.get("games_5", 0) >= 5 else 0
        hit7 = bm.get("hit_games_7", 0) if bm.get("games_7", 0) >= 7 else 0
        density = max(hit5 * 1.5, hit7)
        return (
            bm.get("team_total", 0) * 5.5
            + min(45.0, team_stack_pressure(bm)) * 0.95
            + bm.get("run_contrib", 0) * 9.0
            + bm.get("hr_rate", 0) * 120
            + bm.get("base_hr_rate", 0) * 115
            + max(0, bm.get("hr_lift", 0)) * 80
            + bm.get("season_hr_rate", 0) * 55
            + max(0, bm.get("momi", 50) - 70) * 0.45
            + density * 1.3
            + max(0, bm.get("park_factor", 1.0) - 1.0) * 28
            + min(6, bm.get("h2h_hr", 0)) * 1.6
        )

    def hr_surge_lane_ok(bm, core=True):
        power_signal = (
            bm.get("base_hr_rate", 0) >= (0.036 if core else 0.034)
            or (
                bm.get("season_pa", 0) >= 100
                and bm.get("season_hr", 0) >= 7
                and bm.get("season_hr_rate", 0) >= 0.030
            )
            or (
                bm.get("hr_rate", 0) >= (0.055 if core else 0.040)
                and bm.get("hr_lift", 0) >= 0.018
                and bm.get("run_contrib", 0) >= 0.90
                and (bm.get("base_hr_rate", 0) >= 0.028 or bm.get("season_hr", 0) >= 7)
            )
        )
        stack_or_total = (
            bm.get("team_total", 0) >= 7.0
            or team_stack_pressure(bm) >= 12.0
            or bm.get("park_factor", 1.0) >= 1.08
        )
        rhythm_or_history = (
            bm.get("momi", 50) >= 76
            or bm.get("streak", 0) >= 2
            or (bm.get("games_5", 0) >= 5 and bm.get("hit_games_5", 0) >= 3)
        )
        return (
            bm.get("order", 9) <= (6 if core else 7)
            and bm.get("player_total_pa", 0) >= HR_MIN_PLAYER_PA
            and bm.get("park_factor", 1.0) >= 0.96
            and bm.get("hr_rate", 0) >= (0.052 if core else 0.040)
            and bm.get("run_contrib", 0) >= (0.95 if core else 0.80)
            and power_signal
            and stack_or_total
            and rhythm_or_history
            and surge_power_score(bm) >= (86.0 if core else 72.0)
        )

    def pressure_power_score(bm):
        hit_density = 0.0
        if bm.get("games_5", 0) >= 5:
            hit_density += max(0, bm.get("hit_games_5", 0) - 2) * 7
        if bm.get("streak", 0) >= 3:
            hit_density += 6
        return (
            bm.get("team_total", 0) * 8.0
            + min(45.0, team_stack_pressure(bm)) * 1.4
            + bm.get("run_contrib", 0) * 14.0
            + bm.get("hr_rate", 0) * 150
            + bm.get("base_hr_rate", 0) * 120
            + max(0, bm.get("momi", 50) - 70) * 0.9
            + (14 if bm.get("order", 9) <= 2 else 0)
            + (8 if bm.get("season_hr", 0) >= 7 else 0)
            + hit_density
        )

    def hr_pressure_lane_ok(bm):
        order = bm.get("order", 9)
        top_order_or_stack = (
            order <= 3
            or (order <= 7 and team_stack_pressure(bm) >= 25.0)
            or (
                order <= 5
                and bm.get("team_total", 0) >= 8.5
                and bm.get("base_hr_rate", 0) >= 0.045
            )
        )
        power_ok = (
            bm.get("base_hr_rate", 0) >= 0.035
            or (bm.get("season_pa", 0) >= 120 and bm.get("season_hr", 0) >= 7)
            or (bm.get("hr_rate", 0) >= 0.065 and bm.get("season_hr", 0) >= 6)
        )
        context_ok = (
            bm.get("team_total", 0) >= 7.0
            or team_stack_pressure(bm) >= 18.0
            or bm.get("park_factor", 1.0) >= 1.08
        )
        heat_ok = (
            bm.get("momi", 50) >= 86
            or (bm.get("games_5", 0) >= 5 and bm.get("hit_games_5", 0) >= 3)
        )
        return (
            top_order_or_stack
            and bm.get("player_total_pa", 0) >= HR_MIN_PLAYER_PA
            and bm.get("hr_rate", 0) >= 0.043
            and bm.get("run_contrib", 0) >= 0.95
            and power_ok
            and context_ok
            and heat_ok
        )

    def pressure_card_sort_key(bm):
        return (
            -pressure_power_score(bm),
            -hr_selection_score(bm),
            -hr_damage_score(bm),
            -bm.get("hr_rate", 0),
        )

    def hr_recent_power_lane_ok(bm, core=True):
        hit_density = (
            bm.get("streak", 0) >= 3
            or (bm.get("games_5", 0) >= 5 and bm.get("hit_games_5", 0) >= 4)
            or bm.get("momi", 50) >= 88
        )
        power_signal = (
            bm.get("base_hr_rate", 0) >= (0.038 if core else 0.034)
            or (
                bm.get("season_pa", 0) >= 120
                and bm.get("season_hr", 0) >= 7
                and bm.get("season_hr_rate", 0) >= 0.030
            )
            or (
                bm.get("hr_rate", 0) >= (0.095 if core else 0.070)
                and bm.get("run_contrib", 0) >= 1.15
                and (bm.get("base_hr_rate", 0) >= 0.028 or bm.get("season_hr", 0) >= 7)
            )
        )
        stack_or_total = (
            bm.get("team_total", 0) >= (5.8 if core else 5.4)
            or team_stack_pressure(bm) >= (10.0 if core else 8.0)
            or bm.get("park_factor", 1.0) >= 1.04
        )
        return (
            bm.get("order", 9) <= (6 if core else 8)
            and bm.get("player_total_pa", 0) >= HR_MIN_PLAYER_PA
            and bm.get("park_factor", 1.0) >= 0.96
            and bm.get("hr_rate", 0) >= (0.070 if core else 0.040)
            and bm.get("run_contrib", 0) >= (0.75 if core else 0.45)
            and power_signal
            and stack_or_total
            and (hit_density or bm.get("base_hr_rate", 0) >= 0.050 or team_stack_pressure(bm) >= 14.0)
            and recent_power_score(bm) >= (26.0 if core else 20.0)
        )

    def hr_h2h_lane_ok(bm, core=True):
        """Direct pitcher history can boost proven HR damage, not replace it."""
        min_pa = 12 if core else 8
        min_hr = 2 if core else 1
        min_ops = 0.950 if core else 0.850
        min_slg = 0.600 if core else 0.520
        min_run = 0.50 if core else 0.45
        direct_fit = h2h_direct_hr_fit(bm, core=core)
        team_total_ok = bm.get("team_total", 0) >= (4.0 if direct_fit else 4.4)
        score_ok = h2h_power_score(bm) >= (28.0 if direct_fit and core else (32.0 if core else 20.0))
        return (
            bm.get("h2h_pa", 0) >= min_pa
            and bm.get("h2h_hr", 0) >= min_hr
            and (direct_fit or bm.get("h2h_ops", 0) >= min_ops)
            and (direct_fit or bm.get("h2h_slg", 0) >= min_slg)
            and bm.get("base_hr_rate", 0) >= (0.028 if direct_fit else 0.030)
            and bm.get("run_contrib", 0) >= (0.42 if direct_fit else min_run)
            and team_total_ok
            and bm.get("park_factor", 1.0) >= (0.94 if direct_fit else 0.96)
            and bm.get("order", 9) <= 7
            and score_ok
            and h2h_has_model_support(bm, core=core)
        )

    def hr_stack_lane_ok(bm):
        tier = bm.get("opp_tier", "")
        min_rate = 0.070 if tier == "T1_Apex" else 0.055
        has_stack_context = (
            bm.get("team_total", 0) >= 4.8
            or bm.get("opp_tier_mult", 1.0) >= 1.05
            or team_stack_pressure(bm) >= 4.0
        )
        return (
            bm.get("order", 9) <= 6
            and bm.get("hr_rate", 0) >= min_rate
            and bm.get("base_hr_rate", 0) >= 0.034
            and bm.get("hr_lift", 0) >= 0.010
            and bm.get("proj_hr", 0) >= 0.230
            and bm.get("run_contrib", 0) >= 0.65
            and has_stack_context
        )

    def hr_primary_stack_lane_ok(bm):
        """Near-core HR bats in a live power stack can steal primary-card slots."""
        has_primary_stack_context = (
            team_stack_pressure(bm) >= 4.0
            or bm.get("team_total", 0) >= 4.8
            or bm.get("park_factor", 1.0) >= 1.01
            or bm.get("opp_tier_mult", 1.0) >= 1.05
        )
        return (
            hr_stack_lane_ok(bm)
            and bm.get("hr_rate", 0) >= HR_CORE_NEAR_MIN
            and bm.get("base_hr_rate", 0) >= 0.040
            and bm.get("hr_lift", 0) >= 0.018
            and bm.get("proj_hr", 0) >= 0.280
            and bm.get("run_contrib", 0) >= 0.75
            and bm.get("order", 9) <= 6
            and has_primary_stack_context
            and pitcher_context_ok(bm, core=False)
        )

    def hr_standard_lane_ok(bm, core=True):
        hr_rate = bm.get("hr_rate", 0) or 0
        min_rate = HR_CORE_MIN if core else HR_LONGSHOT_MIN
        return (
            hr_rate >= min_rate
            and bm.get("hr_lift", 0) >= (HR_MIN_LIFT if core else 0.010)
            and bm.get("proj_hr", 0) >= (0.34 if core else 0.30)
            and bm.get("run_contrib", 0) >= (HR_MIN_RUN_CONTRIB if core else 1.00)
            and all_around_heat_ok(bm, core=core)
        )

    def hr_card_qualifies(bm, core=True):
        hr_rate = bm.get("hr_rate", 0) or 0
        max_rate_ok = True if core else hr_rate < HR_CORE_MIN
        standard_lane = hr_standard_lane_ok(bm, core=core)
        damage_lane = hr_damage_lane_ok(bm, core=core) and (not core or hr_rate >= HR_CORE_MIN)
        surge_lane = hr_surge_lane_ok(bm, core=core)
        recent_lane = hr_recent_power_lane_ok(bm, core=core)
        stack_lane = False if core else hr_stack_lane_ok(bm)
        h2h_lane = hr_h2h_lane_ok(bm, core=core)
        power_ok = (
            has_power_profile(bm)
            or surge_lane
            or recent_lane
            or stack_lane
            or (h2h_lane and h2h_has_model_support(bm, core=core))
        )
        context_ok = has_reliable_hr_context(bm) or (
            h2h_lane
            and bm.get("player_total_pa", 0) >= HR_MIN_PLAYER_PA
            and bm.get("park_factor", 1.0) >= 0.96
        )
        return (
            max_rate_ok
            and power_ok
            and context_ok
            and (pitcher_context_ok(bm, core=core) or surge_lane)
            and (standard_lane or damage_lane or surge_lane or recent_lane or stack_lane or h2h_lane)
        )

    def hr_selection_score(bm):
        stack_weight = 0.35
        if hr_h2h_lane_ok(bm, core=True) or hr_damage_lane_ok(bm, core=True):
            stack_weight = 0.70
        return (
            hr_damage_score(bm)
            + h2h_power_score(bm) * 1.35
            + surge_power_score(bm) * 0.65
            + recent_power_score(bm) * 0.85
            + team_stack_pressure(bm) * stack_weight
            + max(0, bm.get("hr_rate", 0) - 0.060) * 180
            + max(0, bm.get("base_hr_rate", 0) - 0.040) * 95
            + max(0, bm.get("park_factor", 1.0) - 1.0) * 16
        )

    def hr_lane_rank(bm, core=True):
        if hr_damage_lane_ok(bm, core=core):
            return 0
        if hr_surge_lane_ok(bm, core=core):
            return 1
        if hr_standard_lane_ok(bm, core=core):
            return 2
        if hr_recent_power_lane_ok(bm, core=core):
            return 3
        if hr_h2h_lane_ok(bm, core=core):
            return 4
        if hr_primary_stack_lane_ok(bm) or hr_stack_lane_ok(bm):
            return 5
        return 6

    def hr_lane_sort_key(bm, core=True):
        return (
            hr_lane_rank(bm, core=core),
            -hr_selection_score(bm),
            -h2h_power_score(bm),
            -hr_damage_score(bm),
            -bm.get("hr_rate", 0),
        )

    def hr_lane_label(bm):
        if hr_damage_lane_ok(bm, core=True) or hr_damage_lane_ok(bm, core=False):
            return "DAMAGE"
        if hr_surge_lane_ok(bm, core=True) or hr_surge_lane_ok(bm, core=False):
            return "SURGE"
        if hr_recent_power_lane_ok(bm, core=True) or hr_recent_power_lane_ok(bm, core=False):
            return "FORM"
        if hr_pressure_lane_ok(bm):
            return "PRESSURE"
        if hr_h2h_lane_ok(bm, core=True) or hr_h2h_lane_ok(bm, core=False):
            return "H2H"
        if hr_primary_stack_lane_ok(bm) or hr_stack_lane_ok(bm):
            return "STACK"
        return "MODEL"

    HR_LANE_META = {
        "DAMAGE": ("power", "HR Profile", "Projected HR%, batter HR baseline, pitcher-type lift, and run setup all point up."),
        "SURGE": ("boost", "Run Setup", "Team total, park, lineup slot, or recent form is adding HR probability."),
        "FORM": ("heater", "Hot Bat", "Recent hit density is adding support to the HR projection."),
        "PRESSURE": ("order", "Lineup Edge", "Batting order and run contribution are adding chances."),
        "H2H": ("history", "Pitcher History", "Direct track record vs today's pitcher adds support."),
        "STACK": ("lineup", "Lineup Stack", "Multiple bats in this lineup are pressuring the same pitcher."),
        "MODEL": ("model", "Balanced Fit", "Projected HR%, pitcher type, and lineup setup all grade well."),
    }
    HR_LANE_ORDER = ["DAMAGE", "SURGE", "STACK", "FORM", "PRESSURE", "H2H", "MODEL"]

    def hr_lane_key(lane):
        return HR_LANE_META.get(lane, HR_LANE_META["MODEL"])[0]

    def hr_lane_display(lane):
        return HR_LANE_META.get(lane, HR_LANE_META["MODEL"])[1]

    def hr_lane_short(lane):
        return HR_LANE_META.get(lane, HR_LANE_META["MODEL"])[2]

    def fmt_pct(value, digits=1):
        return f"{round((value or 0) * 100, digits):.{digits}f}%"

    def fmt_num(value, digits=1):
        return f"{float(value or 0):.{digits}f}"

    def fmt_pp(value):
        return f"+{round(max(0, value or 0) * 100, 1):.1f}pp"

    def fmt_signed_pp(value):
        return f"{float(value or 0) * 100:+.1f}pp"

    def hr_lane_reason(bm):
        return hr_lane_short(hr_lane_label(bm))

    def render_hr_metric(label, value, tone=""):
        return f'''<div class="hr-metric {tone}">
        <span>{h(label)}</span>
        <strong>{h(value)}</strong>
      </div>'''

    def render_hr_proof(label, value, tone=""):
        return f'''<div class="hr-proof {tone}">
        <span>{h(label)}</span>
        <strong>{h(value)}</strong>
      </div>'''

    def render_hr_explain(label, value, sub=""):
        sub_html = f"<em>{h(sub)}</em>" if sub else ""
        return f'''<div class="hr-explain">
        <span>{h(label)}</span>
        <strong>{h(value)}</strong>
        {sub_html}
      </div>'''

    def render_hr_row(rank, bm, status="lotto"):
        hr_pct = round(bm["hr_rate"] * 100, 1)
        base_pct = round((bm.get("base_hr_rate", 0) or 0) * 100, 1)
        lift_pct = round((bm.get("hr_lift", 0) or 0) * 100, 1)
        positive_lift_pct = max(0, lift_pct)
        clean_name = str(bm.get("name", "")).replace(" (H)", "").strip()
        lane = hr_lane_label(bm)
        lane_name = hr_lane_display(lane)
        lane_key = hr_lane_key(lane)
        h2h_tag = ""
        h2h_value = "0"
        if bm.get("h2h_pa", 0) >= 8 and bm.get("h2h_hr", 0) > 0:
            h2h_tag = f'<span>H2H {int(bm.get("h2h_hr", 0))}HR/{int(bm.get("h2h_pa", 0))}PA</span>'
            h2h_value = f'{int(bm.get("h2h_hr", 0))}/{int(bm.get("h2h_pa", 0))}'
        if bm["hr_rate"] >= 0.06:
            heat = "hr-fire"
        elif bm["hr_rate"] >= 0.04:
            heat = "hr-hot"
        elif bm["hr_rate"] >= 0.025:
            heat = "hr-warm"
        else:
            heat = "hr-mild"
        order = int(bm.get("order", 9) or 9)
        stack = round(team_stack_pressure(bm), 1)
        park = fmt_num(bm.get("park_factor", 1.0), 2)
        team_total = fmt_num(bm.get("team_total", 0), 1)
        run = fmt_num(bm.get("run_contrib", 0), 2)
        surge = round(surge_power_score(bm))
        h2h_display = h2h_value if h2h_value != "0" else None
        bar_scale = 15.0
        base_w = max(0.0, min(100.0, (base_pct / bar_scale) * 100.0))
        boost_w = max(0.0, min(100.0 - base_w, (positive_lift_pct / bar_scale) * 100.0))
        total_w = max(0.0, min(100.0, (hr_pct / bar_scale) * 100.0))
        matchup_sub = f"today vs pitcher type"
        lineup_value = f"#{order} / +{run} R"
        park_value = f"{park}x / {team_total}"
        h2h_text = f"H2H {h2h_display}" if h2h_display else f"Park {park}x"
        proof_items = [
            render_hr_proof("Power", f"POW {base_pct}%", "tone-red" if base_pct >= 5.0 else ""),
            render_hr_proof("Lift", f"LIFT {fmt_signed_pp(bm.get('hr_lift', 0))}", "tone-red" if positive_lift_pct >= 3.0 else ""),
            render_hr_proof("H2H" if h2h_display else "Context", f"H2H {h2h_display}" if h2h_display else f"RUN +{run}", "tone-red" if h2h_display else ""),
        ]
        explain_items = [
            render_hr_explain("Batter HR%", f"{base_pct}%", "own HR rate"),
            render_hr_explain("Vs Pitcher Type", fmt_signed_pp(bm.get("hr_lift", 0)), matchup_sub),
            render_hr_explain("Lineup/Runs", lineup_value, "slot and run value"),
            render_hr_explain("Park/Total", park_value, h2h_text),
        ]

        return f'''<div class="hr-row {heat}" data-hr-card="1" data-hr-lane="{h(lane)}" data-hr-status="{h(status)}">
		  <div class="hr-rank">{rank}</div>
		  <div class="hr-info">
		    <div class="hr-title-line">
        <div class="hr-name">{h(clean_name)}</div>
        <span class="hr-lane-pill lane-{h(lane_key)}">{h(lane_name)}</span>
      </div>
		    <div class="hr-meta">#{order} {h(bm["team"])} vs {h(bm["opp_pitcher"])} ({h(bm["opp_team"])}) &middot; team {team_total} &middot; park {park}x</div>
	      <div class="hr-signal">{h(hr_lane_reason(bm))}</div>
        <div class="hr-odds" style="--base-w:{base_w:.1f}%;--boost-w:{boost_w:.1f}%;--total-w:{total_w:.1f}%">
          <div class="hr-odds-head"><span>Projected HR%</span><strong>{hr_pct}%</strong></div>
          <div class="hr-odds-bar" aria-label="Projected HR {hr_pct} percent, batter baseline {base_pct} percent, pitcher type lift {fmt_signed_pp(bm.get("hr_lift", 0))}">
            <span class="hr-bar-base"></span>
            <span class="hr-bar-boost"></span>
            <span class="hr-bar-end"></span>
          </div>
          <div class="hr-odds-scale"><span>0%</span><span>15% elite scale</span></div>
        </div>
        <div class="hr-proof-row">{''.join(proof_items)}</div>
	      <div class="hr-explain-row">{''.join(explain_items)}</div>
		  </div>
	  <div class="hr-rate-col">
	    <div class="hr-rate">{hr_pct}%</div>
    <div class="hr-rate-label">Projected HR</div>
  </div>
</div>'''

    def render_hr_rows(candidates, rank_prefix="", status="lotto"):
        rows = []
        for i, bm in enumerate(candidates):
            rank = f"{rank_prefix}{i+1}" if rank_prefix else f"{i+1}"
            rows.append(render_hr_row(rank, bm, status=status))
        return "".join(rows)

    def hr_board_candidate_ok(bm):
        power_signal = (
            bm.get("base_hr_rate", 0) >= 0.030
            or bm.get("season_hr_rate", 0) >= 0.030
            or bm.get("hr_lift", 0) >= 0.012
            or team_stack_pressure(bm) >= 8.0
        )
        return (
            bm.get("order", 9) <= 8
            and bm.get("player_total_pa", 0) >= 80
            and bm.get("total_pa", 0) >= 20
            and bm.get("park_factor", 1.0) >= 0.93
            and bm.get("hr_rate", 0) >= 0.030
            and power_signal
        )

    def render_hr_intel(core, watch, board):
        if not board:
            return ""
        top_rate = max(core, key=lambda x: x.get("hr_rate", 0)) if core else None
        top_stack = max(core, key=lambda x: team_stack_pressure(x)) if core else None
        top_damage = max(core, key=lambda x: hr_damage_score(x)) if core else None
        top_watch = max(watch, key=lambda x: x.get("hr_rate", 0)) if watch else None
        lane_counts = {}
        for bm in core + watch:
            lane_counts[hr_lane_label(bm)] = lane_counts.get(hr_lane_label(bm), 0) + 1
        lane_mix = " / ".join(
            f"{hr_lane_display(k)} {v}" for k, v in sorted(lane_counts.items(), key=lambda item: HR_LANE_ORDER.index(item[0]) if item[0] in HR_LANE_ORDER else 99)
        ) or "Awaiting qualifiers"

        def cell(label, value, sub):
            return f'''<div class="hr-intel-cell">
          <span>{h(label)}</span>
          <strong>{h(value)}</strong>
          <em>{h(sub)}</em>
        </div>'''

        def hitter_cell(label, bm, sub):
            if not bm:
                return cell(label, "No qualifier", "Awaiting Go-Yard card")
            return cell(label, f'{bm.get("name")} {fmt_pct(bm.get("hr_rate"))}', sub(bm))

        return f'''<div class="hr-intel-strip">
        <div class="hr-intel-head">
          <div>
            <div class="edge-kicker primary">HR DATA ROOM</div>
            <div class="bucket-title">GO-YARD CARD</div>
          </div>
          <div class="hr-intel-copy">Top board is the primary shortlist. Watchlist is secondary context, sorted by the same Go-Yard proof points.</div>
        </div>
        <div class="hr-intel-grid">
          {hitter_cell("Highest HR%", top_rate, lambda bm: f'{bm.get("team")} vs {bm.get("opp_pitcher")}')}
          {cell("Best Batter HR%", f'{top_damage.get("name")}' if top_damage else "No qualifier", f'Batter {fmt_pct(top_damage.get("base_hr_rate"))} / Type {fmt_pp(top_damage.get("hr_lift"))}' if top_damage else "Awaiting Go-Yard card")}
          {hitter_cell("Best Watch", top_watch, lambda bm: f'{bm.get("team")} vs {bm.get("opp_pitcher")}')}
          {cell("Card Mix", lane_mix, f'{len(core)} top / {len(watch)} watch')}
        </div>
      </div>'''

    def render_hr_deep_board(board, core_ids, watch_ids):
        if not board:
            return '<div class="empty-state">NO HR BOARD QUALIFIERS</div>'
        body = ""
        for i, bm in enumerate(board[:24]):
            clean_name = str(bm.get("name", "")).replace(" (H)", "").strip()
            lane = hr_lane_label(bm)
            lane_name = hr_lane_display(lane)
            lane_key = hr_lane_key(lane)
            if bm.get("id") in core_ids:
                status = "CARD"
                status_key = "lotto"
            elif bm.get("id") in watch_ids:
                status = "WATCH"
                status_key = "watch"
            else:
                continue
            h2h = "0"
            if bm.get("h2h_pa", 0) >= 8 and bm.get("h2h_hr", 0) > 0:
                h2h = f'{int(bm.get("h2h_hr", 0))}/{int(bm.get("h2h_pa", 0))}'
            body += f'''<tr class="hr-board-row {h(status_key)}" data-hr-card="1" data-hr-lane="{h(lane)}" data-hr-status="{h(status_key)}">
          <td class="hr-col-rank">{i+1}</td>
          <td><span class="hr-status-pill status-{h(status_key)}">{h(status)}</span></td>
          <td class="hr-col-hitter"><strong>{h(clean_name)}</strong><span>{h(bm.get("team"))} &middot; #{int(bm.get("order", 9) or 9)}</span></td>
          <td class="hr-col-match">{h(bm.get("opp_pitcher"))}<span>{h(bm.get("opp_team"))}</span></td>
          <td><span class="hr-board-lane lane-{h(lane_key)}">{h(lane_name)}</span></td>
          <td>{fmt_pct(bm.get("hr_rate"))}</td>
          <td>{round(hr_damage_score(bm))}</td>
          <td class="hr-col-sur">{round(surge_power_score(bm))}</td>
          <td class="hr-col-stack">{round(team_stack_pressure(bm), 1)}</td>
          <td class="hr-col-park">{fmt_num(bm.get("park_factor", 1.0), 2)}x</td>
          <td class="hr-col-total">{fmt_num(bm.get("team_total", 0), 1)}</td>
          <td class="hr-col-h2h">{h2h}</td>
        </tr>'''
        return f'''<div class="daily-bucket hr-deep-board">
        <div class="bucket-head secondary">
          <div class="edge-kicker secondary">DATA</div>
          <div class="bucket-title">GO-YARD CARD TABLE</div>
          <div class="bucket-copy">Only hitters on the visible Go-Yard or Watch cards appear here.</div>
          {criteria_row("HR rate", "damage score", "surge power", "stack pressure", "park factor", "H2H")}
        </div>
        <div class="hr-board-scroll">
          <table class="hr-board-table">
            <thead>
              <tr>
                <th>Card #</th><th>Status</th><th>Hitter</th><th>Pitcher</th><th>Lens</th><th>HR%</th><th>Damage</th><th class="hr-col-sur">Boost</th><th class="hr-col-stack">Pressure</th><th class="hr-col-park">Park</th><th class="hr-col-total">Total</th><th class="hr-col-h2h">H2H</th>
              </tr>
            </thead>
            <tbody>{body}</tbody>
          </table>
        </div>
      </div>'''

    core_pool = [
        bm for bm in all_batter_matchups
        if hr_batter_allowed(bm)
        and (hr_card_qualifies(bm, core=True) or hr_primary_stack_lane_ok(bm))
    ]
    core_h2h_overrides = sorted(
        [bm for bm in core_pool if hr_h2h_lane_ok(bm, core=True)],
        key=lambda x: (-h2h_power_score(x), -hr_selection_score(x), -x.get("hr_rate", 0))
    )[:HR_CORE_H2H_ROWS]
    core_ids = {bm.get("id") for bm in core_h2h_overrides}
    core_stack_candidates = sorted(
        [
            bm for bm in core_pool
            if bm.get("id") not in core_ids
            and hr_primary_stack_lane_ok(bm)
            and not hr_card_qualifies(bm, core=True)
        ],
        key=lambda x: (-team_stack_pressure(x), -hr_selection_score(x), -x.get("hr_rate", 0))
    )
    core_standard_slots = max(0, HR_CORE_MAX_ROWS - len(core_h2h_overrides))
    core_standard = sorted(
        [bm for bm in core_pool if bm.get("id") not in core_ids and hr_card_qualifies(bm, core=True)],
        key=lambda x: hr_lane_sort_key(x, core=True)
    )[:core_standard_slots]
    core_ids |= {bm.get("id") for bm in core_standard}

    core_stack_overrides = []
    used_core_stack_keys = set()
    if len(core_h2h_overrides) + len(core_standard) < HR_CORE_MAX_ROWS:
        for bm in core_stack_candidates:
            if bm.get("id") in core_ids:
                continue
            key = (bm.get("team"), bm.get("opp_pitcher"), bm.get("opp_team"))
            if key in used_core_stack_keys:
                continue
            core_stack_overrides.append(bm)
            used_core_stack_keys.add(key)
            if len(core_stack_overrides) >= HR_CORE_STACK_ROWS:
                break
    core_hr = sorted(
        (core_h2h_overrides + core_stack_overrides + core_standard)[:HR_CORE_MAX_ROWS],
        key=lambda x: hr_lane_sort_key(x, core=True)
    )

    core_ids = {bm.get("id") for bm in core_hr}
    longshot_pool = [
        bm for bm in all_batter_matchups
        if hr_batter_allowed(bm)
        and bm.get("id") not in core_ids
        and (
            hr_card_qualifies(bm, core=False)
            or hr_card_qualifies(bm, core=True)
            or hr_surge_lane_ok(bm, core=False)
        )
    ]
    longshot_standard = sorted(
        [bm for bm in longshot_pool if hr_standard_lane_ok(bm, core=False)],
        key=lambda x: hr_lane_sort_key(x, core=False)
    )[:HR_LONGSHOT_STANDARD_ROWS]

    longshot_h2h_overrides = sorted(
        [
            bm for bm in longshot_pool
            if hr_h2h_lane_ok(bm, core=False)
        ],
        key=lambda x: (-h2h_power_score(x), -hr_damage_score(x), -x.get("hr_rate", 0))
    )[:HR_LONGSHOT_H2H_ROWS]

    used_longshot_ids = {bm.get("id") for bm in longshot_h2h_overrides}
    longshot_standard = [bm for bm in longshot_standard if bm.get("id") not in used_longshot_ids]
    used_longshot_ids |= {bm.get("id") for bm in longshot_standard}
    longshot_damage_overrides = sorted(
        [
            bm for bm in longshot_pool
            if bm.get("id") not in used_longshot_ids
            and hr_damage_lane_ok(bm, core=False)
        ],
        key=lambda x: (-hr_selection_score(x), -hr_damage_score(x), -x.get("hr_rate", 0))
    )[:HR_LONGSHOT_DAMAGE_ROWS]

    used_longshot_ids |= {bm.get("id") for bm in longshot_damage_overrides}
    longshot_surge_overrides = sorted(
        [
            bm for bm in longshot_pool
            if bm.get("id") not in used_longshot_ids
            and hr_surge_lane_ok(bm, core=False)
        ],
        key=lambda x: (-surge_power_score(x), -hr_selection_score(x), -x.get("hr_rate", 0))
    )[:HR_LONGSHOT_SURGE_ROWS]

    used_longshot_ids |= {bm.get("id") for bm in longshot_surge_overrides}
    longshot_form_overrides = sorted(
        [
            bm for bm in longshot_pool
            if bm.get("id") not in used_longshot_ids
            and hr_recent_power_lane_ok(bm, core=False)
            and not all_around_heat_ok(bm, core=False)
        ],
        key=lambda x: (-recent_power_score(x), -hr_damage_score(x), -x.get("hr_rate", 0))
    )[:HR_LONGSHOT_FORM_ROWS]

    used_longshot_ids |= {bm.get("id") for bm in longshot_form_overrides}
    core_stack_keys = {
        (bm.get("team"), bm.get("opp_pitcher"), bm.get("opp_team"))
        for bm in core_hr
    }
    damage_stack_keys = {
        (bm.get("team"), bm.get("opp_pitcher"), bm.get("opp_team"))
        for bm in longshot_damage_overrides
    }
    form_stack_keys = {
        (bm.get("team"), bm.get("opp_pitcher"), bm.get("opp_team"))
        for bm in longshot_form_overrides
    }
    surge_stack_keys = {
        (bm.get("team"), bm.get("opp_pitcher"), bm.get("opp_team"))
        for bm in longshot_surge_overrides
    }
    standard_stack_keys = {
        (bm.get("team"), bm.get("opp_pitcher"), bm.get("opp_team"))
        for bm in longshot_standard
    }

    def stack_anchor_score(bm):
        key = (bm.get("team"), bm.get("opp_pitcher"), bm.get("opp_team"))
        if key in core_stack_keys:
            return 3
        if key in damage_stack_keys:
            return 2
        if key in surge_stack_keys:
            return 2
        if key in form_stack_keys:
            return 2
        if key in standard_stack_keys:
            return 1
        return 0

    stack_candidates = sorted(
        [
            bm for bm in longshot_pool
            if bm.get("id") not in used_longshot_ids
            and hr_stack_lane_ok(bm)
            and stack_anchor_score(bm) > 0
        ],
        key=lambda x: (-stack_anchor_score(x), -team_stack_pressure(x), -hr_damage_score(x), -x.get("hr_rate", 0))
    )
    longshot_stack_overrides = []
    used_stack_keys = set()
    for bm in stack_candidates:
        key = (bm.get("team"), bm.get("opp_pitcher"), bm.get("opp_team"))
        if key in used_stack_keys:
            continue
        longshot_stack_overrides.append(bm)
        used_stack_keys.add(key)
        if len(longshot_stack_overrides) >= HR_LONGSHOT_STACK_ROWS:
            break

    used_longshot_ids |= {bm.get("id") for bm in longshot_stack_overrides}
    longshot_damage = (
        longshot_h2h_overrides
        + longshot_damage_overrides
        + longshot_surge_overrides
        + longshot_form_overrides
        + longshot_standard
        + longshot_stack_overrides
    )[:HR_LONGSHOT_MAX_ROWS]
    if len(longshot_damage) < HR_LONGSHOT_MAX_ROWS:
        backfill = sorted(
            [bm for bm in longshot_pool if bm.get("id") not in used_longshot_ids],
            key=lambda x: (-hr_damage_score(x), -x.get("hr_rate", 0))
        )
        longshot_damage.extend(backfill[:HR_LONGSHOT_MAX_ROWS - len(longshot_damage)])

    pressure_pool = sorted(
        [bm for bm in all_batter_matchups if hr_batter_allowed(bm) and hr_pressure_lane_ok(bm)],
        key=pressure_card_sort_key,
    )
    if pressure_pool:
        total_hr_rows = HR_CORE_MAX_ROWS + HR_LONGSHOT_MAX_ROWS
        pressure_selected = []
        pressure_ids = set()
        for bm in pressure_pool + core_hr + longshot_damage:
            if bm.get("id") in pressure_ids:
                continue
            pressure_selected.append(bm)
            pressure_ids.add(bm.get("id"))
            if len(pressure_selected) >= total_hr_rows:
                break
        core_hr = pressure_selected[:HR_CORE_MAX_ROWS]
        longshot_damage = pressure_selected[HR_CORE_MAX_ROWS:total_hr_rows]
        core_ids = {bm.get("id") for bm in core_hr}

    display_pool = []
    display_ids = set()
    for bm in sorted(
        [
            bm for bm in all_batter_matchups
            if hr_batter_allowed(bm) and hr_board_candidate_ok(bm)
        ],
        key=lambda x: (
            -(x.get("hr_rate", 0) or 0),
            -hr_selection_score(x),
            normalize_hr_name(x.get("name")),
        ),
    ):
        if bm.get("id") in display_ids:
            continue
        display_pool.append(bm)
        display_ids.add(bm.get("id"))
    core_hr = display_pool[:HR_CORE_MAX_ROWS]
    longshot_damage = display_pool[HR_CORE_MAX_ROWS:HR_CORE_MAX_ROWS + HR_LONGSHOT_MAX_ROWS]
    core_ids = {bm.get("id") for bm in core_hr}

    if os.getenv("MLB_HR_AUDIT"):
        def audit_row(bm):
            return {
                "name": bm.get("name"),
                "team": bm.get("team"),
                "order": bm.get("order"),
                "opp_pitcher": bm.get("opp_pitcher"),
                "opp_team": bm.get("opp_team"),
                "lane": hr_lane_label(bm),
                "core_qualifies": hr_card_qualifies(bm, core=True),
                "watch_qualifies": hr_card_qualifies(bm, core=False),
                "damage_core": hr_damage_lane_ok(bm, core=True),
                "damage_watch": hr_damage_lane_ok(bm, core=False),
                "surge_core": hr_surge_lane_ok(bm, core=True),
                "surge_watch": hr_surge_lane_ok(bm, core=False),
                "pressure_watch": hr_pressure_lane_ok(bm),
                "form_core": hr_recent_power_lane_ok(bm, core=True),
                "form_watch": hr_recent_power_lane_ok(bm, core=False),
                "h2h_core": hr_h2h_lane_ok(bm, core=True),
                "h2h_watch": hr_h2h_lane_ok(bm, core=False),
                "stack_watch": hr_stack_lane_ok(bm),
                "selection_score": round(hr_selection_score(bm), 3),
                "damage_score": round(hr_damage_score(bm), 3),
                "surge_power_score": round(surge_power_score(bm), 3),
                "pressure_power_score": round(pressure_power_score(bm), 3),
                "recent_power_score": round(recent_power_score(bm), 3),
                "stack_pressure": round(team_stack_pressure(bm), 3),
                "hr_rate": bm.get("hr_rate"),
                "base_hr_rate": bm.get("base_hr_rate"),
                "hr_lift": bm.get("hr_lift"),
                "proj_hr": bm.get("proj_hr"),
                "run_contrib": bm.get("run_contrib"),
                "team_total": bm.get("team_total"),
                "park_factor": bm.get("park_factor"),
                "momo": bm.get("ms"),
                "momi": bm.get("momi"),
                "streak": bm.get("streak"),
                "hit_games_5": bm.get("hit_games_5"),
                "games_5": bm.get("games_5"),
                "hit_games_7": bm.get("hit_games_7"),
                "games_7": bm.get("games_7"),
                "season_pa": bm.get("season_pa"),
                "season_hr": bm.get("season_hr"),
                "season_hr_rate": bm.get("season_hr_rate"),
                "player_total_pa": bm.get("player_total_pa"),
                "h2h_pa": bm.get("h2h_pa"),
                "h2h_hr": bm.get("h2h_hr"),
                "h2h_ops": bm.get("h2h_ops"),
            }

        audit_path = os.path.join(REPO_ROOT, "mlbsim", "hr_lotto_audit.json")
        selected_ids = {bm.get("id") for bm in core_hr + longshot_damage}
        with open(audit_path, "w") as f:
            json.dump({
                "generated": NOW.isoformat(),
                "core": [audit_row(bm) for bm in core_hr],
                "watch": [audit_row(bm) for bm in longshot_damage],
                "all": sorted(
                    [audit_row(bm) | {"selected": bm.get("id") in selected_ids} for bm in all_batter_matchups],
                    key=lambda row: (-row["selection_score"], -row["damage_score"], -(row.get("hr_rate") or 0)),
                ),
            }, f, indent=2)
        print(f"  HR audit: {audit_path}")

    hr_html = render_hr_rows(core_hr)
    longshot_html = render_hr_rows(longshot_damage, "L", status="watch")
    watch_ids = {bm.get("id") for bm in longshot_damage}
    hr_card_table_rows = core_hr + longshot_damage
    hr_intel_html = render_hr_intel(core_hr, longshot_damage, hr_card_table_rows)

    def recent_hit_label(bm):
        if bm.get("streak", 0) >= 5:
            return f'{bm["streak"]}G streak'
        if bm.get("games_5", 0) >= 5 and bm.get("hit_games_5", 0) >= 4:
            return f'{bm["hit_games_5"]}/5 hit games'
        if bm.get("games_7", 0) >= 7 and bm.get("hit_games_7", 0) >= 5:
            return f'{bm["hit_games_7"]}/7 hit games'
        if bm.get("games_10", 0) >= 10 and bm.get("hit_games_10", 0) >= 7:
            return f'{bm["hit_games_10"]}/10 hit games'
        if bm.get("streak", 0) >= 2:
            return f'{bm["streak"]}G streak'
        return f'{bm.get("streak", 0)}G streak'

    heating_candidates = []
    featured_hr_ids = core_ids | {bm.get("id") for bm in longshot_damage}
    for bm in all_batter_matchups:
        pid = bm.get("id")
        if pid in featured_hr_ids:
            continue
        streak_data = batter_streaks.get(pid, {})
        streak = streak_data.get("streak", 0)
        last7 = streak_data.get("last7_avg", 0)
        woba_bump = bm["vs_woba"] - bm["base_woba"]
        momentum_delta = bm.get("momi", bm["ms"]) - bm["ms"]
        hit5 = streak_data.get("hit_games_5", 0)
        games5 = streak_data.get("games_5", 0)
        hit7 = streak_data.get("hit_games_7", 0)
        games7 = streak_data.get("games_7", 0)
        hit10 = streak_data.get("hit_games_10", 0)
        games10 = streak_data.get("games_10", 0)
        has_density = (
            (games5 >= 5 and hit5 >= 4) or
            (games7 >= 7 and hit7 >= 5) or
            (games10 >= 10 and hit10 >= 7)
        )
        has_rhythm = streak >= 5 or has_density
        has_matchup_heat = bm.get("momi", 50) >= 85 and bm.get("ms", 0) >= 60
        has_damage_context = (
            bm.get("run_contrib", 0) >= 0.65
            or bm.get("hr_rate", 0) >= 0.035
            or woba_bump >= 0.020
        )
        if momentum_delta > 0 and has_rhythm and has_matchup_heat and has_damage_context:
            density_score = max(
                hit5 if games5 >= 5 else 0,
                hit7 if games7 >= 7 else 0,
                hit10 * 0.7 if games10 >= 10 else 0,
            )
            heat_score = (
                momentum_delta
                + streak * 0.8
                + density_score
                + max(0, woba_bump) * 20
                + bm.get("run_contrib", 0) * 2.0
                + bm.get("hr_rate", 0) * 30
            )
            heating_candidates.append({
                **bm, "streak": streak, "last7_avg": last7,
                "hit_games_5": hit5, "games_5": games5,
                "hit_games_7": hit7, "games_7": games7,
                "hit_games_10": hit10, "games_10": games10,
                "woba_bump": woba_bump, "heat_score": heat_score
            })

    heating = sorted(heating_candidates, key=lambda x: -x["heat_score"])[:HR_HEAT_MAX_ROWS]

    heat_html = ""
    for i, bm in enumerate(heating):
        mc = ms_class(bm["ms"])
        streak_str = recent_hit_label(bm)
        avg_str = f'.{str(bm["last7_avg"])[2:]}' if bm["last7_avg"] > 0 else ""
        bump = bm["woba_bump"]
        bump_str = f'+.{str(abs(round(bump,3)))[2:]}' if bump > 0 else ""
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
    <div class="trend-meta">{streak_str} &middot; L7 {avg_str} &middot; MOMO {bm["ms"]} &middot; MOMI {bm.get("momi", 50)} &middot; {h(bm["team"])} vs {h(bm["opp_pitcher"])} ({h(bm["opp_team"])}){"" if not bump_str else " &middot; wOBA " + bump_str}</div>
  </div>
  <div class="trend-right">
    <div class="trend-ms {mc}">{bm["ms"]}</div>
  </div>
</div>'''

    games_by_matchup = {(g["away_abbr"], g["home_abbr"]): g for g in games}
    published_today = [
        p for p in load_published_mlb_picks()
        if p.get("sport") == "mlb" and p.get("date") == TODAY and p.get("bet_type") == "ml"
    ]
    rows = []
    seen = set()
    for p in published_today:
        key = (p.get("away"), p.get("home"), p.get("side"))
        g = games_by_matchup.get((p.get("away"), p.get("home")))
        seen.add(key)
        rows.append({
            "pick_text": p.get("pick_text") or f'{p.get("side", "")} ML',
            "matchup": p.get("matchup") or f'{p.get("away", "")} @ {p.get("home", "")}',
            "conf": int(p.get("conf") or (g.get("conf") if g else 0) or 0),
            "sort_conf": int(p.get("conf") or (g.get("conf") if g else 0) or 0),
            "sort_edge": float((g or {}).get("edge") or p.get("sim_edge") or 0),
        })

    edges = sorted(qualified_picks, key=lambda x: (-x["conf"], -x.get("edge", 0)))
    for g in edges:
        key = (g["away_abbr"], g["home_abbr"], g["pick_team"])
        if key in seen:
            continue
        rows.append({
            "pick_text": f'{g["pick_team"]} ML',
            "matchup": f'{g["away_abbr"]} @ {g["home_abbr"]}',
            "conf": g["conf"],
            "sort_conf": g["conf"],
            "sort_edge": g.get("edge", 0),
        })

    rows = sorted(rows, key=lambda x: (-x["sort_conf"], -x["sort_edge"]))[:12]
    edges_html = ""
    for i, row in enumerate(rows):
        cc = conf_color(row["conf"])
        prem = ' ma-premium' if row["conf"] >= 8 else ''
        edges_html += f'''<div class="pick-row{prem}">
  <div class="pick-rank">{i+1}</div>
  <div class="pick-info">
    <div class="pick-label gp-pick-strong">{h(row["pick_text"])} <span class="mc-conf-num" style="color:{cc}">C:{row["conf"]}</span></div>
    <div class="pick-matchup">{h(row["matchup"])}</div>
  </div>
</div>'''

    games_with_lu = sum(1 for g in games if g["has_lineups"])
    no_data = '<div class="empty-state">UPDATES WHEN LINEUPS ARE RELEASED</div>' if not (hr_html or longshot_html or heat_html) else ''
    hr_empty = '<div class="empty-state">NO TIER 1 HR % EDGES</div>' if not hr_html else ''
    locked_hr_column = load_locked_hr_lotto_column()
    def criteria_row(*items):
        return '<div class="criteria-row">' + ' '.join(f'<span>{h(item)}</span>' for item in items) + '</div>'

    def bucket_header(kind, kicker, title, copy, *criteria):
        return f'''<div class="bucket-head {kind}">
                    <div class="edge-kicker {kind}">{h(kicker)}</div>
                    <div class="bucket-title">{h(title)}</div>
                    <div class="bucket-copy">{h(copy)}</div>
                    {criteria_row(*criteria)}
                </div>'''

    hr_deep_board_html = render_hr_deep_board(hr_card_table_rows, core_ids, watch_ids)
    longshot_block = f'''<div class="daily-bucket daily-subsection secondary hr-lotto-secondary">
                    {bucket_header("secondary", "WATCH", "GO-YARD WATCH", "Secondary fits where the HR signal is live, with the same projected HR%, pitcher-type lift, and lineup/run readout.", "6.5%+ HR", "power baseline", "matchup lift", "context")}
                    <div class="picks-container">{longshot_html or '<div class="empty-state">NO QUALIFIERS</div>'}</div>
                </div>'''
    heat_empty = '<div class="empty-state">NO HEAT QUALIFIERS</div>' if not heat_html else ''
    hr_column = locked_hr_column or f'''<div class="daily-col daily-center daily-hr-lotto">
                <div class="daily-bucket primary hr-lotto">
                    {bucket_header("primary", "TOP BOARD", "GO-YARD CARD", "Highest-probability HR shortlist with projected HR%, batter HR baseline, pitcher-type lift, and lineup/run setup shown on every bat.", "projected HR%", "power baseline", "matchup lift", "context")}
                    <div class="picks-container">{hr_html or hr_empty}</div>
                </div>
                {longshot_block}
            </div>'''

    return f'''<div class="tab-content" id="tab-daily">
        <div class="daily-hero-line">
            <div class="section-title">GO-YARD BOARD</div>
            <div class="section-sub">{DATE_SHORT} \u00b7 {games_with_lu} games with lineups</div>
        </div>
        {no_data}
        <div class="daily-grid daily-grid-lotto">
            {hr_column}
            <div class="daily-side-stack">
                <div class="daily-col daily-side daily-board-side">
                    <div class="daily-bucket board">
                        {bucket_header("picks", "BOARD", "TODAY'S PICKS", "Official moneyline board, separate from HR edges.", "C:8+ board", "ROI price gates", "posted picks persist")}
                        <div class="picks-container ma-premium">{edges_html}</div>
                    </div>
                </div>
                <div class="daily-col daily-side daily-hot-side">
                    <div class="daily-bucket momentum">
                        {bucket_header("momentum", "MOMENTUM", "HOT BATS", "Recent timing plus matchup support.", "5G+ streak or 4/5 hits", "MOMI 85+", "MOMO 60+")}
                        <div class="picks-container">{heat_html or heat_empty}</div>
                    </div>
                </div>
            </div>
        </div>
        {hr_deep_board_html}
    </div>'''


# ─── Assemble full page ──────────────────────────────────────────────────────
qualified_picks = sorted(
    [g for g in games if qualifies_as_pick(g)],
    key=lambda x: (-x["conf"], -x.get("edge", 0)),
)
game_cards = "".join(render_game(g, i) for i, g in enumerate(games))
gen_time = NOW.strftime("%Y-%m-%d %H:%M ET")

CSS = open(os.path.join(REPO_ROOT, "mlbsim", "index.html")).read()
# Extract just the CSS block (everything between <style> and </style>)
css_start = CSS.find("<style>")
css_end = CSS.find("</style>") + len("</style>")
css_block = CSS[css_start:css_end] if css_start >= 0 else ""
css_block = re.sub(
    r"\n/\* (DAILY_HR_GOYARD_HIERARCHY|GO_YARD_PUBLIC_COPY_FIX|GO_YARD_HR_EXPLAINER)_V\d+ \*/.*?(?=\n/\* [A-Z0-9_]+|\n</style>)",
    "",
    css_block,
    flags=re.S,
)

DAILY_CSS = """
/* ═══ DAILY 3-COL GRID ═══ */
#tab-daily{position:relative;left:50%;transform:translateX(-50%);width:96vw;max-width:1300px;padding:0 24px;box-sizing:border-box}
.daily-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-top:12px}
@media(max-width:900px){.daily-grid{grid-template-columns:1fr}#tab-daily{width:100%;left:0;transform:none;padding:0}}
.daily-col .section-title{font-size:14px;margin-bottom:4px}
.daily-col .section-sub{font-size:10px;margin-bottom:8px}
.hr-row{display:flex;align-items:center;gap:10px;padding:10px 12px;min-height:56px;border-bottom:1px solid #eee}
.hr-row:last-child{border-bottom:none}
.hr-rank{font-family:var(--font-mono);font-size:12px;font-weight:800;color:#111;min-width:28px;height:28px;border:2px solid #111;display:flex;align-items:center;justify-content:center;background:#fff}
.hr-info{flex:1;min-width:0}
.hr-name{font-weight:700;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hr-meta{font-size:10px;color:var(--color-meta);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}
.hr-tags{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}
.hr-tags span{font-family:var(--font-mono);font-size:8px;font-weight:800;line-height:1;border:1px solid #111;background:#f6f6f2;color:#111;padding:4px 5px;text-transform:uppercase;white-space:nowrap}
.hr-fire .hr-tags span:first-child{background:#FF3333;color:#fff}
.hr-hot .hr-tags span:first-child{background:#00A651;color:#fff}
.hr-warm .hr-tags span:first-child{background:#FFEA00;color:#111}
.hr-rate-col{text-align:right;min-width:50px}
.hr-rate{font-family:var(--font-mono);font-weight:800;font-size:14px;color:var(--color-elite)}
.hr-rate-label{font-size:8px;color:var(--color-meta);text-transform:uppercase;letter-spacing:0.5px}
.hr-fire .hr-rate{color:#FF3333}
.hr-hot .hr-rate{color:var(--color-elite)}
.hr-warm .hr-rate{color:var(--color-neutral)}
.hr-mild .hr-rate{color:var(--color-meta)}
"""
if "tab-daily" not in css_block:
    css_block = css_block.replace("</style>", DAILY_CSS + "\n</style>")

DAILY_REFINEMENT_CSS = """
/* DAILY_HR_HIERARCHY_V2 */
#tab-daily .daily-grid{grid-template-columns:minmax(340px,1.05fr) minmax(430px,1.35fr) minmax(220px,.65fr);align-items:start;gap:18px}
#tab-daily .daily-col{min-width:0}
.daily-bucket{background:#f8f8f5;border:2px solid #111;box-shadow:4px 4px 0 #111;margin-bottom:18px;overflow:hidden}
.daily-bucket.primary{border-top:6px solid #FF3333}
.daily-bucket.secondary{border-top:5px solid #111;box-shadow:3px 3px 0 #111}
.daily-bucket.momentum{border-top:6px solid #00A651}
.daily-bucket.board{border-top:6px solid #FFEA00}
.daily-bucket .picks-container{margin:0;border:0;box-shadow:none;background:#fff}
.daily-subsection{margin-top:16px}
.bucket-head{padding:12px 14px 10px;border-bottom:2px solid #111;background:#f2f2ee}
.bucket-head.primary{background:#fff1f1}
.bucket-head.secondary{background:#f1f1ee}
.bucket-head.momentum{background:#effaf2}
.bucket-head.picks{background:#fffbe0}
.edge-kicker{display:inline-flex;align-items:center;width:max-content;margin-bottom:7px;padding:3px 7px;border:1px solid #111;border-radius:2px;background:#111;color:#fff;font-family:var(--font-mono);font-size:8px;font-weight:900;letter-spacing:0.8px;text-transform:uppercase;line-height:1}
.edge-kicker.primary{background:#FF3333;border-color:#111;color:#fff}
.edge-kicker.secondary{background:#111;border-color:#111;color:#fff}
.edge-kicker.momentum{background:#00A651;border-color:#111;color:#fff}
.edge-kicker.picks{background:#FFEA00;border-color:#111;color:#111}
.bucket-title{font-family:var(--font-display);font-size:20px;line-height:1;letter-spacing:1.4px;text-transform:uppercase;color:#050505}
.bucket-copy{margin-top:5px;font-size:11px;line-height:1.35;color:#333;max-width:44ch}
.criteria-row{display:flex;flex-wrap:wrap;gap:6px;margin:9px 0 0}
.criteria-row span{display:inline-flex;align-items:center;min-height:20px;padding:3px 7px;border:1px solid #111;border-radius:2px;background:#fff;font-family:var(--font-mono);font-size:8px;font-weight:900;color:#111;letter-spacing:0;text-transform:uppercase;line-height:1;box-shadow:1px 1px 0 rgba(0,0,0,.2)}
.daily-bucket.board .criteria-row span{background:#FFEA00}
.daily-bucket .hr-row,.daily-bucket .trend-row,.daily-bucket .pick-row{background:#fff}
@media(max-width:1100px){#tab-daily .daily-grid{grid-template-columns:1fr 1fr}.daily-col:last-child{grid-column:1/-1}}
@media(max-width:760px){#tab-daily .daily-grid{grid-template-columns:1fr}.daily-col:last-child{grid-column:auto}.bucket-title{font-size:18px}}
"""
if "DAILY_HR_HIERARCHY_V2" not in css_block:
    css_block = css_block.replace("</style>", DAILY_REFINEMENT_CSS + "\n</style>")

DAILY_LOTTO_CSS = """
/* DAILY_HR_LOTTO_LAYOUT_V3 */
#tab-daily .daily-grid-lotto{grid-template-columns:minmax(240px,.72fr) minmax(520px,1.65fr) minmax(250px,.78fr);align-items:start;gap:20px}
#tab-daily .daily-hr-lotto{order:2}
#tab-daily .daily-hot-side{order:1}
#tab-daily .daily-board-side{order:3}
.daily-bucket.hr-lotto{border:3px solid #111;border-top:10px solid #FF3333;box-shadow:8px 8px 0 #111;background:#fff;transform:translateY(-6px)}
.daily-bucket.hr-lotto .bucket-head{padding:16px 18px 14px;background:linear-gradient(135deg,#fff1f1 0%,#fff 72%)}
.daily-bucket.hr-lotto .edge-kicker{font-size:10px;padding:5px 9px;box-shadow:2px 2px 0 #111}
.daily-bucket.hr-lotto .bucket-title{font-size:34px;letter-spacing:2px;color:#FF3333;text-shadow:2px 2px 0 #111}
.daily-bucket.hr-lotto .bucket-copy{font-size:12px;max-width:58ch;color:#111}
.daily-bucket.hr-lotto .criteria-row span{background:#FF3333;color:#fff}
.daily-bucket.hr-lotto .hr-row{min-height:82px;padding:12px 14px}
.daily-bucket.hr-lotto .hr-rank{font-size:14px;color:#111}
.daily-bucket.hr-lotto .hr-name{font-size:15px}
.daily-bucket.hr-lotto .hr-rate{font-size:18px}
.daily-bucket.hr-lotto .hr-rate-label{font-size:9px}
.daily-bucket.hr-lotto-secondary{box-shadow:5px 5px 0 #111;border-top:6px solid #FF3333}
.daily-side .bucket-title{font-size:17px}
.daily-side .bucket-copy{font-size:10px}
.daily-side .criteria-row span{font-size:7px}
.daily-hot-side .trend-row{min-height:54px;padding:9px 10px}
.daily-hot-side .trend-meta{white-space:normal;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
@media(max-width:1100px){#tab-daily .daily-grid-lotto{grid-template-columns:1.35fr .9fr}#tab-daily .daily-hr-lotto{order:1}#tab-daily .daily-board-side{order:2;grid-column:auto}#tab-daily .daily-hot-side{order:3;grid-column:1/-1}.daily-bucket.hr-lotto{transform:none}}
@media(max-width:760px){#tab-daily .daily-grid-lotto{grid-template-columns:1fr}#tab-daily .daily-hr-lotto{order:1}#tab-daily .daily-board-side{order:2;grid-column:auto}#tab-daily .daily-hot-side{order:3;grid-column:auto}.daily-bucket.hr-lotto .bucket-title{font-size:28px}.daily-bucket.hr-lotto .hr-row{min-height:76px}.hr-rate-col{min-width:44px}.hr-tags span{font-size:7px;padding:3px 4px}}
"""
if "DAILY_HR_LOTTO_LAYOUT_V3" not in css_block:
    css_block = css_block.replace("</style>", DAILY_LOTTO_CSS + "\n</style>")

DAILY_HR_ADVANCED_CSS = """
/* DAILY_HR_ADVANCED_DATA_V1 */
.hr-intel-strip{margin:12px 0 20px;background:#fff;border:2px solid #111;box-shadow:5px 5px 0 #111;overflow:hidden}
.hr-intel-head{display:grid;grid-template-columns:minmax(190px,.5fr) minmax(260px,1fr);gap:16px;align-items:end;padding:14px 16px;background:#fff7d6;border-bottom:2px solid #111}
.hr-intel-copy{font-size:12px;line-height:1.4;color:#222;max-width:80ch}
.hr-intel-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));background:#fff}
.hr-intel-cell{min-width:0;padding:12px 14px;border-right:1px solid #ddd}
.hr-intel-cell:last-child{border-right:0}
.hr-intel-cell span{display:block;font-family:var(--font-mono);font-size:8px;font-weight:900;letter-spacing:.5px;text-transform:uppercase;color:#777}
.hr-intel-cell strong{display:block;margin-top:4px;font-family:var(--font-display);font-size:20px;line-height:1.05;letter-spacing:.7px;text-transform:uppercase;color:#111;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hr-intel-cell em{display:block;margin-top:5px;font-family:var(--font-mono);font-size:9px;font-style:normal;color:#555;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hr-title-line{display:flex;align-items:center;gap:8px;min-width:0}
.hr-title-line .hr-name{flex:1}
.hr-lane-pill{flex:0 0 auto;border:1px solid #111;background:#111;color:#fff;padding:3px 6px;font-family:var(--font-mono);font-size:8px;font-weight:900;line-height:1;text-transform:uppercase}
.hr-signal{margin-top:5px;font-size:10px;line-height:1.35;color:#222;max-width:78ch}
.hr-metric-grid{display:none!important}
.hr-metric{min-width:0;border:1px solid #d7d7d0;background:#fbfbf7;padding:5px 6px}
.hr-metric span{display:block;font-family:var(--font-mono);font-size:7px;font-weight:900;letter-spacing:.4px;text-transform:uppercase;color:#777;line-height:1}
.hr-metric strong{display:block;margin-top:3px;font-family:var(--font-mono);font-size:12px;font-weight:900;color:#111;line-height:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hr-metric.tone-red{background:#fff1f1;border-color:#111}
.hr-proof-row{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:8px}
.hr-proof{min-width:0;border:2px solid #111;background:#fff;padding:6px 7px}
.hr-proof span{display:block;font-family:var(--font-mono);font-size:8px;font-weight:900;line-height:1;text-transform:uppercase;color:#666}
.hr-proof strong{display:block;margin-top:4px;font-family:var(--font-display);font-size:18px;line-height:.95;color:#111;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hr-proof.tone-red{background:#111;color:#fff}
.hr-proof.tone-red span{color:#d8d8d0}
.hr-proof.tone-red strong{color:#FFEA00}
.daily-bucket.hr-lotto .hr-row{align-items:flex-start}
.daily-bucket.hr-lotto-secondary .hr-row{align-items:flex-start}
.daily-bucket.hr-lotto .hr-info,.daily-bucket.hr-lotto-secondary .hr-info{min-width:0}
.daily-bucket.hr-lotto .hr-rate-col{min-width:76px;padding-top:2px}
.daily-bucket.hr-lotto-secondary .hr-rate-col{min-width:64px;padding-top:2px}
.hr-deep-board{margin:20px 0 22px;border-top:6px solid #111}
.hr-board-scroll{overflow-x:auto;background:#fff}
.hr-board-table{width:100%;min-width:900px;border-collapse:collapse;font-family:var(--font-mono)}
.hr-board-table th{position:sticky;top:0;background:#111;color:#fff;padding:9px 8px;border-right:1px solid #333;font-size:8px;font-weight:900;letter-spacing:.6px;text-align:left;text-transform:uppercase;z-index:1}
.hr-board-table td{padding:9px 8px;border-top:1px solid #e8e8e2;border-right:1px solid #efefea;font-size:10px;font-weight:800;color:#111;vertical-align:middle;white-space:nowrap}
.hr-board-table td:last-child,.hr-board-table th:last-child{border-right:0}
.hr-board-row.lotto td{background:#fff1f1}
.hr-board-row.watch td{background:#fffdf0}
.hr-col-rank{width:38px;text-align:center;color:#777}
.hr-col-hitter strong{display:block;font-family:var(--font-body);font-size:12px;line-height:1.1}
.hr-col-hitter span,.hr-col-match span{display:block;margin-top:3px;font-size:8px;color:#777;text-transform:uppercase}
.hr-board-lane{display:inline-flex;align-items:center;border:1px solid #111;background:#fff;padding:3px 6px;font-size:8px;font-weight:900;line-height:1}
.hr-status-pill{display:inline-flex;align-items:center;border:1px solid #111;padding:4px 6px;font-size:8px;font-weight:900;line-height:1;text-transform:uppercase;white-space:nowrap;background:#fff;color:#111}
.hr-status-pill.status-lotto{background:#FF3333;color:#fff}
.hr-status-pill.status-watch{background:#FFEA00;color:#111}
.hr-status-pill.status-model{background:#111;color:#FFEA00}
@media(max-width:980px){.hr-intel-head{grid-template-columns:1fr}.hr-intel-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.hr-intel-cell:nth-child(2){border-right:0}.hr-intel-cell:nth-child(n+3){border-top:1px solid #ddd}.hr-proof-row{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:760px){.hr-intel-strip{box-shadow:3px 3px 0 #111}.hr-intel-grid{grid-template-columns:1fr}.hr-intel-cell{border-right:0;border-top:1px solid #ddd}.hr-intel-cell:first-child{border-top:0}.hr-intel-cell strong{font-size:18px}.daily-bucket.hr-lotto .hr-row,.daily-bucket.hr-lotto-secondary .hr-row{display:grid;grid-template-columns:32px minmax(0,1fr);gap:9px}.daily-bucket.hr-lotto .hr-rate-col,.daily-bucket.hr-lotto-secondary .hr-rate-col{grid-column:2;display:flex;align-items:baseline;gap:6px;justify-content:flex-start;min-width:0;text-align:left;padding-top:0}.hr-proof-row{grid-template-columns:repeat(3,minmax(0,1fr))}.hr-col-sur,.hr-col-stack,.hr-col-park,.hr-col-total,.hr-col-h2h{display:none}.hr-board-table{min-width:560px}}
"""
if "DAILY_HR_ADVANCED_DATA_V1" not in css_block:
    css_block = css_block.replace("</style>", DAILY_HR_ADVANCED_CSS + "\n</style>")

DAILY_HR_FUN_NAV_CSS = """
/* DAILY_HR_FUN_NAV_V1 */
.hr-control-deck{margin:0 0 20px;background:#f8f8f5;border:2px solid #111;box-shadow:4px 4px 0 #111;overflow:hidden}
.hr-control-head{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:12px 14px;background:#fff;border-bottom:2px solid #111}
.hr-jump-rail{display:flex;align-items:center;gap:7px;flex-wrap:wrap;justify-content:flex-end}
.hr-jump-rail button,.hr-lens{appearance:none;border:2px solid #111;background:#fff;color:#111;font-family:var(--font-mono);font-weight:900;text-transform:uppercase;cursor:pointer;transition:transform .12s ease,box-shadow .12s ease,background .12s ease,color .12s ease}
.hr-jump-rail button{min-height:32px;padding:7px 10px;font-size:9px;box-shadow:2px 2px 0 #111}
.hr-jump-rail button:hover,.hr-lens:hover{transform:translate(-1px,-1px);box-shadow:3px 3px 0 #111}
.hr-lens-rail{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:8px;padding:10px;background:#fffdf0}
.hr-lens{min-height:54px;padding:9px 10px;text-align:left;box-shadow:2px 2px 0 rgba(0,0,0,.35)}
.hr-lens span{display:block;font-size:9px;line-height:1.1;letter-spacing:0;white-space:normal}
.hr-lens strong{display:block;margin-top:5px;font-family:var(--font-display);font-size:22px;line-height:1;letter-spacing:.7px}
.hr-lens.active{background:#111;color:#fff;box-shadow:3px 3px 0 #FFEA00;transform:translate(-1px,-1px)}
.hr-lens.is-empty{opacity:.58;background:#f6f6f2}
.hr-lens.is-empty.active{opacity:1;background:#111;color:#fff}
.hr-filter-empty{padding:16px;text-align:center;border-top:1px solid #ddd;background:#fff;font-family:var(--font-mono);font-size:10px;font-weight:900;text-transform:uppercase;color:#777}
.hr-filtered{display:none!important}
.lane-power{background:#FF3333!important;color:#fff!important}
.lane-boost{background:#00A651!important;color:#fff!important}
.lane-lineup{background:#FFEA00!important;color:#111!important}
.lane-heater{background:#111!important;color:#FFEA00!important}
.lane-order{background:#006CFF!important;color:#fff!important}
.lane-history{background:#fff!important;color:#111!important}
.lane-model{background:#f6f6f2!important;color:#111!important}
.hr-lens.lane-power.active{box-shadow:3px 3px 0 #111;background:#FF3333;color:#fff}
.hr-lens.lane-boost.active{box-shadow:3px 3px 0 #111;background:#00A651;color:#fff}
.hr-lens.lane-lineup.active{box-shadow:3px 3px 0 #111;background:#FFEA00;color:#111}
.hr-lens.lane-heater.active{box-shadow:3px 3px 0 #FFEA00;background:#111;color:#FFEA00}
.hr-lens.lane-order.active{box-shadow:3px 3px 0 #111;background:#006CFF;color:#fff}
.hr-lens.lane-history.active{box-shadow:3px 3px 0 #111;background:#fff;color:#111}
.hr-board-lane{max-width:128px;white-space:normal}
@media(max-width:760px){.hr-control-head{align-items:flex-start;flex-direction:column}.hr-jump-rail{justify-content:flex-start}.hr-lens-rail{grid-template-columns:repeat(2,minmax(0,1fr))}.hr-lens{min-height:50px;padding:8px}.hr-lens strong{font-size:19px}}
@media(max-width:390px){.hr-lens-rail{grid-template-columns:1fr}.hr-jump-rail button{flex:1}}
"""
if "DAILY_HR_FUN_NAV_V1" not in css_block:
    css_block = css_block.replace("</style>", DAILY_HR_FUN_NAV_CSS + "\n</style>")

DAILY_HR_RESULTS_TRAY_CSS = """
/* DAILY_HR_RESULTS_TRAY_V1 */
.hr-results-panel{margin:-8px 0 22px;background:#fff;border:2px solid #111;box-shadow:4px 4px 0 #111;overflow:hidden}
.hr-results-head{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:12px 14px;background:#111;color:#fff;border-bottom:2px solid #111}
.hr-results-head .bucket-title{color:#fff}
.hr-results-copy{max-width:420px;font-size:10px;line-height:1.35;font-weight:800;color:#f3f3eb;text-align:right}
.hr-results-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(228px,1fr));gap:8px;padding:10px;background:#f8f8f5}
.hr-result-card{min-width:0;border:2px solid #111;background:#fff!important;color:#111!important;padding:10px;box-shadow:2px 2px 0 rgba(0,0,0,.28)}
.hr-result-card.lotto{background:#fff1f1!important}
.hr-result-card.watch{background:#fffdf0!important}
.hr-result-card.lane-power{border-top:8px solid #FF3333;background:#fff7f7!important;color:#111!important}
.hr-result-card.lane-boost{border-top:8px solid #00A651;background:#f4fff8!important;color:#111!important}
.hr-result-card.lane-lineup{border-top:8px solid #FFEA00;background:#fffdf0!important;color:#111!important}
.hr-result-card.lane-heater{border-top:8px solid #111;background:#fffef2!important;color:#111!important}
.hr-result-card.lane-order{border-top:8px solid #006CFF;background:#f5f9ff!important;color:#111!important}
.hr-result-card.lane-history{border-top:8px solid #111;background:#fff!important;color:#111!important}
.hr-result-card.lane-model{border-top:8px solid #b9b9af;background:#fff!important;color:#111!important}
.hr-result-top{display:flex;align-items:center;justify-content:space-between;gap:8px;font-family:var(--font-mono);font-size:9px;font-weight:900;letter-spacing:.3px;text-transform:uppercase}
.hr-result-top strong{display:inline-flex;align-items:center;min-height:20px;border:1px solid #111;background:#fff;padding:3px 6px;font-size:8px;line-height:1}
.hr-result-name{margin-top:8px;font-family:var(--font-display);font-size:21px;font-weight:900;line-height:.95;letter-spacing:0;overflow-wrap:anywhere}
.hr-result-meta{margin-top:7px;font-size:10px;font-weight:800;line-height:1.25;color:#555;overflow-wrap:anywhere}
.hr-result-band{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:10px}
.hr-result-band strong{font-family:var(--font-display);font-size:24px;line-height:1;color:#111;white-space:nowrap}
.hr-result-stat-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:9px}
.hr-result-stat-grid div{min-width:0;border:1px solid #d7d7d0;background:rgba(255,255,255,.82);padding:5px 6px}
.hr-result-stat-grid span{display:block;font-family:var(--font-mono);font-size:7px;font-weight:900;line-height:1;text-transform:uppercase;color:#777}
.hr-result-stat-grid strong{display:block;margin-top:3px;font-family:var(--font-mono);font-size:12px;font-weight:900;line-height:1;color:#111;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@media(max-width:760px){.hr-results-panel{margin:-6px 0 18px;box-shadow:3px 3px 0 #111}.hr-results-head{align-items:flex-start;flex-direction:column}.hr-results-copy{text-align:left;max-width:none}.hr-results-grid{grid-template-columns:1fr}.hr-result-name{font-size:19px}.hr-result-band strong{font-size:22px}}
"""
if "DAILY_HR_RESULTS_TRAY_V1" not in css_block:
    css_block = css_block.replace("</style>", DAILY_HR_RESULTS_TRAY_CSS + "\n</style>")

DAILY_HR_GOYARD_CSS = """
/* DAILY_HR_GOYARD_HIERARCHY_V6 */
#tab-daily{max-width:1360px}
#tab-daily.active{display:flex;flex-direction:column}
#tab-daily>.daily-hero-line{order:1}
#tab-daily>.empty-state{order:2}
#tab-daily>.hr-intel-strip{display:none}
#tab-daily>.daily-grid-lotto{order:3}
#tab-daily>.hr-control-deck{order:5}
#tab-daily>.hr-results-panel{order:6}
#tab-daily>.hr-deep-board{order:7}
.daily-hero-line{padding-top:10px;margin-bottom:12px;display:flex;align-items:flex-end;justify-content:space-between;gap:12px}
.hr-intel-strip{margin:14px 0 18px;border:3px solid #111;box-shadow:6px 6px 0 #111}
.hr-intel-head{grid-template-columns:minmax(260px,.48fr) minmax(320px,1fr);align-items:center;background:#111;color:#fff;padding:16px 18px}
.hr-intel-head .edge-kicker{background:#FFEA00;color:#111;border-color:#FFEA00;box-shadow:none}
.hr-intel-head .bucket-title{color:#fff;font-size:31px;letter-spacing:1.6px}
.hr-intel-copy{color:#f4f4ea;font-weight:800;font-size:12px;line-height:1.45}
.hr-intel-grid{grid-template-columns:1.05fr 1.05fr .8fr 1.5fr;border-top:3px solid #111}
.hr-intel-cell{padding:14px 15px;border-right:2px solid #111}
.hr-intel-cell:nth-child(1){background:#fff1f1}
.hr-intel-cell:nth-child(2){background:#fff7d6}
.hr-intel-cell:nth-child(3){background:#f4fff8}
.hr-intel-cell:nth-child(4){background:#fff}
.hr-intel-cell strong{font-size:22px;line-height:1.05;white-space:normal;overflow:visible;text-overflow:clip}
.hr-intel-cell em{white-space:normal;line-height:1.25}
#tab-daily .daily-grid-lotto{grid-template-columns:minmax(650px,1fr) minmax(290px,340px);gap:18px;margin-top:8px;align-items:start}
#tab-daily .daily-hr-lotto{order:1;min-width:0}
.daily-side-stack{order:2;display:grid;gap:14px;align-content:start;min-width:0}
.daily-side-stack .daily-col{min-width:0}
.daily-side-stack .daily-bucket{margin:0}
#tab-daily .daily-board-side,#tab-daily .daily-hot-side{order:initial;grid-column:auto}
.daily-bucket.hr-lotto{transform:none;border:3px solid #111;border-top:12px solid #FF3333;box-shadow:6px 6px 0 #111}
.daily-bucket.hr-lotto .bucket-head{background:#fff;padding:17px 18px 15px;border-bottom:3px solid #111}
.daily-bucket.hr-lotto .edge-kicker{background:#111;color:#FFEA00;border-color:#111;font-size:10px;box-shadow:none}
.daily-bucket.hr-lotto .bucket-title{font-size:32px;color:#111;text-shadow:none;letter-spacing:1.6px}
.daily-bucket.hr-lotto .bucket-copy{font-size:12px;font-weight:800;color:#242424;max-width:64ch}
.daily-bucket.hr-lotto .criteria-row span{background:#FF3333;color:#fff;box-shadow:none}
.daily-bucket.hr-lotto .hr-row{display:grid;grid-template-columns:38px minmax(0,1fr) 84px;align-items:start;gap:12px;min-height:0;padding:13px 16px;border-bottom:2px solid #ecece4}
.daily-bucket.hr-lotto .hr-row:first-child{background:#fff7d6}
.daily-bucket.hr-lotto .hr-rank{min-width:38px;width:38px;height:34px;background:#111;color:#FFEA00;font-size:15px}
.daily-bucket.hr-lotto .hr-name{font-size:18px}
.daily-bucket.hr-lotto .hr-rate-col{min-width:0;text-align:left;border-left:2px solid #111;padding:2px 0 0 10px}
.daily-bucket.hr-lotto .hr-rate{font-size:24px;line-height:1;color:#FF3333}
.daily-bucket.hr-lotto .hr-rate-label{font-size:8px;font-weight:900;color:#555}
.hr-odds{margin-top:9px;min-width:0}
.hr-odds-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:5px;font-family:var(--font-mono);font-weight:900;text-transform:uppercase}
.hr-odds-head span{font-size:8px;color:#555;letter-spacing:.4px}
.hr-odds-head strong{font-size:11px;line-height:1;color:#FF3333;white-space:nowrap}
.hr-odds-bar{position:relative;height:14px;border:2px solid #111;background:#f1f1ea;box-shadow:2px 2px 0 rgba(0,0,0,.18);overflow:hidden}
.hr-bar-base,.hr-bar-boost{position:absolute;top:0;bottom:0;display:block;transform:scaleX(0);transform-origin:left;animation:hrBarReveal .72s cubic-bezier(.2,.8,.2,1) forwards}
.hr-bar-base{left:0;width:var(--base-w);background:#111}
.hr-bar-boost{left:var(--base-w);width:var(--boost-w);background:#FF3333;animation-delay:.08s}
.hr-bar-end{position:absolute;top:-2px;bottom:-2px;left:var(--total-w);width:3px;background:#FFEA00;border-left:1px solid #111;border-right:1px solid #111;box-shadow:0 0 0 1px rgba(0,0,0,.08)}
.hr-odds-scale{display:flex;justify-content:space-between;margin-top:4px;font-family:var(--font-mono);font-size:7px;font-weight:900;line-height:1;text-transform:uppercase;color:#777}
.hr-explain-row{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:8px}
.hr-explain{min-width:0;border:1px solid #cfcfc8;background:#fff;padding:6px 7px}
.hr-explain span{display:block;font-family:var(--font-mono);font-size:7px;font-weight:900;line-height:1;text-transform:uppercase;color:#666;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hr-explain strong{display:block;margin-top:4px;font-family:var(--font-display);font-size:17px;line-height:.95;color:#111;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hr-explain em{display:block;margin-top:4px;font-family:var(--font-mono);font-size:7px;font-style:normal;font-weight:800;line-height:1.05;color:#777;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@keyframes hrBarReveal{to{transform:scaleX(1)}}
.daily-bucket.hr-lotto-secondary{border-top:7px solid #111;box-shadow:4px 4px 0 #111}
.daily-bucket.hr-lotto-secondary .bucket-title{font-size:23px}
.daily-bucket.hr-lotto-secondary .hr-row{display:grid;grid-template-columns:34px minmax(0,1fr) 68px;align-items:start;gap:10px;min-height:0;padding:12px 14px}
.daily-bucket.hr-lotto-secondary .hr-rank{min-width:34px;width:34px;height:30px}
.daily-bucket.hr-lotto-secondary .hr-rate-col{min-width:0;text-align:left;border-left:1px solid #d9d9d0;padding-left:8px}
.daily-bucket.hr-lotto .hr-name,.daily-bucket.hr-lotto-secondary .hr-name{white-space:normal;overflow:visible;text-overflow:clip;line-height:1.1}
.daily-bucket.hr-lotto .hr-meta,.daily-bucket.hr-lotto-secondary .hr-meta{white-space:normal;line-height:1.35}
.hr-title-line{align-items:flex-start;flex-wrap:wrap;gap:6px 8px}
.hr-lane-pill{margin-top:1px}
.hr-signal{font-weight:800;color:#222}
.hr-control-deck{display:none;margin:22px 0 16px;border:3px solid #111;box-shadow:5px 5px 0 #111}
.hr-control-head{background:#fff;padding:13px 15px}
.hr-lens-rail{background:#f8f8f5}
.hr-lens{min-height:58px}
.hr-results-panel{display:none;margin:0 0 20px;border:3px solid #111;box-shadow:5px 5px 0 #111}
.hr-results-grid{grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:9px}
.hr-results-grid .hr-result-card:nth-of-type(n+13){display:none}
.hr-result-card{box-shadow:none}
.hr-deep-board{margin-top:20px;border-top:8px solid #111}
.hr-board-table th{font-size:9px}
.hr-board-table td{font-size:11px}
@media(max-width:1100px){#tab-daily .daily-grid-lotto{grid-template-columns:minmax(0,1fr) minmax(250px,.42fr)}#tab-daily .daily-hr-lotto{order:1}.daily-side-stack{order:2}.daily-bucket.hr-lotto .hr-row{grid-template-columns:36px minmax(0,1fr) 78px}.hr-explain-row{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){#tab-daily{padding:0 10px}.daily-hero-line{padding-top:6px;margin-bottom:10px;display:block}#tab-daily .daily-grid-lotto{grid-template-columns:1fr}.daily-side-stack{order:2}.daily-bucket.hr-lotto .bucket-title{font-size:28px}.daily-bucket.hr-lotto .hr-row,.daily-bucket.hr-lotto-secondary .hr-row{grid-template-columns:34px minmax(0,1fr);gap:10px}.daily-bucket.hr-lotto .hr-rate-col,.daily-bucket.hr-lotto-secondary .hr-rate-col{grid-column:2;border-left:0;padding:0;display:flex;align-items:baseline;gap:8px;justify-content:flex-start}.daily-bucket.hr-lotto .hr-rate{font-size:22px}.hr-explain-row{grid-template-columns:repeat(2,minmax(0,1fr))}.hr-explain strong{font-size:16px}.hr-control-head{align-items:flex-start;flex-direction:column}.hr-jump-rail{justify-content:flex-start}.hr-results-grid{grid-template-columns:1fr}.hr-board-table{min-width:620px}}
@media(max-width:760px) and (min-width:431px){.daily-bucket.hr-lotto .hr-row,.daily-bucket.hr-lotto-secondary .hr-row{grid-template-columns:34px minmax(0,1fr) 72px}.daily-bucket.hr-lotto .hr-rate-col,.daily-bucket.hr-lotto-secondary .hr-rate-col{grid-column:3;grid-row:1;display:block;text-align:right}.daily-bucket.hr-lotto .hr-rate-label,.daily-bucket.hr-lotto-secondary .hr-rate-label{font-size:7px}}
"""
css_block = css_block.replace("</style>", DAILY_HR_GOYARD_CSS + "\n</style>")

PLAYER_METRIC_CSS = """
/* ── Player MOMO/MOMI chips ── */
.lineup-col{min-width:0;overflow:hidden}
.batter-top{display:grid;grid-template-columns:16px minmax(0,1fr);align-items:center;column-gap:6px;justify-content:normal}
.batter-order{margin-right:0}
.batter-name{min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.batter-bottom{display:grid;grid-template-columns:16px minmax(0,1fr) auto;align-items:center;column-gap:6px;margin-top:5px}
.batter-detail{grid-column:2;display:flex;align-items:center;gap:5px;min-width:0;overflow:hidden;white-space:nowrap}
.batter-stats{white-space:nowrap}
.batter-pa{font-family:var(--font-mono);font-size:10px;font-weight:700;color:#aaa;white-space:nowrap}
.batter-range{white-space:nowrap;font-size:10px}
.batter-metrics{grid-column:3;display:flex;align-items:center;justify-content:flex-end;justify-self:end;gap:4px;min-width:max-content}
.batter-metric{display:flex;align-items:baseline;justify-content:center;gap:3px;min-width:43px;font-family:var(--font-mono);font-size:11px;font-weight:900;line-height:1;padding:4px 5px;border:1px solid rgba(0,0,0,0.14);border-radius:5px;background:rgba(0,0,0,0.04)}
.batter-metric span{font-size:7px;font-weight:900;color:var(--color-meta);letter-spacing:0}
.batter-woba{padding-left:0}
.woba-base,.woba-vs{display:flex;align-items:baseline;gap:3px}
.woba-base span,.woba-vs span{font-size:7px;font-weight:800;color:var(--color-meta);letter-spacing:0}
.team-record{font-family:'JetBrains Mono',monospace;font-size:10px;color:#888;letter-spacing:0.5px;margin-top:2px;text-align:center}
@media(max-width:560px){.lineup-grid.open{grid-template-columns:1fr}.lineup-col:first-child{border-right:0;border-bottom:1px solid #ddd}}
@media(max-width:380px){.batter-bottom{column-gap:4px}.batter-detail{gap:4px}.batter-pa,.batter-range{font-size:9px}.batter-metric{min-width:39px;font-size:10px;padding:3px 4px}}
"""
if "batter-metrics" not in css_block:
    css_block = css_block.replace("</style>", PLAYER_METRIC_CSS + "\n</style>")

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>MLB SIM \u2014 {DATE_DISPLAY}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
{css_block}
<link rel="stylesheet" href="https://morellosims.com/morello-auth.css?v=20260601-promo-fix">
    <link rel="stylesheet" href="../morello-auth.css?v=20260601-promo-fix">
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

<!-- ─── TRACKED PICKS BOX ────────────────────────────────────── -->
<div style="max-width:640px;margin:14px auto 18px;padding:0 12px;">
  <div style="background:#0a0a0a;border:2px solid #FFEA00;border-radius:6px;padding:16px 22px;box-shadow:5px 5px 0 #FFEA00;">
    <div style="display:grid;grid-template-columns:1.35fr 1fr 0.8fr;align-items:center;font-family:'JetBrains Mono',monospace;gap:16px;">
      <div style="text-align:left;min-width:0;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">TRACKED</div>
        <div style="font-size:30px;color:#00FF55;font-weight:700;line-height:1;margin-top:4px;font-family:'Anton',sans-serif;letter-spacing:1px;">{SEASON_RECORD}</div>
      </div>
      <div style="text-align:center;border-left:1px solid #2a2a2a;border-right:1px solid #2a2a2a;padding:2px 16px;min-width:0;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">ROI</div>
        <div style="font-size:30px;color:#FFEA00;font-weight:700;line-height:1;margin-top:4px;font-family:'Anton',sans-serif;letter-spacing:1px;">{SEASON_ROI_VALUE}</div>
      </div>
      <div style="text-align:right;min-width:0;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">STREAK</div>
        <div style="font-size:30px;color:#fff;font-weight:700;line-height:1;margin-top:4px;font-family:'Anton',sans-serif;letter-spacing:1px;">{SEASON_STREAK}</div>
      </div>
    </div>
    <div style="margin-top:12px;padding-top:10px;border-top:1px solid #2a2a2a;display:flex;justify-content:space-between;gap:12px;align-items:center;font-family:'JetBrains Mono',monospace;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">FILTER</div>
        <div style="font-size:11px;color:#fff;font-weight:700;line-height:1.3;letter-spacing:0.5px;text-align:right;">C:8+ <span style="color:#888;">PRICE GATES</span></div>
    </div>
  </div>
</div>

<!-- FILTER BAR (DESKTOP) -->
<div class="filter-bar">
    <div class="filter-bar-inner">
        <button class="filter-btn active" data-tab="lines">Lines</button>
        <button class="filter-btn" data-tab="daily">Go-Yard</button>
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

    <!-- DAILY TAB -->
    {render_hr_watch_tab()}

    <!-- INFO TAB -->
    <div class="tab-content" id="tab-info">
        <div style="padding-top:12px">
            <div class="info-card">
                <h2>HOW MLB SIM WORKS</h2>
                <p>MLB SIM uses the <strong>Pitcher DNA</strong> system (Gaussian Mixture Model clustering) to classify every pitcher into one of 26 archetypes (15 RHP + 11 LHP) based on their pitch mix, velocity, movement, and approach. Every batter has historical performance data against each archetype \u2014 because baseball is fundamentally a 1v1 sport, the specific pitcher a batter faces defines their expected performance.</p>
                <p>When lineups are released, MLB SIM projects every batter's event rates based on how they've historically hit against the opposing pitcher's archetype. <strong>MOMO</strong> is the matchup output score from that pitcher-DNA projection, anchored to projected output with baseline talent and matchup swing as modifiers. <strong>MOMI</strong> is MOMO with a live momentum adjustment from consecutive streak, recent hit-game density, and last-7 form, because hitter game logs are not treated as independent coin flips.</p>
            </div>
            <div class="info-card">
                <h2>MOMO \u2014 1 TO 99</h2>
                <p>MOMO is Optimized Matchup Output. It is anchored by today's pitcher-DNA projected wOBA, then modified by the hitter's own baseline and the matchup swing. That means an elite hitter in a below-baseline matchup can be downgraded without being incorrectly treated like a zero-impact bat.</p>
                <table class="tier-table">
                    <tr><td class="tier-label" style="color:var(--color-elite)">85-99</td><td>Elite matchup \u2014 archetype strongly favors the hitter</td></tr>
                    <tr><td class="tier-label" style="color:var(--color-favorable)">70-84</td><td>Plus matchup \u2014 strong pitcher-DNA output today</td></tr>
                    <tr><td class="tier-label" style="color:var(--color-neutral)">50-69</td><td>Neutral to playable matchup output</td></tr>
                    <tr><td class="tier-label" style="color:var(--color-tough)">1-49</td><td>Tough matchup \u2014 weak projected output after baseline adjustment</td></tr>
                </table>
                <div class="formula-block ma-premium">MOMO FORMULA (matchup output):
projected output score = pitcher-DNA wOBA mapped to 1-99
baseline talent score   = season wOBA mapped to 1-99
matchup swing modifier = (pitcher-DNA wOBA - baseline wOBA) * 80
MOMO = 75% output score + 25% talent score + matchup modifier

Example:
baseline wOBA       = .417
vs pitcher-DNA wOBA = .325
wOBA swing          = -.092
MOMO                = 64</div>
            </div>
            <div class="info-card">
                <h2>MOMI \u2014 1 TO 99</h2>
                <p>MOMI is Optimized Momentum Impact. It starts with MOMO, then adjusts for active hitting streak length, recent hit-game density, and last-7 batting average. Consecutive streaks are signal, but so are interrupted hot patterns like 4 of the last 5 games with a hit.</p>
                <div class="formula-block ma-premium">MOMI FORMULA (momentum impact):
MOMI starts with MOMO
+ active-streak bonus when a streak exists
+ nonlinear 5+ / 10+ streak ramp
+ recent hit-game density bonus (4/5, 5/7, 7/10)
+ last-7 AVG strength modifier when a momentum signal exists
no streak + no hit-density signal = MOMI remains MOMO

Example:
MOMO                = 75
active/recent form  = 4 of last 5 hit games
last-7 AVG          = .375
MOMI                = 86</div>
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
                <p><strong>Layer 3 \u2014 Matchup Integration:</strong> For each predicted reliever, computes MOMO/MOMI against the lineup slots they'll likely face.</p>
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
        <span>GO-YARD</span>
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
<script src="https://morellosims.com/morello-auth.js?v=20260601-promo-fix" data-ma-theme="mlb"></script>

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

function setupHrNavigation() {{
  const daily = document.getElementById('tab-daily');
  if (!daily) return;

  const buttons = Array.from(daily.querySelectorAll('[data-hr-filter]'));
  const rows = Array.from(daily.querySelectorAll('[data-hr-card]'));
  const empty = document.getElementById('hr-filter-empty');

  function applyFilter(filter) {{
    let visible = 0;
    buttons.forEach(btn => btn.classList.toggle('active', btn.dataset.hrFilter === filter));
    rows.forEach(row => {{
      const show = filter === 'ALL' || row.dataset.hrLane === filter;
      row.classList.toggle('hr-filtered', !show);
      if (show) visible += 1;
    }});
    if (empty) empty.hidden = visible > 0;
  }}

  buttons.forEach(btn => {{
    btn.addEventListener('click', () => applyFilter(btn.dataset.hrFilter || 'ALL'));
  }});

  daily.querySelectorAll('[data-hr-jump]').forEach(btn => {{
    btn.addEventListener('click', () => {{
      const target = daily.querySelector(btn.dataset.hrJump);
      if (!target) return;
      target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }});
  }});

  applyFilter('ALL');
}}

setupHrNavigation();

</script>
</body></html>'''

with open(OUTPUT, "w") as f:
    f.write(html)

# ─── Picks log — append today's pregame publishable picks to CSV ───────────
PICKS_LOG = os.path.join(REPO_ROOT, "mlbsim", "picks_log.csv")
writeable_picks = [g for g in qualified_picks if not g.get("has_started")]
skipped_heavy = [g for g in games if g["has_lineups"] and g["conf"] >= MIN_CONF_PICK and g["odds_too_heavy"]]
if skipped_heavy:
    def _price_gate_summary(g):
        edge = g.get("pick_price_edge")
        edge_txt = f"{edge * 100:+.1f}%" if edge is not None else "n/a"
        return f'{g["pick_team"]} ({g["pick_odds"]:+d}, edge {edge_txt})'

    print(f"  Skipped {len(skipped_heavy)} price-gated picks: " + ", ".join(_price_gate_summary(g) for g in skipped_heavy))

PICKS_LOG_FIELDS = [
    "date", "time", "pick", "conf", "value", "away", "home",
    "away_runs", "home_runs", "away_wp", "home_wp", "away_ml", "home_ml",
    "away_sp", "home_sp", "result",
]


def _pick_log_key(row):
    return (
        row.get("date", ""),
        row.get("time", ""),
        row.get("away", ""),
        row.get("home", ""),
        row.get("pick", ""),
    )


pick_log_rows = {}
if os.path.exists(PICKS_LOG):
    try:
        with open(PICKS_LOG, newline="") as f:
            for row in csv.DictReader(f):
                clean = {field: row.get(field, "") for field in PICKS_LOG_FIELDS}
                pick_log_rows[_pick_log_key(clean)] = clean
    except Exception as e:
        print(f"  WARN: Could not read existing picks CSV, rewriting fresh: {e}")

for g in writeable_picks:
    row = {
        "date": TODAY,
        "time": g["time_str"],
        "pick": g["pick_team"],
        "conf": g["conf"],
        "value": g["value"],
        "away": g["away_abbr"],
        "home": g["home_abbr"],
        "away_runs": g["away_runs"],
        "home_runs": g["home_runs"],
        "away_wp": g["away_wp"],
        "home_wp": g["home_wp"],
        "away_ml": g["away_ml"],
        "home_ml": g["home_ml"],
        "away_sp": g["away_sp"],
        "home_sp": g["home_sp"],
        "result": "",
    }
    pick_log_rows[_pick_log_key(row)] = row

with open(PICKS_LOG, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=PICKS_LOG_FIELDS)
    writer.writeheader()
    writer.writerows(
        sorted(
            pick_log_rows.values(),
            key=lambda row: (
                row.get("date", ""),
                row.get("time", ""),
                row.get("away", ""),
                row.get("home", ""),
                row.get("pick", ""),
            ),
        )
    )

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
matchup_counts = {}
for g in writeable_picks:
    key = (g["away_abbr"], g["home_abbr"])
    matchup_counts[key] = matchup_counts.get(key, 0) + 1

def pick_id_for_game(g):
    matchup_key = (g["away_abbr"], g["home_abbr"])
    game_suffix = ""
    if matchup_counts.get(matchup_key, 0) > 1:
        game_suffix = f'-g{g.get("game_pk")}' if g.get("game_pk") else f'-{g["time_str"].lower().replace(" ", "").replace(":", "")}'
    return f'{TODAY}-mlb-{g["away_abbr"]}-{g["home_abbr"]}{game_suffix}-ml'


if not odds_feed_has_lines:
    print("  WARN: odds feed returned zero real-book lines; preserving pending MLB picks")
else:
    unstarted_game_pks = {
        str(g.get("game_pk"))
        for g in games
        if g.get("game_pk") and not g.get("has_started")
    }
    unstarted_matchups = {
        (g.get("away_abbr"), g.get("home_abbr"))
        for g in games
        if not g.get("has_started")
    }
    qualified_ids = {pick_id_for_game(g) for g in writeable_picks}

    def is_unstarted_today_pick(p):
        game_pk = p.get("game_pk")
        if game_pk:
            return str(game_pk) in unstarted_game_pks
        return (p.get("away"), p.get("home")) in unstarted_matchups

    stale_pending_ids = [
        pick_id
        for pick_id, pick in by_id.items()
        if pick.get("sport") == "mlb"
        and pick.get("date") == TODAY
        and pick.get("bet_type") == "ml"
        and pick.get("status") == "pending"
        and is_unstarted_today_pick(pick)
        and pick_id not in qualified_ids
    ]
    for pick_id in stale_pending_ids:
        del by_id[pick_id]
    if stale_pending_ids:
        print(f"  Pruned {len(stale_pending_ids)} stale pending MLB picks before first pitch")

for g in writeable_picks:
    pick_team = g["pick_team"]
    pick_ml = g["away_ml"] if pick_team == g["away_abbr"] else g["home_ml"]
    pick_id = pick_id_for_game(g)
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
        "units": stake_for_conf(g["conf"]),
        "sim_projection": f'{g["away_abbr"]} {g["away_runs"]} - {g["home_abbr"]} {g["home_runs"]}',
        "sim_edge": g.get("edge"),
        "game_pk": g.get("game_pk"),
        "game_time": g.get("time_str"),
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
today_board = sorted(
    [p for p in merged if p.get("sport") == "mlb" and p.get("date") == TODAY and p.get("bet_type") == "ml"],
    key=lambda p: (-int(p.get("conf") or 0), p.get("matchup", "")),
)
picks_summary = " | ".join(f'{p["pick_text"]} (C:{p["conf"]})' for p in today_board)
if not picks_summary:
    picks_summary = "NO PLAYS"
print(f"\n  OFFICIAL BOARD: {picks_summary}")

size = os.path.getsize(OUTPUT)
print(f"\n{'='*60}")
print(f"  DONE: {OUTPUT}")
print(f"  Size: {size:,} bytes")
print(f"  Games: {len(games)} ({sum(1 for g in games if g['has_lineups'])} with lineups)")
print(f"  Generated: {gen_time}")
print(f"{'='*60}")

#!/usr/bin/env python3
"""
build_mlb_sim.py — Generate mlbsim/index.html from live MLB data + atlas.

Fetches today's schedule, lineups, probable pitchers from MLB Stats API,
runs the matchup model against atlas data, and renders the full page.

Usage: python3 scripts/build_mlb_sim.py
"""

import json, os, sys, math, requests, time as _time
from datetime import datetime, timezone, timedelta
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
ATLAS_DIR = os.path.join(REPO_ROOT, "atlas")
OUTPUT = os.path.join(REPO_ROOT, "mlbsim", "index.html")

MLB_API = "https://statsapi.mlb.com/api/v1"
ET = timezone(timedelta(hours=-4))
NOW = datetime.now(ET)
TODAY = NOW.strftime("%Y-%m-%d")
DATE_DISPLAY = NOW.strftime("%b %d").upper().replace(" 0", " ")  # "APR 3"
DATE_SHORT = NOW.strftime("%b %-d").upper()  # for slate

# ─── Team metadata ────────────────────────────────────────────────────────────
TEAMS = {
    "ARI":{"id":109,"color":"#A71930"},"ATL":{"id":144,"color":"#CE1141"},
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

# batter overall wOBA (weighted avg across blend years)
batter_woba_accum = {}  # bid → (total_wpa, total_w)
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

def get_base_woba(bid):
    acc = batter_woba_accum.get(bid)
    if not acc or acc[1] == 0: return .310
    return acc[0] / acc[1]

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

# ─── Scrape RotoWire lineups as backup ──────────────────────────────────────
import re as _re

def fetch_rotowire_lineups():
    """Scrape projected/confirmed lineups from RotoWire."""
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

        result = {}  # (away_abbr, home_abbr) → {"away_sp", "home_sp", "away_lineup", "home_lineup"}
        n_games = min(len(visit_sections), len(home_sections), len(all_teams) // 2)
        for i in range(n_games):
            away = all_teams[i * 2]
            home = all_teams[i * 2 + 1]
            v_sp, v_batters = parse_section(visit_sections[i])
            h_sp, h_batters = parse_section(home_sections[i])

            def resolve_id(name):
                """Look up MLB ID from player name."""
                if not name: return None
                key = name.lower().strip()
                if key in name_to_mlb_id:
                    return name_to_mlb_id[key]
                # Try last name match
                last = key.split()[-1] if key else ""
                for k, v in name_to_mlb_id.items():
                    if k.endswith(" " + last) or k == last:
                        return v
                return None

            def build_lineup(batters):
                lineup = []
                for pos, name, bats in batters:
                    pid = resolve_id(name)
                    if pid:
                        lineup.append({
                            "id": pid,
                            "fullName": name,
                            "primaryPosition": {"abbreviation": pos.strip()},
                            "batSide": {"code": bats.strip()},
                        })
                return lineup

            result[(away, home)] = {
                "away_sp_name": v_sp,
                "home_sp_name": h_sp,
                "away_sp_id": resolve_id(v_sp),
                "home_sp_id": resolve_id(h_sp),
                "away_lineup": build_lineup(v_batters),
                "home_lineup": build_lineup(h_batters),
            }
        return result
    except Exception as e:
        print(f"  WARN: RotoWire scrape failed: {e}")
        return {}

print("\nFetching RotoWire lineups...")
rw_lineups = fetch_rotowire_lineups()
print(f"  RotoWire games: {len(rw_lineups)}")
rw_used = 0

# ─── Fetch schedule ──────────────────────────────────────────────────────────
print(f"\nFetching schedule for {TODAY}...")
sched = fetch(f"{MLB_API}/schedule?sportId=1&date={TODAY}&hydrate=probablePitcher,lineups,linescore,team,venue")
games_raw = sched.get("dates", [{}])[0].get("games", []) if sched else []
print(f"  Games: {len(games_raw)}")

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

    # Lineups — try MLB API first, fall back to RotoWire
    away_lineup_raw = g.get("lineups", {}).get("awayPlayers", [])
    home_lineup_raw = g.get("lineups", {}).get("homePlayers", [])
    has_lineups = len(away_lineup_raw) > 0 and len(home_lineup_raw) > 0
    lineup_source = "MLB API" if has_lineups else ""

    # RotoWire fallback — also fill in pitcher IDs if MLB API missing them
    rw_key = (away_abbr, home_abbr)
    # ATH → OAK alias
    if rw_key not in rw_lineups:
        rw_key = ("ATH" if away_abbr == "OAK" else away_abbr,
                  "ATH" if home_abbr == "OAK" else home_abbr)
    if rw_key not in rw_lineups:
        rw_key = ("OAK" if away_abbr == "ATH" else away_abbr,
                  "OAK" if home_abbr == "ATH" else home_abbr)
    rw = rw_lineups.get(rw_key, {})

    if not has_lineups and rw:
        away_lineup_raw = rw.get("away_lineup", [])
        home_lineup_raw = rw.get("home_lineup", [])
        has_lineups = len(away_lineup_raw) > 0 and len(home_lineup_raw) > 0
        if has_lineups:
            lineup_source = "RotoWire"
            rw_used += 1

    # Fill in pitcher IDs from RotoWire if MLB API didn't have them
    if not away_sp_id and rw.get("away_sp_id"):
        away_sp_id = rw["away_sp_id"]
        away_sp_name = rw.get("away_sp_name", away_sp_name)
        away_ps = pitcher_idx.get(away_sp_id, {})
        away_cluster = away_ps.get("cluster", "R_UT")
        away_arch = away_ps.get("archetype", "Unknown")
        away_hand = "LHP" if away_ps.get("is_rhp", 1) == 0 else "RHP"
        away_tier = tier_idx.get(away_sp_id, {})
        away_tier_name = away_tier.get("tier", "T3_Standard")
        away_tier_mult = away_tier.get("effective_multiplier", 1.0)
    if not home_sp_id and rw.get("home_sp_id"):
        home_sp_id = rw["home_sp_id"]
        home_sp_name = rw.get("home_sp_name", home_sp_name)
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

        # League average priors
        LG_WOBA = 0.310; LG_H_RATE = 0.245; LG_BB_RATE = 0.08
        LG_HR_RATE = 0.03; LG_TB_RATE = 0.40

        for i, p in enumerate(lineup_raw):
            pid = p.get("id")
            name = p.get("fullName", "Unknown")
            pos = p.get("primaryPosition", {}).get("abbreviation", "?")
            bat_side = p.get("batSide", {}).get("code", "R")

            base_w = get_base_woba(pid)

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
                # GMM-weighted rates - no league avg regression needed
                # The multi-cluster approach already thickens the dataset
                vs_woba = w_woba / total_weight
                vs_woba = max(0.050, min(0.600, vs_woba))
                h_rate = w_h / total_weight
                bb_rate = w_bb / total_weight
                hr_rate = w_hr / total_weight
                tb_rate = w_tb / total_weight
            else:
                # No archetype data at all - use batter's base wOBA
                vs_woba = base_w
                total_pa = 0
                h_rate = 0.245; bb_rate = 0.08
                hr_rate = 0.03; tb_rate = 0.40

            # Per-game PA estimate
            pa = 4

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
        away_batters, away_runs_raw, away_woba, away_pa = process_lineup(
            away_lineup_raw, home_gmm, away_abbr)
        home_batters, home_runs_raw, home_woba, home_pa = process_lineup(
            home_lineup_raw, away_gmm, home_abbr)

        # Apply tier multipliers
        away_runs = round(away_runs_raw * home_tier_mult, 1)
        home_runs = round(home_runs_raw * away_tier_mult, 1)

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

    total_runs = away_runs + home_runs
    if total_runs > 0:
        away_wp = round(away_runs / total_runs * 100)
        home_wp = 100 - away_wp
    else:
        away_wp = 50
        home_wp = 50

    # Home field bump
    if has_lineups:
        home_wp = min(95, home_wp + 3)
        away_wp = 100 - home_wp

    # Confidence (1-10) based on how far from 50/50
    wp_gap = abs(away_wp - 50)
    conf = min(10, max(0, round(wp_gap / 4.5)))

    # Value (1-10) — without real odds, base on edge magnitude
    edge = abs(away_runs - home_runs)
    value = min(10, max(0, round(edge * 2)))
    if not has_lineups:
        conf = 0
        value = 0

    # Pick
    if away_wp > home_wp:
        pick_team = away_abbr
        pick_ml = ""  # no odds available from API
    else:
        pick_team = home_abbr
        pick_ml = ""

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
        "away_woba": away_woba, "home_woba": home_woba,
        "away_batters": away_batters, "home_batters": home_batters,
        "has_lineups": has_lineups,
        "conf": conf, "value": value,
        "edge": round(edge, 1),
        "pick_team": pick_team,
        "venue": venue, "time_str": time_str,
        "total": round(total_runs, 1),
    })

print(f"  Processed {len(games)} games")
print(f"  With lineups: {sum(1 for g in games if g['has_lineups'])}")
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
    <span class="batter-stats">{h(b["pos"])} &middot; {b["bat_side"]}</span>
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

    # Pick display
    pick_html = ""
    if g["has_lineups"] and g["conf"] > 0:
        cc = conf_color(g["conf"])
        vc = conf_color(g["value"])
        pick_html = f'''<div class="sim-pick"><span class="pick-type-label">ML</span> {h(g["pick_team"])} ML <span class="mc-conf-num" style="color:{cc}" title="Confidence">C:{g["conf"]}</span> <span class="mc-conf-num" style="color:{vc}" title="Value">V:{g["value"]}</span></div>'''

    # Edge bar
    edge_html = ""
    if g["has_lineups"] and g["edge"] > 1:
        edge_html = f'<div class="edge-bar ma-premium">ML Edge: {h(g["pick_team"])} +{g["edge"]} projected runs</div>'

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

    return f'''<div class="game-card" data-conf="{g["conf"]}" data-value="{g["value"]}" data-edge="{g["edge"]}">
  <div class="run-bar ma-premium">
  <div class="run-bar-seg" style="width:{aw}%;background:{ac}">{ar}</div>
  <div class="run-bar-seg" style="width:{hw}%;background:{hc}">{hr_}</div>
</div>
  <div class="card-header">
  <div class="team-block">
    <div class="team-logo"><img src="https://www.mlbstatic.com/team-logos/{g["away_id"]}.svg" alt="{aa}" style="width:100%;height:100%;object-fit:contain"></div>
    <div class="team-abbr">{aa}</div>
    <div class="team-ml">\u2014</div>
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
    <div class="team-ml">\u2014</div>
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
      <span class="model-formula">BaseRuns(wOBA\u00d7Tier) + Park = <strong>{formula}</strong></span>
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
    data = fetch(f"{MLB_API}/people/{pid}/stats?stats=gameLog&season={NOW.year}&group=hitting")
    if not data:
        continue
    splits = data.get("stats", [{}])[0].get("splits", [])
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

    # Today's Edges column
    edges = sorted(
        [g for g in games if g["has_lineups"] and g["conf"] > 0],
        key=lambda x: (-x["conf"], -x["edge"])
    )
    edges_html = ""
    for i, g in enumerate(edges[:12]):
        cc = conf_color(g["conf"])
        prem = ' ma-premium' if g["conf"] >= 8 else ''
        edges_html += f'''<div class="pick-row{prem}">
  <div class="pick-rank">{i+1}</div>
  <div class="pick-info">
    <div class="pick-label gp-pick-strong">{h(g["pick_team"])} ML <span class="mc-conf-num" style="color:{cc}">{g["conf"]}</span></div>
    <div class="pick-matchup">{g["away_abbr"]} @ {g["home_abbr"]}</div>
  </div>
  <div class="pick-edge">+{g["edge"]}</div>
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
                <div class="section-title">\U0001f3af TODAY'S EDGES</div>
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
            <div class="chip" onclick="sortGames('value', this)">Value</div>
            <div class="chip" onclick="sortGames('confidence', this)">Confidence</div>
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
  if (mode === 'value') {{
    sorted = [...cards].sort((a, b) => (parseFloat(b.dataset.value) || 0) - (parseFloat(a.dataset.value) || 0));
  }} else if (mode === 'confidence') {{
    sorted = [...cards].sort((a, b) => (parseFloat(b.dataset.conf) || 0) - (parseFloat(a.dataset.conf) || 0));
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

size = os.path.getsize(OUTPUT)
print(f"\n{'='*60}")
print(f"  DONE: {OUTPUT}")
print(f"  Size: {size:,} bytes")
print(f"  Games: {len(games)} ({sum(1 for g in games if g['has_lineups'])} with lineups)")
print(f"  Generated: {gen_time}")
print(f"{'='*60}")

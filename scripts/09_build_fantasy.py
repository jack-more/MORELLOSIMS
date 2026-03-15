"""
09_build_fantasy.py — Fantasy Stat Projections by Position (ESPN format)

Projects actual counting stats using Pitcher DNA matchup data:
  Hitters: R, HR, RBI, SB, AVG, OPS
  Pitchers: K, QS, W, S, ERA, WHIP

Time frames: Weekly (matchup-adjusted), Yearly (full season), Daily (single game)

Data sources:
  - MLB Stats API: rosters (positions), schedule (matchups), player stats (SB rates)
  - atlas/hitter_vs_cluster.json: per-batter stats vs each pitcher archetype
  - atlas/pitcher_tiers.json: pitcher tier + archetype assignments
  - atlas/pitcher_seasons.json: is_sp, whiff_rate, archetype
  - atlas/park_factors.json: park adjustments
  - atlas/sp_innings.json: starter innings per game

Writes:
  - atlas/fantasy_projections.json (all projections, all time frames)
"""

import json
import os
import time
import requests
from collections import defaultdict

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_atlas, save_atlas, woba_to_ms

# ─── Config ───────────────────────────────────────────────────────────────────
SEASON = 2026
WEEK_START = "2026-03-25"
WEEK_END = "2026-03-31"
WEEK_LABEL = "WEEK 1 — MAR 25 – 31"
FULL_SEASON_PA = 650        # typical full-season PA for a starter
FULL_SEASON_GAMES = 162
PA_PER_GAME = 4.0           # average PA per game for a lineup regular
SP_BF_PER_START = 24        # ~6 IP × 4 BF/IP
SP_IP_PER_START = 5.8       # league avg
RP_APP_PER_WEEK = 3         # average RP appearances per week
RP_IP_PER_APP = 1.0
RP_BF_PER_APP = 4.2
TOP_N = 20

MLB_API = "https://statsapi.mlb.com/api/v1"

ESPN_POS_MAP = {
    "C": "C", "1B": "1B", "2B": "2B", "3B": "3B", "SS": "SS",
    "LF": "OF", "CF": "OF", "RF": "OF",
    "DH": "UTIL", "P": "P",
}


# ─── Fetch helpers ────────────────────────────────────────────────────────────

def fetch_json(url, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                print(f"  WARN: Failed {url}: {e}")
                return None


def fetch_all_rosters():
    """Fetch active rosters for all 30 teams."""
    teams_data = fetch_json(f"{MLB_API}/teams?sportId=1&season={SEASON}")
    if not teams_data:
        return {}, []

    team_list = [(t["id"], t["abbreviation"]) for t in teams_data.get("teams", [])]
    players = {}

    for team_id, abbr in team_list:
        data = fetch_json(f"{MLB_API}/teams/{team_id}/roster/active?season={SEASON}")
        if not data:
            continue
        for p in data.get("roster", []):
            pid = p["person"]["id"]
            pos_abbr = p.get("position", {}).get("abbreviation", "?")
            players[pid] = {
                "name": p["person"]["fullName"],
                "team": abbr,
                "api_pos": pos_abbr,
                "espn_pos": ESPN_POS_MAP.get(pos_abbr, pos_abbr),
            }
        time.sleep(0.05)

    print(f"  Fetched {len(players)} players across {len(team_list)} teams")
    return players, team_list


def fetch_week_schedule(start=WEEK_START, end=WEEK_END):
    """Fetch schedule with probable pitchers."""
    url = (f"{MLB_API}/schedule?sportId=1&season={SEASON}&gameType=R"
           f"&startDate={start}&endDate={end}&hydrate=probablePitcher,team")
    data = fetch_json(url)
    if not data:
        return []
    games = []
    for d in data.get("dates", []):
        for g in d["games"]:
            t = g.get("teams", {})
            games.append({
                "date": d["date"],
                "away_team": t["away"]["team"]["abbreviation"],
                "home_team": t["home"]["team"]["abbreviation"],
                "away_sp_id": t["away"].get("probablePitcher", {}).get("id", 0),
                "away_sp_name": t["away"].get("probablePitcher", {}).get("fullName", "TBD"),
                "home_sp_id": t["home"].get("probablePitcher", {}).get("id", 0),
                "home_sp_name": t["home"].get("probablePitcher", {}).get("fullName", "TBD"),
            })
    print(f"  {len(games)} games from {start} to {end}")
    return games


def fetch_player_season_stats(player_ids, season=2024):
    """Fetch SB rates and other stats not in local data. Batch by chunks."""
    stats = {}
    ids = list(player_ids)
    print(f"  Fetching season stats for {len(ids)} players...")
    for i in range(0, len(ids), 50):
        chunk = ids[i:i+50]
        for pid in chunk:
            url = f"{MLB_API}/people/{pid}/stats?stats=season&season={season}&group=hitting"
            data = fetch_json(url)
            if data:
                stat_list = data.get("stats", [])
                if stat_list and stat_list[0].get("splits"):
                    s = stat_list[0]["splits"][0].get("stat", {})
                    pa = s.get("plateAppearances", 0)
                    if pa > 0:
                        hr = s.get("homeRuns", 0)
                        avg = float(s.get("avg", ".250") or ".250")
                        ops = float(s.get("ops", ".720") or ".720")
                        stats[pid] = {
                            "sb": s.get("stolenBases", 0),
                            "cs": s.get("caughtStealing", 0),
                            "r": s.get("runs", 0),
                            "rbi": s.get("rbi", 0),
                            "hr": hr,
                            "pa": pa,
                            "sb_rate": s.get("stolenBases", 0) / pa,
                            "r_rate": s.get("runs", 0) / pa,
                            "rbi_rate": s.get("rbi", 0) / pa,
                            "hr_rate": hr / pa,
                            "avg": avg,
                            "ops": ops,
                        }
            time.sleep(0.02)
    print(f"  Got stats for {len(stats)} players")
    return stats


def fetch_pitcher_season_stats(player_ids, season=2024):
    """Fetch W, QS, S, ERA, WHIP from API for pitchers."""
    stats = {}
    ids = list(player_ids)
    print(f"  Fetching pitcher stats for {len(ids)} pitchers...")
    for pid in ids:
        url = f"{MLB_API}/people/{pid}/stats?stats=season&season={season}&group=pitching"
        data = fetch_json(url)
        if data:
            stat_list = data.get("stats", [])
            splits = stat_list[0].get("splits", []) if stat_list else []
            if splits:
                s = splits[0].get("stat", {})
                ip = float(s.get("inningsPitched", "0") or "0")
                gs = s.get("gamesStarted", 0)
                stats[pid] = {
                    "w": s.get("wins", 0),
                    "l": s.get("losses", 0),
                    "sv": s.get("saves", 0),
                    "k": s.get("strikeOuts", 0),
                    "era": float(s.get("era", "4.50") or "4.50"),
                    "whip": float(s.get("whip", "1.30") or "1.30"),
                    "ip": ip,
                    "gs": gs,
                    "g": s.get("gamesPlayed", 0),
                    "h": s.get("hits", 0),
                    "bb": s.get("baseOnBalls", 0),
                    "er": s.get("earnedRuns", 0),
                    "qs": s.get("qualityStarts", 0) if "qualityStarts" in s else None,
                    "k_per_9": float(s.get("strikeoutsPer9Inn", "0") or "0"),
                    "ip_per_gs": ip / max(1, gs) if gs > 0 else 0,
                }
        time.sleep(0.02)
    print(f"  Got stats for {len(stats)} pitchers")
    return stats


# ─── Index builders ───────────────────────────────────────────────────────────

def build_pitcher_archetype_index(pitcher_seasons, pitcher_tiers):
    """pitcher_id → {cluster, archetype, tier, is_sp, whiff_rate}"""
    index = {}

    # pitcher_seasons may be a list or dict
    items = pitcher_seasons if isinstance(pitcher_seasons, list) else pitcher_seasons.values()
    for rec in items:
        pid = rec.get("pitcher")
        year = rec.get("game_year", 0)
        if pid not in index or year > index[pid].get("year", 0):
            index[pid] = {
                "year": year,
                "cluster": rec.get("cluster"),
                "archetype": rec.get("archetype"),
                "is_sp": rec.get("is_sp", 0),
                "whiff_rate": rec.get("whiff_rate", 0),
            }

    # pitcher_tiers may be a list or dict
    tier_items = pitcher_tiers if isinstance(pitcher_tiers, list) else pitcher_tiers.values()
    for rec in tier_items:
        pid = rec.get("pitcher")
        if pid in index:
            tier_year = rec.get("game_year", 0)
            if tier_year >= index[pid].get("year", 0):
                index[pid]["tier"] = rec.get("tier", "T3_Standard")
    return index


def build_batter_cluster_index(hitter_vs_cluster):
    """(batter_id, cluster) → full stat line for most recent year."""
    index = {}
    for rec in hitter_vs_cluster:
        bid = rec.get("batter")
        cluster = rec.get("cluster")
        year = rec.get("game_year", 0)
        key = (bid, cluster)
        if key not in index or year > index[key].get("game_year", 0):
            index[key] = rec
    return index


def build_batter_aggregate_index(hitter_vs_cluster):
    """batter_id → aggregate stats across all clusters for most recent year."""
    # First group by (batter, year)
    by_batter_year = defaultdict(list)
    for rec in hitter_vs_cluster:
        by_batter_year[(rec["batter"], rec.get("game_year", 0))].append(rec)

    # For each batter, take most recent year
    latest = {}
    for (bid, year), recs in by_batter_year.items():
        if bid not in latest or year > latest[bid]["year"]:
            total_pa = sum(r.get("PA", 0) for r in recs)
            total_ab = sum(r.get("AB", 0) for r in recs)
            total_h = sum(r.get("H", 0) for r in recs)
            total_hr = sum(r.get("HR", 0) for r in recs)
            total_bb = sum(r.get("BB", 0) for r in recs)
            total_k = sum(r.get("K", 0) for r in recs)
            total_singles = sum(r.get("singles", 0) for r in recs)
            total_doubles = sum(r.get("doubles", 0) for r in recs)
            total_triples = sum(r.get("triples", 0) for r in recs)
            total_hbp = sum(r.get("HBP", 0) for r in recs)

            avg = total_h / max(1, total_ab)
            obp = (total_h + total_bb + total_hbp) / max(1, total_pa)
            tb = total_singles + 2*total_doubles + 3*total_triples + 4*total_hr
            slg = tb / max(1, total_ab)

            latest[bid] = {
                "year": year,
                "pa": total_pa, "ab": total_ab, "h": total_h, "hr": total_hr,
                "bb": total_bb, "k": total_k, "hbp": total_hbp,
                "singles": total_singles, "doubles": total_doubles,
                "triples": total_triples,
                "avg": round(avg, 3), "obp": round(obp, 3),
                "slg": round(slg, 3), "ops": round(obp + slg, 3),
                "hr_rate": total_hr / max(1, total_pa),
                "h_rate": total_h / max(1, total_pa),
                "bb_rate": total_bb / max(1, total_pa),
                "k_rate": total_k / max(1, total_pa),
            }
    return latest


# ─── Projection engine ───────────────────────────────────────────────────────

def project_batter_game(batter_id, cluster, batter_cluster_idx, batter_agg, park_factor=1.0):
    """Project a single game's stats for a batter vs a specific pitcher archetype."""
    rec = batter_cluster_idx.get((batter_id, cluster))
    agg = batter_agg.get(batter_id, {})

    if rec and rec.get("PA", 0) >= 10:
        # Use H2H archetype-specific rates (min 10 AB to qualify)
        pa = rec["PA"]
        h_rate = rec.get("H", 0) / max(1, pa)
        hr_rate = rec.get("HR", 0) / max(1, pa)
        bb_rate = rec.get("BB", 0) / max(1, pa)
        k_rate = rec.get("K", 0) / max(1, pa)
        singles_rate = rec.get("singles", 0) / max(1, pa)
        doubles_rate = rec.get("doubles", 0) / max(1, pa)
        triples_rate = rec.get("triples", 0) / max(1, pa)
        hbp_rate = rec.get("HBP", 0) / max(1, pa)
        ab_rate = rec.get("AB", 0) / max(1, pa)
    elif agg:
        # Fall back to aggregate rates
        h_rate = agg["h_rate"]
        hr_rate = agg["hr_rate"]
        bb_rate = agg["bb_rate"]
        k_rate = agg["k_rate"]
        singles_rate = agg.get("singles", 0) / max(1, agg["pa"])
        doubles_rate = agg.get("doubles", 0) / max(1, agg["pa"])
        triples_rate = agg.get("triples", 0) / max(1, agg["pa"])
        hbp_rate = 0.01
        ab_rate = agg["ab"] / max(1, agg["pa"])
    else:
        # League average fallback
        h_rate = 0.230
        hr_rate = 0.030
        bb_rate = 0.085
        k_rate = 0.220
        singles_rate = 0.150
        doubles_rate = 0.045
        triples_rate = 0.005
        hbp_rate = 0.010
        ab_rate = 0.905

    # Apply park factor to power/hit stats
    pf = park_factor
    game_pa = PA_PER_GAME
    game_ab = game_pa * ab_rate

    h = game_pa * h_rate * pf
    hr = game_pa * hr_rate * pf
    singles = game_pa * singles_rate * pf
    doubles = game_pa * doubles_rate * pf
    triples = game_pa * triples_rate * pf
    bb = game_pa * bb_rate

    # Derived stats
    tb = singles + 2*doubles + 3*triples + 4*hr
    avg = h / max(0.1, game_ab)
    obp = (h + bb + game_pa * hbp_rate) / max(0.1, game_pa)
    slg = tb / max(0.1, game_ab)
    ops = obp + slg

    return {
        "pa": game_pa, "ab": game_ab,
        "h": h, "hr": hr, "bb": bb,
        "singles": singles, "doubles": doubles, "triples": triples,
        "avg": avg, "obp": obp, "slg": slg, "ops": ops,
    }


def project_hitters(players, games, batter_cluster_idx, batter_agg, pitcher_idx,
                    park_factors, api_stats):
    """Project hitter stats for all time frames."""
    # Build team schedule + game counts
    team_matchups = defaultdict(list)
    team_game_counts = defaultdict(int)
    for g in games:
        team_matchups[g["away_team"]].append({
            "vs_sp_id": g["home_sp_id"], "vs_sp_name": g["home_sp_name"],
            "opponent": g["home_team"], "park": g["home_team"], "date": g["date"],
        })
        team_matchups[g["home_team"]].append({
            "vs_sp_id": g["away_sp_id"], "vs_sp_name": g["away_sp_name"],
            "opponent": g["away_team"], "park": g["home_team"], "date": g["date"],
        })
        team_game_counts[g["away_team"]] += 1
        team_game_counts[g["home_team"]] += 1

    results = []
    for pid, pinfo in players.items():
        if pinfo["espn_pos"] == "P":
            continue

        team = pinfo["team"]
        matchups = team_matchups.get(team, [])
        agg = batter_agg.get(pid, {})
        api = api_stats.get(pid, {})

        if not agg and not api:
            continue  # no data at all

        # ── Weekly projection (matchup-adjusted) ──
        weekly = {"r": 0, "hr": 0, "rbi": 0, "sb": 0, "h": 0, "ab": 0,
                  "obp_sum": 0, "slg_sum": 0, "games": len(matchups)}
        matchup_details = []

        for m in matchups:
            sp_info = pitcher_idx.get(m["vs_sp_id"])
            cluster = sp_info["cluster"] if sp_info and sp_info.get("cluster") else None

            pf_data = park_factors.get(m["park"], {})
            pf = pf_data.get("park_factor", pf_data.get("factor", 100)) / 100 if isinstance(pf_data, dict) else 1.0

            proj = project_batter_game(pid, cluster, batter_cluster_idx, batter_agg, pf)

            weekly["h"] += proj["h"]
            weekly["hr"] += proj["hr"]
            weekly["ab"] += proj["ab"]
            weekly["obp_sum"] += proj["obp"]
            weekly["slg_sum"] += proj["slg"]

            # wOBA for MS display
            woba_rec = batter_cluster_idx.get((pid, cluster)) if cluster else None
            woba = woba_rec.get("wOBA", 0.320) if woba_rec and woba_rec.get("PA", 0) >= 10 else 0.320
            ms = woba_to_ms(woba)

            matchup_details.append({
                "vs": m["vs_sp_name"], "opp": m["opponent"], "ms": ms, "date": m["date"],
            })

        n_games = max(1, len(matchups))
        # Cap rates to prevent outliers from small samples
        sb_rate = min(api.get("sb_rate", 0.015), 0.08)   # cap ~50 SB/season
        r_rate = min(api.get("r_rate", 0.110), 0.20)     # cap ~130 R/season
        rbi_rate = min(api.get("rbi_rate", 0.115), 0.22)  # cap ~140 RBI/season
        # Require minimum PA for rate stats
        if api.get("pa", 0) < 100:
            sb_rate = 0.015
            r_rate = 0.110
            rbi_rate = 0.115

        # ── Yearly projection (full season) — use REAL API stats as anchor ──
        yearly_pa = FULL_SEASON_PA
        if api and api.get("pa", 0) >= 100:
            # Use actual MLB stats as primary source
            yearly_hr = yearly_pa * api["hr_rate"]
            yearly_avg = api["avg"]
            yearly_ops = api["ops"]
            yearly_ab = yearly_pa * 0.905
            yearly_h = yearly_pa * (api["avg"] * 0.905)  # avg × ab_rate
        elif agg and agg.get("pa", 0) >= 50:
            # Fall back to cluster aggregate (but cap HR rate)
            yearly_ab = yearly_pa * agg["ab"] / max(1, agg["pa"])
            yearly_h = yearly_pa * agg["h_rate"]
            yearly_hr = yearly_pa * min(agg["hr_rate"], 0.070)  # cap ~45 HR max
            yearly_avg = agg["avg"]
            yearly_ops = agg["ops"]
        else:
            yearly_ab = yearly_pa * 0.905
            yearly_h = yearly_pa * 0.230
            yearly_hr = yearly_pa * 0.030
            yearly_avg = 0.250
            yearly_ops = 0.720

        # Cap weekly HR to be consistent with yearly pace
        # yearly_hr / 26 weeks = reasonable per-week cap (with 20% upside buffer)
        max_weekly_hr = (yearly_hr / 26) * 1.20
        weekly["hr"] = min(weekly["hr"], max_weekly_hr)

        weekly["r"] = round(r_rate * PA_PER_GAME * n_games + weekly["hr"] * 0.3, 1)
        weekly["rbi"] = round(rbi_rate * PA_PER_GAME * n_games + weekly["hr"] * 0.5, 1)
        weekly["sb"] = round(sb_rate * PA_PER_GAME * n_games, 1)
        weekly["hr"] = round(weekly["hr"], 1)
        weekly["avg"] = round(weekly["h"] / max(0.1, weekly["ab"]), 3)
        weekly["ops"] = round((weekly["obp_sum"] + weekly["slg_sum"]) / n_games, 3)

        yearly_r = round(r_rate * yearly_pa + yearly_hr * 0.3, 0)
        yearly_rbi = round(rbi_rate * yearly_pa + yearly_hr * 0.5, 0)
        yearly_sb = round(sb_rate * yearly_pa, 0)

        yearly = {
            "r": int(yearly_r), "hr": int(round(yearly_hr)),
            "rbi": int(yearly_rbi), "sb": int(yearly_sb),
            "avg": round(yearly_avg, 3), "ops": round(yearly_ops, 3),
            "games": FULL_SEASON_GAMES,
        }

        # ── Compute fantasy value: Standalone → H2H → Archetype ──
        # Standalone is the foundation, matchup data adjusts from there
        ms_scores = [m["ms"] for m in matchup_details]
        avg_ms = sum(ms_scores) / len(ms_scores) if ms_scores else 60

        # Standalone: batter's own production (OPS → 40-99 scale) — PRIMARY
        player_ops = yearly["ops"]
        standalone = max(40, min(99, 40 + (player_ops - 0.550) / (0.950 - 0.550) * 59))

        # Archetype adjustment: opposing pitcher tier shifts value up/down
        tier_scores = {"T1_Apex": 45, "T2_Core": 60, "T3_Standard": 75, "T4_Fringe": 92}
        arch_scores = []
        for m in matchups:
            sp_info = pitcher_idx.get(m["vs_sp_id"])
            sp_tier = sp_info["tier"] if sp_info else "T3_Standard"
            arch_scores.append(tier_scores.get(sp_tier, 75))
        arch_score = sum(arch_scores) / len(arch_scores) if arch_scores else 75

        # Weighted blend: 50% Standalone + 30% H2H + 20% Archetype
        blended = 0.50 * standalone + 0.30 * avg_ms + 0.20 * arch_score
        games_adj = 1 + (n_games - 5) * 0.04
        fv = blended * games_adj + weekly["hr"] * 5 + weekly["sb"] * 3

        results.append({
            "id": pid, "name": pinfo["name"], "team": team,
            "pos": pinfo["api_pos"], "espn_pos": pinfo["espn_pos"],
            "avg_ms": round(avg_ms, 1),
            "weekly": weekly, "yearly": yearly,
            "matchups": matchup_details,
            "opponents": list(set(m["opp"] for m in matchup_details)),
            "fantasy_value": round(fv, 1),
        })

    results.sort(key=lambda x: x["fantasy_value"], reverse=True)
    return results


def project_pitchers(players, games, pitcher_idx, batter_cluster_idx, batter_agg,
                     park_factors, pitcher_api_stats, sp_innings):
    """Project pitcher stats for all time frames."""
    # Build pitcher schedule + team game counts
    team_game_counts = defaultdict(int)
    pitcher_starts = defaultdict(list)
    for g in games:
        team_game_counts[g["away_team"]] += 1
        team_game_counts[g["home_team"]] += 1
        if g["home_sp_id"]:
            pitcher_starts[g["home_sp_id"]].append({
                "opponent": g["away_team"], "park": g["home_team"], "date": g["date"],
            })
        if g["away_sp_id"]:
            pitcher_starts[g["away_sp_id"]].append({
                "opponent": g["home_team"], "park": g["home_team"], "date": g["date"],
            })

    results = []
    for pid, pinfo in players.items():
        if pinfo["espn_pos"] != "P":
            continue

        p_data = pitcher_idx.get(pid, {})
        is_sp = p_data.get("is_sp", 0)
        tier = p_data.get("tier", "T3_Standard")
        archetype = p_data.get("archetype", "Unknown")
        whiff_rate = p_data.get("whiff_rate", 0)
        api = pitcher_api_stats.get(pid, {})

        starts = pitcher_starts.get(pid, [])
        n_starts = len(starts)

        # If SP has no scheduled starts (TBD), estimate from team games / 5 rotation
        if is_sp and n_starts == 0:
            team = pinfo["team"]
            team_games = team_game_counts.get(team, 5)
            # Each SP in a 5-man rotation gets ~team_games/5 starts
            n_starts = max(1, round(team_games / 5))

        # Use API stats as base rates
        if api:
            k_per_9 = api.get("k_per_9", 8.0)
            era = api.get("era", 4.50)
            whip = api.get("whip", 1.30)
            ip_per_gs = api.get("ip_per_gs", SP_IP_PER_START)
            if is_sp:
                w_rate = api.get("w", 0) / max(1, api.get("gs", 1))
                w_rate = min(w_rate, 0.65)  # cap: nobody wins >65% of starts
            else:
                # RPs: wins are rare — use per-game rate, capped low
                w_rate = api.get("w", 0) / max(1, api.get("g", 1))
                w_rate = min(w_rate, 0.10)  # cap: ~6 W per 60 games max
            sv = api.get("sv", 0)
            sv_rate = sv / max(1, api.get("g", 1) or 1)
            # QS: use actual data if available, otherwise estimate from ERA + IP/GS
            if api.get("qs") is not None and api.get("gs", 0) > 0:
                qs_pct = api["qs"] / max(1, api["gs"])
            elif is_sp:
                # Estimate QS probability from ERA and IP/GS
                # Lower ERA + deeper into games = more QS
                qs_era_factor = max(0, 1 - (era - 2.50) / 5.0)  # ERA 2.50 → 1.0, ERA 7.50 → 0.0
                qs_ip_factor = min(1, ip_per_gs / 6.0)  # Need 6+ IP for QS
                qs_pct = min(0.75, qs_era_factor * qs_ip_factor * 0.70)
                qs_pct = max(0.05, qs_pct)
            else:
                qs_pct = 0
            k_per_ip = k_per_9 / 9
        else:
            # Tier-based defaults
            tier_defaults = {
                "T1_Apex": {"k9": 10.5, "era": 2.80, "whip": 1.05},
                "T2_Core": {"k9": 8.5, "era": 3.60, "whip": 1.15},
                "T3_Standard": {"k9": 7.5, "era": 4.20, "whip": 1.25},
                "T4_Fringe": {"k9": 6.5, "era": 5.00, "whip": 1.40},
            }
            td = tier_defaults.get(tier, tier_defaults["T3_Standard"])
            k_per_9 = td["k9"]
            era = td["era"]
            whip = td["whip"]
            ip_per_gs = SP_IP_PER_START
            w_rate = 0.35
            sv_rate = 0
            qs_pct = 0.45
            k_per_ip = k_per_9 / 9

        pos_label = "SP" if is_sp else "RP"

        # ── Weekly projection ──
        if is_sp and n_starts > 0:
            week_ip = ip_per_gs * n_starts
            week_k = round(k_per_ip * week_ip, 1)
            week_qs = round(qs_pct * n_starts, 1)
            week_w = round(w_rate * n_starts, 1)
            week_s = 0
            week_era = round(era, 2)
            week_whip = round(whip, 2)
        elif not is_sp:
            # RP: estimate ~3 appearances per week
            apps = RP_APP_PER_WEEK
            week_ip = RP_IP_PER_APP * apps
            week_k = round(k_per_ip * week_ip, 1)
            week_qs = 0
            week_w = round(w_rate * apps, 1)
            week_s = round(sv_rate * apps, 1)
            week_era = round(era, 2)
            week_whip = round(whip, 2)
        else:
            week_ip = 0
            week_k = 0
            week_qs = 0
            week_w = 0
            week_s = 0
            week_era = era
            week_whip = whip

        weekly = {
            "k": week_k, "qs": week_qs, "w": week_w, "s": week_s,
            "era": week_era, "whip": week_whip,
            "starts": n_starts, "ip": round(week_ip, 1),
        }

        # ── Yearly projection ──
        if is_sp:
            yearly_gs = api.get("gs", 30) if api else 30
            yearly_ip = ip_per_gs * yearly_gs
            yearly_k = round(k_per_ip * yearly_ip)
            yearly_qs = round(qs_pct * yearly_gs)
            yearly_w = round(w_rate * yearly_gs)
            yearly_s = 0
        else:
            yearly_g = api.get("g", 60) if api else 60
            yearly_ip = RP_IP_PER_APP * yearly_g
            yearly_k = round(k_per_ip * yearly_ip)
            yearly_qs = 0
            yearly_w = round(w_rate * yearly_g)
            yearly_s = round(sv_rate * yearly_g)

        yearly = {
            "k": int(yearly_k), "qs": int(yearly_qs), "w": int(yearly_w),
            "s": int(yearly_s), "era": round(era, 2), "whip": round(whip, 2),
            "ip": round(yearly_ip),
        }

        # ── Fantasy value ──
        tier_scores = {"T1_Apex": 92, "T2_Core": 78, "T3_Standard": 64, "T4_Fringe": 50}
        base_score = tier_scores.get(tier, 64)
        whiff_bonus = max(0, (whiff_rate - 0.22) * 50)

        if is_sp:
            fv = (base_score + whiff_bonus) * max(1, n_starts)
        else:
            fv = base_score + whiff_bonus + (sv_rate * 30)

        results.append({
            "id": pid, "name": pinfo["name"], "team": pinfo["team"],
            "pos": pos_label, "espn_pos": pos_label,
            "tier": tier, "archetype": archetype,
            "whiff_rate": round(whiff_rate, 4),
            "weekly": weekly, "yearly": yearly,
            "opponents": [s["opponent"] for s in starts],
            "fantasy_value": round(fv, 1),
        })

    results.sort(key=lambda x: x["fantasy_value"], reverse=True)
    return results


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("FANTASY PROJECTIONS — Building by position")
    print("=" * 60)

    print("\n[1/7] Fetching rosters...")
    players, team_list = fetch_all_rosters()

    print("\n[2/7] Fetching Week 1 schedule...")
    games = fetch_week_schedule()

    print("\n[3/7] Loading atlas data...")
    hitter_vs_cluster = load_atlas("hitter_vs_cluster.json")
    pitcher_tiers = load_atlas("pitcher_tiers.json")
    pitcher_seasons = load_atlas("pitcher_seasons.json")
    park_factors_raw = load_atlas("park_factors.json")
    sp_innings = load_atlas("sp_innings.json")

    # park_factors_raw is dict keyed by team abbreviation (COL, BOS, etc.)
    park_factors = park_factors_raw if isinstance(park_factors_raw, dict) else {}
    if isinstance(park_factors_raw, list):
        for pf in park_factors_raw:
            park_factors[pf.get("team", pf.get("abbreviation", ""))] = pf

    print("\n[4/7] Building indexes...")
    pitcher_idx = build_pitcher_archetype_index(pitcher_seasons, pitcher_tiers)
    batter_cluster_idx = build_batter_cluster_index(hitter_vs_cluster)
    batter_agg = build_batter_aggregate_index(hitter_vs_cluster)

    # Identify hitters and pitchers on active rosters
    hitter_ids = [pid for pid, p in players.items() if p["espn_pos"] != "P" and pid in batter_agg]
    pitcher_ids = [pid for pid, p in players.items() if p["espn_pos"] == "P"]

    print(f"\n[5/7] Fetching API stats ({len(hitter_ids)} hitters)...")
    hitter_api_stats = fetch_player_season_stats(hitter_ids)

    print(f"\n[6/7] Fetching pitcher API stats ({len(pitcher_ids)} pitchers)...")
    pitcher_api_stats = fetch_pitcher_season_stats(pitcher_ids)

    print("\n[7/7] Computing projections...")
    hitter_results = project_hitters(
        players, games, batter_cluster_idx, batter_agg,
        pitcher_idx, park_factors, hitter_api_stats
    )
    pitcher_results = project_pitchers(
        players, games, pitcher_idx, batter_cluster_idx, batter_agg,
        park_factors, pitcher_api_stats, sp_innings
    )

    # Group by position
    position_groups = defaultdict(list)
    for h in hitter_results:
        position_groups[h["espn_pos"]].append(h)
    for p in pitcher_results:
        position_groups[p["espn_pos"]].append(p)

    output = {
        "week_label": WEEK_LABEL,
        "week_start": WEEK_START,
        "week_end": WEEK_END,
        "season": SEASON,
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "positions": {},
    }

    pos_order = ["C", "1B", "2B", "3B", "SS", "OF", "SP", "RP", "UTIL"]
    for pos in pos_order:
        group = position_groups.get(pos, [])
        group.sort(key=lambda x: x["fantasy_value"], reverse=True)
        output["positions"][pos] = group[:TOP_N]
        count = len(group)
        top = group[0]["name"] if group else "—"
        print(f"  {pos:>4}: {count:>3} total → top {min(TOP_N, count)} (#{1}: {top})")

    save_atlas("fantasy_projections.json", output)
    print("\nDone!")


if __name__ == "__main__":
    main()

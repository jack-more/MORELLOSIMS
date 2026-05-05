#!/usr/bin/env python3
"""
07_fetch_bullpen.py — Build per-team bullpen quality + SP-innings tables.

Reads:  MLB Stats API (single bulk call to /stats with playerPool=ALL)
Writes:
  atlas/team_bullpen.json — per-team bullpen quality
    {team_id: {abbr, rp_ip, rp_er, rp_runs_per_ip, sp_avg_ip,
               vs_league_runs_per_ip, n_relievers, top_relievers: [...]}}
  atlas/sp_innings.json   — per-SP avg IP per start
    {pitcher_id: {name, avg_ip_per_start, gs}}

Formula used downstream by build_mlb_sim.py:
  bp_ip          = max(0, 9 - opp_sp_avg_ip_per_start)
  bp_run_delta   = bp_ip * (opp_team_bp_runs_per_ip - league_avg_runs_per_ip)
  team_runs_adj  = team_runs_raw + bp_run_delta

Positive bp_run_delta = batting team scores MORE because the opposing bullpen
is below league average. Negative = opposing bullpen is suppressive.

Replaces the old FanGraphs scraper (started returning 403 in April 2026).
Single MLB Stats API bulk call → all 500+ pitchers in one shot. SP/RP
classification is by gamesStarted/gamesPlayed ratio (>=50% = SP).
"""
import json
import os
import urllib.request
from collections import defaultdict
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATLAS_DIR = os.path.join(REPO_ROOT, "atlas")
TEAM_BULLPEN_OUT = os.path.join(ATLAS_DIR, "team_bullpen.json")
SP_INNINGS_OUT = os.path.join(ATLAS_DIR, "sp_innings.json")

SEASON = datetime.now().year
MLB_API = "https://statsapi.mlb.com/api/v1"
SP_RATIO_THRESHOLD = 0.5  # gamesStarted/gamesPlayed >= 0.5 → SP


def fetch(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read())


def fetch_teams_index() -> dict:
    """team_id → abbreviation."""
    data = fetch(f"{MLB_API}/teams?sportId=1&season={SEASON}")
    return {t["id"]: t.get("abbreviation", str(t["id"])) for t in data.get("teams", [])}


def fetch_all_pitchers() -> list[dict]:
    """One bulk call returns every pitcher with stats + team this season."""
    url = (
        f"{MLB_API}/stats?stats=season&group=pitching&season={SEASON}"
        f"&sportId=1&playerPool=ALL&limit=2000"
    )
    return fetch(url).get("stats", [{}])[0].get("splits", [])


def parse_innings(ip_str) -> float:
    """MLB API returns IP as e.g. '32.1' meaning 32 + 1/3 innings."""
    if ip_str in (None, "", 0):
        return 0.0
    s = str(ip_str)
    if "." in s:
        whole, frac = s.split(".")
        return float(whole) + (int(frac) / 3 if frac else 0)
    return float(s)


def main():
    print(f"Fetching bullpen data for {SEASON}...")
    teams = fetch_teams_index()
    print(f"  Teams: {len(teams)}")

    pitchers = fetch_all_pitchers()
    print(f"  Pitchers: {len(pitchers)}")

    team_data = defaultdict(lambda: {"rp_pitchers": [], "sp_pitchers": []})
    sp_innings = {}

    for split in pitchers:
        team = split.get("team") or {}
        team_id = team.get("id")
        if not team_id:
            continue
        player = split.get("player") or {}
        pid = player.get("id")
        name = player.get("fullName", "?")
        st = split.get("stat") or {}

        gs = int(st.get("gamesStarted") or 0)
        g = int(st.get("gamesPlayed") or 0)
        ip = parse_innings(st.get("inningsPitched"))
        er = int(st.get("earnedRuns") or 0)
        r = int(st.get("runs") or 0)
        bf = int(st.get("battersFaced") or 0)

        if g == 0 or ip == 0:
            continue

        is_sp = gs >= max(1, g * SP_RATIO_THRESHOLD)

        if is_sp and gs >= 3:
            avg_ip_per_start = ip / gs
            sp_innings[str(pid)] = {
                "name": name,
                "team_id": team_id,
                "team_abbr": teams.get(team_id, str(team_id)),
                "avg_ip_per_start": round(avg_ip_per_start, 2),
                "gs": gs,
            }
            team_data[team_id]["sp_pitchers"].append({
                "id": pid, "name": name, "ip": ip, "gs": gs,
                "avg_ip_per_start": round(avg_ip_per_start, 2),
            })
        elif not is_sp:
            team_data[team_id]["rp_pitchers"].append({
                "id": pid, "name": name, "ip": ip, "g": g,
                "er": er, "r": r, "bf": bf,
                "era": round((er * 9 / ip), 2) if ip else None,
                "runs_per_ip": round(r / ip, 4) if ip else None,
            })

    # Aggregate per-team bullpen + compute league baseline
    league_rp_ip = 0.0
    league_rp_runs = 0
    team_bullpen = {}

    for team_id, data in team_data.items():
        rps = data["rp_pitchers"]
        rp_ip = sum(p["ip"] for p in rps)
        rp_runs = sum(p["r"] for p in rps)
        rp_er = sum(p["er"] for p in rps)

        league_rp_ip += rp_ip
        league_rp_runs += rp_runs

        top = sorted(rps, key=lambda p: -p["ip"])[:5]

        sps = data["sp_pitchers"]
        sp_total_gs = sum(p["gs"] for p in sps)
        sp_avg_ip = (
            sum(p["ip"] for p in sps) / sp_total_gs
            if sps and sp_total_gs > 0 else 5.5
        )

        team_bullpen[str(team_id)] = {
            "abbr": teams.get(team_id, str(team_id)),
            "rp_ip": round(rp_ip, 1),
            "rp_runs": rp_runs,
            "rp_earned_runs": rp_er,
            "rp_runs_per_ip": round(rp_runs / rp_ip, 4) if rp_ip else None,
            "rp_era": round((rp_er * 9 / rp_ip), 2) if rp_ip else None,
            "n_relievers": len(rps),
            "sp_avg_ip_per_start": round(sp_avg_ip, 2),
            "top_relievers": [
                {"id": p["id"], "name": p["name"], "ip": round(p["ip"], 1),
                 "g": p["g"], "era": p["era"], "runs_per_ip": p["runs_per_ip"]}
                for p in top
            ],
        }

    league_runs_per_ip = round(league_rp_runs / league_rp_ip, 4) if league_rp_ip else 0.5

    for tid, t in team_bullpen.items():
        if t.get("rp_runs_per_ip") is not None:
            t["vs_league_runs_per_ip"] = round(t["rp_runs_per_ip"] - league_runs_per_ip, 4)
        else:
            t["vs_league_runs_per_ip"] = 0.0

    league_avg_sp_ip = round(
        sum(s["avg_ip_per_start"] * s["gs"] for s in sp_innings.values())
        / max(1, sum(s["gs"] for s in sp_innings.values())), 2
    ) if sp_innings else 5.5

    payload = {
        "_doc": "Per-team bullpen runs/IP + sp_avg_ip_per_start. Rebuilt daily by 07_fetch_bullpen.py.",
        "season": SEASON,
        "league_avg_rp_runs_per_ip": league_runs_per_ip,
        "league_avg_sp_ip_per_start": league_avg_sp_ip,
        "teams": team_bullpen,
        "generated_at": datetime.now().isoformat(),
    }

    os.makedirs(ATLAS_DIR, exist_ok=True)
    with open(TEAM_BULLPEN_OUT, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    with open(SP_INNINGS_OUT, "w") as f:
        json.dump(sp_innings, f, indent=2)

    print(f"\n  League avg bullpen runs/IP: {league_runs_per_ip:.3f}")
    print(f"  League avg SP IP/start:     {league_avg_sp_ip:.2f}")
    print(f"  Wrote {TEAM_BULLPEN_OUT}")
    print(f"  Wrote {SP_INNINGS_OUT}")

    sorted_teams = sorted(
        team_bullpen.items(),
        key=lambda x: x[1].get("rp_runs_per_ip") or 99,
    )
    print("\n  Best 3 bullpens (lowest runs/IP):")
    for _, t in sorted_teams[:3]:
        print(f"    {t['abbr']:4}  {t['rp_runs_per_ip']:.3f} R/IP   ERA {t['rp_era']:.2f}   ({t['n_relievers']} arms)")
    print("\n  Worst 3 bullpens (highest runs/IP):")
    for _, t in sorted_teams[-3:]:
        print(f"    {t['abbr']:4}  {t['rp_runs_per_ip']:.3f} R/IP   ERA {t['rp_era']:.2f}   ({t['n_relievers']} arms)")


if __name__ == "__main__":
    main()

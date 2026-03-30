#!/usr/bin/env python3
"""
refresh_atlas_2026.py — Daily cumulative Statcast refresh for the 2026 season.

Pulls ALL 2026 pitch-by-pitch data from Baseball Savant via pybaseball,
computes batter-vs-cluster matchup stats and pitcher season features,
then merges into the existing atlas files so the MLB SIM pipeline
uses current-season data.

Updates:
  - atlas/hitter_vs_cluster.json  (append/update 2026 records)
  - atlas/pitcher_seasons.json    (append/update 2026 records)
  - atlas/pitcher_siera.json      (append/update 2026 SIERA estimates)
  - atlas/pitcher_tiers.json      (recompute tiers including 2026)

Usage:
  python3 scripts/refresh_atlas_2026.py [--start 2026-03-25] [--end 2026-03-30]
  (defaults: season start through today)
"""

import json
import os
import sys
import argparse
from datetime import datetime, date, timedelta
from collections import defaultdict
import math

import numpy as np
import pandas as pd
from pybaseball import statcast

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
ATLAS_DIR = os.path.join(REPO_ROOT, "atlas")

SEASON = 2026
SEASON_START = "2026-03-25"

# ─── wOBA weights (2024 linear weights, standard) ────────────────────────────
WOBA_WEIGHTS = {
    "walk": 0.690,
    "hit_by_pitch": 0.722,
    "single": 0.878,
    "double": 1.242,
    "triple": 1.568,
    "home_run": 2.007,
}
WOBA_SCALE = 1.15  # wOBA scale factor


# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_atlas(filename):
    path = os.path.join(ATLAS_DIR, filename)
    with open(path, "r") as f:
        return json.load(f)


def save_atlas(filename, data):
    path = os.path.join(ATLAS_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"  Saved {path} ({os.path.getsize(path):,} bytes)")


def event_to_hit_type(event):
    """Classify Statcast event string into hit type."""
    if event is None or pd.isna(event):
        return None
    event = str(event).lower()
    if event == "single":
        return "single"
    elif event == "double":
        return "double"
    elif event == "triple":
        return "triple"
    elif event == "home_run":
        return "home_run"
    elif event in ("walk", "intent_walk"):
        return "walk"
    elif event == "hit_by_pitch":
        return "hit_by_pitch"
    elif event in ("strikeout", "strikeout_double_play"):
        return "strikeout"
    elif event in (
        "field_out", "grounded_into_double_play", "force_out",
        "double_play", "fielders_choice", "fielders_choice_out",
        "sac_fly", "sac_bunt", "sac_fly_double_play",
        "triple_play", "sac_bunt_double_play",
    ):
        return "out"
    elif event in ("field_error", "catcher_interf"):
        return "other"
    return "other"


def compute_woba(pa_events):
    """Compute wOBA from a list of event type strings."""
    numerator = 0.0
    denominator = 0
    for ev in pa_events:
        if ev in WOBA_WEIGHTS:
            numerator += WOBA_WEIGHTS[ev]
            denominator += 1
        elif ev in ("strikeout", "out"):
            denominator += 1
        # walks, HBP already handled above; "other" doesn't count
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


# ─── Step 1: Pull Statcast ───────────────────────────────────────────────────

def pull_statcast(start_date, end_date):
    """Pull all Statcast data for the date range."""
    print(f"\n{'='*60}")
    print(f"PULLING STATCAST: {start_date} → {end_date}")
    print(f"{'='*60}")

    # pybaseball works best in chunks of ~7 days
    all_dfs = []
    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    while current <= end:
        chunk_end = min(current + timedelta(days=6), end)
        s = current.strftime("%Y-%m-%d")
        e = chunk_end.strftime("%Y-%m-%d")
        print(f"  Fetching {s} → {e}...")
        try:
            df = statcast(s, e)
            if df is not None and len(df) > 0:
                all_dfs.append(df)
                print(f"    → {len(df)} pitches")
        except Exception as ex:
            print(f"    WARN: Failed to fetch {s}→{e}: {ex}")
        current = chunk_end + timedelta(days=1)

    if not all_dfs:
        print("  ERROR: No Statcast data retrieved!")
        return None

    df = pd.concat(all_dfs, ignore_index=True)
    # Filter to regular season only
    df = df[df["game_type"] == "R"]
    print(f"\n  Total pitches (regular season): {len(df)}")
    print(f"  Unique pitchers: {df['pitcher'].nunique()}")
    print(f"  Unique batters: {df['batter'].nunique()}")
    return df


# ─── Step 2: Build pitcher cluster index from existing atlas ─────────────────

def build_pitcher_cluster_index():
    """
    Build pitcher_id → cluster mapping from pitcher_seasons.json.
    Uses most recent year available for each pitcher.
    """
    pitcher_seasons = load_atlas("pitcher_seasons.json")
    idx = {}
    for ps in pitcher_seasons:
        pid = ps["pitcher"]
        yr = ps["game_year"]
        if pid not in idx or yr > idx[pid]["game_year"]:
            idx[pid] = ps
    print(f"  Pitcher cluster index: {len(idx)} pitchers (latest year per pitcher)")
    return idx


# ─── Step 3: Compute hitter-vs-cluster stats for 2026 ───────────────────────

def compute_hitter_vs_cluster(df, pitcher_idx):
    """
    For each (batter, pitcher_cluster) pair in the 2026 data,
    compute PA, AB, H, HR, BB, K, wOBA, etc.
    """
    print(f"\n{'='*60}")
    print(f"COMPUTING HITTER VS CLUSTER (2026)")
    print(f"{'='*60}")

    # Map each pitch to pitcher's cluster
    def get_cluster(pid):
        ps = pitcher_idx.get(pid)
        return ps["cluster"] if ps else None

    df = df.copy()
    df["cluster"] = df["pitcher"].map(get_cluster)

    # Filter to pitches where we know the cluster
    known = df[df["cluster"].notna()]
    unknown_pitchers = df[df["cluster"].isna()]["pitcher"].nunique()
    print(f"  Pitches with known cluster: {len(known)}/{len(df)}")
    print(f"  Pitchers without cluster assignment: {unknown_pitchers}")

    # Get plate appearance outcomes (rows where events is not null = end of PA)
    pa_df = known[known["events"].notna()].copy()
    pa_df["hit_type"] = pa_df["events"].apply(event_to_hit_type)
    print(f"  Plate appearances: {len(pa_df)}")

    # Also compute whiff rate per batter-cluster from all pitches
    known["is_whiff"] = known["description"].isin([
        "swinging_strike", "swinging_strike_blocked",
        "foul_tip",  # foul tips that are strikes
    ])
    known["is_swing"] = known["description"].isin([
        "swinging_strike", "swinging_strike_blocked", "foul_tip",
        "foul", "foul_bunt", "hit_into_play", "hit_into_play_no_out",
        "hit_into_play_score",
    ])
    whiff_agg = known.groupby(["batter", "cluster"]).agg(
        whiffs=("is_whiff", "sum"),
        swings=("is_swing", "sum"),
        pitches_seen=("pitch_type", "count"),
    ).reset_index()

    # Group PA outcomes by batter × cluster
    records = []
    for (batter_id, cluster_id), group in pa_df.groupby(["batter", "cluster"]):
        events = group["hit_type"].tolist()
        stand = group["stand"].iloc[0] if len(group) > 0 else "R"
        batter_name = group["player_name"].iloc[0] if "player_name" in group.columns else ""
        # Sometimes player_name is the pitcher's name in Statcast; use batter lookup
        # We'll fix names later

        singles = events.count("single")
        doubles = events.count("double")
        triples = events.count("triple")
        hr = events.count("home_run")
        bb = events.count("walk")
        hbp = events.count("hit_by_pitch")
        k = events.count("strikeout")
        outs = events.count("out")

        h = singles + doubles + triples + hr
        ab = h + k + outs  # AB excludes BB, HBP, sac
        pa = len(events)

        ba = round(h / ab, 4) if ab > 0 else 0.0
        obp = round((h + bb + hbp) / pa, 4) if pa > 0 else 0.0
        tb = singles + 2 * doubles + 3 * triples + 4 * hr
        slg = round(tb / ab, 4) if ab > 0 else 0.0
        k_pct = round(k / pa, 4) if pa > 0 else 0.0
        bb_pct = round(bb / pa, 4) if pa > 0 else 0.0

        woba = compute_woba(events)
        if woba is None:
            woba = 0.0

        # Get whiff rate
        wh = whiff_agg[
            (whiff_agg["batter"] == batter_id) &
            (whiff_agg["cluster"] == cluster_id)
        ]
        if len(wh) > 0:
            swings = int(wh.iloc[0]["swings"])
            whiff_rate_vs = round(
                int(wh.iloc[0]["whiffs"]) / swings, 4
            ) if swings > 0 else 0.0
            pitches = int(wh.iloc[0]["pitches_seen"])
        else:
            whiff_rate_vs = 0.0
            pitches = 0

        records.append({
            "batter": int(batter_id),
            "batter_name": "",  # will fill from Statcast batter lookup
            "game_year": SEASON,
            "cluster": str(cluster_id),
            "stand": stand,
            "PA": float(pa),
            "AB": float(ab),
            "H": float(h),
            "HR": float(hr),
            "BB": float(bb),
            "K": float(k),
            "HBP": float(hbp),
            "BA": ba,
            "OBP": obp,
            "SLG": slg,
            "K_pct": k_pct,
            "BB_pct": bb_pct,
            "wOBA": woba,
            "pitches_seen": float(pitches),
            "whiff_rate_vs": whiff_rate_vs,
            "singles": float(singles),
            "doubles": float(doubles),
            "triples": float(triples),
        })

    print(f"  Generated {len(records)} batter-vs-cluster records for 2026")
    return records


# ─── Step 4: Build batter name lookup ────────────────────────────────────────

def build_batter_names(df):
    """
    Statcast player_name column is the PITCHER name. We need batter names.
    Use the MLB Stats API or existing batters.json.
    """
    # Load existing batters for known names
    try:
        batters = load_atlas("batters.json")
        name_map = {b["batter"]: b["batter_name"] for b in batters}
    except Exception:
        name_map = {}

    # Also try to get names from existing hitter_vs_cluster
    try:
        hvc = load_atlas("hitter_vs_cluster.json")
        for r in hvc:
            if r["batter"] not in name_map and r.get("batter_name"):
                name_map[r["batter"]] = r["batter_name"]
    except Exception:
        pass

    # For any missing, try MLB Stats API
    missing = set(df["batter"].unique()) - set(name_map.keys())
    if missing:
        print(f"  Looking up {len(missing)} batter names from MLB API...")
        import requests
        for pid in missing:
            try:
                resp = requests.get(
                    f"https://statsapi.mlb.com/api/v1/people/{pid}",
                    timeout=10,
                )
                if resp.ok:
                    data = resp.json()
                    ppl = data.get("people", [])
                    if ppl:
                        name_map[pid] = ppl[0]["fullName"].lower()
            except Exception:
                pass

    return name_map


# ─── Step 5: Compute pitcher season features for 2026 ───────────────────────

def compute_pitcher_seasons(df, pitcher_idx):
    """
    Compute 2026 pitcher-season features from Statcast data.
    For known pitchers, inherit cluster from their most recent season.
    """
    print(f"\n{'='*60}")
    print(f"COMPUTING PITCHER SEASONS (2026)")
    print(f"{'='*60}")

    records = []
    for pid, group in df.groupby("pitcher"):
        prev = pitcher_idx.get(int(pid))

        # Pitch mix features
        pitches = group["pitch_type"].value_counts(normalize=True)
        velo = group.loc[
            group["pitch_type"].isin(["FF", "SI"]), "release_speed"
        ]
        avg_velo = round(float(velo.mean()), 1) if len(velo) > 0 else 0.0

        # Whiff rate
        swings = group[group["description"].isin([
            "swinging_strike", "swinging_strike_blocked", "foul_tip",
            "foul", "foul_bunt", "hit_into_play", "hit_into_play_no_out",
            "hit_into_play_score",
        ])]
        whiffs = group[group["description"].isin([
            "swinging_strike", "swinging_strike_blocked",
        ])]
        whiff_rate = round(len(whiffs) / len(swings), 4) if len(swings) > 0 else 0.0

        # Spin
        spin = group["release_spin_rate"].dropna()
        avg_spin = round(float(spin.mean()), 1) if len(spin) > 0 else 0.0

        # Movement
        pfx_x = group["pfx_x"].dropna()
        pfx_z = group["pfx_z"].dropna()
        avg_pfx_x = round(float(pfx_x.mean()), 4) if len(pfx_x) > 0 else 0.0
        avg_pfx_z = round(float(pfx_z.mean()), 4) if len(pfx_z) > 0 else 0.0

        # Groundball rate (from batted balls)
        batted = group[group["bb_type"].notna()]
        gb = batted[batted["bb_type"] == "ground_ball"]
        gb_rate = round(len(gb) / len(batted), 4) if len(batted) > 0 else 0.0

        # Is SP? Check if they started (at_bat_number == 1 means first AB of game)
        p_throws = group["p_throws"].iloc[0] if len(group) > 0 else "R"
        is_rhp = 1 if p_throws == "R" else 0

        # Pitcher name from Statcast (player_name IS the pitcher name in statcast)
        pitcher_name = group["player_name"].iloc[0] if len(group) > 0 else ""
        # Statcast format: "Last, First"
        pitcher_name = str(pitcher_name)

        # Inherit cluster and other fields from previous season
        if prev:
            cluster = prev["cluster"]
            archetype = prev.get("archetype", "")
            pca_x = prev.get("pca_x", 0)
            pca_y = prev.get("pca_y", 0)
            pca_z = prev.get("pca_z", 0)
            is_sp = prev.get("is_sp", 0)
            arm_angle = prev.get("arm_angle", 0)
            gmm_proba = prev.get("gmm_proba", {})
        else:
            # Unknown pitcher — assign to generic cluster
            cluster = f"{'R' if is_rhp else 'L'}_UT"
            archetype = "Untyped"
            pca_x = 0
            pca_y = 0
            pca_z = 0
            is_sp = 0
            arm_angle = 0
            gmm_proba = {cluster: 1.0}

        records.append({
            "pitcher": int(pid),
            "player_name": pitcher_name,
            "game_year": SEASON,
            "is_rhp": is_rhp,
            "is_sp": is_sp,
            "cluster": cluster,
            "archetype": archetype,
            "pca_x": pca_x,
            "pca_y": pca_y,
            "pca_z": pca_z,
            "avg_velo_FF": avg_velo,
            "whiff_rate": whiff_rate,
            "arm_angle": arm_angle,
            "pfx_x_avg": avg_pfx_x,
            "pfx_z_avg": avg_pfx_z,
            "gmm_proba": gmm_proba,
        })

    print(f"  Generated {len(records)} pitcher-season records for 2026")
    known = sum(1 for r in records if r["archetype"] != "Untyped")
    print(f"  Known cluster: {known}, Untyped: {len(records) - known}")
    return records


# ─── Step 6: Estimate SIERA for 2026 pitchers ───────────────────────────────

def compute_siera_estimates(df, pitcher_seasons_2026):
    """
    Estimate SIERA from Statcast data for 2026 pitchers.
    SIERA ≈ f(K%, BB%, GB/FB ratio).
    Uses the simplified SIERA formula.
    """
    print(f"\n{'='*60}")
    print(f"ESTIMATING SIERA (2026)")
    print(f"{'='*60}")

    records = {}
    for pid, group in df.groupby("pitcher"):
        # Only pitches that ended a PA
        pa_pitches = group[group["events"].notna()]
        if len(pa_pitches) < 5:
            continue

        events = pa_pitches["events"]
        total_pa = len(events)
        k = events.isin(["strikeout", "strikeout_double_play"]).sum()
        bb = events.isin(["walk", "intent_walk"]).sum()

        k_pct = k / total_pa if total_pa > 0 else 0
        bb_pct = bb / total_pa if total_pa > 0 else 0

        # GB/FB ratio from batted balls
        batted = group[group["bb_type"].notna()]
        gb = (batted["bb_type"] == "ground_ball").sum()
        fb = (batted["bb_type"] == "fly_ball").sum()
        gb_fb = gb / fb if fb > 0 else 1.0

        # Simplified SIERA formula:
        # SIERA ≈ 6.145 - 16.986*(K%) + 11.434*(BB%) - 1.858*(GB/FB)
        #        + 7.653*(K%^2) + 6.664*(BB%^2) + 0.9*(GB/FB^2)
        #        - 2.0*(K%*GB/FB) + 0.1*(BB%*GB/FB)
        siera = (
            6.145
            - 16.986 * k_pct
            + 11.434 * bb_pct
            - 1.858 * (gb_fb / (gb_fb + 1))  # normalize
            + 7.653 * (k_pct ** 2)
            + 6.664 * (bb_pct ** 2)
        )
        # Clamp to reasonable range
        siera = max(1.5, min(7.0, siera))

        pitcher_name = str(group["player_name"].iloc[0])

        # Estimate ERA from earned runs (rough)
        outs = events.isin([
            "field_out", "grounded_into_double_play", "force_out",
            "double_play", "fielders_choice", "fielders_choice_out",
            "strikeout", "strikeout_double_play", "sac_fly",
            "sac_bunt", "triple_play",
        ]).sum()
        ip = outs / 3.0 if outs > 0 else 0

        key = f"{int(pid)}_{SEASON}"
        records[key] = {
            "pitcher": int(pid),
            "player_name": pitcher_name,
            "game_year": SEASON,
            "era": round(siera + 0.3, 2),  # rough ERA estimate from SIERA
            "siera": round(siera, 2),
            "ip": round(ip, 1),
            "k_pct": round(k_pct, 4),
            "bb_pct": round(bb_pct, 4),
            "gb_fb": round(gb_fb, 2),
        }

    print(f"  Estimated SIERA for {len(records)} pitchers")
    return records


# ─── Step 7: Merge into existing atlas ───────────────────────────────────────

def merge_hitter_vs_cluster(new_records):
    """Replace all 2026 records, keep everything else."""
    print(f"\n  Merging hitter_vs_cluster...")
    existing = load_atlas("hitter_vs_cluster.json")

    # Remove old 2026 records
    kept = [r for r in existing if r.get("game_year") != SEASON]
    print(f"    Existing records (non-2026): {len(kept)}")
    print(f"    New 2026 records: {len(new_records)}")

    merged = kept + new_records
    save_atlas("hitter_vs_cluster.json", merged)
    return len(new_records)


def merge_pitcher_seasons(new_records):
    """Replace all 2026 records, keep everything else."""
    print(f"\n  Merging pitcher_seasons...")
    existing = load_atlas("pitcher_seasons.json")

    kept = [r for r in existing if r.get("game_year") != SEASON]
    print(f"    Existing records (non-2026): {len(kept)}")
    print(f"    New 2026 records: {len(new_records)}")

    merged = kept + new_records
    save_atlas("pitcher_seasons.json", merged)
    return len(new_records)


def merge_pitcher_siera(new_records):
    """Replace all 2026 SIERA records, keep everything else."""
    print(f"\n  Merging pitcher_siera...")
    existing = load_atlas("pitcher_siera.json")

    # Remove old 2026 entries
    kept = {k: v for k, v in existing.items() if v.get("game_year") != SEASON}
    print(f"    Existing records (non-2026): {len(kept)}")
    print(f"    New 2026 records: {len(new_records)}")

    kept.update(new_records)
    save_atlas("pitcher_siera.json", kept)
    return len(new_records)


# ─── Step 8: Recompute pitcher tiers ─────────────────────────────────────────

# Tier assignment thresholds (z-score based)
TIER_THRESHOLDS = [
    (1.0, "T1_Apex"),
    (0.0, "T2_Core"),
    (-1.0, "T3_Standard"),
]
DEFAULT_TIER = "T4_Fringe"

BASE_TIER_MULTIPLIERS = {
    "T1_Apex": 0.87,
    "T2_Core": 0.95,
    "T3_Standard": 1.00,
    "T4_Fringe": 1.10,
}

BAYESIAN_PRIOR_WEIGHT = 5


def assign_tier(z_score):
    for threshold, tier in TIER_THRESHOLDS:
        if z_score >= threshold:
            return tier
    return DEFAULT_TIER


def recompute_pitcher_tiers():
    """Rerun tier assignment including 2026 data."""
    print(f"\n{'='*60}")
    print(f"RECOMPUTING PITCHER TIERS")
    print(f"{'='*60}")

    pitcher_seasons = load_atlas("pitcher_seasons.json")
    siera_data = load_atlas("pitcher_siera.json")

    # Build SIERA index
    siera_idx = {}
    for key, rec in siera_data.items():
        pid = rec.get("pitcher")
        yr = rec.get("game_year")
        if pid and yr:
            siera_idx[(pid, yr)] = rec.get("siera")

    # Match SIERA to pitcher-seasons
    matched = 0
    for ps in pitcher_seasons:
        siera = siera_idx.get((ps["pitcher"], ps["game_year"]))
        if siera is not None:
            ps["siera"] = siera
            matched += 1
        else:
            ps["siera"] = None

    print(f"  SIERA matched: {matched}/{len(pitcher_seasons)}")

    # Group by cluster
    by_cluster = defaultdict(list)
    for ps in pitcher_seasons:
        if ps["siera"] is not None:
            by_cluster[ps["cluster"]].append(ps)

    # Global stats
    all_siera = [ps["siera"] for ps in pitcher_seasons if ps["siera"] is not None]
    global_mean = np.mean(all_siera)
    global_stdev = np.std(all_siera, ddof=1)

    # Assign tiers
    tiers_output = {}
    for cluster_id, records in sorted(by_cluster.items()):
        sieras = [r["siera"] for r in records]
        n = len(sieras)
        if n == 0:
            continue
        cluster_mean = np.mean(sieras)
        cluster_stdev = np.std(sieras, ddof=1) if n > 1 else global_stdev
        effective_stdev = (
            (n * cluster_stdev + BAYESIAN_PRIOR_WEIGHT * global_stdev)
            / (n + BAYESIAN_PRIOR_WEIGHT)
        )
        arch_siera = cluster_mean

        for r in records:
            z = -(r["siera"] - cluster_mean) / effective_stdev if effective_stdev > 0 else 0.0
            tier = assign_tier(z)
            base_mult = BASE_TIER_MULTIPLIERS[tier]
            dominance = global_mean / arch_siera if arch_siera > 0 else 1.0
            eff_mult = 1.0 + (base_mult - 1.0) * dominance

            key = f"{r['pitcher']}_{r['game_year']}"
            tiers_output[key] = {
                "pitcher": r["pitcher"],
                "player_name": r.get("player_name", ""),
                "game_year": r["game_year"],
                "cluster": cluster_id,
                "archetype": r.get("archetype", ""),
                "siera": round(r["siera"], 2),
                "whiff_rate": round(r.get("whiff_rate", 0), 4),
                "z_score": round(z, 4),
                "tier": tier,
                "base_multiplier": base_mult,
                "effective_multiplier": round(eff_mult, 4),
                "archetype_dominance": round(dominance, 4),
            }

    save_atlas("pitcher_tiers.json", tiers_output)

    # Count 2026 entries
    count_2026 = sum(1 for v in tiers_output.values() if v["game_year"] == SEASON)
    print(f"  Total tiers: {len(tiers_output)}, 2026 entries: {count_2026}")
    return count_2026


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Refresh atlas with 2026 Statcast data")
    parser.add_argument("--start", default=SEASON_START, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=date.today().strftime("%Y-%m-%d"), help="End date")
    args = parser.parse_args()

    print(f"\n{'#'*60}")
    print(f"  ATLAS 2026 REFRESH")
    print(f"  Range: {args.start} → {args.end}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")

    # 1. Pull Statcast
    df = pull_statcast(args.start, args.end)
    if df is None or len(df) == 0:
        print("No data available. Exiting.")
        sys.exit(1)

    # 2. Build pitcher cluster index from existing data
    pitcher_idx = build_pitcher_cluster_index()

    # 3. Build batter name lookup
    name_map = build_batter_names(df)

    # 4. Compute hitter-vs-cluster for 2026
    hvc_records = compute_hitter_vs_cluster(df, pitcher_idx)
    # Fill in batter names
    for r in hvc_records:
        r["batter_name"] = name_map.get(r["batter"], "")

    # 5. Compute pitcher seasons for 2026
    ps_records = compute_pitcher_seasons(df, pitcher_idx)

    # 6. Estimate SIERA
    siera_records = compute_siera_estimates(df, ps_records)

    # 7. Merge everything
    print(f"\n{'='*60}")
    print(f"MERGING INTO ATLAS")
    print(f"{'='*60}")
    n_hvc = merge_hitter_vs_cluster(hvc_records)
    n_ps = merge_pitcher_seasons(ps_records)
    n_siera = merge_pitcher_siera(siera_records)

    # 8. Recompute tiers
    n_tiers = recompute_pitcher_tiers()

    # Summary
    print(f"\n{'#'*60}")
    print(f"  REFRESH COMPLETE")
    print(f"  hitter_vs_cluster: +{n_hvc} records")
    print(f"  pitcher_seasons:   +{n_ps} records")
    print(f"  pitcher_siera:     +{n_siera} records")
    print(f"  pitcher_tiers:     {n_tiers} entries for 2026")
    print(f"{'#'*60}\n")


if __name__ == "__main__":
    main()

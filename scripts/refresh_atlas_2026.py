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
import re
import urllib.request
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

CLUSTER_FEATURE_WEIGHTS = {
    "avg_velo_FF": 1.20,
    "whiff_rate": 1.30,
    "pfx_x_avg": 1.00,
    "pfx_z_avg": 1.00,
    "groundball_rate": 0.90,
    "spin_overall": 0.70,
}

CLUSTER_FALLBACK_SCALES = {
    "avg_velo_FF": 2.5,
    "whiff_rate": 0.055,
    "pfx_x_avg": 0.50,
    "pfx_z_avg": 0.28,
    "groundball_rate": 0.16,
    "spin_overall": 250.0,
}

CLUSTER_PROBA_TEMP = 0.65
CLUSTER_TOP_N = 3

HEATER_TYPES = {"FF", "FA", "SI", "FC"}
CURVE_TYPES = {"CU", "KC"}
SLIDER_TYPES = {"SL", "ST", "SV"}
CHANGE_TYPES = {"CH"}
SPLIT_TYPES = {"FS", "FO", "SC"}
KNUCKLE_TYPES = {"KN"}

PITCH_FAMILY_MINIMUMS = {
    "Split Demon": ("split", 0.08),
    "Ghost": ("split_or_change", 0.08),
    "Uncle Charlie": ("curve", 0.10),
    "Knuckleball Wizard": ("knuckle", 0.05),
    "Cutman": ("cutter", 0.12),
    "Boomerang": ("slider", 0.12),
    "Yakker": ("breaking", 0.12),
}


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


def parse_float(value):
    if value in (None, "", "-.--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_innings(value):
    if value in (None, ""):
        return None
    whole, _, frac = str(value).partition(".")
    try:
        outs = int(whole) * 3 + (int(frac) if frac else 0)
    except ValueError:
        return None
    return outs / 3.0


def fetch_mlb_pitching_stats(season=SEASON):
    """Return real MLB season pitching stats keyed by player id."""
    url = (
        "https://statsapi.mlb.com/api/v1/stats"
        f"?stats=season&group=pitching&season={season}&playerPool=ALL&limit=5000"
    )
    print(f"\nFetching real MLB pitching stats for {season}...")
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.load(resp)

    stats = {}
    splits = data.get("stats", [{}])[0].get("splits", [])
    for split in splits:
        player = split.get("player", {})
        pid = player.get("id")
        stat = split.get("stat", {})
        if not pid:
            continue

        bf = parse_float(stat.get("battersFaced"))
        strikeouts = parse_float(stat.get("strikeOuts"))
        walks = parse_float(stat.get("baseOnBalls"))
        intentional_walks = parse_float(stat.get("intentionalWalks"))
        k_pct = (strikeouts / bf) if bf else None
        bb_pct = (walks / bf) if bf else None
        kbb_pct = (k_pct - bb_pct) if k_pct is not None and bb_pct is not None else None

        stats[int(pid)] = {
            "player_name": player.get("fullName", ""),
            "era": parse_float(stat.get("era")),
            "whip": parse_float(stat.get("whip")),
            "ip": parse_innings(stat.get("inningsPitched")),
            "k_pct": k_pct,
            "bb_pct": bb_pct,
            "kbb_pct": kbb_pct,
            "strikeouts": int(strikeouts or 0),
            "walks": int(walks or 0),
            "intentional_walks": int(intentional_walks or 0),
            "batters_faced": int(bf or 0),
            "ground_outs": int(parse_float(stat.get("groundOuts")) or 0),
            "air_outs": int(parse_float(stat.get("airOuts")) or 0),
            "games_started": int(parse_float(stat.get("gamesStarted")) or 0),
        }

    print(f"  MLB pitching stats loaded: {len(stats)} pitchers")
    return stats


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


def _median_or_none(values):
    clean = [v for v in values if isinstance(v, (int, float)) and not pd.isna(v)]
    if not clean:
        return None
    return float(np.median(clean))


def build_cluster_assignment_model():
    """
    Build fixed cluster profiles from the historical atlas.

    We do not have the original saved GMM/PCA/scaler artifacts in this repo, so
    current-year assignment uses normalized distance to the existing archetype
    profiles. It is still a true current-year recluster: 2026 pitchers are scored
    from their 2026 Statcast features instead of inheriting last year's bucket.
    """
    clusters_meta = load_atlas("clusters.json")
    pitcher_seasons = load_atlas("pitcher_seasons.json")

    by_cluster = defaultdict(list)
    all_values = defaultdict(list)
    for ps in pitcher_seasons:
        if ps.get("game_year") == SEASON:
            continue
        cid = ps.get("cluster")
        if not cid:
            continue
        by_cluster[cid].append(ps)
        for f in CLUSTER_FEATURE_WEIGHTS:
            v = ps.get(f)
            if isinstance(v, (int, float)) and not pd.isna(v):
                if f != "arm_angle" and v == 0:
                    continue
                all_values[f].append(float(v))

    scales = {}
    for f, fallback in CLUSTER_FALLBACK_SCALES.items():
        vals = all_values.get(f) or []
        stdev = float(np.std(vals)) if len(vals) >= 2 else 0.0
        scales[f] = stdev if stdev > 0 else fallback

    profiles = {}
    for cid, meta in clusters_meta.items():
        rows = by_cluster.get(cid, [])
        profile = {
            "cluster": cid,
            "hand": meta.get("hand") or ("RHP" if cid.startswith("R_") else "LHP"),
            "archetype": _cluster_short_label(cid, clusters_meta),
        }

        for f in CLUSTER_FEATURE_WEIGHTS:
            hist_val = _median_or_none([r.get(f) for r in rows])
            meta_val = meta.get(f)
            if hist_val is not None:
                profile[f] = hist_val
            elif isinstance(meta_val, (int, float)) and not pd.isna(meta_val):
                profile[f] = float(meta_val)

        for f in ("pca_x", "pca_y", "pca_z"):
            meta_val = meta.get(f)
            if isinstance(meta_val, (int, float)) and not pd.isna(meta_val):
                profile[f] = float(meta_val)

        # These are only available in clusters.json, not older pitcher_seasons.
        for f in ("groundball_rate", "spin_overall"):
            meta_val = meta.get(f)
            if isinstance(meta_val, (int, float)) and not pd.isna(meta_val):
                profile[f] = float(meta_val)

        profiles[cid] = profile

    print(f"  Cluster assignment profiles: {len(profiles)} clusters")
    return profiles, scales, clusters_meta


def _cluster_distance(features, profile, scales):
    weighted = 0.0
    total_weight = 0.0
    for f, weight in CLUSTER_FEATURE_WEIGHTS.items():
        fv = features.get(f)
        pv = profile.get(f)
        if not isinstance(fv, (int, float)) or not isinstance(pv, (int, float)):
            continue
        if pd.isna(fv) or pd.isna(pv):
            continue
        if f != "arm_angle" and fv == 0:
            continue
        scale = scales.get(f) or CLUSTER_FALLBACK_SCALES[f]
        z = (float(fv) - float(pv)) / scale
        weighted += weight * z * z
        total_weight += weight

    if total_weight == 0:
        return float("inf")
    return weighted / total_weight


def compute_pitch_mix(group):
    counts = group["pitch_type"].dropna().astype(str).value_counts()
    total = int(counts.sum())
    if total == 0:
        return {}
    return {
        pitch: round(int(count) / total, 4)
        for pitch, count in counts.items()
        if pitch != "PO"
    }


def _mix_share(pitch_mix, pitch_types):
    return sum(float(pitch_mix.get(pt, 0.0)) for pt in pitch_types)


def _mix_family_share(pitch_mix, family):
    if family == "heater":
        return _mix_share(pitch_mix, HEATER_TYPES)
    if family == "cutter":
        return _mix_share(pitch_mix, {"FC"})
    if family == "curve":
        return _mix_share(pitch_mix, CURVE_TYPES)
    if family == "slider":
        return _mix_share(pitch_mix, SLIDER_TYPES)
    if family == "breaking":
        return _mix_share(pitch_mix, CURVE_TYPES | SLIDER_TYPES)
    if family == "split":
        return _mix_share(pitch_mix, SPLIT_TYPES)
    if family == "change":
        return _mix_share(pitch_mix, CHANGE_TYPES)
    if family == "split_or_change":
        return _mix_share(pitch_mix, SPLIT_TYPES | CHANGE_TYPES)
    if family == "knuckle":
        return _mix_share(pitch_mix, KNUCKLE_TYPES)
    return 0.0


def _active_pitch_count(pitch_mix, threshold=0.05):
    return sum(1 for share in pitch_mix.values() if share >= threshold)


def _active_family_count(pitch_mix, threshold=0.05):
    families = (
        "heater",
        "curve",
        "slider",
        "split",
        "change",
        "knuckle",
    )
    return sum(1 for family in families if _mix_family_share(pitch_mix, family) >= threshold)


def _pitch_family_penalty(features, profile):
    """Return inf for pitch-family impossible labels, otherwise a soft penalty."""
    pitch_mix = features.get("pitch_mix") or {}
    if not pitch_mix:
        return 0.0

    label = profile.get("archetype") or ""
    for name, (family, minimum) in PITCH_FAMILY_MINIMUMS.items():
        if name in label and _mix_family_share(pitch_mix, family) < minimum:
            return float("inf")

    heater = _mix_family_share(pitch_mix, "heater")
    split_or_change = _mix_family_share(pitch_mix, "split_or_change")
    breaking = _mix_family_share(pitch_mix, "breaking")
    active_pitches = _active_pitch_count(pitch_mix)
    active_families = _active_family_count(pitch_mix)
    heater_dominant = heater >= 0.75 and split_or_change < 0.08 and breaking < 0.18

    if "Heater-Heavy" in label:
        if heater_dominant:
            return -0.45
        return -0.18 if heater >= 0.60 else 0.25
    if "Kitchen Sink" in label:
        if heater_dominant:
            return 0.25
        return -0.12 if active_pitches >= 4 and active_families >= 3 else 0.20
    if "Triple Threat" in label:
        return -0.08 if active_pitches >= 3 else 0.15
    if "Snake" in label and _mix_family_share(pitch_mix, "slider") >= 0.10:
        return -0.06
    return 0.0


def assign_current_cluster(features, profiles, scales):
    """Assign a 2026 pitcher to the nearest existing archetype profile."""
    hand = "RHP" if features.get("is_rhp", 1) else "LHP"
    candidates = [
        (cid, profile)
        for cid, profile in profiles.items()
        if profile.get("hand") == hand
    ]
    if not candidates:
        candidates = list(profiles.items())

    ranked = []
    for cid, profile in candidates:
        distance = _cluster_distance(features, profile, scales)
        penalty = _pitch_family_penalty(features, profile)
        ranked.append((cid, distance + penalty))
    ranked = sorted(ranked, key=lambda item: item[1])
    ranked = [(cid, d) for cid, d in ranked if math.isfinite(d)]
    if not ranked:
        fallback = f"{'R' if hand == 'RHP' else 'L'}_UT"
        return fallback, {fallback: 1.0}

    top = ranked[:CLUSTER_TOP_N]
    best = top[0][0]

    raw = [math.exp(-d / CLUSTER_PROBA_TEMP) for _, d in top]
    total = sum(raw) or 1.0
    proba = {
        cid: round(score / total, 4)
        for (cid, _), score in zip(top, raw)
    }
    return best, proba


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


# ─── Step 4b: Compute hitter season totals for 2026 ─────────────────────────

def compute_hitter_seasons(df, name_map):
    """Compute 2026 season-to-date stats per batter from Statcast data.
    Returns one record per batter with PA/H/HR/BB/K/wOBA accumulated for 2026.
    """
    print(f"\n{'='*60}")
    print(f"COMPUTING HITTER SEASONS (2026)")
    print(f"{'='*60}")

    # PA outcomes only (rows where events is set = end of plate appearance)
    pa_df = df[df["events"].notna()].copy()
    pa_df["hit_type"] = pa_df["events"].apply(event_to_hit_type)
    print(f"  Plate appearances: {len(pa_df)}")

    records = []
    for bid, group in pa_df.groupby("batter"):
        events = group["hit_type"].tolist()
        singles = events.count("single")
        doubles = events.count("double")
        triples = events.count("triple")
        hr = events.count("home_run")
        bb = events.count("walk")
        k = events.count("strikeout")
        h = singles + doubles + triples + hr
        woba = compute_woba(events)

        records.append({
            "batter": int(bid),
            "batter_name": name_map.get(int(bid), ""),
            "season_PA_2026": float(len(events)),
            "season_H_2026": float(h),
            "season_HR_2026": float(hr),
            "season_BB_2026": float(bb),
            "season_K_2026": float(k),
            "season_wOBA_2026": float(woba) if woba is not None else 0.0,
        })

    print(f"  Generated {len(records)} hitter-season records for 2026")
    return records


def merge_batters(new_records, name_map):
    """Update batters.json with 2026 season data.

    Schema upgrade (one-time, on first refresh after this code lands):
      - Snapshot existing total_PA → baseline_PA (preserves preseason career total)
    Each refresh:
      - Recompute season_*_2026 fields fresh from the cumulative Statcast pull
      - total_PA = baseline_PA + season_PA_2026
      - Add new rookies who appear in 2026 but weren't in the preseason file
      - Zero-out season fields for batters with no 2026 PA (handles trades, IL, retired)
    Idempotent: safe to run every cron with no double-counting.
    """
    print(f"\n  Merging batters.json...")
    existing = load_atlas("batters.json")
    by_id = {b["batter"]: b for b in existing}

    # One-time migration: snapshot baseline_PA from preseason total_PA
    n_migrated = 0
    for b in existing:
        if "baseline_PA" not in b:
            b["baseline_PA"] = float(b.get("total_PA") or 0.0)
            n_migrated += 1
    if n_migrated:
        print(f"    Snapshotted baseline_PA for {n_migrated} batters (one-time)")

    new_by_id = {r["batter"]: r for r in new_records}
    SEASON_FIELDS = (
        "season_PA_2026", "season_H_2026", "season_HR_2026",
        "season_BB_2026", "season_K_2026", "season_wOBA_2026",
    )

    n_updated = 0
    n_new = 0
    for bid, season in new_by_id.items():
        if bid in by_id:
            r = by_id[bid]
            for f in SEASON_FIELDS:
                r[f] = season[f]
            r["total_PA"] = round((r.get("baseline_PA") or 0.0) + season["season_PA_2026"], 1)
            if season["batter_name"]:
                r["batter_name"] = season["batter_name"]
            n_updated += 1
        else:
            existing.append({
                "batter": bid,
                "batter_name": season["batter_name"] or name_map.get(bid, str(bid)),
                "baseline_PA": 0.0,
                **{f: season[f] for f in SEASON_FIELDS},
                "total_PA": season["season_PA_2026"],
            })
            n_new += 1

    # Zero out 2026 fields for batters without any 2026 PA (handles offseason rosters)
    n_zeroed = 0
    for b in existing:
        if b["batter"] not in new_by_id and "season_PA_2026" in b:
            for f in SEASON_FIELDS:
                b[f] = 0.0
            b["total_PA"] = round(b.get("baseline_PA") or 0.0, 1)
            n_zeroed += 1

    print(f"    Updated: {n_updated}, New rookies: {n_new}, Zeroed (no 2026 PA): {n_zeroed}")
    save_atlas("batters.json", existing)
    return n_updated + n_new


# ─── Step 5: Compute pitcher season features for 2026 ───────────────────────

def compute_pitcher_seasons(df, pitcher_idx, cluster_profiles, cluster_scales, clusters_meta):
    """
    Compute 2026 pitcher-season features from Statcast data.
    Assign current-season clusters from 2026 Statcast features.
    """
    print(f"\n{'='*60}")
    print(f"COMPUTING PITCHER SEASONS (2026)")
    print(f"{'='*60}")

    records = []
    for pid, group in df.groupby("pitcher"):
        prev = pitcher_idx.get(int(pid))

        # Pitch mix features
        pitch_mix = compute_pitch_mix(group)
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

        # Current role metadata. Not used for archetype assignment.
        appearances = group["game_pk"].nunique() if "game_pk" in group.columns else 1
        starts = 0
        if "game_pk" in group.columns and "inning" in group.columns:
            for _, g in group.groupby("game_pk"):
                inning = g["inning"].dropna()
                if len(inning) and int(inning.min()) == 1:
                    starts += 1
        avg_pitches_per_app = len(group) / appearances if appearances else len(group)
        is_sp = 1 if starts > 0 and (starts >= appearances * 0.4 or avg_pitches_per_app >= 45) else 0

        p_throws = group["p_throws"].iloc[0] if len(group) > 0 else "R"
        is_rhp = 1 if p_throws == "R" else 0

        # Pitcher name from Statcast (player_name IS the pitcher name in statcast)
        pitcher_name = group["player_name"].iloc[0] if len(group) > 0 else ""
        # Statcast format: "Last, First"
        pitcher_name = str(pitcher_name)

        if "arm_angle" in group.columns:
            arm = group["arm_angle"].dropna()
            arm_angle = round(float(arm.mean()), 1) if len(arm) > 0 else 0.0
        else:
            arm_angle = prev.get("arm_angle", 0) if prev else 0

        features = {
            "is_rhp": is_rhp,
            "is_sp": is_sp,
            "avg_velo_FF": avg_velo,
            "whiff_rate": whiff_rate,
            "groundball_rate": gb_rate,
            "spin_overall": avg_spin,
            "pfx_x_avg": avg_pfx_x,
            "pfx_z_avg": avg_pfx_z,
            "arm_angle": arm_angle,
            "pitch_mix": pitch_mix,
        }
        cluster, gmm_proba = assign_current_cluster(
            features, cluster_profiles, cluster_scales
        )
        archetype = _cluster_short_label(cluster, clusters_meta) or "Untyped"
        profile = cluster_profiles.get(cluster, {})
        pca_x = profile.get("pca_x", prev.get("pca_x", 0) if prev else 0)
        pca_y = profile.get("pca_y", prev.get("pca_y", 0) if prev else 0)
        pca_z = profile.get("pca_z", prev.get("pca_z", 0) if prev else 0)

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
            "groundball_rate": gb_rate,
            "spin_overall": avg_spin,
            "pitch_mix": pitch_mix,
            "starts": int(starts),
            "appearances": int(appearances),
            "arm_angle": arm_angle,
            "pfx_x_avg": avg_pfx_x,
            "pfx_z_avg": avg_pfx_z,
            "gmm_proba": gmm_proba,
        })

    print(f"  Generated {len(records)} pitcher-season records for 2026")
    known = sum(1 for r in records if r["archetype"] != "Untyped")
    print(f"  Known cluster: {known}, Untyped: {len(records) - known}")
    return records


# ─── Step 6: Calculate SIERA for 2026 pitchers ──────────────────────────────

def calculate_siera(k_pct, bb_pct, net_gb_pa):
    """
    Baseball Prospectus / MLB glossary SIERA formula.
    net_gb_pa = (GB - FB - PU) / PA, with the squared term negative when
    net_gb_pa is positive and positive when net_gb_pa is negative.
    """
    net_gb_sq = net_gb_pa ** 2
    signed_net_gb_sq_term = -6.664 * net_gb_sq if net_gb_pa >= 0 else 6.664 * net_gb_sq
    return (
        6.145
        - 16.986 * k_pct
        + 11.434 * bb_pct
        - 1.858 * net_gb_pa
        + 7.653 * (k_pct ** 2)
        + signed_net_gb_sq_term
        + 10.130 * k_pct * net_gb_pa
        - 5.195 * bb_pct * net_gb_pa
    )

def compute_siera_estimates(df, pitcher_seasons_2026, actual_pitching_stats=None):
    """
    Calculate SIERA from official MLB season strikeout/walk/BF totals, using
    Statcast batted-ball types for the GB/FB/PU component.
    """
    print(f"\n{'='*60}")
    print(f"CALCULATING SIERA (2026)")
    print(f"{'='*60}")

    actual_pitching_stats = actual_pitching_stats or {}
    records = {}
    for pid, group in df.groupby("pitcher"):
        # Only pitches that ended a PA
        pa_pitches = group[group["events"].notna()]
        if len(pa_pitches) < 5:
            continue

        events = pa_pitches["events"]
        statcast_pa = len(events)
        statcast_k = events.isin(["strikeout", "strikeout_double_play"]).sum()
        statcast_bb = events.isin(["walk", "intent_walk"]).sum()

        actual = actual_pitching_stats.get(int(pid), {})
        official_pa = actual.get("batters_faced")
        pa = official_pa if official_pa else statcast_pa
        if not pa:
            continue

        k_pct = actual.get("k_pct")
        bb_pct = actual.get("bb_pct")
        if k_pct is None:
            k_pct = statcast_k / statcast_pa if statcast_pa else 0
        if bb_pct is None:
            bb_pct = statcast_bb / statcast_pa if statcast_pa else 0

        # Statcast provides all batted-ball types; MLB season stats only expose
        # ground/air outs, which is not enough for the SIERA GB-FB-PU term.
        batted = group[group["bb_type"].notna()]
        gb = (batted["bb_type"] == "ground_ball").sum()
        fb = (batted["bb_type"] == "fly_ball").sum()
        pu = (batted["bb_type"] == "popup").sum()
        gb_fb = gb / fb if fb > 0 else 1.0
        net_gb_pa = (gb - fb - pu) / pa

        siera = calculate_siera(k_pct, bb_pct, net_gb_pa)

        pitcher_name = str(group["player_name"].iloc[0])

        outs = events.isin([
            "field_out", "grounded_into_double_play", "force_out",
            "double_play", "fielders_choice", "fielders_choice_out",
            "strikeout", "strikeout_double_play", "sac_fly",
            "sac_bunt", "triple_play",
        ]).sum()
        statcast_ip = outs / 3.0 if outs > 0 else 0
        real_ip = actual.get("ip")

        key = f"{int(pid)}_{SEASON}"
        records[key] = {
            "pitcher": int(pid),
            "player_name": actual.get("player_name") or pitcher_name,
            "game_year": SEASON,
            "era": round(actual["era"], 2) if actual.get("era") is not None else None,
            "whip": round(actual["whip"], 2) if actual.get("whip") is not None else None,
            "siera": round(siera, 2),
            "siera_source": "mlb_stats_api_plus_statcast_batted_ball",
            "pa": int(pa),
            "pa_source": "mlb_stats_api" if official_pa else "statcast_pa",
            "ip": round(real_ip if real_ip is not None else statcast_ip, 1),
            "ip_source": "mlb_stats_api" if real_ip is not None else "statcast_pa_outs",
            "k_pct": round(k_pct, 4),
            "bb_pct": round(bb_pct, 4),
            "kbb_pct": round(actual["kbb_pct"], 4) if actual.get("kbb_pct") is not None else round(k_pct - bb_pct, 4),
            "strikeouts": actual.get("strikeouts"),
            "walks": actual.get("walks"),
            "intentional_walks": actual.get("intentional_walks"),
            "batters_faced": actual.get("batters_faced"),
            "ground_balls": int(gb),
            "fly_balls": int(fb),
            "popups": int(pu),
            "net_gb_pa": round(net_gb_pa, 4),
            "games_started": actual.get("games_started"),
            "gb_fb": round(gb_fb, 2),
        }

    print(f"  Calculated SIERA for {len(records)} pitchers")
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


def _cluster_short_label(cluster_id, clusters_meta):
    """Extract the short archetype name from clusters.json for a cluster_id.
    e.g. '👹 Split Demon RP' → 'Split Demon'."""
    c = clusters_meta.get(cluster_id, {})
    sn = c.get("short_name", "")
    sn = re.sub(r"^[^\w]+", "", sn).strip()
    for suffix in (" RP", " SP"):
        if sn.endswith(suffix):
            sn = sn[: -len(suffix)]
    return sn


# Manual overrides for pitchers whose GMM clustering doesn't match their
# actual stuff (e.g. Senga throws a ghost fork but clustering places him in
# Kitchen Sink Illusionist). Keyed by (lowercased name fragment → cluster_id).
CLUSTER_OVERRIDES = {
    "senga, kodai": ("R_11", {"R_11": 0.55, "R_8": 0.25, "R_5": 0.20}),
}


def _apply_cluster_overrides(records):
    """Force specific pitchers into the right cluster regardless of GMM."""
    count = 0
    for r in records:
        name = (r.get("player_name") or "").lower()
        for frag, (cid, gmm) in CLUSTER_OVERRIDES.items():
            if frag in name:
                r["cluster"] = cid
                r["gmm_proba"] = dict(gmm)
                count += 1
                break
    return count


def _sync_archetype_labels(records, clusters_meta):
    """Ensure every pitcher's archetype label matches their cluster's short name.
    Prevents stale labels like 'Knuckleball Wizard' on non-knuckleball clusters."""
    synced = 0
    for r in records:
        cid = r.get("cluster")
        if not cid:
            continue
        expected = _cluster_short_label(cid, clusters_meta)
        if expected and r.get("archetype") != expected:
            r["archetype"] = expected
            synced += 1
    return synced


def merge_pitcher_seasons(new_records):
    """Replace all 2026 records, keep everything else.
    Also apply cluster overrides and sync archetype labels across ALL years
    so the atlas stays consistent with clusters.json."""
    print(f"\n  Merging pitcher_seasons...")
    existing = load_atlas("pitcher_seasons.json")
    clusters_meta = load_atlas("clusters.json")

    kept = [r for r in existing if r.get("game_year") != SEASON]
    print(f"    Existing records (non-2026): {len(kept)}")
    print(f"    New 2026 records: {len(new_records)}")

    merged = kept + new_records

    # Apply manual overrides (Senga, etc.) across all years
    n_over = _apply_cluster_overrides(merged)
    print(f"    Cluster overrides applied: {n_over}")

    # Sync archetype labels to match cluster short names
    n_sync = _sync_archetype_labels(merged, clusters_meta)
    print(f"    Archetype labels synced: {n_sync}")

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

# Pure SIERA cutoffs — no z-score, no whiff rate, no cluster-relative nonsense
SIERA_TIER_CUTOFFS = [
    (3.00, "T1_Apex"),     # SIERA < 3.00
    (3.75, "T2_Core"),     # SIERA 3.00–3.75
    (4.50, "T3_Standard"), # SIERA 3.75–4.50
]                          # SIERA > 4.50 → T4_Fringe
DEFAULT_TIER = "T4_Fringe"

BASE_TIER_MULTIPLIERS = {
    "T1_Apex": 0.87,
    "T2_Core": 0.95,
    "T3_Standard": 1.00,
    "T4_Fringe": 1.10,
}

TIER_RANK = {
    "T1_Apex": 1,
    "T2_Core": 2,
    "T3_Standard": 3,
    "T4_Fringe": 4,
}


def assign_tier_by_siera(siera):
    """Assign tier based on pure SIERA thresholds."""
    for cutoff, tier in SIERA_TIER_CUTOFFS:
        if siera < cutoff:
            return tier
    return DEFAULT_TIER


def cap_tier(tier, max_tier):
    return max(tier, max_tier, key=lambda t: TIER_RANK[t])


def apply_real_stat_guardrails(tier, rec):
    """Prevent estimated SIERA from outranking ugly real-season production."""
    ip = rec.get("ip") or 0
    batters_faced = rec.get("batters_faced") or 0
    if ip < 20 and batters_faced < 80:
        return tier, ""

    era = rec.get("era")
    whip = rec.get("whip")
    kbb_pct = rec.get("kbb_pct")
    reasons = []

    max_tier = "T1_Apex"
    if era is not None:
        if era >= 5.00:
            max_tier = cap_tier(max_tier, "T4_Fringe")
            reasons.append(f"ERA {era:.2f} >= 5.00")
        elif era >= 4.25:
            max_tier = cap_tier(max_tier, "T3_Standard")
            reasons.append(f"ERA {era:.2f} >= 4.25")
        elif era >= 3.75:
            max_tier = cap_tier(max_tier, "T2_Core")
            reasons.append(f"ERA {era:.2f} >= 3.75")

    if whip is not None:
        if whip >= 1.40:
            max_tier = cap_tier(max_tier, "T4_Fringe")
            reasons.append(f"WHIP {whip:.2f} >= 1.40")
        elif whip >= 1.30:
            max_tier = cap_tier(max_tier, "T3_Standard")
            reasons.append(f"WHIP {whip:.2f} >= 1.30")
        elif whip >= 1.25:
            max_tier = cap_tier(max_tier, "T2_Core")
            reasons.append(f"WHIP {whip:.2f} >= 1.25")

    if kbb_pct is not None:
        if kbb_pct < 0.08:
            max_tier = cap_tier(max_tier, "T4_Fringe")
            reasons.append(f"K-BB% {kbb_pct:.1%} < 8%")
        elif kbb_pct < 0.12:
            max_tier = cap_tier(max_tier, "T3_Standard")
            reasons.append(f"K-BB% {kbb_pct:.1%} < 12%")
        elif kbb_pct < 0.15:
            max_tier = cap_tier(max_tier, "T2_Core")
            reasons.append(f"K-BB% {kbb_pct:.1%} < 15%")

    guarded = cap_tier(tier, max_tier)
    if guarded != tier:
        return guarded, "; ".join(reasons)
    return tier, ""


def recompute_pitcher_tiers():
    """Rerun tier assignment including 2026 data. Uses pure SIERA cutoffs."""
    print(f"\n{'='*60}")
    print(f"RECOMPUTING PITCHER TIERS (pure SIERA cutoffs)")
    print(f"{'='*60}")
    print(f"  T1_Apex: SIERA < 3.00  (0.87x)")
    print(f"  T2_Core: SIERA 3.00-3.75  (0.95x)")
    print(f"  T3_Standard: SIERA 3.75-4.50  (1.00x)")
    print(f"  T4_Fringe: SIERA > 4.50  (1.10x)")

    pitcher_seasons = load_atlas("pitcher_seasons.json")
    siera_data = load_atlas("pitcher_siera.json")

    # Build SIERA index
    siera_idx = {}
    for key, rec in siera_data.items():
        pid = rec.get("pitcher")
        yr = rec.get("game_year")
        if pid and yr:
            siera_idx[(pid, yr)] = rec

    # Match SIERA to pitcher-seasons
    matched = 0
    for ps in pitcher_seasons:
        siera_rec = siera_idx.get((ps["pitcher"], ps["game_year"]))
        if siera_rec is not None and siera_rec.get("siera") is not None:
            ps["siera"] = siera_rec.get("siera")
            ps["_siera_rec"] = siera_rec
            matched += 1
        else:
            ps["siera"] = None
            ps["_siera_rec"] = {}

    print(f"  SIERA matched: {matched}/{len(pitcher_seasons)}")

    # Assign tiers using pure SIERA cutoffs
    tiers_output = {}
    tier_counts = defaultdict(int)
    for ps in pitcher_seasons:
        if ps["siera"] is None:
            continue
        siera_rec = ps.get("_siera_rec", {})
        raw_tier = assign_tier_by_siera(ps["siera"])
        tier, guardrail = apply_real_stat_guardrails(raw_tier, siera_rec)
        mult = BASE_TIER_MULTIPLIERS[tier]
        tier_counts[tier] += 1

        key = f"{ps['pitcher']}_{ps['game_year']}"
        tiers_output[key] = {
            "pitcher": ps["pitcher"],
            "player_name": ps.get("player_name", ""),
            "game_year": ps["game_year"],
            "cluster": ps["cluster"],
            "archetype": ps.get("archetype", ""),
            "siera": round(ps["siera"], 2),
            "tier": tier,
            "raw_siera_tier": raw_tier,
            "tier_guardrail": guardrail,
            "era": siera_rec.get("era"),
            "whip": siera_rec.get("whip"),
            "k_pct": siera_rec.get("k_pct"),
            "bb_pct": siera_rec.get("bb_pct"),
            "kbb_pct": siera_rec.get("kbb_pct"),
            "base_multiplier": mult,
            "effective_multiplier": mult,
        }

    save_atlas("pitcher_tiers.json", tiers_output)

    # Count 2026 entries
    count_2026 = sum(1 for v in tiers_output.values() if v["game_year"] == SEASON)
    for t in ["T1_Apex", "T2_Core", "T3_Standard", "T4_Fringe"]:
        print(f"  {t}: {tier_counts[t]}")
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
    cluster_profiles, cluster_scales, clusters_meta = build_cluster_assignment_model()

    # 3. Build batter name lookup
    name_map = build_batter_names(df)

    # 4. Compute pitcher seasons for 2026 first, so hitter-vs-cluster uses
    # current-year pitcher assignments instead of stale inherited clusters.
    ps_records = compute_pitcher_seasons(
        df, pitcher_idx, cluster_profiles, cluster_scales, clusters_meta
    )
    current_pitcher_idx = {r["pitcher"]: r for r in ps_records}

    # 5. Compute hitter-vs-cluster for 2026
    hvc_records = compute_hitter_vs_cluster(df, current_pitcher_idx)
    # Fill in batter names
    for r in hvc_records:
        r["batter_name"] = name_map.get(r["batter"], "")

    # 5b. Compute hitter season totals for 2026 (powers atlas/batters.json)
    hs_records = compute_hitter_seasons(df, name_map)

    # 6. Estimate SIERA and overlay real MLB season stats for guardrails.
    actual_pitching_stats = fetch_mlb_pitching_stats(SEASON)
    siera_records = compute_siera_estimates(df, ps_records, actual_pitching_stats)

    # 7. Merge everything
    print(f"\n{'='*60}")
    print(f"MERGING INTO ATLAS")
    print(f"{'='*60}")
    n_hvc = merge_hitter_vs_cluster(hvc_records)
    n_hs = merge_batters(hs_records, name_map)
    n_ps = merge_pitcher_seasons(ps_records)
    n_siera = merge_pitcher_siera(siera_records)

    # 8. Recompute tiers
    n_tiers = recompute_pitcher_tiers()

    # Summary
    print(f"\n{'#'*60}")
    print(f"  REFRESH COMPLETE")
    print(f"  hitter_vs_cluster: +{n_hvc} records")
    print(f"  batters:           {n_hs} batters with 2026 stats")
    print(f"  pitcher_seasons:   +{n_ps} records")
    print(f"  pitcher_siera:     +{n_siera} records")
    print(f"  pitcher_tiers:     {n_tiers} entries for 2026")
    print(f"{'#'*60}\n")


if __name__ == "__main__":
    main()

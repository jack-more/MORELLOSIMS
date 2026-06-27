"""
Pitcher and hitter vector feature builders for the MLB SIM.

This module keeps the new vector layer separate from the live archetype model.
It turns pitch-level Statcast rows into:
  - pitcher vectors: pitch mix, velo, movement, release, location, skill,
    batted-ball, platoon, recent trend, TTO, and leash features
  - hitter inverse vectors: hitter skill against pitch families, velocity
    bands, movement bands, location buckets, handedness, and recent form
  - matchup scores: pitcher vector dot hitter inverse vector with shrinkage

The output is intentionally JSON-friendly so it can be stored in atlas files or
inside SQLite without requiring a service dependency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd


FASTBALL_TYPES = {"FF", "FA", "SI", "FC"}
FOUR_SEAM_TYPES = {"FF", "FA"}
SINKER_TYPES = {"SI"}
CUTTER_TYPES = {"FC"}
SLIDER_TYPES = {"SL", "ST", "SV"}
CURVE_TYPES = {"CU", "KC"}
CHANGE_TYPES = {"CH"}
SPLIT_TYPES = {"FS", "FO", "SC"}
KNUCKLE_TYPES = {"KN"}
OTHER_TYPES = {"EP", "PO"}

PITCH_FAMILIES = [
    "four_seam",
    "sinker",
    "cutter",
    "slider",
    "curve",
    "changeup",
    "splitter",
    "knuckle",
    "other",
]

VELOCITY_BANDS = ["soft", "medium", "high", "elite", "unknown"]
MOVEMENT_BANDS = [
    "high_ivb",
    "low_ivb",
    "heavy_horizontal",
    "neutral_movement",
    "unknown",
]
LOCATION_BUCKETS = ["heart", "zone_edge", "chase", "waste", "unknown"]
PITCHER_HANDS = ["L", "R"]

SWING_DESCRIPTIONS = {
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "foul_bunt",
    "hit_into_play",
    "hit_into_play_no_out",
    "hit_into_play_score",
    "missed_bunt",
}

WHIFF_DESCRIPTIONS = {
    "swinging_strike",
    "swinging_strike_blocked",
    "missed_bunt",
}

CALLED_STRIKE_DESCRIPTIONS = {"called_strike"}
BALL_DESCRIPTIONS = {"ball", "blocked_ball", "pitchout", "intent_ball"}

STRIKEOUT_EVENTS = {"strikeout", "strikeout_double_play"}
WALK_EVENTS = {"walk", "intent_walk"}
HBP_EVENTS = {"hit_by_pitch"}
HIT_EVENTS = {"single", "double", "triple", "home_run"}
PA_EVENTS = (
    STRIKEOUT_EVENTS
    | WALK_EVENTS
    | HBP_EVENTS
    | HIT_EVENTS
    | {
        "field_out",
        "force_out",
        "grounded_into_double_play",
        "double_play",
        "fielders_choice",
        "fielders_choice_out",
        "sac_fly",
        "sac_bunt",
        "sac_fly_double_play",
        "triple_play",
        "sac_bunt_double_play",
        "field_error",
        "catcher_interf",
    }
)

TOTAL_BASES_BY_EVENT = {
    "single": 1,
    "double": 2,
    "triple": 3,
    "home_run": 4,
}


@dataclass(frozen=True)
class ShrinkageConfig:
    """Prior weights for noisy split stats."""

    pitch_family_prior: int = 90
    velocity_prior: int = 110
    movement_prior: int = 120
    location_prior: int = 100
    handedness_prior: int = 140
    recent_prior: int = 70


DEFAULT_SHRINKAGE = ShrinkageConfig()


def safe_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    number = safe_float(value)
    if number is None:
        return default
    return int(number)


def rate(numerator: float, denominator: float) -> float | None:
    if not denominator:
        return None
    return float(numerator) / float(denominator)


def rounded(value: Any, digits: int = 4) -> float | None:
    number = safe_float(value)
    if number is None or not math.isfinite(number):
        return None
    return round(number, digits)


def mean_or_none(series: pd.Series) -> float | None:
    if series is None or len(series) == 0:
        return None
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None
    return float(numeric.mean())


def shrink_value(split_value: float | None, sample: int, baseline: float | None, prior: int) -> float | None:
    """Bayesian shrinkage toward baseline."""
    if split_value is None:
        return baseline
    if baseline is None:
        return split_value
    sample = max(0, int(sample or 0))
    weight = sample / (sample + prior) if sample + prior > 0 else 0.0
    return weight * split_value + (1.0 - weight) * baseline


def pitch_family(pitch_type: Any) -> str:
    pt = str(pitch_type or "").upper()
    if pt in FOUR_SEAM_TYPES:
        return "four_seam"
    if pt in SINKER_TYPES:
        return "sinker"
    if pt in CUTTER_TYPES:
        return "cutter"
    if pt in SLIDER_TYPES:
        return "slider"
    if pt in CURVE_TYPES:
        return "curve"
    if pt in CHANGE_TYPES:
        return "changeup"
    if pt in SPLIT_TYPES:
        return "splitter"
    if pt in KNUCKLE_TYPES:
        return "knuckle"
    return "other"


def velocity_band(release_speed: Any) -> str:
    velo = safe_float(release_speed)
    if velo is None:
        return "unknown"
    if velo < 90:
        return "soft"
    if velo < 95:
        return "medium"
    if velo < 98:
        return "high"
    return "elite"


def movement_band(pfx_x: Any, pfx_z: Any) -> str:
    x = safe_float(pfx_x)
    z = safe_float(pfx_z)
    if x is None and z is None:
        return "unknown"
    x = x or 0.0
    z = z or 0.0
    if z >= 1.35:
        return "high_ivb"
    if z <= 0.45:
        return "low_ivb"
    if abs(x) >= 0.95:
        return "heavy_horizontal"
    return "neutral_movement"


def location_bucket(zone: Any, plate_x: Any, plate_z: Any) -> str:
    z = safe_int(zone, default=-1)
    if z == 5:
        return "heart"
    if z in {1, 2, 3, 4, 6, 7, 8, 9}:
        return "zone_edge"
    if z in {11, 12, 13, 14}:
        return "chase"
    x = safe_float(plate_x)
    height = safe_float(plate_z)
    if x is None or height is None:
        return "unknown"
    if abs(x) <= 0.55 and 2.1 <= height <= 3.3:
        return "heart"
    if abs(x) <= 0.95 and 1.6 <= height <= 3.7:
        return "zone_edge"
    if abs(x) <= 1.55 and 1.0 <= height <= 4.3:
        return "chase"
    return "waste"


def xwoba_value(row: pd.Series) -> float | None:
    value = safe_float(row.get("estimated_woba_using_speedangle"))
    if value is not None:
        return value
    return safe_float(row.get("woba_value"))


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column not in df.columns:
            df[column] = np.nan
    return df


def prepare_statcast_frame(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize Statcast rows and add reusable feature flags.

    This function accepts raw pybaseball.statcast output or a CSV exported from
    that output. Missing columns are tolerated and filled with nulls so the
    builder can run on small test fixtures.
    """
    df = df.copy().reset_index(drop=True)
    needed = [
        "game_date",
        "game_pk",
        "pitcher",
        "player_name",
        "p_throws",
        "batter",
        "stand",
        "pitch_type",
        "release_speed",
        "release_spin_rate",
        "pfx_x",
        "pfx_z",
        "release_pos_x",
        "release_pos_z",
        "release_extension",
        "plate_x",
        "plate_z",
        "zone",
        "description",
        "events",
        "type",
        "launch_speed",
        "launch_angle",
        "bb_type",
        "estimated_woba_using_speedangle",
        "woba_value",
        "inning",
        "at_bat_number",
        "pitch_number",
    ]
    df = _ensure_columns(df, needed)

    df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
    df["pitcher"] = pd.to_numeric(df["pitcher"], errors="coerce").astype("Int64")
    df["batter"] = pd.to_numeric(df["batter"], errors="coerce").astype("Int64")
    df["pitch_family"] = df["pitch_type"].map(pitch_family)
    df["velocity_band"] = df["release_speed"].map(velocity_band)
    df["movement_band"] = [
        movement_band(x, z) for x, z in zip(df["pfx_x"], df["pfx_z"])
    ]
    df["location_bucket"] = [
        location_bucket(z, x, y)
        for z, x, y in zip(df["zone"], df["plate_x"], df["plate_z"])
    ]
    df["description_norm"] = df["description"].fillna("").astype(str)
    df["events_norm"] = df["events"].fillna("").astype(str)
    df["is_pa_end"] = df["events_norm"].isin(PA_EVENTS)
    df["is_swing"] = df["description_norm"].isin(SWING_DESCRIPTIONS)
    df["is_whiff"] = df["description_norm"].isin(WHIFF_DESCRIPTIONS)
    df["is_called_strike"] = df["description_norm"].isin(CALLED_STRIKE_DESCRIPTIONS)
    df["is_csw"] = df["is_whiff"] | df["is_called_strike"]
    df["is_ball"] = df["description_norm"].isin(BALL_DESCRIPTIONS)
    df["is_strike"] = df["type"].fillna("").astype(str).eq("S") | df["is_csw"]
    df["in_zone"] = pd.to_numeric(df["zone"], errors="coerce").isin(range(1, 10))
    df["is_chase"] = df["is_swing"] & ~df["in_zone"]
    df["is_k"] = df["events_norm"].isin(STRIKEOUT_EVENTS)
    df["is_bb"] = df["events_norm"].isin(WALK_EVENTS)
    df["is_hbp"] = df["events_norm"].isin(HBP_EVENTS)
    df["is_hit"] = df["events_norm"].isin(HIT_EVENTS)
    df["total_bases"] = df["events_norm"].map(TOTAL_BASES_BY_EVENT).fillna(0)
    df["xwoba_value"] = df.apply(xwoba_value, axis=1)
    df["is_batted_ball"] = df["bb_type"].notna() | df["launch_speed"].notna()
    launch_speed = pd.to_numeric(df["launch_speed"], errors="coerce")
    launch_angle = pd.to_numeric(df["launch_angle"], errors="coerce")
    df["is_hard_hit"] = launch_speed >= 95
    df["is_barrel_proxy"] = (launch_speed >= 98) & (launch_angle.between(18, 34))
    df["is_gb"] = df["bb_type"].fillna("").eq("ground_ball")
    df["is_fb"] = df["bb_type"].fillna("").isin({"fly_ball", "popup"})
    df["is_ld"] = df["bb_type"].fillna("").eq("line_drive")

    df = add_times_through_order(df)
    return df


def add_times_through_order(df: pd.DataFrame) -> pd.DataFrame:
    if not {"game_pk", "pitcher", "batter", "at_bat_number", "pitch_number"}.issubset(df.columns):
        df["times_through_order"] = np.nan
        return df
    pa = df[df["is_pa_end"]].copy()
    if pa.empty:
        df["times_through_order"] = np.nan
        return df
    pa = pa.sort_values(["game_pk", "pitcher", "at_bat_number", "pitch_number"])
    pa["times_through_order"] = pa.groupby(["game_pk", "pitcher", "batter"]).cumcount() + 1
    df["times_through_order"] = np.nan
    df.loc[pa.index, "times_through_order"] = pa["times_through_order"]
    return df


def _share_map(group: pd.DataFrame, column: str, allowed: list[str]) -> dict[str, float]:
    total = len(group)
    if total <= 0:
        return {key: 0.0 for key in allowed}
    counts = group[column].value_counts(dropna=False)
    return {key: round(float(counts.get(key, 0)) / total, 4) for key in allowed}


def _mean_map(group: pd.DataFrame, key_col: str, value_col: str, allowed: list[str]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for key in allowed:
        out[key] = rounded(mean_or_none(group.loc[group[key_col] == key, value_col]))
    return out


def _pa_group(group: pd.DataFrame) -> pd.DataFrame:
    return group[group["is_pa_end"]].copy()


def _rate_from_bool(group: pd.DataFrame, column: str) -> float | None:
    if group.empty:
        return None
    return rounded(group[column].mean())


def _xwoba_mean(group: pd.DataFrame) -> float | None:
    return rounded(mean_or_none(group["xwoba_value"]))


def _split_xwoba(group: pd.DataFrame, split_col: str, values: list[str]) -> dict[str, dict[str, Any]]:
    pa = _pa_group(group)
    out: dict[str, dict[str, Any]] = {}
    for value in values:
        sub = pa[pa[split_col].fillna("").astype(str).eq(value)]
        out[value] = {
            "pa": int(len(sub)),
            "xwoba_allowed": _xwoba_mean(sub),
            "k_pct": _rate_from_bool(sub, "is_k"),
            "bb_pct": _rate_from_bool(sub, "is_bb"),
        }
    return out


def aggregate_pitcher_vectors(df: pd.DataFrame, as_of: str | None = None) -> dict[str, dict[str, Any]]:
    """
    Build pitcher vectors keyed by pitcher id.

    The vector is descriptive and model-ready. It does not decide picks.
    """
    if as_of:
        as_of_date = pd.to_datetime(as_of)
    else:
        as_of_date = df["game_date"].max()
    recent_30_cutoff = as_of_date - timedelta(days=30) if pd.notna(as_of_date) else None
    recent_14_cutoff = as_of_date - timedelta(days=14) if pd.notna(as_of_date) else None

    vectors: dict[str, dict[str, Any]] = {}
    for pitcher_id, group in df.dropna(subset=["pitcher"]).groupby("pitcher"):
        group = group.sort_values("game_date")
        pa = _pa_group(group)
        recent_30 = group[group["game_date"] >= recent_30_cutoff] if recent_30_cutoff is not None else group.iloc[0:0]
        recent_14 = group[group["game_date"] >= recent_14_cutoff] if recent_14_cutoff is not None else group.iloc[0:0]
        pa_recent_30 = _pa_group(recent_30)

        pitch_count = len(group)
        pa_count = len(pa)
        starts = _starter_appearances(group)
        season_velo = mean_or_none(group["release_speed"])
        recent_velo = mean_or_none(recent_30["release_speed"])
        season_zone = _rate_from_bool(group, "in_zone")
        recent_zone = _rate_from_bool(recent_30, "in_zone")
        season_csw = _rate_from_bool(group, "is_csw")
        recent_csw = _rate_from_bool(recent_30, "is_csw")
        season_xwoba = _xwoba_mean(pa)
        recent_xwoba = _xwoba_mean(pa_recent_30)

        tto = _times_through_order_features(pa)
        vector = {
            "pitcher": int(pitcher_id),
            "player_name": _first_non_null(group, "player_name"),
            "p_throws": _first_non_null(group, "p_throws"),
            "as_of": None if pd.isna(as_of_date) else str(as_of_date.date()),
            "sample": {
                "pitches": int(pitch_count),
                "pa": int(pa_count),
                "games": int(group["game_pk"].nunique(dropna=True)),
                "recent_30_pitches": int(len(recent_30)),
                "recent_14_pitches": int(len(recent_14)),
            },
            "pitch_mix": _share_map(group, "pitch_family", PITCH_FAMILIES),
            "velocity_band_mix": _share_map(group, "velocity_band", VELOCITY_BANDS),
            "movement_band_mix": _share_map(group, "movement_band", MOVEMENT_BANDS),
            "location_mix": _share_map(group, "location_bucket", LOCATION_BUCKETS),
            "velocity": {
                "avg": rounded(season_velo),
                "max": rounded(group["release_speed"].max()),
                "by_family": _mean_map(group, "pitch_family", "release_speed", PITCH_FAMILIES),
            },
            "movement": {
                "pfx_x_avg": rounded(mean_or_none(group["pfx_x"])),
                "pfx_z_avg": rounded(mean_or_none(group["pfx_z"])),
                "spin_avg": rounded(mean_or_none(group["release_spin_rate"])),
                "pfx_x_by_family": _mean_map(group, "pitch_family", "pfx_x", PITCH_FAMILIES),
                "pfx_z_by_family": _mean_map(group, "pitch_family", "pfx_z", PITCH_FAMILIES),
            },
            "release": {
                "height": rounded(mean_or_none(group["release_pos_z"])),
                "side": rounded(mean_or_none(group["release_pos_x"])),
                "extension": rounded(mean_or_none(group["release_extension"])),
            },
            "location": {
                "zone_pct": season_zone,
                "chase_pct": _rate_from_bool(group, "is_chase"),
                "heart_pct": rounded((group["location_bucket"] == "heart").mean()) if pitch_count else None,
                "edge_pct": rounded((group["location_bucket"] == "zone_edge").mean()) if pitch_count else None,
                "waste_pct": rounded((group["location_bucket"] == "waste").mean()) if pitch_count else None,
                "called_strike_pct": _rate_from_bool(group, "is_called_strike"),
            },
            "skill": {
                "k_pct": _rate_from_bool(pa, "is_k"),
                "bb_pct": _rate_from_bool(pa, "is_bb"),
                "k_minus_bb": _k_minus_bb(pa),
                "csw_pct": season_csw,
                "swstr_pct": _rate_from_bool(group, "is_whiff"),
                "strike_pct": _rate_from_bool(group, "is_strike"),
                "xwoba_allowed": season_xwoba,
            },
            "contact": {
                "gb_pct": _rate_from_bool(group[group["is_batted_ball"]], "is_gb"),
                "fb_pct": _rate_from_bool(group[group["is_batted_ball"]], "is_fb"),
                "ld_pct": _rate_from_bool(group[group["is_batted_ball"]], "is_ld"),
                "hard_hit_pct": _rate_from_bool(group[group["is_batted_ball"]], "is_hard_hit"),
                "barrel_proxy_pct": _rate_from_bool(group[group["is_batted_ball"]], "is_barrel_proxy"),
            },
            "platoon": _split_xwoba(group, "stand", ["L", "R"]),
            "recent_trend": {
                "velo_delta_30d": _delta(recent_velo, season_velo),
                "zone_delta_30d": _delta(recent_zone, season_zone),
                "csw_delta_30d": _delta(recent_csw, season_csw),
                "xwoba_allowed_delta_30d": _delta(recent_xwoba, season_xwoba),
            },
            "times_through_order": tto,
            "leash": starts,
        }
        vectors[str(int(pitcher_id))] = vector
    return vectors


def _first_non_null(group: pd.DataFrame, column: str) -> str | None:
    if column not in group:
        return None
    values = group[column].dropna()
    if values.empty:
        return None
    value = str(values.iloc[-1])
    return value if value and value.lower() != "nan" else None


def _k_minus_bb(pa: pd.DataFrame) -> float | None:
    k = _rate_from_bool(pa, "is_k")
    bb = _rate_from_bool(pa, "is_bb")
    if k is None or bb is None:
        return None
    return round(k - bb, 4)


def _delta(recent: float | None, season: float | None) -> float | None:
    if recent is None or season is None:
        return None
    return round(recent - season, 4)


def _times_through_order_features(pa: pd.DataFrame) -> dict[str, Any]:
    if pa.empty or "times_through_order" not in pa:
        return {"tto1_xwoba": None, "tto2_xwoba": None, "tto3plus_xwoba": None, "tto_penalty": None}
    tto1 = pa[pa["times_through_order"] == 1]
    tto2 = pa[pa["times_through_order"] == 2]
    tto3 = pa[pa["times_through_order"] >= 3]
    tto1_x = _xwoba_mean(tto1)
    tto3_x = _xwoba_mean(tto3)
    return {
        "tto1_xwoba": tto1_x,
        "tto2_xwoba": _xwoba_mean(tto2),
        "tto3plus_xwoba": tto3_x,
        "tto_penalty": _delta(tto3_x, tto1_x),
        "tto3plus_pa": int(len(tto3)),
    }


def _starter_appearances(group: pd.DataFrame) -> dict[str, Any]:
    if group.empty or "game_pk" not in group:
        return {"starts": 0, "avg_pitches_start": None, "avg_batters_faced_start": None}
    games = []
    for _, game in group.groupby("game_pk"):
        min_inning = safe_int(game["inning"].min(), default=99)
        pitch_count = len(game)
        if min_inning == 1 and pitch_count >= 20:
            games.append(
                {
                    "pitches": pitch_count,
                    "batters_faced": int(game.loc[game["is_pa_end"], "batter"].count()),
                }
            )
    if not games:
        return {"starts": 0, "avg_pitches_start": None, "avg_batters_faced_start": None}
    return {
        "starts": len(games),
        "avg_pitches_start": rounded(np.mean([g["pitches"] for g in games]), 2),
        "avg_batters_faced_start": rounded(np.mean([g["batters_faced"] for g in games]), 2),
    }


def aggregate_hitter_inverse_vectors(
    df: pd.DataFrame,
    as_of: str | None = None,
    shrinkage: ShrinkageConfig = DEFAULT_SHRINKAGE,
) -> dict[str, dict[str, Any]]:
    """Build hitter inverse vectors keyed by batter id."""
    if as_of:
        as_of_date = pd.to_datetime(as_of)
    else:
        as_of_date = df["game_date"].max()
    recent_30_cutoff = as_of_date - timedelta(days=30) if pd.notna(as_of_date) else None
    recent_14_cutoff = as_of_date - timedelta(days=14) if pd.notna(as_of_date) else None

    vectors: dict[str, dict[str, Any]] = {}
    for batter_id, group in df.dropna(subset=["batter"]).groupby("batter"):
        group = group.sort_values("game_date")
        pa = _pa_group(group)
        baseline_xwoba = _xwoba_mean(pa)
        baseline_woba = rounded(mean_or_none(pa["woba_value"]))
        recent_30 = group[group["game_date"] >= recent_30_cutoff] if recent_30_cutoff is not None else group.iloc[0:0]
        recent_14 = group[group["game_date"] >= recent_14_cutoff] if recent_14_cutoff is not None else group.iloc[0:0]
        pa_recent_30 = _pa_group(recent_30)
        pa_recent_14 = _pa_group(recent_14)

        vector = {
            "batter": int(batter_id),
            "stand": _first_non_null(group, "stand"),
            "as_of": None if pd.isna(as_of_date) else str(as_of_date.date()),
            "sample": {
                "pitches": int(len(group)),
                "pa": int(len(pa)),
                "recent_30_pa": int(len(pa_recent_30)),
                "recent_14_pa": int(len(pa_recent_14)),
            },
            "baseline": {
                "xwoba": baseline_xwoba,
                "woba": baseline_woba,
                "k_pct": _rate_from_bool(pa, "is_k"),
                "bb_pct": _rate_from_bool(pa, "is_bb"),
                "hard_hit_pct": _rate_from_bool(group[group["is_batted_ball"]], "is_hard_hit"),
                "barrel_proxy_pct": _rate_from_bool(group[group["is_batted_ball"]], "is_barrel_proxy"),
            },
            "pitch_family": _hitter_bucket_skills(
                group, "pitch_family", PITCH_FAMILIES, baseline_xwoba, shrinkage.pitch_family_prior
            ),
            "velocity_band": _hitter_bucket_skills(
                group, "velocity_band", VELOCITY_BANDS, baseline_xwoba, shrinkage.velocity_prior
            ),
            "movement_band": _hitter_bucket_skills(
                group, "movement_band", MOVEMENT_BANDS, baseline_xwoba, shrinkage.movement_prior
            ),
            "location": _hitter_bucket_skills(
                group, "location_bucket", LOCATION_BUCKETS, baseline_xwoba, shrinkage.location_prior
            ),
            "handedness": _hitter_bucket_skills(
                group, "p_throws", PITCHER_HANDS, baseline_xwoba, shrinkage.handedness_prior
            ),
            "recent_form": {
                "xwoba_14d": _xwoba_mean(pa_recent_14),
                "xwoba_30d": _xwoba_mean(pa_recent_30),
                "xwoba_delta_14d": _delta(
                    shrink_value(_xwoba_mean(pa_recent_14), len(pa_recent_14), baseline_xwoba, shrinkage.recent_prior),
                    baseline_xwoba,
                ),
                "xwoba_delta_30d": _delta(
                    shrink_value(_xwoba_mean(pa_recent_30), len(pa_recent_30), baseline_xwoba, shrinkage.recent_prior),
                    baseline_xwoba,
                ),
            },
        }
        vectors[str(int(batter_id))] = vector
    return vectors


def _hitter_bucket_skills(
    group: pd.DataFrame,
    bucket_col: str,
    buckets: list[str],
    baseline_xwoba: float | None,
    prior: int,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    pa_all = _pa_group(group)
    for bucket in buckets:
        pitch_sub = group[group[bucket_col].fillna("").astype(str).eq(bucket)]
        pa = _pa_group(pitch_sub)
        raw_xwoba = _xwoba_mean(pa)
        shrunk_xwoba = shrink_value(raw_xwoba, len(pa), baseline_xwoba, prior)
        out[bucket] = {
            "pa": int(len(pa)),
            "pitches": int(len(pitch_sub)),
            "xwoba": rounded(raw_xwoba),
            "xwoba_shrunk": rounded(shrunk_xwoba),
            "skill_delta": _delta(shrunk_xwoba, baseline_xwoba),
            "whiff_pct": _rate_from_bool(pitch_sub[pitch_sub["is_swing"]], "is_whiff"),
            "swing_pct": rounded(len(pitch_sub[pitch_sub["is_swing"]]) / len(pitch_sub), 4)
            if len(pitch_sub)
            else None,
            "k_pct": _rate_from_bool(pa, "is_k"),
            "bb_pct": _rate_from_bool(pa, "is_bb"),
            "sample_weight": rounded(len(pa) / (len(pa) + prior)) if len(pa) + prior else 0.0,
        }
    out["_baseline_pa"] = {"pa": int(len(pa_all))}
    return out


def build_matchup_features(
    pitcher_vector: dict[str, Any],
    hitter_vector: dict[str, Any],
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Score one hitter against one pitcher.

    The score is in xwOBA points. A +0.020 score means the hitter's inverse
    vector aligns positively with the pitcher's shape by about 20 xwOBA points.
    """
    weights = weights or {
        "pitch_family": 0.45,
        "velocity": 0.15,
        "movement": 0.15,
        "location": 0.15,
        "handedness": 0.10,
        "recent_form": 0.10,
    }
    family_score = _weighted_bucket_score(
        pitcher_vector.get("pitch_mix", {}), hitter_vector.get("pitch_family", {})
    )
    velocity_score = _weighted_bucket_score(
        pitcher_vector.get("velocity_band_mix", {}), hitter_vector.get("velocity_band", {})
    )
    movement_score = _weighted_bucket_score(
        pitcher_vector.get("movement_band_mix", {}), hitter_vector.get("movement_band", {})
    )
    location_score = _weighted_bucket_score(
        pitcher_vector.get("location_mix", {}), hitter_vector.get("location", {})
    )
    hand = pitcher_vector.get("p_throws")
    handedness_score = 0.0
    if hand:
        handedness_score = safe_float(
            hitter_vector.get("handedness", {}).get(hand, {}).get("skill_delta"), 0.0
        ) or 0.0
    recent_score = safe_float(hitter_vector.get("recent_form", {}).get("xwoba_delta_30d"), 0.0) or 0.0
    baseline = safe_float(hitter_vector.get("baseline", {}).get("xwoba"), 0.310) or 0.310

    components = {
        "pitch_family": round(family_score, 5),
        "velocity": round(velocity_score, 5),
        "movement": round(movement_score, 5),
        "location": round(location_score, 5),
        "handedness": round(handedness_score, 5),
        "recent_form": round(recent_score, 5),
    }
    matchup_delta = sum(components[key] * weights.get(key, 0.0) for key in components)
    projected_xwoba = baseline + matchup_delta
    return {
        "pitcher": pitcher_vector.get("pitcher"),
        "batter": hitter_vector.get("batter"),
        "baseline_xwoba": rounded(baseline),
        "matchup_delta": rounded(matchup_delta, 5),
        "projected_xwoba": rounded(projected_xwoba, 5),
        "components": components,
        "weights": weights,
    }


def _weighted_bucket_score(pitcher_mix: dict[str, Any], hitter_skills: dict[str, Any]) -> float:
    score = 0.0
    for bucket, share in pitcher_mix.items():
        share_value = safe_float(share, 0.0) or 0.0
        delta = safe_float(hitter_skills.get(bucket, {}).get("skill_delta"), 0.0) or 0.0
        score += share_value * delta
    return score


def score_lineup_matchup(
    pitcher_id: int | str,
    hitter_ids: list[int | str],
    pitcher_vectors: dict[str, dict[str, Any]],
    hitter_vectors: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    pitcher = pitcher_vectors.get(str(pitcher_id))
    if not pitcher:
        raise KeyError(f"Pitcher vector not found: {pitcher_id}")

    hitter_scores = []
    missing = []
    for hitter_id in hitter_ids:
        hitter = hitter_vectors.get(str(hitter_id))
        if not hitter:
            missing.append(str(hitter_id))
            continue
        hitter_scores.append(build_matchup_features(pitcher, hitter))

    if hitter_scores:
        avg_delta = float(np.mean([s["matchup_delta"] or 0.0 for s in hitter_scores]))
        avg_projected_xwoba = float(np.mean([s["projected_xwoba"] or 0.0 for s in hitter_scores]))
    else:
        avg_delta = 0.0
        avg_projected_xwoba = 0.0

    return {
        "pitcher": pitcher.get("pitcher"),
        "pitcher_name": pitcher.get("player_name"),
        "hitters_scored": len(hitter_scores),
        "missing_hitters": missing,
        "avg_matchup_delta": rounded(avg_delta, 5),
        "avg_projected_xwoba": rounded(avg_projected_xwoba, 5),
        "hitter_scores": hitter_scores,
    }


def flatten_vector_rows(vectors: dict[str, dict[str, Any]], entity_key: str) -> list[dict[str, Any]]:
    """Return compact rows for SQLite storage."""
    rows = []
    for entity_id, vector in vectors.items():
        rows.append(
            {
                entity_key: int(entity_id),
                "as_of": vector.get("as_of"),
                "sample_pa": vector.get("sample", {}).get("pa"),
                "sample_pitches": vector.get("sample", {}).get("pitches"),
                "vector_json": vector,
            }
        )
    return rows

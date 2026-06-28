#!/usr/bin/env python3
"""
Live MLB vector layer for official moneyline publishing.

The live builder owns the final run/probability math. This module builds the
45-day pitcher vectors and hitter inverse-vectors, scores lineup projected
xwOBA for both teams, and applies the research-backed agreement gate after the
builder has recomputed the pick side.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from mlb_vector_features import (
    aggregate_hitter_inverse_vectors,
    aggregate_pitcher_vectors,
    prepare_statcast_frame,
    score_lineup_matchup,
)


DEFAULT_LOOKBACK_DAYS = 45
DEFAULT_MIN_HISTORY_PITCHES = 5000
DEFAULT_MIN_VECTOR_EDGE = 0.0
DEFAULT_MIN_XWOBA_EDGE = 0.0


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _date_range(today: str, lookback_days: int) -> tuple[str, str]:
    today_date = datetime.strptime(today, "%Y-%m-%d").date()
    start = today_date - timedelta(days=lookback_days)
    end = today_date - timedelta(days=1)
    return str(start), str(end)


def _load_statcast(today: str, lookback_days: int, atlas_dir: Path) -> pd.DataFrame:
    start, end = _date_range(today, lookback_days)
    cache = atlas_dir / f".statcast_cache_{start}_{end}.csv"
    if cache.exists():
        print(f"  Vector projection: loading cached Statcast {cache.name}")
        return pd.read_csv(cache)

    try:
        from pybaseball import statcast
    except ImportError as exc:
        raise RuntimeError("pybaseball is required for the MLB vector gate") from exc

    print(f"  Vector projection: fetching Statcast {start} -> {end}")
    df = statcast(start, end)
    if df is None or df.empty:
        raise RuntimeError("Statcast returned no rows for vector gate")
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache, index=False)
    return df


def _candidate_games(games: list[dict[str, Any]], min_conf: int) -> list[dict[str, Any]]:
    return [
        g
        for g in games
        if g.get("has_lineups")
        and int(g.get("conf") or 0) >= min_conf
        and not g.get("odds_too_heavy")
        and g.get("odds_source") != "NO_LINE"
        and g.get("pick_coverage_ok")
        and not g.get("has_started")
    ]


def _projection_games(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        g
        for g in games
        if g.get("has_lineups")
        and _starter_id(g, "away")
        and _starter_id(g, "home")
        and _lineup_ids(g, "away")
        and _lineup_ids(g, "home")
    ]


def _lineup_ids(game: dict[str, Any], side: str) -> list[int]:
    key = "away_batters" if side == "away" else "home_batters"
    ids = []
    for batter in game.get(key) or []:
        pid = batter.get("id") if isinstance(batter, dict) else None
        if pid:
            ids.append(int(pid))
    return ids


def _starter_id(game: dict[str, Any], side: str) -> int | None:
    key = "away_sp_id" if side == "away" else "home_sp_id"
    value = game.get(key)
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def _apply_unavailable(games: list[dict[str, Any]], reason: str, min_conf: int) -> dict[str, Any]:
    blocked = 0
    for game in _candidate_games(games, min_conf):
        game["vector_gate_status"] = "UNAVAILABLE"
        game["vector_gate_reason"] = reason
        game["vector_gate_pre_conf"] = int(game.get("conf") or 0)
        game["conf"] = 0
        game["value"] = 0
        blocked += 1
    return {
        "available": False,
        "reason": reason,
        "blocked": blocked,
        "passed": 0,
        "failed": blocked,
        "scored": 0,
    }


def _mark_projection_unavailable(
    games: list[dict[str, Any]],
    reason: str,
) -> dict[str, Any]:
    for game in games:
        if game.get("has_lineups"):
            game["vector_projection_status"] = "UNAVAILABLE"
            game["vector_projection_reason"] = reason
    return {
        "available": False,
        "reason": reason,
        "blocked": 0,
        "passed": 0,
        "failed": 0,
        "scored": 0,
    }


def apply_live_vector_projection(
    games: list[dict[str, Any]],
    *,
    today: str,
    atlas_dir: str | Path,
) -> dict[str, Any]:
    """Score both lineups with 45-day pitcher and hitter inverse-vectors.

    Environment:
      MLB_VECTOR_GATE_DISABLED=1 disables the vector layer.
      MLB_VECTOR_GATE_LOOKBACK_DAYS overrides 45-day history.
    """
    if os.environ.get("MLB_VECTOR_GATE_DISABLED") == "1":
        for game in games:
            game["vector_projection_status"] = "DISABLED"
            game["vector_gate_status"] = "DISABLED"
        return {"available": False, "disabled": True, "blocked": 0, "passed": 0, "failed": 0, "scored": 0}

    atlas_dir = Path(atlas_dir)
    lookback_days = _env_int("MLB_VECTOR_GATE_LOOKBACK_DAYS", DEFAULT_LOOKBACK_DAYS)
    min_history_pitches = _env_int("MLB_VECTOR_GATE_MIN_HISTORY_PITCHES", DEFAULT_MIN_HISTORY_PITCHES)

    projection_games = _projection_games(games)
    if not projection_games:
        for game in games:
            game.setdefault("vector_projection_status", "NO_LINEUP")
        return {"available": True, "blocked": 0, "passed": 0, "failed": 0, "scored": 0}

    try:
        raw = _load_statcast(today, lookback_days, atlas_dir)
        prepared = prepare_statcast_frame(raw).dropna(subset=["pitcher", "batter"])
    except Exception as exc:
        return _mark_projection_unavailable(games, f"load_failed: {exc}")

    today_ts = pd.to_datetime(today)
    start_ts = today_ts - timedelta(days=lookback_days)
    hist = prepared[(prepared["game_date"] < today_ts) & (prepared["game_date"] >= start_ts)]
    if len(hist) < min_history_pitches:
        return _mark_projection_unavailable(games, f"insufficient_history:{len(hist)}")

    target_pitchers: set[int] = set()
    target_hitters: set[int] = set()
    for game in projection_games:
        for side in ("away", "home"):
            starter = _starter_id(game, side)
            if starter:
                target_pitchers.add(starter)
            target_hitters.update(_lineup_ids(game, side))

    try:
        pitcher_hist = hist[hist["pitcher"].isin(target_pitchers)]
        hitter_hist = hist[hist["batter"].isin(target_hitters)]
        as_of = str((today_ts - timedelta(days=1)).date())
        pitcher_vectors = aggregate_pitcher_vectors(pitcher_hist, as_of=as_of)
        hitter_vectors = aggregate_hitter_inverse_vectors(hitter_hist, as_of=as_of)
    except Exception as exc:
        return _mark_projection_unavailable(games, f"vector_build_failed: {exc}")

    summary = {
        "available": True,
        "lookback_days": lookback_days,
        "history_pitches": int(len(hist)),
        "pitcher_vectors": len(pitcher_vectors),
        "hitter_vectors": len(hitter_vectors),
        "blocked": 0,
        "passed": 0,
        "failed": 0,
        "scored": 0,
    }

    for game in games:
        game.setdefault("vector_projection_status", "NOT_APPLIED")

    for game in projection_games:
        away_starter = _starter_id(game, "away")
        home_starter = _starter_id(game, "home")
        away_hitters = _lineup_ids(game, "away")
        home_hitters = _lineup_ids(game, "home")
        try:
            away_score = score_lineup_matchup(home_starter, away_hitters, pitcher_vectors, hitter_vectors)
            home_score = score_lineup_matchup(away_starter, home_hitters, pitcher_vectors, hitter_vectors)
        except Exception as exc:
            game["vector_projection_status"] = "FAIL"
            game["vector_projection_reason"] = f"score_failed: {exc}"
            summary["failed"] += 1
            continue

        game["vector_projection_status"] = "SCORED"
        game["away_vector_matchup_delta"] = round(away_score["avg_matchup_delta"] or 0.0, 5)
        game["home_vector_matchup_delta"] = round(home_score["avg_matchup_delta"] or 0.0, 5)
        game["away_vector_xwoba"] = round(away_score["avg_projected_xwoba"] or 0.0, 5)
        game["home_vector_xwoba"] = round(home_score["avg_projected_xwoba"] or 0.0, 5)
        game["away_vector_hitters_scored"] = away_score["hitters_scored"]
        game["home_vector_hitters_scored"] = home_score["hitters_scored"]
        game["away_vector_missing_hitters"] = away_score["missing_hitters"]
        game["home_vector_missing_hitters"] = home_score["missing_hitters"]
        summary["scored"] += 1

    print(
        "  Vector projection: "
        f"{summary['scored']} scored, {summary['failed']} failed, "
        f"{summary['history_pitches']:,} history pitches, "
        f"{summary['pitcher_vectors']} pitcher vectors, {summary['hitter_vectors']} hitter vectors"
    )
    return summary


def apply_vector_gate_to_candidates(
    games: list[dict[str, Any]],
    *,
    min_conf: int = 8,
) -> dict[str, Any]:
    """Apply vector/xwOBA agreement to the post-projection C8+ board."""
    if os.environ.get("MLB_VECTOR_GATE_DISABLED") == "1":
        for game in games:
            game["vector_gate_status"] = "DISABLED"
        return {"available": False, "disabled": True, "blocked": 0, "passed": 0, "failed": 0, "scored": 0}

    min_vector_edge = _env_float("MLB_VECTOR_GATE_MIN_VECTOR_EDGE", DEFAULT_MIN_VECTOR_EDGE)
    min_xwoba_edge = _env_float("MLB_VECTOR_GATE_MIN_XWOBA_EDGE", DEFAULT_MIN_XWOBA_EDGE)
    candidates = _candidate_games(games, min_conf)

    summary = {
        "available": True,
        "min_vector_edge": min_vector_edge,
        "min_xwoba_edge": min_xwoba_edge,
        "blocked": 0,
        "passed": 0,
        "failed": 0,
        "scored": 0,
    }

    if not candidates:
        for game in games:
            game.setdefault("vector_gate_status", "NO_CANDIDATE")
        print("  Vector gate: no post-vector C8+ candidates")
        return summary

    for game in games:
        game.setdefault("vector_gate_status", "NOT_APPLIED")

    for game in candidates:
        picked_side = "away" if game.get("pick_team") == game.get("away_abbr") else "home"
        opp_side = "home" if picked_side == "away" else "away"

        game["vector_gate_pre_conf"] = int(game.get("conf") or 0)
        if game.get("vector_projection_status") != "SCORED":
            reason = game.get("vector_projection_reason") or game.get("vector_projection_status") or "not_scored"
            game["vector_gate_status"] = "UNAVAILABLE"
            game["vector_gate_reason"] = f"projection_unavailable: {reason}"
            game["conf"] = 0
            game["value"] = 0
            summary["blocked"] += 1
            summary["failed"] += 1
            continue

        picked_delta = float(game.get(f"{picked_side}_vector_matchup_delta") or 0.0)
        opp_delta = float(game.get(f"{opp_side}_vector_matchup_delta") or 0.0)
        picked_xwoba = float(game.get(f"{picked_side}_vector_xwoba") or 0.0)
        opp_xwoba = float(game.get(f"{opp_side}_vector_xwoba") or 0.0)
        vector_edge = picked_delta - opp_delta
        projected_xwoba_edge = picked_xwoba - opp_xwoba

        vector_pass = vector_edge >= min_vector_edge and projected_xwoba_edge >= min_xwoba_edge
        game["vector_edge"] = round(vector_edge, 5)
        game["vector_xwoba_edge"] = round(projected_xwoba_edge, 5)
        game["vector_gate_reason"] = (
            f"vec {vector_edge:+.5f} >= {min_vector_edge:+.5f}; "
            f"xwoba {projected_xwoba_edge:+.5f} >= {min_xwoba_edge:+.5f}"
        )
        summary["scored"] += 1

        if vector_pass:
            game["vector_gate_status"] = "PASS"
            summary["passed"] += 1
        else:
            game["vector_gate_status"] = "FAIL"
            game["conf"] = 0
            game["value"] = 0
            summary["blocked"] += 1
            summary["failed"] += 1

    print(
        "  Vector gate: "
        f"{summary['passed']} passed, {summary['blocked']} blocked, "
        f"{summary['scored']} candidates scored"
    )
    return summary


def apply_live_vector_gate(
    games: list[dict[str, Any]],
    *,
    today: str,
    atlas_dir: str | Path,
    min_conf: int = 8,
) -> dict[str, Any]:
    """Backward-compatible wrapper: score projections, then gate candidates."""
    projection_summary = apply_live_vector_projection(games, today=today, atlas_dir=atlas_dir)
    gate_summary = apply_vector_gate_to_candidates(games, min_conf=min_conf)
    return {
        **projection_summary,
        "gate": gate_summary,
        "blocked": gate_summary.get("blocked", 0),
        "passed": gate_summary.get("passed", 0),
        "failed": gate_summary.get("failed", 0),
    }


def dump_summary(path: str | Path, summary: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")

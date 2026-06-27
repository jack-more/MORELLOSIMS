#!/usr/bin/env python3
"""
Rolling backtest for the MLB vector matchup layer.

This script answers the first practical question:
  "If we had the pitcher-vector and hitter inverse-vector layer on that day,
   would it have agreed with the published side, and did that agreement
   separate winners from losers?"

It does not publish picks and it does not train a model. It uses only
pitch-level rows before each pick date to build rolling vectors, then scores:

  picked lineup vs opposing starter
  opponent lineup vs picked starter

vector_edge = picked_lineup_avg_delta - opponent_lineup_avg_delta

Positive vector_edge means the vector layer liked the published side's hitter
matchup more than the opponent's. The summary buckets actual ROI by that signal.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
ATLAS_DIR = REPO_ROOT / "atlas"
PICKS_PATH = REPO_ROOT / "picks" / "mlb.json"
PICKS_LOG_PATH = REPO_ROOT / "mlbsim" / "picks_log.csv"

sys.path.insert(0, str(SCRIPT_DIR))
from mlb_vector_features import (  # noqa: E402
    aggregate_hitter_inverse_vectors,
    aggregate_pitcher_vectors,
    prepare_statcast_frame,
    score_lineup_matchup,
)


@dataclass
class PickRow:
    id: str
    date: str
    away: str
    home: str
    side: str
    odds: int
    conf: int
    units: float
    status: str
    pl: float
    result: str
    game_pk: int | None
    sim_edge: float | None
    away_ml: int | None = None
    home_ml: int | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest MLB vector matchup signal on settled picks.")
    parser.add_argument("--start", help="Pick start date YYYY-MM-DD.")
    parser.add_argument("--end", help="Pick end date YYYY-MM-DD.")
    parser.add_argument("--statcast-start", help="Statcast fetch/cache start date. Defaults to start-lookback.")
    parser.add_argument("--statcast-end", help="Statcast fetch/cache end date. Defaults to end date.")
    parser.add_argument("--input-csv", help="Existing Statcast CSV. If omitted, pybaseball fetches/caches data.")
    parser.add_argument("--cache-csv", help="Optional Statcast cache CSV.")
    parser.add_argument("--lookback-days", type=int, default=45, help="Rolling history window before each pick date.")
    parser.add_argument("--min-history-pitches", type=int, default=5000, help="Skip dates with less pitch history.")
    parser.add_argument("--min-conf", type=int, default=8)
    parser.add_argument("--max-picks", type=int, default=0, help="Limit number of picks for quick tests.")
    parser.add_argument(
        "--full-vectors",
        action="store_true",
        help="Build every pitcher and hitter vector for each date. Default is focused to tested lineups.",
    )
    parser.add_argument(
        "--snapshot-dir",
        default=str(ATLAS_DIR / ".vector_backtest_snapshots"),
        help="Directory for per-date vector snapshots.",
    )
    parser.add_argument("--no-snapshot-cache", action="store_true", help="Disable per-date vector snapshot reuse.")
    parser.add_argument("--picks-json", default=str(PICKS_PATH))
    parser.add_argument("--picks-log", default=str(PICKS_LOG_PATH))
    parser.add_argument(
        "--out",
        default=str(ATLAS_DIR / "vector_backtest_preview.json"),
        help="JSON output path. Ignored by git.",
    )
    return parser.parse_args()


def american_to_int(value: Any) -> int | None:
    if value in (None, "", "—"):
        return None
    try:
        return int(str(value).replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def implied_prob(odds: int | None) -> float | None:
    if odds is None or odds == 0:
        return None
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)


def no_vig_prob(side: str, away: str, home: str, away_ml: int | None, home_ml: int | None) -> float | None:
    away_imp = implied_prob(away_ml)
    home_imp = implied_prob(home_ml)
    if away_imp is None or home_imp is None:
        return None
    total = away_imp + home_imp
    if total <= 0:
        return None
    if side == away:
        return away_imp / total
    if side == home:
        return home_imp / total
    return None


def load_pick_log_prices(path: str | Path) -> dict[tuple[str, str, str], tuple[int | None, int | None]]:
    prices = {}
    path = Path(path)
    if not path.exists():
        return prices
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            key = (row.get("date", ""), row.get("away", ""), row.get("home", ""))
            prices[key] = (american_to_int(row.get("away_ml")), american_to_int(row.get("home_ml")))
    return prices


def load_picks(args: argparse.Namespace) -> list[PickRow]:
    with Path(args.picks_json).open() as f:
        raw = json.load(f)
    prices = load_pick_log_prices(args.picks_log)
    picks: list[PickRow] = []
    for row in raw:
        if row.get("sport") != "mlb" or row.get("status") not in {"win", "loss"}:
            continue
        conf = int(row.get("conf") or 0)
        if conf < args.min_conf:
            continue
        date = row.get("date", "")
        if args.start and date < args.start:
            continue
        if args.end and date > args.end:
            continue
        away = row.get("away", "")
        home = row.get("home", "")
        away_ml, home_ml = prices.get((date, away, home), (None, None))
        odds = american_to_int(row.get("odds"))
        if odds is None:
            continue
        picks.append(
            PickRow(
                id=row.get("id", ""),
                date=date,
                away=away,
                home=home,
                side=row.get("side", ""),
                odds=odds,
                conf=conf,
                units=float(row.get("units") or 0),
                status=row.get("status", ""),
                pl=float(row.get("pl") or 0),
                result=row.get("result") or "",
                game_pk=int(row["game_pk"]) if row.get("game_pk") else None,
                sim_edge=float(row.get("sim_edge")) if row.get("sim_edge") is not None else None,
                away_ml=away_ml,
                home_ml=home_ml,
            )
        )
    picks.sort(key=lambda p: (p.date, p.id))
    if args.max_picks:
        picks = picks[-args.max_picks :]
    return picks


def load_statcast(args: argparse.Namespace, pick_start: str, pick_end: str) -> pd.DataFrame:
    if args.input_csv:
        print(f"Loading Statcast CSV: {args.input_csv}")
        return pd.read_csv(args.input_csv)

    start = args.statcast_start
    if not start:
        first = datetime.strptime(pick_start, "%Y-%m-%d").date()
        start = str(first - timedelta(days=args.lookback_days + 5))
    end = args.statcast_end or pick_end
    cache = Path(args.cache_csv) if args.cache_csv else ATLAS_DIR / f".statcast_cache_{start}_{end}.csv"
    if cache.exists():
        print(f"Loading cached Statcast CSV: {cache}")
        return pd.read_csv(cache)

    try:
        from pybaseball import statcast
    except ImportError as exc:
        raise SystemExit("pybaseball is required unless --input-csv is supplied") from exc

    print(f"Fetching Statcast: {start} -> {end}")
    df = statcast(start, end)
    if df is None or df.empty:
        raise SystemExit("No Statcast rows returned")
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache, index=False)
    print(f"Cached Statcast rows: {cache}")
    return df


def fetch_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.loads(response.read())


def boxscore_for_game(game_pk: int, cache: dict[int, dict[str, Any]]) -> dict[str, Any] | None:
    if game_pk in cache:
        return cache[game_pk]
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
    try:
        cache[game_pk] = fetch_json(url)
        time.sleep(0.05)
    except Exception as exc:
        print(f"  WARN boxscore {game_pk}: {exc}")
        cache[game_pk] = None
    return cache[game_pk]


def parse_boxscore_lineups(box: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for side in ("away", "home"):
        team = box.get("teams", {}).get(side, {})
        players = team.get("players", {})
        starters_by_slot = {}
        for player_key, player in players.items():
            order_raw = player.get("battingOrder")
            if not order_raw:
                continue
            try:
                order = int(order_raw)
            except (TypeError, ValueError):
                continue
            slot = order // 100
            person = player.get("person") or {}
            pid = person.get("id")
            if not pid:
                continue
            if slot not in starters_by_slot or order < starters_by_slot[slot][0]:
                starters_by_slot[slot] = (order, int(pid))
        hitters = [pid for _, pid in sorted(starters_by_slot.values())][:9]
        pitchers = team.get("pitchers") or []
        result[side] = {
            "hitters": hitters,
            "starter": int(pitchers[0]) if pitchers else None,
        }
    return result


def target_players_for_date(
    picks: list[PickRow], box_cache: dict[int, dict[str, Any]]
) -> tuple[set[int], set[int], list[dict[str, Any]]]:
    pitcher_ids: set[int] = set()
    hitter_ids: set[int] = set()
    skipped = []
    for pick in picks:
        if not pick.game_pk:
            skipped.append({"id": pick.id, "date": pick.date, "reason": "missing_game_pk"})
            continue
        box = boxscore_for_game(pick.game_pk, box_cache)
        if not box:
            skipped.append({"id": pick.id, "date": pick.date, "reason": "boxscore_failed"})
            continue
        parsed = parse_boxscore_lineups(box)
        for side in ("away", "home"):
            starter = parsed.get(side, {}).get("starter")
            if starter:
                pitcher_ids.add(int(starter))
            hitter_ids.update(int(pid) for pid in parsed.get(side, {}).get("hitters", []))
    return pitcher_ids, hitter_ids, skipped


def vector_snapshot_path(
    args: argparse.Namespace,
    pick_date: str,
    target_pitchers: set[int] | None,
    target_hitters: set[int] | None,
) -> Path | None:
    if args.no_snapshot_cache:
        return None
    mode = "full" if args.full_vectors else "focused"
    key_payload = {
        "date": pick_date,
        "lookback_days": args.lookback_days,
        "mode": mode,
        "target_pitchers": sorted(target_pitchers or []),
        "target_hitters": sorted(target_hitters or []),
    }
    key = hashlib.sha1(json.dumps(key_payload, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return Path(args.snapshot_dir) / f"{pick_date}_lb{args.lookback_days}_{mode}_{key}.json.gz"


def load_vector_snapshot(path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    if not path.exists():
        return None
    with gzip.open(path, "rt") as f:
        payload = json.load(f)
    meta = payload.get("meta") or {}
    meta["snapshot_cache"] = str(path)
    return payload.get("pitcher_vectors", {}), payload.get("hitter_vectors", {}), meta


def save_vector_snapshot(
    path: Path,
    pitcher_vectors: dict[str, Any],
    hitter_vectors: dict[str, Any],
    meta: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": meta,
        "pitcher_vectors": pitcher_vectors,
        "hitter_vectors": hitter_vectors,
    }
    with gzip.open(path, "wt") as f:
        json.dump(payload, f)


def build_vectors_for_date(
    prepared: pd.DataFrame,
    pick_date: str,
    lookback_days: int,
    min_history_pitches: int,
    target_pitchers: set[int] | None = None,
    target_hitters: set[int] | None = None,
    snapshot_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    if snapshot_path:
        cached = load_vector_snapshot(snapshot_path)
        if cached:
            return cached

    date = pd.to_datetime(pick_date)
    start = date - timedelta(days=lookback_days)
    hist = prepared[(prepared["game_date"] < date) & (prepared["game_date"] >= start)]
    if len(hist) < min_history_pitches:
        print(f"  SKIP {pick_date}: only {len(hist):,} history pitches")
        return None

    pitcher_hist = hist
    hitter_hist = hist
    if target_pitchers is not None:
        pitcher_hist = hist[hist["pitcher"].isin(target_pitchers)]
    if target_hitters is not None:
        hitter_hist = hist[hist["batter"].isin(target_hitters)]

    as_of = str((date - timedelta(days=1)).date())
    pitcher_vectors = aggregate_pitcher_vectors(pitcher_hist, as_of=as_of)
    hitter_vectors = aggregate_hitter_inverse_vectors(hitter_hist, as_of=as_of)
    meta = {
        "history_pitches": int(len(hist)),
        "pitcher_history_pitches": int(len(pitcher_hist)),
        "hitter_history_pitches": int(len(hitter_hist)),
        "history_start": str(start.date()),
        "history_end": str((date - timedelta(days=1)).date()),
        "pitcher_vectors": len(pitcher_vectors),
        "hitter_vectors": len(hitter_vectors),
        "focused": target_pitchers is not None or target_hitters is not None,
        "target_pitchers": len(target_pitchers or []),
        "target_hitters": len(target_hitters or []),
    }
    if snapshot_path:
        save_vector_snapshot(snapshot_path, pitcher_vectors, hitter_vectors, meta)
        meta["snapshot_cache"] = str(snapshot_path)
    return pitcher_vectors, hitter_vectors, meta


def score_pick(
    pick: PickRow,
    box_cache: dict[int, dict[str, Any]],
    pitcher_vectors: dict[str, Any],
    hitter_vectors: dict[str, Any],
) -> dict[str, Any] | None:
    if not pick.game_pk:
        return None
    box = boxscore_for_game(pick.game_pk, box_cache)
    if not box:
        return None
    parsed = parse_boxscore_lineups(box)
    picked_side = "away" if pick.side == pick.away else "home" if pick.side == pick.home else None
    if not picked_side:
        return None
    opp_side = "home" if picked_side == "away" else "away"
    picked_lineup = parsed[picked_side]["hitters"]
    opp_lineup = parsed[opp_side]["hitters"]
    picked_starter = parsed[picked_side]["starter"]
    opp_starter = parsed[opp_side]["starter"]
    if not picked_lineup or not opp_lineup or not picked_starter or not opp_starter:
        return None

    try:
        picked_score = score_lineup_matchup(opp_starter, picked_lineup, pitcher_vectors, hitter_vectors)
        opp_score = score_lineup_matchup(picked_starter, opp_lineup, pitcher_vectors, hitter_vectors)
    except KeyError as exc:
        return {
            "id": pick.id,
            "date": pick.date,
            "matchup": f"{pick.away} @ {pick.home}",
            "pick_text": f"{pick.side} ML",
            "status": pick.status,
            "pl": pick.pl,
            "units": pick.units,
            "skip_reason": str(exc),
        }

    vector_edge = (picked_score["avg_matchup_delta"] or 0.0) - (opp_score["avg_matchup_delta"] or 0.0)
    projected_xwoba_edge = (picked_score["avg_projected_xwoba"] or 0.0) - (
        opp_score["avg_projected_xwoba"] or 0.0
    )
    market_prob = no_vig_prob(pick.side, pick.away, pick.home, pick.away_ml, pick.home_ml)
    return {
        "id": pick.id,
        "date": pick.date,
        "matchup": f"{pick.away} @ {pick.home}",
        "pick_text": f"{pick.side} ML",
        "conf": pick.conf,
        "odds": pick.odds,
        "away_ml": pick.away_ml,
        "home_ml": pick.home_ml,
        "market_no_vig_prob": round(market_prob, 4) if market_prob is not None else None,
        "status": pick.status,
        "result": pick.result,
        "units": pick.units,
        "pl": pick.pl,
        "sim_edge": pick.sim_edge,
        "picked_starter": picked_starter,
        "opponent_starter": opp_starter,
        "picked_hitters_scored": picked_score["hitters_scored"],
        "opp_hitters_scored": opp_score["hitters_scored"],
        "picked_avg_delta": picked_score["avg_matchup_delta"],
        "opp_avg_delta": opp_score["avg_matchup_delta"],
        "vector_edge": round(vector_edge, 5),
        "projected_xwoba_edge": round(projected_xwoba_edge, 5),
        "picked_avg_projected_xwoba": picked_score["avg_projected_xwoba"],
        "opp_avg_projected_xwoba": opp_score["avg_projected_xwoba"],
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    settled = [row for row in rows if row.get("status") in {"win", "loss"} and not row.get("skip_reason")]
    if not settled:
        return {"n": 0}
    wins = sum(1 for row in settled if row["status"] == "win")
    losses = sum(1 for row in settled if row["status"] == "loss")
    risk = sum(float(row.get("units") or 0) for row in settled)
    pl = sum(float(row.get("pl") or 0) for row in settled)
    return {
        "n": len(settled),
        "wins": wins,
        "losses": losses,
        "roi": round(pl / risk * 100, 2) if risk else None,
        "pl": round(pl, 2),
        "risk": round(risk, 2),
        "avg_vector_edge": round(sum(float(row.get("vector_edge") or 0) for row in settled) / len(settled), 5),
        "avg_xwoba_edge": round(
            sum(float(row.get("projected_xwoba_edge") or 0) for row in settled) / len(settled), 5
        ),
    }


def bucket_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    buckets = {
        "vector_edge_lt_-010": [],
        "vector_edge_-010_to_000": [],
        "vector_edge_000_to_010": [],
        "vector_edge_010_to_020": [],
        "vector_edge_gte_020": [],
    }
    for row in rows:
        if row.get("skip_reason") or row.get("vector_edge") is None:
            continue
        edge = float(row["vector_edge"])
        if edge < -0.010:
            buckets["vector_edge_lt_-010"].append(row)
        elif edge < 0:
            buckets["vector_edge_-010_to_000"].append(row)
        elif edge < 0.010:
            buckets["vector_edge_000_to_010"].append(row)
        elif edge < 0.020:
            buckets["vector_edge_010_to_020"].append(row)
        else:
            buckets["vector_edge_gte_020"].append(row)
    return {name: aggregate(bucket) for name, bucket in buckets.items()}


def threshold_summaries(
    rows: list[dict[str, Any]], field: str, thresholds: list[float]
) -> dict[str, dict[str, Any]]:
    out = {}
    digits = 4 if field == "vector_edge" else 3
    for threshold in thresholds:
        kept = [
            row
            for row in rows
            if not row.get("skip_reason")
            and row.get("status") in {"win", "loss"}
            and row.get(field) is not None
            and float(row[field]) >= threshold
        ]
        out[f"{field}_gte_{threshold:+.{digits}f}"] = aggregate(kept)
    return out


def combined_threshold_summaries(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    combos = [
        (0.0, -0.020),
        (0.0, 0.000),
        (0.0, 0.010),
        (0.0, 0.020),
        (0.0005, 0.010),
        (0.0005, 0.020),
        (0.0010, 0.000),
    ]
    out = {}
    for vector_threshold, xwoba_threshold in combos:
        kept = [
            row
            for row in rows
            if not row.get("skip_reason")
            and row.get("status") in {"win", "loss"}
            and row.get("vector_edge") is not None
            and row.get("projected_xwoba_edge") is not None
            and float(row["vector_edge"]) >= vector_threshold
            and float(row["projected_xwoba_edge"]) >= xwoba_threshold
        ]
        key = f"vector_gte_{vector_threshold:+.4f}_xwoba_gte_{xwoba_threshold:+.3f}"
        out[key] = aggregate(kept)
    return out


def main() -> None:
    args = parse_args()
    picks = load_picks(args)
    if not picks:
        raise SystemExit("No settled picks matched filters")
    pick_start = args.start or min(p.date for p in picks)
    pick_end = args.end or max(p.date for p in picks)
    print(f"Picks: {len(picks)} settled C{args.min_conf}+ from {pick_start} to {pick_end}")

    raw = load_statcast(args, pick_start, pick_end)
    print("Preparing Statcast frame...")
    prepared = prepare_statcast_frame(raw).dropna(subset=["pitcher", "batter"])
    print(f"Prepared {len(prepared):,} pitches")

    rows = []
    skipped = []
    box_cache: dict[int, dict[str, Any]] = {}
    for date in sorted({p.date for p in picks}):
        print(f"\nDate {date}")
        picks_for_date = [p for p in picks if p.date == date]
        target_pitchers = None
        target_hitters = None
        if not args.full_vectors:
            target_pitchers, target_hitters, target_skips = target_players_for_date(picks_for_date, box_cache)
            skipped.extend(target_skips)
            print(f"  targets: {len(target_pitchers)} pitchers, {len(target_hitters)} hitters")
        snapshot_path = vector_snapshot_path(args, date, target_pitchers, target_hitters)
        vectors_for_date = build_vectors_for_date(
            prepared,
            date,
            args.lookback_days,
            args.min_history_pitches,
            target_pitchers=target_pitchers,
            target_hitters=target_hitters,
            snapshot_path=snapshot_path,
        )
        if vectors_for_date is None:
            for pick in picks_for_date:
                skipped.append({"id": pick.id, "date": pick.date, "reason": "insufficient_history"})
            continue
        pitcher_vectors, hitter_vectors, meta = vectors_for_date
        print(
            f"  vectors: {meta['pitcher_vectors']} pitchers, {meta['hitter_vectors']} hitters "
            f"from {meta['history_pitches']:,} pitches"
        )
        for pick in picks_for_date:
            row = score_pick(pick, box_cache, pitcher_vectors, hitter_vectors)
            if row is None:
                skipped.append({"id": pick.id, "date": pick.date, "reason": "score_failed"})
                continue
            if row.get("skip_reason"):
                skipped.append({"id": pick.id, "date": pick.date, "reason": row["skip_reason"]})
            else:
                print(
                    f"  {row['matchup']:<12} {row['pick_text']:<7} "
                    f"{row['status']:<4} {row['pl']:>7} "
                    f"vec={row['vector_edge']:+.5f} xwoba={row['projected_xwoba_edge']:+.5f}"
                )
            rows.append(row)

    payload = {
        "config": {
            "pick_start": pick_start,
            "pick_end": pick_end,
            "lookback_days": args.lookback_days,
            "min_history_pitches": args.min_history_pitches,
            "min_conf": args.min_conf,
            "focused_vectors": not args.full_vectors,
            "snapshot_dir": None if args.no_snapshot_cache else str(Path(args.snapshot_dir)),
        },
        "summary": aggregate(rows),
        "buckets": bucket_rows(rows),
        "thresholds": {
            "vector_edge": threshold_summaries(
                rows, "vector_edge", [-0.010, -0.005, 0.0, 0.0005, 0.0010, 0.0015, 0.0020]
            ),
            "projected_xwoba_edge": threshold_summaries(
                rows, "projected_xwoba_edge", [-0.025, 0.0, 0.010, 0.020, 0.030, 0.040, 0.050]
            ),
            "combined": combined_threshold_summaries(rows),
        },
        "skipped": skipped,
        "rows": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    print("\nSUMMARY")
    print(json.dumps(payload["summary"], indent=2))
    print("\nTHRESHOLDS")
    print(json.dumps(payload["thresholds"], indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()

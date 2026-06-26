#!/usr/bin/env python3
"""
Build the MLB pitcher vector database.

This is the first step of the new matchup system. It turns pitch-level
Statcast data into:
  - data/mlb_vectors.sqlite
  - atlas/pitcher_vectors.json
  - atlas/hitter_inverse_vectors.json

The generated database and vector JSON files are ignored by git because they
are reproducible and can get large.

Examples:
  python3 scripts/build_mlb_vector_db.py --start 2026-06-01 --end 2026-06-26
  python3 scripts/build_mlb_vector_db.py --input-csv /tmp/statcast.csv --db-path /tmp/mlb_vectors.sqlite
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
ATLAS_DIR = REPO_ROOT / "atlas"
DATA_DIR = REPO_ROOT / "data"

sys.path.insert(0, str(SCRIPT_DIR))
from mlb_vector_features import (  # noqa: E402
    aggregate_hitter_inverse_vectors,
    aggregate_pitcher_vectors,
    prepare_statcast_frame,
)


DEFAULT_COLUMNS = [
    "game_date",
    "game_pk",
    "pitcher",
    "player_name",
    "p_throws",
    "batter",
    "stand",
    "pitch_type",
    "pitch_family",
    "velocity_band",
    "movement_band",
    "location_bucket",
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
    "xwoba_value",
    "inning",
    "at_bat_number",
    "pitch_number",
    "is_pa_end",
    "is_swing",
    "is_whiff",
    "is_csw",
    "is_chase",
    "is_k",
    "is_bb",
    "is_hard_hit",
    "is_barrel_proxy",
    "times_through_order",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build MLB pitcher and hitter vector data.")
    parser.add_argument("--start", help="Start date YYYY-MM-DD for Statcast fetch.")
    parser.add_argument("--end", help="End date YYYY-MM-DD for Statcast fetch.")
    parser.add_argument("--input-csv", help="Use an existing Statcast CSV instead of fetching.")
    parser.add_argument("--cache-csv", help="Optional raw Statcast cache CSV path.")
    parser.add_argument(
        "--db-path",
        default=str(DATA_DIR / "mlb_vectors.sqlite"),
        help="SQLite output path. Default: data/mlb_vectors.sqlite",
    )
    parser.add_argument(
        "--pitcher-out",
        default=str(ATLAS_DIR / "pitcher_vectors.json"),
        help="Pitcher vector JSON output path.",
    )
    parser.add_argument(
        "--hitter-out",
        default=str(ATLAS_DIR / "hitter_inverse_vectors.json"),
        help="Hitter inverse vector JSON output path.",
    )
    parser.add_argument(
        "--sample-rows",
        type=int,
        default=0,
        help="Keep only the first N rows after load. Useful for smoke tests.",
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Write JSON outputs only.",
    )
    return parser.parse_args()


def load_statcast(args: argparse.Namespace) -> pd.DataFrame:
    if args.input_csv:
        print(f"Loading Statcast CSV: {args.input_csv}")
        return pd.read_csv(args.input_csv)

    if not args.start or not args.end:
        raise SystemExit("--start and --end are required unless --input-csv is supplied")

    cache_path = Path(args.cache_csv) if args.cache_csv else ATLAS_DIR / f".statcast_cache_{args.start}_{args.end}.csv"
    if cache_path.exists():
        print(f"Loading cached Statcast CSV: {cache_path}")
        return pd.read_csv(cache_path)

    try:
        from pybaseball import statcast
    except ImportError as exc:
        raise SystemExit("pybaseball is required for live Statcast fetches") from exc

    print(f"Fetching Statcast: {args.start} -> {args.end}")
    df = statcast(args.start, args.end)
    if df is None or df.empty:
        raise SystemExit("No Statcast rows returned")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path, index=False)
    print(f"Cached raw Statcast rows: {cache_path}")
    return df


def json_dump(path: str | Path, payload: Any) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        json.dump(payload, f, indent=2, default=_json_default)
        f.write("\n")
    print(f"Wrote {out} ({out.stat().st_size:,} bytes)")


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def write_sqlite(db_path: str | Path, df: pd.DataFrame, pitcher_vectors: dict, hitter_vectors: dict) -> None:
    db = Path(db_path)
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()

    fact = df[[column for column in DEFAULT_COLUMNS if column in df.columns]].copy()
    for column in fact.columns:
        if str(fact[column].dtype) == "boolean":
            fact[column] = fact[column].astype("Int64")
    fact["game_date"] = fact["game_date"].astype(str)

    pitcher_rows = [
        {
            "pitcher": int(pid),
            "as_of": vector.get("as_of"),
            "sample_pitches": vector.get("sample", {}).get("pitches"),
            "sample_pa": vector.get("sample", {}).get("pa"),
            "vector_json": json.dumps(vector, separators=(",", ":"), default=_json_default),
        }
        for pid, vector in pitcher_vectors.items()
    ]
    hitter_rows = [
        {
            "batter": int(bid),
            "as_of": vector.get("as_of"),
            "sample_pitches": vector.get("sample", {}).get("pitches"),
            "sample_pa": vector.get("sample", {}).get("pa"),
            "vector_json": json.dumps(vector, separators=(",", ":"), default=_json_default),
        }
        for bid, vector in hitter_vectors.items()
    ]

    with sqlite3.connect(db) as conn:
        fact.to_sql("fact_pitches", conn, index=False, if_exists="replace")
        pd.DataFrame(pitcher_rows).to_sql("pitcher_vectors", conn, index=False, if_exists="replace")
        pd.DataFrame(hitter_rows).to_sql("hitter_inverse_vectors", conn, index=False, if_exists="replace")
        conn.execute("CREATE INDEX idx_fact_pitcher_date ON fact_pitches(pitcher, game_date)")
        conn.execute("CREATE INDEX idx_fact_batter_date ON fact_pitches(batter, game_date)")
        conn.execute("CREATE INDEX idx_pitcher_vectors_pitcher ON pitcher_vectors(pitcher)")
        conn.execute("CREATE INDEX idx_hitter_vectors_batter ON hitter_inverse_vectors(batter)")
    print(f"Wrote {db} ({db.stat().st_size:,} bytes)")


def main() -> None:
    args = parse_args()
    raw = load_statcast(args)
    if args.sample_rows:
        raw = raw.head(args.sample_rows).copy()
        print(f"Sampled first {len(raw)} rows")

    print("Preparing pitch-level features...")
    prepared = prepare_statcast_frame(raw)
    prepared = prepared.dropna(subset=["pitcher", "batter"])
    print(
        "Prepared "
        f"{len(prepared):,} pitches, "
        f"{prepared['pitcher'].nunique():,} pitchers, "
        f"{prepared['batter'].nunique():,} hitters"
    )

    print("Building pitcher vectors...")
    pitcher_vectors = aggregate_pitcher_vectors(prepared)
    print(f"Pitcher vectors: {len(pitcher_vectors):,}")

    print("Building hitter inverse vectors...")
    hitter_vectors = aggregate_hitter_inverse_vectors(prepared)
    print(f"Hitter inverse vectors: {len(hitter_vectors):,}")

    json_dump(args.pitcher_out, pitcher_vectors)
    json_dump(args.hitter_out, hitter_vectors)

    if not args.skip_db:
        write_sqlite(args.db_path, prepared, pitcher_vectors, hitter_vectors)

    print("Vector build complete.")


if __name__ == "__main__":
    main()


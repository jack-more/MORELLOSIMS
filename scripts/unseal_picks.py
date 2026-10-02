#!/usr/bin/env python3
"""Unseal every sealed pick whose game has started (seal mode).

Runs first in every MLB / NBA pipeline job. For each public file it rewrites
records whose first pitch / tip has passed in plaintext:

  picks/mlb.json, picks/nba.json   plaintext + "nonce", "unsealed_at",
                                   "seal_keys" (+ "sealed_id" for NBA), so
                                   scripts/verify_seal.py can check the
                                   published commitment
  nba_pipeline/data/picks.csv, pick_log.json, daily_picks.json,
  mlbsim/picks_log.csv, reports/shadow_mlb.json
                                   restored verbatim

NBA picks captured while sealed are inserted into nba_sim.db here (capture
defers them: the DB is committed publicly).

No sealed records → touches nothing (seal mode off is a no-op). Sealed
records that are due but PICKS_SEAL_KEY is missing → exit 1: settlement
must never see sealed data, so the pipeline stops here.

  python3 scripts/unseal_picks.py [--sport mlb|nba|all] [--dry-run]

Each pipeline unseals only its own lane (MLB: picks/mlb.json,
mlbsim/picks_log.csv, reports/shadow_mlb.json; NBA: picks/nba.json and
nba_pipeline/data + db; NFL: picks/nfl.json, reports/shadow_nfl.json), so
its working tree holds only files it commits.
"""

import argparse
import csv
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import picks_store as store  # noqa: E402

REPO = store.REPO
NBA = os.path.join(REPO, "nba_pipeline")
NBA_DATA = os.path.join(NBA, "data")
PICKS_CSV = os.path.join(NBA_DATA, "picks.csv")
PICK_LOG = os.path.join(NBA_DATA, "pick_log.json")
DAILY = os.path.join(NBA_DATA, "daily_picks.json")
MLB_PICKS_LOG = os.path.join(REPO, "mlbsim", "picks_log.csv")
SHADOW = os.path.join(REPO, "reports", "shadow_mlb.json")
SHADOW_NFL = os.path.join(REPO, "reports", "shadow_nfl.json")


class Run:
    def __init__(self, dry):
        self.dry = dry
        self.blocked = []   # (file, n) due but cannot open (no key)
        self.changed = []   # (file, n)

    def due(self, rec):
        return store.is_raw_sealed(rec) and store.has_started(rec)

    def write(self, path, text, n):
        self.changed.append((os.path.relpath(path, REPO), n))
        if not self.dry:
            with open(path, "w", newline="") as f:
                f.write(text)


def _read(path):
    try:
        with open(path, newline="") as f:
            return f.read()
    except FileNotFoundError:
        return None


def unseal_pick_files(run, sports):
    for sport, path in store.PICK_FILES.items():
        if sport not in sports:
            continue
        raw = store._read_raw(path)
        sealed = [r for r in raw if store.is_raw_sealed(r)]
        due = [r for r in sealed if store.has_started(r)]
        if not due and not (sealed and not store.seal_mode()):
            continue
        if not store.have_key():
            run.blocked.append((os.path.relpath(path, REPO), len(due)))
            continue
        out = store.prepare_picks(store.load_picks(path), raw)
        text = json.dumps(out, indent=2)
        if text != _read(path):
            opened = {r.get("commitment") for r in raw if store.is_raw_sealed(r)} - {
                r.get("commitment") for r in out if store.is_raw_sealed(r)}
            run.write(path, text, len(opened))


def unseal_json_list(run, path, get_list, set_list, dump_kwargs, on_open=None):
    text = _read(path)
    if text is None:
        return
    data = json.loads(text)
    items = get_list(data)
    due = [i for i, r in enumerate(items) if run.due(r)]
    if not due:
        return
    if not store.have_key():
        run.blocked.append((os.path.relpath(path, REPO), len(due)))
        return
    opened = []
    for i in due:
        items[i] = store.open_record(items[i])
        opened.append(items[i])
    set_list(data, items)
    run.write(path, json.dumps(data, **dump_kwargs), len(due))
    if on_open and not run.dry:
        on_open(opened)


def unseal_csv(run, path, reader_open):
    text = _read(path)
    if text is None or store.BLOB_COL not in text.split("\n", 1)[0]:
        return
    reader = csv.DictReader(io.StringIO(text))
    fields = [f for f in reader.fieldnames if f != store.BLOB_COL]
    rows = list(reader)
    due = [i for i, r in enumerate(rows) if r.get(store.BLOB_COL) and store.has_started(r)]
    if not due:
        return
    if not store.have_key():
        run.blocked.append((os.path.relpath(path, REPO), len(due)))
        return
    for i in due:
        rows[i] = reader_open(rows[i], fields)
    out = io.StringIO()
    names = store.csv_fieldnames(fields, rows)
    w = csv.DictWriter(out, fieldnames=names, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") if r.get(k) is not None else "" for k in names})
    run.write(path, out.getvalue(), len(due))


def _open_csv(row, fields):
    plain = store.decrypt(row[store.BLOB_COL])["row"]
    return {f: plain.get(f, "") for f in fields}


def _nba_db_backfill(entries):
    """Picks captured while sealed were kept out of nba_sim.db; add them now."""
    if not entries:
        return
    sys.path.insert(0, NBA)
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "capture_picks_unseal", os.path.join(NBA, "scripts", "capture_picks.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.insert_picks_db(entries)
    print(f"  nba_sim.db: inserted {len(entries)} unsealed pick(s)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sport", choices=["mlb", "nba", "nfl", "all"], default="all")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run = Run(a.dry_run)
    sports = ("mlb", "nba", "nfl") if a.sport == "all" else (a.sport,)

    unseal_pick_files(run, sports)
    if "nba" in sports:
        unseal_csv(run, PICKS_CSV, _open_csv)
        unseal_json_list(run, PICK_LOG, lambda d: d, lambda d, v: d.__setitem__(slice(None), v),
                         {"indent": 2}, on_open=_nba_db_backfill)
        unseal_json_list(run, DAILY, lambda d: d.get("games") or [], lambda d, v: d.__setitem__("games", v),
                         {"indent": 2})
    if "mlb" in sports:
        unseal_csv(run, MLB_PICKS_LOG, _open_csv)

        def shadow_items(d):
            return list((d.get("rows") or {}).values())

        def shadow_set(d, items):
            d["rows"] = dict(zip((d.get("rows") or {}).keys(), items))

        unseal_json_list(run, SHADOW, shadow_items, shadow_set, {"separators": (",", ":")})
    if "nfl" in sports:
        def nfl_items(d):
            return list((d.get("rows") or {}).values())

        def nfl_set(d, items):
            d["rows"] = dict(zip((d.get("rows") or {}).keys(), items))

        unseal_json_list(run, SHADOW_NFL, nfl_items, nfl_set, {"indent": 1})

    for path, n in run.changed:
        print(f"  unsealed {n} record(s) in {path}" + (" (dry run)" if run.dry else ""))
    if run.blocked:
        for path, n in run.blocked:
            print(f"::error::{n} sealed record(s) in {path} are due (game started) but "
                  f"{store.KEY_ENV} is not set — cannot unseal")
        return 1
    if not run.changed:
        print("  unseal: nothing due")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

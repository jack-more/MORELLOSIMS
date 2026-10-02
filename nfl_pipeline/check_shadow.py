#!/usr/bin/env python3
"""check_shadow.py — integrity guardrail for reports/shadow_nfl.json.

Fails (exit 1) when:
  * a row in the committed ledger (git HEAD) is missing now (nothing is deleted);
  * a row's `first` capture changed after it was committed;
  * a final row's result changed, or a row went backwards (final → open, ...);
  * any capture's captured_at is not strictly before the row's kickoff;
  * a "missed" row carries a capture (missed games are never backfilled);
  * a final row has no result.

Sealed rows (seal mode, no key) are checked for presence only.

  python3 nfl_pipeline/check_shadow.py            # compare against git HEAD
  python3 nfl_pipeline/check_shadow.py --no-git
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import REPO, SHADOW_LEDGER  # noqa: E402

sys.path.insert(0, os.path.join(REPO, "scripts"))
import picks_store  # noqa: E402

REPO_PATH = "reports/shadow_nfl.json"
ORDER = {"open": 0, "locked": 1, "final": 2, "missed": 2}


def head_rows():
    try:
        out = subprocess.run(["git", "show", f"HEAD:{REPO_PATH}"], capture_output=True, text=True, cwd=REPO)
    except FileNotFoundError:
        return None
    if out.returncode != 0:
        return None
    rows = json.loads(out.stdout).get("rows", {})
    return {k: picks_store.open_record(v) for k, v in rows.items()}


def check(rows, old=None):
    errors = []
    for gid, r in rows.items():
        if picks_store.is_raw_sealed(r):
            continue
        ko = picks_store.parse_ts(r.get("kickoff_utc"))
        if ko is None:
            errors.append(f"{gid}: no kickoff_utc")
            continue
        status = r.get("status")
        if status not in ORDER:
            errors.append(f"{gid}: unknown status {status!r}")
        if status == "missed":
            if r.get("first") or r.get("last"):
                errors.append(f"{gid}: missed row carries a capture")
            continue
        for k in ("first", "last"):
            c = r.get(k)
            if not c:
                errors.append(f"{gid}: no {k} capture")
                continue
            cap = picks_store.parse_ts(c.get("captured_at"))
            if cap is None or cap >= ko:
                errors.append(f"{gid}: {k} capture at {c.get('captured_at')} is not before kickoff {r['kickoff_utc']}")
        if status == "final" and not r.get("result"):
            errors.append(f"{gid}: final row without result")
    if old:
        for gid, o in old.items():
            n = rows.get(gid)
            if n is None:
                errors.append(f"{gid}: row deleted from shadow ledger")
                continue
            if picks_store.is_raw_sealed(o) or picks_store.is_raw_sealed(n):
                continue
            if o.get("first") and n.get("first") != o.get("first"):
                errors.append(f"{gid}: first capture rewritten")
            if ORDER.get(n.get("status"), 0) < ORDER.get(o.get("status"), 0):
                errors.append(f"{gid}: status went backwards {o.get('status')} -> {n.get('status')}")
            if o.get("status") == "final" and n.get("result") != o.get("result"):
                errors.append(f"{gid}: settled result restated")
            if o.get("status") in ("locked", "final") and n.get("last") != o.get("last"):
                errors.append(f"{gid}: capture changed after kickoff")
    return errors


def main():
    try:
        with open(SHADOW_LEDGER) as f:
            rows = json.load(f).get("rows", {})
    except FileNotFoundError:
        print("no shadow ledger yet")
        return 0
    rows = {k: picks_store.open_record(v) for k, v in rows.items()}
    old = None if "--no-git" in sys.argv else head_rows()
    errors = check(rows, old)
    if errors:
        for e in errors:
            print(f"::error::{e}")
        print(f"\nNFL shadow ledger check FAILED: {len(errors)} problem(s)")
        return 1
    st = {}
    for r in rows.values():
        st[r.get("status", "sealed")] = st.get(r.get("status", "sealed"), 0) + 1
    print(f"NFL shadow ledger check OK: {len(rows)} rows {st}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""check_ledger.py — integrity guardrail for data/picks.csv.

Fails (exit 1) when:
  * a row that exists in the committed ledger (git HEAD) is missing now
    (nothing is ever deleted — void it instead);
  * a settled row in HEAD changed its result, stake or profit (no restating
    after the fact; pending -> settled/void is the only allowed transition);
  * a counted row (W/L/P or pending) has no
    captured_at, or was captured at/after tip-off;
  * a stake differs from the stake in the pick_log.json capture record;
  * a settled row's profit is not what its stake and result imply;
  * a void row has no void_reason.

Usage:
  python scripts/check_ledger.py            # compare against git HEAD
  python scripts/check_ledger.py --no-git   # skip the HEAD comparison
"""

import csv
import io
import json
import os
import subprocess
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from utils.ledger import (  # noqa: E402
    SETTLED, VOID, capture_check, compute_profit, read_rows, row_odds,
)

PICKS_CSV = os.path.join(PROJECT_ROOT, "data", "picks.csv")
PICK_LOG = os.path.join(PROJECT_ROOT, "data", "pick_log.json")
REPO_PATH = "nba_pipeline/data/picks.csv"


def key(r):
    return (r["date"], r["matchup"], r["side"], r.get("type") or "spread")


def head_rows():
    try:
        out = subprocess.run(["git", "show", f"HEAD:{REPO_PATH}"], capture_output=True, text=True,
                             cwd=os.path.dirname(PROJECT_ROOT))
    except FileNotFoundError:
        return None
    if out.returncode != 0:
        return None
    return [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(io.StringIO(out.stdout))]


def log_index():
    if not os.path.exists(PICK_LOG):
        return {}
    idx = {}
    for p in json.load(open(PICK_LOG)):
        sd = p.get("slate_date", "")
        if sd[:1].isdigit():
            d = sd[:10]
        else:
            try:
                d = datetime.strptime(f"{sd} {p.get('captured_at', '')[:4]}", "%b %d %Y").strftime("%Y-%m-%d")
            except ValueError:
                continue
        idx[(d, p["matchup"].strip(), p["side"].strip())] = p
    return idx


def main():
    rows = read_rows(PICKS_CSV)
    errors = []

    if "--no-git" not in sys.argv:
        old = head_rows()
        if old is not None:
            now = {key(r): r for r in rows}
            for o in old:
                k = key(o)
                if k not in now:
                    errors.append(f"row deleted from ledger: {k}")
                    continue
                n = now[k]
                if o.get("result") in SETTLED:
                    for f in ("result", "risk", "profit"):
                        if (o.get(f) or "") != (n.get(f) or ""):
                            errors.append(f"settled row restated ({f}: {o.get(f)!r} -> {n.get(f)!r}): {k}")

    logs = log_index()
    for r in rows:
        k = key(r)
        res = r["result"]
        if res == VOID:
            if not r.get("void_reason"):
                errors.append(f"void row without void_reason: {k}")
            continue
        if res and res not in SETTLED:
            errors.append(f"unknown result {res!r}: {k}")
        reason = capture_check(r)
        if reason:
            errors.append(f"counted row fails capture rule ({reason}): {k}")
        lg = logs.get((r["date"], r["matchup"], r["side"]))
        if lg is not None and lg.get("risk") is not None and str(lg["risk"]) != str(int(float(r["risk"] or 0))):
            errors.append(f"stake {r['risk']} differs from capture record {lg['risk']}: {k}")
        if res in SETTLED:
            want = compute_profit(res, float(r["risk"] or 0), row_odds(r))
            if abs(float(r["profit"] or 0) - want) > 0.011:
                errors.append(f"profit {r['profit']} != {want} for {res} at stake {r['risk']}: {k}")

    if errors:
        for e in errors:
            print(f"::error::{e}")
        print(f"\nLedger check FAILED: {len(errors)} problem(s)")
        sys.exit(1)
    counted = [r for r in rows if r["result"] in SETTLED]
    print(f"Ledger check OK: {len(rows)} rows ({len(counted)} settled, "
          f"{sum(r['result'] == VOID for r in rows)} void, {sum(not r['result'] for r in rows)} pending)")


if __name__ == "__main__":
    main()

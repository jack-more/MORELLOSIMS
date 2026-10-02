#!/usr/bin/env python3
"""One-time ledger repair (2026-09-29): VECTOR-era MLB picks graded at the
price that was posted, and posted picks put back in the record.

Until 2026-09-29 build_mlb_sim.py rewrote every pending pick on every run
(odds, conf) and deleted pending picks the current gates no longer took.
Two consequences, both reconstructed here from git history of
picks/mlb.json (the only record of what was on the site at each run):

  1. `odds` held the last pre-game line, not the posted one, so every pick
     had closing_odds == odds and CLV was 0 by construction. Each VECTOR
     pick gets back the odds/conf it was first published with; the line it
     ended on is kept as `last_odds`.
  2. 22 VECTOR picks were published then deleted before first pitch. The 15
     that mlbsim/posted_cards.json shows were posted to Telegram as NEW PICK
     are restored as pending, so settle_mlb.py grades them with the same
     code as every other pick. The other 7 were only on the site between
     builds; they are restored too (owner decision 2026-09-29: keep them all in).

Idempotent: picks already carrying `published_at` are left alone.

  python3 scripts/restore_posted_mlb_picks.py [--dry-run]
  python3 scripts/settle_mlb.py            # grades the restored picks
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import picks_store  # noqa: E402  (seal mode: one door to pick data)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PICKS_JSON = os.path.join(REPO, "picks", "mlb.json")
VECTOR_START = "2026-07-16"


def git(*args):
    return subprocess.check_output(["git", "-C", REPO, *args], stderr=subprocess.DEVNULL)


def history(path, since="2026-07-15"):
    """(commit, commit_time_iso) oldest first."""
    out = git("log", "--reverse", "--format=%H %cI", f"--since={since}", "HEAD", "--", path).decode()
    return [line.split() for line in out.splitlines() if line.strip()]


def first_published():
    first = {}
    for sha, ts in history("picks/mlb.json"):
        try:
            data = json.loads(git("show", f"{sha}:picks/mlb.json"))
        except Exception:
            continue
        if picks_store.have_key():  # sealed history opens with the key
            data = [picks_store.open_pick(r) if picks_store.is_raw_sealed(r) else r for r in data]
        for p in data:
            if p.get("sport") == "mlb" and p.get("date", "") >= VECTOR_START and p["id"] not in first:
                first[p["id"]] = (p, sha, ts)
    return first


def telegram_receipts():
    ids = set()
    for sha, _ in history("mlbsim/posted_cards.json"):
        try:
            data = json.loads(git("show", f"{sha}:mlbsim/posted_cards.json"))
        except Exception:
            continue
        receipts = data.get("receipts") or []
        ids.update(receipts.keys() if isinstance(receipts, dict) else receipts)
    return ids


def payout(units, odds):
    ml = int(str(odds).replace("+", ""))
    return round(units * (ml / 100 if ml > 0 else 100 / abs(ml)), 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    picks = picks_store.load_picks(PICKS_JSON)
    by_id = {p["id"]: p for p in picks}
    first = first_published()
    posted = telegram_receipts()

    repriced = 0
    for pid, p in by_id.items():
        if pid not in first or p.get("published_at"):
            continue
        fp, sha, ts = first[pid]
        p["published_at"] = ts
        if str(fp.get("odds")) != str(p.get("odds")):
            p["last_odds"] = p.get("odds")
            p["odds"] = fp.get("odds")
            repriced += 1
        if fp.get("conf") is not None:
            p["conf"] = fp["conf"]
        if p.get("status") in ("win", "loss") and p.get("odds") not in (None, ""):
            p["pl"] = payout(p.get("units") or 50, p["odds"]) if p["status"] == "win" else -(p.get("units") or 50)
        # closing_odds (last snapshot line) is real and untouched: against the
        # posted odds it now yields actual closing-line value.

    restored, site_only = [], []
    for pid, (fp, sha, ts) in sorted(first.items()):
        if pid in by_id:
            continue
        was_posted = pid in posted
        if not was_posted:
            site_only.append(pid)
        p = dict(fp)
        p.update(status="pending", result=None, pl=None, settled_at=None,
                 published_at=ts, restored_from=sha[:8],
                 restored_reason=("posted to Telegram, later deleted by pre-game pruning" if was_posted
                                  else "published on the site, later deleted by pre-game pruning"))
        p.pop("closing_odds", None)
        by_id[pid] = p
        restored.append(pid)

    print(f"Repriced {repriced} VECTOR picks to their first-published odds")
    print(f"Restored {len(restored)} picks: {', '.join(restored)}")
    print(f"  of which site-only (never posted): {', '.join(site_only) or 'none'}")
    if args.dry_run:
        return
    merged = sorted(by_id.values(), key=lambda p: (p["date"], p["matchup"]), reverse=True)
    picks_store.save_picks(PICKS_JSON, merged)


if __name__ == "__main__":
    main()

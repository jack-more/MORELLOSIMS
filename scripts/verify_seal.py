#!/usr/bin/env python3
"""Verify a sealed-then-unsealed pick against the commitment published
before the game.

  python3 scripts/verify_seal.py 2026-10-21-mlb-NYY-BOS-ml
  python3 scripts/verify_seal.py <id> --history     # also find the commit
                                                     # that first published
                                                     # the commitment
  python3 scripts/verify_seal.py --all              # every unsealed pick

The check is self-contained — anyone can redo it by hand:

  payload = {k: pick[k] for k in pick["seal_keys"]}
  canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
  sha256(canonical + bytes.fromhex(pick["nonce"])).hexdigest() == pick["commitment"]

--history adds the proof of timing: the git commit that first contained the
commitment (while the pick was still sealed) and its time vs first pitch/tip.
Needs no key. Exit 0 = verified, 1 = mismatch / not found, 2 = still sealed.
"""

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import picks_store as store  # noqa: E402


def find(pick_id):
    for sport, path in store.PICK_FILES.items():
        for rec in store._read_raw(path):
            if pick_id in (rec.get("id"), rec.get("sealed_id")):
                return sport, path, rec
    return None, None, None


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=store.REPO)


def first_published(path, commitment):
    """Earliest commit whose version of `path` contains the commitment."""
    rel = os.path.relpath(path, store.REPO)
    out = git("log", "--reverse", "--format=%H %cI", f"-S{commitment}", "--", rel)
    lines = [ln for ln in out.stdout.splitlines() if ln.strip()]
    if not lines:
        return None
    sha, when = lines[0].split(" ", 1)
    sealed_then = None
    shown = git("show", f"{sha}:{rel}")
    if shown.returncode == 0:
        try:
            for rec in json.loads(shown.stdout):
                if rec.get("commitment") == commitment:
                    sealed_then = bool(rec.get("sealed")) and not any(k in rec for k in store.FORBIDDEN_SEALED)
                    break
        except json.JSONDecodeError:
            pass
    return sha, when, sealed_then


def verify_one(rec, path, history):
    pid = rec.get("id")
    if store.is_raw_sealed(rec):
        print(f"{pid}: still SEALED (commitment {rec.get('commitment')}, unlocks {rec.get('unlocks_at')})")
        return 2
    ok, msg = store.verify_record(rec)
    pick_txt = f"{rec.get('pick_text')} {rec.get('odds') or ''}".strip()
    print(f"{pid}: {'OK' if ok else 'FAIL'} — {msg}" + (f" · {pick_txt} · {rec.get('matchup')}" if ok else ""))
    if ok and history:
        found = first_published(path, rec["commitment"])
        if not found:
            print("  history: commitment not found in git history")
            return 1
        sha, when, sealed_then = found
        start = store.unlock_time(rec)
        before = store.parse_ts(when) < start
        print(f"  history: first published in {sha[:10]} at {when} "
              f"({'before' if before else 'AFTER'} start {store.iso(start)}; "
              f"{'sealed' if sealed_then else 'NOT sealed' if sealed_then is False else 'unknown'} in that commit)")
        if not before or sealed_then is False:
            return 1
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pick_id", nargs="?")
    ap.add_argument("--all", action="store_true", help="verify every unsealed pick in picks/*.json")
    ap.add_argument("--history", action="store_true", help="also prove the commitment predates the game")
    a = ap.parse_args()
    if a.all:
        worst = 0
        n = 0
        for sport, path in store.PICK_FILES.items():
            for rec in store._read_raw(path):
                if rec.get("commitment") and not store.is_raw_sealed(rec):
                    n += 1
                    worst = max(worst, verify_one(rec, path, a.history))
        print(f"{n} unsealed pick(s) checked")
        return 1 if worst == 1 else 0
    if not a.pick_id:
        ap.error("give a pick id or --all")
    sport, path, rec = find(a.pick_id)
    if rec is None:
        print(f"{a.pick_id}: not found in picks/mlb.json or picks/nba.json")
        return 1
    return verify_one(rec, path, a.history)


if __name__ == "__main__":
    raise SystemExit(main())

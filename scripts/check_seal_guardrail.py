#!/usr/bin/env python3
"""Seal-mode guardrail: run right before a pipeline commits.

When seal mode is on (ops/config/monetization.json), fails (exit 1) if any
file staged for commit (git diff --cached) exposes a sealed pick before its
game starts:

  1. structure — every pick-bearing data file is parsed and every pending,
     not-yet-started pick must be in sealed form with no side / odds / line /
     pick_text / model fields:
       picks/mlb.json, picks/nba.json, nba_pipeline/data/picks.csv,
       pick_log.json, daily_picks.json, mlbsim/picks_log.csv,
       reports/shadow_mlb.json, nba_pipeline/db/nba_sim.db (picks table)
  2. text — every other staged text file (index.html, mlbsim/, nbasim/,
     sim/, blog snippet, ...) is scanned for each sealed pick's plaintext
     fingerprints: pick_text next to its odds or confidence, side + odds,
     an NBA side + line ("MIN +11.0"), the MLB projection string. A hit only
     counts when the staged file has MORE occurrences than HEAD (so a past,
     settled pick with the same text is not a false alarm).

Errors name the file, the pick id and the kind of leak — never the side
(Actions logs are public). Seal mode off → prints a note and exits 0.

  python3 scripts/check_seal_guardrail.py            # staged changes
  python3 scripts/check_seal_guardrail.py --all      # every tracked file vs HEAD
"""

import argparse
import csv
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import picks_store as store  # noqa: E402

REPO = store.REPO
F_MLB = "picks/mlb.json"
F_NBA = "picks/nba.json"
F_CSV = "nba_pipeline/data/picks.csv"
F_LOG = "nba_pipeline/data/pick_log.json"
F_DAILY = "nba_pipeline/data/daily_picks.json"
F_MLB_LOG = "mlbsim/picks_log.csv"
F_SHADOW = "reports/shadow_mlb.json"
F_DB = "nba_pipeline/db/nba_sim.db"
STRUCTURED = {F_MLB, F_NBA, F_CSV, F_LOG, F_DAILY, F_MLB_LOG, F_SHADOW, F_DB}
LOG_FORBIDDEN = ("side", "line_value", "direction", "confidence", "sim_spread", "spread_edge",
                 "sim_total", "raw_edge", "conf_label", "ml_odds", "pick_text", "ou_pick_text",
                 "ou_conf", "ou_edge", "pick_team", "run_diff", "model_prob", "model_prob_raw",
                 "odds", "price_edge", "gates")
TEXT_EXT = (".html", ".htm", ".json", ".csv", ".md", ".txt", ".js", ".xml", ".svg", ".css", ".yml", ".yaml")


def git(*args, binary=False):
    r = subprocess.run(["git", *args], capture_output=True, cwd=REPO)
    if r.returncode != 0:
        return None
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def staged_files():
    out = git("diff", "--cached", "--name-only", "--diff-filter=ACMR") or ""
    return [p for p in out.splitlines() if p.strip()]


def staged_blob(path, binary=False):
    return git("show", f":{path}", binary=binary)


def head_blob(path, binary=False):
    return git("show", f"HEAD:{path}", binary=binary)


def current(path, staged):
    """Staged version if staged, else the working copy."""
    if path in staged:
        return staged_blob(path)
    try:
        with open(os.path.join(REPO, path)) as f:
            return f.read()
    except FileNotFoundError:
        return None


class Check:
    def __init__(self):
        self.errors = []
        self.secrets = []  # plaintext pick facts of everything sealed right now

    def err(self, path, msg):
        self.errors.append(f"{path}: {msg}")

    # ── secrets (plaintext of sealed records, needs the key) ──
    def add_secret(self, sport, ref, date, matchup, side, pick_text, odds, conf, projection=None):
        if not side and not pick_text:
            return
        self.secrets.append({
            "sport": sport, "ref": ref, "date": date, "matchup": matchup, "side": side or "",
            "pick_text": pick_text or "", "odds": _signed(odds), "conf": str(conf or ""),
            "projection": projection or "",
        })


def _signed(odds):
    if odds in (None, ""):
        return ""
    s = str(odds).strip()
    try:
        v = int(float(s.replace("+", "")))
    except ValueError:
        return s
    return f"{v:+d}"


def _load_json(text):
    try:
        return json.loads(text) if text else None
    except json.JSONDecodeError:
        return None


# ── 1. structure ──────────────────────────────────────────────────────────

def check_pick_file(c, path, text, sport, staged):
    data = _load_json(text)
    if not isinstance(data, list):
        return
    for rec in data:
        if not isinstance(rec, dict):
            continue
        pid = rec.get("id")
        if store.is_raw_sealed(rec):
            bad = [k for k in store.FORBIDDEN_SEALED if k in rec]
            if bad:
                c.err(path, f"sealed pick {pid} carries plaintext field(s) {bad}")
            if store.have_key():
                try:
                    p = store.decrypt(rec["sealed_blob"])["pick"]
                except store.SealError as e:
                    c.err(path, f"sealed pick {pid}: {e}")
                    continue
                if not store.has_started(rec):
                    c.add_secret(sport, pid, p.get("date"), p.get("matchup"), p.get("side"),
                                 p.get("pick_text"), p.get("odds"), p.get("conf"),
                                 p.get("sim_projection") if sport == "mlb" else None)
        elif rec.get("status") == "pending" and store.before_start(rec) and path in staged:
            c.err(path, f"pending pick {pid} is in plaintext before its game starts")


def check_csv(c, path, text, side_col, staged):
    if not text:
        return
    reader = csv.DictReader(io.StringIO(text))
    for i, row in enumerate(reader, 2):
        started = store.has_started(row)
        if row.get(store.BLOB_COL):
            if (row.get(side_col) or "") != store.SEALED_SIDE:
                c.err(path, f"line {i}: sealed row shows a {side_col!r} value")
            if (row.get("odds") or "").strip():
                c.err(path, f"line {i}: sealed row shows odds")
            if store.have_key() and not started:
                p = store.decrypt(row[store.BLOB_COL])["row"]
                sport = "nba" if side_col == "side" else "mlb"
                side = p.get(side_col) or ""
                pick_text = side if sport == "nba" else (f"{side} ML" if side else "")
                odds = p.get("odds") if sport == "nba" else (
                    p.get("away_ml") if side == p.get("away") else p.get("home_ml"))
                c.add_secret(sport, f"{path}:{i}", p.get("date"), p.get("matchup") or
                             f"{p.get('away')} @ {p.get('home')}", side.split()[0] if side else "",
                             pick_text, odds if sport == "mlb" or (p.get("type") == "ml") else "",
                             p.get("conf"))
        elif not (row.get("result") or "").strip() and store.before_start(row) and path in staged:
            c.err(path, f"line {i}: pending row is in plaintext before its game starts")


def check_entries(c, path, entries, keep_label, staged, must_seal):
    for i, e in enumerate(entries or []):
        if not isinstance(e, dict):
            continue
        if store.is_raw_sealed(e):
            bad = [k for k in LOG_FORBIDDEN if k in e]
            if bad:
                c.err(path, f"sealed {keep_label} #{i} carries plaintext field(s) {bad}")
            if store.have_key() and not store.has_started(e):
                p = store.decrypt(e["sealed_blob"])["rec"]
                side = p.get("side") or p.get("pick_text") or p.get("pick_team") or ""
                pick_text = p.get("side") or p.get("pick_text") or (f"{side} ML" if side else "")
                c.add_secret("nba" if "nba" in path else "mlb", f"{path}#{i}",
                             p.get("slate_date") or p.get("date") or (p.get("tip_at") or "")[:10], p.get("matchup") or
                             f"{p.get('away')} @ {p.get('home')}", side.split()[0] if side else "",
                             pick_text, p.get("ml_odds") or p.get("odds"), p.get("conf_1_10") or p.get("conf"))
        elif must_seal(e) and store.before_start(e) and path in staged:
            c.err(path, f"{keep_label} #{i} ({e.get('matchup') or e.get('game_pk')}) is in plaintext before its game starts")


def check_db(c, staged):
    blob = staged_blob(F_DB, binary=True)
    if not blob:
        return
    nba_sealed = {(s["date"], s["matchup"]) for s in c.secrets if s["sport"] == "nba"}
    if not nba_sealed:
        return
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        tmp.write(blob)
        tmp.flush()
        try:
            con = sqlite3.connect(tmp.name)
            rows = con.execute("SELECT slate_date, matchup FROM picks").fetchall()
            con.close()
        except sqlite3.Error as e:
            print(f"  WARN guardrail: could not read staged {F_DB}: {e}")
            return
    for d, m in rows:
        if (str(d)[:10], m) in nba_sealed:
            c.err(F_DB, f"picks table holds a sealed pick ({d} {m}) before tip")


# ── 2. text fingerprints ──────────────────────────────────────────────────

def fingerprints(s):
    out = []
    pt, side, odds, conf = s["pick_text"], s["side"], s["odds"], s["conf"]
    gap = r"[\s\S]{0,200}?"
    if s["projection"] and len(s["projection"]) >= 9:
        out.append(("model projection", re.escape(s["projection"])))
    if pt and conf:
        out.append(("pick + confidence", re.escape(pt) + gap + r"C:?\s*" + re.escape(conf) + r"(?!\d)"))
    if pt and odds:
        out.append(("pick + odds", re.escape(pt) + gap + re.escape(odds) + r"(?!\d)"))
    if side and odds and s["sport"] == "mlb":
        out.append(("side + odds", r"(?<![A-Z])" + re.escape(side) + r"(?:\s+ML)?\s*\(?" + re.escape(odds) + r"(?!\d)"))
    if s["sport"] == "nba" and re.search(r"[+-]\d+(\.\d)?$", pt or ""):
        out.append(("side + line", r"(?<![A-Z])" + re.escape(pt) + r"(?![\d.])"))
    return out


def scan_text(c, files):
    if not c.secrets:
        return
    for path in files:
        if path in STRUCTURED or not path.lower().endswith(TEXT_EXT):
            continue
        new = staged_blob(path)
        if new is None:
            continue
        old = head_blob(path) or ""
        for s in c.secrets:
            for kind, rx in fingerprints(s):
                n_new = len(re.findall(rx, new))
                if n_new and n_new > len(re.findall(rx, old)):
                    c.err(path, f"exposes sealed pick {s['ref']} ({s['matchup']}, {s['date']}): {kind}")
                    break


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="treat every tracked file as staged")
    a = ap.parse_args()
    if not store.seal_mode():
        print("seal guardrail: seal mode is off — nothing to check")
        return 0
    staged = set(staged_files())
    if a.all:
        staged |= set((git("ls-files") or "").splitlines())
    c = Check()
    if not store.have_key():
        print(f"::warning::seal guardrail: {store.KEY_ENV} not set — structural checks only")

    check_pick_file(c, F_MLB, current(F_MLB, staged), "mlb", staged)
    check_pick_file(c, F_NBA, current(F_NBA, staged), "nba", staged)
    check_csv(c, F_CSV, current(F_CSV, staged), "side", staged)
    check_csv(c, F_MLB_LOG, current(F_MLB_LOG, staged), "pick", staged)

    log = _load_json(current(F_LOG, staged))
    check_entries(c, F_LOG, log if isinstance(log, list) else [], "pick_log entry", staged, lambda e: True)

    nba_pending = {(s["date"], s["matchup"]) for s in c.secrets if s["sport"] == "nba"}
    daily = _load_json(current(F_DAILY, staged)) or {}
    slate = daily.get("slate_date_iso") or ""
    check_entries(c, F_DAILY, daily.get("games") or [], "daily_picks game", staged,
                  lambda g: (slate, g.get("matchup")) in nba_pending)

    mlb_pending = {(s["date"], s["matchup"]) for s in c.secrets if s["sport"] == "mlb"}
    shadow = _load_json(current(F_SHADOW, staged)) or {}
    check_entries(c, F_SHADOW, list((shadow.get("rows") or {}).values()), "shadow row", staged,
                  lambda r: (r.get("date"), f"{r.get('away')} @ {r.get('home')}") in mlb_pending)

    if F_DB in staged:
        check_db(c, staged)
    scan_text(c, sorted(staged))

    if c.errors:
        for e in c.errors:
            print(f"::error::SEAL LEAK {e}")
        print(f"\nseal guardrail FAILED: {len(c.errors)} problem(s) — nothing was committed")
        return 1
    print(f"seal guardrail OK: {len(staged)} staged file(s), {len(c.secrets)} sealed record(s) checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

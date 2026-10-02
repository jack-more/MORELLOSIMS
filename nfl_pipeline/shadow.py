#!/usr/bin/env python3
"""NFL shadow ledger — every game projected and logged before kickoff, settled
after. Nothing here publishes or messages anyone.

reports/shadow_nfl.json:
  {"_about": ..., "model": {...frozen config...},
   "rows": {game_id: {
       game, kickoff_utc, teams, venue, neutral,
       "first": capture,   # first pre-kickoff capture (never rewritten)
       "last":  capture,   # latest pre-kickoff capture (rewritten only before kickoff)
       "n_captures": int,
       "status": "open" | "locked" | "final" | "missed",
       "result": {...}     # after the game: score, closing line, ATS, CLV
   }}}
  capture = {captured_at, line_home_fav, line_source, pred_home_margin, edge,
             side, side_line, qb_home, qb_away, components...}

Ledger rules (scripts/check_shadow_nfl.py enforces them against git HEAD):
  * a row is never deleted; `first` never changes once written;
  * every capture's captured_at is before kickoff; after kickoff the row is
    locked and only `status` / `result` may be filled in;
  * a game that kicked off with no capture is recorded as "missed" — never
    backfilled with a projection;
  * settled results never change.

  python3 nfl_pipeline/shadow.py run        # settle finished games, capture upcoming
  python3 nfl_pipeline/shadow.py settle
  python3 nfl_pipeline/shadow.py capture [--horizon-days 8]
  python3 nfl_pipeline/shadow.py report
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (  # noqa: E402
    CURRENT_SEASON, PKG, REPO, SCHEDULES_CSV, SHADOW_LEDGER,
)
import model as M  # noqa: E402

sys.path.insert(0, os.path.join(REPO, "scripts"))
import picks_store  # noqa: E402  (seal mode + clock override for tests)

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
MODEL_PARAMS_JSON = os.path.join(PKG, "model_params.json")
ABOUT = ("NFL shadow ledger: every game projected and logged before kickoff (captured_at < kickoff), "
         "settled after. Shadow only — nothing here is a published pick. Spreads are home-favored-by "
         "(nflverse convention). Rows are never deleted; first captures never change.")
SEAL_KEEP = ("game_id", "season", "week", "game_type", "kickoff_utc", "away", "home", "status", "n_captures",
             "published", "venue", "neutral")


def now_utc():
    return picks_store.now_utc()


def iso(dt):
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(ts):
    return picks_store.parse_ts(ts)


# ── ledger io ──

def load_ledger(path=SHADOW_LEDGER):
    """Ledger dict; sealed rows are opened when PICKS_SEAL_KEY is present."""
    try:
        with open(path) as f:
            d = json.load(f)
    except FileNotFoundError:
        d = {}
    d.setdefault("_about", ABOUT)
    d.setdefault("rows", {})
    # seal mode: published pending rows may be sealed — open them when we can
    d["rows"] = {k: picks_store.open_record(v) for k, v in d["rows"].items()}
    return d


def pick_id(row):
    """Public pick id for a game: ET date of kickoff + both teams. Never the side."""
    d = parse(row["kickoff_utc"]).astimezone(ET).strftime("%Y-%m-%d")
    return f"{d}-nfl-{row['away']}-{row['home']}-spread".lower()


def save_ledger(d, path=SHADOW_LEDGER, published_pending=()):
    """Write the ledger. Under seal mode, open rows whose pick is published
    and pending are sealed (picks_store.seal_record) until kickoff."""
    rows = {}
    for k in sorted(d["rows"], key=lambda g: (d["rows"][g].get("kickoff_utc") or "", g)):
        r = d["rows"][k]
        if (picks_store.seal_mode() and not picks_store.is_raw_sealed(r) and r.get("status") == "open"
                and r.get("kickoff_utc") and pick_id(r) in published_pending):
            r = picks_store.seal_record({**r, "starts_at_utc": r["kickoff_utc"]}, SEAL_KEEP,
                                        unlock=parse(r["kickoff_utc"]), kind="nfl_shadow")
        rows[k] = r
    out = {"_about": d.get("_about", ABOUT), "model": d.get("model", {}), "rows": rows}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
        f.write("\n")


# ── model ──

def load_model():
    with open(MODEL_PARAMS_JSON) as f:
        cfg = json.load(f)
    p = M.Params(**cfg["params"])
    cal = M.Calibration.from_dict(cfg["calibration"])
    return cfg, p, cal


def kickoff_utc(g, espn_row=None):
    """ESPN's event time when available, else nflverse gameday + gametime (ET)."""
    if espn_row and espn_row.get("kickoff_utc"):
        ko = parse(espn_row["kickoff_utc"])
        if ko:
            return ko.astimezone(UTC)
    gt = g.get("gametime")
    gt = "13:00" if gt is None or (isinstance(gt, float) and math.isnan(gt)) else str(gt)
    day = pd.Timestamp(g["gameday"]).strftime("%Y-%m-%d")
    return datetime.strptime(f"{day} {gt}", "%Y-%m-%d %H:%M").replace(tzinfo=ET).astimezone(UTC)


def qb_override(g, side, injuries, depth):
    """Schedule starter unless the latest injury report has him Out/Doubtful;
    then the highest depth-chart QB who is not. Returns (qb_id, source)."""
    qb = g.get(f"{side}_qb_id")
    team = g[f"{side}_team"]
    if injuries is None or pd.isna(qb):
        return (None if pd.isna(qb) else qb), "nflverse schedule"
    inj = injuries[(injuries["team"] == team) & (injuries["week"] == injuries[injuries["team"] == team]["week"].max())]
    out = set(inj[inj["report_status"].isin(["Out", "Doubtful"])]["gsis_id"].dropna())
    if qb not in out:
        return qb, "nflverse schedule"
    if depth is not None and len(depth):
        d = depth[(depth["team"] == team) & (depth["pos_abb"] == "QB")]
        if len(d):
            d = d[d["dt"] == d["dt"].max()].sort_values("pos_rank")
            for _, r in d.iterrows():
                if r["gsis_id"] not in out and pd.notna(r["gsis_id"]):
                    return r["gsis_id"], f"depth chart (schedule QB {qb} listed out)"
    return qb, "nflverse schedule (listed out, no depth-chart alternative)"


def load_injuries_depth(season):
    try:
        import sources
        inj = pd.read_parquet(sources.injuries_path(season, refresh=True))
        dep = pd.read_parquet(sources.depth_path(season, refresh=True))
        return inj, dep
    except Exception as e:
        print(f"  WARN injuries/depth unavailable ({e}); using schedule starters")
        return None, None


def side_text(team, line_home_fav, is_home):
    """Bettor's line for `team` given a home-favored-by line."""
    line = -line_home_fav if is_home else line_home_fav
    return team, round(line, 1)


def make_capture(data, p, cal, g, line, line_source, qb_home, qb_away, qb_src, now):
    gg = dict(g)
    gg["home_qb_id"], gg["away_qb_id"] = qb_home, qb_away
    r = M.ratings_at(data, pd.Timestamp(g["gameday"]), int(g["season"]), p)
    comp = M.components(data, r, gg)
    pred = float(cal.predict(comp))
    cap = {
        "captured_at": iso(now),
        "line_home_fav": None if line is None else float(line),
        "line_source": line_source,
        "pred_home_margin": round(pred, 2),
        "qb_home": qb_home, "qb_home_name": r.qb_name.get(qb_home), "qb_away": qb_away,
        "qb_away_name": r.qb_name.get(qb_away), "qb_source": qb_src,
        "components": {k: round(v, 3) for k, v in comp.items()},
        "ratings_through": str((data.tg_before(pd.Timestamp(g["gameday"]))["gameday"].max()).date()),
    }
    if line is not None:
        edge = pred - float(line)
        side_home = edge > 0
        team = g["home_team"] if side_home else g["away_team"]
        _, side_line = side_text(team, float(line), side_home)
        cap.update({"edge": round(edge, 2), "side": team, "side_line": side_line,
                    "side_margin": round(pred if side_home else -pred, 2)})
    return cap


def capture(ledger, horizon_days=8, espn_board=None, injuries=None, depth=None, now=None, data=None):
    now = now or now_utc()
    cfg, p, cal = load_model()
    data = data or M.Data()
    sched = data.sched
    ledger["model"] = {"params_key": cfg["params_key"], "feature_set": cfg.get("feature_set"),
                       "calibration_seasons": cfg["calibration"]["seasons"], "frozen_at": cfg["frozen_at"]}
    upcoming = sched[(sched["result"].isna()) & (sched["gameday"] >= pd.Timestamp(now.astimezone(ET).date()) - pd.Timedelta(days=1))
                     & (sched["gameday"] <= pd.Timestamp((now + timedelta(days=horizon_days)).astimezone(ET).date()))]
    board = espn_board if espn_board is not None else fetch_board(upcoming)
    by_espn = {str(b["espn"]): b for b in board}
    n_new = n_upd = n_skip = 0
    for _, g in upcoming.iterrows():
        gid = g["game_id"]
        e = by_espn.get(str(int(g["espn"]))) if pd.notna(g.get("espn")) else None
        ko = kickoff_utc(g, e)
        row = ledger["rows"].get(gid)
        if now >= ko:
            n_skip += 1
            continue                          # kicked off: locked, settle() handles it
        if row and row.get("status") not in (None, "open"):
            continue
        if e and e.get("spread_home_fav") is not None:
            line, src = e["spread_home_fav"], f"ESPN scoreboard ({e.get('provider') or 'consensus'})"
        elif pd.notna(g.get("spread_line")):
            line, src = float(g["spread_line"]), "nflverse schedule"
        else:
            line, src = None, "none"
        qh, sh = qb_override(g, "home", injuries, depth)
        qa, sa = qb_override(g, "away", injuries, depth)
        cap = make_capture(data, p, cal, g, line, src, qh, qa, {"home": sh, "away": sa}, now)
        if row is None:
            row = {
                "game_id": gid, "season": int(g["season"]), "week": int(g["week"]), "game_type": g["game_type"],
                "espn": None if pd.isna(g.get("espn")) else str(int(g["espn"])),
                "kickoff_utc": iso(ko), "away": g["away_team"], "home": g["home_team"],
                "neutral": str(g.get("location")) == "Neutral",
                "venue": (e or {}).get("venue") or g.get("stadium"),
                "first": cap, "last": cap, "n_captures": 1, "status": "open", "published": False,
                "stake_units": 1.0,
            }
            ledger["rows"][gid] = row
            n_new += 1
        else:
            row["kickoff_utc"] = iso(ko)
            row["last"] = cap
            row["n_captures"] = int(row.get("n_captures") or 1) + 1
            if row["first"].get("line_home_fav") is None and line is not None:
                pass  # first capture stays as written (no line then); the last capture has one
            n_upd += 1
    print(f"capture: {n_new} new, {n_upd} updated, {n_skip} already kicked off (horizon {horizon_days}d)")
    return ledger


def fetch_board(upcoming):
    import espn
    out = []
    for day in sorted({pd.Timestamp(d).strftime("%Y%m%d") for d in upcoming["gameday"]}):
        try:
            out += espn.week_board(day)
        except Exception as e:
            print(f"  WARN ESPN scoreboard {day}: {e} (falling back to nflverse lines)")
    return out


# ── settle ──

def ats(side_home, margin, line):
    """W/L/P for a home-favored-by `line` with the model on the home side if side_home."""
    d = margin - line
    if d == 0:
        return "P"
    return "W" if (d > 0) == side_home else "L"


def settle(ledger, now=None, espn_close=None, sched=None):
    now = now or now_utc()
    sched = pd.read_csv(SCHEDULES_CSV) if sched is None else sched.copy()
    sched = sched.set_index("game_id")
    n_lock = n_final = n_missed = 0
    # games that kicked off without any capture: record as missed (never backfilled)
    logged_seasons = {r.get("season") for r in ledger["rows"].values()} or {CURRENT_SEASON}
    season_games = sched[sched["season"].isin(logged_seasons)]
    first_logged = min((parse(r["kickoff_utc"]) for r in ledger["rows"].values() if r.get("kickoff_utc")), default=None)
    for gid, g in season_games.iterrows():
        if gid in ledger["rows"] or first_logged is None:
            continue
        ko = kickoff_utc(g.to_dict() | {"gameday": g["gameday"]})
        if first_logged <= ko <= now:
            ledger["rows"][gid] = {"game_id": gid, "season": int(g["season"]), "week": int(g["week"]),
                                   "game_type": g["game_type"], "kickoff_utc": iso(ko), "away": g["away_team"],
                                   "home": g["home_team"], "status": "missed", "published": False,
                                   "note": "kicked off with no pre-game capture; not backfilled"}
            n_missed += 1
    for gid, row in ledger["rows"].items():
        if row.get("status") in ("final", "missed") or picks_store.is_raw_sealed(row):
            continue
        ko = parse(row["kickoff_utc"])
        if now < ko:
            continue
        if row.get("status") == "open":
            row["status"] = "locked"
            n_lock += 1
        if gid not in sched.index or pd.isna(sched.loc[gid, "result"]):
            continue
        g = sched.loc[gid]
        margin = float(g["result"])
        close = None if pd.isna(g["spread_line"]) else float(g["spread_line"])
        res = {"home_score": int(g["home_score"]), "away_score": int(g["away_score"]), "home_margin": margin,
               "closing_line_home_fav": close, "closing_source": "nflverse spread_line (final pre-game)",
               "settled_at": iso(now)}
        if espn_close and gid in espn_close:
            res["espn_close_home_fav"] = espn_close[gid]
        for k in ("first", "last"):
            c = row.get(k) or {}
            if c.get("edge") is None:
                continue
            side_home = c["edge"] > 0
            res[f"ats_{k}_line"] = ats(side_home, margin, c["line_home_fav"])
            if close is not None:
                res[f"ats_{k}_side_at_close"] = ats(side_home, margin, close)
                # CLV in points for the side taken at that capture's line
                res[f"clv_{k}_pts"] = round((close - c["line_home_fav"]) * (1 if side_home else -1), 2)
        row["result"] = res
        row["status"] = "final"
        n_final += 1
    print(f"settle: {n_final} settled, {n_lock} locked at kickoff, {n_missed} missed")
    return ledger


def espn_close_map():
    from config import ESPN_LINES_CSV
    if not os.path.exists(ESPN_LINES_CSV):
        return {}
    l = pd.read_csv(ESPN_LINES_CSV).dropna(subset=["close_home_fav"])
    return dict(zip(l["game_id"], l["close_home_fav"].astype(float)))


# ── report ──

def report(ledger):
    rows = [r for r in ledger["rows"].values() if not picks_store.is_raw_sealed(r)]
    fin = [r for r in rows if r.get("status") == "final"]
    print(f"SHADOW NFL — {len(rows)} rows: {sum(r['status'] == 'open' for r in rows)} open, "
          f"{sum(r['status'] == 'locked' for r in rows)} locked, {len(fin)} final, "
          f"{sum(r['status'] == 'missed' for r in rows)} missed")
    for k in ("first", "last"):
        for th in (0, 2, 3):
            sub = [r for r in fin if r.get(k, {}).get("edge") is not None and abs(r[k]["edge"]) >= th]
            res = [r["result"].get(f"ats_{k}_line") for r in sub]
            w, l, p = res.count("W"), res.count("L"), res.count("P")
            clv = [r["result"].get(f"clv_{k}_pts") for r in sub if r["result"].get(f"clv_{k}_pts") is not None]
            print(f"  {k:5} capture |edge|>={th}: {w}-{l}-{p} ATS at captured line"
                  + (f", CLV mean {np.mean(clv):+.2f} pts, beat close {sum(c > 0 for c in clv)}/{len(clv)}" if clv else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "capture", "settle", "report"])
    ap.add_argument("--horizon-days", type=int, default=8)
    ap.add_argument("--no-injuries", action="store_true")
    a = ap.parse_args()
    ledger = load_ledger()
    if a.cmd in ("run", "settle"):
        ledger = settle(ledger, espn_close=espn_close_map())
    if a.cmd in ("run", "capture"):
        inj, dep = (None, None) if a.no_injuries else load_injuries_depth(CURRENT_SEASON)
        ledger = capture(ledger, a.horizon_days, injuries=inj, depth=dep)
    if a.cmd != "report":
        pub = set()
        try:
            from publish import published_pending_ids
            pub = published_pending_ids()
        except Exception:
            pass
        save_ledger(ledger, published_pending=pub)
    report(ledger)


if __name__ == "__main__":
    main()

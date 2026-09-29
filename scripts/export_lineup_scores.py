#!/usr/bin/env python3
"""Per-hitter model scores for one published MLB pick, written per game.

  python3 scripts/export_lineup_scores.py --pick-id 2026-09-26-mlb-TB-PHI-ml

Writes mlbsim/lineup_scores/{date}_{gamePk}.json. Read-only with respect to the
model: nothing here feeds back into build_mlb_sim.py.

Two per-hitter layers produce the published run projection, and they are
persisted differently:

1. Archetype layer (build_mlb_sim.process_lineup) -- STORED.
   Every pipeline run commits the per-batter output: mlbsim/index.html (lineup
   rows: archetype PA, +R, MOMO, MOMI, base wOBA, ARCH wOBA) and
   mlbsim/hr_lotto_audit.json (id-keyed: momo, run_contrib, hr_rate, h2h...).
   We read both from the last pipeline commit before first pitch, i.e. the
   board the pick was made from. MOMO (mlb_momo.matchup_swing_to_momo of base
   wOBA and ARCH wOBA) is the model's per-hitter matchup score; it is
   re-derived here from the two stored (3-place) wOBAs as a check (+-1).

2. Vector layer (mlb_vector_live_gate.apply_live_vector_projection) -- NOT
   stored per hitter. The pipeline keeps only the team means
   ({side}_vector_xwoba, vector_edge). We recompute the per-hitter rows with
   the same functions and the same 45-day Statcast window, then check that
   their means reproduce the stored team numbers. Statcast xwOBA is revised
   after the fact, so a re-pull can drift slightly; the check is recorded.
"""

from __future__ import annotations

import argparse
import html as htmllib
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR / "video"))

from mlb_momo import matchup_swing_to_momo  # noqa: E402

OUT_DIR = REPO / "mlbsim" / "lineup_scores"
PICKS = REPO / "picks" / "mlb.json"
LINEUP_DIR = REPO / "data" / "reference" / "mlb_lineups"
AUDIT = "mlbsim/hr_lotto_audit.json"
PAGE = "mlbsim/index.html"
VECTOR_CHECK_TOL = 0.0005        # xwOBA; team-mean drift tolerated from Statcast revisions


def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", s)
    return re.sub(r"[^a-z]", "", s)


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True)


def load_pick(pick_id: str) -> dict:
    picks = json.load(open(PICKS))
    picks = picks if isinstance(picks, list) else picks.get("picks", [])
    p = next((x for x in picks if isinstance(x, dict) and x.get("id") == pick_id), None)
    if not p:
        raise SystemExit(f"pick id not found in {PICKS}: {pick_id}")
    return p


def first_pitch_utc(pick: dict) -> datetime:
    t = (pick.get("game_time") or "").replace(" ET", "").strip()
    if not t:
        raise SystemExit(f"{pick['id']}: no game_time stored; cannot find the pre-game board")
    local = datetime.strptime(f"{pick['date']} {t}", "%Y-%m-%d %I:%M %p").replace(tzinfo=ZoneInfo("America/New_York"))
    return local.astimezone(ZoneInfo("UTC"))


def pregame_commit(pick: dict) -> tuple[str, str]:
    """Last commit touching the audit file before first pitch on the pick's date."""
    start = first_pitch_utc(pick)
    since = (start - timedelta(hours=20)).isoformat()
    rows = git("log", f"--since={since}", f"--until={start.isoformat()}", "--format=%H %cI", "--", AUDIT).split("\n")
    rows = [r.split() for r in rows if r.strip()]
    if not rows:
        raise SystemExit(f"no pipeline commit touching {AUDIT} before first pitch {start.isoformat()}")
    sha, when = rows[0]
    return sha, when


# ── archetype layer (stored) ────────────────────────────────────────────────

ROW_RE = re.compile(
    r'<span class="batter-order">(\d+)</span>\s*<span class="batter-name">(.*?)</span>.*?'
    r'<span class="batter-stats">(.*?)</span>\s*<span class="batter-pa">(\d+)PA</span>\s*'
    r'<span class="batter-range">\+([\d.]+) R</span>.*?'
    r'<span>MOMO</span>(\d+)</span>.*?<span>MOMI</span>(\d+)</span>.*?'
    r'<span>WOBA</span>(\.\d+|[01]\.\d+)</span>.*?<span>ARCH</span>(\.\d+|[01]\.\d+)</span>',
    re.S,
)


def page_lineups(page: str, away: str, home: str, away_sp: str, home_sp: str) -> dict:
    """Lineup rows for this game from the published mlbsim page."""
    cards = page.split('<div class="game-card"')
    hits = []
    for c in cards[1:]:
        abbrs = re.findall(r'<div class="team-abbr">(\w+)</div>', c[:4000])
        sps = [htmllib.unescape(x) for x in re.findall(r'<div class="sp-name">(.*?)</div>', c[:8000])]
        if abbrs[:2] == [away, home] and sps[:2] == [away_sp, home_sp]:
            hits.append(c)
    if len(hits) != 1:
        raise SystemExit(f"expected one {away}@{home} card ({away_sp} v {home_sp}) on the page, found {len(hits)}")
    card = hits[0]
    out = {}
    for abbr in (away, home):
        m = re.search(rf'<div class="lineup-col-hdr">{abbr} LINEUP</div>(.*?)(?=<div class="lineup-col-hdr">|$)', card, re.S)
        if not m:
            raise SystemExit(f"{abbr} lineup column not on the page")
        rows = []
        for r in ROW_RE.findall(m.group(1)):
            rows.append({
                "order": int(r[0]), "name": htmllib.unescape(r[1]), "pos": htmllib.unescape(r[2]),
                "arch_pa": int(r[3]), "run_contrib": float(r[4]), "momo": int(r[5]), "momi": int(r[6]),
                "base_woba": float(r[7]), "arch_woba": float(r[8]),
            })
        out[abbr] = rows
    return out


# ── vector layer (recomputed) ───────────────────────────────────────────────

def vector_rows(pick: dict, lu: dict) -> dict:
    import pandas as pd
    from mlb_vector_features import (aggregate_hitter_inverse_vectors, aggregate_pitcher_vectors,
                                     prepare_statcast_frame, score_lineup_matchup)
    from mlb_vector_live_gate import DEFAULT_LOOKBACK_DAYS, _date_range, _load_statcast

    today = pick["date"]
    raw = _load_statcast(today, DEFAULT_LOOKBACK_DAYS, REPO / "atlas")   # same window + cache as the live gate
    prep = prepare_statcast_frame(raw).dropna(subset=["pitcher", "batter"])
    t = pd.to_datetime(today)
    hist = prep[(prep["game_date"] < t) & (prep["game_date"] >= t - timedelta(days=DEFAULT_LOOKBACK_DAYS))]
    ids = {s: [b["id"] for b in lu[s]["lineup"]] for s in ("away", "home")}
    sps = {s: lu[s]["sp"]["id"] for s in ("away", "home")}
    as_of = str((t - timedelta(days=1)).date())
    # vectors are per entity, so building them on this game's subset equals the slate-wide build
    pv = aggregate_pitcher_vectors(hist[hist["pitcher"].isin(set(sps.values()))], as_of=as_of)
    hv = aggregate_hitter_inverse_vectors(hist[hist["batter"].isin(set(ids["away"] + ids["home"]))], as_of=as_of)
    scores = {
        "away": score_lineup_matchup(sps["home"], ids["away"], pv, hv),
        "home": score_lineup_matchup(sps["away"], ids["home"], pv, hv),
    }
    check = {}
    for s in ("away", "home"):
        stored = pick.get(f"{s}_vector_xwoba")
        got = scores[s]["avg_projected_xwoba"]
        check[f"{s}_vector_xwoba"] = {"stored": stored, "recomputed": got,
                                      "diff": None if stored is None else round(got - float(stored), 5)}
    edge = scores[pick_side(pick)]["avg_matchup_delta"] - scores[opp_side(pick)]["avg_matchup_delta"]
    check["vector_edge"] = {"stored": pick.get("vector_edge"), "recomputed": round(edge, 5)}
    ok = all(v.get("diff") is None or abs(v["diff"]) <= VECTOR_CHECK_TOL for k, v in check.items() if "diff" in v)
    start, end = _date_range(today, DEFAULT_LOOKBACK_DAYS)
    rows = {}
    for s in ("away", "home"):
        for r in scores[s]["hitter_scores"]:
            h = hv[str(r["batter"])]
            rows[int(r["batter"])] = {
                "baseline_xwoba": r["baseline_xwoba"], "matchup_delta": r["matchup_delta"],
                "projected_xwoba": r["projected_xwoba"], "components": r["components"], "weights": r["weights"],
                "sample_pa": h["sample"]["pa"],
            }
    starters = {}
    for s in ("away", "home"):
        p = pv.get(str(sps[s]))
        if p:
            starters[s] = {k: p.get(k) for k in ("p_throws", "sample", "pitch_mix", "velocity_band_mix",
                                                 "movement_band_mix", "location_mix")}
    return {
        "meta": {"statcast_window": [start, end], "statcast_pulled": datetime.now().date().isoformat(),
                 "lookback_days": DEFAULT_LOOKBACK_DAYS, "check": check, "check_ok": ok,
                 "tolerance": VECTOR_CHECK_TOL,
                 "missing": {s: scores[s]["missing_hitters"] for s in ("away", "home")}},
        "rows": rows, "starters": starters,
    }


def pick_side(p):
    return "away" if p["side"] == p["away"] else "home"


def opp_side(p):
    return "home" if pick_side(p) == "away" else "away"


# ── colour scale (shared by the card back and the lineup page) ─────────────

# best -> worst. Light green, yellow, orange, red; all light enough to carry
# dark ink, which is how they are used (highlighter chips on the blue card).
RAMP = [(1.0, (126, 245, 160)), (0.66, (255, 228, 94)), (0.33, (255, 154, 60)), (0.0, (255, 84, 72))]
INK = (10, 22, 72)


def ramp(t: float) -> tuple[int, int, int]:
    t = min(max(t, 0.0), 1.0)
    for (t1, c1), (t0, c0) in zip(RAMP, RAMP[1:]):
        if t >= t0:
            u = (t - t0) / (t1 - t0)
            return tuple(int(round(c0[i] + (c1[i] - c0[i]) * u)) for i in range(3))
    return RAMP[-1][1]


def hexcol(c) -> str:
    return "#%02X%02X%02X" % tuple(c)


def load_scores(pick: dict) -> dict | None:
    path = OUT_DIR / f"{pick['date']}_{pick.get('game_pk')}.json"
    return json.load(open(path)) if path.exists() else None


def scale_game(scores: dict) -> dict[int, dict]:
    """Colour + rank per hitter id, scaled within the game (both lineups).

    Score = stored MOMO. t = (MOMO - game min) / (game max - game min), so the
    game's best matchup is full green and its worst full red, and equal MOMOs
    get equal colours. Rank is 1 = best, ties share a rank."""
    hs = scores["hitters"]
    vals = [h["archetype"]["momo"] for h in hs]
    lo, hi = min(vals), max(vals)
    out = {}
    for h in hs:
        m = h["archetype"]["momo"]
        t = 0.5 if hi == lo else (m - lo) / (hi - lo)
        rank = 1 + sum(v > m for v in vals)
        out[int(h["id"])] = {"momo": m, "t": round(t, 4), "rank": rank, "of": len(vals),
                             "rgb": ramp(t), "hex": hexcol(ramp(t))}
    return out


# ── main ────────────────────────────────────────────────────────────────────

def export(pick_id: str, skip_vector: bool = False) -> Path:
    pick = load_pick(pick_id)
    pk = pick.get("game_pk")
    lu_path = LINEUP_DIR / f"{pick['date']}_{pk}.json"
    if not lu_path.exists():
        raise SystemExit(f"{lu_path} missing; run scripts/video/sim_reference.py --pick-id {pick_id}")
    lu = json.load(open(lu_path))

    sha, when = pregame_commit(pick)
    audit = json.loads(git("show", f"{sha}:{AUDIT}"))
    page = git("show", f"{sha}:{PAGE}")
    arch = page_lineups(page, pick["away"], pick["home"], lu["away"]["sp"]["name"], lu["home"]["sp"]["name"])
    audit_by_id = {int(r["id"]): r for r in audit.get("all", []) if r.get("id")}

    vec = None if skip_vector else vector_rows(pick, lu)
    hitters = []
    for s in ("away", "home"):
        abbr = pick[s]
        opp = "home" if s == "away" else "away"
        page_rows = {r["order"]: r for r in arch[abbr]}
        for b in lu[s]["lineup"]:
            pr = page_rows.get(b["order"])
            if not pr or norm_name(pr["name"]) != norm_name(b["name"]):
                raise SystemExit(f"{abbr} #{b['order']} {b['name']}: page row is {pr and pr['name']!r}; "
                                 "the lineup the model priced differs from the snapshot")
            momo_check = matchup_swing_to_momo(pr["base_woba"], pr["arch_woba"])
            # the page prints wOBA to 3 places, so a re-derivation can land 1 off
            if abs(momo_check - pr["momo"]) > 1:
                raise SystemExit(f"{b['name']}: stored MOMO {pr['momo']} != recomputed {momo_check}")
            au = audit_by_id.get(int(b["id"]), {})
            if au and au.get("momo") != pr["momo"]:
                raise SystemExit(f"{b['name']}: page MOMO {pr['momo']} != audit MOMO {au.get('momo')}")
            hitters.append({
                "side": s, "team": abbr, "order": b["order"], "id": b["id"], "name": b["name"], "pos": b["pos"],
                "opp_sp": lu[opp]["sp"],
                "archetype": {
                    "momo": pr["momo"], "base_woba": pr["base_woba"], "arch_woba": pr["arch_woba"],
                    "arch_pa": pr["arch_pa"], "run_contrib": pr["run_contrib"], "momi": pr["momi"],
                    "hr_rate": au.get("hr_rate"), "base_hr_rate": au.get("base_hr_rate"),
                    "h2h_pa_pregame": au.get("h2h_pa"),
                },
                "vector": (vec["rows"].get(int(b["id"])) if vec else None),
            })

    out = {
        "_about": "Per-hitter model scores for one pick. See scripts/export_lineup_scores.py docstring.",
        "pick_id": pick_id, "date": pick["date"], "game_pk": pk, "away": pick["away"], "home": pick["home"],
        "model_mode": pick.get("model_mode"),
        "archetype_source": {"kind": "stored", "commit": sha, "committed_at": when,
                             "first_pitch_utc": first_pitch_utc(pick).isoformat(),
                             "files": [PAGE, AUDIT], "audit_generated": audit.get("generated")},
        "vector_source": ({"kind": "recomputed", **vec["meta"]} if vec else None),
        "starters_vector": (vec["starters"] if vec else None),
        "hitters": hitters,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{pick['date']}_{pk}.json"
    json.dump(out, open(path, "w"), indent=1, ensure_ascii=False)
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick-id", required=True)
    ap.add_argument("--skip-vector", action="store_true", help="stored archetype layer only (no Statcast pull)")
    a = ap.parse_args()
    path = export(a.pick_id, a.skip_vector)
    d = json.load(open(path))
    print(path)
    print(f"archetype: stored, commit {d['archetype_source']['commit'][:8]} at {d['archetype_source']['committed_at']}")
    if d["vector_source"]:
        print(f"vector: recomputed, check_ok={d['vector_source']['check_ok']} {json.dumps(d['vector_source']['check'])}")
    for h in sorted(d["hitters"], key=lambda h: -h["archetype"]["momo"]):
        v = h["vector"] or {}
        print(f"  {h['team']:<4}{h['order']} {h['name']:<20} MOMO {h['archetype']['momo']:>2}  "
              f"ARCH {h['archetype']['arch_woba']:.3f}  vec {v.get('projected_xwoba')}")

#!/usr/bin/env python3
"""Data for the interactive lineup page: lineup/data/{pickId}.json.

  python3 scripts/export_lineup_scores.py --pick-id 2026-09-26-mlb-TB-PHI-ml   # model scores first
  python3 scripts/export_lineup_page.py   --pick-id 2026-09-26-mlb-TB-PHI-ml [--refresh]

Every value in the output is tagged by where it comes from (see "sources"):
  stored      picks/mlb.json, and the per-hitter archetype output the pipeline
              committed before first pitch (via mlbsim/lineup_scores/)
  recomputed  per-hitter vector rows (same code + Statcast window as the live
              gate; team means checked against the stored ones)
  derived     matchup colour/rank (scaled within the game), the run
              distribution (NB fitted to the stored projection + WP, as on
              the card back), head-to-head before first pitch (career
              vsPlayer total minus the plate appearances from this game on)
  fetched     MLB Stats API: lineups, park, handedness, head-to-head,
              play-by-play; cached with URL + date in data/reference/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR / "video"))

import sim_reference as ref  # noqa: E402
from export_lineup_scores import load_pick, load_scores, scale_game, RAMP, hexcol  # noqa: E402

OUT_DIR = REPO / "lineup" / "data"
CACHE_DIR = REPO / "data" / "reference" / "mlb_matchups"
API = "https://statsapi.mlb.com/api/v1"
PEOPLE_URL = API + "/people?personIds={ids}"
VS_URL = API + "/people/{batter}/stats?stats=vsPlayer&opposingPlayerId={pitcher}&group=hitting&gameType=R"
SERIES_URL = API + "/schedule?sportId=1&teamId={a}&opponentId={b}&startDate={start}&endDate={end}&gameType=R"
PBP_URL = API + "/game/{pk}/playByPlay"
HEADSHOT = "https://img.mlbstatic.com/mlb-photos/image/upload/w_213,q_auto:best/v1/people/{id}/headshot/67/current"

PA_EVENTS = {
    "single", "double", "triple", "home_run", "walk", "intent_walk", "hit_by_pitch", "strikeout",
    "strikeout_double_play", "strikeout_triple_play", "field_out", "force_out", "grounded_into_double_play",
    "grounded_into_triple_play", "double_play", "triple_play", "fielders_choice", "fielders_choice_out",
    "field_error", "sac_fly", "sac_bunt", "sac_fly_double_play", "sac_bunt_double_play", "catcher_interf",
}
COUNT_KEYS = ("pa", "ab", "h", "d2", "d3", "hr", "bb", "k", "hbp", "sf", "tb")


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "morellosims-lineup/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _counts_from_api(stat: dict) -> dict:
    g = lambda k: int(stat.get(k) or 0)  # noqa: E731
    return {"pa": g("plateAppearances"), "ab": g("atBats"), "h": g("hits"), "d2": g("doubles"),
            "d3": g("triples"), "hr": g("homeRuns"), "bb": g("baseOnBalls"), "k": g("strikeOuts"),
            "hbp": g("hitByPitch"), "sf": g("sacFlies"), "tb": g("totalBases")}


def _counts_from_events(events: list[str]) -> dict:
    c = dict.fromkeys(COUNT_KEYS, 0)
    for e in events:
        c["pa"] += 1
        hit = {"single": 1, "double": 2, "triple": 3, "home_run": 4}.get(e)
        if hit:
            c["h"] += 1
            c["tb"] += hit
            c["d2"] += e == "double"
            c["d3"] += e == "triple"
            c["hr"] += e == "home_run"
        c["bb"] += e in ("walk", "intent_walk")
        c["k"] += e.startswith("strikeout")
        c["hbp"] += e == "hit_by_pitch"
        c["sf"] += e.startswith("sac_fly")
        no_ab = e in ("walk", "intent_walk", "hit_by_pitch", "catcher_interf") or e.startswith("sac_")
        c["ab"] += not no_ab
    return c


def _line(c: dict) -> dict:
    out = dict(c)
    out["avg"] = round(c["h"] / c["ab"], 3) if c["ab"] else None
    den = c["ab"] + c["bb"] + c["hbp"] + c["sf"]
    out["obp"] = round((c["h"] + c["bb"] + c["hbp"]) / den, 3) if den else None
    out["slg"] = round(c["tb"] / c["ab"], 3) if c["ab"] else None
    return out


def matchup_refs(pick: dict, lu: dict, refresh: bool = False) -> dict:
    """People (handedness), head-to-head totals and play-by-play of this game onward. Cached."""
    path = CACHE_DIR / f"{pick['date']}_{pick['game_pk']}.json"
    if path.exists() and not refresh:
        return json.load(open(path))
    today = date.today().isoformat()
    ids = [r["id"] for s in ("away", "home") for r in lu[s]["lineup"]] + [lu[s]["sp"]["id"] for s in ("away", "home")]
    p_url = PEOPLE_URL.format(ids=",".join(map(str, ids)))
    people = {str(p["id"]): {"name": p["fullName"], "bats": (p.get("batSide") or {}).get("code"),
                             "throws": (p.get("pitchHand") or {}).get("code"),
                             "number": p.get("primaryNumber")} for p in _get(p_url)["people"]}
    # every game between these two clubs from the pick date to today: the pre-game
    # head-to-head is the career total minus plate appearances in these games
    ta, th = ref.team(pick["away"])["id"], ref.team(pick["home"])["id"]
    s_url = SERIES_URL.format(a=ta, b=th, start=pick["date"], end=today)
    pks = [g["gamePk"] for d in _get(s_url).get("dates", []) for g in d["games"]]
    if pick["game_pk"] not in pks:
        raise SystemExit(f"game {pick['game_pk']} not in {s_url}")
    plays = []
    for pk in pks:
        for pl in _get(PBP_URL.format(pk=pk)).get("allPlays", []):
            ev = (pl.get("result") or {}).get("eventType")
            if ev in PA_EVENTS and (pl.get("about") or {}).get("isComplete", True):
                plays.append({"game_pk": pk, "batter": pl["matchup"]["batter"]["id"],
                              "pitcher": pl["matchup"]["pitcher"]["id"], "event": ev})
    h2h = {}
    for s, opp in (("away", "home"), ("home", "away")):
        pid = lu[opp]["sp"]["id"]
        for r in lu[s]["lineup"]:
            url = VS_URL.format(batter=r["id"], pitcher=pid)
            tot = next((sp["stat"] for st in _get(url).get("stats", [])
                        if st["type"]["displayName"] == "vsPlayerTotal" for sp in st["splits"]), {})
            h2h[f"{r['id']}_{pid}"] = {"url": url, "total": _counts_from_api(tot) if tot else dict.fromkeys(COUNT_KEYS, 0)}
    snap = {"_fetched": today, "_sources": {"people": p_url, "series": s_url, "play_by_play": PBP_URL,
                                             "vs_player": VS_URL},
            "people": people, "series_games": pks, "plays": plays, "h2h": h2h}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(snap, open(path, "w"), indent=1, ensure_ascii=False)
    return snap


def pregame_h2h(mref: dict, batter: int, pitcher: int) -> dict:
    tot = mref["h2h"][f"{batter}_{pitcher}"]["total"]
    since = [p["event"] for p in mref["plays"] if p["batter"] == batter and p["pitcher"] == pitcher]
    sub = _counts_from_events(since)
    pre = {k: tot[k] - sub[k] for k in COUNT_KEYS}
    if min(pre.values()) < 0:
        raise SystemExit(f"h2h {batter} v {pitcher}: negative after subtracting {sub} from {tot}")
    return _line(pre)


def sim_block(pick: dict) -> dict:
    import render_card_back as rb
    sim = rb.SimDist(pick)
    n = rb.HIST_BINS
    a = rb._nb_pmf(sim.mu_side, sim.k)
    b = rb._nb_pmf(sim.mu_opp, sim.k)
    return {"side": sim.side, "opp": sim.opp, "mu_side": sim.mu_side, "mu_opp": sim.mu_opp, "wp": sim.wp,
            "nb_size_k": None if sim.k is None else round(sim.k, 4),
            "pmf_side": [round(float(x), 5) for x in a[:n]], "pmf_opp": [round(float(x), 5) for x in b[:n]],
            "tail_side": round(float(a[n:].sum()), 5), "tail_opp": round(float(b[n:].sum()), 5)}


def export(pick_id: str, refresh: bool = False) -> Path:
    from render_series_card import load_picks, team_ref
    pick = load_pick(pick_id)
    scores = load_scores(pick)
    if not scores:
        raise SystemExit(f"no mlbsim/lineup_scores for {pick_id}; run scripts/export_lineup_scores.py first")
    scale = scale_game(scores)
    lu = ref.lineups(pick)
    venue = ref.venue_for_team(pick["home"])
    mref = matchup_refs(pick, lu, refresh)
    set_no = next(i for i, p in enumerate(load_picks(), 1) if p["id"] == pick_id)
    by_id = {h["id"]: h for h in scores["hitters"]}

    sides = {}
    for s, opp in (("away", "home"), ("home", "away")):
        abbr = pick[s]
        city, club, _ = team_ref(abbr)
        sp = lu[s]["sp"]
        opp_sp = lu[opp]["sp"]
        hitters = []
        for r in lu[s]["lineup"]:
            h = by_id[r["id"]]
            sc = scale[r["id"]]
            pp = mref["people"].get(str(r["id"]), {})
            hitters.append({
                "order": r["order"], "id": r["id"], "name": r["name"], "pos": r["pos"], "bats": pp.get("bats"),
                "headshot": HEADSHOT.format(id=r["id"]),
                "score": {"momo": sc["momo"], "rank": sc["rank"], "of": sc["of"], "t": sc["t"], "color": sc["hex"]},
                "archetype": h["archetype"], "vector": h["vector"],
                "h2h": pregame_h2h(mref, r["id"], opp_sp["id"]),
            })
            stored_pa = h["archetype"].get("h2h_pa_pregame")
            hitters[-1]["h2h"]["pa_matches_stored"] = (None if stored_pa is None
                                                       else hitters[-1]["h2h"]["pa"] == stored_pa)
        spv = (scores.get("starters_vector") or {}).get(s) or {}
        sides[s] = {"abbr": abbr, "club": club, "city": city, "is_pick": abbr == pick["side"],
                    "sp": {"id": sp["id"], "name": sp["name"],
                           "throws": mref["people"].get(str(sp["id"]), {}).get("throws"),
                           "headshot": HEADSHOT.format(id=sp["id"]), "vector": spv},
                    "hitters": hitters}

    out = {
        "pick": {k: pick.get(k) for k in ("id", "date", "away", "home", "side", "odds", "conf", "game_time",
                                          "sim_projection", "model_wp_calibrated", "model_mode", "game_pk")},
        "set_no": set_no,
        "venue": {"name": venue["name"], "city": venue.get("city"), "state": venue.get("state"),
                  "fieldInfo": {k: venue["fieldInfo"][k] for k in ref.FENCE_KEYS if k in venue["fieldInfo"]}},
        "sides": sides,
        "sim": sim_block(pick),
        "scale": {"rule": "MOMO scaled within the game across both lineups: t = (MOMO - min) / (max - min)",
                  "ramp": [{"t": t, "color": hexcol(c)} for t, c in RAMP]},
        "sources": {
            "stored": {"picks": "picks/mlb.json",
                       "archetype": {k: scores["archetype_source"][k] for k in ("commit", "committed_at", "files")}},
            "recomputed": scores.get("vector_source"),
            "derived": ["score.t/color/rank", "sim.pmf_*", "h2h (career vsPlayer minus plays from this game on)"],
            "fetched": {"lineups": lu.get("_source"), "lineups_fetched": lu.get("_fetched"),
                        "park": venue.get("source"), "matchups": mref["_sources"],
                        "matchups_fetched": mref["_fetched"]},
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{pick_id}.json"
    json.dump(out, open(path, "w"), indent=1, ensure_ascii=False)
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick-id", required=True)
    ap.add_argument("--refresh", action="store_true", help="re-fetch people / head-to-head / play-by-play")
    a = ap.parse_args()
    p = export(a.pick_id, a.refresh)
    d = json.load(open(p))
    print(p, f"({os.path.getsize(p) // 1024} KB)")
    for s in ("away", "home"):
        for h in d["sides"][s]["hitters"]:
            x = h["h2h"]
            print(f"  {d['sides'][s]['abbr']:<4}{h['order']} {h['name']:<18} {h['bats']}  MOMO {h['score']['momo']:>2} "
                  f"#{h['score']['rank']:<2} h2h {x['h']}-{x['ab']} ({x['pa']} PA) stored pregame PA "
                  f"{h['archetype'].get('h2h_pa_pregame')}")

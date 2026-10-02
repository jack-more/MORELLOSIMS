#!/usr/bin/env python3
"""test_nfl_pipeline.py — NFL model + shadow pipeline, offline.

  * no lookahead: ratings for a date are identical when every game on/after
    that date is scrambled; a season's predictions ignore that season's results
  * spread sign convention and ATS grading
  * shadow ledger: captures only before kickoff, first capture frozen, missed
    games recorded (never backfilled), settlement grades the right side
  * check_shadow catches deletion / rewrite / post-kickoff capture
  * publishing: flag off → nothing written; flag on without tiers → nothing;
    flag on with a tier → picks/nfl.json via picks_store, sealed until kickoff
    under seal mode (id never names the side), shadow row sealed too
  * card copy: "LIONS WIN BY 6.5 · The line gives -3.5. That's 3.0 points of edge."

Run: python3 scripts/test_nfl_pipeline.py   (no network)
"""

import copy
import json
import os
import shutil
import sys
import tempfile
from datetime import timedelta

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "nfl_pipeline"))

import picks_store as store  # noqa: E402
import model as M  # noqa: E402
import shadow  # noqa: E402
import check_shadow  # noqa: E402
import backtest  # noqa: E402

TMP = tempfile.mkdtemp(prefix="nfl-test-")
DATA = M.Data()
P = M.Params(10.0, 0.8, 1500.0, False)


def env(publish=False, seal=False, key=False, now=None):
    cfg = os.path.join(TMP, "monetization.json")
    json.dump({"seal_mode": seal, "nfl_publish": publish}, open(cfg, "w"))
    os.environ[store.CONFIG_ENV] = cfg
    if key:
        os.environ[store.KEY_ENV] = KEY
    else:
        os.environ.pop(store.KEY_ENV, None)
    if now:
        os.environ[store.NOW_ENV] = now
    else:
        os.environ.pop(store.NOW_ENV, None)


KEY = store.generate_key()


# ── model ──

def test_ratings_ignore_future():
    day = pd.Timestamp("2023-11-12")
    r1 = M.ratings_at(DATA, day, 2023, P)
    tg = DATA.tg.copy()
    qg = DATA.qg.copy()
    fut = tg["gameday"] >= day
    rng = np.random.default_rng(0)
    for c in ("epa", "pass_epa", "rush_epa", "epa_c", "st_epa"):
        tg.loc[fut, c] = rng.normal(0, 50, fut.sum())
    qf = qg["gameday"] >= day
    qg.loc[qf, "qb_epa"] = rng.normal(0, 50, qf.sum())
    sched = DATA.sched.copy()
    sched.loc[sched["gameday"] >= day, "result"] = 99
    d2 = M.Data(sched.assign(gameday=sched["gameday"].dt.strftime("%Y-%m-%d")),
                tg.assign(gameday=tg["gameday"].dt.strftime("%Y-%m-%d")),
                qg.assign(gameday=qg["gameday"].dt.strftime("%Y-%m-%d")))
    r2 = M.ratings_at(d2, day, 2023, P)
    for a in ("off", "dfn", "st", "qb_mix", "off_p", "def_r"):
        assert np.allclose(getattr(r1, a), getattr(r2, a)), f"{a} changed when future games were scrambled"
    assert r1.qb_value == r2.qb_value
    assert r1.n_obs == r2.n_obs


def test_calibration_ignores_target_season():
    games = DATA.sched[["game_id", "season", "week", "game_type", "gameday", "home_team", "away_team",
                        "result", "spread_line", "location"]].copy()
    sub = games[games["season"].between(2017, 2020)]
    comp = M.raw_components(DATA, P, sub[sub["season"] >= 2019].iloc[:0])  # schema only
    # components for a slice: cheap enough for two seasons
    comp = M.raw_components(DATA, P, sub)
    a, _ = backtest.season_predictions(sub, comp, 2020, M.FEATURE_SETS["combined"])
    sub2 = sub.copy()
    sub2.loc[sub2["season"] == 2020, "result"] = -sub2.loc[sub2["season"] == 2020, "result"] + 40
    b, _ = backtest.season_predictions(sub2, comp, 2020, M.FEATURE_SETS["combined"])
    assert np.allclose(a["pred"].values, b["pred"].values), "2020 predictions moved with 2020 results"


def test_sign_convention_and_ats():
    # home favored by 3.5 (spread_line +3.5), home wins by 7 → home covers
    assert shadow.ats(True, 7, 3.5) == "W" and shadow.ats(False, 7, 3.5) == "L"
    assert shadow.ats(True, 3, 3) == "P"
    df = pd.DataFrame({"pred": [6.0, -2.0], "spread_line": [3.5, 1.0], "result": [7.0, 4.0], "season": [2020, 2020]})
    out = backtest.add_ats(df)
    assert list(out["cover"]) == [1.0, 0.0]   # model home +6 vs 3.5 → home covers; model away vs home -1 → home won by 4
    # ESPN: home pointSpread +4.5 (home underdog) → home favored by -4.5
    import espn
    o = {"homeTeamOdds": {"close": {"pointSpread": {"american": "+4.5"}}}}
    assert espn._side_spread(o, "close") == -4.5


def test_wilson_and_binomial():
    lo, hi = backtest.wilson(55, 100)
    assert 0.45 < lo < 0.46 and 0.64 < hi < 0.65
    assert abs(backtest.binom_sf(0, 10, 0.5) - 1.0) < 1e-12
    assert abs(backtest.binom_sf(10, 10, 0.5) - 0.5 ** 10) < 1e-12


# ── shadow ledger ──

def _fixture():
    """2025 week 5 as if it had not been played yet."""
    s = pd.read_csv(os.path.join(REPO, "nfl_pipeline", "data", "schedules.csv"))
    wk = s[(s["season"] == 2025) & (s["week"] == 5)]
    pre = s.copy()
    pre.loc[wk.index, ["result", "home_score", "away_score"]] = np.nan
    return s, pre, wk


def test_shadow_capture_settle_rules():
    s, pre, wk = _fixture()
    d_pre = M.Data(pre)
    first_ko = min(shadow.kickoff_utc(g) for _, g in wk.iterrows())
    t0 = first_ko - timedelta(days=2)
    env(now=shadow.iso(t0))
    led = {"rows": {}}
    led = shadow.capture(led, horizon_days=8, espn_board=[], data=d_pre, now=t0)
    assert set(led["rows"]) == set(wk["game_id"]), "every game of the week gets a row"
    for r in led["rows"].values():
        assert shadow.parse(r["first"]["captured_at"]) < shadow.parse(r["kickoff_utc"])
        assert r["first"]["line_source"] == "nflverse schedule"
    # a later run: first stays, last updates; games already kicked off are not touched
    late_game = max(wk["game_id"], key=lambda g: shadow.kickoff_utc(wk[wk["game_id"] == g].iloc[0]))
    snap = copy.deepcopy(led)
    t1 = shadow.parse(led["rows"][late_game]["kickoff_utc"]) - timedelta(hours=1)
    led = shadow.capture(led, horizon_days=8, espn_board=[], data=d_pre, now=t1)
    for gid, r in led["rows"].items():
        assert r["first"] == snap["rows"][gid]["first"], "first capture rewritten"
        ko = shadow.parse(r["kickoff_utc"])
        if ko <= t1:
            assert r["last"] == snap["rows"][gid]["last"], "captured after kickoff"
    assert led["rows"][late_game]["n_captures"] == 2
    # drop one row as if no run ever captured it → settle records it as missed
    missing = sorted(set(wk["game_id"]) - {late_game})[0]
    del led["rows"][missing]
    t2 = shadow.parse(led["rows"][late_game]["kickoff_utc"]) + timedelta(days=1)
    led = shadow.settle(led, now=t2, sched=s)
    assert led["rows"][missing]["status"] == "missed" and "first" not in led["rows"][missing]
    fin = [r for r in led["rows"].values() if r["status"] == "final"]
    assert len(fin) == len(wk) - 1
    for r in fin:
        g = s[s["game_id"] == r["game_id"]].iloc[0]
        side_home = r["last"]["edge"] > 0
        assert r["result"]["ats_last_line"] == shadow.ats(side_home, g["result"], r["last"]["line_home_fav"])
        assert r["result"]["closing_line_home_fav"] == g["spread_line"]
    path = os.path.join(TMP, "shadow_nfl.json")
    shadow.save_ledger(led, path)
    rows = json.load(open(path))["rows"]
    assert not check_shadow.check(rows, copy.deepcopy(rows)), "clean ledger flagged"
    return rows


def test_check_shadow_catches_tampering():
    rows = test_shadow_capture_settle_rules()
    old = copy.deepcopy(rows)
    gid = next(k for k, r in rows.items() if r["status"] == "final")
    bad = copy.deepcopy(rows)
    del bad[gid]
    assert any("deleted" in e for e in check_shadow.check(bad, old))
    bad = copy.deepcopy(rows)
    bad[gid]["first"]["pred_home_margin"] += 3
    assert any("first capture rewritten" in e for e in check_shadow.check(bad, old))
    bad = copy.deepcopy(rows)
    bad[gid]["result"]["ats_last_line"] = "W" if bad[gid]["result"]["ats_last_line"] != "W" else "L"
    assert any("restated" in e for e in check_shadow.check(bad, old))
    bad = copy.deepcopy(rows)
    bad[gid]["last"]["captured_at"] = bad[gid]["kickoff_utc"]
    assert any("not before kickoff" in e for e in check_shadow.check(bad, None))


# ── publishing gate ──

def _open_ledger(t0):
    s, pre, wk = _fixture()
    led = shadow.capture({"rows": {}}, horizon_days=8, espn_board=[], data=M.Data(pre), now=t0)
    path = os.path.join(TMP, "shadow_pub.json")
    shadow.save_ledger(led, path)
    return path, led


def test_publish_gate():
    import publish
    s, pre, wk = _fixture()
    t0 = min(shadow.kickoff_utc(g) for _, g in wk.iterrows()) - timedelta(days=2)
    path, led = _open_ledger(t0)
    picks = os.path.join(TMP, "nfl_picks.json")
    tiers_none = os.path.join(TMP, "tiers_none.json")
    json.dump({"tiers": []}, open(tiers_none, "w"))
    tiers_one = os.path.join(TMP, "tiers_one.json")
    json.dump({"tiers": [{"conf": 8, "min_edge": 0.0}]}, open(tiers_one, "w"))

    env(publish=False, now=shadow.iso(t0))
    assert publish.run(path, picks, tiers_one, now=t0) == [] and not os.path.exists(picks)
    env(publish=True, now=shadow.iso(t0))
    assert publish.run(path, picks, tiers_none, now=t0) == [] and not os.path.exists(picks)
    # real repo state: the committed tiers.json must hold no tier (backtest verdict)
    assert publish.load_tiers() == [], "tiers.json has a tier — the backtest verdict changed?"

    # flag on + a tier + seal mode: picks written sealed, side never public
    env(publish=True, seal=True, key=True, now=shadow.iso(t0))
    new = publish.run(path, picks, tiers_one, now=t0)
    assert new, "no picks published with a 0-point tier"
    raw = json.load(open(picks))
    for r in raw:
        assert r.get("sealed") is True, "pending pick not sealed"
        assert not any(k in r for k in store.FORBIDDEN_SEALED), "sealed pick leaks a field"
        assert r["id"].endswith("-spread") and r["id"].count("-nfl-") == 1
    srows = json.load(open(path))["rows"]
    assert all(store.is_raw_sealed(v) for v in srows.values()), "shadow rows of published picks must be sealed"
    # stakes frozen: a second run does not add or restake
    again = publish.run(path, picks, tiers_one, now=t0)
    assert again == []
    assert json.load(open(picks)) == raw
    # after the games: unseal opens with a verifiable commitment, settle grades
    t2 = max(shadow.kickoff_utc(g) for _, g in wk.iterrows()) + timedelta(days=1)
    env(publish=True, seal=True, key=True, now=shadow.iso(t2))
    opened = store.load_picks(picks)
    store.save_picks(picks, opened, now=t2)
    for r in json.load(open(picks)):
        ok, why = store.verify_record(r)
        assert ok, why
    led2 = shadow.load_ledger(path)
    led2 = shadow.settle(led2, now=t2, sched=s)
    shadow.save_ledger(led2, path)
    publish.run(path, picks, tiers_one, now=t2)
    done = json.load(open(picks))
    assert all(p["status"] in ("win", "loss", "push") for p in done)
    for p in done:
        g = s[s["game_id"] == p["game_id"]].iloc[0]
        home_side = p["side"] == p["home"]
        line_home = -p["line"] if home_side else p["line"]
        d = g["result"] - line_home
        want = "push" if d == 0 else ("win" if (d > 0) == home_side else "loss")
        assert p["status"] == want, (p["id"], p["status"], want)


def test_card_copy():
    import render_nfl_card as card
    assert card.why_line("Lions", 6.5, -3.5) == ("LIONS WIN BY 6.5", "The line gives -3.5. That's 3.0 points of edge.")
    assert card.why_line("Bears", -1.5, 4.5) == ("BEARS LOSE BY 1.5", "The line gives +4.5. That's 3.0 points of edge.")


TESTS = [test_ratings_ignore_future, test_calibration_ignores_target_season, test_sign_convention_and_ats,
         test_wilson_and_binomial, test_shadow_capture_settle_rules, test_check_shadow_catches_tampering,
         test_publish_gate, test_card_copy]


if __name__ == "__main__":
    failed = 0
    for t in TESTS:
        try:
            t()
            print(f"  ok   {t.__name__}")
        except Exception as e:
            failed += 1
            import traceback
            traceback.print_exc()
            print(f"  FAIL {t.__name__}: {type(e).__name__}: {e}")
        finally:
            env()
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"{len(TESTS) - failed}/{len(TESTS)} NFL pipeline tests passed")
    sys.exit(1 if failed else 0)

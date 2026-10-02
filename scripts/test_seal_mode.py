#!/usr/bin/env python3
"""test_seal_mode.py — seal mode (scripts/picks_store.py) end to end, offline.

  * seal mode OFF is a byte-for-byte no-op on the real picks files
  * sealing hides side/odds/line/pick_text/model fields, hides ciphertext
    length, is deterministic, and reopens with the key
  * unsealing after first pitch / tip publishes a nonce that verifies against
    the pre-game commitment (MLB and NBA, incl. NBA's side-bearing ids)
  * settlement refuses sealed picks; writers refuse to publish without a key
  * the NBA CSV ledger seals / reopens rows without changing their keys
  * the commit guardrail catches a deliberate leak and passes a clean commit

Run: python3 scripts/test_seal_mode.py   (needs `cryptography`; no network)
"""

import copy
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "nba_pipeline"))

import picks_store as store  # noqa: E402

TMP = tempfile.mkdtemp(prefix="seal-test-")
CFG_ON = os.path.join(TMP, "monetization_on.json")
CFG_OFF = os.path.join(TMP, "monetization_off.json")
json.dump({"seal_mode": True, "whop_checkout_url": "https://whop.com/test-checkout"}, open(CFG_ON, "w"))
json.dump({"seal_mode": False, "whop_checkout_url": ""}, open(CFG_OFF, "w"))
KEY = store.generate_key()

BEFORE = "2026-10-21T14:00:00Z"   # morning of the game
AFTER = "2026-10-22T03:30:00Z"    # after a 7:10 PM ET first pitch / 7:30 PM ET tip


def env(mode=None, key=True, now=None):
    if mode is None:
        os.environ.pop(store.CONFIG_ENV, None)
    else:
        os.environ[store.CONFIG_ENV] = CFG_ON if mode else CFG_OFF
    if key:
        os.environ[store.KEY_ENV] = KEY
    else:
        os.environ.pop(store.KEY_ENV, None)
    if now:
        os.environ[store.NOW_ENV] = now
    else:
        os.environ.pop(store.NOW_ENV, None)


def mlb_pick(side="NYY", odds="-120"):
    return {
        "id": "2026-10-21-mlb-NYY-BOS-ml", "sport": "mlb", "date": "2026-10-21",
        "away": "NYY", "home": "BOS", "matchup": "NYY @ BOS", "bet_type": "ml",
        "side": side, "line": None, "odds": odds, "published_at": "2026-10-21T13:05:00Z",
        "pick_text": f"{side} ML", "conf": 9, "units": 50,
        "sim_projection": "NYY 5.1 - BOS 3.9", "sim_edge": 1.2, "model_wp_raw": 61.2,
        "model_wp_calibrated": 60.4, "model_mode": "VECTOR_NATIVE", "model_version": "v2",
        "game_pk": 999001, "game_time": "7:10 PM ET",
        "status": "pending", "result": None, "pl": None, "settled_at": None,
    }


def nba_pick(side="MIN", line=11.0):
    return {
        "id": f"2026-10-21-nba-min-sa-spread-{side.lower()}", "sport": "nba", "date": "2026-10-21",
        "away": "MIN", "home": "SA", "matchup": "MIN @ SA", "bet_type": "spread",
        "side": side, "line": line, "odds": -110, "pick_text": f"{side} {line:+.1f}",
        "conf": 8, "units": 50, "sim_projection": f"{side} +2.5", "sim_edge": 6.0,
        "closing_line": None, "closing_odds": None, "status": "pending", "result": None,
        "pl": None, "captured_at": "2026-10-21T13:31:00+00:00", "void_reason": None,
        "_starts_at": "2026-10-21T23:30:00Z",
    }


def test_off_is_noop_on_real_files():
    env(mode=False, key=False)
    assert not store.seal_mode()
    for sport, path in store.PICK_FILES.items():
        if not os.path.exists(path):
            continue  # picks/nfl.json exists only once NFL publishing is turned on
        # the plaintext ledger as committed (records that never were sealed)
        raw = [r for r in json.load(open(path)) if not any(k in r for k in store.SEAL_META)]
        path = os.path.join(TMP, f"{sport}_plain.json")
        json.dump(raw, open(path, "w"), indent=2)
        assert store.load_picks(path) == raw
        assert store.load_public_picks(path) == raw
        out = store.prepare_picks(copy.deepcopy(raw), raw)
        assert json.dumps(out, indent=2) == json.dumps(raw, indent=2), f"{sport}: not a no-op"
    from utils import ledger
    csv_path = os.path.join(REPO, "nba_pipeline", "data", "picks.csv")
    rows = [r for r in ledger.read_rows(csv_path) if not r.get(ledger.BLOB_COL) and not r.get("_sealed")]
    tmp = os.path.join(TMP, "picks_off.csv")
    ledger.write_rows(tmp, rows)
    legacy = io.StringIO()
    w = csv.DictWriter(legacy, fieldnames=ledger.CSV_FIELDS, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") if r.get(k) is not None else "" for k in ledger.CSV_FIELDS})
    assert open(tmp).read() == legacy.getvalue(), "ledger.write_rows changed output with seal mode off"
    log = [e for e in json.load(open(os.path.join(REPO, "nba_pipeline", "data", "pick_log.json")))
           if not e.get("sealed")]
    assert ledger.seal_entries(ledger.open_entries(log)) is log


def test_seal_hides_and_reopens():
    env(mode=True, now=BEFORE)
    path = os.path.join(TMP, "mlb.json")
    json.dump([], open(path, "w"))
    store.save_picks(path, [mlb_pick()])
    text = open(path).read()
    rec = json.loads(text)[0]
    assert rec["sealed"] is True and rec["commitment"] and rec["sealed_blob"]
    for k in store.FORBIDDEN_SEALED:
        assert k not in rec, f"sealed record leaks {k}"
    for needle in ("NYY ML", "-120", "5.1", "61.2"):
        assert needle not in text, f"sealed file contains {needle!r}"
    assert set(rec) <= set(store.PUBLIC_PICK_FIELDS) | set(store.SEAL_META)
    # deterministic: rewriting the same pick gives the same bytes
    store.save_picks(path, store.load_picks(path))
    assert open(path).read() == text, "re-sealing changed the file (git churn)"
    # length-hiding: a 2-letter vs 3-letter side gives the same blob length
    a = store.seal_pick(mlb_pick("NYY"))
    b = store.seal_pick(dict(mlb_pick("SD"), pick_text="SD ML"))
    assert len(a["sealed_blob"]) == len(b["sealed_blob"])
    opened = store.load_picks(path)[0]
    assert opened["side"] == "NYY" and opened["odds"] == "-120" and opened["sealed"] is True
    # public view never decrypts
    pub = store.load_public_picks(path)[0]
    assert "side" not in pub and "sealed_blob" not in pub and pub["sealed"] is True


def test_unseal_verifies_commitment():
    env(mode=True, now=BEFORE)
    path = os.path.join(TMP, "mlb2.json")
    json.dump([], open(path, "w"))
    store.save_picks(path, [mlb_pick()])
    sealed = json.load(open(path))[0]
    env(mode=True, now=AFTER)
    store.save_picks(path, store.load_picks(path))       # what unseal_picks.py does
    rec = json.load(open(path))[0]
    assert "sealed" not in rec and rec["side"] == "NYY"
    assert rec["commitment"] == sealed["commitment"]
    ok, msg = store.verify_record(rec)
    assert ok, msg
    # settlement later mutates lifecycle fields: still verifies
    rec.update(status="win", result="5-3", pl=41.67, settled_at="2026-10-22")
    assert store.verify_record(rec)[0]
    # a restated bet fails
    bad = dict(rec, side="BOS", pick_text="BOS ML")
    assert not store.verify_record(bad)[0]
    # carried forward unchanged by later saves (e.g. settle_mlb)
    store.save_picks(path, [rec])
    again = json.load(open(path))[0]
    assert again["nonce"] == rec["nonce"] and again["unsealed_at"] == rec["unsealed_at"]


def test_nba_public_id_hides_side():
    env(mode=True, now=BEFORE)
    path = os.path.join(TMP, "nba.json")
    json.dump([], open(path, "w"))
    store.save_picks(path, [nba_pick()])
    rec = json.load(open(path))[0]
    assert rec["id"].startswith("2026-10-21-nba-min-sa-spread-sealed-"), rec["id"]
    assert "MIN +11.0" not in open(path).read()
    env(mode=True, now=AFTER)
    # NBA rebuilds picks/nba.json from the CSV every run (sync_to_picks_json)
    store.save_picks(path, [dict(nba_pick(), status="pending")])
    rec2 = json.load(open(path))[0]
    assert rec2["id"] == "2026-10-21-nba-min-sa-spread-min" and rec2["sealed_id"] == rec["id"]
    assert rec2["commitment"] == rec["commitment"]
    assert store.verify_record(rec2)[0]


def test_settlement_and_key_guards():
    env(mode=True, now=BEFORE)
    sealed = store.seal_pick(mlb_pick())
    try:
        store.assert_settleable([sealed])
        raise AssertionError("settlement accepted a sealed pick")
    except store.SealError:
        pass
    store.assert_settleable([dict(mlb_pick(), status="win")])
    env(mode=True, key=False, now=BEFORE)
    try:
        store.prepare_picks([mlb_pick()], [])
        raise AssertionError("published a pending pick in plaintext without a key")
    except store.SealError:
        pass
    # defense in depth: a plaintext pending pick reaching a public renderer is sealed
    view = store.public_view(mlb_pick())
    assert "side" not in view and view["sealed"] is True


def test_csv_ledger_seal_roundtrip():
    env(mode=True, now=BEFORE)
    from utils import ledger
    path = os.path.join(TMP, "picks.csv")
    settled = {"date": "2026-10-20", "matchup": "BOS @ NYK", "side": "NYK -3.5", "type": "spread",
               "risk": "50", "result": "W", "profit": "45.45", "captured_at": "2026-10-20T13:00:00+00:00",
               "tip_at": "2026-10-20T23:30:00+00:00"}
    pending = {"date": "2026-10-21", "matchup": "MIN @ SA", "side": "MIN +11.0", "type": "spread",
               "risk": "50", "result": "", "captured_at": "2026-10-21T13:31:00+00:00",
               "tip_at": "2026-10-21T23:30:00+00:00"}
    ledger.write_rows(path, [settled, pending])
    text = open(path).read()
    assert "MIN +11.0" not in text and "SEALED" in text and "sealed_blob" in text.splitlines()[0]
    rows = ledger.read_rows(path)
    assert rows[1]["side"] == "MIN +11.0" and rows[1].get("_sealed")
    assert rows[0]["side"] == "NYK -3.5"
    ledger.write_rows(path, rows)
    assert open(path).read() == text, "re-sealing a CSV row changed bytes"
    env(mode=True, now=AFTER)
    ledger.write_rows(path, ledger.read_rows(path))
    text2 = open(path).read()
    assert "MIN +11.0" in text2 and "sealed_blob" not in text2


def test_legacy_undated_rows_never_sealed():
    """pick_log entries from early 2026 carry "MAR 2"-style dates and no tip:
    they are history and must stay plaintext (regression: sealed forever)."""
    env(mode=True, now=BEFORE)
    from utils import ledger
    legacy = {"slate_date": "MAR 2", "matchup": "BOS @ MIL", "side": "MIL -4.5", "risk": 30,
              "captured_at": "2026-03-02T15:00:00+00:00"}
    fresh = {"slate_date": "2026-10-21", "matchup": "MIN @ SA", "side": "MIN +11.0", "risk": 50,
             "tip_at": "2026-10-21T23:30:00+00:00"}
    out = ledger.seal_entries([legacy, fresh])
    assert out[0] is legacy and out[1].get("sealed") is True and "side" not in out[1]
    assert not store.before_start({"date": "", "status": "pending"})


def test_state_refs_hide_nba_side():
    env(mode=True)
    pid = "2026-10-21-nba-min-sa-spread-min"
    ref = store.state_ref(pid)
    assert ref.startswith("h:") and "min" not in ref[2:4]
    assert store.ref_in([ref], pid) and store.ref_in([pid], pid)
    assert store.state_ref("2026-10-21-mlb-NYY-BOS-ml") == "2026-10-21-mlb-NYY-BOS-ml"
    env(mode=False)
    assert store.state_ref(pid) == pid


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def test_guardrail_catches_leak():
    env(mode=True, now=BEFORE)
    repo = os.path.join(TMP, "repo")
    os.makedirs(os.path.join(repo, "scripts"))
    os.makedirs(os.path.join(repo, "ops", "config"))
    os.makedirs(os.path.join(repo, "picks"))
    for f in ("picks_store.py", "check_seal_guardrail.py"):
        shutil.copy(os.path.join(HERE, f), os.path.join(repo, "scripts", f))
    shutil.copy(CFG_ON, os.path.join(repo, "ops", "config", "monetization.json"))
    sealed = store.seal_pick(mlb_pick())
    json.dump([sealed], open(os.path.join(repo, "picks", "mlb.json"), "w"), indent=2)
    json.dump([], open(os.path.join(repo, "picks", "nba.json"), "w"))
    page = '<div class="pick-row">{}</div>\n'
    open(os.path.join(repo, "index.html"), "w").write(page.format("NYY @ BOS · SEALED · C:9"))
    _git(repo, "init", "-q")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")

    def guard():
        e = dict(os.environ)
        e.pop(store.CONFIG_ENV, None)  # the temp repo's own config (seal mode on)
        r = subprocess.run([sys.executable, os.path.join(repo, "scripts", "check_seal_guardrail.py")],
                           cwd=repo, capture_output=True, text=True, env=e)
        return r.returncode, r.stdout + r.stderr

    # clean change: a sealed row re-rendered → passes
    open(os.path.join(repo, "index.html"), "w").write(page.format("NYY @ BOS · SEALED · C:9 · 7:10 PM ET"))
    _git(repo, "add", "index.html")
    rc, out = guard()
    assert rc == 0, out
    # deliberate leak: the board shows the side with its price → fails
    leak = '<span class="pr-side">NYY ML</span><span class="pr-conf">-120</span>'
    open(os.path.join(repo, "index.html"), "w").write(page.format(leak))
    _git(repo, "add", "index.html")
    rc, out = guard()
    assert rc == 1 and "exposes sealed pick" in out, out
    assert "NYY ML" not in out, "guardrail output must not repeat the side"
    # deliberate leak: a pending pick written to picks/mlb.json in plaintext → fails
    _git(repo, "checkout", "-q", "HEAD", "--", "index.html")
    json.dump([mlb_pick()], open(os.path.join(repo, "picks", "mlb.json"), "w"), indent=2)
    _git(repo, "add", "-A")
    rc, out = guard()
    assert rc == 1 and "plaintext" in out, out
    # same files after first pitch → allowed
    os.environ[store.NOW_ENV] = AFTER
    rc, out = guard()
    assert rc == 0, out


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    saved = {k: os.environ.get(k) for k in (store.CONFIG_ENV, store.KEY_ENV, store.NOW_ENV)}
    failed = 0
    try:
        for t in tests:
            try:
                t()
                print(f"  ok   {t.__name__}")
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"  FAIL {t.__name__}: {type(e).__name__}: {e}")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(TMP, ignore_errors=True)
    print(f"{len(tests) - failed}/{len(tests)} seal-mode tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

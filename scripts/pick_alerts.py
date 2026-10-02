#!/usr/bin/env python3
"""New-pick alerts, both sports: owner DM first, members, sealed card to X.

Owner rule (2026-09-30): X posts are blurred unless Jack says otherwise.
For every newly published pick (MLB picks/mlb.json, NBA picks/nba.json):
  1. DM Jack the full pick (the real card for MLB) with a button
     "Post to X unblurred" — tg_channel_bot.py handles the tap;
  2. members: when TELEGRAM_PREMIUM_CHANNEL_ID is set, post the full v3
     card + pick text to the premium channel (the paid product — seal mode
     keeps every public copy sealed until first pitch / tip);
  3. post the SEALED card to X (render_sealed.py) — matchup, time,
     confidence and log time only; the side never leaves the DM.

Picks are read through picks_store (sealed picks open with PICKS_SEAL_KEY).
Without the key a sealed pick cannot be read: its DM / member post wait
(not marked sent) until a run has the key; the sealed X card still goes.

Runs from tg_channel_bot.py (15-min cron) and is dispatched right after the
MLB/NBA pipelines publish, so alerts land within minutes. State in
ops/state/pick_alerts.json keeps every send exactly-once across runs.

  python3 scripts/pick_alerts.py [--dry-run]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ops_tg  # noqa: E402
import picks_store  # noqa: E402

REPO = os.path.dirname(HERE)
STATE = os.path.join(REPO, "ops", "state", "pick_alerts.json")  # telegram/ is gitignored
LEGACY = os.path.join(REPO, "mlbsim", "posted_cards.json")
OUT = os.path.join(REPO, "posters", "v2")
ET = timezone(timedelta(hours=-4))
MIN_CONF = 8
UNLOCK_WORD = {"nba": "tip", "nfl": "kickoff"}
PREMIUM = os.environ.get("TELEGRAM_PREMIUM_CHANNEL_ID", "").strip()


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def odds_str(p):
    o = str(p.get("odds") or "")
    return o if not o or o.startswith(("+", "-")) else f"+{o}"


def pick_sources():
    """Sport files to alert on. NFL only when the owner has turned NFL
    publishing on (ops/config/monetization.json nfl_publish) — shadow mode
    DMs nothing."""
    out = [("mlb", "picks/mlb.json"), ("nba", "picks/nba.json")]
    if picks_store.config().get("nfl_publish") is True:
        out.append(("nfl", "picks/nfl.json"))
    return out


def published_today(today):
    out = []
    for sport, path in pick_sources():
        for p in picks_store.load_picks(os.path.join(REPO, path)):
            if (p.get("sport") or sport) == sport and p.get("date") == today \
                    and p.get("status") == "pending" and int(p.get("conf") or 0) >= MIN_CONF:
                p.setdefault("sport", sport)
                out.append(p)
    return out


def card_path(p, sealed=False):
    """v3 pick card (MLB render_pick_card / NBA render_nba_card), saved to OUT."""
    os.makedirs(OUT, exist_ok=True)
    sport = p.get("sport") or "mlb"
    mod = __import__({"nba": "render_nba_card", "nfl": "render_nfl_card"}.get(sport, "render_pick_card"))
    path = os.path.join(OUT, f"{'sealed' if sealed else 'pick'}-{p['id']}.png")
    (mod.sealed(p) if sealed else mod.render(p, False)).save(path)
    return path


def dm_text(p):
    sim = p.get("sim_projection") or ""
    return (f"🚨 NEW {p['sport'].upper()} PICK · C{p.get('conf')}\n"
            f"{p['pick_text']} {odds_str(p)} · {p.get('matchup')} · {p.get('game_time') or ''}\n"
            f"Risk {p.get('units')} $PP" + (f" · Sim {sim}" if sim else "") + "\n"
            f"X gets the sealed card. Tap below to post it unblurred.")


def premium_text(p):
    """Member post. First line carries no side (dry runs print it to public logs)."""
    sim = p.get("sim_projection") or ""
    when = p.get("game_time") or picks_store.start_label(p)
    return (f"🔒 MEMBERS · {p['sport'].upper()} · C{p.get('conf')} · {p.get('matchup')}\n"
            f"{p['pick_text']} {odds_str(p)}" + (f" · {when}" if when else "") + "\n"
            f"Risk {p.get('units')} $PP" + (f" · Sim {sim}" if sim else "") + "\n"
            f"Public copy stays sealed until {UNLOCK_WORD.get(p['sport'], 'first pitch')}.")


def x_caption(p):
    when = p.get("game_time") or ""
    return (f"SEALED · C{p.get('conf')} · {p.get('matchup')}" + (f" · {when}" if when else "") + "\n"
            f"Logged {datetime.now(ET).strftime('%-I:%M %p ET')}, before the game.\n"
            f"Members have it now → morellosims.com")


def run(dry=False):
    if dry:
        ops_tg.DRY = True
    today = datetime.now(ET).strftime("%Y-%m-%d")
    st = load(STATE, {"dm": [], "x_sealed": [], "x_open": []})
    if PREMIUM:
        st.setdefault("premium", [])
    # picks already receipted by the old post_daily_cards flow count as sent
    legacy = load(LEGACY, {})
    for pid in legacy.get("receipts", []):
        if pid not in st["dm"]:
            st["dm"].append(pid)
    for pid in legacy.get("x_receipts", []):
        if pid not in st["x_sealed"]:
            st["x_sealed"].append(pid)

    from post_social_daily import post_to_x
    os.makedirs(OUT, exist_ok=True)
    for p in published_today(today):
        pid = p["id"]
        readable = not picks_store.is_raw_sealed(p)
        if not readable:
            print(f"  WARN {pid}: sealed and {picks_store.KEY_ENV} not set — DM / member post wait")
        ref = picks_store.state_ref(pid)  # NBA ids name the side: hashed in committed state under seal mode
        if readable and not picks_store.ref_in(st["dm"], pid):
            button = [[("📣 Post to X unblurred", f"xopen:{pid}")]]
            ok = False
            try:
                path = card_path(p)
                ok = ops_tg.send_photo(path, dm_text(p), button)
            except (Exception, SystemExit) as e:
                print(f"  WARN card render {pid}: {e}")
            if not ok:
                ok = ops_tg.send(dm_text(p), button)
            if ok:
                st["dm"].append(ref)
        if PREMIUM and readable and not picks_store.ref_in(st["premium"], pid):
            ok = False
            try:
                ok = ops_tg.send_photo(card_path(p), premium_text(p), chat=PREMIUM)
            except (Exception, SystemExit) as e:
                print(f"  WARN member card {pid}: {e}")
            if not ok:
                ok = ops_tg.send(premium_text(p), chat=PREMIUM)
            if ok:
                st["premium"].append(ref)
        if not picks_store.ref_in(st["x_sealed"], pid) and not picks_store.ref_in(st["x_open"], pid):
            try:
                path = card_path(p, sealed=True)
                if post_to_x(x_caption(p), Path(path), dry_run=dry):
                    st["x_sealed"].append(ref)
            except Exception as e:
                print(f"  WARN sealed X post {pid}: {e}")
    for k in st:
        st[k] = st[k][-600:]
    if not dry:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w") as f:
            json.dump(st, f, indent=2)
    return st


def open_on_x(pid, dry=False):
    """Owner tapped 'Post to X unblurred': the real card, full pick."""
    st = load(STATE, {"dm": [], "x_sealed": [], "x_open": []})
    if picks_store.ref_in(st["x_open"], pid):
        return "already posted unblurred"
    p = next((q for q in published_today(datetime.now(ET).strftime("%Y-%m-%d")) if q["id"] == pid), None)
    if p is None:
        for _, path in pick_sources():
            p = p or next((q for q in picks_store.load_picks(os.path.join(REPO, path)) if q["id"] == pid), None)
    if p is None:
        return "pick not found"
    from post_social_daily import post_to_x
    cap = (f"{p['pick_text']} {odds_str(p)} · C{p.get('conf')} · {p.get('matchup')}\n"
           f"Logged before the game. Every pick → morellosims.com")
    try:
        images = [Path(card_path(p))]
    except (Exception, SystemExit) as e:
        return f"card render failed: {e}"
    if post_to_x(cap, images, dry_run=dry):
        st["x_open"].append(picks_store.state_ref(pid))
        if not dry:
            with open(STATE, "w") as f:
                json.dump(st, f, indent=2)
        return "posted to X unblurred"
    return "X post failed (are the X secrets set?)"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(dry=a.dry_run)

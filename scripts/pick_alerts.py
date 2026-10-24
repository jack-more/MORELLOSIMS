#!/usr/bin/env python3
"""New-pick alerts, both sports: owner DM first, members, sealed card to X.

Owner rule (2026-09-30): X posts are blurred unless Jack says otherwise.
For every newly published pick (MLB picks/mlb.json, NBA picks/nba.json):
  1. DM Jack the full pick (the real card for MLB) with a button
     "Post to X unblurred" — tg_channel_bot.py handles the tap;
  2. members (the paid product; seal mode keeps every public copy sealed
     until first pitch / tip): the full pick goes to the members page
     (Firestore member_picks, read by /members/) and to every active member's
     inbox (member_delivery.py); and, when TELEGRAM_PREMIUM_CHANNEL_ID is set,
     the full v3 card + pick text to the premium Telegram channel;
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
import member_delivery  # noqa: E402
import ops_tg  # noqa: E402
import picks_store  # noqa: E402

REPO = os.path.dirname(HERE)
STATE = os.path.join(REPO, "ops", "state", "pick_alerts.json")  # telegram/ is gitignored
LEGACY = os.path.join(REPO, "mlbsim", "posted_cards.json")
# owner stake changes after a pick went out: [{"ref": state_ref, "was": "2u to win", "why": ..., "done": ...}]
RESTAKE = os.path.join(REPO, "ops", "state", "restake.json")
OUT = os.path.join(REPO, "posters", "v2")
ET = timezone(timedelta(hours=-4))
MIN_CONF = 6   # same floor as capture_picks.MIN_TRACKED_CONF_GRADE
# The owner is the guard (2026-10-22): from this date a pick reaches members (page,
# email, premium channel) only after Jack taps Send on its DM. One he holds, or never
# sends before tip, is voided at grading (nba_pipeline/scripts/grade_picks.release_check).
GATE_FROM = "2026-10-23"
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
    """The pick's card, saved to OUT: an NBA spread is its banknote note with the home arena
    (render_pick_note, headless Chrome); anything else, or a note that fails to render, is the
    v3 card (MLB render_pick_card / NBA render_nba_card)."""
    os.makedirs(OUT, exist_ok=True)
    sport = p.get("sport") or "mlb"
    if sport == "nba" and not sealed and (p.get("bet_type") or "spread") == "spread":
        try:
            import render_pick_note
            ps = sorted(picks_store.load_picks(os.path.join(REPO, "picks", "nba.json")), key=lambda x: (x["date"], x["id"]))
            n = next((i for i, x in enumerate(ps, 1) if x["id"] == p["id"]), 1)
            note = render_pick_note.render(p, os.path.join(OUT, f"note-{p['id']}.png"), n=n,
                                           when_label=p.get("game_time") or picks_store.start_label(p))
            if note:
                return note
        except Exception as e:
            print(f"  WARN note render {p.get('matchup')}: {type(e).__name__}")
    mod = __import__({"nba": "render_nba_card", "nfl": "render_nfl_card"}.get(sport, "render_pick_card"))
    path = os.path.join(OUT, f"{'sealed' if sealed else 'pick'}-{p['id']}.png")
    (mod.sealed(p) if sealed else mod.render(p, False)).save(path)
    return path


def gap(p):
    """Points between the sim's number and the book's for the picked side, or None.
    CLE +3.5 with the sim at CLE -3.5 is 7 apart."""
    sim, line = (p.get("sim_projection") or "").split(), p.get("line")
    if len(sim) != 2 or line is None:
        return None
    try:
        mine = 0.0 if sim[1] == "PK" else float(sim[1])
        return abs(float(line) - mine) if sim[0] == str(p.get("pick_text", "")).split()[0] else abs(float(line) + mine)
    except ValueError:
        return None


def gated(p):
    return p.get("sport") == "nba" and (p.get("date") or "") >= GATE_FROM


def released(st, p):
    """Members may have this pick: Jack tapped Send (or it predates the gate)."""
    return not gated(p) or any(picks_store.ref_matches(e.split("|", 1)[0], p["id"]) for e in st.get("approved", []))


def dm_text(p):
    sim = p.get("sim_projection") or ""
    g = gap(p)
    head = (f"🚨 NEW {p['sport'].upper()} PICK · C{p.get('conf')}\n"
            f"{p['pick_text']} {odds_str(p)} · {p.get('matchup')} · {p.get('game_time') or ''}\n"
            f"Risk {p.get('units')} $PP ({float(p.get('units') or 0) / 25:g}u)" + (f" · Sim {sim}" if sim else "")
            + (f" · {g:.1f} pts off the book" if g is not None else "") + "\n")
    if gated(p):
        return head + ("Members don't have it yet. ✅ Send puts it on the members page, email and channel; "
                       "❌ Hold keeps it off and it won't count. Nothing goes out if you don't tap before tip.")
    return head + "X gets the sealed card. Tap below to post it unblurred."


def decide(ref, send):
    """Jack tapped ✅ Send / ❌ Hold on a pick DM (tg_channel_bot.handle_owner). Recorded with
    the time; run() delivers a sent pick in the same bot run. Returns the reply for the DM."""
    p = next((p for sport, path in pick_sources() for p in picks_store.load_picks(os.path.join(REPO, path))
              if p.get("status") == "pending" and picks_store.ref_matches(ref, p.get("id"))), None)
    if p is None:
        return "That pick isn't pending anymore (graded, voided or not found)."
    p.setdefault("sport", "nba")
    name = f"{p.get('pick_text') or 'the pick'} ({p.get('matchup')})"
    start = picks_store.start_time(p)
    if start is not None and datetime.now(timezone.utc) >= start:
        return f"Too late: {name} has tipped. It stays off the members page and won't count."
    st = load(STATE, {})
    key = "approved" if send else "held"
    st.setdefault(key, []).append(f"{picks_store.state_ref(p['id'])}|{datetime.now(timezone.utc).isoformat()}")
    if send:   # a Hold after a Send takes it back off the list, and the other way round
        st["held"] = [e for e in st.get("held", []) if not picks_store.ref_matches(e.split("|", 1)[0], p["id"])]
    else:
        st["approved"] = [e for e in st.get("approved", []) if not picks_store.ref_matches(e.split("|", 1)[0], p["id"])]
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(st, f, indent=2)
    if send:
        return f"✅ Sent: {name} goes to the members page, email and channel now."
    return f"❌ Held: {name} stays off the members page and email, and won't count on the ledger."


def premium_text(p):
    """Member post. First line carries no side (dry runs print it to public logs)."""
    sim = p.get("sim_projection") or ""
    when = p.get("game_time") or picks_store.start_label(p)
    return (f"MEMBERS · {p['sport'].upper()} · {p.get('matchup')}" + (f" · {when}" if when else "") + "\n"
            f"{p['pick_text']} {odds_str(p)} · {float(p.get('units') or 0) / 25:g}u\n"
            + (f"The sim: {sim}\n" if sim else "")
            + f"Logged {datetime.now(ET).strftime('%-I:%M %p ET')}. The public card stays sealed until {UNLOCK_WORD.get(p['sport'], 'tip')}.")


def x_caption(p):
    when = p.get("game_time") or ""
    return (f"SEALED · C{p.get('conf')} · {p.get('matchup')}" + (f" · {when}" if when else "") + "\n"
            f"Logged {datetime.now(ET).strftime('%-I:%M %p ET')}, before the game.\n"
            f"Members have it now → morellosims.com")


def voided_today(today):
    """NBA/MLB picks of the day the owner voided before tip: they come off the members page."""
    out = []
    for sport, path in pick_sources():
        for p in picks_store.load_picks(os.path.join(REPO, path)):
            if (p.get("sport") or sport) == sport and p.get("date") == today and p.get("status") == "void":
                p.setdefault("sport", sport)
                out.append(p)
    return out


def run(dry=False):
    if dry:
        ops_tg.DRY = True
    today = datetime.now(ET).strftime("%Y-%m-%d")
    st = load(STATE, {"dm": [], "x_sealed": [], "x_open": []})
    if PREMIUM:
        st.setdefault("premium", [])
    st.setdefault("site", [])
    st.setdefault("email", [])
    st.setdefault("email_to", [])
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
            if gated(p):
                button = [[("✅ Send to members", f"send:{ref}"), ("❌ Hold", f"hold:{ref}")]] + button
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
        ok_members = released(st, p)   # Jack's Send first (GATE_FROM on)
        if PREMIUM and readable and ok_members and not picks_store.ref_in(st["premium"], pid):
            ok = False
            try:
                ok = ops_tg.send_photo(card_path(p), premium_text(p), chat=PREMIUM)
            except (Exception, SystemExit) as e:
                print(f"  WARN member card {pid}: {e}")
            if not ok:
                ok = ops_tg.send(premium_text(p), chat=PREMIUM)
            if ok:
                st["premium"].append(ref)
        # the members page first, then the inbox: the email links to the page
        if readable and ok_members and member_delivery.enabled() and not picks_store.ref_in(st["site"], pid):
            try:
                if member_delivery.publish(p, picks_store.start_label(p), dry=dry):
                    st["site"].append(ref)
            except Exception as e:
                # Google's reason (role missing, API disabled, no database) and
                # never the record itself: Actions logs are public.
                print(f"  WARN member page {p.get('matchup')}: {type(e).__name__}: "
                      f"{getattr(e, 'message', '') or str(e).splitlines()[0][:160]}")
                if type(e).__name__ == "PermissionDenied":
                    who, proj = member_delivery.tg_members.identity()
                    print(f"  WARN member page: service account {who} (project {proj}) needs "
                          f"Cloud Datastore User on the Firestore project")
        # every member gets each pick once, including members who join after
        # it first went out, until the game starts (email_to: "ref|recipient")
        start = picks_store.start_time(p)
        live = start is None or datetime.now(timezone.utc) < start
        if readable and live and member_delivery.email_enabled() and picks_store.ref_in(st["site"], pid):
            try:
                had = [e.split("|", 1)[1] for e in st["email_to"] if e.split("|", 1)[0] == ref]
                sent = member_delivery.email(p, picks_store.start_label(p), dry=dry, skip=had)
                if sent is not None:
                    st["email_to"] += [f"{ref}|{k}" for k in sent]
                    if not picks_store.ref_in(st["email"], pid):
                        st["email"].append(ref)
            except Exception as e:
                print(f"  WARN member email {p.get('matchup')}: {type(e).__name__}")
        if not picks_store.ref_in(st["x_sealed"], pid) and not picks_store.ref_in(st["x_open"], pid):
            try:
                path = card_path(p, sealed=True)
                if post_to_x(x_caption(p), Path(path), dry_run=dry):
                    st["x_sealed"].append(ref)
            except Exception as e:
                print(f"  WARN sealed X post {pid}: {e}")
    # the owner changed a sent pick's stake before tip (ops/state/restake.json): the members
    # page takes the new stake and every member gets one stake-change email
    restakes = load(RESTAKE, [])
    for r in restakes:
        if r.get("done"):
            continue
        p = next((p for p in published_today(today) if picks_store.ref_matches(r["ref"], p["id"])), None)
        if p is None or picks_store.is_raw_sealed(p) or not released(st, p):
            continue
        start = picks_store.start_time(p)
        if start is not None and datetime.now(timezone.utc) >= start:
            r["done"] = "tipped before the change went out"
            continue
        note = f"Stake change: now {member_delivery._stake_txt(p)} (was {r['was']}). {r.get('why') or ''}".strip()
        try:
            if member_delivery.enabled():
                member_delivery.publish(p, picks_store.start_label(p), dry=dry)
            if member_delivery.email_enabled():
                member_delivery.email(p, picks_store.start_label(p), dry=dry, update=note)
            r["done"] = datetime.now(timezone.utc).isoformat()
            print(f"  members: stake change sent · {p.get('matchup')}")
        except Exception as e:
            print(f"  WARN stake change {p.get('matchup')}: {type(e).__name__}")
    if restakes and not dry:
        with open(RESTAKE, "w") as f:
            json.dump(restakes, f, indent=2)
    # a pick voided before tip comes off the members page
    for p in voided_today(today):
        if member_delivery.enabled() and picks_store.ref_in(st["site"], p["id"]):
            try:
                if member_delivery.retract(p, dry=dry):
                    st["site"] = [r for r in st["site"] if not picks_store.ref_in([r], p["id"])]
                    print(f"  members: {p.get('matchup')} voided, off the page")
            except Exception as e:
                print(f"  WARN member page retract {p.get('matchup')}: {type(e).__name__}")
    # members whose rules can't read member_picks get the picks on their own doc
    if member_delivery.enabled():
        try:
            fed, cleared = member_delivery.sync_feeds(dry=dry)
            if fed or cleared:
                print(f"  members: page feed updated for {fed}, cleared for {cleared}")
        except Exception as e:
            print(f"  WARN member feeds: {type(e).__name__}: "
                  f"{getattr(e, 'message', '') or str(e).splitlines()[0][:160]}")
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

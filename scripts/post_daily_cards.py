#!/usr/bin/env python3
"""Rolling Telegram card poster — runs on every pipeline cron.

Posts, in order, anything not yet posted (tracked in mlbsim/posted_cards.json,
committed by the workflow so state survives between Actions runs):
  1. settled cards for picks settled since the last run (the morning recap)
  2. the day's slate board (once, when the first pick qualifies) + GO-YARD
     ticket (once, if today's HR lotto audit is fresh)
  3. (per-pick alerts live in pick_alerts.py — one sender, sealed on X)

No TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID env → prints what it would do and
exits 0, so local runs and forks don't fail the workflow.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_cards_v2 as cards
import render_pick_card as render_series_card  # v3 layout (2026-09-30)
import render_series_sheets
from pathlib import Path

SERIES_OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "posters", "v2")


def series_card(p, settled):
    os.makedirs(SERIES_OUT, exist_ok=True)
    path = os.path.join(SERIES_OUT, f"series-{'settled-' if settled else ''}{p['id']}.png")
    render_series_card.render(p, settled).save(path)
    return path

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
STATE_FILE = os.path.join(REPO, "mlbsim", "posted_cards.json")
PICKS_JSON = os.path.join(REPO, "picks", "mlb.json")
HR_AUDIT = os.path.join(REPO, "mlbsim", "hr_lotto_audit.json")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
DRY = not (TOKEN and CHAT_ID)

ET = timezone(timedelta(hours=-4))
TODAY = datetime.now(ET).strftime("%Y-%m-%d")
NOW_ET = datetime.now(ET).strftime("%-I:%M %p ET")


def send_photo(path, caption):
    if DRY:
        print(f"  [dry] would send {os.path.basename(path)}: {caption.splitlines()[0]}")
        return True
    import urllib.request
    boundary = "----tgcard"
    with open(path, "rb") as f:
        img = f.read()
    body = b""
    for k, v in (("chat_id", CHAT_ID), ("caption", caption)):
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; "
             f"filename=\"card.png\"\r\nContent-Type: image/png\r\n\r\n").encode() + img + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendPhoto", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            ok = json.loads(r.read()).get("ok", False)
    except Exception as e:
        print(f"  WARN send failed for {os.path.basename(path)}: {e}")
        return False
    print(f"  sent {os.path.basename(path)}" if ok else f"  FAILED {os.path.basename(path)}")
    return ok


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"receipts": [], "settled": [], "slate_date": "", "goyard_date": ""}


def save_state(st):
    # keep the id lists from growing forever
    st["receipts"] = st["receipts"][-400:]
    st["settled"] = st["settled"][-400:]
    with open(STATE_FILE, "w") as f:
        json.dump(st, f, indent=2)


def fmt_units(pl):
    return f"+{pl:g}" if pl >= 0 else f"{pl:g}"


def main():
    if DRY:
        print("  (no Telegram env — dry run)")
    import picks_store  # owner DM (TELEGRAM_CHAT_ID): sealed picks open with the key
    picks = picks_store.load_picks(PICKS_JSON)
    st = load_state()
    cutoff = (datetime.now(ET) - timedelta(days=3)).strftime("%Y-%m-%d")

    # 1. freshly settled picks (last 3 days, not yet posted)
    settled = [p for p in picks
               if p.get("sport") == "mlb" and p["status"] in ("win", "loss")
               and p["date"] >= cutoff and int(p.get("conf") or 0) >= 8
               and p["id"] not in st["settled"]]
    for p in sorted(settled, key=lambda p: p["date"]):
        try:
            path = series_card(p, settled=True)
        except Exception as e:
            print(f"  WARN render settled {p['id']}: {e}")
            continue
        mark = "✅ WIN" if p["status"] == "win" else "🔴 LOSS"
        cap = (f"{mark} · {p['pick_text']} ({p['odds']}) — {p.get('result','')}\n"
               f"{fmt_units(p.get('pl') or 0)} $PP · settled in public, like always")
        if send_photo(path, cap):
            st["settled"].append(p["id"])

    # 2. today's board + go-yard, once, when the first pick exists
    today_pending = [p for p in picks
                     if p.get("sport") == "mlb" and p["date"] == TODAY
                     and p["status"] == "pending" and int(p.get("conf") or 0) >= 8]
    if today_pending and st.get("slate_date") != TODAY:
        try:
            os.makedirs(SERIES_OUT, exist_ok=True)
            path = os.path.join(SERIES_OUT, f"checklist-{TODAY}.png")
            render_series_sheets.checklist(TODAY).save(path)
            n = len(today_pending)
            if send_photo(path, f"📋 THE BOARD · {n} play{'s' if n != 1 else ''} today.\n"
                                f"Receipts drop here the moment lineups confirm."):
                st["slate_date"] = TODAY
        except SystemExit:
            pass
        except Exception as e:
            print(f"  WARN slate: {e}")
    if st.get("goyard_date") != TODAY and os.path.exists(HR_AUDIT):
        try:
            with open(HR_AUDIT) as f:
                audit = json.load(f)
            if (audit.get("generated") or "")[:10] == TODAY and audit.get("core"):
                path = cards.render_goyard()
                if send_photo(path, "💛 GO-YARD TICKET · today's HR lotto.\nGo yard or go home."):
                    st["goyard_date"] = TODAY
        except Exception as e:
            print(f"  WARN goyard: {e}")

    # 3. per-pick alerts (owner DM + sealed X card) moved to pick_alerts.py,
    #    dispatched after each pipeline publish so there is one sender.

    if DRY:
        print("  (dry run — state not saved)")
    else:
        save_state(st)
    print(f"  state: {len(st['receipts'])} receipts, {len(st['settled'])} settled, "
          f"slate={st.get('slate_date')}, goyard={st.get('goyard_date')}")


if __name__ == "__main__":
    main()

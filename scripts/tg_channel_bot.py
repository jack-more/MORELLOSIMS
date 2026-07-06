#!/usr/bin/env python3
"""@MorelloSimsBot — premium channel gatekeeper + publisher.

Designed to run stateless on a cron (no persistent server). Each run:
  1. drains getUpdates
  2. answers /start DMs with the pitch + checkout link
  3. approves channel join requests for active subscribers, declines others
     (with a DM pointing at checkout)
  4. kicks subscribers whose access expired

Channel setup (one-time, by hand — Telegram does not let bots create channels):
  1. Create a private channel (e.g. "Morello Sims Premium")
  2. Add @MorelloSimsBot as admin with "Invite Users via Link" +
     "Manage Join Requests" (and "Post Messages" for card publishing)
  3. Channel settings → create an invite link with "Request Admin Approval" ON
     — that link is what you sell / put behind checkout
  4. Forward any message from the channel to @userinfobot (or run this script
     with --discover after posting once) to get the channel id, then add
     TELEGRAM_PREMIUM_CHANNEL_ID=<id> to .env

Subscribers ledger: bankroll-grade honesty — a plain JSON file
(telegram/subscribers.json) mapping user_id -> {until, note}. Until Stripe or
Telegram Stars is wired into checkout, adding a subscriber is manual:
  python3 scripts/tg_channel_bot.py grant --user 12345 --days 30 --note "..."

Usage:
  python3 scripts/tg_channel_bot.py run        # process updates + expiries
  python3 scripts/tg_channel_bot.py post --photo <path> --caption "..."
  python3 scripts/tg_channel_bot.py grant --user <id> --days 30
  python3 scripts/tg_channel_bot.py revoke --user <id>
  python3 scripts/tg_channel_bot.py list
"""

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SUBS_FILE = os.path.join(REPO, "telegram", "subscribers.json")
STATE_FILE = os.path.join(REPO, "telegram", "bot_state.json")

CHECKOUT_URL = "https://morellosims.com/#packages"  # swap for Stripe/Stars link when live
PITCH = (
    "🌀 Morello Sims Premium\n\n"
    "Every C8+ pick, the GO-YARD home run lotto, and the full sim board — "
    "posted before first pitch, settled in public, tracked with closing lines.\n\n"
    f"Join here: {CHECKOUT_URL}\n\n"
    "Already a member? Request to join the channel and you'll be approved automatically."
)


def env(name):
    v = os.environ.get(name, "").strip()
    if v:
        return v
    envfile = os.path.join(REPO, ".env")
    if os.path.exists(envfile):
        for line in open(envfile):
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return ""


TOKEN = env("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = env("TELEGRAM_PREMIUM_CHANNEL_ID")


def api(method, **params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/{method}", data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def api_photo(chat_id, path, caption):
    boundary = "----tgb"
    with open(path, "rb") as f:
        img = f.read()
    body = b""
    for k, v in (("chat_id", str(chat_id)), ("caption", caption)):
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; "
             f"filename=\"card.png\"\r\nContent-Type: image/png\r\n\r\n").encode() + img + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendPhoto", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def is_active(subs, user_id):
    rec = subs.get(str(user_id))
    return bool(rec) and rec.get("until", "") >= datetime.now(timezone.utc).strftime("%Y-%m-%d")


def cmd_run():
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN missing")
    subs = load_json(SUBS_FILE, {})
    state = load_json(STATE_FILE, {"offset": 0})
    upd = api("getUpdates", offset=state["offset"], timeout=10)
    for u in upd.get("result", []):
        state["offset"] = u["update_id"] + 1
        msg = u.get("message") or {}
        jr = u.get("chat_join_request")
        if msg and msg.get("text", "").startswith("/start"):
            api("sendMessage", chat_id=msg["chat"]["id"], text=PITCH)
            print(f"  pitched {msg['chat'].get('first_name')} ({msg['chat']['id']})")
        elif jr and CHANNEL_ID and str(jr["chat"]["id"]) == str(CHANNEL_ID):
            uid = jr["from"]["id"]
            if is_active(subs, uid):
                api("approveChatJoinRequest", chat_id=CHANNEL_ID, user_id=uid)
                print(f"  approved subscriber {uid}")
            else:
                api("declineChatJoinRequest", chat_id=CHANNEL_ID, user_id=uid)
                try:
                    api("sendMessage", chat_id=uid,
                        text=f"Your Morello Sims Premium membership isn't active yet.\n{CHECKOUT_URL}")
                except Exception:
                    pass  # user never DM'd the bot; Telegram blocks cold DMs
                print(f"  declined non-subscriber {uid}")
    # expiries: kick lapsed members (ban+unban = remove without permanent ban)
    if CHANNEL_ID:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for uid, rec in list(subs.items()):
            if rec.get("until", "") < today and not rec.get("kicked"):
                try:
                    api("banChatMember", chat_id=CHANNEL_ID, user_id=uid)
                    api("unbanChatMember", chat_id=CHANNEL_ID, user_id=uid, only_if_banned=True)
                    rec["kicked"] = today
                    print(f"  expired + removed {uid}")
                except Exception as e:
                    print(f"  WARN could not remove {uid}: {e}")
    save_json(SUBS_FILE, subs)
    save_json(STATE_FILE, state)


def cmd_post(photo, caption):
    if not CHANNEL_ID:
        raise SystemExit("TELEGRAM_PREMIUM_CHANNEL_ID missing — create the channel first (see docstring)")
    r = api_photo(CHANNEL_ID, photo, caption)
    print("posted" if r.get("ok") else r)


def cmd_grant(user, days, note):
    subs = load_json(SUBS_FILE, {})
    until = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")
    subs[str(user)] = {"until": until, "note": note or "", "granted": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
    save_json(SUBS_FILE, subs)
    print(f"granted {user} until {until}")


def cmd_revoke(user):
    subs = load_json(SUBS_FILE, {})
    if str(user) in subs:
        subs[str(user)]["until"] = "1970-01-01"
        save_json(SUBS_FILE, subs)
        print(f"revoked {user} (will be removed on next run)")
    else:
        print("unknown user")


def cmd_list():
    subs = load_json(SUBS_FILE, {})
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for uid, rec in sorted(subs.items()):
        status = "ACTIVE" if rec.get("until", "") >= today else "expired"
        print(f"  {uid:>12} until {rec.get('until')} [{status}] {rec.get('note','')}")
    print(f"{sum(1 for r in subs.values() if r.get('until','') >= today)} active / {len(subs)} total")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "post", "grant", "revoke", "list"])
    ap.add_argument("--photo")
    ap.add_argument("--caption", default="")
    ap.add_argument("--user")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    if a.cmd == "run":
        cmd_run()
    elif a.cmd == "post":
        cmd_post(a.photo, a.caption)
    elif a.cmd == "grant":
        cmd_grant(a.user, a.days, a.note)
    elif a.cmd == "revoke":
        cmd_revoke(a.user)
    else:
        cmd_list()


if __name__ == "__main__":
    main()

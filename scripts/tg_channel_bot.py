#!/usr/bin/env python3
"""@MorelloSimsBot — members channel gatekeeper + publisher + owner console.

Runs stateless on a 15-minute cron (.github/workflows/tg-channel-bot.yml). Each run:
  1. drains getUpdates (messages, button taps, join requests, member joins)
  2. answers /start DMs with the pitch
  3. records who joined the members channel with which purchase (tg_members.py)
  4. removes anyone whose pass or comp has ended, and anyone who got in
     without one of our one-person links
  5. owner console, slip relay and pick alerts (picks post to the channel)

Getting in: a paid member taps "Join the members channel" on morellosims.com;
the telegramInvite Cloud Function checks their pass and mints a link that works
once, for one person, for one hour. Join requests are always declined.

Channel setup (one-time, by hand — Telegram does not let bots create channels):
  1. Create a private channel; Settings → turn on "Restrict saving content"
  2. Add @MorelloSimsBot as admin: Invite users via link, Ban users,
     Post messages, Pin messages, Delete messages
  3. The bot DMs the owner the channel id when it's made admin — save it as
     TELEGRAM_PREMIUM_CHANNEL_ID (GitHub secret + Firebase function secret)
  4. python3 scripts/tg_channel_bot.py post-rules   (posts + pins ops/telegram_rules.md)

Usage:
  python3 scripts/tg_channel_bot.py run
  python3 scripts/tg_channel_bot.py post --photo <path> --caption "..."
  python3 scripts/tg_channel_bot.py grant --user <telegram id> --days 30 --note "comp"
  python3 scripts/tg_channel_bot.py revoke --user <telegram id>
  python3 scripts/tg_channel_bot.py list
  python3 scripts/tg_channel_bot.py post-rules
"""

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
# telegram/ is gitignored (subscriber ids stay local); the update offset must
# persist between cron runs or every run replays the last 24h of updates.
STATE_FILE = os.path.join(REPO, "ops", "state", "bot_state.json")

CHECKOUT_URL = "https://morellosims.com/#plans"
PITCH = (
    "Morello Sims — members channel\n\n"
    "Every NBA pick posts here the moment the sim logs it, before tip. "
    "Every one is graded on the public ledger, wins and losses.\n\n"
    f"Get a pass: {CHECKOUT_URL}\n\n"
    "Already bought one? Sign in at morellosims.com, open your account and tap "
    "Join the members channel. Your link works once and only for you."
)
WELCOME = (
    "You're in. Picks post in the channel the moment they're logged, before tip.\n"
    "The rules are pinned at the top. Your access ends with your pass; renew any time at "
    + CHECKOUT_URL
)
ENDED = (
    "Your Morello Sims pass has ended, so you've been removed from the members channel.\n"
    f"Pick it back up any time: {CHECKOUT_URL}"
)
ALLOWED_UPDATES = json.dumps(["message", "callback_query", "chat_join_request", "chat_member", "my_chat_member"])


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
OWNER_ID = env("TELEGRAM_CHAT_ID")   # Jack's DM: the owner console
OWNER_HELP = (
    "Owner console\n"
    "/status — check-in now (slate, picks, pipelines, anything that needs you)\n"
    "/picks — today's picks in full\n"
    "Send a bet-slip screenshot — I'll pair it with the pick and post it to X with the card when you say.\n"
    "Pick alerts arrive here the moment a pick is published; the button under "
    "each one posts it to X unblurred (X gets the sealed card by default)."
)


def remove_member(user_id, dm=ENDED):
    """Remove without a permanent ban (ban + unban), then tell them why."""
    api("banChatMember", chat_id=CHANNEL_ID, user_id=user_id)
    api("unbanChatMember", chat_id=CHANNEL_ID, user_id=user_id, only_if_banned=True)
    if dm:
        try:
            api("sendMessage", chat_id=user_id, text=dm)
        except Exception:
            pass  # never DM'd the bot; Telegram blocks cold DMs


def invite_link(name, expire_ts):
    r = api("createChatInviteLink", chat_id=CHANNEL_ID, name=name[:32], member_limit=1, expire_date=expire_ts)
    return r["result"]["invite_link"]


def handle_member_update(cm):
    """chat_member: somebody joined or left the members channel."""
    import tg_members
    new, old = cm.get("new_chat_member", {}), cm.get("old_chat_member", {})
    if new.get("status") != "member" or old.get("status") not in ("left", "kicked"):
        return
    user = new["user"]
    if str(user["id"]) == str(OWNER_ID) or user.get("is_bot"):
        return
    name = (cm.get("invite_link") or {}).get("name", "")
    kind = tg_members.record_join(user, name) if tg_members.db() is not None else "unchecked"
    if kind in ("member", "comp"):
        print(f"  members: {user['id']} joined ({kind})")
        try:
            api("sendMessage", chat_id=user["id"], text=WELCOME)
        except Exception:
            pass
    elif kind is None:
        remove_member(user["id"], dm=PITCH)
        print(f"  members: removed {user['id']} — joined without a pass link")


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


def cmd_run():
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN missing")
    state = load_json(STATE_FILE, {"offset": 0})
    upd = api("getUpdates", offset=state["offset"], timeout=10, allowed_updates=ALLOWED_UPDATES)
    for u in upd.get("result", []):
        state["offset"] = u["update_id"] + 1
        msg = u.get("message") or {}
        jr = u.get("chat_join_request")
        cb = u.get("callback_query")
        cm = u.get("chat_member")
        mcm = u.get("my_chat_member")
        if mcm and OWNER_ID and mcm.get("new_chat_member", {}).get("status") == "administrator":
            # setup helper: the bot was made admin somewhere — tell the owner the chat id
            ch = mcm.get("chat", {})
            api("sendMessage", chat_id=OWNER_ID,
                text=f"I'm now an admin in \"{ch.get('title')}\". Its id is {ch.get('id')} — "
                     "save that as TELEGRAM_PREMIUM_CHANNEL_ID.")
            continue
        if cm and CHANNEL_ID and str(cm.get("chat", {}).get("id")) == str(CHANNEL_ID):
            try:
                handle_member_update(cm)
            except Exception as e:
                print(f"  WARN member update {u['update_id']}: {e}")
            continue
        if cb or (msg and OWNER_ID and str(msg.get("chat", {}).get("id")) == str(OWNER_ID)):
            try:
                handle_owner(msg, cb)
            except Exception as e:  # one bad update must not stop the run or lose the offset
                print(f"  WARN owner update {u['update_id']}: {e}")
            continue
        if msg and msg.get("text", "").startswith("/start"):
            api("sendMessage", chat_id=msg["chat"]["id"], text=PITCH)
            print(f"  pitched {msg['chat'].get('first_name')} ({msg['chat']['id']})")
        elif jr and CHANNEL_ID and str(jr["chat"]["id"]) == str(CHANNEL_ID):
            # members join with their own one-person link, never by request
            uid = jr["from"]["id"]
            api("declineChatJoinRequest", chat_id=CHANNEL_ID, user_id=uid)
            try:
                api("sendMessage", chat_id=uid, text=PITCH)
            except Exception:
                pass  # user never DM'd the bot; Telegram blocks cold DMs
            print(f"  declined join request {uid}")
    # confirm processed updates server-side too, so nothing can replay
    if upd.get("result"):
        api("getUpdates", offset=state["offset"], timeout=0)
        save_json(STATE_FILE, state)
    # slips held for first pitch, and result follow-ups for posted slips
    try:
        import slips
        slips.tick()
    except Exception as e:
        print(f"  WARN slips: {e}")
    # new picks → owner DM + sealed X card (exactly once, see pick_alerts.py)
    try:
        import pick_alerts
        pick_alerts.run()
    except Exception as e:
        print(f"  WARN pick alerts: {e}")
    # expiries: remove members whose pass or comp has ended
    if CHANNEL_ID:
        import tg_members
        tg_members.sweep(remove_member)
    save_json(STATE_FILE, state)


def ack(cb, text):
    """Best effort: Telegram rejects answers to taps older than ~15s, and the
    bot runs on a cron, so a late tap just gets its result as a DM instead."""
    try:
        api("answerCallbackQuery", callback_query_id=cb["id"], text=text[:190])
    except Exception:
        pass


def handle_owner(msg, cb):
    """Owner DM commands and button taps. Taps from anyone else are ignored."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ops_digest
    import pick_alerts
    if cb:
        if str(cb.get("from", {}).get("id")) != str(OWNER_ID):
            ack(cb, "Not available")
            return
        data = cb.get("data", "")
        note = "ok"
        if data.startswith("slip:"):
            import slips
            note = slips.handle(data)
            api("sendMessage", chat_id=OWNER_ID, text=f"Slip: {note}")
        elif data.startswith("xopen:"):
            note = pick_alerts.open_on_x(data.split(":", 1)[1])
            api("sendMessage", chat_id=OWNER_ID, text=f"X: {note} ({data.split(':', 1)[1]})")
        elif data == "status":
            ops_digest.digest("Check-in")
        elif data == "picks":
            lines = ops_digest.picks_block(datetime.now(ops_digest.ET).strftime("%Y-%m-%d"))
            api("sendMessage", chat_id=OWNER_ID, text="\n".join(lines) or "No C8+ picks yet today.")
        ack(cb, note)
        return
    if msg.get("photo"):
        import slips
        slips.receive(msg)
        return
    text = (msg.get("text") or "").strip().lower()
    if text.startswith("/status"):
        ops_digest.digest("Check-in")
    elif text.startswith("/picks"):
        lines = ops_digest.picks_block(datetime.now(ops_digest.ET).strftime("%Y-%m-%d"))
        api("sendMessage", chat_id=OWNER_ID, text="\n".join(lines) or "No C8+ picks yet today.")
    else:
        api("sendMessage", chat_id=OWNER_ID, text=OWNER_HELP)


def cmd_post(photo, caption):
    if not CHANNEL_ID:
        raise SystemExit("TELEGRAM_PREMIUM_CHANNEL_ID missing — create the channel first (see docstring)")
    r = api_photo(CHANNEL_ID, photo, caption)
    print("posted" if r.get("ok") else r)


def cmd_grant(user, days, note):
    """Comp a Telegram user id; the one-person link goes to the owner's DM."""
    import tg_members
    link, until = tg_members.grant(user, days, note, invite_link)
    msg = f"Comp for {user} until {until:%b %d %H:%M} UTC ({note or 'no note'}). Their link (one use, 24h): {link}"
    if OWNER_ID:
        api("sendMessage", chat_id=OWNER_ID, text=msg)
    print("comp granted — link sent to the owner DM")


def cmd_revoke(user):
    import tg_members
    tg_members.revoke(user)
    print(f"revoked {user} (removed on the next run)")


def cmd_list():
    import tg_members
    if tg_members.db() is None:
        raise SystemExit("FIREBASE_SERVICE_ACCOUNT missing")
    for row in tg_members.listing():
        print(row)


def cmd_post_rules():
    """Post the membership rules (ops/telegram_rules.md) to the channel and pin them."""
    path = os.path.join(REPO, "ops", "telegram_rules.md")
    text = open(path).read().strip()
    r = api("sendMessage", chat_id=CHANNEL_ID, text=text, disable_web_page_preview=True)
    api("pinChatMessage", chat_id=CHANNEL_ID, message_id=r["result"]["message_id"], disable_notification=True)
    print("rules posted and pinned")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "post", "grant", "revoke", "list", "post-rules"])
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
    elif a.cmd == "post-rules":
        cmd_post_rules()
    else:
        cmd_list()


if __name__ == "__main__":
    main()

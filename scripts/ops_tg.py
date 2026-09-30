"""Owner console over Telegram: @MorelloSimsBot → Jack's DM (TELEGRAM_CHAT_ID).

Every automated job reports here, so the system runs on its own and the
owner steps in only when a message asks for it. Buttons are Telegram
inline-keyboard callbacks; tg_channel_bot.py (15-min cron) handles the taps.

No token/chat in env → prints what it would send (dry run), never raises.
"""

import json
import os
import urllib.request

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
OWNER = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
DRY = not (TOKEN and OWNER)


def _kb(buttons):
    """[[("label", "callback_data"), ...], ...] → reply_markup JSON."""
    if not buttons:
        return None
    return json.dumps({"inline_keyboard": [
        [{"text": t, "callback_data": c[:64]} for t, c in row] for row in buttons]})


def api(method, **params):
    if DRY:
        return {"ok": True, "dry": True}
    data = json.dumps({k: v for k, v in params.items() if v is not None}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/{method}", data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  WARN telegram {method}: {e}")
        return {"ok": False}


def send(text, buttons=None, chat=None):
    if DRY:
        print(f"  [dry] DM: {text.splitlines()[0]}" + (f"  buttons={buttons}" if buttons else ""))
        return True
    markup = _kb(buttons)
    return api("sendMessage", chat_id=chat or OWNER, text=text[:4000],
               disable_web_page_preview=True,
               reply_markup=json.loads(markup) if markup else None).get("ok", False)


def send_photo(path, caption, buttons=None, chat=None):
    if DRY:
        print(f"  [dry] DM photo {os.path.basename(path)}: {caption.splitlines()[0]}"
              + (f"  buttons={buttons}" if buttons else ""))
        return True
    boundary = "----opstg"
    fields = [("chat_id", str(chat or OWNER)), ("caption", caption[:1000])]
    markup = _kb(buttons)
    if markup:
        fields.append(("reply_markup", markup))
    body = b""
    for k, v in fields:
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    with open(path, "rb") as f:
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"card.png\"\r\n"
                 f"Content-Type: image/png\r\n\r\n").encode() + f.read() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendPhoto", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()).get("ok", False)
    except Exception as e:
        print(f"  WARN telegram sendPhoto: {e}")
        return False

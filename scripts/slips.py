"""Real-slip relay: Jack sends a bet-slip screenshot to @MorelloSimsBot, the
bot pairs it with the pick and, on his tap, posts slip + card to X.

Owner direction (2026-10-01): copy the trust model of sportsbook-synced
brands (Pikkit / Juice Reel: real slips, wins AND losses permanent) — not a
win-only feed. So a slip is posted for whichever result, and the caption
always points at the full public ledger.

Flow (all in Jack's DM, handled by the 15-min bot cron):
  photo in → matched to today's/yesterday's pick (caption words or the only
  candidate; otherwise buttons to choose) → buttons:
     📣 Post now          — slip + revealed card (reveals the pick)
     ⏳ At first pitch    — held; posted when the game starts = the unseal
     ✖ Don't post
  after a pick settles, a slip posted for it gets the result card + "WHO TAILED?"

Privacy: the screenshot is never committed to the (public) repo — only the
Telegram file_id is kept in ops/state/slips.json. X shows the image as sent,
so Jack is reminded to crop balance/username.
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ops_tg  # noqa: E402
import pick_alerts  # noqa: E402
import picks_store  # noqa: E402

REPO = os.path.dirname(HERE)
STATE = os.path.join(REPO, "ops", "state", "slips.json")
ET = timezone(timedelta(hours=-4))
TMP = "/tmp/morello_slips"


def _load():
    return pick_alerts.load(STATE, {"slips": {}})


def _save(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(st, f, indent=2)


def _all_picks():
    out = []
    import picks_store  # seal mode: sealed picks open with PICKS_SEAL_KEY
    for sport, path in (("mlb", "picks/mlb.json"), ("nba", "picks/nba.json")):
        for p in picks_store.load_picks(os.path.join(REPO, path)):
            p.setdefault("sport", sport)
            out.append(p)
    return out


def _candidates():
    now = datetime.now(ET)
    days = {now.strftime("%Y-%m-%d"), (now - timedelta(days=1)).strftime("%Y-%m-%d")}
    return [p for p in _all_picks() if p.get("date") in days and int(p.get("conf") or 0) >= 8]


def _match(caption, cands):
    if len(cands) == 1:
        return cands
    words = set(re.findall(r"[a-z]+", (caption or "").lower()))
    hit = [p for p in cands if {p.get("side", "").lower(), p.get("away", "").lower(), p.get("home", "").lower()} & words]
    return hit or cands


def _start(p):
    """First pitch / tip in ET from 'date' + 'game_time' ('7:15 PM ET'), else None."""
    gt = (p.get("game_time") or "").replace(" ET", "").strip()
    try:
        return datetime.strptime(f"{p['date']} {gt}", "%Y-%m-%d %I:%M %p").replace(tzinfo=ET)
    except ValueError:
        return None


def _buttons(key, p):
    row = [("📣 Post now", f"slip:now:{key}")]
    st = _start(p)
    if p.get("status") == "pending" and st and st > datetime.now(ET):
        row.append(("⏳ At first pitch", f"slip:pitch:{key}"))
    row.append(("✖ Don't post", f"slip:skip:{key}"))
    return [row]


def receive(msg):
    """Owner sent a photo."""
    photos = msg.get("photo") or []
    if not photos:
        return
    key = str(msg["message_id"])
    st = _load()
    # ops/state is committed publicly: under seal mode the caption (Jack's
    # words, may name the side) is not kept and NBA pick ids are hashed.
    caption = "" if picks_store.seal_mode() else (msg.get("caption") or "")
    st["slips"][key] = {"file_id": photos[-1]["file_id"], "caption": caption,
                        "received": datetime.now(ET).isoformat(), "pick_id": None, "status": "new"}
    cands = _match(msg.get("caption"), _candidates())
    if not cands:
        ops_tg.send("Got the slip, but there's no C8+ pick today or yesterday to pair it with.")
        st["slips"][key]["status"] = "unmatched"
    elif len(cands) == 1:
        p = cands[0]
        st["slips"][key]["pick_id"] = picks_store.state_ref(p["id"])
        ops_tg.send(f"Slip for {p['pick_text']} {pick_alerts.odds_str(p)} · {p.get('matchup')} "
                    f"{p.get('game_time') or ''} [{p.get('status')}].\n"
                    "Post it to X with the card? (X shows the screenshot as sent — crop balance/username.)",
                    _buttons(key, p))
    else:
        ops_tg.send("Which pick is this slip for?",
                    [[(f"{p['pick_text']} · {p.get('matchup')}", f"slip:pick:{key}:{i}")] for i, p in enumerate(cands[:6])])
        st["slips"][key]["choices"] = [picks_store.state_ref(p["id"]) for p in cands[:6]]
    _save(st)


def handle(data):
    """Button tap 'slip:<action>:<key>[:<i>]'. Returns a short note."""
    parts = data.split(":")
    action, key = parts[1], parts[2]
    st = _load()
    s = st["slips"].get(key)
    if not s:
        return "slip not found"
    if action == "pick":
        s["pick_id"] = s.get("choices", [])[int(parts[3])]
        p = _pick(s["pick_id"])
        _save(st)
        ops_tg.send(f"Slip for {p['pick_text']} · {p.get('matchup')}. Post it?", _buttons(key, p))
        return "paired"
    if action == "skip":
        s["status"] = "skipped"
        _save(st)
        return "won't post"
    if action == "pitch":
        p = _pick(s["pick_id"])
        s["status"], s["post_after"] = "scheduled", _start(p).isoformat()
        _save(st)
        return f"posts at first pitch ({p.get('game_time')})"
    if action == "now":
        note = _post(s)
        _save(st)
        return note
    return "?"


def _pick(pid):
    return next(p for p in _all_picks() if picks_store.ref_matches(pid, p["id"]))


def _download(file_id):
    info = ops_tg.api("getFile", file_id=file_id)
    path = (info.get("result") or {}).get("file_path")
    if not path:
        raise RuntimeError("telegram getFile failed")
    os.makedirs(TMP, exist_ok=True)
    out = os.path.join(TMP, os.path.basename(path))
    urllib.request.urlretrieve(f"https://api.telegram.org/file/bot{ops_tg.TOKEN}/{path}", out)
    return out


def _caption(p):
    logged = None
    try:
        import render_pick_card
        logged = render_pick_card._logged(p)
    except Exception:
        pass
    stamp = f"Logged {logged}, before the game." if logged else "Logged before the game."
    st = p.get("status")
    try:  # stored result: MLB away-home, NBA home-away (both verified against the leagues' finals)
        x, y = str(p.get("result")).split("-")
        a_pts, h_pts = (y, x) if p.get("sport") == "nba" else (x, y)
        final = f"{p['away']} {a_pts} – {p['home']} {h_pts}"
    except ValueError:
        final = str(p.get("result") or "")
    if st == "win":
        head = f"✅ CASHED · {p['pick_text']} {pick_alerts.odds_str(p)} · {final}"
        tail = "WHO TAILED? Every pick, wins and losses → morellosims.com"
    elif st == "loss":
        head = f"❌ {p['pick_text']} {pick_alerts.odds_str(p)} · {final}"
        tail = "Losses stay on the ledger too → morellosims.com"
    else:
        head = f"{p['pick_text']} {pick_alerts.odds_str(p)} · C{p.get('conf')} · {p.get('matchup')}"
        tail = "My slip. Every pick, wins and losses → morellosims.com"
    return f"{head}\n{stamp}\n{tail}"


def _post(s, dry=False):
    from post_social_daily import post_to_x
    p = _pick(s["pick_id"])
    try:
        slip = _download(s["file_id"])
    except Exception as e:
        return f"couldn't fetch the slip: {e}"
    nba = p["sport"] == "nba"
    mod = __import__("render_nba_card" if nba else "render_pick_card")
    settled = p.get("status") in ("win", "loss", "push")
    os.makedirs(TMP, exist_ok=True)
    card = os.path.join(TMP, f"card-{p['id']}.png")
    mod.render(p, settled).save(card)
    ok = post_to_x(_caption(p), [Path(slip), Path(card)], dry_run=dry)
    if ok:
        s["status"], s["posted_at"] = "posted", datetime.now(ET).isoformat()
        s["posted_settled"] = settled
        ast = pick_alerts.load(pick_alerts.STATE, {"dm": [], "x_sealed": [], "x_open": []})
        if not picks_store.ref_in(ast["x_open"], p["id"]):
            ast["x_open"].append(picks_store.state_ref(p["id"]))
            with open(pick_alerts.STATE, "w") as f:
                json.dump(ast, f, indent=2)
        return "posted to X"
    return "X post failed (are the X secrets set?)"


def tick(dry=False):
    """Post slips scheduled for first pitch; follow up settled ones with the result."""
    st = _load()
    now = datetime.now(ET)
    changed = False
    for key, s in st["slips"].items():
        if s.get("status") == "scheduled" and s.get("post_after") and datetime.fromisoformat(s["post_after"]) <= now:
            note = _post(s, dry)
            ops_tg.send(f"⏰ First pitch: slip for {s['pick_id']} — {note}")
            changed = True
        elif s.get("status") == "posted" and not s.get("posted_settled") and not s.get("result_posted"):
            p = _pick(s["pick_id"])
            if p.get("status") in ("win", "loss", "push"):
                from post_social_daily import post_to_x
                mod = __import__("render_nba_card" if p["sport"] == "nba" else "render_pick_card")
                card = os.path.join(TMP, f"result-{p['id']}.png")
                os.makedirs(TMP, exist_ok=True)
                mod.render(p, True).save(card)
                if post_to_x(_caption(p), Path(card), dry_run=dry):
                    s["result_posted"] = now.isoformat()
                    changed = True
    if changed and not dry:
        _save(st)

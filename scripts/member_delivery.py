#!/usr/bin/env python3
"""Member delivery: every new pick to the members page and to members' inboxes.

The paid product. pick_alerts.py calls this once per new pick (its state file
keeps each step exactly-once):

  publish(p)  writes the full pick to Firestore member_picks/{doc}. The
              Firestore rules let only a signed-in account with an active
              pass read it; /members/ on the site lists tonight's picks.
  email(p)    sends the pick to every active member through Resend
              (RESEND_API_KEY; from MEMBER_EMAIL_FROM, on a domain verified
              in Resend). One message per member, so no one sees another
              member's address.

Active = the same rule as hasActiveAccess in functions/index.js and
tg_members.pass_active: admin, an unexpired accessExpiresAt, or a live
recurring subscription. Addresses come from Firebase Auth (the users doc is
written by the Stripe webhook, which doesn't store one).

Plus the whitelist, which that rule never saw: the site grants admin / FnF
from EMAIL_WHITELIST in morello-auth.js (in the browser, nothing is written
to Firestore), onUserCreate grants FnF from the fnf_whitelist collection, and
tier "fnf" itself isn't one hasActiveAccess counts.

Nothing here prints the side: Actions logs are public.
"""

import hashlib
import hmac
import os
import re
from datetime import datetime, timedelta, timezone

import tg_members

ET = timezone(timedelta(hours=-4))
RESEND_URL = "https://api.resend.com/emails/batch"
RESEND_ONE = "https://api.resend.com/emails"      # single sends carry the note as an inline image
NOTE_CID = "pick-note"
FROM = os.environ.get("MEMBER_EMAIL_FROM", "").strip() or "Morello Sims <picks@morellosims.com>"
MEMBERS_URL = "https://morellosims.com/members/"
UNLOCK_WORD = {"nba": "tip", "nfl": "kickoff"}


def enabled():
    return tg_members.db() is not None


# the owner's hold: while this file exists no member email goes out (the page still updates)
HOLD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ops", "HOLD_MEMBER_EMAIL")


def email_enabled():
    if os.path.exists(HOLD):
        print("  members: email on hold (ops/HOLD_MEMBER_EMAIL)")
        return False
    return enabled() and bool(os.environ.get("RESEND_API_KEY", "").strip())


AUTH_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "morello-auth.js")
WHITELIST_TIERS = ("admin", "fnf")


def site_whitelist():
    """Emails EMAIL_WHITELIST in morello-auth.js grants a member tier."""
    try:
        src = open(AUTH_JS, encoding="utf-8").read()
    except OSError:
        return set()
    m = re.search(r"EMAIL_WHITELIST\s*=\s*\{(.*?)\}", src, re.S)
    if not m:
        return set()
    return {e.lower() for e, tier in re.findall(r"'([^']+@[^']+)'\s*:\s*'([^']+)'", m.group(1))
            if tier in WHITELIST_TIERS}


def recipient_key(addr):
    """Short keyed hash of an address for the committed state file (the repo
    is public): records who already has a pick without naming them."""
    salt = os.environ.get("PICKS_SEAL_KEY", "").encode() or b"morello"
    return hmac.new(salt, addr.lower().encode(), hashlib.sha256).hexdigest()[:12]


def doc_id(pick_id):
    """Firestore doc name: a hash, since NBA pick ids end with the side."""
    return hashlib.sha256(str(pick_id).encode()).hexdigest()[:24]


def _u(p):
    return round(float(p.get("units") or 0) / 25, 2)   # $PP stake -> units (25 $PP = 1u)


def _odds(p):
    o = str(p.get("odds") or "")
    return o if not o or o.startswith(("+", "-")) else f"+{o}"


def publish(p, when_label, dry=False):
    """The full pick, readable by active members only. True when stored."""
    rec = {
        "sport": p.get("sport"), "date": p.get("date"), "matchup": p.get("matchup"),
        "away": p.get("away"), "home": p.get("home"), "bet_type": p.get("bet_type"),
        "pick_text": p.get("pick_text"), "odds": _odds(p), "units": _u(p),
        "conf": p.get("conf"), "sim_projection": p.get("sim_projection"),
        "game_time": when_label, "start": p.get("start") or p.get("tip_at"),
        "captured_at": p.get("captured_at"),
    }
    if dry:
        print(f"  [dry] member page: {p.get('matchup')} ({p.get('date')})")
        return True
    from firebase_admin import firestore
    rec["logged_at"] = firestore.SERVER_TIMESTAMP
    tg_members.db().collection("member_picks").document(doc_id(p["id"])).set(rec, merge=True)
    return True


def active_emails():
    """Addresses of every account with an active pass."""
    return sorted(active_members())


def active_members():
    """{address: uid or None} for every account with an active pass, plus the
    whitelist (uid None when the address has no users doc yet)."""
    d = tg_members.db()
    now = datetime.now(timezone.utc)
    docs = {}
    for q in (d.collection("users").where("accessExpiresAt", ">", now),
              d.collection("users").where("tier", "==", "admin"),
              d.collection("users").where("checkoutMode", "==", "subscription")):
        for snap in q.stream():
            docs[snap.id] = snap.to_dict()
    for snap in d.collection("users").where("tier", "==", "fnf").stream():
        docs[snap.id] = snap.to_dict()
    uids = [uid for uid, u in docs.items()
            if tg_members.pass_active(u) or u.get("tier") in WHITELIST_TIERS]
    from firebase_admin import auth
    out = {}
    try:
        for i in range(0, len(uids), 100):
            res = auth.get_users([auth.UidIdentifier(u) for u in uids[i:i + 100]])
            for user in res.users:
                if user.email and not user.disabled:
                    out[user.email.lower()] = user.uid
    except auth.InsufficientPermissionError:
        # the Actions service account has Firestore rights but no Firebase Auth
        # role: the users doc's email (written by onUserCreate) stands in
        print("  members: no Firebase Auth access, addresses from users docs")
    for uid in uids:                                     # fall back to the users doc
        e = (docs[uid].get("email") or "").lower()
        if e and e not in out:
            out[e] = uid
    for e in site_whitelist():
        out.setdefault(e, None)
    for snap in d.collection("fnf_whitelist").stream():
        if "@" in snap.id:
            out.setdefault(snap.id.lower(), None)
    return out


FEED_DAYS = 2   # tonight and last night, the same window /members/ shows


def sync_feeds(dry=False):
    """Copy tonight's and last night's member_picks onto each active member's
    own users doc (member_feed), and take it off everyone else's.

    /members/ reads member_picks directly where the live Firestore rules allow
    it. Where they don't (the deployed ruleset predates the member_picks rule),
    the page reads the member's own users doc instead, which every ruleset lets
    its owner read. Runs on every bot pass, so someone who buys after a pick
    went out has it within one run. Returns (members fed, feeds cleared)."""
    d = tg_members.db()
    if d is None:
        return (0, 0)
    from firebase_admin import auth, firestore
    since = (datetime.now(ET) - timedelta(days=FEED_DAYS - 1)).strftime("%Y-%m-%d")
    feed = [s.to_dict() for s in d.collection("member_picks").where("date", ">=", since).stream()]
    feed.sort(key=lambda r: (str(r.get("date") or ""), str(r.get("logged_at") or "")))
    key = hashlib.sha256(repr(feed).encode()).hexdigest()[:16]
    uids, listed, found = set(), 0, 0
    for addr, uid in active_members().items():
        if uid is not None:
            uids.add(uid)
            continue
        # whitelisted: Firebase Auth knows the account; without an Auth role,
        # fall back to the email onUserCreate stored on the users doc
        listed += 1
        try:
            hits = [auth.get_user_by_email(addr).uid]
        except auth.UserNotFoundError:
            hits = []                                     # never signed up
        except auth.InsufficientPermissionError:
            hits = [s.id for s in d.collection("users").where("email", "in", list({addr, addr.lower()})).stream()]
        found += bool(hits)
        uids.update(hits)
    print(f"  members: page feed has {len(feed)} pick(s) for {len(uids)} account(s); "
          f"{found} of {listed} whitelisted address(es) have an account")
    if dry:
        print(f"  [dry] member feeds: {len(feed)} pick(s) for {len(uids)} member(s)")
        return (len(uids), 0)
    fed = 0
    for uid in uids:
        ref = d.collection("users").document(uid)
        snap = ref.get()
        if snap.exists and (snap.to_dict() or {}).get("member_feed_key") == key:
            continue
        ref.set({"member_feed": feed, "member_feed_key": key,
                 "member_feed_at": firestore.SERVER_TIMESTAMP}, merge=True)
        fed += 1
    cleared = 0
    epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)
    for snap in d.collection("users").where("member_feed_at", ">", epoch).stream():
        if snap.id not in uids:
            snap.reference.update({"member_feed": firestore.DELETE_FIELD,
                                   "member_feed_key": firestore.DELETE_FIELD,
                                   "member_feed_at": firestore.DELETE_FIELD})
            cleared += 1
    return (fed, cleared)


def note_png(p, when_label):
    """The pick's note (render_pick_note.py) as PNG bytes, or None (no Chrome, not a spread...)."""
    import tempfile
    try:
        import render_pick_note
        with tempfile.TemporaryDirectory() as d:
            out = render_pick_note.render(p, os.path.join(d, "note.png"), when_label=when_label)
            return open(out, "rb").read() if out else None
    except Exception as e:                       # the email goes out without the card
        print(f"  WARN pick note not rendered: {type(e).__name__}")
        return None


def message(p, when_label, with_note=False):
    sport = (p.get("sport") or "nba").upper()
    sim = p.get("sim_projection")
    subject = f"{sport} pick · {p.get('matchup')}" + (f" · {when_label}" if when_label else "")
    logged = datetime.now(ET).strftime("%-I:%M %p ET")
    lines = [f"{p.get('pick_text')} {_odds(p)}", f"{p.get('matchup')}" + (f" · {when_label}" if when_label else ""),
             f"{_u(p):g}u · confidence {p.get('conf')}/10"]
    if sim:
        lines.append(f"The sim: {sim}")
    lines.append(f"Logged {logged}. The public card stays sealed until {UNLOCK_WORD.get(p.get('sport'), 'tip')}.")
    text = "\n".join(lines) + f"\n\nTonight's picks: {MEMBERS_URL}\nEvery pick, graded: https://morellosims.com/ledger/nba/\n"
    note = (f'<img src="cid:{NOTE_CID}" width="520" alt="{p.get("pick_text")} {_odds(p)}, confidence {p.get("conf")}" '
            'style="display:block;width:100%;max-width:520px;height:auto;border:0;border-radius:18px;margin:0 0 20px">') if with_note else ""
    html = (
        '<div style="font-family:Georgia,serif;max-width:520px;margin:0 auto;padding:24px;color:#10202E">'
        + note +
        f'<div style="font:600 12px/1.4 Arial,sans-serif;letter-spacing:.12em;color:#5E6B66">MORELLO SIMS · {sport} · MEMBERS</div>'
        f'<div style="font-size:30px;font-weight:700;margin:14px 0 4px">{p.get("pick_text")} {_odds(p)}</div>'
        f'<div style="font-size:16px">{p.get("matchup")}' + (f' · {when_label}' if when_label else '') + '</div>'
        f'<div style="font:15px/1.6 Arial,sans-serif;margin-top:12px">{_u(p):g}u · confidence {p.get("conf")}/10'
        + (f'<br>The sim: {sim}' if sim else '') + f'<br>Logged {logged}.</div>'
        f'<a href="{MEMBERS_URL}" style="display:inline-block;margin-top:20px;background:#14743C;color:#fff;'
        'padding:12px 20px;text-decoration:none;font:600 15px Arial,sans-serif">Open tonight\'s picks</a>'
        '<div style="font:12px/1.5 Arial,sans-serif;color:#5E6B66;margin-top:24px">Every pick is graded in public at '
        '<a href="https://morellosims.com/ledger/nba/" style="color:#5E6B66">morellosims.com/ledger</a>. '
        'Simulations, not guarantees. 21+. 1-800-GAMBLER.</div></div>')
    return subject, text, html


def send_with_note(p, when_label, to, png, key):
    """One email per member with the note inline (cid). Returns the addresses Resend
    refused (all of them if it refuses the first), for the text batch to cover."""
    import base64
    import time
    import requests
    subject, text, html = message(p, when_label, with_note=True)
    att = [{"filename": f"{doc_id(p['id'])}.png", "content": base64.b64encode(png).decode(),
            "content_type": "image/png", "content_id": NOTE_CID}]
    failed = []
    for n, addr in enumerate(to):
        r = requests.post(RESEND_ONE, json={"from": FROM, "to": [addr], "subject": subject, "text": text,
                                            "html": html, "attachments": att}, timeout=30,
                          headers={"Authorization": f"Bearer {key}",
                                   "Idempotency-Key": f"{doc_id(p['id'])}-note-{hashlib.sha256(recipient_key(addr).encode()).hexdigest()[:16]}"})
        if r.status_code >= 300:
            print(f"  WARN member email with note: HTTP {r.status_code} {r.text[:200]}")
            if n == 0:
                return list(to)
            failed.append(addr)
        time.sleep(0.6)                          # Resend's default limit is 2 requests a second
    return failed


def email(p, when_label, dry=False, skip=()):
    """Send the pick to every active member not in `skip` (recipient_key
    values). Returns the keys of the members it went to, or None when a batch
    was refused."""
    to = [a for a in active_emails() if recipient_key(a) not in set(skip)] if not dry else []
    if dry:
        print(f"  [dry] member email: {p.get('matchup')} ({p.get('date')})")
        return []
    if not to:
        print(f"  members: nobody new to email · {p.get('matchup')}")
        return []
    import requests
    key = os.environ["RESEND_API_KEY"].strip()
    png = note_png(p, when_label)
    everyone = list(to)
    if png:
        to = send_with_note(p, when_label, to, png, key)
        print(f"  members: emailed {len(everyone) - len(to)} member(s) with the note · {p.get('matchup')}")
        if not to:
            return [recipient_key(a) for a in everyone]
    subject, text, html = message(p, when_label)
    ok = True
    for i in range(0, len(to), 100):
        batch = [{"from": FROM, "to": [addr], "subject": subject, "text": text, "html": html} for addr in to[i:i + 100]]
        chunk = "".join(sorted(recipient_key(a) for a in to[i:i + 100]))
        r = requests.post(RESEND_URL, json=batch, timeout=30,
                          headers={"Authorization": f"Bearer {key}",
                                   "Idempotency-Key": f"{doc_id(p['id'])}-{hashlib.sha256(chunk.encode()).hexdigest()[:16]}"})
        if r.status_code >= 300:
            print(f"  WARN member email batch {i // 100}: HTTP {r.status_code} {r.text[:200]}")
            ok = False
    print(f"  members: emailed {len(to)} member(s) · {p.get('matchup')}")
    return [recipient_key(a) for a in everyone] if ok else None

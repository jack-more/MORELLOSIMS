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

Nothing here prints the side: Actions logs are public.
"""

import hashlib
import os
from datetime import datetime, timedelta, timezone

import tg_members

ET = timezone(timedelta(hours=-4))
RESEND_URL = "https://api.resend.com/emails/batch"
FROM = os.environ.get("MEMBER_EMAIL_FROM", "").strip() or "Morello Sims <picks@morellosims.com>"
MEMBERS_URL = "https://morellosims.com/members/"
UNLOCK_WORD = {"nba": "tip", "nfl": "kickoff"}


def enabled():
    return tg_members.db() is not None


def email_enabled():
    return enabled() and bool(os.environ.get("RESEND_API_KEY", "").strip())


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
    d = tg_members.db()
    now = datetime.now(timezone.utc)
    docs = {}
    for q in (d.collection("users").where("accessExpiresAt", ">", now),
              d.collection("users").where("tier", "==", "admin"),
              d.collection("users").where("checkoutMode", "==", "subscription")):
        for snap in q.stream():
            docs[snap.id] = snap.to_dict()
    uids = [uid for uid, u in docs.items() if tg_members.pass_active(u)]
    from firebase_admin import auth
    out = {}
    for i in range(0, len(uids), 100):
        res = auth.get_users([auth.UidIdentifier(u) for u in uids[i:i + 100]])
        for user in res.users:
            if user.email and not user.disabled:
                out[user.email.lower()] = user.uid
    for uid in uids:                                     # fall back to the users doc
        e = (docs[uid].get("email") or "").lower()
        if e and e not in out:
            out[e] = uid
    return sorted(out)


def message(p, when_label):
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
    html = (
        '<div style="font-family:Georgia,serif;max-width:520px;margin:0 auto;padding:24px;color:#10202E">'
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


def email(p, when_label, dry=False):
    """Send the pick to every active member. True when every batch was accepted."""
    to = active_emails() if not dry else []
    if dry:
        print(f"  [dry] member email: {p.get('matchup')} ({p.get('date')})")
        return True
    if not to:
        print("  members: no active passes — nothing to email")
        return True
    import requests
    subject, text, html = message(p, when_label)
    key = os.environ["RESEND_API_KEY"].strip()
    ok = True
    for i in range(0, len(to), 100):
        batch = [{"from": FROM, "to": [addr], "subject": subject, "text": text, "html": html} for addr in to[i:i + 100]]
        r = requests.post(RESEND_URL, json=batch, timeout=30,
                          headers={"Authorization": f"Bearer {key}",
                                   "Idempotency-Key": f"{doc_id(p['id'])}-{i}"})
        if r.status_code >= 300:
            print(f"  WARN member email batch {i // 100}: HTTP {r.status_code} {r.text[:200]}")
            ok = False
    print(f"  members: emailed {len(to)} active member(s) · {p.get('matchup')}")
    return ok

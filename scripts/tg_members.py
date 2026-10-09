#!/usr/bin/env python3
"""tg_members.py — who is allowed in the members channel, and for how long.

Source of truth is Firestore, the same place Stripe's webhook writes a pass:
  users/{uid}.accessExpiresAt   — set by stripeWebhook on purchase
  tg_members/{telegram_id}      — {uid, username, joinedAt, removedAt, compUntil, note}

How a member gets in: the site's telegramInvite function (functions/index.js)
mints a one-person, one-hour invite link named "u:<uid>". When someone joins
with it, Telegram reports the link on the chat_member update, so we record
telegram_id -> uid here. Anyone who joins without one of our links (or a comp)
is removed on sight.

How a member gets out: sweep() runs every bot cycle; anyone whose pass (or
comp) has ended is removed (ban + unban, so they can buy back in) and DM'd.

Comps: grant(telegram_id, days) records compUntil and returns a one-person link.

Credentials: FIREBASE_SERVICE_ACCOUNT (the service-account JSON). Without it
every function here is a no-op and says so — gatekeeping never half-runs.
"""

import json
import os
from datetime import datetime, timedelta, timezone

_db = None
RENEW_URL = "https://morellosims.com/#plans"


def db():
    """Firestore client, or None when no service account is configured."""
    global _db
    if _db is not None:
        return _db
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    if not raw:
        return None
    import firebase_admin
    from firebase_admin import credentials, firestore
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(json.loads(raw)))
    _db = firestore.client()
    return _db


def _now():
    return datetime.now(timezone.utc)


def pass_active(user_doc):
    """Mirror of hasActiveAccess in functions/index.js."""
    if not user_doc:
        return False
    if user_doc.get("tier") == "admin":
        return True
    exp = user_doc.get("accessExpiresAt")
    if exp is not None and exp > _now():
        return True
    return user_doc.get("checkoutMode") == "subscription" and user_doc.get("tier") not in (None, "free")


def member_active(member):
    comp = member.get("compUntil")
    if comp is not None and comp > _now():
        return True
    uid = member.get("uid")
    if not uid:
        return False
    snap = db().collection("users").document(uid).get()
    return pass_active(snap.to_dict() if snap.exists else None)


def record_join(tg_user, invite_name):
    """A join through one of our links. Returns 'member', 'comp' or None (not ours)."""
    d = db()
    ref = d.collection("tg_members").document(str(tg_user["id"]))
    base = {"username": tg_user.get("username"), "first_name": tg_user.get("first_name"),
            "joinedAt": _now(), "removedAt": None}
    if invite_name.startswith("u:"):
        ref.set({**base, "uid": invite_name[2:]}, merge=True)
        return "member"
    snap = ref.get()
    if snap.exists and (snap.to_dict().get("compUntil") or _now()) > _now():
        ref.set(base, merge=True)
        return "comp"
    return None


def sweep(remove):
    """Remove everyone whose pass or comp has ended. remove(tg_id) does the kick + DM."""
    d = db()
    if d is None:
        print("  members: FIREBASE_SERVICE_ACCOUNT not set — sweep skipped")
        return 0
    n = 0
    for doc in d.collection("tg_members").where("removedAt", "==", None).stream():
        m = doc.to_dict()
        if member_active(m):
            continue
        try:
            remove(int(doc.id))
            doc.reference.update({"removedAt": _now()})
            n += 1
            print(f"  members: removed {doc.id} (pass ended)")
        except Exception as e:
            print(f"  WARN members: could not remove {doc.id}: {e}")
    return n


def grant(tg_id, days, note, make_link):
    """Comp a Telegram user for N days; returns a one-person invite link for them."""
    until = _now() + timedelta(days=days)
    db().collection("tg_members").document(str(tg_id)).set(
        {"compUntil": until, "note": note or "", "removedAt": None}, merge=True)
    return make_link(f"c:{tg_id}", int((min(until, _now() + timedelta(days=1))).timestamp())), until


def revoke(tg_id):
    db().collection("tg_members").document(str(tg_id)).set(
        {"compUntil": _now() - timedelta(seconds=1), "uid": None}, merge=True)


def listing():
    rows = []
    for doc in db().collection("tg_members").stream():
        m = doc.to_dict()
        status = "removed" if m.get("removedAt") else ("ACTIVE" if member_active(m) else "lapsed")
        rows.append(f"  {doc.id:>12} {status:8} uid={m.get('uid') or '-'} comp={m.get('compUntil') or '-'} {m.get('note', '')}")
    return rows

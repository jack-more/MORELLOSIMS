#!/usr/bin/env python3
"""Put the full dashboard cards of tonight's picked games in Firestore.

Under seal mode generate_frontend.py renders a picked game as a sealed card on
the public dashboard and writes its full card (lineups, the sim's side, the
edge) to nba_pipeline/_member_cards.json, which is never committed. This
copies each one, branded like the page, to member_cards/{date}_{AWY}_{HOM};
the Firestore rules let the member_picks readers (whitelist, active pass)
read them, and the dashboard swaps them in after sign-in.

Never fails the pipeline: without FIREBASE_SERVICE_ACCOUNT, or on any
Firestore error, it says so and exits 0.

  python3 scripts/publish_member_cards.py
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import publish_member_dashboard  # noqa: E402
import tg_members  # noqa: E402

SRC = os.path.join(REPO, "nba_pipeline", "_member_cards.json")
ET = timezone(timedelta(hours=-4))
MAX_BYTES = 900_000               # a Firestore document tops out at 1 MiB
KEEP_DAYS = 3


def main():
    if not os.path.exists(SRC):
        print(f"member cards: {os.path.relpath(SRC, REPO)} not found — run generate_frontend.py first")
        return
    cards = json.load(open(SRC)).get("cards", {})
    db = tg_members.db()
    if db is None:
        print(f"member cards: FIREBASE_SERVICE_ACCOUNT not set — {len(cards)} card(s) not published")
        return
    from firebase_admin import firestore
    today = datetime.now(ET).strftime("%Y-%m-%d")
    col = db.collection("member_cards")
    for game, html in sorted(cards.items()):
        html = publish_member_dashboard.brand(html)
        if len(html.encode()) > MAX_BYTES:
            print(f"  member cards: {game} is {len(html.encode())} bytes, over the document limit — skipped")
            continue
        away, home = game.split("@")
        col.document(f"{today}_{away}_{home}").set({
            "date": today, "game": game, "html": html, "published_at": firestore.SERVER_TIMESTAMP})
        print(f"  member cards: {today} {game}")
    cutoff = (datetime.now(ET) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    for snap in col.where("date", "<", cutoff).stream():
        snap.reference.delete()
    print(f"member cards: {len(cards)} published for {today}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 — the dashboard still publishes; members see the sealed card
        print(f"::warning::member cards not published: {type(e).__name__}: {e}")

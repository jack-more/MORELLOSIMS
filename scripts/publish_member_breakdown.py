#!/usr/bin/env python3
"""Put tonight's breakdown in Firestore for /members/breakdown/ (member_breakdowns/{date}).

  python3 scripts/publish_member_breakdown.py walk.json

walk.json is nba_pipeline/sim/explain.py's output; render_breakdown.py turns it
into the page. Read by the member_picks readers only (firestore.rules). Never
fails the pipeline: without FIREBASE_SERVICE_ACCOUNT, or on any error, it says
so and exits 0.
"""

import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_breakdown  # noqa: E402
import tg_members  # noqa: E402

MAX_BYTES = 900_000


def main(path):
    walk = json.load(open(path))
    date = datetime.fromisoformat(walk["generated"].replace("Z", "+00:00")).astimezone(render_breakdown.ET).strftime("%Y-%m-%d")
    page = render_breakdown.render(walk, date)
    if len(page.encode()) > MAX_BYTES:
        print(f"breakdown: {len(page.encode())} bytes, over the document limit — not published")
        return
    db = tg_members.db()
    if db is None:
        print("breakdown: FIREBASE_SERVICE_ACCOUNT not set — not published")
        return
    from firebase_admin import firestore
    db.collection("member_breakdowns").document(date).set(
        {"date": date, "html": page, "games": len(walk["games"]), "published_at": firestore.SERVER_TIMESTAMP})
    print(f"breakdown: {len(walk['games'])} games published for {date}")


if __name__ == "__main__":
    try:
        main(sys.argv[1])
    except Exception as e:  # noqa: BLE001 — the rest of the site publishes regardless
        print(f"::warning::breakdown not published: {type(e).__name__}: {e}")

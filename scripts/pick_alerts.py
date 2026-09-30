#!/usr/bin/env python3
"""New-pick alerts, both sports: owner DM first, sealed card to X.

Owner rule (2026-09-30): X posts are blurred unless Jack says otherwise.
For every newly published pick (MLB picks/mlb.json, NBA picks/nba.json):
  1. DM Jack the full pick (the real card for MLB) with a button
     "Post to X unblurred" — tg_channel_bot.py handles the tap;
  2. post the SEALED card to X (render_sealed.py) — matchup, time,
     confidence and log time only; the side never leaves the DM.

Runs from tg_channel_bot.py (15-min cron) and is dispatched right after the
MLB/NBA pipelines publish, so alerts land within minutes. State in
ops/state/pick_alerts.json keeps every send exactly-once across runs.

  python3 scripts/pick_alerts.py [--dry-run]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ops_tg  # noqa: E402

REPO = os.path.dirname(HERE)
STATE = os.path.join(REPO, "ops", "state", "pick_alerts.json")  # telegram/ is gitignored
LEGACY = os.path.join(REPO, "mlbsim", "posted_cards.json")
OUT = os.path.join(REPO, "posters", "v2")
ET = timezone(timedelta(hours=-4))
MIN_CONF = 8


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def odds_str(p):
    o = str(p.get("odds") or "")
    return o if not o or o.startswith(("+", "-")) else f"+{o}"


def published_today(today):
    out = []
    for sport, path in (("mlb", "picks/mlb.json"), ("nba", "picks/nba.json")):
        for p in load(os.path.join(REPO, path), []):
            if (p.get("sport") or sport) == sport and p.get("date") == today \
                    and p.get("status") == "pending" and int(p.get("conf") or 0) >= MIN_CONF:
                p.setdefault("sport", sport)
                out.append(p)
    return out


def dm_text(p):
    sim = p.get("sim_projection") or ""
    return (f"🚨 NEW {p['sport'].upper()} PICK · C{p.get('conf')}\n"
            f"{p['pick_text']} {odds_str(p)} · {p.get('matchup')} · {p.get('game_time') or ''}\n"
            f"Risk {p.get('units')} $PP" + (f" · Sim {sim}" if sim else "") + "\n"
            f"X gets the sealed card. Tap below to post it unblurred.")


def x_caption(p):
    when = p.get("game_time") or ""
    return (f"SEALED · C{p.get('conf')} · {p.get('matchup')}" + (f" · {when}" if when else "") + "\n"
            f"Logged {datetime.now(ET).strftime('%-I:%M %p ET')}, before the game.\n"
            f"Members have it now → morellosims.com")


def run(dry=False):
    if dry:
        ops_tg.DRY = True
    today = datetime.now(ET).strftime("%Y-%m-%d")
    st = load(STATE, {"dm": [], "x_sealed": [], "x_open": []})
    # picks already receipted by the old post_daily_cards flow count as sent
    legacy = load(LEGACY, {})
    for pid in legacy.get("receipts", []):
        if pid not in st["dm"]:
            st["dm"].append(pid)
    for pid in legacy.get("x_receipts", []):
        if pid not in st["x_sealed"]:
            st["x_sealed"].append(pid)

    from post_social_daily import post_to_x
    import render_sealed
    os.makedirs(OUT, exist_ok=True)
    for p in published_today(today):
        pid = p["id"]
        if pid not in st["dm"]:
            button = [[("📣 Post to X unblurred", f"xopen:{pid}")]]
            ok = False
            if p["sport"] == "mlb":
                try:
                    import render_pick_card as render_series_card  # v3 layout (2026-09-30)
                    path = os.path.join(OUT, f"series-{pid}.png")
                    render_series_card.render(p, False).save(path)
                    ok = ops_tg.send_photo(path, dm_text(p), button)
                except Exception as e:
                    print(f"  WARN card render {pid}: {e}")
            if not ok:
                ok = ops_tg.send(dm_text(p), button)
            if ok:
                st["dm"].append(pid)
        if pid not in st["x_sealed"] and pid not in st["x_open"]:
            try:
                path = os.path.join(OUT, f"sealed-{pid}.png")
                render_sealed.sealed_card(p).save(path)
                if post_to_x(x_caption(p), Path(path), dry_run=dry):
                    st["x_sealed"].append(pid)
            except Exception as e:
                print(f"  WARN sealed X post {pid}: {e}")
    for k in st:
        st[k] = st[k][-600:]
    if not dry:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w") as f:
            json.dump(st, f, indent=2)
    return st


def open_on_x(pid, dry=False):
    """Owner tapped 'Post to X unblurred': the real card, full pick."""
    st = load(STATE, {"dm": [], "x_sealed": [], "x_open": []})
    if pid in st["x_open"]:
        return "already posted unblurred"
    p = next((q for q in published_today(datetime.now(ET).strftime("%Y-%m-%d")) if q["id"] == pid), None)
    if p is None:
        for path in ("picks/mlb.json", "picks/nba.json"):
            p = p or next((q for q in load(os.path.join(REPO, path), []) if q["id"] == pid), None)
    if p is None:
        return "pick not found"
    from post_social_daily import post_to_x
    cap = (f"{p['pick_text']} {odds_str(p)} · C{p.get('conf')} · {p.get('matchup')}\n"
           f"Logged before the game. Every pick → morellosims.com")
    images = []
    if (p.get("sport") or "mlb") == "mlb":
        import render_pick_card as render_series_card  # v3 layout (2026-09-30)
        path = os.path.join(OUT, f"series-{pid}.png")
        os.makedirs(OUT, exist_ok=True)
        render_series_card.render(p, False).save(path)
        images = [Path(path)]
    if not images:
        return "no card for this sport yet — X needs an image post"
    if post_to_x(cap, images, dry_run=dry):
        st["x_open"].append(pid)
        if not dry:
            with open(STATE, "w") as f:
                json.dump(st, f, indent=2)
        return "posted to X unblurred"
    return "X post failed (are the X secrets set?)"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(dry=a.dry_run)

#!/usr/bin/env python3
"""Render a pick as its note (scripts/templates/pick_note.html) to a 1080x1350 PNG.

Headless Chrome screenshots the template, served from the repo by a throwaway
local server, so the PNG is the same note members see on /members/ (tier, team
colours, foil, rosette). Used by member_delivery.py for the pick email.

Chrome: $CHROME_BIN, else google-chrome / chromium on PATH (GitHub's Ubuntu
runners ship google-chrome). No Chrome, or a render that fails, returns None and
the caller sends the email without the card.

  python3 scripts/render_pick_note.py --pick-id <id> [--out file.png]
"""

import argparse
import functools
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.parse
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

ET = timezone(timedelta(hours=-4))
TEAMS_JSON = os.path.join(REPO, "data", "reference", "nba_teams_espn_2026.json")
# NBA abbreviations where ESPN's differ (render_nba_card.NBA_TO_ESPN, kept here so this has no PIL import)
NBA_TO_ESPN = {"GSW": "GS", "NOP": "NO", "NYK": "NY", "SAS": "SA", "UTA": "UTAH", "WAS": "WSH"}
STAKE = {0.25: "¼U", 0.5: "½U"}


def _team(abbr):
    teams = json.load(open(TEAMS_JSON))["teams"]
    return teams.get(NBA_TO_ESPN.get(abbr, abbr)), NBA_TO_ESPN.get(abbr, abbr).lower()


def _num(v):
    return ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v):.1f}"


def _et(ts):
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(ET).strftime("%-I:%M %p")


def note_data(p, n=1, when_label=None):
    """The template's fields for one NBA spread pick, or None for anything else."""
    if (p.get("sport") or "nba") != "nba" or (p.get("bet_type") or "spread") != "spread":
        return None
    abbr, _, line_raw = (p.get("pick_text") or "").partition(" ")
    try:
        book = float(line_raw.replace("−", "-"))
    except ValueError:
        return None
    away, _, home = (p.get("matchup") or "").partition(" @ ")
    away, home = p.get("away") or away, p.get("home") or home
    t, logo = _team(abbr)
    if not t:
        return None
    opp = away if abbr == home else home
    o, _ = _team(opp)
    try:
        sim = float((p.get("sim_projection") or "").split(" ")[1].replace("−", "-"))
    except (IndexError, ValueError):
        sim = None
    # a logged pick always has the sim on its side of the book; records written before the
    # away-side sign fix in sync_to_picks_json carry the sim line flipped (members page does the same)
    if sim is not None and sim > book:
        sim = -sim
    sim_txt = "—" if sim is None else (f"{t['name']} by {abs(sim):g}" if sim < 0 else "Pick'em" if sim == 0 else f"{t['name']} +{sim:g}")
    u = round(float(p.get("units") or 0) / 25, 2)          # $PP → units (25 $PP = 1u)
    tier = max(6, min(10, int(p.get("conf") or 6)))
    tip = when_label or p.get("game_time") or _et(p.get("tip_at") or p.get("start")) or "Tonight"
    date = p.get("date") or ""
    o_name = o["name"] if o else opp
    names = {away: (o_name if away == opp else t["name"]), home: (t["name"] if home == abbr else o_name)}
    venue = (t if abbr == home else o or {}).get("venue") or ""
    return {
        "tier": tier, "tc": t["color"], "tc2": t["alt"],
        "logo": f"https://a.espncdn.com/i/teamlogos/nba/500/{logo}.png",
        "city": t["location"], "nick": t["name"], "abbr": abbr,
        "line": _num(book), "terms": f"{str(p.get('odds') or '').replace('-', '−')} · {u:g} unit{'' if u == 1 else 's'} · {'vs' if abbr == home else 'at'} {o_name}",
        "ser": f"{date[8:10]}{n:02d}", "stake": STAKE.get(u, f"{u:g}U"),
        "book": f"{abbr} {_num(book)}", "sim": sim_txt,
        "edge": "—" if sim is None else f"{abs(book - sim):.1f} pts", "tip": str(tip).replace(" ET", ""),
        "game": f"{names[away]} at {names[home]}" + (f" · {venue}" if venue else ""),
        "logged": f"Logged {_et(p.get('captured_at'))} ET" if _et(p.get("captured_at")) else "Logged before tip",
    }


def _chrome():
    for c in (os.environ.get("CHROME_BIN"), "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if c and (shutil.which(c) or os.path.exists(c)):
            return shutil.which(c) or c
    return None


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def render(p, out_path, n=1, when_label=None):
    """Write the note PNG for pick p to out_path. Returns the path, or None."""
    data = note_data(p, n, when_label)
    chrome = _chrome()
    if not data or not chrome:
        return None
    handler = functools.partial(_Quiet, directory=REPO)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = (f"http://127.0.0.1:{srv.server_address[1]}/scripts/templates/pick_note.html#"
           + urllib.parse.quote(json.dumps(data, ensure_ascii=False)))
    try:
        with tempfile.TemporaryDirectory() as prof:
            subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                            f"--user-data-dir={prof}", "--window-size=1080,1500", "--virtual-time-budget=9000",
                            "--force-device-scale-factor=1", f"--screenshot={out_path}", url],
                           check=True, timeout=90, capture_output=True)
    except (subprocess.SubprocessError, OSError) as e:
        print(f"  WARN pick note render failed: {type(e).__name__}")
        return None
    finally:
        srv.shutdown()
    if not os.path.exists(out_path) or os.path.getsize(out_path) < 20000:
        return None
    from PIL import Image                      # the window runs taller than the note; keep the note
    Image.open(out_path).crop((0, 0, 1080, 1350)).save(out_path)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick-id", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    import picks_store  # seal mode: sealed picks open with PICKS_SEAL_KEY
    p = next((x for x in picks_store.load_picks("nba") if x["id"] == a.pick_id), None)
    if not p:
        raise SystemExit(f"{a.pick_id}: not in picks/nba.json")
    out = render(p, a.out or os.path.join(tempfile.gettempdir(), f"note-{a.pick_id}.png"))
    print(out or "not rendered")


if __name__ == "__main__":
    main()

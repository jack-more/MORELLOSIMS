#!/usr/bin/env python3
"""
Update the SEASON RECORD BOX on /mlbsim/index.html and /nbasim/index.html
from picks/{nba,mlb}.json + picks/baselines.json.

Combines manual baselines (historical season-to-date) with newly settled picks
in the JSON contract. Idempotent — safe to run after every pipeline.

Marker convention: each card lives between
  <!-- RECORD-CARD:{SPORT}:BEGIN --> ... <!-- RECORD-CARD:{SPORT}:END -->
"""
import json
import os
import re

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PICKS_DIR = os.path.join(REPO, "picks")
BASELINES = os.path.join(PICKS_DIR, "baselines.json")
PAGES = {
    "mlb": (os.path.join(REPO, "mlbsim", "index.html"), os.path.join(PICKS_DIR, "mlb.json"), "#FFEA00"),
    "nba": (os.path.join(REPO, "nbasim", "index.html"), os.path.join(PICKS_DIR, "nba.json"), "#00FF55"),
}


def aggregate(picks_json_path, baseline):
    """Combine baseline + JSON-settled picks → unified record."""
    wins = baseline["wins"]
    losses = baseline["losses"]
    risked = baseline["risked"]
    pl = baseline["pl"]
    if os.path.exists(picks_json_path):
        with open(picks_json_path) as f:
            picks = json.load(f)
        for p in picks:
            if p["status"] not in ("win", "loss"):
                continue
            wins += 1 if p["status"] == "win" else 0
            losses += 1 if p["status"] == "loss" else 0
            risked += p.get("units") or 50
            pl += p.get("pl") or 0
    roi = (pl / risked * 100) if risked else 0
    return wins, losses, roi


def render_card(sport, wins, losses, roi, filter_text, accent):
    return f'''<!-- RECORD-CARD:{sport.upper()}:BEGIN -->
<!-- ─── SEASON RECORD BOX ────────────────────────────────────── -->
<div style="max-width:560px;margin:14px auto 18px;padding:0 12px;">
  <div style="background:#0a0a0a;border:2px solid {accent};border-radius:6px;padding:16px 22px;box-shadow:5px 5px 0 {accent};">
    <div style="display:flex;justify-content:space-between;align-items:center;font-family:'JetBrains Mono',monospace;gap:18px;">
      <div style="text-align:left;flex:1;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">SEASON</div>
        <div style="font-size:30px;color:#00FF55;font-weight:700;line-height:1;margin-top:4px;font-family:'Anton',sans-serif;letter-spacing:1px;">{wins}-{losses}</div>
      </div>
      <div style="text-align:center;border-left:1px solid #2a2a2a;border-right:1px solid #2a2a2a;padding:2px 22px;flex:1;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">ROI</div>
        <div style="font-size:30px;color:#FFEA00;font-weight:700;line-height:1;margin-top:4px;font-family:'Anton',sans-serif;letter-spacing:1px;">{roi:+.1f}%</div>
      </div>
      <div style="text-align:right;flex:1;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">FILTER</div>
        <div style="font-size:11px;color:#fff;font-weight:700;line-height:1.3;margin-top:6px;letter-spacing:0.5px;">{filter_text}</div>
      </div>
    </div>
  </div>
</div>
<!-- RECORD-CARD:{sport.upper()}:END -->'''


def install_or_replace(html, sport, new_block):
    begin = f"<!-- RECORD-CARD:{sport.upper()}:BEGIN -->"
    end = f"<!-- RECORD-CARD:{sport.upper()}:END -->"
    bi = html.find(begin)
    ei = html.find(end)
    if bi >= 0 and ei >= 0:
        return html[:bi] + new_block + html[ei + len(end):]

    # First-time install: locate existing inline record box and wrap it
    # mlbsim has the box between <!-- ─── SEASON RECORD BOX ──...
    pattern = re.compile(
        r'<!-- ─── SEASON RECORD BOX[^>]*?-->\s*<div[^>]*>\s*<div[^>]*border:2px solid[^>]*>.*?</div>\s*</div>\s*</div>',
        re.DOTALL,
    )
    m = pattern.search(html)
    if m:
        return html[:m.start()] + new_block + html[m.end():]

    # No existing card — inject after </header>
    h_close = html.find("</header>")
    if h_close >= 0:
        insert_at = h_close + len("</header>")
        return html[:insert_at] + "\n\n" + new_block + "\n" + html[insert_at:]

    raise RuntimeError(f"Could not find an insertion point for {sport} record card.")


def main():
    with open(BASELINES) as f:
        baselines = json.load(f)

    for sport, (page_path, picks_path, accent) in PAGES.items():
        if not os.path.exists(page_path):
            print(f"  [WARN] {page_path} missing — skipping {sport}")
            continue

        wins, losses, roi = aggregate(picks_path, baselines[sport])
        filter_text = baselines[sport]["filter"].replace(" · ", "<br><span style=\"color:#888;\">") + "</span>"

        block = render_card(sport, wins, losses, roi, filter_text, accent)
        with open(page_path) as f:
            html = f.read()
        new_html = install_or_replace(html, sport, block)
        with open(page_path, "w") as f:
            f.write(new_html)
        print(f"  {sport.upper()}: {wins}-{losses} ({roi:+.1f}% ROI) → {page_path}")


if __name__ == "__main__":
    main()

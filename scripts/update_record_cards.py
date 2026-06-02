#!/usr/bin/env python3
"""
Update the tracked picks card on /mlbsim/index.html and /nbasim/index.html
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
HOMEPAGE = os.path.join(REPO, "index.html")
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
<!-- ─── TRACKED PICKS BOX ────────────────────────────────────── -->
<div style="max-width:560px;margin:14px auto 18px;padding:0 12px;">
  <div style="background:#0a0a0a;border:2px solid {accent};border-radius:6px;padding:16px 22px;box-shadow:5px 5px 0 {accent};">
    <div style="display:flex;justify-content:space-between;align-items:center;font-family:'JetBrains Mono',monospace;gap:18px;">
      <div style="text-align:left;flex:1;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">TRACKED</div>
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

    # First-time install: locate an existing inline record box and wrap it.
    # Keep the old marker in the matcher so older generated pages migrate cleanly.
    pattern = re.compile(
        r'<!-- ─── (?:SEASON RECORD|TRACKED PICKS) BOX[^>]*?-->\s*<div[^>]*>\s*<div[^>]*border:2px solid[^>]*>.*?</div>\s*</div>\s*</div>',
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


def update_homepage_hero(html, sport, wins, losses, roi, baseline):
    """Patch the homepage MLB/NBA picks tracker hero stats from JSON."""
    risked = baseline["risked"]
    pl = baseline["pl"]
    if os.path.exists(os.path.join(PICKS_DIR, f"{sport}.json")):
        with open(os.path.join(PICKS_DIR, f"{sport}.json")) as f:
            picks = json.load(f)
        for p in picks:
            if p["status"] in ("win", "loss"):
                risked += p.get("units") or 50
                pl += p.get("pl") or 0
    bankroll = 1000 + pl
    total_picks = wins + losses

    # Replace hero stats inside the post-{sport}-picks block via class anchors
    block_pattern = re.compile(
        rf'(<details class="blog-card post-{sport}-picks"[^>]*>)(.*?)(</details>)',
        re.DOTALL,
    )
    m = block_pattern.search(html)
    if not m:
        return html

    block = m.group(2)
    # Title
    block = re.sub(
        r'(<h3 class="blog-title bebas">)[^<]*(</h3>)',
        rf'\g<1>{sport.upper()} SIM: {wins}-{losses} RECORD ({roi:+.1f}% ROI)\g<2>',
        block,
    )
    # Hero record
    block = re.sub(
        r'(stat-record">\s*<span class="stat-value">)[^<]*(</span>)',
        rf'\g<1>{wins}-{losses}\g<2>',
        block,
    )
    # Hero ROI
    block = re.sub(
        r'(stat-roi">\s*<span class="stat-value">)[^<]*(</span>)',
        rf'\g<1>{roi:+.1f}%\g<2>',
        block,
    )
    # Hero bankroll
    block = re.sub(
        r'(stat-bankroll">\s*<span class="stat-value">)[^<]*(</span>)',
        rf'\g<1>{bankroll:,}\g<2>',
        block,
    )
    # Hero picks count
    block = re.sub(
        r'(stat-picks">\s*<span class="stat-value">)[^<]*(</span>)',
        rf'\g<1>{total_picks}\g<2>',
        block,
    )
    # Dispatch summary inside body
    block = re.sub(
        r'(<span class="dispatch-val record">)[^<]*(</span>)',
        rf'\g<1>{wins}-{losses}\g<2>',
        block,
    )
    block = re.sub(
        r'(<span class="dispatch-val roi">)[^<]*(</span>)',
        rf'\g<1>{roi:+.1f}%\g<2>',
        block,
    )
    block = re.sub(
        r'(<span class="dispatch-val bankroll">)[^<]*(</span>)',
        rf'\g<1>{bankroll:,}\g<2>',
        block,
    )

    return html[:m.start(2)] + block + html[m.end(2):]


def main():
    with open(BASELINES) as f:
        baselines = json.load(f)

    # Per-sport tracked picks card on /mlbsim/ and /nbasim/
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
        print(f"  {sport.upper()} card: {wins}-{losses} ({roi:+.1f}% ROI) → {page_path}")

    # Homepage dispatch hero stats (NBA + MLB)
    if os.path.exists(HOMEPAGE):
        with open(HOMEPAGE) as f:
            home_html = f.read()
        for sport in ("nba", "mlb"):
            wins, losses, roi = aggregate(os.path.join(PICKS_DIR, f"{sport}.json"), baselines[sport])
            home_html = update_homepage_hero(home_html, sport, wins, losses, roi, baselines[sport])
        with open(HOMEPAGE, "w") as f:
            f.write(home_html)
        print(f"  Homepage hero stats updated → {HOMEPAGE}")


if __name__ == "__main__":
    main()

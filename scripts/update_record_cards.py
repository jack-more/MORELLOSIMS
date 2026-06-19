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


def html_escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_filter_text(value):
    parts = str(value or "").split(" · ", 1)
    if len(parts) == 1:
        return html_escape(parts[0])
    return f'{html_escape(parts[0])} <span style="color:#888;">{html_escape(parts[1])}</span>'


def is_tracked_pick(pick, sport):
    if pick["status"] not in ("win", "loss", "push"):
        return False
    if sport == "mlb":
        try:
            return int(pick.get("conf") or 0) >= 8
        except (TypeError, ValueError):
            return False
    return True


def aggregate(picks_json_path, baseline, sport):
    """Combine baseline + JSON-settled picks → unified record."""
    wins = baseline["wins"]
    losses = baseline["losses"]
    risked = baseline["risked"]
    pl = baseline["pl"]
    settled_for_streak = []
    if os.path.exists(picks_json_path):
        with open(picks_json_path) as f:
            picks = json.load(f)
        for p in picks:
            if not is_tracked_pick(p, sport):
                continue
            wins += 1 if p["status"] == "win" else 0
            losses += 1 if p["status"] == "loss" else 0
            risked += p.get("units") or 50
            pl += p.get("pl") or 0
            if p["status"] in ("win", "loss"):
                settled_for_streak.append(p)

    settled_for_streak.sort(key=lambda p: p.get("date", ""), reverse=True)
    streak = 0
    streak_type = ""
    if settled_for_streak:
        streak_type = settled_for_streak[0].get("status", "")
        for p in settled_for_streak:
            if p.get("status") == streak_type:
                streak += 1
            else:
                break
    streak_label = f'{"W" if streak_type == "win" else "L"}{streak}' if streak else "-"
    roi = (pl / risked * 100) if risked else 0
    return wins, losses, roi, streak_label


def render_card(sport, wins, losses, roi, streak, filter_text, accent):
    card_label = "SEASON" if sport == "nba" else "TRACKED"
    card_comment = "SEASON RECORD BOX" if sport == "nba" else "─── TRACKED PICKS BOX ──────────────────────────────────────"
    roi_color = accent if sport == "nba" else "#FFEA00"
    return f'''<!-- RECORD-CARD:{sport.upper()}:BEGIN -->
<!-- {card_comment} -->
<div style="max-width:640px;margin:14px auto 18px;padding:0 12px;">
  <div style="background:#0a0a0a;border:2px solid {accent};border-radius:6px;padding:16px 22px;box-shadow:5px 5px 0 {accent};">
    <div style="display:grid;grid-template-columns:1.35fr 1fr 0.8fr;align-items:center;font-family:'JetBrains Mono',monospace;gap:16px;">
      <div style="text-align:left;min-width:0;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">{card_label}</div>
        <div style="font-size:30px;color:#00FF55;font-weight:700;line-height:1;margin-top:4px;font-family:'Anton',sans-serif;letter-spacing:1px;">{wins}-{losses}</div>
      </div>
      <div style="text-align:center;border-left:1px solid #2a2a2a;border-right:1px solid #2a2a2a;padding:2px 16px;min-width:0;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">ROI</div>
        <div style="font-size:30px;color:{roi_color};font-weight:700;line-height:1;margin-top:4px;font-family:'Anton',sans-serif;letter-spacing:1px;">{roi:+.1f}%</div>
      </div>
      <div style="text-align:right;min-width:0;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">STREAK</div>
        <div style="font-size:30px;color:#fff;font-weight:700;line-height:1;margin-top:4px;font-family:'Anton',sans-serif;letter-spacing:1px;">{streak}</div>
      </div>
    </div>
    <div style="margin-top:12px;padding-top:10px;border-top:1px solid #2a2a2a;display:flex;justify-content:space-between;gap:12px;align-items:center;font-family:'JetBrains Mono',monospace;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">FILTER</div>
        <div style="font-size:11px;color:#fff;font-weight:700;line-height:1.3;letter-spacing:0.5px;text-align:right;">{filter_text}</div>
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

    # First-time install: locate an existing inline record box and replace it
    # through the next stable page anchor. This avoids leaving orphan closing
    # divs when the old card has nested inline markup.
    old_marker = re.search(
        r'<!-- (?:SEASON RECORD BOX|─── (?:SEASON RECORD|TRACKED PICKS) BOX.*?-->)',
        html,
    )
    if old_marker:
        anchors = [
            "\n<!-- FILTER BAR",
            "\n        <!-- FILTER BAR",
            "\n    <!-- MAIN CONTENT AREA",
            "\n    <main",
            "\n<main",
        ]
        ends = [html.find(anchor, old_marker.start()) for anchor in anchors]
        ends = [idx for idx in ends if idx >= 0]
        if ends:
            end_idx = min(ends)
            return html[:old_marker.start()] + new_block + html[end_idx:]

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
            if is_tracked_pick(p, sport):
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

        wins, losses, roi, streak = aggregate(picks_path, baselines[sport], sport)
        filter_text = render_filter_text(baselines[sport].get("filter", ""))

        block = render_card(sport, wins, losses, roi, streak, filter_text, accent)
        with open(page_path) as f:
            html = f.read()
        new_html = install_or_replace(html, sport, block)
        with open(page_path, "w") as f:
            f.write(new_html)
        print(f"  {sport.upper()} card: {wins}-{losses} ({roi:+.1f}% ROI) → {page_path}")

    print("  Homepage dispatch is owned by scripts/render_dispatch.py")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build the public /nbasim/ artifact from the internal NBA dashboard.

The generator owns the full dashboard. This script applies the MORELLOSIMS
shell tweaks the public page needs, then adds the season record card that sits
near the top of the page.
"""

from __future__ import annotations

import re
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "nba_pipeline" / "index.html"
TARGET = ROOT / "nbasim" / "index.html"
PICKS_JSON = ROOT / "picks" / "nba.json"
BASELINES_JSON = ROOT / "picks" / "baselines.json"


def aggregate_nba_record() -> tuple[int, int, float, str]:
    with BASELINES_JSON.open() as f:
        baselines = json.load(f)

    baseline = baselines["nba"]
    wins = int(baseline["wins"])
    losses = int(baseline["losses"])
    risked = float(baseline["risked"])
    pl = float(baseline["pl"])

    if PICKS_JSON.exists():
        with PICKS_JSON.open() as f:
            picks = json.load(f)
        for pick in picks:
            status = pick.get("status")
            if status not in ("win", "loss"):
                continue
            wins += 1 if status == "win" else 0
            losses += 1 if status == "loss" else 0
            risked += float(pick.get("units") or 50)
            pl += float(pick.get("pl") or 0)

    roi = (pl / risked * 100) if risked else 0.0
    return wins, losses, roi, str(baseline.get("filter") or "C:5+ MIN")


def render_record_card() -> str:
    wins, losses, roi, filter_text = aggregate_nba_record()
    filter_html = filter_text.replace(" · ", '<br><span style="color:#888;">') + "</span>"
    return f'''<!-- RECORD-CARD:NBA:BEGIN -->
<!-- SEASON RECORD BOX -->
<div style="max-width:560px;margin:14px auto 18px;padding:0 12px;">
  <div style="background:#0a0a0a;border:2px solid #00FF55;border-radius:6px;padding:16px 22px;box-shadow:5px 5px 0 #00FF55;">
    <div style="display:flex;justify-content:space-between;align-items:center;font-family:'JetBrains Mono',monospace;gap:18px;">
      <div style="text-align:left;flex:1;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">SEASON</div>
        <div style="font-size:30px;color:#00FF55;font-weight:700;line-height:1;margin-top:4px;font-family:'Anton',sans-serif;letter-spacing:1px;">{wins}-{losses}</div>
      </div>
      <div style="text-align:center;border-left:1px solid #2a2a2a;border-right:1px solid #2a2a2a;padding:2px 22px;flex:1;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">ROI</div>
        <div style="font-size:30px;color:#00FF55;font-weight:700;line-height:1;margin-top:4px;font-family:'Anton',sans-serif;letter-spacing:1px;">{roi:+.1f}%</div>
      </div>
      <div style="text-align:right;flex:1;">
        <div style="font-size:9px;color:#888;letter-spacing:2px;font-weight:700;">FILTER</div>
        <div style="font-size:11px;color:#fff;font-weight:700;line-height:1.3;margin-top:6px;letter-spacing:0.5px;">{filter_html}</div>
      </div>
    </div>
  </div>
</div>
<!-- RECORD-CARD:NBA:END -->'''


def install_record_card(html: str) -> str:
    card = render_record_card()
    begin = "<!-- RECORD-CARD:NBA:BEGIN -->"
    end = "<!-- RECORD-CARD:NBA:END -->"
    start = html.find(begin)
    finish = html.find(end)
    if start >= 0 and finish >= 0:
        return html[:start] + card + html[finish + len(end):]

    marker = "    <!-- MAIN CONTENT AREA -->"
    idx = html.find(marker)
    if idx >= 0:
        return html[:idx] + card + "\n\n" + html[idx:]

    body = html.find("<main")
    if body >= 0:
        return html[:body] + card + "\n\n" + html[body:]

    raise RuntimeError("Could not find an insertion point for the NBA record card.")


def remove_block(html: str, start_marker: str, end_marker: str) -> str:
    start = html.find(start_marker)
    end = html.find(end_marker)
    if start < 0 or end < 0 or end <= start:
        return html
    return html[:start] + html[end:]


def strip_legacy_tabs(html: str) -> str:
    for tab in ("sim", "props", "trends"):
        html = re.sub(
            rf'\n\s*<button class="filter-btn" data-tab="{tab}">.*?</button>',
            "",
            html,
            flags=re.IGNORECASE,
        )
        html = re.sub(
            rf'\n\s*<button class="nav-btn" data-tab="{tab}">.*?</button>',
            "",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )

    html = remove_block(html, "        <!-- PROPS TAB -->", "        <!-- TRENDS TAB -->")
    html = remove_block(html, "        <!-- TRENDS TAB -->", "        <!-- SIM TAB -->")
    html = remove_block(html, "        <!-- SIM TAB -->", "        <!-- INFO TAB -->")
    return html


def inject_morello_shell(html: str) -> str:
    html = re.sub(r"<body(?:\s[^>]*)?>", '<body data-ma-theme="dark">', html, count=1)
    html = html.replace(
        '<div class="top-picks">',
        '<div class="top-picks" style="display:flex;align-items:center;gap:8px;">\n'
        '                <div class="status-indicators" style="display:flex;align-items:center;"></div>',
        1,
    )
    return html


def strip_trailing_whitespace(html: str) -> str:
    ending = "\n" if html.endswith("\n") else ""
    return "\n".join(line.rstrip() for line in html.splitlines()) + ending


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Missing source dashboard: {SOURCE}")

    html = SOURCE.read_text()
    html = inject_morello_shell(html)
    html = strip_legacy_tabs(html)
    html = install_record_card(html)
    html = strip_trailing_whitespace(html)

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(html)
    print(f"Built public NBA dashboard: {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

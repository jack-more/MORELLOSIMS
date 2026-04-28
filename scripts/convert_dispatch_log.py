#!/usr/bin/env python3
"""Convert the DISPATCH LOG from verbose pick-cards to compact table rows with weekly grouping."""
import re
import sys
from datetime import datetime, timedelta
from collections import OrderedDict

PATH = "/home/user/MORELLOSIMS/index.html"

with open(PATH) as f:
    html = f.read()

# ── Locate the NBA picks blog-card-body ──────────────────────────────────────
body_marker = '<!-- NBA SIM PICKS TRACKER (TOP POST)'
body_start_search = html.find(body_marker)
assert body_start_search != -1, "NBA picks marker not found"

body_open = html.find('<div class="blog-card-body">', body_start_search)
assert body_open != -1, "blog-card-body not found"
body_content_start = body_open + len('<div class="blog-card-body">')

# Find the matching </div> — it's followed by </details> for the blog-card
# The blog-tags div and closing </div> for blog-card-body are right before </details>
blog_tags_marker = '<div class="blog-tags mono">'
blog_tags_pos = html.find(blog_tags_marker, body_content_start)
# Find the </div> that closes blog-card-body (after blog-tags closing </div>)
# The structure is: blog-tags </div> \n </div> \n </details>
close_search = html.find('</details>', blog_tags_pos)
body_close = html.rfind('</div>', body_content_start, close_search)
# Actually, we want to replace everything inside blog-card-body, keeping blog-tags
# Let's find the end more precisely
body_content_end = html.find(blog_tags_marker, body_content_start)
assert body_content_end != -1, "blog-tags not found"

old_content = html[body_content_start:body_content_end]

# ── Parse all pick cards ─────────────────────────────────────────────────────
# Each slate-day has a date label and pick cards inside it
slate_pattern = re.compile(
    r'<span class="slate-day-label">([^<]+)</span>.*?'
    r'<span class="slate-day-meta">([^<]+)</span>.*?'
    r'<span class="slate-day-record"[^>]*>([^<]+)</span>',
    re.DOTALL
)

picks = []

# First, find all slate-day sections and map positions to dates
slate_dates = []
for m in re.finditer(r'<details class="slate-day"[^>]*>.*?<span class="slate-day-label">([^<]+)</span>', old_content, re.DOTALL):
    slate_dates.append((m.start(), m.group(1).strip()))

def get_date_for_pos(pos):
    """Find which slate-day a position belongs to."""
    result = None
    for start, date_str in slate_dates:
        if start <= pos:
            result = date_str
        else:
            break
    return result

# Split into individual pick-card blocks
card_blocks = re.split(r'(?=<div class="pick-card")', old_content)
for block in card_blocks:
    if not block.startswith('<div class="pick-card"'):
        continue

    # Parse attributes
    status_m = re.search(r'data-status="(\w+)"', block)
    matchup_m = re.search(r'data-matchup="([^"]+)"', block)
    side_m = re.search(r'pick-side-text[^>]*>([^<]+)', block)
    units_m = re.search(r'(\d+)\s*\$PP', block)
    conf_m = re.search(r'(?:SPREAD|CONF)\s*(\d+)', block)
    result_m = re.search(r'FINAL:\s*([^<]+)', block)
    rationale_m = re.search(r'pick-rationale[^>]*>([^<]*)</p>', block)
    if not rationale_m:
        rationale_m = re.search(r'blog-body-text pick-rationale[^>]*>([^<]*)</p>', block)

    if not (status_m and matchup_m and side_m):
        continue

    status = status_m.group(1)
    matchup = matchup_m.group(1)
    side_text = side_m.group(1).strip()
    units = int(units_m.group(1)) if units_m else 50
    conf = int(conf_m.group(1)) if conf_m else 5
    result_line = result_m.group(1).strip() if result_m else ""
    rationale = rationale_m.group(1).strip() if rationale_m else ""

    side = side_text.split("—")[-1].strip() if "—" in side_text else side_text.split("—")[-1].strip() if "—" in side_text else side_text

    wl = ""
    pl = ""
    score = ""
    if result_line:
        wl_match = re.search(r'\b(W|L|PUSH)\b\s*\(([^)]+)\)', result_line)
        if wl_match:
            wl = wl_match.group(1)
            pl = wl_match.group(2).replace("$PP", "").strip()
        score_match = re.search(r'^([^|]+)', result_line)
        if score_match:
            score = score_match.group(1).strip().replace(" — ", " - ").replace(" — ", " - ")

    # Find the date for this card by its position in old_content
    card_pos = old_content.find(block[:80])
    date_str = get_date_for_pos(card_pos) if card_pos >= 0 else None

    picks.append({
        "date_str": date_str,
        "status": status,
        "matchup": matchup,
        "side_text": side_text,
        "side": side,
        "units": units,
        "conf": conf,
        "result_line": result_line,
        "wl": wl,
        "pl": pl,
        "score": score,
        "rationale": rationale,
    })

print(f"Parsed {len(picks)} picks")

# Also try to catch picks from the table if we missed any from cards
table_start = old_content.find('<table')
if table_start != -1:
    # Count table rows for comparison
    table_rows = re.findall(r'<tr[^>]*>.*?</tr>', old_content[table_start:], re.DOTALL)
    # Subtract header row
    print(f"Table rows found: {len(table_rows) - 1} (for cross-check)")

# ── Parse dates ──────────────────────────────────────────────────────────────
MONTH_MAP = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
             "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}

def parse_date(date_str):
    """Parse 'APR 27 · MON' or 'APR 27 . MON' to datetime."""
    if not date_str:
        return datetime(2026, 1, 1)
    parts = re.match(r'(\w+)\s+(\d+)', date_str)
    if parts:
        month = MONTH_MAP.get(parts.group(1).upper(), 1)
        day = int(parts.group(2))
        return datetime(2026, month, day)
    return datetime(2026, 1, 1)

for p in picks:
    p["date"] = parse_date(p["date_str"])
    p["date_short"] = p["date"].strftime("%b %d").upper()

# Sort by date descending (newest first)
picks.sort(key=lambda p: p["date"], reverse=True)

# ── Parse hero stats from summary ────────────────────────────────────────────
summary_section = html[body_start_search:body_content_start]
record_match = re.search(r'stat-record.*?stat-value[^>]*>([^<]+)', summary_section, re.DOTALL)
roi_match = re.search(r'stat-roi.*?stat-value[^>]*>([^<]+)', summary_section, re.DOTALL)
bankroll_match = re.search(r'stat-bankroll.*?stat-value[^>]*>([^<]+)', summary_section, re.DOTALL)
picks_match = re.search(r'stat-picks.*?stat-value[^>]*>([^<]+)', summary_section, re.DOTALL)
risked_match = re.search(r'TOTAL RISKED.*?(\d[\d,]+)', html[body_content_start:body_content_start+500], re.DOTALL)

record = record_match.group(1).strip() if record_match else "103-86"
roi = roi_match.group(1).strip() if roi_match else "+4%"
bankroll = bankroll_match.group(1).strip() if bankroll_match else "1,467"
total_picks = picks_match.group(1).strip() if picks_match else "191"
total_risked = risked_match.group(1).strip() if risked_match else "7,870"

print(f"Hero stats: {record} | {roi} ROI | {bankroll} bankroll | {total_picks} picks | {total_risked} risked")

# ── Compute streak ───────────────────────────────────────────────────────────
settled = [p for p in picks if p["wl"] in ("W", "L")]
streak_count = 0
streak_type = ""
if settled:
    streak_type = settled[0]["wl"]
    for p in settled:
        if p["wl"] == streak_type:
            streak_count += 1
        else:
            break

streak_str = f"{streak_type}{streak_count}" if streak_type else "—"
print(f"Current streak: {streak_str}")

# ── Group by ISO week ───────────────────────────────────────────────────────
def week_key(dt):
    """Return (year, iso_week) tuple."""
    iso = dt.isocalendar()
    return (iso[0], iso[1])

def week_range(dt):
    """Return the Monday-Sunday range string for the week containing dt."""
    iso = dt.isocalendar()
    monday = dt - timedelta(days=dt.weekday())
    sunday = monday + timedelta(days=6)
    return f"{monday.strftime('%b %d').upper()} — {sunday.strftime('%b %d').upper()}"

weeks = OrderedDict()
for p in picks:
    wk = week_key(p["date"])
    if wk not in weeks:
        weeks[wk] = {"picks": [], "range": week_range(p["date"])}
    weeks[wk]["picks"].append(p)

# Compute per-week stats
for wk_data in weeks.values():
    w = sum(1 for p in wk_data["picks"] if p["wl"] == "W")
    l = sum(1 for p in wk_data["picks"] if p["wl"] == "L")
    pending = sum(1 for p in wk_data["picks"] if p["status"] == "pending")
    pl_total = 0
    for p in wk_data["picks"]:
        if p["pl"]:
            try:
                pl_total += int(p["pl"].replace("+", "").replace(",", ""))
            except ValueError:
                pass
    wk_data["w"] = w
    wk_data["l"] = l
    wk_data["pending"] = pending
    wk_data["pl"] = pl_total

print(f"Weeks: {len(weeks)}")
for wk, data in weeks.items():
    print(f"  {data['range']}: {data['w']}-{data['l']} ({data['pending']} pending) | {data['pl']:+d} $PP")

# ── Generate new HTML ────────────────────────────────────────────────────────

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

# Summary strip
summary_html = f'''
                    <!-- ── DISPATCH SUMMARY ── -->
                    <div class="dispatch-summary" id="dispatch-summary">
                        <div class="dispatch-stat">
                            <span class="dispatch-val record">{esc(record)}</span>
                            <span class="dispatch-lbl">RECORD</span>
                        </div>
                        <div class="dispatch-stat">
                            <span class="dispatch-val roi">{esc(roi)}</span>
                            <span class="dispatch-lbl">ROI</span>
                        </div>
                        <div class="dispatch-stat">
                            <span class="dispatch-val bankroll">{esc(bankroll)}</span>
                            <span class="dispatch-lbl">BANKROLL</span>
                        </div>
                        <div class="dispatch-stat">
                            <span class="dispatch-val">{esc(total_risked)}</span>
                            <span class="dispatch-lbl">RISKED</span>
                        </div>
                        <div class="dispatch-stat">
                            <span class="dispatch-val streak">{esc(streak_str)}</span>
                            <span class="dispatch-lbl">STREAK</span>
                        </div>
                    </div>
'''

# Streak dots (last 20 picks, newest first)
last_20 = picks[:20]
dots_html_parts = []
for p in last_20:
    if p["wl"] == "W":
        cls = "win"
    elif p["wl"] == "L":
        cls = "loss"
    else:
        cls = "pending"
    tip = f'{p["matchup"]} — {p["wl"] + " " + p["pl"] if p["wl"] else "PENDING"}'
    dots_html_parts.append(f'<span class="streak-dot {cls}" title="{esc(tip)}"></span>')

dots_html = f'''
                    <!-- ── STREAK DOTS ── -->
                    <div class="streak-dots" id="streak-dots">
                        <span class="streak-label">LAST 20</span>
                        {" ".join(dots_html_parts)}
                    </div>

                    <p class="mono" style="font-size:9px; color:#888; letter-spacing:1.5px; margin:0 0 8px;">UNIT KEY: <span style="color:#2a9d5f;">8-10 CONF = 50 $PP</span> &nbsp;&middot;&nbsp; <span style="color:#2a9d5f;">5-7 CONF = 30 $PP</span> &nbsp;&middot;&nbsp; <span style="color:#555;">1-10 SCALE &mdash; 5+ MINIMUM</span></p>
'''

# Weekly grouped table
weeks_html_parts = []
for i, (wk, data) in enumerate(weeks.items()):
    is_current = (i == 0)
    open_attr = " open" if is_current else ""

    w, l, pending_count, pl = data["w"], data["l"], data["pending"], data["pl"]
    if pending_count > 0 and w == 0 and l == 0:
        rec_cls = "pending"
        rec_text = "PENDING"
    elif pending_count > 0:
        rec_cls = "mixed"
        rec_text = f"{w}-{l} · {pl:+d} $PP · {pending_count}P"
    elif w > l:
        rec_cls = "win"
        rec_text = f"{w}-{l} · {pl:+d} $PP"
    elif l > w:
        rec_cls = "loss"
        rec_text = f"{w}-{l} · {pl:+d} $PP"
    else:
        rec_cls = "mixed"
        rec_text = f"{w}-{l} · {pl:+d} $PP"

    # Build rows for this week
    rows_html = ""
    for p in data["picks"]:
        if p["wl"] == "W":
            row_cls = "win"
            result_text = f'W {p["pl"]}'
        elif p["wl"] == "L":
            row_cls = "loss"
            result_text = f'L {p["pl"]}'
        elif p["wl"] == "PUSH":
            row_cls = "push"
            result_text = "PUSH"
        else:
            row_cls = "pending"
            result_text = "—"

        score_display = p["score"] if p["score"] else ""

        rows_html += f'''
                        <div class="pick-row {row_cls}" data-status="{p['status']}" data-matchup="{esc(p['matchup'])}">
                            <span class="pr-date">{p['date_short']}</span>
                            <span class="pr-matchup">{esc(p['matchup'])}</span>
                            <span class="pr-side pick-side-text">{esc(p['side'])}</span>
                            <span class="pr-conf">C:{p['conf']}</span>
                            <span class="pr-units">{p['units']}</span>
                            <span class="pr-result">{result_text}</span>
                        </div>'''
        if p["rationale"] or score_display:
            detail = score_display
            if p["rationale"]:
                detail = f'{detail} · {p["rationale"]}' if detail else p["rationale"]
            rows_html += f'''
                        <div class="pick-detail" hidden>{esc(detail)}</div>'''

    weeks_html_parts.append(f'''
                    <details class="week-group"{open_attr}>
                        <summary class="week-header">
                            <span class="week-label">{data['range']}</span>
                            <span class="week-record {rec_cls}">{rec_text}</span>
                        </summary>
                        <div class="week-body">{rows_html}
                        </div>
                    </details>''')

table_html = f'''
                    <!-- ── PICKS TABLE ── -->
                    <div class="dispatch-table" id="dispatch-table">
                        {"".join(weeks_html_parts)}
                    </div>
'''

# Methodology footer (keep existing text)
footer_html = '''
                    <p class="blog-body-text" style="font-size:11px; color:#555; margin-top:12px;">
                        All picks sourced from the NBA SIM pipeline &mdash; scheme detection, archetype clustering (K-Means on 16 features), Dynamic Score rankings, and lineup synergy. Lines via The Odds API. Full methodology at <a href="/nbasim/" style="color:#2a9d5f;">nbasim</a>.
                    </p>

'''

new_content = summary_html + dots_html + table_html + footer_html

# ── Replace in HTML ──────────────────────────────────────────────────────────
new_html = html[:body_content_start] + new_content + html[body_content_end:]

with open(PATH, "w") as f:
    f.write(new_html)

print(f"\nDone! Replaced {len(old_content):,} chars with {len(new_content):,} chars")
print(f"Old file: {len(html):,} chars → New file: {len(new_html):,} chars")

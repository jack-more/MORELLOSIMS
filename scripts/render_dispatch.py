#!/usr/bin/env python3
"""
Regenerate the dispatch log section of index.html from picks/{nba,mlb}.json.

This is the ONLY thing that should ever write to the dispatch log block in
index.html. Pipelines write to picks/*.json — never directly to the HTML.

Usage:  python3 scripts/render_dispatch.py
"""
import json
import os
import re
from collections import defaultdict, OrderedDict
from datetime import datetime, timedelta

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
INDEX = os.path.join(REPO, "index.html")
NBA_PATH = os.path.join(REPO, "picks", "nba.json")
MLB_PATH = os.path.join(REPO, "picks", "mlb.json")
BASELINES_PATH = os.path.join(REPO, "picks", "baselines.json")


def load_baselines():
    """Pre-tracking-era totals (manually entered through 2026-04-30 for MLB,
    through 2026-04-30 for NBA). Auto-tracked picks from picks/{nba,mlb}.json
    add to these. See picks/baselines.json for canonical record + filter."""
    try:
        with open(BASELINES_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

NBA_BEGIN = "<!-- DISPATCH:NBA:BEGIN -->"
NBA_END = "<!-- DISPATCH:NBA:END -->"
MLB_BEGIN = "<!-- DISPATCH:MLB:BEGIN -->"
MLB_END = "<!-- DISPATCH:MLB:END -->"


def esc(s):
    if s is None:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def short_date(date_iso):
    """'2026-04-30' → 'APR 30'."""
    dt = datetime.strptime(date_iso, "%Y-%m-%d")
    return dt.strftime("%b %d").upper().replace(" 0", " ")


def week_range(date_iso):
    """Monday–Sunday range string for the week containing date_iso."""
    dt = datetime.strptime(date_iso, "%Y-%m-%d")
    monday = dt - timedelta(days=dt.weekday())
    sunday = monday + timedelta(days=6)
    return f'{monday.strftime("%b %d").upper().replace(" 0", " ")} — {sunday.strftime("%b %d").upper().replace(" 0", " ")}'


def week_key(date_iso):
    dt = datetime.strptime(date_iso, "%Y-%m-%d")
    iso = dt.isocalendar()
    return (iso[0], iso[1])


def aggregate(picks, baseline=None):
    """Aggregate pick totals. If baseline is provided (a dict with wins/losses/
    risked/pl), it is ADDED to the computed totals — used to fold in the
    pre-auto-tracking-era manual record from picks/baselines.json."""
    # Push counts as settled (game graded, just neutral on P/L). Bucketing
    # pushes into pending was a bug — the dispatch row showed them as
    # still-pending and the hero record under-counted by the push count.
    settled = [p for p in picks if p["status"] in ("win", "loss", "push")]
    new_wins = sum(1 for p in settled if p["status"] == "win")
    new_losses = sum(1 for p in settled if p["status"] == "loss")
    new_risked = sum(p["units"] for p in settled)
    new_pl = sum(p.get("pl") or 0 for p in settled)

    base = baseline or {}
    wins = new_wins + (base.get("wins") or 0)
    losses = new_losses + (base.get("losses") or 0)
    risked = new_risked + (base.get("risked") or 0)
    pl = new_pl + (base.get("pl") or 0)
    bankroll = 1000 + pl
    roi = (pl / risked * 100) if risked else 0

    # Streak — last N settled, newest first (pure auto-tracked picks only;
    # baseline doesn't contribute since we don't have per-pick history there)
    settled_sorted = sorted(settled, key=lambda p: p["date"], reverse=True)
    streak = 0
    streak_type = ""
    if settled_sorted:
        streak_type = settled_sorted[0]["status"]
        for p in settled_sorted:
            if p["status"] == streak_type:
                streak += 1
            else:
                break
    streak_str = f'{"W" if streak_type == "win" else "L"}{streak}' if streak else "—"
    return {
        "wins": wins, "losses": losses,
        "risked": risked, "pl": pl, "bankroll": int(bankroll),
        "roi": roi, "streak": streak_str,
        "total": len(picks), "settled": len(settled), "pending": len(picks) - len(settled),
    }


def group_by_week(picks):
    grouped = OrderedDict()
    for p in sorted(picks, key=lambda p: p["date"], reverse=True):
        wk = week_key(p["date"])
        if wk not in grouped:
            grouped[wk] = {"range": week_range(p["date"]), "picks": []}
        grouped[wk]["picks"].append(p)
    return grouped


def render_pick_row(p, sport):
    if p["status"] == "win":
        cls = "win"
        result = f'W {(p.get("pl") or 0):+g}'
    elif p["status"] == "loss":
        cls = "loss"
        result = f'L {(p.get("pl") or 0):+g}'
    elif p["status"] == "push":
        cls = "push"
        result = "PUSH"
    else:
        cls = "pending"
        result = "—"

    # MLB ML rows show the odds in the conf column instead of "C:10"
    if sport == "nba":
        conf_disp = f'C:{p["conf"]}'
    else:
        # odds may be int (-326) or str ("-326" / "+150"); normalize either way
        try:
            odds_int = int(str(p["odds"]).replace("+", ""))
            conf_disp = f"{odds_int:+d}"
        except (ValueError, TypeError):
            conf_disp = str(p.get("odds", ""))

    detail = ""
    if p.get("result"):
        detail = p["result"]
    if p.get("sim_projection"):
        detail = f'{detail} · SIM: {p["sim_projection"]} (edge {p.get("sim_edge", "")})' if detail else f'SIM: {p["sim_projection"]} (edge {p.get("sim_edge", "")})'

    out = f'''
                        <div class="pick-row {cls}" data-status="{"settled" if p["status"] != "pending" else "pending"}" data-matchup="{esc(p["matchup"])}">
                            <span class="pr-date">{short_date(p["date"])}</span>
                            <span class="pr-matchup">{esc(p["matchup"])}</span>
                            <span class="pr-side pick-side-text">{esc(p["pick_text"])}</span>
                            <span class="pr-conf">{conf_disp}</span>
                            <span class="pr-units">{p["units"]}</span>
                            <span class="pr-result">{result}</span>
                        </div>'''
    if detail:
        out += f'\n                        <div class="pick-detail" hidden>{esc(detail)}</div>'
    return out


def render_week(wk_data, sport):
    picks = wk_data["picks"]
    w = sum(1 for p in picks if p["status"] == "win")
    l = sum(1 for p in picks if p["status"] == "loss")
    pending = sum(1 for p in picks if p["status"] == "pending")
    pl = sum(p.get("pl") or 0 for p in picks if p["status"] in ("win", "loss"))

    if pending and not w and not l:
        rec_cls = "pending"
        rec_text = "PENDING"
    elif pending:
        rec_cls = "mixed"
        rec_text = f'{w}-{l} · {pl:+g} $PP · {pending}P'
    elif w > l:
        rec_cls = "win"
        rec_text = f'{w}-{l} · {pl:+g} $PP'
    elif l > w:
        rec_cls = "loss"
        rec_text = f'{w}-{l} · {pl:+g} $PP'
    else:
        rec_cls = "mixed"
        rec_text = f'{w}-{l} · {pl:+g} $PP'

    rows = "".join(render_pick_row(p, sport) for p in picks)
    return f'''
                    <details class="week-group">
                        <summary class="week-header">
                            <span class="week-label">{wk_data["range"]}</span>
                            <span class="week-record {rec_cls}">{rec_text}</span>
                        </summary>
                        <div class="week-body">{rows}
                        </div>
                    </details>'''


def render_sport_block(picks, sport, hero_color, baseline=None):
    """Render a full dispatch card for one sport.
    `baseline` is the pre-tracking-era manual record (dict with wins/losses/
    risked/pl) — when provided, hero stats include it. Per-pick rows below
    only show auto-tracked picks (we don't have per-pick rows for baselines).
    """
    if not picks and not baseline:
        return ""

    agg = aggregate(picks, baseline=baseline)
    grouped = group_by_week(picks)
    weeks_html = "".join(render_week(g, sport) for g in grouped.values())

    sport_upper = sport.upper()
    hero_title = f'{sport_upper} SIM: {agg["wins"]}-{agg["losses"]} RECORD ({agg["roi"]:+.0f}% ROI)'
    css_class = "post-nba-picks" if sport == "nba" else "post-mlb-picks"
    methodology = (
        '<a href="/nbasim/" style="color:#2a9d5f;">nbasim</a>' if sport == "nba"
        else '<a href="/mlbsim/" style="color:#FFEA00;">mlbsim</a>'
    )
    method_text = (
        f"Picks sourced from the {sport_upper} SIM pipeline. Lines via The Odds API. "
        f"Full methodology at {methodology}."
    )
    if picks:
        earliest = min(p["date"] for p in picks)
        latest = max(p["date"] for p in picks)
        date_range = f'{short_date(earliest)} — {short_date(latest)}, 2026'
    elif baseline and baseline.get("since"):
        # No auto-tracked picks yet — show the baseline's "since" date
        date_range = f'SINCE {baseline["since"]}'
    else:
        date_range = '—'

    return f'''
            <details class="blog-card {css_class}" open>
                <summary>
                    <div class="blog-meta mono">
                        <span class="blog-card-type type-picks">PICKS LOG</span>
                        <div class="blog-system-dots">
                            <span class="blog-date">{date_range}</span>
                        </div>
                    </div>
                    <h3 class="blog-title bebas">{hero_title}</h3>
                    <div class="blog-hero-stats">
                        <div class="blog-hero-stat stat-record">
                            <span class="stat-value">{agg["wins"]}-{agg["losses"]}</span>
                            <span class="stat-label">RECORD</span>
                        </div>
                        <div class="blog-hero-stat stat-roi">
                            <span class="stat-value">{agg["roi"]:+.0f}%</span>
                            <span class="stat-label">ROI</span>
                        </div>
                        <div class="blog-hero-stat stat-bankroll">
                            <span class="stat-value">{agg["bankroll"]:,}</span>
                            <span class="stat-label">BANKROLL</span>
                        </div>
                        <div class="blog-hero-stat stat-picks">
                            <span class="stat-value">{agg["total"]}</span>
                            <span class="stat-label">PICKS</span>
                        </div>
                    </div>
                    <p class="blog-preview">
                        {agg["total"]} picks across {agg["settled"]} settled. Auto-rendered from <code>picks/{sport}.json</code>.
                    </p>
                </summary>
                <div class="blog-card-body">
                    <div class="dispatch-summary">
                        <div class="dispatch-stat"><span class="dispatch-val record">{agg["wins"]}-{agg["losses"]}</span><span class="dispatch-lbl">RECORD</span></div>
                        <div class="dispatch-stat"><span class="dispatch-val roi">{agg["roi"]:+.0f}%</span><span class="dispatch-lbl">ROI</span></div>
                        <div class="dispatch-stat"><span class="dispatch-val bankroll">{agg["bankroll"]:,}</span><span class="dispatch-lbl">BANKROLL</span></div>
                        <div class="dispatch-stat"><span class="dispatch-val">{agg["risked"]:,}</span><span class="dispatch-lbl">RISKED</span></div>
                        <div class="dispatch-stat"><span class="dispatch-val streak">{agg["streak"]}</span><span class="dispatch-lbl">STREAK</span></div>
                    </div>

                    <div class="dispatch-table">{weeks_html}
                    </div>

                    <p class="blog-body-text" style="font-size:11px; color:#555; margin-top:12px;">
                        {method_text}
                    </p>
                </div>
            </details>
'''


def replace_section(html, begin_marker, end_marker, new_content):
    """Replace block between markers, inserting markers if missing."""
    bi = html.find(begin_marker)
    ei = html.find(end_marker)
    if bi >= 0 and ei >= 0:
        return html[:bi] + begin_marker + "\n" + new_content + "\n            " + html[ei:]
    return None  # caller decides what to do


def strip_orphans_after(html, end_marker, stop_patterns):
    """Strip orphaned <details class="week-group"> markup that lives between
    `end_marker` and the next legitimate sibling boundary.

    Earlier versions of the dispatch system rendered week-groups directly into
    the page; when the marker contract was added, the renderer started writing
    new content between the markers but never cleaned up the original siblings
    that lived outside them. This idempotent strip handles that legacy.
    """
    end_idx = html.find(end_marker)
    if end_idx < 0:
        return html
    after = end_idx + len(end_marker)

    # Find the earliest legitimate stop pattern after the end marker.
    earliest = len(html)
    for pat in stop_patterns:
        idx = html.find(pat, after)
        if idx >= 0 and idx < earliest:
            earliest = idx

    section = html[after:earliest]
    # Only strip if there's actual orphan content (not just whitespace).
    if '<details class="week-group"' in section or '<div class="pick-row' in section:
        # Preserve newline + standard indentation before the stop pattern.
        return html[:after] + "\n\n            " + html[earliest:]
    return html


def install_or_replace_dispatch(html, nba_html, mlb_html):
    """Inject markers + replace blocks. If markers don't exist yet, do a one-time install."""
    nba_replaced = replace_section(html, NBA_BEGIN, NBA_END, nba_html)
    if nba_replaced is None:
        # First-time install: locate existing post-nba-picks block, wrap in markers
        m = re.search(r'(<details class="blog-card post-nba-picks"[^>]*>.*?</details>)', html, re.DOTALL)
        if not m:
            raise RuntimeError("Could not find existing NBA picks block to wrap.")
        wrapped = f'{NBA_BEGIN}\n{nba_html}\n            {NBA_END}'
        nba_replaced = html[:m.start()] + wrapped + html[m.end():]

    mlb_replaced = replace_section(nba_replaced, MLB_BEGIN, MLB_END, mlb_html)
    if mlb_replaced is None:
        m = re.search(r'(<details class="blog-card post-mlb-picks"[^>]*>.*?</details>)', nba_replaced, re.DOTALL)
        if not m:
            raise RuntimeError("Could not find existing MLB picks block to wrap.")
        wrapped = f'{MLB_BEGIN}\n{mlb_html}\n            {MLB_END}'
        mlb_replaced = nba_replaced[:m.start()] + wrapped + nba_replaced[m.end():]

    # Defensive cleanup: strip any orphaned week-group / pick-row markup that
    # may have been left outside the markers from the pre-marker dispatch era.
    # Idempotent: no-op if nothing orphaned is present.
    mlb_replaced = strip_orphans_after(
        mlb_replaced, NBA_END,
        stop_patterns=[MLB_BEGIN, '<!-- ═', '<details class="blog-card'],
    )
    mlb_replaced = strip_orphans_after(
        mlb_replaced, MLB_END,
        stop_patterns=['<details class="blog-card', '<!-- ═', '</main>', '</body>'],
    )

    return mlb_replaced


def main():
    with open(NBA_PATH) as f:
        nba_picks = json.load(f)
    with open(MLB_PATH) as f:
        mlb_picks = json.load(f)

    baselines = load_baselines()
    nba_baseline = baselines.get("nba")
    mlb_baseline = baselines.get("mlb")

    nba_html = render_sport_block(nba_picks, "nba", "#00FF55", baseline=nba_baseline)
    mlb_html = render_sport_block(mlb_picks, "mlb", "#FFEA00", baseline=mlb_baseline)

    with open(INDEX) as f:
        html = f.read()

    new_html = install_or_replace_dispatch(html, nba_html, mlb_html)

    with open(INDEX, "w") as f:
        f.write(new_html)

    nba_agg = aggregate(nba_picks, baseline=nba_baseline)
    mlb_agg = aggregate(mlb_picks, baseline=mlb_baseline)
    print(f"  NBA: {nba_agg['wins']}-{nba_agg['losses']} ({nba_agg['pending']}P) · {nba_agg['roi']:+.1f}% ROI")
    print(f"  MLB: {mlb_agg['wins']}-{mlb_agg['losses']} ({mlb_agg['pending']}P) · {mlb_agg['roi']:+.1f}% ROI")
    print(f"  Wrote {INDEX}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Calibration + CLV report for tracked picks.

Reads picks/mlb.json and picks/nba.json and reports, per confidence tier:
  - record, win%, ROI
  - average price and the break-even win% that price implies
  - realized edge (actual win% minus break-even win%)
  - CLV (closing line value) once closing lines are captured on picks

Positive realized edge means the tier is beating its prices. Break-even
comes from each pick's own odds, not a tier-wide average, so mixed
favorite/dog tiers are handled correctly.

CLV fields expected on picks (attached at settlement once snapshots exist):
  - closing_odds: American odds at last pre-start snapshot (ML picks)
  - closing_line: closing spread for the side taken (spread picks)

Usage:
  python3 scripts/report_calibration.py            # print report
  python3 scripts/report_calibration.py --json     # also write reports/calibration.json
"""

import json
import os
import sys
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PICK_FILES = {
    "mlb": os.path.join(REPO_ROOT, "picks", "mlb.json"),
    "nba": os.path.join(REPO_ROOT, "picks", "nba.json"),
}
REPORT_JSON = os.path.join(REPO_ROOT, "reports", "calibration.json")

MIN_TRACKED_CONF = 8


def implied_prob(american):
    """Break-even win probability for American odds."""
    if american is None:
        return None
    try:
        odds = float(str(american).replace("+", ""))
    except (TypeError, ValueError):
        return None
    if odds == 0:
        return None
    if odds < 0:
        return -odds / (-odds + 100.0)
    return 100.0 / (odds + 100.0)


def pick_clv(p):
    """CLV for one pick, or None if no closing data.

    ML picks: closing implied prob minus pick implied prob (positive = beat
    the close). Spread picks: pick line minus closing line for the side
    taken (positive = got the better number).
    """
    bet_type = p.get("bet_type")
    if bet_type == "ml":
        pick_ip = implied_prob(p.get("odds"))
        close_ip = implied_prob(p.get("closing_odds"))
        if pick_ip is None or close_ip is None:
            return None
        return close_ip - pick_ip
    if bet_type in ("spread", "total"):
        line = p.get("line")
        closing = p.get("closing_line")
        if line is None or closing is None:
            return None
        return float(line) - float(closing)
    return None


def load_picks(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def tier_stats(picks):
    """Aggregate one bucket of settled picks."""
    wins = sum(1 for p in picks if p["status"] == "win")
    losses = sum(1 for p in picks if p["status"] == "loss")
    pushes = sum(1 for p in picks if p["status"] == "push")
    decided = wins + losses
    risked = sum(float(p.get("units") or 0) for p in picks if p["status"] in ("win", "loss"))
    pl = sum(float(p.get("pl") or 0) for p in picks if p.get("pl") is not None)
    be_probs = [ip for ip in (implied_prob(p.get("odds")) for p in picks if p["status"] in ("win", "loss")) if ip is not None]
    clvs_ml = [c for c in (pick_clv(p) for p in picks if p.get("bet_type") == "ml") if c is not None]
    clvs_pts = [c for c in (pick_clv(p) for p in picks if p.get("bet_type") in ("spread", "total")) if c is not None]
    win_pct = wins / decided if decided else None
    break_even = sum(be_probs) / len(be_probs) if be_probs else None
    return {
        "n": len(picks),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "win_pct": win_pct,
        "break_even_pct": break_even,
        "realized_edge": (win_pct - break_even) if (win_pct is not None and break_even is not None) else None,
        "risked": risked,
        "pl": round(pl, 2),
        "roi": (pl / risked) if risked else None,
        "clv_ml_avg": (sum(clvs_ml) / len(clvs_ml)) if clvs_ml else None,
        "clv_ml_n": len(clvs_ml),
        "clv_pts_avg": (sum(clvs_pts) / len(clvs_pts)) if clvs_pts else None,
        "clv_pts_n": len(clvs_pts),
    }


def fmt_pct(x):
    return f"{x * 100:5.1f}%" if x is not None else "    —"


def report_sport(sport, picks):
    settled = [p for p in picks if p.get("status") in ("win", "loss", "push")]
    pending = [p for p in picks if p.get("status") == "pending"]
    tracked = [p for p in settled if int(p.get("conf") or 0) >= MIN_TRACKED_CONF]

    lines = []
    lines.append(f"\n{'=' * 74}")
    lines.append(f"{sport.upper()} — {len(settled)} settled ({len(tracked)} at C{MIN_TRACKED_CONF}+), {len(pending)} pending")
    lines.append(f"{'=' * 74}")
    header = f"{'tier':>5} {'n':>4} {'record':>9} {'win%':>6} {'brkevn':>6} {'edge':>6} {'ROI':>7} {'CLV':>12}"
    lines.append(header)
    lines.append("-" * len(header))

    by_tier = defaultdict(list)
    for p in tracked:
        by_tier[int(p["conf"])].append(p)

    out = {"tiers": {}, "settled": len(settled), "tracked": len(tracked), "pending": len(pending)}
    for conf in sorted(by_tier, reverse=True):
        s = tier_stats(by_tier[conf])
        out["tiers"][f"C{conf}"] = s
        clv_txt = "no close data"
        if s["clv_ml_n"]:
            clv_txt = f"{s['clv_ml_avg'] * 100:+.2f}% ({s['clv_ml_n']})"
        elif s["clv_pts_n"]:
            clv_txt = f"{s['clv_pts_avg']:+.2f}pt ({s['clv_pts_n']})"
        lines.append(
            f"  C{conf:>2} {s['n']:>4} {s['wins']:>4}-{s['losses']:<4} {fmt_pct(s['win_pct'])} "
            f"{fmt_pct(s['break_even_pct'])} {fmt_pct(s['realized_edge'])} "
            f"{fmt_pct(s['roi'])} {clv_txt:>12}"
        )

    total = tier_stats(tracked)
    out["total"] = total
    lines.append("-" * len(header))
    clv_txt = "no close data"
    if total["clv_ml_n"]:
        clv_txt = f"{total['clv_ml_avg'] * 100:+.2f}% ({total['clv_ml_n']})"
    elif total["clv_pts_n"]:
        clv_txt = f"{total['clv_pts_avg']:+.2f}pt ({total['clv_pts_n']})"
    lines.append(
        f"  ALL {total['n']:>4} {total['wins']:>4}-{total['losses']:<4} {fmt_pct(total['win_pct'])} "
        f"{fmt_pct(total['break_even_pct'])} {fmt_pct(total['realized_edge'])} "
        f"{fmt_pct(total['roi'])} {clv_txt:>12}"
    )

    # Price-band view: is any odds range dragging the record?
    bands = [("dogs (+)", lambda o: o > 0), ("-100..-150", lambda o: -150 <= o <= -100),
             ("-151..-200", lambda o: -200 <= o < -150), ("<-200", lambda o: o < -200)]
    lines.append(f"\n  by price band (C{MIN_TRACKED_CONF}+):")
    out["price_bands"] = {}
    for label, test in bands:
        band = []
        for p in tracked:
            try:
                o = float(str(p.get("odds")).replace("+", ""))
            except (TypeError, ValueError):
                continue
            if test(o):
                band.append(p)
        if not band:
            continue
        s = tier_stats(band)
        out["price_bands"][label] = s
        lines.append(
            f"  {label:>12} {s['n']:>4} {s['wins']:>4}-{s['losses']:<4} {fmt_pct(s['win_pct'])} "
            f"{fmt_pct(s['break_even_pct'])} {fmt_pct(s['realized_edge'])} {fmt_pct(s['roi'])}"
        )
    return "\n".join(lines), out


def main():
    write_json = "--json" in sys.argv
    full = {}
    for sport, path in PICK_FILES.items():
        picks = load_picks(path)
        text, data = report_sport(sport, picks)
        print(text)
        full[sport] = data
    print(
        "\nNotes: edge = actual win% minus break-even win% at the prices taken."
        "\nCLV appears once closing lines are captured (mlbsim/odds_snapshots.csv"
        "\nand nba_pipeline/data/line_snapshots.csv) and attached at settlement."
    )
    if write_json:
        os.makedirs(os.path.dirname(REPORT_JSON), exist_ok=True)
        with open(REPORT_JSON, "w") as f:
            json.dump(full, f, indent=2)
        print(f"\nWrote {os.path.relpath(REPORT_JSON, REPO_ROOT)}")


if __name__ == "__main__":
    main()

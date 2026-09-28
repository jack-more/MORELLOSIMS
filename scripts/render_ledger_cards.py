#!/usr/bin/env python3
"""MorelloSims ledger cards — tracked history per sport, receipt design system.

  python3 scripts/render_ledger_cards.py mlb|nba|nfl [--out DIR]

MLB leads with the live model era (picks/model_era.json) and lists the retired
era underneath; NBA splits the manual log from the auto-tracked ledger; NFL is
the blank 0-0 ledger. Every number is read from picks/*.json + baselines.json.
"""

import argparse
import json
import os
from datetime import date, datetime

from PIL import Image, ImageDraw

from render_cards_v2 import (
    REPO, W, H, INK, INK_SOFT, PAPER, PAPER_EDGE, POP_YELLOW, WIN_GREEN, LOSS_RED,
    BRAND_DOTS, font, text_w, fit_font, cement_background, ticket_shadow, ticket_paper,
    edge_vignette, offset_print_text, rail_microtype, barcode, qr_stub, brand_icon,
    brand_dots,
)

SPORT_RAIL = {"mlb": BRAND_DOTS[1], "nba": BRAND_DOTS[0], "nfl": (122, 74, 40)}
RAIL_TEXT = {"mlb": INK, "nba": INK, "nfl": (235, 233, 228)}


def load(name):
    return json.load(open(os.path.join(REPO, "picks", name)))


def agg(rows):
    w = sum(p["status"] == "win" for p in rows)
    l = sum(p["status"] == "loss" for p in rows)
    pu = sum(p["status"] == "push" for p in rows)
    risked = sum(p.get("units") or 0 for p in rows)
    pl = sum(p.get("pl") or 0 for p in rows)
    return w, l, pu, risked, pl


def settled(rows):
    return sorted((p for p in rows if p.get("status") in ("win", "loss", "push")),
                  key=lambda p: (p["date"], p["id"]))


def md(s):
    return datetime.strptime(s, "%Y-%m-%d").strftime("%b %-d").upper()


def rec(w, l, pu=0):
    return f"{w}-{l}" + (f"-{pu}" if pu else "")


def signed(x, dec=0):
    return f"{'+' if x >= 0 else '−'}{abs(x):,.{dec}f}"


# ── shared ticket frame ────────────────────────────────────────────────────

def frame(sport, subtitle):
    img = cement_background()
    tx0, ty0, tx1, ty1 = 90, 90, W - 90, H - 90
    notch_y = ty1 - 240
    ticket_shadow(img, (tx0, ty0, tx1, ty1))
    ticket_paper(img, (tx0, ty0, tx1, ty1), notch_y=notch_y)
    edge_vignette(img, (tx0, ty0, tx1, ty1))
    d = ImageDraw.Draw(img)

    band_h = 128
    d.rounded_rectangle((tx0, ty0, tx1, ty0 + band_h + 26), radius=26, fill=INK)
    d.rectangle((tx0, ty0 + band_h - 10, tx1, ty0 + band_h), fill=INK)
    d.rectangle((tx0 + 5, ty0 + band_h, tx1 - 5, ty0 + band_h + 5), fill=PAPER)
    x = tx0 + 58
    icon = brand_icon(78)
    hx = x
    if icon:
        img.paste(icon, (x, ty0 + 26), icon)
        hx = x + icon.width + 22
        d = ImageDraw.Draw(img)
    d.text((hx, ty0 + 30), "MORELLO SIMS", font=font("black", 42), fill=PAPER)
    d.text((hx, ty0 + 86), f"OFFICIAL LEDGER · {sport.upper()}", font=font("mono_b", 20), fill=POP_YELLOW)
    today = date.today().strftime("%b %d, %Y").upper()
    d.text((tx1 - 50 - text_w(d, today, font("mono_b", 26)), ty0 + 34), today, font=font("mono_b", 26), fill=PAPER)
    d.text((tx1 - 50 - text_w(d, subtitle, font("mono", 22)), ty0 + 78), subtitle,
           font=font("mono", 22), fill=(160, 158, 152))

    rail = SPORT_RAIL[sport]
    d.rounded_rectangle((tx0, ty0, tx0 + 26, ty1), radius=26, fill=rail)
    d.rectangle((tx0 + 13, ty0, tx0 + 26, ty1), fill=rail)
    ledger_id = f"LEDGER-{sport.upper()}-{date.today().isoformat()}"
    rail_microtype(img, tx0 + 1, notch_y - 30, f"№ {ledger_id}", fill=RAIL_TEXT[sport])

    # stub
    d = ImageDraw.Draw(img)
    sy = notch_y + 32
    qr_stub(img, (x, sy), f"https://morellosims.com/?utm_source=card&utm_medium=social"
                          f"&utm_campaign=ledger&utm_content={sport}", size=168)
    d = ImageDraw.Draw(img)
    bx = x + 196
    barcode(d, (bx, sy + 8, bx + 130, sy + 76), ledger_id)
    d.text((bx, sy + 92), ledger_id, font=font("mono", 17), fill=INK_SOFT)
    d.text((bx, sy + 124), "SCAN FOR EVERY PICK", font=font("mono_b", 18), fill=INK)
    d.text((tx1 - 50 - text_w(d, "MORELLOSIMS.COM", font("black", 34)), sy + 4),
           "MORELLOSIMS.COM", font=font("black", 34), fill=INK)
    tag = "EVERY PICK TRACKED · SETTLED IN PUBLIC"
    d.text((tx1 - 50 - text_w(d, tag, font("mono_b", 19)), sy + 60), tag, font=font("mono_b", 19), fill=INK_SOFT)
    brand_dots(d, tx1 - 50 - 52, sy + 116)
    return img, (tx0, ty0, tx1, ty1), x, notch_y


def stat_row(d, x, y, right, cells):
    colw = (right - x) / len(cells)
    for i, (val, label, color) in enumerate(cells):
        cx = x + i * colw
        d.text((cx, y), val, font=font("black", 50), fill=color)
        d.text((cx + 2, y + 70), label, font=font("mono_b", 20), fill=INK_SOFT)


def sparkline(d, box, series):
    x0, y0, x1, y1 = box
    lo, hi = min(0, *series), max(0, *series)
    span = (hi - lo) or 1
    ys = lambda v: y1 - (v - lo) / span * (y1 - y0)
    zy = ys(0)
    for dx in range(int(x0), int(x1), 18):
        d.line((dx, zy, dx + 8, zy), fill=PAPER_EDGE, width=3)
    n = len(series)
    pts = [(x0 + i * (x1 - x0) / max(n - 1, 1), ys(v)) for i, v in enumerate(series)]
    d.line(pts, fill=INK, width=5, joint="curve")
    ex, ey = pts[-1]
    col = WIN_GREEN if series[-1] >= 0 else LOSS_RED
    d.ellipse((ex - 10, ey - 10, ex + 10, ey + 10), fill=col, outline=INK, width=3)


# ── cards ──────────────────────────────────────────────────────────────────

def card_mlb():
    era = load("model_era.json")
    start = era["start_date"]
    rows = settled(load("mlb.json"))
    live = [p for p in rows if p["date"] >= start]
    old = [p for p in rows if p["date"] < start]
    w, l, pu, risked, pl = agg(live)
    ow, ol, opu, orisk, opl = agg(old)
    base = load("baselines.json")["mlb"]
    label = era.get("short_label") or era.get("label", "").replace(" MODEL", "")

    img, (tx0, ty0, tx1, ty1), x, notch_y = frame("mlb", f"{md(start)} → {md(live[-1]['date'])}")
    d = ImageDraw.Draw(img)
    right = tx1 - 50
    d.text((x, ty0 + 186), f"{label} MODEL · CURRENT ERA", font=font("cond_sb", 42), fill=INK_SOFT)
    offset_print_text(img, (x, ty0 + 236), rec(w, l, pu),
                      fit_font(d, rec(w, l, pu), "black", 190, right - x, min_size=110),
                      accent=POP_YELLOW, off=(10, 10))
    d = ImageDraw.Draw(img)
    roi = 100 * pl / risked if risked else 0
    stat_row(d, x, ty0 + 480, right, [
        (signed(pl), "NET $PP", WIN_GREEN if pl >= 0 else LOSS_RED),
        (f"{risked:,}", "$PP RISKED", INK),
        (f"{signed(roi, 1)}%", "ROI", WIN_GREEN if roi >= 0 else LOSS_RED),
    ])
    d.text((x, ty0 + 610), "RUNNING $PP · EVERY PICK", font=font("mono_b", 20), fill=INK_SOFT)
    run, s = [0], 0
    for p in live:
        s += p.get("pl") or 0
        run.append(s)
    sparkline(d, (x + 4, ty0 + 650, right - 14, ty0 + 760), run)

    y = ty0 + 800
    d.line((x, y, right, y), fill=PAPER_EDGE, width=3)
    oroi = 100 * opl / orisk if orisk else 0
    lines = [
        f"V1 MODEL · {md(old[0]['date'])}–{md(old[-1]['date'])} · {rec(ow, ol, opu)} · {signed(oroi, 1)}% · RETIRED",
        f"APRIL · MANUAL LOG, PRE-TRACKING · {rec(base['wins'], base['losses'])}",
    ]
    for i, t in enumerate(lines):
        d.text((x, y + 22 + i * 38), t, font=fit_font(d, t, "mono_b", 22, right - x, min_size=16), fill=INK_SOFT)
    return img


def card_nba():
    rows = settled(load("nba.json"))
    base = load("baselines.json")["nba"]
    tw, tl, tpu, trisk, tpl = agg(rows)
    bw, bl, brisk, bpl = base["wins"], base["losses"], base["risked"], base["pl"]
    w, l, risked, pl = bw + tw, bl + tl, brisk + trisk, bpl + tpl
    since = base["since"]
    season = f"{since[:4]}-{int(since[2:4]) + 1:02d}"

    img, (tx0, ty0, tx1, ty1), x, notch_y = frame("nba", f"{md(since)} → {md(rows[-1]['date'])}")
    d = ImageDraw.Draw(img)
    right = tx1 - 50
    d.text((x, ty0 + 186), f"{season} SEASON · FULL LEDGER", font=font("cond_sb", 42), fill=INK_SOFT)
    offset_print_text(img, (x, ty0 + 236), rec(w, l, tpu),
                      fit_font(d, rec(w, l, tpu), "black", 190, right - x, min_size=110),
                      accent=BRAND_DOTS[0], off=(10, 10))
    d = ImageDraw.Draw(img)
    roi = 100 * pl / risked
    stat_row(d, x, ty0 + 480, right, [
        (signed(pl), "NET $PP", WIN_GREEN if pl >= 0 else LOSS_RED),
        (f"{risked:,}", "$PP RISKED", INK),
        (f"{signed(roi, 1)}%", "ROI", WIN_GREEN if roi >= 0 else LOSS_RED),
    ])

    y = ty0 + 620
    d.text((x, y), "HOW IT WAS LOGGED", font=font("mono_b", 20), fill=INK_SOFT)
    segs = [
        (f"{md(since)} – APR 30", "MANUAL LOG", rec(bw, bl), bpl, brisk),
        (f"{md(rows[0]['date'])} – {md(rows[-1]['date'])}", "AUTO-TRACKED", rec(tw, tl, tpu), tpl, trisk),
    ]
    for i, (when, how, r, p, rk) in enumerate(segs):
        ry = y + 44 + i * 84
        d.rounded_rectangle((x, ry, right, ry + 70), radius=12, outline=INK, width=3)
        d.text((x + 20, ry + 8), how, font=font("mono_b", 22), fill=INK)
        d.text((x + 20, ry + 38), when, font=font("mono", 19), fill=INK_SOFT)
        tail = f"{r}   {signed(p)} $PP   {signed(100 * p / rk, 1)}%"
        tf = font("mono_b", 26)
        d.text((right - 20 - text_w(d, tail, tf), ry + 20), tail, font=tf, fill=INK)
    return img


def card_nfl():
    img, (tx0, ty0, tx1, ty1), x, notch_y = frame("nfl", "FRESH LEDGER")
    d = ImageDraw.Draw(img)
    right = tx1 - 50
    d.text((x, ty0 + 186), "NFL · OPENING THE BOOKS", font=font("cond_sb", 42), fill=INK_SOFT)
    offset_print_text(img, (x, ty0 + 236), "0-0", font("black", 190), accent=(196, 140, 90), off=(10, 10))
    d = ImageDraw.Draw(img)
    stat_row(d, x, ty0 + 480, right, [
        ("0", "NET $PP", INK),
        ("0", "$PP RISKED", INK),
        ("—", "ROI", INK),
    ])
    y = ty0 + 620
    d.text((x, y), "PICK 001", font=font("mono_b", 20), fill=INK_SOFT)
    d.rounded_rectangle((x, y + 40, right, y + 150), radius=14, outline=INK, width=4)
    t = "DROPS TONIGHT"
    tf = font("black", 58)
    d.text((x + (right - x - text_w(d, t, tf)) / 2, y + 60), t, font=tf, fill=INK)
    rules = "FLAT 50 $PP · LOGGED BEFORE KICKOFF · NOTHING DELETED"
    d.text((x, y + 176), rules, font=fit_font(d, rules, "mono_b", 22, right - x, min_size=16), fill=INK_SOFT)
    return img


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("sport", choices=["mlb", "nba", "nfl"])
    ap.add_argument("--out", default=os.path.join(REPO, "posters", "v2"))
    a = ap.parse_args()
    img = {"mlb": card_mlb, "nba": card_nba, "nfl": card_nfl}[a.sport]()
    os.makedirs(a.out, exist_ok=True)
    out = os.path.join(a.out, f"ledger-{a.sport}-{date.today().isoformat()}.png")
    img.save(out)
    print(out)

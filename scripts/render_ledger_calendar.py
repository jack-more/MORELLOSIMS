#!/usr/bin/env python3
"""Ledger calendar: every day of the NBA pick-by-pick ledger as a tile.

Ad format after a high-performing affiliate post (a monthly profit calendar,
every day a tile with its P/L, month totals in the header) — but built from
the public ledger, so red days show red. Units are $PP, graded at the posted
price, nothing deleted (nba_pipeline/data/picks.csv).

  python3 scripts/render_ledger_calendar.py [--out PATH]
"""

import argparse
import calendar
import collections
import csv
import os
import sys
from datetime import date

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from render_cards_v2 import text_w  # noqa: E402
from render_series_card import REPO, S, W, H, BG, CREAM, INK, WIN, LOSS, s, F, paper_grain, _mix  # noqa: E402

MUTED = (112, 102, 90)
UNIT = 50.0  # $PP per unit, the standard stake
EMPTY = (228, 220, 202)


def daily():
    out, n = collections.defaultdict(float), collections.Counter()
    for r in csv.DictReader(open(os.path.join(REPO, "nba_pipeline", "data", "picks.csv"))):
        if r["result"] in ("W", "L", "P"):
            out[r["date"]] += float(r["profit"] or 0) / UNIT   # units (1u = 50 $PP)
            n[r["date"]] += 1
    return out, n


def _record():
    c = collections.Counter(r["result"] for r in csv.DictReader(open(os.path.join(REPO, "nba_pipeline", "data", "picks.csv"))))
    return f"{c['W']}-{c['L']}" + (f"-{c['P']}" if c["P"] else "")


def month_block(img, x0, y0, w, h, ym, pl):
    d = ImageDraw.Draw(img)
    y, m = int(ym[:4]), int(ym[5:])
    days = {k: v for k, v in pl.items() if k.startswith(ym)}
    tot = sum(days.values())
    d.text((x0, y0 + s(4)), date(y, m, 1).strftime("%b").upper(), font=F("mono_b", 20), fill=INK)
    tt = f"{tot:+,.1f}u"
    d.text((x0 + w - text_w(d, tt, F("black", 26)), y0 - s(2)), tt, font=F("black", 26), fill=WIN if tot >= 0 else LOSS)
    gy = y0 + s(42)
    cw = (w - s(4) * 6) / 7
    weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(y, m)
    ch = min(cw * 1.08, (h - s(42) - s(4) * (len(weeks) - 1)) / len(weeks))
    for wi, wk in enumerate(weeks):
        for di, dd in enumerate(wk):
            if not dd:
                continue
            cx, cy = x0 + di * (cw + s(4)), gy + wi * (ch + s(4))
            key = f"{ym}-{dd:02d}"
            v = days.get(key)
            fill = EMPTY if v is None else (WIN if v > 0 else LOSS if v < 0 else MUTED)
            d.rounded_rectangle((cx, cy, cx + cw, cy + ch), radius=s(5), fill=fill)
            col = MUTED if v is None else CREAM
            d.text((cx + s(3), cy + s(2)), str(dd), font=F("mono_b", 10), fill=col)
            if v is not None:
                lab = "0" if abs(v) < 0.05 else f"{v:+.1f}"
                f = F("cond", 15)
                d.text((cx + (cw - text_w(d, lab, f)) / 2, cy + ch - s(19)), lab, font=f, fill=CREAM)


def render():
    pl, n = daily()
    months = sorted({k[:7] for k in pl})
    img = Image.new("RGBA", (W, H), BG + (255,))
    x0, y0, x1, y1 = s(44), s(44), W - s(44), H - s(44)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x0, y0 + s(16), x1, y1 + s(16)), radius=s(54), fill=(0, 0, 0, 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(s(22))))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x0, y0, x1, y1), radius=s(54), fill=CREAM + (255,))
    L, R = s(92), W - s(92)

    d.text((L, s(96)), "MORELLO SIMS · NBA LEDGER", font=F("mono_b", 24), fill=INK)
    green = sum(v > 0 for v in pl.values())
    red = sum(v < 0 for v in pl.values())
    up = all(sum(v for k, v in pl.items() if k.startswith(m)) > 0 for m in months)
    head = "EVERY MONTH UP." if up else "EVERY DAY, LOGGED."
    from render_cards_v2 import fit_font
    d.text((L, s(140)), head, font=fit_font(d, head, "black", s(84), R - L, min_size=s(48)), fill=INK)
    tail = "RED DAYS INCLUDED."
    d.text((L, s(236)), tail, font=fit_font(d, tail, "black", s(84), R - L, min_size=s(48)), fill=LOSS)
    total = sum(pl.values())
    sub = f"{green} green days · {red} red · {total:+,.1f}u · every pick logged, none deleted"
    d.text((L, s(352)), sub, font=F("mono_b", 22), fill=MUTED)

    cols = 3
    gx, gy = s(26), s(30)
    bw = (R - L - gx * (cols - 1)) / cols
    bh = s(330)
    top = s(420)
    for i, ym in enumerate(months[:5]):
        cx = L + (i % cols) * (bw + gx)
        cy = top + (i // cols) * (bh + gy)
        month_block(img, cx, cy, bw, bh, ym, pl)
    d = ImageDraw.Draw(img)
    # sixth slot: the totals, same weight as a month
    sx, sy = L + 2 * (bw + gx), top + (bh + gy)
    d.rounded_rectangle((sx, sy, sx + bw, sy + bh - s(30)), radius=s(22), fill=INK)
    d.text((sx + s(24), sy + s(26)), "ALL PICKS", font=F("mono_b", 20), fill=CREAM)
    wl = sum(1 for _ in [])
    big = f"{total:+,.1f}u"
    d.text((sx + s(24), sy + s(70)), big, font=fit_font(d, big, "black", s(64), bw - s(48), min_size=s(36)), fill=(120, 220, 160))
    rec = _record()
    d.text((sx + s(24), sy + s(160)), rec, font=F("black", 40), fill=CREAM)
    d.text((sx + s(24), sy + s(222)), f"{green} up days · {red} down", font=F("mono_b", 18), fill=CREAM)
    foot = "FLAT 1U · GRADED AT THE POSTED PRICE · MORELLOSIMS.COM"
    d.text(((W - text_w(d, foot, F("mono_b", 22))) / 2, s(1236)), foot, font=F("mono_b", 22), fill=INK)
    return paper_grain(img.convert("RGB")).resize((1080, 1350), Image.LANCZOS)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "posters", "v2", "nba-ledger-calendar.png"))
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    render().save(a.out)
    print(a.out)

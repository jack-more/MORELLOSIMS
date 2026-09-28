#!/usr/bin/env python3
"""Series-system sheets: the day's checklist and the running set record.

Same stock, inks and type as the series card (render_series_card.py):
cream card, vermilion bands, yellow diamond, near-black ink.

  python3 scripts/render_series_sheets.py checklist --date 2026-09-26 [--out DIR]
  python3 scripts/render_series_sheets.py record [--out DIR]
"""

import argparse
import json
import os
from datetime import datetime

from PIL import Image, ImageDraw, ImageFilter

from render_cards_v2 import text_w, fit_font, team_logo
from render_series_card import (
    REPO, S, W, H, BG, CREAM, RED, YELLOW, INK, WIN, LOSS,
    s, F, load_picks, team_ref, keyline_mark, paper_grain, baseball, final_str,
)

MUTED = (120, 108, 96)


def era_start():
    return json.load(open(os.path.join(REPO, "picks", "model_era.json")))["start_date"]


def set_numbers():
    return {p["id"]: i for i, p in enumerate(load_picks(), 1)}


def odds_of(p):
    o = str(p.get("odds") or "")
    return o if not o or o.startswith(("+", "-")) else "+" + o


def stock():
    """Card stock + printed frame, shared by every sheet."""
    img = Image.new("RGBA", (W, H), BG + (255,))
    cx0, cy0, cx1, cy1 = s(44), s(44), W - s(44), H - s(44)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((cx0, cy0 + s(16), cx1, cy1 + s(16)), radius=s(54), fill=(0, 0, 0, 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(s(22))))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((cx0, cy0, cx1, cy1), radius=s(54), fill=CREAM + (255,))
    frame = (s(92), s(92), W - s(92), H - s(92))
    return img, frame


def header(img, frame, kicker, title, right):
    fx0, fy0, fx1, fy1 = frame
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(band).rectangle((fx0, fy0, fx1, fy0 + s(250)), fill=RED)
    clip = Image.new("L", (W, H), 0)
    ImageDraw.Draw(clip).rounded_rectangle(frame, radius=s(40), fill=255)
    band.putalpha(Image.composite(band.getchannel("A"), Image.new("L", (W, H), 0), clip))
    img.alpha_composite(band)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(frame, radius=s(40), outline=RED, width=s(3))
    baseball(d, fx0 + s(96), fy0 + s(124), s(62))
    # cream ball on red: redraw the ball body in cream with red seams
    d.ellipse((fx0 + s(34), fy0 + s(62), fx0 + s(158), fy0 + s(186)), fill=CREAM)
    baseball_seams(d, fx0 + s(96), fy0 + s(124), s(62))
    x = fx0 + s(190)
    d.text((x, fy0 + s(42)), kicker, font=F("mono_b", 22), fill=CREAM)
    tf = fit_font(d, title, "cond", s(112), fx1 - s(40) - x, min_size=s(60))
    d.text((x, fy0 + s(74)), title, font=tf, fill=INK)
    rf = F("mono_b", 22)
    d.text((fx1 - s(40) - text_w(d, right, rf), fy0 + s(42)), right, font=rf, fill=CREAM)
    return fy0 + s(250)


def baseball_seams(d, cx, cy, r):
    import math
    for side in (-1, 1):
        R, ox = r * 1.05, cx + side * r * 1.55
        pts = [(ox + R * math.cos(math.radians(180 + t if side > 0 else t)),
                cy + R * math.sin(math.radians(180 + t if side > 0 else t))) for t in range(-38, 39, 2)]
        pts = [p for p in pts if (p[0] - cx) ** 2 + (p[1] - cy) ** 2 < (r * 0.94) ** 2]
        d.line(pts, fill=RED, width=s(3))


def footer(img, frame, left, right):
    fx0, fy0, fx1, fy1 = frame
    d = ImageDraw.Draw(img)
    y = fy1 - s(92)
    d.line((fx0 + s(40), y, fx1 - s(40), y), fill=RED, width=s(3))
    f = F("black", 30)
    d.text((fx0 + s(40), y + s(28)), left, font=f, fill=INK)
    mf = F("mono_b", 20)
    d.text((fx1 - s(40) - text_w(d, right, mf), y + s(36)), right, font=mf, fill=MUTED)


def finish(img):
    return paper_grain(img.convert("RGB")).resize((W // S, H // S), Image.LANCZOS)


# ── checklist: the day's board ─────────────────────────────────────────────

def checklist(date, sport="mlb"):
    picks = [p for p in load_picks() if p.get("date") == date and int(p.get("conf") or 0) >= 8]
    if not picks:
        raise SystemExit(f"no picks for {date}")
    picks.sort(key=lambda p: (-int(p.get("conf") or 0), p["id"]))
    nums = set_numbers()
    img, frame = stock()
    fx0, fy0, fx1, fy1 = frame
    day = datetime.strptime(date, "%Y-%m-%d")
    top = header(img, frame, f"MORELLO SIMS · {day.year} MLB SERIES", "TODAY'S CHECKLIST",
                 day.strftime("%a %b %-d").upper())
    d = ImageDraw.Draw(img)

    shown = picks[:6]
    area_top, area_bot = top + s(40), fy1 - s(120)
    row_h = min(s(190), (area_bot - area_top) // max(len(shown), 1))
    area_top += (area_bot - area_top - row_h * len(shown)) // 2      # centre the block
    for i, p in enumerate(shown):
        y = area_top + i * row_h
        side = p["side"]
        opp = p["home"] if side == p["away"] else p["away"]
        city, name, _ = team_ref(side)
        st = p.get("status")
        # checkbox
        bx, by, bs = fx0 + s(44), y + (row_h - s(56)) // 2, s(56)
        d.rounded_rectangle((bx, by, bx + bs, by + bs), radius=s(8), outline=INK, width=s(4))
        if st in ("win", "loss", "push"):
            col = WIN if st == "win" else LOSS if st == "loss" else INK
            d.rounded_rectangle((bx, by, bx + bs, by + bs), radius=s(8), fill=col)
            w8 = s(7)
            if st == "win":      # drawn check — the fonts carry no ✓ glyph
                d.line([(bx + s(13), by + s(29)), (bx + s(24), by + s(41)), (bx + s(44), by + s(15))],
                       fill=CREAM, width=w8, joint="curve")
            elif st == "loss":
                d.line((bx + s(16), by + s(16), bx + s(40), by + s(40)), fill=CREAM, width=w8)
                d.line((bx + s(40), by + s(16), bx + s(16), by + s(40)), fill=CREAM, width=w8)
            else:
                d.line((bx + s(14), by + bs / 2, bx + s(42), by + bs / 2), fill=CREAM, width=w8)
        # logo
        logo = team_logo(side, 200)
        lx = bx + bs + s(30)
        if logo:
            logo = logo.resize((logo.width * S, logo.height * S), Image.LANCZOS)
            mark_img = keyline_mark(logo, row_h - s(40), line=6)
            img.alpha_composite(mark_img, (lx, y + (row_h - mark_img.height) // 2))
            d = ImageDraw.Draw(img)
        tx = lx + row_h
        meta = f"No. {nums.get(p['id'], '')} · {'at' if side == p['away'] else 'vs'} {opp} · C{p.get('conf')}"
        d.text((tx, y + row_h / 2 - s(56)), meta,
               font=fit_font(d, meta, "mono_b", s(22), ox_left(d, p) - tx - s(24), min_size=s(16)), fill=MUTED)
        nf = fit_font(d, name, "cond", s(84), ox_left(d, p) - tx - s(30), min_size=s(44))
        d.text((tx, y + row_h / 2 - s(28)), name, font=nf, fill=INK)
        # price in a yellow tab
        o = odds_of(p)
        of = F("cond", 72)
        ow = text_w(d, o, of) + s(40)
        ox1 = fx1 - s(40)
        d.rounded_rectangle((ox1 - ow, y + row_h / 2 - s(46), ox1, y + row_h / 2 + s(46)), radius=s(12), fill=YELLOW)
        d.text((ox1 - ow + s(20), y + row_h / 2 - s(44)), o, font=of, fill=INK)
        if st in ("win", "loss", "push"):
            fin = final_str(p)
            ff = F("mono_b", 20)
            d.text((ox1 - ow / 2 - text_w(d, fin, ff) / 2, y + row_h / 2 + s(54)), fin, font=ff, fill=INK)
        if i < len(shown) - 1:
            for dx in range(fx0 + s(44), fx1 - s(40), s(22)):
                d.line((dx, y + row_h, dx + s(10), y + row_h), fill=(214, 200, 180), width=s(2))

    w, l, pl = era_totals()
    extra = f" · +{len(picks) - 6} more on site" if len(picks) > 6 else ""
    footer(img, frame, "MORELLOSIMS.COM", f"SINCE {md(era_start())}: {w}-{l} · {pl:+g} $PP{extra}")
    return finish(img)


def ox_left(d, p):
    """Left edge of the price tab, so the team name never runs under it."""
    return W - s(92) - s(40) - (text_w(d, odds_of(p), F("cond", 72)) + s(40))


def md(iso):
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %-d").upper()


def era_totals():
    start = era_start()
    rows = [p for p in load_picks() if p["date"] >= start and p.get("status") in ("win", "loss")]
    w = sum(p["status"] == "win" for p in rows)
    return w, len(rows) - w, round(sum(p.get("pl") or 0 for p in rows), 2)


# ── record: the running set ────────────────────────────────────────────────

def record():
    start = era_start()
    rows = [p for p in load_picks() if p["date"] >= start and p.get("status") in ("win", "loss", "push")]
    w = sum(p["status"] == "win" for p in rows)
    l = sum(p["status"] == "loss" for p in rows)
    pu = sum(p["status"] == "push" for p in rows)
    risked = sum(p.get("units") or 0 for p in rows)
    pl = sum(p.get("pl") or 0 for p in rows)
    last = max(p["date"] for p in rows)

    img, frame = stock()
    fx0, fy0, fx1, fy1 = frame
    top = header(img, frame, f"MORELLO SIMS · {start[:4]} MLB SERIES", "THE SET SO FAR",
                 f"{md(start)} → {md(last)}")
    d = ImageDraw.Draw(img)
    mx = (fx0 + fx1) // 2
    my = top + s(300)
    R = s(250)
    d.polygon([(mx, my - R), (mx + R, my), (mx, my + R), (mx - R, my)], fill=YELLOW)
    rec = f"{w}-{l}" + (f"-{pu}" if pu else "")
    rf = fit_font(d, rec, "cond", s(210), int(R * 1.3), min_size=s(90))
    bb = d.textbbox((0, 0), rec, font=rf)
    d.text((mx - (bb[2] - bb[0]) / 2 - bb[0], my - (bb[3] - bb[1]) / 2 - bb[1] - s(14)), rec, font=rf, fill=INK)
    lab = f"{len(rows)} CARDS SETTLED"
    d.text((mx - text_w(d, lab, F("mono_b", 22)) / 2, my + s(96)), lab, font=F("mono_b", 22), fill=INK)

    y = my + R + s(60)
    cells = [(f"{pl:+,.0f}", "NET $PP", WIN if pl >= 0 else LOSS),
             (f"{risked:,}", "$PP RISKED", INK),
             (f"{100 * pl / risked:+.1f}%" if risked else "–", "ROI", WIN if pl >= 0 else LOSS)]
    colw = (fx1 - fx0 - s(80)) / 3
    for i, (v, lab, col) in enumerate(cells):
        cx = fx0 + s(40) + colw * i + colw / 2
        vf = F("cond", 92)
        d.text((cx - text_w(d, v, vf) / 2, y), v, font=vf, fill=col)
        d.text((cx - text_w(d, lab, F("mono_b", 22)) / 2, y + s(112)), lab, font=F("mono_b", 22), fill=MUTED)
    footer(img, frame, "MORELLOSIMS.COM", "EVERY PICK LOGGED BEFORE THE GAME")
    return finish(img)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet", choices=["checklist", "record"])
    ap.add_argument("--date")
    ap.add_argument("--out", default=os.path.join(REPO, "posters", "v2"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.sheet == "checklist":
        date = a.date or datetime.now().strftime("%Y-%m-%d")
        img, name = checklist(date), f"checklist-{date}.png"
    else:
        img, name = record(), f"record-{datetime.now().strftime('%Y-%m-%d')}.png"
    path = os.path.join(a.out, name)
    img.save(path)
    print(path)

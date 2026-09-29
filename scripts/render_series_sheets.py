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
    REPO, S, W, H, BG, CREAM, INK, WIN, LOSS, palette,
    s, F, load_picks, team_ref, keyline_mark, paper_grain, baseball, final_str,
)

MUTED = (120, 108, 96)
BLUE = (18, 56, 214)        # house blue (brand guide): sheets + card back
BLUE_DEEP = (12, 38, 150)


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


def header(img, frame, kicker, title, right, sport="mlb"):
    fx0, fy0, fx1, fy1 = frame
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(band).rectangle((fx0, fy0, fx1, fy0 + s(250)), fill=BLUE)
    clip = Image.new("L", (W, H), 0)
    ImageDraw.Draw(clip).rounded_rectangle(frame, radius=s(40), fill=255)
    band.putalpha(Image.composite(band.getchannel("A"), Image.new("L", (W, H), 0), clip))
    img.alpha_composite(band)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(frame, radius=s(40), outline=BLUE, width=s(3))
    sport_glyph(d, sport, fx0 + s(96), fy0 + s(124), s(62))
    x = fx0 + s(190)
    d.text((x, fy0 + s(42)), kicker, font=F("mono_b", 22), fill=CREAM)
    tf = fit_font(d, title, "cond", s(112), fx1 - s(40) - x, min_size=s(60))
    d.text((x, fy0 + s(74)), title, font=tf, fill=CREAM)
    rf = F("mono_b", 22)
    d.text((fx1 - s(40) - text_w(d, right, rf), fy0 + s(42)), right, font=rf, fill=CREAM)
    return fy0 + s(250)


def sport_glyph(d, sport, cx, cy, r):
    """Cream ball in the header band, lines in house blue."""
    w = s(3)
    if sport == "nfl":
        box = (cx - r * 1.15, cy - r * 0.72, cx + r * 1.15, cy + r * 0.72)
        d.ellipse(box, fill=CREAM)
        d.line((cx - r * 0.55, cy, cx + r * 0.55, cy), fill=BLUE, width=w)
        for i in range(-2, 3):
            x = cx + i * r * 0.2
            d.line((x, cy - r * 0.16, x, cy + r * 0.16), fill=BLUE, width=w)
        for sx in (-1, 1):
            x = cx + sx * r * 0.82
            d.line((x, cy - r * 0.5, x, cy + r * 0.5), fill=BLUE, width=w)
        return
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=CREAM)
    if sport == "nba":
        d.line((cx, cy - r, cx, cy + r), fill=BLUE, width=w)
        d.line((cx - r, cy, cx + r, cy), fill=BLUE, width=w)
        for sx in (-1, 1):
            d.arc((cx + sx * r * 0.55 - r * 0.75, cy - r * 0.95, cx + sx * r * 0.55 + r * 0.75, cy + r * 0.95),
                  90 if sx > 0 else 270, 270 if sx > 0 else 90, fill=BLUE, width=w)
        return
    baseball_seams(d, cx, cy, r)


def baseball_seams(d, cx, cy, r):
    import math
    for side in (-1, 1):
        R, ox = r * 1.05, cx + side * r * 1.55
        pts = [(ox + R * math.cos(math.radians(180 + t if side > 0 else t)),
                cy + R * math.sin(math.radians(180 + t if side > 0 else t))) for t in range(-38, 39, 2)]
        pts = [p for p in pts if (p[0] - cx) ** 2 + (p[1] - cy) ** 2 < (r * 0.94) ** 2]
        d.line(pts, fill=BLUE, width=s(3))


def footer(img, frame, left, right):
    fx0, fy0, fx1, fy1 = frame
    d = ImageDraw.Draw(img)
    y = fy1 - s(92)
    d.line((fx0 + s(40), y, fx1 - s(40), y), fill=BLUE, width=s(3))
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
        pal = palette(side)
        d.rounded_rectangle((ox1 - ow, y + row_h / 2 - s(46), ox1, y + row_h / 2 + s(46)), radius=s(12), fill=pal["P"])
        d.text((ox1 - ow + s(20), y + row_h / 2 - s(44)), o, font=of, fill=pal["on_P"])
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
    d.polygon([(mx + s(4), my - R + s(3)), (mx + R + s(4), my + s(3)), (mx + s(4), my + R + s(3)), (mx - R + s(4), my + s(3))], fill=BLUE_DEEP)
    d.polygon([(mx, my - R), (mx + R, my), (mx, my + R), (mx - R, my)], fill=BLUE)
    rec = f"{w}-{l}" + (f"-{pu}" if pu else "")
    rf = fit_font(d, rec, "cond", s(210), int(R * 1.3), min_size=s(90))
    bb = d.textbbox((0, 0), rec, font=rf)
    d.text((mx - (bb[2] - bb[0]) / 2 - bb[0], my - (bb[3] - bb[1]) / 2 - bb[1] - s(14)), rec, font=rf, fill=CREAM)
    lab = f"{len(rows)} CARDS SETTLED"
    d.text((mx - text_w(d, lab, F("mono_b", 22)) / 2, my + s(96)), lab, font=F("mono_b", 22), fill=CREAM)

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


# ── ledger: tracked history per sport ──────────────────────────────────────

def _agg(rows):
    w = sum(p["status"] == "win" for p in rows)
    l = sum(p["status"] == "loss" for p in rows)
    pu = sum(p["status"] == "push" for p in rows)
    rk = sum(p.get("units") or 0 for p in rows)
    pl = sum(p.get("pl") or 0 for p in rows)
    return w, l, pu, rk, pl


def _rec(w, l, pu=0):
    return f"{w}-{l}" + (f"-{pu}" if pu else "")


def ledger(sport):
    """Headline = tracked picks of the live model only; manual logs and
    retired eras are listed underneath, never blended into the headline."""
    base = json.load(open(os.path.join(REPO, "picks", "baselines.json")))
    img, frame = stock()
    fx0, fy0, fx1, fy1 = frame
    history, rows, since = [], [], None
    if sport == "mlb":
        allp = [p for p in load_picks() if p.get("status") in ("win", "loss", "push")]
        start = era_start()
        rows = [p for p in allp if p["date"] >= start]
        old = [p for p in allp if p["date"] < start]
        ow, ol, opu, ork, opl = _agg(old)
        b = base["mlb"]
        history = [
            (f"V1 MODEL · {md(old[0]['date'])}–{md(old[-1]['date'])}", f"{_rec(ow, ol, opu)} · {100 * opl / ork:+.1f}% · RETIRED"),
            (f"APRIL · LOGGED BY HAND", f"{_rec(b['wins'], b['losses'])} · BEFORE TRACKING"),
        ]
        since, title = start, "MLB LEDGER"
    elif sport == "nba":
        nba = json.load(open(os.path.join(REPO, "picks", "nba.json")))
        rows = sorted([p for p in nba if p.get("status") in ("win", "loss", "push")], key=lambda p: p["date"])
        b = base["nba"]
        history = [(f"{md(b['since'])} – APR 30 · LOGGED BY HAND",
                    f"{_rec(b['wins'], b['losses'])} · {100 * b['pl'] / b['risked']:+.1f}% · BEFORE TRACKING")]
        since, title = rows[0]["date"] if rows else None, "NBA LEDGER"
    else:
        title = "NFL LEDGER"

    w, l, pu, rk, pl = _agg(rows)
    span = f"{md(since)} → {md(rows[-1]['date'])}" if rows else "FRESH LEDGER"
    kicker = "MORELLO SIMS · TRACKED IN PUBLIC" if rows else "MORELLO SIMS · OPENING THE BOOKS"
    top = header(img, frame, kicker, title, span, sport=sport)
    d = ImageDraw.Draw(img)
    mx, R = (fx0 + fx1) // 2, s(170)
    my = top + s(195)
    d.polygon([(mx + s(4), my - R + s(3)), (mx + R + s(4), my + s(3)), (mx + s(4), my + R + s(3)), (mx - R + s(4), my + s(3))], fill=BLUE_DEEP)
    d.polygon([(mx, my - R), (mx + R, my), (mx, my + R), (mx - R, my)], fill=BLUE)
    rec = _rec(w, l, pu)
    rf = fit_font(d, rec, "cond", s(160), int(R * 1.3), min_size=s(70))
    bb = d.textbbox((0, 0), rec, font=rf)
    d.text((mx - (bb[2] - bb[0]) / 2 - bb[0], my - (bb[3] - bb[1]) / 2 - bb[1] - s(12)), rec, font=rf, fill=CREAM)
    lab = f"{len(rows)} SETTLED" if rows else "NO PICKS YET"
    ly = s(58)
    lf = fit_font(d, lab, "mono_b", s(22), int(2 * (R - ly - s(24)) * 0.85), min_size=s(12))
    d.text((mx - text_w(d, lab, lf) / 2, my + ly), lab, font=lf, fill=CREAM)

    y = my + R + s(26)
    cells = [(f"{pl:+,.0f}" if rows else "0", "NET $PP", (WIN if pl >= 0 else LOSS) if rows else INK),
             (f"{rk:,}", "$PP RISKED", INK),
             (f"{100 * pl / rk:+.1f}%" if rk else "–", "ROI", (WIN if pl >= 0 else LOSS) if rk else INK)]
    colw = (fx1 - fx0 - s(80)) / 3
    for i, (v, lb, col) in enumerate(cells):
        cx = fx0 + s(40) + colw * i + colw / 2
        vf = F("cond", 84)
        d.text((cx - text_w(d, v, vf) / 2, y), v, font=vf, fill=col)
        d.text((cx - text_w(d, lb, F("mono_b", 20)) / 2, y + s(100)), lb, font=F("mono_b", 20), fill=MUTED)

    # running $PP, one step per settled pick
    y += s(176)
    x0, x1 = fx0 + s(44), fx1 - s(44)
    if rows:
        run, acc = [0.0], 0.0
        for p in rows:
            acc += p.get("pl") or 0
            run.append(acc)
        lo, hi = min(run), max(run)
        spanv = (hi - lo) or 1
        gh = s(70)
        ys = lambda v: y + gh - (v - lo) / spanv * gh
        for dx in range(int(x0), int(x1), s(18)):
            d.line((dx, ys(0), dx + s(8), ys(0)), fill=(200, 190, 172), width=s(2))
        pts = [(x0 + i * (x1 - x0) / (len(run) - 1), ys(v)) for i, v in enumerate(run)]
        d.line(pts, fill=BLUE, width=s(5), joint="curve")
        ex, ey = pts[-1]
        d.ellipse((ex - s(9), ey - s(9), ex + s(9), ey + s(9)), fill=WIN if run[-1] >= 0 else LOSS)
        d.text((x0, y - s(30)), "RUNNING $PP · EVERY PICK", font=F("mono_b", 18), fill=MUTED)
        y += gh + s(26)
    else:
        rules = "FLAT 50 $PP · LOGGED BEFORE KICKOFF · NOTHING DELETED"
        rfnt = fit_font(d, rules, "mono_b", s(22), x1 - x0, min_size=s(14))
        d.text((mx - text_w(d, rules, rfnt) / 2, y + s(20)), rules, font=rfnt, fill=MUTED)

    # history rows: separate, never blended
    for i, (a, b2) in enumerate(history):
        ry = y + i * s(52)
        for dx in range(int(x0), int(x1), s(22)):
            d.line((dx, ry, dx + s(10), ry), fill=(214, 200, 180), width=s(2))
        d.text((x0, ry + s(14)), a, font=fit_font(d, a, "mono_b", s(20), (x1 - x0) * 0.52, min_size=s(13)), fill=INK)
        bf = fit_font(d, b2, "mono_b", s(20), (x1 - x0) * 0.46, min_size=s(13))
        d.text((x1 - text_w(d, b2, bf), ry + s(14)), b2, font=bf, fill=MUTED)

    footer(img, frame, "MORELLOSIMS.COM", "EVERY PICK LOGGED BEFORE THE GAME")
    return finish(img)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet", choices=["checklist", "record", "ledger"])
    ap.add_argument("--sport", default="mlb", choices=["mlb", "nba", "nfl"])
    ap.add_argument("--date")
    ap.add_argument("--out", default=os.path.join(REPO, "posters", "v2"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.sheet == "checklist":
        date = a.date or datetime.now().strftime("%Y-%m-%d")
        img, name = checklist(date), f"checklist-{date}.png"
    elif a.sheet == "ledger":
        img, name = ledger(a.sport), f"ledger-{a.sport}-{datetime.now().strftime('%Y-%m-%d')}.png"
    else:
        img, name = record(), f"record-{datetime.now().strftime('%Y-%m-%d')}.png"
    path = os.path.join(a.out, name)
    img.save(path)
    print(path)

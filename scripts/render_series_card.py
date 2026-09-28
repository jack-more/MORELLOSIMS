#!/usr/bin/env python3
"""MorelloSims series cards — every pick is a numbered card in the season set.

Two-colour vintage print: cream stock, vermilion quadrants, a yellow diamond
holding a halftoned team mark, playing-card corner indices carrying the price,
and the card's set number running along the diamond edge. Settled cards get
a rubber stamp across the diamond.

  python3 scripts/render_series_card.py --pick-id 2026-09-26-mlb-TB-PHI-ml [--settled] [--out DIR]
"""

import argparse
import json
import math
import os
import random
from datetime import datetime

from PIL import Image, ImageDraw, ImageFilter

from render_cards_v2 import REPO, font, text_w, fit_font, team_logo

S = 2                      # supersample; final card is 1080x1350
W, H = 1080 * S, 1350 * S

BG = (22, 20, 18)
CREAM = (243, 236, 220)
RED = (222, 60, 36)
YELLOW = (246, 206, 48)
INK = (28, 24, 22)
WIN = (20, 128, 70)
LOSS = (176, 32, 30)

# Team identity comes from the MLB Stats API snapshot, never a hand-typed table.
TEAMS = json.load(open(os.path.join(REPO, "data", "reference", "mlb_teams_2026.json")))["teams"]


def team_ref(abbr):
    t = TEAMS.get(abbr) or TEAMS.get({"AZ": "ARI", "ARI": "AZ", "OAK": "ATH", "WAS": "WSH"}.get(abbr, ""), {})
    if not t:
        raise SystemExit(f"{abbr} not in data/reference/mlb_teams_2026.json; refresh the snapshot")
    city = t["franchise"] if t["franchise"] != t["team"] else t["location"]
    return city.upper(), t["team"].upper(), t


def final_str(pick):
    """Stored result is away-home (verified against every settled ML pick);
    label it so a loss never reads like a win."""
    r = str(pick.get("result") or "")
    try:
        a, h = r.split("-")
        return f"{pick['away']} {int(a)} – {pick['home']} {int(h)}"
    except (ValueError, KeyError):
        return r


def s(v):
    return int(round(v * S))


def F(kind, size):
    return font(kind, s(size))


def load_picks():
    return sorted(json.load(open(os.path.join(REPO, "picks", "mlb.json"))), key=lambda p: (p["date"], p["id"]))


# ── print effects ──────────────────────────────────────────────────────────

def halftone_mark(logo, size, cell=9):
    """Team mark as black halftone dots over solid ink shapes — one-colour
    letterpress look instead of full-colour logo."""
    logo = logo.copy()
    logo.thumbnail((size, size), Image.LANCZOS)
    w, h = logo.size
    flat = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    flat.alpha_composite(logo)
    lum = flat.convert("L")
    alpha = flat.getchannel("A")
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    c = s(cell) // 2 * 2 or 2
    for y in range(0, h, c):
        for x in range(0, w, c):
            box = (x, y, min(x + c, w), min(y + c, h))
            a = sum(alpha.crop(box).getdata()) / (255 * max((box[2] - box[0]) * (box[3] - box[1]), 1))
            if a < 0.15:
                continue
            dark = 1 - sum(lum.crop(box).getdata()) / (255 * (box[2] - box[0]) * (box[3] - box[1]))
            dark = 0.18 + 0.82 * dark          # every inked area carries some dot
            r = (c / 2) * math.sqrt(dark) * 1.28 * a
            cx, cy = x + c / 2, y + c / 2
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=INK + (255,))
    # crisp ink for the darkest shapes so the mark still reads at thumbnail size
    solid = lum.point(lambda v: 255 if v < 70 else 0)
    solid = Image.composite(solid, Image.new("L", (w, h), 0), alpha.point(lambda a: 255 if a > 200 else 0))
    ink = Image.new("RGBA", (w, h), INK + (255,))
    out.paste(ink, (0, 0), solid)
    return out


def keyline_mark(logo, size, line=10):
    """Full-colour team mark with a cream die-cut keyline so it sits cleanly
    on the yellow diamond."""
    logo = logo.copy()
    logo.thumbnail((size, size), Image.LANCZOS)
    pad = s(line) * 2
    canvas = Image.new("RGBA", (logo.width + pad * 2, logo.height + pad * 2), (0, 0, 0, 0))
    canvas.alpha_composite(logo, (pad, pad))
    a = canvas.getchannel("A").point(lambda v: 255 if v > 40 else 0)
    grown = a.filter(ImageFilter.MaxFilter(s(line) * 2 + 1)).filter(ImageFilter.GaussianBlur(S))
    out = Image.new("RGBA", canvas.size, CREAM + (0,))
    out.putalpha(grown)
    out.alpha_composite(canvas)
    return out


def paper_grain(img, amount=7, seed=7):
    rnd = random.Random(seed)
    noise = Image.effect_noise((W // 4, H // 4), 40).resize((W, H), Image.BILINEAR)
    noise = noise.point(lambda v: 128 + (v - 128) * amount // 40)
    grain = Image.merge("RGB", (noise, noise, noise))
    return Image.blend(img, Image.composite(img, grain, Image.new("L", (W, H), 200)), 0.18)


# ── glyphs ─────────────────────────────────────────────────────────────────

def baseball(d, cx, cy, r):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=RED)
    for side in (-1, 1):
        # seam: arc of a larger circle offset sideways
        R = r * 1.05
        ox = cx + side * r * 1.55
        pts = []
        for t in range(-38, 39, 2):
            a = math.radians(180 + t if side > 0 else t)
            pts.append((ox + R * math.cos(a), cy + R * math.sin(a)))
        pts = [p for p in pts if (p[0] - cx) ** 2 + (p[1] - cy) ** 2 < (r * 0.94) ** 2]
        d.line(pts, fill=CREAM, width=s(3))
        for i in range(1, len(pts) - 1, 2):
            (x0, y0), (x1, y1) = pts[i - 1], pts[i + 1]
            ang = math.atan2(y1 - y0, x1 - x0) + math.pi / 2
            px, py = pts[i]
            L = r * 0.11
            for sgn in (-1, 1):
                d.line((px, py, px + sgn * L * math.cos(ang + 0.5 * sgn * side),
                        py + sgn * L * math.sin(ang + 0.5 * sgn * side)), fill=CREAM, width=s(3))


def corner_index(odds, sport_label="MLB"):
    """Playing-card index: ball + price + sport. Returned as its own layer so
    it can be rotated 180 for the opposite corner."""
    w, h = s(210), s(262)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    baseball(d, w // 2, s(68), s(62))
    of = fit_font(d, odds, "cond", s(96), w - s(10), min_size=s(56))
    d.text(((w - text_w(d, odds, of)) / 2, s(130)), odds, font=of, fill=RED)
    lf = F("mono_b", 22)
    d.text(((w - text_w(d, sport_label, lf)) / 2, s(232)), sport_label, font=lf, fill=RED)
    return layer


def rotated_text(img, text, fnt, fill, center, angle):
    d0 = ImageDraw.Draw(img)
    tw = text_w(d0, text, fnt)
    bb = d0.textbbox((0, 0), text, font=fnt)
    th = bb[3]
    layer = Image.new("RGBA", (tw + s(8), th + s(8)), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((s(4), s(4)), text, font=fnt, fill=fill)
    layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(layer, (int(center[0] - layer.width / 2), int(center[1] - layer.height / 2)))


def stamp(img, center, line1, line2, color, angle=-9):
    """Solid ink block, cream type: the result has to read at thumbnail size."""
    f1, f2 = F("black", 78), F("mono_b", 25)
    d0 = ImageDraw.Draw(img)
    w = max(text_w(d0, line1, f1), text_w(d0, line2, f2)) + s(70)
    h = s(172)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((0, 0, w, h), radius=s(18), fill=color + (255,))
    d.rounded_rectangle((s(12), s(12), w - s(12), h - s(12)), radius=s(10), outline=CREAM, width=s(3))
    d.text(((w - text_w(d, line1, f1)) / 2, s(20)), line1, font=f1, fill=CREAM)
    d.text(((w - text_w(d, line2, f2)) / 2, s(120)), line2, font=f2, fill=CREAM)
    sh = Image.new("RGBA", (w + s(60), h + s(60)), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((s(30), s(40), w + s(30), h + s(40)), radius=s(18), fill=(0, 0, 0, 90))
    sh = sh.filter(ImageFilter.GaussianBlur(s(12)))
    sh.alpha_composite(layer, (s(30), s(30)))
    sh = sh.rotate(angle, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(sh, (int(center[0] - sh.width / 2), int(center[1] - sh.height / 2)))


# ── card ───────────────────────────────────────────────────────────────────

def render(pick, settled=False):
    picks = load_picks()
    set_no = next(i for i, p in enumerate(picks, 1) if p["id"] == pick["id"])
    year = pick["date"][:4]
    side = pick["side"]
    opp = pick["home"] if side == pick["away"] else pick["away"]
    at = "at" if side == pick["away"] else "vs"
    odds = str(pick.get("odds") or "")
    if odds and not odds.startswith(("+", "-")):
        odds = "+" + odds

    img = Image.new("RGBA", (W, H), BG + (255,))
    cx0, cy0, cx1, cy1 = s(44), s(44), W - s(44), H - s(44)       # card stock
    fx0, fy0, fx1, fy1 = s(92), s(92), W - s(92), H - s(92)       # printed frame
    mx, my = (fx0 + fx1) // 2, s(640)                              # quadrant centre
    R = (fx1 - fx0) // 2 - s(34)                                   # diamond radius

    # card shadow + stock
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((cx0, cy0 + s(16), cx1, cy1 + s(16)), radius=s(54), fill=(0, 0, 0, 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(s(22))))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((cx0, cy0, cx1, cy1), radius=s(54), fill=CREAM + (255,))

    # vermilion quadrants, clipped to the rounded frame
    quad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    qd = ImageDraw.Draw(quad)
    qd.rectangle((mx, fy0, fx1, my), fill=RED)
    qd.rectangle((fx0, my, mx, fy1), fill=RED)
    clip = Image.new("L", (W, H), 0)
    ImageDraw.Draw(clip).rounded_rectangle((fx0, fy0, fx1, fy1), radius=s(40), fill=255)
    quad.putalpha(Image.composite(quad.getchannel("A"), Image.new("L", (W, H), 0), clip))
    img.alpha_composite(quad)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((fx0, fy0, fx1, fy1), radius=s(40), outline=RED, width=s(3))
    d.line((mx, fy0, mx, fy1), fill=RED, width=s(3))

    # yellow diamond with a hair of misregistration under the ink
    dia = [(mx, my - R), (mx + R, my), (mx, my + R), (mx - R, my)]
    d.polygon([(x + s(3), y + s(2)) for x, y in dia], fill=(232, 186, 30))
    d.polygon(dia, fill=YELLOW)

    logo = team_logo(side, 500)
    if logo:
        logo = logo.resize((logo.width * S, logo.height * S), Image.LANCZOS)
        is_settled = settled and pick.get("status") in ("win", "loss", "push")
        mark = keyline_mark(logo, int(R * (0.78 if is_settled else 0.98)))
        lift = int(R * 0.16) if is_settled else -s(6)
        img.alpha_composite(mark, (mx - mark.width // 2, my - mark.height // 2 - lift))
        d = ImageDraw.Draw(img)

    # corner indices — price lives where the suit would
    idx = corner_index(odds)
    img.alpha_composite(idx, (fx0 + s(14), fy0 + s(18)))
    img.alpha_composite(idx.rotate(180), (fx1 - s(14) - idx.width, fy1 - s(18) - idx.height))
    d = ImageDraw.Draw(img)

    # top-right: maker's mark
    tx = fx1 - s(40)
    for i, (t, f, c) in enumerate([
        ("MORELLO SIMS", F("black", 40), CREAM),
        (f"{year} MLB SERIES", F("mono_b", 22), CREAM),
    ]):
        d.text((tx - text_w(d, t, f), fy0 + s(40) + i * s(58)), t, font=f, fill=c)
    when = datetime.strptime(pick["date"], "%Y-%m-%d").strftime("%b %-d").upper()
    wt = f"{when} · {pick.get('game_time') or ''}".strip(" ·")
    d.text((tx - text_w(d, wt, F("mono_b", 22)), fy0 + s(128)), wt, font=F("mono_b", 22), fill=INK)

    # bottom-left: the name + the numbers, in the card-back voice
    lx = fx0 + s(44)
    city, name, _ = team_ref(side)
    edge = lambda y: (mx - R) + (y - my) - s(24)            # diamond's lower-left edge
    cf = fit_font(d, city, "cond", s(52), edge(my + s(250)) - lx, min_size=s(30))
    d.text((lx, my + s(232)), city, font=cf, fill=INK)
    nf = fit_font(d, name, "cond", s(112), max(edge(my + s(300)) - lx, s(260)), min_size=s(58))
    d.text((lx, my + s(284)), name, font=nf, fill=INK)
    pa, pr, ha, hr = (pick.get("sim_projection") or "").replace(" - ", " ").split()[:4] or ("", "", "", "")
    lines = [
        f"Sim: {pa} {pr} – {ha} {hr}",
        f"Moneyline {odds} {at} {team_ref(opp)[0].title()}",
        f"C{pick.get('conf')} confidence · {pick.get('units')} $PP",
    ]
    bf = F("cond_sb", 38)
    for i, t in enumerate(lines):
        d.text((lx, my + s(430) + i * s(46)), t, font=fit_font(d, t, "cond_sb", s(38), mx - lx - s(20), min_size=s(26)), fill=INK)

    # set number along the diamond's lower-right edge
    ex, ey = (mx + R * 0.5 + s(30), my + R * 0.5 + s(30))
    rotated_text(img, f"No. {set_no} IN THE {year} MLB SERIES", F("cond", 46), INK, (ex, ey), 45)

    if settled and pick.get("status") in ("win", "loss", "push"):
        pl = pick.get("pl") or 0
        st = pick["status"]
        l1 = {"win": "CASHED", "loss": "LOSS", "push": "PUSH"}[st]
        l2 = f"{final_str(pick)} · {'+' if pl > 0 else ''}{pl:g} $PP"
        stamp(img, (mx - s(26), my + int(R * 0.40)), l1, l2, WIN if st == "win" else LOSS if st == "loss" else INK)

    out = img.convert("RGB")
    out = paper_grain(out)
    return out.resize((W // S, H // S), Image.LANCZOS)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick-id", required=True)
    ap.add_argument("--settled", action="store_true")
    ap.add_argument("--out", default=os.path.join(REPO, "posters", "v2"))
    a = ap.parse_args()
    pick = next((p for p in load_picks() if p["id"] == a.pick_id), None)
    if not pick:
        raise SystemExit(f"pick id not found: {a.pick_id}")
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, f"series-{'settled-' if a.settled else ''}{pick['id']}.png")
    render(pick, a.settled).save(path)
    print(path)

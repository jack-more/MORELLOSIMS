#!/usr/bin/env python3
"""MorelloSims social cards v2 — the receipt/ticket design system.

Design language: picks printed on off-white ticket paper over clean cement
grey, die-cut notches, team-color rails, mono numerals, a barcode built from
the pick id, and rubber WIN/LOSS stamps at settlement. Receipts = proof,
tickets = fun. No lasers, no dots, no clutter.

Card types:
  receipt  — single pick, pre-game (the timestamped proof artifact)
  settled  — same ticket, stamped WIN/LOSS with P&L
  slate    — today's board: stacked ticket stubs + record header

Usage:
  python3 scripts/render_cards_v2.py receipt --pick-id 2026-07-05-mlb-DET-TEX-ml
  python3 scripts/render_cards_v2.py settled --pick-id 2026-07-04-mlb-MIL-AZ-ml
  python3 scripts/render_cards_v2.py slate --date 2026-07-05
Outputs to posters/v2/.
"""

import argparse
import hashlib
import json
import math
import os
from datetime import datetime

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FONT_DIR = os.path.join(REPO, "posters", "assets", "fonts")
LOGO_DIR = os.path.join(REPO, "posters", "assets", "mlb-team-logos")
OUT_DIR = os.path.join(REPO, "posters", "v2")
PICKS_JSON = os.path.join(REPO, "picks", "mlb.json")

W, H = 1080, 1350

# ── Palette (cement + ink + paper) ──
CEMENT_TOP = (152, 150, 146)
CEMENT_BOT = (128, 126, 122)
PAPER = (203, 202, 198)        # cool cement ticket stock
PAPER_EDGE = (150, 148, 144)
INK = (22, 21, 19)
INK_SOFT = (82, 80, 76)
WIN_GREEN = (18, 138, 74)
LOSS_RED = (188, 44, 44)
POP_YELLOW = (245, 205, 10)    # site nav yellow — the screenprint accent
GOLD = (176, 141, 60)

TEAM_COLORS = {
    "ARI": "#A71930", "AZ": "#A71930", "ATL": "#CE1141", "BAL": "#DF4601",
    "BOS": "#BD3039", "CHC": "#0E3386", "CIN": "#C6011F", "CLE": "#00385D",
    "COL": "#333366", "CWS": "#27251F", "DET": "#0C2340", "HOU": "#002D62",
    "KC": "#004687", "LAA": "#BA0021", "LAD": "#005A9C", "MIA": "#00A3E0",
    "MIL": "#0C2C56", "MIN": "#002B5C", "NYM": "#002D72", "NYY": "#092C5C",
    "OAK": "#003831", "ATH": "#003831", "PHI": "#E81828", "PIT": "#27251F",
    "SD": "#2F241D", "SEA": "#0C2C56", "SF": "#FD5A1E", "STL": "#C41E3A",
    "TB": "#092C5C", "TEX": "#003278", "TOR": "#134A8E", "WSH": "#AB0003",
    "WAS": "#AB0003",
}

TEAM_NAMES = {
    "ARI": "DIAMONDBACKS", "AZ": "DIAMONDBACKS", "ATL": "BRAVES", "BAL": "ORIOLES",
    "BOS": "RED SOX", "CHC": "CUBS", "CIN": "REDS", "CLE": "GUARDIANS",
    "COL": "ROCKIES", "CWS": "WHITE SOX", "DET": "TIGERS", "HOU": "ASTROS",
    "KC": "ROYALS", "LAA": "ANGELS", "LAD": "DODGERS", "MIA": "MARLINS",
    "MIL": "BREWERS", "MIN": "TWINS", "NYM": "METS", "NYY": "YANKEES",
    "OAK": "ATHLETICS", "ATH": "ATHLETICS", "PHI": "PHILLIES", "PIT": "PIRATES",
    "SD": "PADRES", "SEA": "MARINERS", "SF": "GIANTS", "STL": "CARDINALS",
    "TB": "RAYS", "TEX": "RANGERS", "TOR": "BLUE JAYS", "WSH": "NATIONALS",
    "WAS": "NATIONALS",
}

ESPN_SLUG = {
    "ARI": "ari", "AZ": "ari", "ATL": "atl", "BAL": "bal", "BOS": "bos",
    "CHC": "chc", "CIN": "cin", "CLE": "cle", "COL": "col", "CWS": "chw",
    "DET": "det", "HOU": "hou", "KC": "kc", "LAA": "laa", "LAD": "lad",
    "MIA": "mia", "MIL": "mil", "MIN": "min", "NYM": "nym", "NYY": "nyy",
    "OAK": "oak", "ATH": "oak", "PHI": "phi", "PIT": "pit", "SD": "sd",
    "SEA": "sea", "SF": "sf", "STL": "stl", "TB": "tb", "TEX": "tex",
    "TOR": "tor", "WSH": "wsh", "WAS": "wsh",
}


def hexrgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def font(name, size):
    paths = {
        "black": "ArchivoBlack.ttf",
        "cond": "BarlowCondensed-Bold.ttf",
        "cond_sb": "BarlowCondensed-SemiBold.ttf",
        "mono": "IBMPlexMono-Medium.ttf",
        "mono_b": "IBMPlexMono-Bold.ttf",
    }
    return ImageFont.truetype(os.path.join(FONT_DIR, paths[name]), size=size)


def text_w(d, t, f):
    b = d.textbbox((0, 0), t, font=f)
    return b[2] - b[0]


def team_logo(abbr, size):
    slug = ESPN_SLUG.get(abbr)
    if not slug:
        return None
    path = os.path.join(LOGO_DIR, f"espn-{slug}.png")
    if not os.path.exists(path):
        try:
            import urllib.request
            urllib.request.urlretrieve(f"https://a.espncdn.com/i/teamlogos/mlb/500/{slug}.png", path)
        except Exception:
            return None
    try:
        img = Image.open(path).convert("RGBA")
        img.thumbnail((size, size), Image.LANCZOS)
        return img
    except Exception:
        return None


def cement_background():
    """Clean vertical cement gradient, faint top light. No texture spam."""
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / H
        r = int(CEMENT_TOP[0] + (CEMENT_BOT[0] - CEMENT_TOP[0]) * t)
        g = int(CEMENT_TOP[1] + (CEMENT_BOT[1] - CEMENT_TOP[1]) * t)
        b = int(CEMENT_TOP[2] + (CEMENT_BOT[2] - CEMENT_TOP[2]) * t)
        for x in range(W):
            px[x, y] = (r, g, b)
    return img


def ticket_shadow(base, box, radius=26):
    x0, y0, x1, y1 = box
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(sh)
    d.rounded_rectangle((x0 + 6, y0 + 14, x1 + 6, y1 + 14), radius=radius, fill=(0, 0, 0, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(16))
    base.paste(sh, (0, 0), sh)


def ticket_paper(base, box, notch_y=None, radius=26):
    """Cement ticket stock: heavy ink border, print-shop crop marks."""
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(base)
    d.rounded_rectangle(box, radius=radius, fill=PAPER, outline=INK, width=5)
    if notch_y is not None:
        bgc = base.getpixel((10, min(notch_y, H - 1)))
        for cx in (x0, x1):
            d.ellipse((cx - 22, notch_y - 22, cx + 22, notch_y + 22), fill=bgc, outline=INK, width=5)
        # perforation dashes between notches
        for dx in range(x0 + 40, x1 - 30, 26):
            d.line((dx, notch_y, dx + 12, notch_y), fill=PAPER_EDGE, width=3)
    # crop marks just outside the corners — the print-shop signature
    for cx, cy, dx, dy in ((x0, y0, -1, -1), (x1, y0, 1, -1), (x0, y1, -1, 1), (x1, y1, 1, 1)):
        d.line((cx + dx * 14, cy + dy * 34, cx + dx * 14, cy + dy * 14), fill=INK, width=3)
        d.line((cx + dx * 34, cy + dy * 14, cx + dx * 14, cy + dy * 14), fill=INK, width=3)


def offset_print_text(base, xy, text, fnt, ink=INK, accent=POP_YELLOW, off=(7, 7)):
    """Screenprint misregistration: accent layer offset under the ink layer."""
    d = ImageDraw.Draw(base)
    d.text((xy[0] + off[0], xy[1] + off[1]), text, font=fnt, fill=accent)
    d.text(xy, text, font=fnt, fill=ink)


def rail_microtype(base, x, y_bottom, text, fill=None):
    """Vertical microtype running up the rail — indie poster move."""
    f = font("mono_b", 20)
    tmp = Image.new("RGBA", (900, 30), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    td.text((0, 0), text, font=f, fill=fill or (235, 233, 228))
    tw = td.textbbox((0, 0), text, font=f)[2]
    tmp = tmp.crop((0, 0, tw + 2, 28)).rotate(90, expand=True)
    base.paste(tmp, (x, y_bottom - tmp.height), tmp)


def barcode(d, box, seed_text):
    """Deterministic barcode from the pick id. Decor with a purpose."""
    x0, y0, x1, y1 = box
    h = hashlib.sha256(seed_text.encode()).digest()
    x = x0
    i = 0
    while x < x1 - 6:
        wbar = 3 + (h[i % len(h)] % 6)
        if i % 2 == 0:
            d.rectangle((x, y0, x + wbar, y1), fill=INK)
        x += wbar + 3
        i += 1


def qr_stub(base, xy, url, size=170, ink=INK, paper=PAPER):
    """Scannable QR in ticket ink. Every scan is tracked card traffic."""
    import qrcode
    q = qrcode.QRCode(border=1, box_size=10, error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data(url)
    q.make(fit=True)
    qr = q.make_image(fill_color=ink, back_color=paper).convert("RGB")
    qr = qr.resize((size, size), Image.NEAREST)
    base.paste(qr, xy)


def card_url(campaign, content=""):
    u = f"https://morellosims.com/mlbsim/?utm_source=card&utm_medium=social&utm_campaign={campaign}"
    if content:
        u += f"&utm_content={content}"
    return u


# ── High-end finish helpers ─────────────────────────────────────────────────

def gradient_text(base, xy, text, fnt, colors, angle_shift=0.35):
    """Draw text filled with a vertical foil gradient (list of RGB stops)."""
    d = ImageDraw.Draw(base)
    box = d.textbbox(xy, text, font=fnt)
    w, h = box[2] - box[0], box[3] - box[1]
    if w <= 0 or h <= 0:
        return
    grad = Image.new("RGB", (w, h))
    gd = ImageDraw.Draw(grad)
    n = len(colors) - 1
    for row in range(h):
        t = row / max(h - 1, 1)
        seg = min(int(t * n), n - 1)
        f = t * n - seg
        c0, c1 = colors[seg], colors[seg + 1]
        col = tuple(int(c0[i] + (c1[i] - c0[i]) * f) for i in range(3))
        # subtle diagonal shimmer
        shift = int(angle_shift * row)
        gd.line((0 - shift, row, w - shift, row), fill=col)
        gd.line((w - shift, row, w, row), fill=col)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((-box[0] + xy[0], -box[1] + xy[1]), text, font=fnt, fill=255)
    base.paste(grad, (box[0], box[1]), mask)


FOIL_GOLD = [(206, 172, 90), (247, 227, 160), (166, 124, 40), (232, 204, 120)]

# site nav accent dots (NBA green / MLB yellow / ATLAS orange)
BRAND_DOTS = [(58, 200, 60), (250, 205, 10), (245, 110, 20)]
LOGO_PATH = os.path.join(REPO, "assets", "morello-logo-cutout.png")


def brand_icon(size):
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo.thumbnail((size, size), Image.LANCZOS)
        return logo
    except Exception:
        return None


def brand_dots(d, x, y, r=7, gap=26):
    for i, c in enumerate(BRAND_DOTS):
        cx = x + i * gap
        d.ellipse((cx - r, y - r, cx + r, y + r), fill=c, outline=(20, 20, 20), width=2)


def logo_watermark(base, abbr, box, opacity=0.10, size=560):
    """Giant ghosted team logo bleeding off the ticket edge."""
    logo = team_logo(abbr, size)
    if logo is None:
        return
    x0, y0, x1, y1 = box
    region = base.crop((x0, y0, x1, y1))
    faded = Image.new("RGBA", region.size, (0, 0, 0, 0))
    lx = region.width - int(size * 0.62)
    ly = (region.height - size) // 2
    faded.paste(logo, (lx, ly), logo)
    alpha = faded.getchannel("A").point(lambda a: int(a * opacity))
    faded.putalpha(alpha)
    region = Image.alpha_composite(region.convert("RGBA"), faded)
    base.paste(region.convert("RGB"), (x0, y0))


def edge_vignette(base, box, radius=26, strength=42):
    """Soft inner shadow around the ticket edges for depth."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    vig = Image.new("L", (w, h), 0)
    vd = ImageDraw.Draw(vig)
    vd.rounded_rectangle((0, 0, w, h), radius=radius, fill=strength)
    inset = 26
    vd.rounded_rectangle((inset, inset, w - inset, h - inset), radius=radius, fill=0)
    vig = vig.filter(ImageFilter.GaussianBlur(18))
    shadow = Image.new("RGB", (w, h), (60, 50, 30))
    region = base.crop((x0, y0, x1, y1))
    region = Image.composite(shadow, region, vig)
    base.paste(region, (x0, y0))


def conf_stamp(base, center, conf, color=INK):
    """Circular confidence seal, slightly rotated, ink-stamp look."""
    size = 190
    stamp = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(stamp)
    c = color + (235,)
    d.ellipse((6, 6, size - 6, size - 6), outline=c, width=7)
    d.ellipse((20, 20, size - 20, size - 20), outline=c, width=3)
    f_big = font("black", 64)
    f_sm = font("mono_b", 17)
    t = f"C{conf}"
    tw = text_w(d, t, f_big)
    d.text(((size - tw) / 2, size / 2 - 48), t, font=f_big, fill=c)
    label = "CONFIDENCE"
    lw = text_w(d, label, f_sm)
    d.text(((size - lw) / 2, size / 2 + 28), label, font=f_sm, fill=c)
    stamp = stamp.rotate(-8, resample=Image.BICUBIC, expand=True)
    base.paste(stamp, (int(center[0] - stamp.width / 2), int(center[1] - stamp.height / 2)), stamp)


def result_stamp(base, center, text, color, angle=-10):
    """Rubber stamp: WIN +40 / LOSS -50. Translucent ink so the ticket
    stays readable underneath."""
    f = font("black", 84)
    tmp = Image.new("RGBA", (10, 10))
    tw = text_w(ImageDraw.Draw(tmp), text, f)
    pad = 38
    stamp = Image.new("RGBA", (tw + pad * 2, 84 + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(stamp)
    c = color + (160,)
    d.rounded_rectangle((4, 4, stamp.width - 4, stamp.height - 4), radius=16, outline=c, width=9)
    d.text((pad, pad - 8), text, font=f, fill=c)
    stamp = stamp.rotate(angle, resample=Image.BICUBIC, expand=True)
    base.paste(stamp, (int(center[0] - stamp.width / 2), int(center[1] - stamp.height / 2)), stamp)


def runs_bar(d, x, y, w, label_l, val_l, color_l, label_r, val_r, color_r):
    """Sim projection as two proportional bars."""
    f_lab = font("mono_b", 26)
    f_val = font("black", 34)
    total = max(val_l + val_r, 0.1)
    bar_h = 46
    gap = 8
    wl = int((val_l / total) * (w - gap))
    d.rounded_rectangle((x, y, x + wl, y + bar_h), radius=10, fill=color_l)
    d.rounded_rectangle((x + wl + gap, y, x + w, y + bar_h), radius=10, fill=color_r)
    d.text((x + 16, y + 6), f"{label_l} {val_l:g}", font=f_lab, fill=(255, 255, 255))
    rt = f"{val_r:g} {label_r}"
    d.text((x + w - 16 - text_w(d, rt, f_lab), y + 6), rt, font=f_lab, fill=(255, 255, 255))


def load_pick(pick_id):
    picks = json.load(open(PICKS_JSON))
    for p in picks:
        if p["id"] == pick_id:
            return p
    raise SystemExit(f"pick id not found: {pick_id}")


def season_record():
    picks = json.load(open(PICKS_JSON))
    w = sum(1 for p in picks if p.get("status") == "win")
    l = sum(1 for p in picks if p.get("status") == "loss")
    base = {}
    bpath = os.path.join(REPO, "picks", "baselines.json")
    if os.path.exists(bpath):
        base = json.load(open(bpath)).get("mlb", {})
    return w + base.get("wins", 0), l + base.get("losses", 0)


# ── Card: single-pick receipt ──────────────────────────────────────────────

def render_receipt(pick, settled=False, out_name=None):
    img = cement_background()
    d = ImageDraw.Draw(img)

    tx0, ty0, tx1, ty1 = 90, 90, W - 90, H - 90
    notch_y = ty1 - 240
    ticket_shadow(img, (tx0, ty0, tx1, ty1))
    ticket_paper(img, (tx0, ty0, tx1, ty1), notch_y=notch_y)

    side = pick["side"]
    opp = pick["home"] if side == pick["away"] else pick["away"]
    side_color = hexrgb(TEAM_COLORS.get(side, "#222222"))
    opp_color = hexrgb(TEAM_COLORS.get(opp, "#666666"))

    # high-end finish: ghosted team logo + soft edge depth, under all content
    logo_watermark(img, side, (tx0 + 20, ty0 + 20, tx1 - 20, notch_y - 20), opacity=0.07)
    edge_vignette(img, (tx0, ty0, tx1, ty1))
    d = ImageDraw.Draw(img)

    # ink header band across the ticket top, reversed type (screenprint)
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
    d.text((hx, ty0 + 86), "OFFICIAL SIM RECEIPT · MLB", font=font("mono_b", 20), fill=POP_YELLOW)
    when = pick.get("game_time") or ""
    datestr = datetime.strptime(pick["date"], "%Y-%m-%d").strftime("%b %d, %Y").upper()
    d.text((tx1 - 50 - text_w(d, datestr, font("mono_b", 26)), ty0 + 34), datestr,
           font=font("mono_b", 26), fill=PAPER)
    if when:
        d.text((tx1 - 50 - text_w(d, when, font("mono", 22)), ty0 + 78), when,
               font=font("mono", 22), fill=(160, 158, 152))

    # team color rail + vertical microtype
    d.rounded_rectangle((tx0, ty0, tx0 + 26, ty1), radius=26, fill=side_color)
    d.rectangle((tx0 + 13, ty0, tx0 + 26, ty1), fill=side_color)
    rail_microtype(img, tx0 + 1, notch_y - 30, f'№ {pick["id"].upper()}')
    d = ImageDraw.Draw(img)

    # matchup line
    y = ty0 + 196
    matchup = f'{pick["away"]} @ {pick["home"]}  ·  {pick["pick_text"]}'
    d.text((x, y), matchup, font=font("cond_sb", 42), fill=INK_SOFT)

    # the pick: team name poster-huge, filling the width, logo beside
    y += 70
    logo = team_logo(side, 165)
    if logo:
        img.paste(logo, (x, y + 14), logo)
    name_x = x + (190 if logo else 0)
    name = TEAM_NAMES.get(side, side).upper()
    nf = fit_font(d, name, "cond", 170, tx1 - 50 - name_x, min_size=90)
    offset_print_text(img, (name_x, y - 14), name, nf, accent=side_color, off=(8, 8))
    d = ImageDraw.Draw(img)

    # odds block: screenprint offset, massive
    y += 208
    odds = str(pick.get("odds") or "")
    if odds and not odds.startswith(("+", "-")):
        odds = f"+{odds}"
    offset_print_text(img, (x, y), odds, font("black", 160), accent=POP_YELLOW, off=(10, 10))
    d = ImageDraw.Draw(img)
    d.text((x + 6, y + 180), "MONEYLINE · REGULATION", font=font("mono_b", 22), fill=INK_SOFT)
    conf_stamp(img, (tx1 - 210, y + 80), int(pick.get("conf") or 0),
               color=WIN_GREEN if not settled else (WIN_GREEN if pick["status"] == "win" else LOSS_RED))
    d = ImageDraw.Draw(img)

    # sim projection bars
    y += 250
    proj = pick.get("sim_projection") or ""
    try:
        parts = proj.replace(" - ", " ").split()
        a_ab, a_rn, h_ab, h_rn = parts[0], float(parts[1]), parts[2], float(parts[3])
        d.text((x, y), "SIM PROJECTION", font=font("mono_b", 22), fill=INK_SOFT)
        runs_bar(d, x, y + 40, tx1 - 50 - x,
                 a_ab, a_rn, hexrgb(TEAM_COLORS.get(a_ab, "#444")),
                 h_ab, h_rn, hexrgb(TEAM_COLORS.get(h_ab, "#888")))
        y += 120
    except Exception:
        pass

    # stake line
    units = pick.get("units")
    if units:
        d.text((x, y + 6), f"RISK {units} $PP", font=font("mono_b", 30), fill=INK)
        rec_w, rec_l = season_record()
        rec = f"SEASON {rec_w}-{rec_l}"
        d.text((tx1 - 50 - text_w(d, rec, font("mono_b", 30)), y + 6), rec, font=font("mono_b", 30), fill=INK)

    # settled stamp — angled across the lower ticket, clear of odds + seal
    if settled and pick.get("status") in ("win", "loss"):
        pl = pick.get("pl") or 0
        stxt = f'WIN +{pl:g}' if pick["status"] == "win" else f'LOSS {pl:g}'
        result_stamp(img, (W // 2 - 60, notch_y - 330), stxt,
                     WIN_GREEN if pick["status"] == "win" else LOSS_RED)
        d = ImageDraw.Draw(img)

    # stub below perforation: scannable QR + barcode decor + id + site
    sy = notch_y + 32
    x = tx0 + 58
    qr_stub(img, (x, sy), card_url("settled" if settled else "receipt", pick["id"]), size=168)
    d = ImageDraw.Draw(img)
    bx = x + 196
    barcode(d, (bx, sy + 8, bx + 130, sy + 76), pick["id"])
    d.text((bx, sy + 92), pick["id"].upper(), font=font("mono", 17), fill=INK_SOFT)
    d.text((bx, sy + 124), "SCAN FOR THE FULL BOARD", font=font("mono_b", 18), fill=INK)
    d.text((tx1 - 50 - text_w(d, "MORELLOSIMS.COM", font("black", 34)), sy + 4),
           "MORELLOSIMS.COM", font=font("black", 34), fill=INK)
    tag = "EVERY PICK TRACKED · SETTLED IN PUBLIC"
    d.text((tx1 - 50 - text_w(d, tag, font("mono_b", 19)), sy + 60), tag, font=font("mono_b", 19), fill=INK_SOFT)
    brand_dots(d, tx1 - 50 - 52, sy + 116)

    os.makedirs(OUT_DIR, exist_ok=True)
    name = out_name or f'{"settled" if settled else "receipt"}-{pick["id"]}.png'
    out = os.path.join(OUT_DIR, name)
    img.save(out)
    print(out)
    return out


# ── Card: daily slate board ────────────────────────────────────────────────

def render_slate(date):
    picks = [p for p in json.load(open(PICKS_JSON)) if p["date"] == date]
    if not picks:
        raise SystemExit(f"no picks for {date}")
    img = cement_background()
    d = ImageDraw.Draw(img)

    # header plate: brand icon + wordmark like the site nav
    icon = brand_icon(96)
    hx = 90
    if icon:
        img.paste(icon, (90, 66), icon)
        hx = 90 + icon.width + 26
        d = ImageDraw.Draw(img)
    d.text((hx, 74), "TODAY'S BOARD", font=font("black", 50), fill=INK)
    datestr = datetime.strptime(date, "%Y-%m-%d").strftime("%A · %b %d, %Y").upper()
    d.text((hx + 4, 144), f"MORELLO SIMS · MLB · {datestr}", font=font("mono_b", 24), fill=(88, 86, 82))
    rec_w, rec_l = season_record()
    rec = f"{rec_w}-{rec_l}"
    rf = font("black", 44)
    d.text((W - 90 - text_w(d, rec, rf), 220), rec, font=rf, fill=INK)
    d.text((W - 90 - text_w(d, "SEASON RECORD", font("mono_b", 20)), 278), "SEASON RECORD",
           font=font("mono_b", 20), fill=(88, 86, 82))

    stub_h = 220
    shown = picks[:4]
    total_h = len(shown) * (stub_h + 34) - 34
    y = 250 + max(0, (H - 250 - 170 - total_h) // 2)
    for p in shown:
        side = p["side"]
        color = hexrgb(TEAM_COLORS.get(side, "#333"))
        box = (90, y, W - 90, y + stub_h)
        ticket_shadow(img, box, radius=20)
        ticket_paper(img, box, radius=20)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((90, y, 106, y + stub_h), radius=20, fill=color)
        lx = 150
        logo = team_logo(side, 120)
        if logo:
            img.paste(logo, (lx, y + 48), logo)
        nx = lx + 145
        d.text((nx, y + 34), TEAM_NAMES.get(side, side), font=font("black", 56), fill=INK)
        sub = f'{p["pick_text"]}  ·  {p["away"]} @ {p["home"]}'
        d.text((nx, y + 110), sub, font=font("cond_sb", 38), fill=INK_SOFT)
        proj = p.get("sim_projection") or ""
        if proj:
            d.text((nx, y + 158), f"SIM {proj}", font=font("mono", 24), fill=INK_SOFT)
        odds = str(p.get("odds") or "")
        if odds and not odds.startswith(("+", "-")):
            odds = f"+{odds}"
        of = font("black", 72)
        d.text((W - 150 - text_w(d, odds, of), y + 44), odds, font=of, fill=INK)
        cf = font("mono_b", 26)
        ct = f'C{p.get("conf")} · {p.get("units")} $PP'
        d.text((W - 150 - text_w(d, ct, cf), y + 130), ct, font=cf, fill=hexrgb("#B08D3C"))
        y += stub_h + 34

    # footer
    fy = H - 140
    d.text((90, fy), "MORELLOSIMS.COM", font=font("black", 40), fill=INK)
    tag = "EVERY PICK TRACKED · SETTLED IN PUBLIC"
    d.text((90, fy + 58), tag, font=font("mono_b", 22), fill=(88, 86, 82))
    brand_dots(d, W - 90 - 52, fy + 24, r=9, gap=32)

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"slate-{date}.png")
    img.save(out)
    print(out)
    return out


# ── Card: GO-YARD ticket (HR lotto) ────────────────────────────────────────

GOLD_PAPER = (252, 246, 228)
GOLD_EDGE = (214, 194, 142)
GOLD_DEEP = (146, 112, 38)

LANE_COLORS = {"DAMAGE": (168, 32, 32), "SURGE": (176, 106, 8), "PRESSURE": (30, 84, 158)}

HEADSHOT_DIR = os.path.join(REPO, "posters", "assets", "mlb-headshots")


def player_headshot(name, size):
    """Resolve a player headshot by name via MLB Stats API, cached on disk.
    Returns a square center-crop ready for circle masking."""
    os.makedirs(HEADSHOT_DIR, exist_ok=True)
    slug = name.lower().replace(" ", "-")
    path = os.path.join(HEADSHOT_DIR, f"{slug}.jpg")
    if not os.path.exists(path):
        try:
            import urllib.request
            import urllib.parse
            q = urllib.parse.quote(name)
            data = json.loads(urllib.request.urlopen(
                f"https://statsapi.mlb.com/api/v1/people/search?names={q}", timeout=20).read())
            pid = data["people"][0]["id"]
            urllib.request.urlretrieve(
                f"https://img.mlbstatic.com/mlb-photos/image/upload/w_360,q_auto:best/v1/people/{pid}/headshot/67/current",
                path)
        except Exception:
            return None
    try:
        img = Image.open(path).convert("RGBA")
        w, h = img.size
        side = min(w, h)
        top = int((h - side) * 0.18)  # bias crop toward the face
        img = img.crop(((w - side) // 2, top, (w - side) // 2 + side, top + side))
        img = img.resize((size, size), Image.LANCZOS)
        return img
    except Exception:
        return None


def fit_font(d, text, kind, size, max_w, min_size=28):
    for s in range(size, min_size - 1, -2):
        f = font(kind, s)
        if text_w(d, text, f) <= max_w:
            return f
    return font(kind, min_size)


def gold_ticket_paper(base, box, notch_y=None, radius=26):
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(base)
    d.rounded_rectangle(box, radius=radius, fill=GOLD_PAPER, outline=GOLD_EDGE, width=3)
    if notch_y is not None:
        bgc = base.getpixel((10, min(notch_y, H - 1)))
        for cx in (x0, x1):
            d.ellipse((cx - 22, notch_y - 22, cx + 22, notch_y + 22), fill=bgc, outline=GOLD_EDGE, width=3)
        for dx in range(x0 + 40, x1 - 30, 26):
            d.line((dx, notch_y, dx + 12, notch_y), fill=GOLD_EDGE, width=3)


def lane_chip(d, x, y, lane):
    c = LANE_COLORS.get(lane, INK)
    f = font("mono_b", 22)
    w = text_w(d, lane, f) + 36
    d.rounded_rectangle((x, y, x + w, y + 40), radius=9, fill=c)
    d.text((x + 18, y + 7), lane, font=f, fill=(255, 255, 255))
    return x + w


def render_goyard(out_name=None):
    audit = json.load(open(os.path.join(REPO, "mlbsim", "hr_lotto_audit.json")))
    core = audit.get("core") or []
    if not core:
        raise SystemExit("no core HR picks in hr_lotto_audit.json")
    gen_date = (audit.get("generated") or "")[:10]
    try:
        datestr = datetime.strptime(gen_date, "%Y-%m-%d").strftime("%b %d, %Y").upper()
    except ValueError:
        datestr = gen_date

    img = cement_background()
    tx0, ty0, tx1, ty1 = 90, 80, W - 90, H - 80
    notch_y = ty1 - 230
    ticket_shadow(img, (tx0, ty0, tx1, ty1))
    gold_ticket_paper(img, (tx0, ty0, tx1, ty1), notch_y=notch_y)
    edge_vignette(img, (tx0, ty0, tx1, ty1), strength=34)
    d = ImageDraw.Draw(img)

    # gold rail
    d.rounded_rectangle((tx0, ty0, tx0 + 16, ty1), radius=26, fill=GOLD_DEEP)
    d.rectangle((tx0 + 8, ty0, tx0 + 16, ty1), fill=GOLD_DEEP)

    x = tx0 + 58
    gradient_text(img, (x, ty0 + 42), "GO-YARD TICKET", font("black", 52), FOIL_GOLD)
    d = ImageDraw.Draw(img)
    icon = brand_icon(34)
    sub_x = x
    if icon:
        img.paste(icon, (x, ty0 + 108), icon)
        sub_x = x + icon.width + 14
        d = ImageDraw.Draw(img)
    d.text((sub_x, ty0 + 112), "MORELLO SIMS · HOME RUN LOTTO", font=font("mono_b", 22), fill=GOLD_DEEP)
    d.text((tx1 - 50 - text_w(d, datestr, font("mono_b", 26)), ty0 + 56), datestr,
           font=font("mono_b", 26), fill=INK)
    d.line((x, ty0 + 162, tx1 - 50, ty0 + 162), fill=GOLD_EDGE, width=3)

    # two featured core picks; right 290px reserved for the lift block
    y = ty0 + 200
    lift_col = tx1 - 60
    for r in core[:2]:
        head = player_headshot(r["name"], 200)
        nx = x
        if head:
            d.ellipse((x - 4, y - 4, x + 204, y + 204), outline=GOLD_DEEP, width=5)
            mask = Image.new("L", head.size, 0)
            ImageDraw.Draw(mask).ellipse((0, 0, head.width, head.height), fill=255)
            img.paste(head, (x, y), mask)
            nx = x + 235
        name_max_w = lift_col - 290 - nx
        nf = fit_font(d, r["name"].upper(), "black", 54, name_max_w)
        d.text((nx, y + 2), r["name"].upper(), font=nf, fill=INK)
        matchup = f'{r["team"]} vs {r["opp_pitcher"]} ({r["opp_team"]})'
        mf = fit_font(d, matchup, "cond_sb", 36, name_max_w, min_size=24)
        d.text((nx, y + 76), matchup, font=mf, fill=INK_SOFT)
        lane_chip(d, nx, y + 128, r.get("lane") or "DAMAGE")
        # lift multiplier huge on the right
        lift = r["hr_rate"] / max(r.get("base_hr_rate") or 0.001, 0.001)
        lt = f"{lift:.1f}×"
        lf = font("black", 88)
        gradient_text(img, (lift_col - text_w(d, lt, lf), y + 26), lt, lf, FOIL_GOLD)
        d = ImageDraw.Draw(img)
        sub = f'{r["hr_rate"]*100:.1f}% TONIGHT · {(r.get("base_hr_rate") or 0)*100:.1f}% BASE'
        d.text((lift_col - text_w(d, sub, font("mono_b", 21)), y + 138), sub,
               font=font("mono_b", 21), fill=INK_SOFT)
        y += 252
        if r is core[0]:
            d.line((x, y - 26, tx1 - 50, y - 26), fill=GOLD_EDGE, width=2)

    # watch strip
    d.line((x, y - 6, tx1 - 50, y - 6), fill=GOLD_EDGE, width=3)
    d.text((x, y + 8), "ALSO LIVE", font=font("mono_b", 22), fill=GOLD_DEEP)
    wy = y + 46
    for r in core[2:6]:
        nm = r["name"].upper()
        d.text((x, wy), nm, font=font("cond", 34), fill=INK)
        rate = f'{r["hr_rate"]*100:.1f}%'
        d.text((x + 430, wy + 2), f'vs {r["opp_pitcher"]}', font=font("cond_sb", 28), fill=INK_SOFT)
        d.text((tx1 - 60 - text_w(d, rate, font("mono_b", 28)), wy + 2), rate,
               font=font("mono_b", 28), fill=GOLD_DEEP)
        wy += 48

    # stub: scannable QR + barcode decor
    sy = notch_y + 30
    qr_stub(img, (x, sy), card_url("goyard", gen_date), size=168, paper=GOLD_PAPER)
    d = ImageDraw.Draw(img)
    bx = x + 196
    barcode(d, (bx, sy + 8, bx + 130, sy + 74), "goyard-" + gen_date)
    d.text((bx, sy + 90), f"GO-YARD-{gen_date}".upper(), font=font("mono", 17), fill=INK_SOFT)
    d.text((bx, sy + 122), "SCAN FOR TONIGHT'S FULL LIST", font=font("mono_b", 18), fill=GOLD_DEEP)
    d.text((tx1 - 50 - text_w(d, "MORELLOSIMS.COM", font("black", 34)), sy + 2),
           "MORELLOSIMS.COM", font=font("black", 34), fill=INK)
    tag = "GO YARD OR GO HOME · TRACKED DAILY"
    d.text((tx1 - 50 - text_w(d, tag, font("mono_b", 19)), sy + 56), tag,
           font=font("mono_b", 19), fill=GOLD_DEEP)
    brand_dots(d, tx1 - 50 - 52, sy + 112)

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, out_name or f"goyard-{gen_date}.png")
    img.save(out)
    print(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("card", choices=["receipt", "settled", "slate", "goyard"])
    ap.add_argument("--pick-id")
    ap.add_argument("--date")
    a = ap.parse_args()
    if a.card in ("receipt", "settled"):
        if not a.pick_id:
            raise SystemExit("--pick-id required")
        render_receipt(load_pick(a.pick_id), settled=(a.card == "settled"))
    elif a.card == "goyard":
        render_goyard()
    else:
        render_slate(a.date or datetime.now().strftime("%Y-%m-%d"))


if __name__ == "__main__":
    main()

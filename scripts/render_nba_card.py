#!/usr/bin/env python3
"""NBA pick card: the v3 layout (render_pick_card.py) for spreads.

One read, top to bottom: THE PICK (team, spread huge) → WHY (sim margin vs
the line, in plain words) → THE GAME (opponent, date, arena over a to-scale
half court) → RECEIPT. sealed() is the same card, locked, for X.

Sources:
  data/reference/nba_teams_espn_2026.json  names, colors, logos (ESPN), arenas
      (Wikipedia/NBA.com — ESPN's own venue field is stale for 5 teams)
  data/reference/nba_court_dimensions.json court geometry
  picks/nba.json sim_projection = projected MARGIN for the picked side
      ("NYK +1.0" = Knicks win by 1), so edge = margin + line; verified on
      every logged pick (e.g. NYK +5.0, sim +1.0 → edge 6.0).

  python3 scripts/render_nba_card.py --pick-id <id> [--settled|--sealed] [--out DIR]
"""

import argparse
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from render_cards_v2 import text_w, fit_font  # noqa: E402
from render_series_card import (  # noqa: E402
    REPO, S, W, H, BG, CREAM, INK, WIN, LOSS, s, F, keyline_mark, paper_grain, _mix, _contrast, _hex, _lum,
)

ET = timezone(timedelta(hours=-4))
MUTED = (112, 102, 90)
# brand (morellosims.com): poster sky, gold rim, money green
SKY = (49, 135, 220)
GOLD, GOLD_DEEP, GOLD_HI, GOLD_SHINE = (232, 181, 59), (185, 134, 27), (247, 215, 116), (255, 243, 196)
GRASS = (15, 138, 67)
HOUSE = SKY
SNAP = json.load(open(os.path.join(REPO, "data", "reference", "nba_teams_espn_2026.json")))["teams"]
COURT = json.load(open(os.path.join(REPO, "data", "reference", "nba_court_dimensions.json")))
LOGOS = os.path.join(REPO, "posters", "assets", "nba-team-logos")
# picks use NBA abbreviations; the snapshot is keyed by ESPN's (mapping from
# nba_pipeline/utils/constants.ESPN_ABBR_MAP, inverted)
sys.path.insert(0, os.path.join(REPO, "nba_pipeline"))
from utils.constants import ESPN_ABBR_MAP  # noqa: E402
NBA_TO_ESPN = {v: k for k, v in ESPN_ABBR_MAP.items()}


def team(abbr):
    t = SNAP.get(NBA_TO_ESPN.get(abbr, abbr))
    if not t:
        raise SystemExit(f"{abbr} not in data/reference/nba_teams_espn_2026.json; refresh the snapshot")
    return t


def palette(abbr):
    t = team(abbr)
    P, A = _hex(t["color"]), _hex(t["alt"])
    if _lum(P) > 0.55:                       # very light primaries (e.g. GSW gold) print their alt
        P, A = A, P
    on_P = CREAM if _contrast(CREAM, P) >= _contrast(INK, P) else INK
    return P, A, on_P


def logo(abbr, size):
    t = team(abbr)
    os.makedirs(LOGOS, exist_ok=True)
    path = os.path.join(LOGOS, f"espn-{NBA_TO_ESPN.get(abbr, abbr).lower()}.png")
    if not os.path.exists(path):
        try:
            urllib.request.urlretrieve(t["logo"], path)
        except Exception:
            return None
    img = Image.open(path).convert("RGBA")
    img.thumbnail((size, size), Image.LANCZOS)
    return img


def load_picks():
    import picks_store  # seal mode: sealed picks open with PICKS_SEAL_KEY
    return sorted(picks_store.load_picks("nba"), key=lambda p: (p["date"], p["id"]))


def _num(v):
    return f"{v:+.1f}" if v else "PK"


UNIT_PP = 50.0   # 1u = 50 $PP, the standard stake


def _u(pp, sign=False):
    v = float(pp or 0) / UNIT_PP
    t = f"{v:+.2f}" if sign else f"{v:.2f}"
    return t.rstrip("0").rstrip(".") + "u" if "." in t else t + "u"


def _logged(p):
    ts = p.get("published_at") or p.get("captured_at")
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(ET).strftime("%-I:%M %p ET")
    except (TypeError, ValueError):
        return None


def half_court(tint, width, height):
    """To-scale NBA half court, baseline on the right, drawn in `tint`."""
    c = COURT
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = min(width / (c["length_ft"] / 2 + 2), height / (c["width_ft"] + 2))
    ox, oy = width - k * 1, height / 2                 # baseline x, court centerline y
    P = lambda x, y: (ox - x * k, oy + y * k)           # x = ft from baseline, y = ft from center  # noqa: E731
    lw = max(4, int(k * 0.42))
    half, wd = c["length_ft"] / 2, c["width_ft"] / 2
    d.rectangle((*P(half, -wd), *P(0, wd)), outline=tint, width=lw)
    rim = c["rim_center_from_baseline_ft"]
    bb = c["backboard_from_baseline_ft"]
    # lane + free-throw circle
    ft_x = bb + c["free_throw_from_backboard_ft"]
    kw = c["key_width_ft"] / 2
    d.rectangle((*P(ft_x, -kw), *P(0, kw)), outline=tint, width=lw)
    r = 6 * k
    fx, fy = P(ft_x, 0)
    d.arc((fx - r, fy - r, fx + r, fy + r), 90, 270, fill=tint, width=lw)
    # backboard, rim, no-charge arc
    d.line((P(bb, -3), P(bb, 3)), fill=tint, width=lw)
    rx, ry = P(rim, 0)
    rr = 0.75 * k
    d.ellipse((rx - rr, ry - rr, rx + rr, ry + rr), outline=tint, width=lw)
    nr = c["no_charge_arc_radius_ft"] * k
    d.arc((rx - nr, ry - nr, rx + nr, ry + nr), 90, 270, fill=tint, width=lw)
    # three-point line: corner straights 3 ft from the sidelines, then the arc
    arc_r = c["three_point_arc_ft"]
    cy_ft = wd - c["three_point_corner_from_sideline_ft"]
    cx_ft = rim + math.sqrt(max(0.0, arc_r ** 2 - cy_ft ** 2))
    for sgn in (-1, 1):
        d.line((P(0, sgn * cy_ft), P(cx_ft, sgn * cy_ft)), fill=tint, width=lw)
    a0 = math.degrees(math.atan2(cy_ft, cx_ft - rim))
    R3 = arc_r * k
    d.arc((rx - R3, ry - R3, rx + R3, ry + R3), 180 - a0, 180 + a0, fill=tint, width=lw)
    # half-court line + center circle
    d.line((P(half, -wd), P(half, wd)), fill=tint, width=lw)
    cr = c["center_circle_diameter_ft"] / 2 * k
    hx, hy = P(half, 0)
    d.arc((hx - cr, hy - cr, hx + cr, hy + cr), 270, 90, fill=tint, width=lw)
    return img


def _bez(p0, p1, p2, n=24):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in (i / n for i in range(n + 1))]


def coin(d, cx, cy, r):
    """The brand's gold coin (same proportions as the site's SVG)."""
    k = r / 18
    d.ellipse((cx - r, cy - r + k, cx + r, cy + r + k), fill=GOLD_DEEP)
    d.ellipse((cx - 17 * k, cy - 17 * k, cx + 17 * k, cy + 17 * k), fill=GOLD)
    d.ellipse((cx - 12.5 * k, cy - 12.5 * k, cx + 12.5 * k, cy + 12.5 * k), outline=GOLD_HI, width=max(1, int(2 * k)))
    d.line(_bez((cx - 9 * k, cy - 6 * k), (cx - 6 * k, cy - 11 * k), (cx, cy - 12 * k)), fill=GOLD_SHINE, width=max(1, int(2.4 * k)))


def brand_mark(img, x, y, size):
    """Logo: gold-rimmed tile, a coin rising over money-green grass."""
    d = ImageDraw.Draw(img)
    u = size / 32
    d.rounded_rectangle((x + 2 * u, y + 2 * u, x + 30 * u, y + 30 * u), radius=8 * u, fill=GOLD)
    d.rounded_rectangle((x + 4.5 * u, y + 4.5 * u, x + 27.5 * u, y + 27.5 * u), radius=5.5 * u, fill=CREAM)
    coin(d, x + 11.5 * u, y + 11.5 * u, 5 * u)
    for a, b, c in (((16.5, 26), (16, 20), (21, 14)), ((19, 26), (19.5, 21.5), (15, 18.5)), ((22.5, 25.5), (23.5, 21), (26.5, 18.5))):
        d.line(_bez(*[(x + px * u, y + py * u) for px, py in (a, b, c)]), fill=GRASS, width=max(2, int(2.2 * u)), joint="curve")


def _stock(pick):
    """The card is the brand tile: gold rim with a deeper gold edge, on the poster sky."""
    img = Image.new("RGBA", (W, H), SKY + (255,))
    x0, y0, x1, y1 = s(44), s(40), W - s(44), H - s(48)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x0, y0 + s(24), x1, y1 + s(24)), radius=s(58), fill=(8, 40, 80, 110))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(s(26))))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x0 - s(10), y0 + s(6), x1 - s(10), y1 + s(6)), radius=s(58), fill=GOLD_DEEP + (255,))
    d.rounded_rectangle((x0, y0, x1, y1), radius=s(58), fill=GOLD + (255,))
    d.rounded_rectangle((x0 + s(12), y0 + s(12), x1 - s(12), y1 - s(12)), radius=s(48), fill=CREAM + (255,))
    set_no = next((i for i, p in enumerate(load_picks(), 1) if p["id"] == pick["id"]), None)
    mf = F("mono_b", 24)
    brand_mark(img, s(88), s(80), s(46))
    d = ImageDraw.Draw(img)
    d.text((s(146), s(94)), "MORELLO SIMS", font=mf, fill=INK)
    tag = f"NBA No. {set_no}" if set_no else "NBA"
    d.text((W - s(92) - text_w(d, tag, mf), s(94)), tag, font=mf, fill=INK)
    return img


def _band(img, pick, tint, title):
    L, R = s(92), W - s(92)
    gy0, gy1 = s(978), s(1158)
    band = Image.new("RGBA", (R - L, gy1 - gy0), _mix(tint, CREAM, 0.86) + (255,))
    # drawn ~2x the band height and cropped by it: the key and the arc fill
    # the band and bleed off, like the MLB park plate
    ch = int((gy1 - gy0) * 2.1)
    court = half_court(_mix(tint, CREAM, 0.22) + (255,), int(ch * 1.05), ch)
    band.alpha_composite(court, (band.width - court.width + s(90), (band.height - court.height) // 2))
    mask = Image.new("L", band.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, band.width, band.height), radius=s(28), fill=255)
    img.paste(band, (L, gy0), mask)
    d = ImageDraw.Draw(img)
    d.text((L + s(36), gy0 + s(30)), title, font=fit_font(d, title, "cond", s(56), s(500), min_size=s(38)), fill=INK)
    when = datetime.strptime(pick["date"], "%Y-%m-%d").strftime("%a %b %-d").upper()
    tip = pick.get("game_time") or ""
    d.text((L + s(36), gy0 + s(100)), f"{when} · {tip}".strip(" ·"), font=F("mono_b", 28), fill=INK)
    d.text((L + s(36), gy0 + s(140)), (team(pick["home"])["venue"] or "").upper(), font=F("mono_b", 24), fill=MUTED)


def _receipt(img, pick, footer):
    d = ImageDraw.Draw(img)
    L, R, cx = s(92), W - s(92), W // 2
    logged = _logged(pick)
    rf = F("mono_b", 22)
    # "before tip" only when the record shows it: reinstated rows were logged late
    late = str(pick.get("void_reason") or "").startswith("REINSTATED")
    when = "LOGGED LATE" if late else "BEFORE TIP"
    d.text((L, s(1186)), f"LOGGED {logged} · {when}" if logged and not late else when, font=rf, fill=MUTED)
    right = f"{_u(pick.get('units'))} STAKE"
    d.text((R - text_w(d, right, rf), s(1186)), right, font=rf, fill=MUTED)
    ff = F("mono_b", 26)
    d.text((cx - text_w(d, footer, ff) / 2, s(1232)), footer, font=ff, fill=INK)


def render(pick, settled=False):
    side, home, away = pick["side"], pick["home"], pick["away"]
    opp = home if side == away else away
    P, A, on_P = palette(side)
    t, o = team(side), team(opp)
    img = _stock(pick)
    d = ImageDraw.Draw(img)
    L, R = s(92), W - s(92)

    # 1. THE PICK
    py0, py1 = s(146), s(700)
    d.rounded_rectangle((L, py0, R, py1), radius=s(34), fill=P)
    lg = logo(side, 500)
    lx, lsize = L + s(40), s(250)
    if lg:
        lg = lg.resize((lg.width * S, lg.height * S), Image.LANCZOS)
        img.alpha_composite(keyline_mark(lg, lsize, line=8), (lx, py0 + s(40)))
        d = ImageDraw.Draw(img)
    tx = lx + lsize + s(44)
    d.text((tx, py0 + s(64)), t["location"].upper(), font=F("cond_sb", 48), fill=on_P)
    nm = t["name"].upper()
    d.text((tx, py0 + s(112)), nm, font=fit_font(d, nm, "cond", s(150), R - s(40) - tx, min_size=s(84)), fill=on_P)
    bet_y = py0 + s(330)
    d.line((L + s(40), bet_y - s(18), R - s(40), bet_y - s(18)), fill=on_P + (110,), width=s(3))
    is_ml = pick.get("bet_type") == "ml"
    label = "MONEYLINE" if is_ml else f"SPREAD · {pick.get('odds')}"
    d.text((L + s(40), bet_y + s(40)), label, font=F("mono_b", 34), fill=on_P)
    big = str(pick.get("odds")) if is_ml else _num(float(pick.get("line") or 0))
    of = F("black", 172)
    d.text((R - s(40) - text_w(d, big, of), bet_y - s(8)), big, font=of, fill=on_P)

    # 2. WHY / RESULT
    wy = s(728)
    margin = None
    try:
        margin = float((pick.get("sim_projection") or "").split()[-1])
    except (ValueError, IndexError):
        pass
    if settled and pick.get("status") in ("win", "loss", "push"):
        col = {"win": WIN, "loss": LOSS}.get(pick["status"], MUTED)
        word = {"win": "WIN", "loss": "LOSS"}.get(pick["status"], "PUSH")
        d.rounded_rectangle((L, wy, R, wy + s(170)), radius=s(26), fill=col)
        d.text((L + s(40), wy + s(26)), word, font=F("black", 104), fill=CREAM)
        try:  # NBA results are stored HOME-AWAY (verified vs ESPN: 06-13 NYK@SAS "90-94" = SA 90, NY 94)
            h_pts, a_pts = str(pick.get("result")).split("-")
            fin = f"{away} {a_pts} – {home} {h_pts}"
        except ValueError:
            fin = str(pick.get("result") or "")
        money = _u(pick.get("pl"), sign=True)
        d.text((R - s(40) - text_w(d, fin, F("mono_b", 30)), wy + s(40)), fin, font=F("mono_b", 30), fill=CREAM)
        d.text((R - s(40) - text_w(d, money, F("black", 54)), wy + s(86)), money, font=F("black", 54), fill=CREAM)
        if margin is not None:
            d.text((L, wy + s(190)), f"The sim had the {t['name']} {'by ' if margin >= 0 else 'losing by '}{abs(margin):.1f}",
                   font=F("cond_sb", 40), fill=MUTED)
    elif margin is not None:
        d.text((L, wy), "THE SIM", font=F("mono_b", 26), fill=MUTED)
        head = f"{t['name'].upper()} {'WIN' if margin >= 0 else 'LOSE'} BY {abs(margin):.1f}"
        hf = fit_font(d, head, "black", s(92), R - L, min_size=s(56))
        d.text((L, wy + s(40)), head, font=hf, fill=P if _contrast(P, CREAM) >= 2.2 else INK)
        if not is_ml:
            line = float(pick.get("line") or 0)
            edge = margin + line
            d.text((L, wy + s(146)), f"The line gives {_num(line)}. That's {edge:.1f} points of edge.",
                   font=F("cond_sb", 46), fill=INK)

    at = "AT" if side == away else "VS"
    _band(img, pick, P, f"{at} {o['display'].upper()}")
    _receipt(img, pick, "MORELLOSIMS.COM")
    return paper_grain(img.convert("RGB")).resize((1080, 1350), Image.LANCZOS)


def sealed(pick):
    """Same card, locked. Texture from fixed placeholder shapes (never the
    real card), matchup as 'A @ B' so VS/AT can't reveal the side."""
    img = _stock(pick)
    L, R, cx = s(92), W - s(92), W // 2

    def locked(box, radius, blobs):
        w, h = box[2] - box[0], box[3] - box[1]
        g = Image.new("L", (w, h), 40)
        gd = ImageDraw.Draw(g)
        for bx0, by0, bx1, by1, v in blobs:
            gd.rounded_rectangle((s(bx0), s(by0), s(bx1), s(by1)), radius=s(18), fill=v)
        g = g.filter(ImageFilter.GaussianBlur(s(70)))
        tile = ImageOps.colorize(g, black=(22, 82, 150), white=(150, 200, 245)).convert("RGBA")
        mask = Image.new("L", tile.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
        img.paste(tile, box[:2], mask)

    locked((L, s(146), R, s(700)), s(34),
           [(40, 40, 290, 290, 150), (330, 60, 520, 110, 120), (330, 120, 840, 270, 170),
            (40, 300, 856, 316, 110), (40, 380, 300, 420, 120), (470, 330, 856, 500, 180)])
    locked((L, s(768), R, s(930)), s(24), [(20, 30, 380, 120, 170), (470, 30, 856, 120, 150)])
    d = ImageDraw.Draw(img)
    sf = F("black", 150)
    d.text((cx - text_w(d, "SEALED", sf) / 2, s(300)), "SEALED", font=sf, fill=CREAM)
    sub = f"TONIGHT · {'MONEYLINE' if pick.get('bet_type') == 'ml' else 'SPREAD'}"
    d.text((cx - text_w(d, sub, F("mono_b", 34)) / 2, s(490)), sub, font=F("mono_b", 34), fill=CREAM)
    d.text((L, s(728)), "THE SIM", font=F("mono_b", 26), fill=MUTED)
    msg, mf = "MEMBERS HAVE IT NOW", F("cond", 64)
    d.text((cx - text_w(d, msg, mf) / 2, s(812)), msg, font=mf, fill=CREAM)
    _band(img, pick, HOUSE, f"{team(pick['away'])['name'].upper()} @ {team(pick['home'])['name'].upper()}")
    _receipt(img, pick, "UNLOCK · MORELLOSIMS.COM")
    return paper_grain(img.convert("RGB")).resize((1080, 1350), Image.LANCZOS)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick-id", required=True)
    ap.add_argument("--settled", action="store_true")
    ap.add_argument("--sealed", action="store_true")
    ap.add_argument("--out", default=os.path.join(REPO, "posters", "v2"))
    a = ap.parse_args()
    pick = next((p for p in load_picks() if p["id"] == a.pick_id), None)
    if not pick:
        raise SystemExit(f"pick id not found: {a.pick_id}")
    os.makedirs(a.out, exist_ok=True)
    kind = "sealed-" if a.sealed else "settled-" if a.settled else ""
    path = os.path.join(a.out, f"nba-{kind}{pick['id']}.png")
    (sealed(pick) if a.sealed else render(pick, a.settled)).save(path)
    print(path)

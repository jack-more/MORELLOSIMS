#!/usr/bin/env python3
"""Pick card v3: one straight read, top to bottom.

Owner feedback (2026-09-30) on the series card: "very hard to follow, not
sure where to look — people need it right in front of them." The series
card split the pick across four corners (price top-left and upside-down
bottom-right, team bottom-left, a diagonal set number) around a park
centerpiece. This card reads in one pass:

  1. THE PICK   — logo, team, bet + price, huge, on the team's own ink
  2. WHY        — the sim score, one line, the picked side in team ink
  3. THE GAME   — opponent, date, first pitch, park (engraved plate band)
  4. RECEIPT    — logged time, stake, confidence, series number (small)

Team names/venues from data/reference/mlb_teams_2026.json, colors from the
ESPN snapshot, park plates from posters/assets/plates/mlb — all sourced.

  python3 scripts/render_pick_card.py --pick-id 2026-09-27-mlb-ATL-MIA-ml [--settled] [--out DIR]
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from render_cards_v2 import text_w, fit_font, team_logo  # noqa: E402
from render_series_card import (  # noqa: E402
    REPO, S, W, H, BG, CREAM, INK, WIN, LOSS, PLATES,
    palette, team_ref, final_str, s, F, load_picks, keyline_mark, paper_grain, _mix, _contrast,
)

ET = timezone(timedelta(hours=-4))
MUTED = (112, 102, 90)


def _odds(p):
    o = str(p.get("odds") or "")
    return o if not o or o.startswith(("+", "-")) else "+" + o


def _logged(p):
    ts = p.get("published_at") or p.get("captured_at")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(ET).strftime("%-I:%M %p ET")
    except ValueError:
        return None


def _sim(p):
    parts = (p.get("sim_projection") or "").replace(" - ", " ").split()
    if len(parts) != 4:
        return None
    return {parts[0]: float(parts[1]), parts[2]: float(parts[3])}


def render(pick, settled=False):
    side, home, away = pick["side"], pick["home"], pick["away"]
    opp = home if side == away else away
    pal = palette(side)
    P, on_P = pal["P"], pal["on_P"]
    city, name, _ = team_ref(side)
    ocity, oname, _ = team_ref(opp)
    _, _, home_t = team_ref(home)

    img = _stock(pick)
    d = ImageDraw.Draw(img)
    L, R = s(92), W - s(92)
    cx = W // 2

    # ── 1. THE PICK: team ink panel ────────────────────────────────────────
    py0, py1 = s(146), s(700)
    d.rounded_rectangle((L, py0, R, py1), radius=s(34), fill=P)
    logo = team_logo(side, 500)
    lx, lsize = L + s(40), s(250)
    if logo:
        logo = logo.resize((logo.width * S, logo.height * S), Image.LANCZOS)
        mark = keyline_mark(logo, lsize, line=8)
        img.alpha_composite(mark, (lx, py0 + s(40)))
        d = ImageDraw.Draw(img)
    tx = lx + lsize + s(44)
    d.text((tx, py0 + s(64)), city, font=F("cond_sb", 48), fill=on_P)
    nf = fit_font(d, name, "cond", s(150), R - s(40) - tx, min_size=s(84))
    d.text((tx, py0 + s(112)), name, font=nf, fill=on_P)

    # the bet, the biggest thing on the card
    bet_y = py0 + s(330)
    d.line((L + s(40), bet_y - s(18), R - s(40), bet_y - s(18)), fill=on_P + (110,), width=s(3))
    d.text((L + s(40), bet_y + s(40)), "MONEYLINE", font=F("mono_b", 34), fill=on_P)
    of = F("black", 172)
    odds = _odds(pick)
    d.text((R - s(40) - text_w(d, odds, of), bet_y - s(8)), odds, font=of, fill=on_P)

    # ── 2. WHY (pre-game) / RESULT (settled) ───────────────────────────────
    sim = _sim(pick)
    wy = s(728)
    is_settled = settled and pick.get("status") in ("win", "loss", "push")
    if is_settled:
        # the result replaces the sim as the second thing you read
        col = {"win": WIN, "loss": LOSS}.get(pick["status"], MUTED)
        word = {"win": "WIN", "loss": "LOSS"}.get(pick["status"], "PUSH")
        pl = pick.get("pl") or 0
        d.rounded_rectangle((L, wy, R, wy + s(170)), radius=s(26), fill=col)
        d.text((L + s(40), wy + s(26)), word, font=F("black", 104), fill=CREAM)
        f2 = F("mono_b", 30)
        fin, money = final_str(pick), f"{pl:+g} $PP"
        d.text((R - s(40) - text_w(d, fin, f2), wy + s(40)), fin, font=f2, fill=CREAM)
        d.text((R - s(40) - text_w(d, money, F("black", 54)), wy + s(86)), money, font=F("black", 54), fill=CREAM)
        if sim and side in sim and opp in sim:
            d.text((L, wy + s(190)), f"The sim had it {side} {sim[side]:.1f} – {opp} {sim[opp]:.1f}",
                   font=F("cond_sb", 40), fill=MUTED)
    elif sim and side in sim and opp in sim:
        d.text((L, wy), "THE SIM", font=F("mono_b", 26), fill=MUTED)
        a_txt, b_txt = f"{side} {sim[side]:.1f}", f"{opp} {sim[opp]:.1f}"
        dash = "  –  "
        big = fit_font(d, a_txt + dash + b_txt, "black", s(92), R - L, min_size=s(56))
        x = L
        d.text((x, wy + s(40)), a_txt, font=big, fill=P if _contrast(P, CREAM) >= 2.2 else INK)
        x += text_w(d, a_txt, big)
        d.text((x, wy + s(40)), dash, font=big, fill=MUTED)
        x += text_w(d, dash, big)
        d.text((x, wy + s(40)), b_txt, font=big, fill=INK)
        margin = sim[side] - sim[opp]
        d.text((L, wy + s(146)), f"{name.title()} by {margin:.1f} runs in the sim", font=F("cond_sb", 46), fill=INK)

    at = "AT" if side == away else "VS"
    _game_band(img, pick, P, f"{at} {ocity} {oname}")
    _receipt(img, pick, "MORELLOSIMS.COM")

    out = paper_grain(img.convert("RGB"))
    return out.resize((1080, 1350), Image.LANCZOS)

def _game_band(img, pick, tint, title):
    """Opponent/date/park band with the home park's engraved plate."""
    home = pick["home"]
    _, _, home_t = team_ref(home)
    L, R = s(92), W - s(92)
    gy0, gy1 = s(978), s(1158)
    band = Image.new("RGBA", (R - L, gy1 - gy0), _mix(tint, CREAM, 0.86) + (255,))
    plate = os.path.join(PLATES, f"{home}.png")
    if os.path.exists(plate):
        m = Image.open(plate).convert("L")
        pw = int((R - L) * 0.62)
        m = m.resize((pw, int(m.height * pw / m.width)), Image.LANCZOS)
        ink = Image.new("RGBA", m.size, _mix(tint, CREAM, 0.35) + (0,))
        ink.putalpha(m.point(lambda v: int(v * 0.85)))
        band.alpha_composite(ink, (band.width - pw + s(40), (band.height - m.height) // 2 + s(20)))
    mask = Image.new("L", band.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, band.width, band.height), radius=s(28), fill=255)
    img.paste(band, (L, gy0), mask)
    d = ImageDraw.Draw(img)
    d.text((L + s(36), gy0 + s(30)), title, font=fit_font(d, title, "cond", s(56), s(560), min_size=s(40)), fill=INK)
    when = datetime.strptime(pick["date"], "%Y-%m-%d").strftime("%a %b %-d").upper()
    d.text((L + s(36), gy0 + s(100)), f"{when} · {pick.get('game_time') or ''}".strip(" ·"), font=F("mono_b", 28), fill=INK)
    d.text((L + s(36), gy0 + s(140)), home_t["venue"].upper(), font=F("mono_b", 24), fill=MUTED)


def _receipt(img, pick, footer):
    d = ImageDraw.Draw(img)
    L, R, cx = s(92), W - s(92), W // 2
    logged = _logged(pick)
    rf = F("mono_b", 22)
    left = f"LOGGED {logged} · BEFORE FIRST PITCH" if logged else "LOGGED BEFORE FIRST PITCH"
    d.text((L, s(1186)), left, font=rf, fill=MUTED)
    right = f"{pick.get('units')} $PP"
    d.text((R - text_w(d, right, rf), s(1186)), right, font=rf, fill=MUTED)
    ff = F("mono_b", 26)
    d.text((cx - text_w(d, footer, ff) / 2, s(1232)), footer, font=ff, fill=INK)


def _stock(pick):
    img = Image.new("RGBA", (W, H), BG + (255,))
    x0, y0, x1, y1 = s(44), s(44), W - s(44), H - s(44)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x0, y0 + s(16), x1, y1 + s(16)), radius=s(54), fill=(0, 0, 0, 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(s(22))))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x0, y0, x1, y1), radius=s(54), fill=CREAM + (255,))
    picks = load_picks()
    set_no = next((i for i, p in enumerate(picks, 1) if p["id"] == pick["id"]), None)
    mf = F("mono_b", 24)
    d.text((s(92), s(96)), "MORELLO SIMS", font=mf, fill=INK)
    tag = f"C{pick.get('conf')}" + (f" · No. {set_no}" if set_no else "")
    d.text((W - s(92) - text_w(d, tag, mf), s(96)), tag, font=mf, fill=INK)
    return img


HOUSE = (18, 56, 214)        # brand guide house blue, #1238D6


def sealed(pick):
    """The same card, locked: what X sees before first pitch.

    The pick panel and the sim line are the real card's pixels blurred hard
    and recolored to house blue, so no team color, logo, name or price
    survives. The game band names both teams with "@" (VS/AT would reveal
    the side). Same layout as the reveal, so the unlock maps one-to-one."""
    from PIL import ImageOps
    img = _stock(pick)
    L, R, cx = s(92), W - s(92), W // 2

    def locked(box, radius, blobs):
        """Blurred texture built from FIXED placeholder shapes (same for every
        pick), never from the real card: blurring real type left ghosts of the
        price and its +/- sign (checked 2026-09-30). Nothing to recover."""
        w, h = box[2] - box[0], box[3] - box[1]
        g = Image.new("L", (w, h), 40)
        gd = ImageDraw.Draw(g)
        for (bx0, by0, bx1, by1, v) in blobs:
            gd.rounded_rectangle((s(bx0), s(by0), s(bx1), s(by1)), radius=s(18), fill=v)
        g = g.filter(ImageFilter.GaussianBlur(s(26)))
        tile = ImageOps.colorize(g, black=(10, 26, 110), white=(120, 150, 250)).convert("RGBA")
        mask = Image.new("L", tile.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
        img.paste(tile, box[:2], mask)

    # panel: logo, city, name, rule, label, price — generic positions
    locked((L, s(146), R, s(700)), s(34),
           [(40, 40, 290, 290, 150), (330, 60, 520, 110, 120), (330, 120, 840, 270, 170),
            (40, 300, 856, 316, 110), (40, 380, 300, 420, 120), (470, 330, 856, 500, 180)])
    # sim row: two score blocks
    locked((L, s(768), R, s(930)), s(24), [(20, 30, 380, 120, 170), (470, 30, 856, 120, 150)])
    d = ImageDraw.Draw(img)
    sf = F("black", 150)
    d.text((cx - text_w(d, "SEALED", sf) / 2, s(300)), "SEALED", font=sf, fill=CREAM)
    sub = f"C{pick.get('conf')} PLAY · {'MONEYLINE' if pick.get('bet_type', 'ml') == 'ml' else 'SPREAD'}"
    d.text((cx - text_w(d, sub, F("mono_b", 34)) / 2, s(490)), sub, font=F("mono_b", 34), fill=CREAM)
    d.text((L, s(728)), "THE SIM", font=F("mono_b", 26), fill=MUTED)
    msg = "MEMBERS HAVE IT NOW"
    mf = F("cond", 64)
    d.text((cx - text_w(d, msg, mf) / 2, s(812)), msg, font=mf, fill=CREAM)
    a_name, h_name = team_ref(pick["away"])[1], team_ref(pick["home"])[1]
    _game_band(img, pick, HOUSE, f"{a_name} @ {h_name}")
    _receipt(img, pick, "UNLOCK · MORELLOSIMS.COM")
    out = paper_grain(img.convert("RGB"))
    return out.resize((1080, 1350), Image.LANCZOS)


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
    path = os.path.join(a.out, f"pick-{kind}{pick['id']}.png")
    (sealed(pick) if a.sealed else render(pick, a.settled)).save(path)
    print(path)

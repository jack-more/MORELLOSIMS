#!/usr/bin/env python3
"""Sealed pick card: what X sees before first pitch.

X posts are blurred by default (owner rule, 2026-09-30). Blurring only the
team name is not enough — the series card's colors, logo and odds give the
side away — so the whole real card is blurred hard and recolored to house
blue (no team color survives), and the facts that are safe to show are set
crisp on top: matchup, first pitch, confidence, when it was logged.

  python3 scripts/render_sealed.py --pick-id 2026-09-27-mlb-ATL-MIA-ml [--out DIR]
"""

import argparse
import os
import sys
from datetime import datetime

from PIL import Image, ImageDraw, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from render_cards_v2 import text_w, fit_font  # noqa: E402
from render_series_card import REPO, S, W, H, CREAM, s, F, load_picks, team_ref  # noqa: E402

DEEP = (8, 20, 86)
GLOW = (96, 128, 244)


def _base(pick):
    """The real card when we can draw it, else a plain field — always blurred."""
    if pick.get("sport", "mlb") == "mlb":
        import render_series_card
        try:
            return render_series_card.render(pick, False).convert("L")
        except Exception:
            pass
    return Image.new("L", (1080, 1350), 90)


def sealed_card(pick, logged=None):
    blur = _base(pick).filter(ImageFilter.GaussianBlur(30))
    img = ImageOps.colorize(blur, black=DEEP, white=GLOW).resize((W, H), Image.BICUBIC).convert("RGBA")
    d = ImageDraw.Draw(img)

    sport = (pick.get("sport") or "mlb").upper()
    away, home = pick.get("away", ""), pick.get("home", "")
    cx = W / 2

    def center(text, fnt, y, fill=CREAM):
        d.text((cx - text_w(d, text, fnt) / 2, y), text, font=fnt, fill=fill)

    # masthead
    mf = F("mono_b", 24)
    d.text((s(72), s(70)), "MORELLO SIMS", font=mf, fill=CREAM)
    right = f"{pick['date'][:4]} {sport} SERIES"
    d.text((W - s(72) - text_w(d, right, mf), s(70)), right, font=mf, fill=CREAM)
    d.line((s(72), s(112), W - s(72), s(112)), fill=CREAM + (150,), width=s(2))

    # the game (safe: it names both teams, not the side)
    mu = f"{team_ref(away)[1] if sport == 'MLB' else away}  @  {team_ref(home)[1] if sport == 'MLB' else home}"
    center(mu.upper(), fit_font(d, mu.upper(), "cond", s(96), W - s(160), min_size=s(56)), s(300))
    when = datetime.strptime(pick["date"], "%Y-%m-%d").strftime("%b %-d").upper()
    tip = "FIRST PITCH" if sport == "MLB" else "TIP"
    center(f"{when} · {tip} {pick.get('game_time') or ''}".strip(), F("mono_b", 30), s(420))

    # the seal
    bw, bh = s(640), s(250)
    bx, by = cx - bw / 2, s(560)
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=s(22), outline=CREAM, width=s(6))
    center("SEALED", F("black", 132), by + s(38))
    conf = pick.get("conf")
    center(f"C{conf} CONFIDENCE" if conf else "OFFICIAL PLAY", F("mono_b", 30), by + bh + s(40))

    # receipt + call
    logged = logged or pick.get("published_at") or pick.get("captured_at")
    if logged:
        try:
            t = datetime.fromisoformat(str(logged).replace("Z", "+00:00"))
            from datetime import timedelta, timezone
            t = t.astimezone(timezone(timedelta(hours=-4)))
            logged = t.strftime("%-I:%M %p ET")
        except ValueError:
            pass
        center(f"LOGGED {logged} · BEFORE THE GAME", F("mono_b", 26), s(1040), CREAM + (220,))
    center("MEMBERS HAVE IT NOW", F("cond", 64), s(1110))
    center("MORELLOSIMS.COM", F("mono_b", 30), s(1200))

    return img.convert("RGB").resize((1080, 1350), Image.LANCZOS)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick-id", required=True)
    ap.add_argument("--out", default=os.path.join(REPO, "posters", "v2"))
    a = ap.parse_args()
    pick = next((p for p in load_picks() if p["id"] == a.pick_id), None)
    if not pick:
        raise SystemExit(f"pick id not found: {a.pick_id}")
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, f"sealed-{pick['id']}.png")
    sealed_card(pick).save(path)
    print(path)

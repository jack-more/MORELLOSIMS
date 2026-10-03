#!/usr/bin/env python3
"""Field card (prototype): the home park's field, drawn to scale, as the pick.

Surface-as-canvas, after the owner's Sport-Info-Design board: a full-bleed
sheet in the picked team's primary ink, one white line drawing of the real
park (MLB fieldInfo fence distances, rulebook infield), a thin inset frame,
and the specs set in mono around the border like a printed towel's
dimensions — the top line upside down, the sides running vertically.

  python3 scripts/render_field_card.py --pick-id 2026-09-26-mlb-TB-PHI-ml [--out DIR]
"""

import argparse
import math
import os
import sys
from datetime import datetime

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "video"))

from render_cards_v2 import text_w, fit_font  # noqa: E402
from render_series_card import REPO, load_picks, team_ref, palette, _mix, _lum, _contrast  # noqa: E402
from render_card_back import s, F, S, W, H, WHITE, fence_knots, fence_curve, polar  # noqa: E402
import sim_reference as ref  # noqa: E402
from unit_fmt import stake_u  # noqa: E402

INSET = 64          # frame line, px from the edge (1x)
BAND = 40           # spec band between edge and frame


def surface(color):
    """Flat ink with a fine woven texture: two directions of fibre noise + grain."""
    rng = np.random.default_rng(7)
    h, w = H, W
    base = np.ones((h, w, 3), np.float32) * np.array(color, np.float32)
    rows = rng.normal(0, 1, (h, 1)).astype(np.float32)
    cols = rng.normal(0, 1, (1, w)).astype(np.float32)
    weave = (np.repeat(rows, w, 1) * 0.6 + np.repeat(cols, h, 0) * 0.6)
    grain = rng.normal(0, 1, (h // 2, w // 2)).astype(np.float32)
    grain = np.asarray(Image.fromarray(((grain * 30) + 128).clip(0, 255).astype(np.uint8)).resize((w, h))) / 30.0 - 128 / 30.0
    k = 5.5 if _lum(color) < 0.2 else 4.0
    base += (weave * 0.55 + grain * 0.8)[..., None] * k
    return Image.fromarray(base.clip(0, 255).astype(np.uint8)).convert("RGBA")


def text_rot(img, text, fnt, fill, center, angle):
    d0 = ImageDraw.Draw(img)
    tw = text_w(d0, text, fnt)
    bb = d0.textbbox((0, 0), text, font=fnt)
    layer = Image.new("RGBA", (tw + s(8), bb[3] + s(8)), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((s(4), s(4)), text, font=fnt, fill=fill)
    layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(layer, (int(center[0] - layer.width / 2), int(center[1] - layer.height / 2)))


def render(pick):
    side, home = pick["side"], pick["home"]
    opp = home if side == pick["away"] else pick["away"]
    pal = palette(side)
    ink = pal["P"]
    if _lum(ink) > 0.45:                          # light primaries print as a deep shade
        ink = _mix(ink, (20, 20, 24), 0.45)
    line = WHITE
    # second ink: the team's alternate, when it prints clearly on the primary
    alt = pal["A"] if _contrast(pal["A"], ink) >= 2.4 else WHITE

    img = surface(ink)
    d = ImageDraw.Draw(img)
    fr = s(INSET)
    d.rectangle((fr, fr, W - fr, H - fr), outline=line, width=s(3))

    # ── the park, to scale ────────────────────────────────────────────────
    venue = ref.venue_for_team(home)
    fi = venue["fieldInfo"]
    knots = fence_knots(fi)
    fence = fence_curve(knots)
    ft = [polar(a, dist) for a, dist in fence]
    box = (s(INSET + 96), s(340), W - s(INSET + 96), H - s(INSET + 70))
    span_x = max(abs(x) for x, _ in ft) * 2
    span_y = max(y for _, y in ft)
    k = min((box[2] - box[0]) / span_x, (box[3] - box[1] - s(60)) / span_y)
    hx, hy = (box[0] + box[2]) / 2, box[3]
    P = lambda x, y: (hx + x * k, hy - y * k)  # noqa: E731

    lf, rf = knots[0], knots[-1]
    d.line([P(0, 0), P(*polar(lf[0], lf[1]))], fill=line, width=s(3))
    d.line([P(0, 0), P(*polar(rf[0], rf[1]))], fill=line, width=s(3))
    d.line([P(x, y) for x, y in ft], fill=alt, width=s(8), joint="curve")
    b = 90 / math.sqrt(2)
    d.line([P(0, 0), P(b, b), P(0, 2 * b), P(-b, b), P(0, 0)], fill=line, width=s(3), joint="curve")
    arc = [P(*(np.array(polar(a, 95)) + np.array((0, 60.5)))) for a in np.arange(-72, 72.1, 2)]
    d.line(arc, fill=line + (170,), width=s(2))
    mx, my = P(0, 60.5)
    d.ellipse((mx - s(7), my - s(7), mx + s(7), my + s(7)), fill=line)
    hxp, hyp = P(0, 0)
    d.polygon([(hxp, hyp + s(6)), (hxp - s(9), hyp - s(2)), (hxp - s(9), hyp - s(11)),
               (hxp + s(9), hyp - s(11)), (hxp + s(9), hyp - s(2))], fill=line)

    # distances at every published fence knot
    nf = F("cond", 44)
    for a, dist, key in knots:
        t = f"{int(dist)}"
        tw = text_w(d, t, nf)
        if key in ("leftLine", "rightLine"):      # foul poles: tuck inside, just below the corner
            x, y = P(*polar(a, dist))              # just outside the pole, in foul ground
            tx = x - s(12) - tw if key == "leftLine" else x + s(12)
            d.text((tx, y - s(8)), t, font=nf, fill=alt)
            continue
        x, y = P(*polar(a, dist + 12))
        d.text((x - tw / 2, y - s(46)), t, font=nf, fill=alt)

    # ── the pick: one line of type, big ─────────────────────────────────────
    city, name, _ = team_ref(side)
    odds = str(pick.get("odds") or "")
    odds = odds if odds.startswith(("+", "-")) else "+" + odds
    head = f"{name} {odds}"
    hf = fit_font(d, head, "cond", s(150), W - 2 * s(INSET + 70), min_size=s(80))
    d.text((W / 2 - text_w(d, head, hf) / 2, s(INSET + 70)), head, font=hf, fill=line)
    sub = f"MONEYLINE {'AT' if side == pick['away'] else 'VS'} {team_ref(opp)[0]}"
    sf = F("mono_b", 22)
    d.text((W / 2 - text_w(d, sub, sf) / 2, s(INSET + 70) + s(170)), sub, font=sf, fill=line)

    # ── specs around the border, towel-style ────────────────────────────────
    picks = load_picks()
    set_no = next(i for i, p in enumerate(picks, 1) if p["id"] == pick["id"])
    when = datetime.strptime(pick["date"], "%Y-%m-%d").strftime("%b %-d").upper()
    bf = F("mono_b", 20)
    mid = s(INSET / 2 + 2)
    top = f"MORELLO SIMS   ·   {pick['date'][:4]} MLB SERIES   ·   No. {set_no}"
    text_rot(img, top, bf, line, (W / 2, mid), 180)
    dims = " · ".join(f"{int(fi[k2])}" for k2 in ("leftLine", "center", "rightLine") if fi.get(k2))
    bottom = f"{venue['name'].upper()}   ·   {dims} FT   ·   {when} {pick.get('game_time') or ''}".strip()
    d = ImageDraw.Draw(img)
    d.text((W / 2 - text_w(d, bottom, bf) / 2, H - mid - s(14)), bottom, font=bf, fill=line)
    text_rot(img, f"C{pick.get('conf')} CONFIDENCE   ·   {stake_u(pick.get('units'))}", bf, line, (mid, H / 2), 90)
    text_rot(img, "LOGGED BEFORE FIRST PITCH   ·   MORELLOSIMS.COM", bf, line, (W - mid, H / 2), -90)

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
    path = os.path.join(a.out, f"field-{pick['id']}.png")
    render(pick).save(path)
    print(path)

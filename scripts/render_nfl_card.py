#!/usr/bin/env python3
"""NFL pick card: the v3 layout (render_nba_card.py) for spreads.

One read, top to bottom: THE PICK (team, spread huge) → WHY (sim margin vs
the line, in plain words) → THE GAME (opponent, date, kickoff, venue over a
to-scale football field) → RECEIPT. sealed() is the same card, locked, built
from fixed placeholder shapes (never the real card blurred).

Sources (nothing typed from memory):
  data/reference/nfl_teams_espn_2026.json   names, colors, logos (ESPN); venues
      agreed by >= 2 of ESPN / nflverse / Wikipedia (ESPN is stale for LAR, LAC)
  data/reference/nfl_field_dimensions.json  field geometry (Wikipedia, quoted)
  pick["sim_projection"] = projected MARGIN for the picked side ("DET +6.5" =
      Lions win by 6.5), so edge = margin + line (DET -3.5 → 3.0 points).

  python3 scripts/render_nfl_card.py --pick-id <id> [--settled|--sealed] [--out DIR]
  python3 scripts/render_nfl_card.py --backtest <nflverse game_id> [--settled|--sealed]
  python3 scripts/render_nfl_card.py --samples [--out DIR]   # sample set from backtest games
"""

import argparse
import json
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
HOUSE = (18, 56, 214)
SNAP = json.load(open(os.path.join(REPO, "data", "reference", "nfl_teams_espn_2026.json")))["teams"]
FIELD = json.load(open(os.path.join(REPO, "data", "reference", "nfl_field_dimensions.json")))
LOGOS = os.path.join(REPO, "posters", "assets", "nfl-team-logos")
BACKTEST_GAMES = os.path.join(REPO, "nfl_pipeline", "data", "backtest_games.csv")
SCHEDULES = os.path.join(REPO, "nfl_pipeline", "data", "schedules.csv")


def team(abbr):
    t = SNAP.get(abbr)
    if not t:
        raise SystemExit(f"{abbr} not in data/reference/nfl_teams_espn_2026.json; run nfl_pipeline/reference.py")
    return t


def palette(abbr):
    t = team(abbr)
    P, A = _hex(t["color"]), _hex(t["alt"])
    if _lum(P) > 0.55:                       # very light primaries print their alt
        P, A = A, P
    on_P = CREAM if _contrast(CREAM, P) >= _contrast(INK, P) else INK
    return P, A, on_P


def logo(abbr, size):
    t = team(abbr)
    os.makedirs(LOGOS, exist_ok=True)
    path = os.path.join(LOGOS, f"espn-{t['espn_abbr'].lower()}.png")
    if not os.path.exists(path):
        try:
            req = urllib.request.Request(t["logo"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r, open(path, "wb") as f:
                f.write(r.read())
        except Exception:
            return None
    img = Image.open(path).convert("RGBA")
    img.thumbnail((size, size), Image.LANCZOS)
    return img


def load_picks():
    import picks_store  # seal mode: sealed picks open with PICKS_SEAL_KEY
    return sorted(picks_store.load_picks("nfl"), key=lambda p: (p["date"], p["id"]))


def _num(v):
    return f"{v:+.1f}" if v else "PK"


def _logged(p):
    ts = p.get("published_at") or p.get("captured_at")
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(ET).strftime("%-I:%M %p ET")
    except (TypeError, ValueError):
        return None


def field_plate(tint, width, height, k, pad_ft=4.0):
    """To-scale NFL field, length horizontal, right end line pad_ft inside x = width,
    centerline at y = height / 2. k = pixels per foot."""
    f = FIELD
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ox, oy = width - pad_ft * k, height / 2
    P = lambda x, y: (ox - x * k, oy + y * k)          # x = ft from right end line, y = ft from center  # noqa: E731
    half_w = f["width_ft"] / 2
    ez = f["end_zone_yd"] * 3
    lw = max(3, int(k * 0.9))
    thin = max(2, int(k * 0.5))
    # boundary (sidelines + end lines; out of the crop vertically, kept for scale)
    d.rectangle((*P(f["length_ft"], -half_w), *P(0, half_w)), outline=tint, width=lw * 2)
    # goal lines and every 5-yard line between them
    step = f["yard_line_interval_yd"] * 3
    x = ez
    while x <= f["length_ft"] - ez + 0.01:
        is_goal = abs(x - ez) < 0.01 or abs(x - (f["length_ft"] - ez)) < 0.01
        d.line((P(x, -half_w), P(x, half_w)), fill=tint, width=lw * (2 if is_goal else 1))
        x += step
    # hash marks: 2-ft ticks every yard; inner edge hash_from_sideline from each sideline
    inner = half_w - f["hash_from_sideline_ft"]
    for yd in range(1, 100):
        if yd % f["yard_line_interval_yd"] == 0:
            continue
        xx = ez + yd * 3
        for sgn in (-1, 1):
            d.line((P(xx, sgn * inner), P(xx, sgn * (inner + f["hash_tick_ft"]))), fill=tint, width=thin)
    # try line: 3 ft, centered, at the 2-yard line (both ends)
    for gx in (ez + f["try_line_yd"] * 3, f["length_ft"] - ez - f["try_line_yd"] * 3):
        d.line((P(gx, -f["try_line_ft"] / 2), P(gx, f["try_line_ft"] / 2)), fill=tint, width=lw)
    # goal posts (top view): crossbar over each end line, uprights 18'6" apart
    gw = f["goalpost_width_ft"] / 2
    for ex in (0, f["length_ft"]):
        d.line((P(ex, -gw), P(ex, gw)), fill=tint, width=lw * 3)
        for sgn in (-1, 1):
            cx, cy = P(ex, sgn * gw)
            r = k * 1.2
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=tint)
    return img


def _stock(pick, tag=None):
    img = Image.new("RGBA", (W, H), BG + (255,))
    x0, y0, x1, y1 = s(44), s(44), W - s(44), H - s(44)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x0, y0 + s(16), x1, y1 + s(16)), radius=s(54), fill=(0, 0, 0, 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(s(22))))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x0, y0, x1, y1), radius=s(54), fill=CREAM + (255,))
    mf = F("mono_b", 24)
    d.text((s(92), s(96)), "MORELLO SIMS", font=mf, fill=INK)
    if tag is None:
        set_no = next((i for i, p in enumerate(load_picks(), 1) if p["id"] == pick["id"]), None)
        tag = f"C{pick.get('conf')}" + (f" · NFL No. {set_no}" if set_no else " · NFL")
    d.text((W - s(92) - text_w(d, tag, mf), s(96)), tag, font=mf, fill=INK)
    return img


def venue_for(pick):
    return pick.get("venue") or team(pick["home"])["venue"] or ""


def _band(img, pick, tint, title):
    L, R = s(92), W - s(92)
    gy0, gy1 = s(978), s(1158)
    bh = gy1 - gy0
    bg = _mix(tint, CREAM, 0.86)
    band = Image.new("RGBA", (R - L, bh), bg + (255,))
    # To scale, one end of the field: the end zone, goal post and ~30 yards
    # fill the right half of the band (cropped top/bottom around the hash
    # marks, like the MLB park plate); the left half stays clear for text.
    visible_ft = FIELD["end_zone_yd"] * 3 + 100          # end zone + 33 yards
    k = band.width * 0.44 / visible_ft
    plate = field_plate(_mix(tint, CREAM, 0.22) + (255,), int((FIELD["length_ft"] + 4) * k) + s(4),
                        int(FIELD["width_ft"] * k), k)
    keep = int((visible_ft + 4) * k) + s(4)
    plate = plate.crop((plate.width - keep, 0, plate.width, plate.height))
    fade = Image.linear_gradient("L").rotate(90, expand=True).resize((s(140), plate.height))
    alpha = plate.getchannel("A")
    alpha.paste(Image.composite(alpha.crop((0, 0, s(140), plate.height)), Image.new("L", (s(140), plate.height), 0),
                                ImageOps.mirror(fade)), (0, 0))
    plate.putalpha(alpha)
    band.alpha_composite(plate, (band.width - plate.width - s(20), (band.height - plate.height) // 2))
    mask = Image.new("L", band.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, band.width, band.height), radius=s(28), fill=255)
    img.paste(band, (L, gy0), mask)
    d = ImageDraw.Draw(img)
    d.text((L + s(36), gy0 + s(30)), title, font=fit_font(d, title, "cond", s(56), s(440), min_size=s(34)), fill=INK)
    when = datetime.strptime(pick["date"], "%Y-%m-%d").strftime("%a %b %-d").upper()
    ko = pick.get("game_time") or ""
    d.text((L + s(36), gy0 + s(100)), f"{when} · {ko}".strip(" ·"), font=F("mono_b", 28), fill=INK)
    d.text((L + s(36), gy0 + s(140)), venue_for(pick).upper(), font=F("mono_b", 24), fill=MUTED)


def _receipt(img, pick, footer, left=None):
    d = ImageDraw.Draw(img)
    L, R, cx = s(92), W - s(92), W // 2
    logged = _logged(pick)
    rf = F("mono_b", 22)
    left = left or (f"LOGGED {logged} · BEFORE KICKOFF" if logged else "LOGGED BEFORE KICKOFF")
    d.text((L, s(1186)), left, font=rf, fill=MUTED)
    right = f"{pick.get('units')} $PP" if pick.get("units") is not None else ""
    d.text((R - text_w(d, right, rf), s(1186)), right, font=rf, fill=MUTED)
    ff = F("mono_b", 26)
    d.text((cx - text_w(d, footer, ff) / 2, s(1232)), footer, font=ff, fill=INK)


def why_line(name, margin, line):
    """'LIONS WIN BY 6.5' + 'The line gives -3.5. That's 3.0 points of edge.'"""
    head = f"{name.upper()} {'WIN' if margin >= 0 else 'LOSE'} BY {abs(margin):.1f}"
    edge = margin + line
    return head, f"The line gives {_num(line)}. That's {edge:.1f} points of edge."


def render(pick, settled=False, tag=None, receipt=None):
    side, home, away = pick["side"], pick["home"], pick["away"]
    opp = home if side == away else away
    P, A, on_P = palette(side)
    t, o = team(side), team(opp)
    img = _stock(pick, tag)
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
    d.text((L + s(40), bet_y + s(40)), f"SPREAD · {pick.get('odds')}", font=F("mono_b", 34), fill=on_P)
    big = _num(float(pick.get("line") or 0))
    of = F("black", 172)
    d.text((R - s(40) - text_w(d, big, of), bet_y - s(8)), big, font=of, fill=on_P)

    # 2. WHY / RESULT
    wy = s(728)
    margin = None
    try:
        margin = float((pick.get("sim_projection") or "").split()[-1])
    except (ValueError, IndexError):
        pass
    line = float(pick.get("line") or 0)
    if settled and pick.get("status") in ("win", "loss", "push"):
        col = {"win": WIN, "loss": LOSS}.get(pick["status"], MUTED)
        word = {"win": "WIN", "loss": "LOSS"}.get(pick["status"], "PUSH")
        d.rounded_rectangle((L, wy, R, wy + s(170)), radius=s(26), fill=col)
        d.text((L + s(40), wy + s(26)), word, font=F("black", 104), fill=CREAM)
        try:
            a_pts, h_pts = str(pick.get("result")).split("-")
            fin = f"{away} {a_pts} – {home} {h_pts}"
        except ValueError:
            fin = str(pick.get("result") or "")
        money = f"{(pick.get('pl') or 0):+g} $PP" if pick.get("pl") is not None else ""
        d.text((R - s(40) - text_w(d, fin, F("mono_b", 30)), wy + s(40)), fin, font=F("mono_b", 30), fill=CREAM)
        if money:
            d.text((R - s(40) - text_w(d, money, F("black", 54)), wy + s(86)), money, font=F("black", 54), fill=CREAM)
        if margin is not None:
            head, sub = why_line(t["name"], margin, line)
            d.text((L, wy + s(190)), f"The sim: {head.lower().capitalize()}. {sub}", font=F("cond_sb", 34), fill=MUTED)
    elif margin is not None:
        d.text((L, wy), "THE SIM", font=F("mono_b", 26), fill=MUTED)
        head, sub = why_line(t["name"], margin, line)
        hf = fit_font(d, head, "black", s(92), R - L, min_size=s(56))
        d.text((L, wy + s(40)), head, font=hf, fill=P if _contrast(P, CREAM) >= 2.2 else INK)
        d.text((L, wy + s(146)), sub, font=F("cond_sb", 46), fill=INK)

    at = "AT" if side == away else "VS"
    _band(img, pick, P, f"{at} {o['display'].upper()}")
    _receipt(img, pick, "MORELLOSIMS.COM", receipt)
    return paper_grain(img.convert("RGB")).resize((1080, 1350), Image.LANCZOS)


def sealed(pick, tag=None, receipt=None):
    """Same card, locked. Texture from fixed placeholder shapes (never the
    real card), matchup as 'A @ B' so VS/AT can't reveal the side."""
    img = _stock(pick, tag)
    L, R, cx = s(92), W - s(92), W // 2

    def locked(box, radius, blobs):
        w, h = box[2] - box[0], box[3] - box[1]
        g = Image.new("L", (w, h), 40)
        gd = ImageDraw.Draw(g)
        for bx0, by0, bx1, by1, v in blobs:
            gd.rounded_rectangle((s(bx0), s(by0), s(bx1), s(by1)), radius=s(18), fill=v)
        g = g.filter(ImageFilter.GaussianBlur(s(70)))
        tile = ImageOps.colorize(g, black=(10, 26, 110), white=(120, 150, 250)).convert("RGBA")
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
    sub = f"C{pick.get('conf')} PLAY · SPREAD"
    d.text((cx - text_w(d, sub, F("mono_b", 34)) / 2, s(490)), sub, font=F("mono_b", 34), fill=CREAM)
    d.text((L, s(728)), "THE SIM", font=F("mono_b", 26), fill=MUTED)
    msg, mf = "MEMBERS HAVE IT NOW", F("cond", 64)
    d.text((cx - text_w(d, msg, mf) / 2, s(812)), msg, font=mf, fill=CREAM)
    _band(img, pick, HOUSE, f"{team(pick['away'])['name'].upper()} @ {team(pick['home'])['name'].upper()}")
    _receipt(img, pick, "UNLOCK · MORELLOSIMS.COM", receipt)
    return paper_grain(img.convert("RGB")).resize((1080, 1350), Image.LANCZOS)


# ── backtest samples (no published NFL picks exist; publishing is off) ──

def backtest_pick(game_id):
    """A pick-shaped dict for a walk-forward backtest game (model side vs the
    closing line). Labelled BACKTEST on the card; never a published pick."""
    import pandas as pd
    b = pd.read_csv(BACKTEST_GAMES)
    row = b[b["game_id"] == game_id]
    if row.empty:
        raise SystemExit(f"{game_id} not in {BACKTEST_GAMES}")
    g = row.iloc[0]
    sc = pd.read_csv(SCHEDULES)
    sg = sc[sc["game_id"] == game_id].iloc[0]
    home_side = g["edge"] > 0
    side = g["home_team"] if home_side else g["away_team"]
    line = -g["spread_line"] if home_side else g["spread_line"]
    margin = g["pred"] if home_side else -g["pred"]
    d = g["result"] - g["spread_line"]
    status = "push" if d == 0 else ("win" if (d > 0) == home_side else "loss")
    gt = str(sg.get("gametime") or "")
    try:
        game_time = datetime.strptime(gt, "%H:%M").strftime("%-I:%M %p ET")
    except ValueError:
        game_time = ""
    return {
        "id": f"backtest-{game_id}", "sport": "nfl", "date": str(g["gameday"]), "away": g["away_team"],
        "home": g["home_team"], "matchup": f"{g['away_team']} @ {g['home_team']}", "side": side,
        "line": round(float(line), 1), "odds": -110, "conf": None, "units": None,
        "sim_projection": f"{side} {margin:+.1f}", "game_time": game_time,
        "venue": sg.get("stadium") if isinstance(sg.get("stadium"), str) else None,
        "status": status, "result": f"{int(sg['away_score'])}-{int(sg['home_score'])}",
        "pl": None,   # backtest: no stake was ever placed
    }


SAMPLES = ["2024_05_ARI_SF", "2024_08_NYG_PIT", "2024_01_MIN_NYG", "2024_02_NO_DAL"]


def render_backtest(game_id, out, settled=False, is_sealed=False):
    p = backtest_pick(game_id)
    tag = "BACKTEST · NOT A PICK"
    receipt = "WALK-FORWARD BACKTEST · CLOSING LINE"
    if is_sealed:
        p["conf"] = 8
        img = sealed(p, tag="SAMPLE · SEALED VARIANT", receipt="BACKTEST GAME · NOT A PICK")
    else:
        img = render(p, settled, tag=tag, receipt=receipt)
    kind = "sealed-" if is_sealed else "settled-" if settled else ""
    path = os.path.join(out, f"nfl-{kind}{p['id']}.jpg")
    img.save(path, quality=90)
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick-id")
    ap.add_argument("--backtest")
    ap.add_argument("--samples", action="store_true")
    ap.add_argument("--settled", action="store_true")
    ap.add_argument("--sealed", action="store_true")
    ap.add_argument("--out", default=os.path.join(REPO, "posters", "v2"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.samples:
        print(render_backtest(SAMPLES[0], a.out))                  # pre-game card
        print(render_backtest(SAMPLES[1], a.out, settled=True))    # settled (a win)
        print(render_backtest(SAMPLES[2], a.out, settled=True))    # settled (a loss)
        print(render_backtest(SAMPLES[3], a.out, is_sealed=True))  # sealed variant
    elif a.backtest:
        print(render_backtest(a.backtest, a.out, a.settled, a.sealed))
    else:
        pick = next((p for p in load_picks() if p["id"] == a.pick_id), None)
        if not pick:
            raise SystemExit(f"pick id not found: {a.pick_id}")
        kind = "sealed-" if a.sealed else "settled-" if a.settled else ""
        path = os.path.join(a.out, f"nfl-{kind}{pick['id']}.png")
        (sealed(pick) if a.sealed else render(pick, a.settled)).save(path)
        print(path)

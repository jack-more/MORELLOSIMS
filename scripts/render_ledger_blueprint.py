#!/usr/bin/env python3
"""Ledger cards in the blueprint language of the card back.

The record is drawn, not tabulated: a to-scale running-$PP line with every
pick as a mark, dimension callouts for the peak and the current mark, a text
wall of every settled pick, and the totals set big at the foot.

Headline = tracked picks of the live model only. Hand-logged and retired-era
records sit in the footnote, never in the headline.

  python3 scripts/render_ledger_blueprint.py --sport mlb|nba|nfl [--out DIR]
"""

import argparse
import json
import os
import sys
from datetime import datetime

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "video"))

from render_cards_v2 import text_w, fit_font  # noqa: E402
from render_series_card import REPO, CREAM, load_picks  # noqa: E402
from render_card_back import (  # noqa: E402
    s, F, S, W, H, BLUE, WHITE, CARD, FRAME, CX0, CX1, card_mask, grain_layer, on_background,
)
import numpy as np  # noqa: E402
from unit_fmt import stake_u, pl_u  # noqa: E402

WIN_TINT = (140, 232, 170)
LOSS_TINT = (255, 150, 140)

Y_HEAD = 122
Y_RULE1 = 236
PLOT = (136, 272, 944, 690)       # running $PP drawing
Y_RULE2 = 726
Y_WALL = 744
Y_RULE3 = 1014
Y_FOOT = 1030


def md(iso):
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %-d").upper()


def odds_s(p):
    o = str(p.get("odds") or "")
    return o if not o or o.startswith(("+", "-")) else "+" + o


def rec(w, l, pu=0):
    return f"{w}-{l}" + (f"-{pu}" if pu else "")


def data(sport):
    base = json.load(open(os.path.join(REPO, "picks", "baselines.json")))
    settled = lambda ps: sorted([p for p in ps if p.get("status") in ("win", "loss", "push")],
                                key=lambda p: (p["date"], p["id"]))
    notes = []
    if sport == "mlb":
        era = json.load(open(os.path.join(REPO, "picks", "model_era.json")))["start_date"]
        allp = settled(load_picks())
        rows = [p for p in allp if p["date"] >= era]
        old = [p for p in allp if p["date"] < era]
        ow = sum(p["status"] == "win" for p in old); ol = sum(p["status"] == "loss" for p in old)
        opu = sum(p["status"] == "push" for p in old)
        ork = sum(p.get("units") or 0 for p in old); opl = sum(p.get("pl") or 0 for p in old)
        b = base["mlb"]
        notes = [f"PREVIOUS MODEL {md(old[0]['date'])}–{md(old[-1]['date'])}: {rec(ow, ol, opu)}, {100 * opl / ork:+.1f}%. RETIRED.",
                 f"APRIL, LOGGED BY HAND BEFORE TRACKING: {rec(b['wins'], b['losses'])}."]
    elif sport == "nba":
        # every individually logged NBA pick (the auto-tracked picks/nba.json rows are a subset)
        import csv
        rows = []
        for x in csv.DictReader(open(os.path.join(REPO, "nba_pipeline", "data", "picks.csv"))):
            st = {"W": "win", "L": "loss", "P": "push"}.get(x["result"])
            if not st:
                continue                      # unsettled
            rows.append({"date": x["date"], "id": x["date"] + x["side"], "side": x["side"].split()[0],
                         "pick_text": x["side"], "bet_type": x["type"], "odds": x["odds"] or None,
                         "status": st, "pl": float(x["profit"] or 0), "units": float(x["risk"] or 0)})
        rows.sort(key=lambda p: (p["date"], p["id"]))
        from datetime import timedelta
        before = (datetime.strptime(rows[0]["date"], "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        notes = [f"OCT 22 – {md(before)} WAS LOGGED AS SEASON TOTALS, NOT PICK BY PICK."]
    else:
        rows = []
    return rows, notes


class LedgerCard:
    def __init__(self, sport):
        self.sport = sport
        self.rows, self.notes = data(sport)
        self.img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def stock(self):
        d = self.d
        d.rounded_rectangle(CARD, radius=s(54), fill=CREAM + (255,))
        d.rounded_rectangle(FRAME, radius=s(40), fill=BLUE + (255,))
        grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        g = ImageDraw.Draw(grid)
        step = s(24)
        for i, x in enumerate(range(FRAME[0], FRAME[2], step)):
            g.line((x, FRAME[1], x, FRAME[3]), fill=WHITE + (34 if i % 4 == 0 else 14,), width=S)
        for i, y in enumerate(range(FRAME[1], FRAME[3], step)):
            g.line((FRAME[0], y, FRAME[2], y), fill=WHITE + (34 if i % 4 == 0 else 14,), width=S)
        clip = Image.new("L", (W, H), 0)
        ImageDraw.Draw(clip).rounded_rectangle(FRAME, radius=s(40), fill=255)
        grid.putalpha(Image.composite(grid.getchannel("A"), Image.new("L", (W, H), 0), clip))
        self.img.alpha_composite(grid)
        self.d = d = ImageDraw.Draw(self.img)
        inset = s(14)
        d.rounded_rectangle((FRAME[0] + inset, FRAME[1] + inset, FRAME[2] - inset, FRAME[3] - inset),
                            radius=s(28), outline=WHITE, width=s(2))
        for y in (Y_RULE1, Y_RULE2, Y_RULE3):
            d.line((CX0, s(y), CX1, s(y)), fill=WHITE, width=s(2))

    def header(self):
        d, rows = self.d, self.rows
        w = sum(p["status"] == "win" for p in rows); l = sum(p["status"] == "loss" for p in rows)
        pu = sum(p["status"] == "push" for p in rows)
        d.text((CX0, s(Y_HEAD)), "MORELLO SIMS", font=F("black", 38), fill=WHITE)
        span = f"{md(rows[0]['date'])} → {md(rows[-1]['date'])}" if rows else "OPENING THE BOOKS"
        d.text((CX0, s(Y_HEAD + 60)), f"{self.sport.upper()} LEDGER · {span}", font=F("mono_b", 20), fill=WHITE)
        lab = "TRACKED IN PUBLIC"
        d.text((CX1 - text_w(d, lab, F("mono_b", 20)), s(Y_HEAD + 2)), lab, font=F("mono_b", 20), fill=WHITE)
        big = rec(w, l, pu)
        bf = F("cond", 68)
        d.text((CX1 - text_w(d, big, bf), s(Y_HEAD + 18)), big, font=bf, fill=WHITE)

    # ── the drawing: running $PP, every pick a mark ─────────────────────────
    def plot(self):
        d, rows = self.d, self.rows
        x0, y0, x1, y1 = (s(v) for v in PLOT)
        lab_f, num_f = F("mono_b", 16), F("cond", 40)
        if not rows:
            ymid = (y0 + y1) // 2
            d.line((x0, ymid, x1, ymid), fill=WHITE, width=s(4))
            d.ellipse((x0 - s(9), ymid - s(9), x0 + s(9), ymid + s(9)), outline=WHITE, width=s(4), fill=BLUE)
            d.text((x0 + s(18), ymid - s(56)), "0u", font=num_f, fill=WHITE)
            d.text((x0 + s(18), ymid + s(18)), "PICK 001 LANDS HERE", font=lab_f, fill=WHITE)
            for i in range(1, 17):
                x = x0 + i * (x1 - x0) / 16
                d.line((x, ymid - s(8), x, ymid + s(8)), fill=WHITE + (0,), width=s(2))
                d.line((x, ymid - s(8), x, ymid + s(8)), fill=WHITE, width=s(2))
            return
        run, acc = [0.0], 0.0
        for p in rows:
            acc += p.get("pl") or 0
            run.append(acc)
        lo, hi = min(run), max(run)
        pad = (hi - lo) * 0.12 or 20
        lo, hi = lo - pad, hi + pad
        ty0, ty1 = y0 + s(36), y1 - s(64)                  # leave room for callouts + axis
        X = lambda i: x0 + s(8) + i * (x1 - x0 - s(16)) / (len(run) - 1)
        Y = lambda v: ty1 - (v - lo) / (hi - lo) * (ty1 - ty0)

        # zero line, dashed
        zy = Y(0)
        for dx in range(int(x0), int(x1), s(20)):
            d.line((dx, zy, dx + s(10), zy), fill=WHITE, width=s(2))
        d.text((x1 - text_w(d, "0u", lab_f), zy + s(8)), "0u", font=lab_f, fill=WHITE)

        # stepped ledger line: flat between picks, a riser at each result
        pts = [(X(0), Y(0))]
        for i in range(1, len(run)):
            pts += [(X(i), Y(run[i - 1])), (X(i), Y(run[i]))]
        d.line(pts, fill=WHITE, width=s(5), joint="curve")

        # every pick a mark on the axis: filled = win, open = loss
        ay = y1 - s(30)
        d.line((x0, ay, x1, ay), fill=WHITE, width=s(2))
        gap = (x1 - x0 - s(16)) / max(len(rows), 1)
        r = max(S, min(s(6), int(gap * 0.36)))
        dense = len(rows) > 60
        for i, p in enumerate(rows, 1):
            x = X(i)
            if dense:                          # barcode: wins tick up, losses tick down
                h = s(12)
                if p["status"] == "win":
                    d.line((x, ay, x, ay - h), fill=WHITE, width=max(S, int(gap * 0.5)))
                elif p["status"] == "loss":
                    d.line((x, ay, x, ay + h), fill=WHITE, width=max(S, int(gap * 0.5)))
                continue
            if p["status"] == "win":
                d.rectangle((x - r, ay - r, x + r, ay + r), fill=WHITE)
            elif p["status"] == "loss":
                d.rectangle((x - r, ay - r, x + r, ay + r), fill=BLUE, outline=WHITE, width=s(2))
            else:
                d.line((x - r, ay, x + r, ay), fill=WHITE, width=s(3))
        d.text((x0, ay + s(12)), md(rows[0]["date"]), font=lab_f, fill=WHITE)
        end = md(rows[-1]["date"])
        d.text((x1 - text_w(d, end, lab_f), ay + s(12)), end, font=lab_f, fill=WHITE)
        if dense:
            key = "WINS UP · LOSSES DOWN"
            d.text(((x0 + x1) / 2 - text_w(d, key, lab_f) / 2, ay + s(16)), key, font=lab_f, fill=WHITE)
            self.plot_callouts(run, X, Y)
            return
        # legend drawn as shapes (the mono face has no box glyphs)
        kw = s(12) + s(8) + text_w(d, "WIN", lab_f) + s(28) + s(12) + s(8) + text_w(d, "LOSS", lab_f)
        kx, ky = (x0 + x1) / 2 - kw / 2, ay + s(15)
        d.rectangle((kx, ky, kx + s(12), ky + s(12)), fill=WHITE)
        kx += s(20); d.text((kx, ay + s(12)), "WIN", font=lab_f, fill=WHITE)
        kx += text_w(d, "WIN", lab_f) + s(28)
        d.rectangle((kx, ky, kx + s(12), ky + s(12)), fill=BLUE, outline=WHITE, width=s(2))
        kx += s(20); d.text((kx, ay + s(12)), "LOSS", font=lab_f, fill=WHITE)

        self.plot_callouts(run, X, Y)

    def plot_callouts(self, run, X, Y):
        # dimension callouts: peak and current, leader lines like the fence marks
        ip = max(range(len(run)), key=lambda i: run[i])
        self.callout(X(ip), Y(run[ip]), f"{run[ip]:+,.0f}", "PEAK", up=True)
        last = len(run) - 1
        if last != ip:
            self.callout(X(last), Y(run[last]), f"{run[last]:+,.0f}", "NOW", up=run[last] >= run[last - 1])

    def callout(self, x, y, num, lab, up=True):
        d = self.d
        num_f, lab_f = F("cond", 40), F("mono_b", 16)
        d.ellipse((x - s(8), y - s(8), x + s(8), y + s(8)), fill=BLUE, outline=WHITE, width=s(3))
        ly = y - s(46) if up else y + s(46)
        d.line((x, y + (-s(8) if up else s(8)), x, ly), fill=WHITE, width=s(2))
        tw = text_w(d, num, num_f)
        full = tw + s(6) + text_w(d, lab, lab_f)          # number + label must stay inside the frame
        tx = min(max(x - tw / 2, s(PLOT[0])), s(PLOT[2]) - full)
        ty = ly - s(44) if up else ly + s(2)
        d.text((tx, ty), num, font=num_f, fill=WHITE)
        d.text((tx + tw + s(6), ty + s(20)), lab, font=lab_f, fill=WHITE)

    # ── text wall: every settled pick ──────────────────────────────────────
    def wall(self):
        d, rows = self.d, self.rows
        d.text((CX0, s(Y_WALL)), "EVERY PICK, IN ORDER", font=F("mono_b", 16), fill=WHITE)
        if not rows:
            msg = ("NO ENTRIES YET. EVERY PICK IS LOGGED BEFORE KICKOFF AT A FLAT 1U, "
                   "SETTLED IN PUBLIC, NOTHING DELETED.")
            self.flow([(w + " ", WHITE) for w in msg.split()], F("cond_sb", 40))
            return
        words = []
        for p in rows:
            col = WHITE if p["status"] == "win" else WHITE + (130,)
            tag = {"win": "W", "loss": "L", "push": "P"}[p["status"]]
            # spreads show the line (the -110 is just juice); moneylines show the price
            if p.get("bet_type") == "spread":
                bet = p.get("pick_text")
            else:
                bet = f"{p['side']} {odds_s(p)}" if p.get("odds") else f"{p['side']} ML"
            words.append((f"{md(p['date'])} {bet} {tag}. ", col))
        size = 40
        while size > 12 and not self.flow(words, F("cond_sb", size), dry=True):
            size -= 2
        self.flow(words, F("cond_sb", size))

    def flow(self, words, fnt, dry=False):
        d = self.d
        x, y = CX0, s(Y_WALL + 30)
        lh = int(fnt.size * 1.08)
        bottom = s(Y_RULE3 - 10)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        for text, col in words:
            w = text_w(d, text, fnt)
            if x + w > CX1 + s(6):
                x, y = CX0, y + lh
            if y + lh > bottom:
                return False
            if not dry:
                ld.text((x, y), text, font=fnt, fill=col if len(col) == 4 else col + (255,))
            x += w
        if not dry:
            self.img.alpha_composite(layer)
            self.d = ImageDraw.Draw(self.img)
        return True

    # ── foot: the totals, big ───────────────────────────────────────────────
    def foot(self):
        d, rows = self.d, self.rows
        rk = sum(p.get("units") or 0 for p in rows)
        pl = sum(p.get("pl") or 0 for p in rows)
        big = pl_u(pl) if rows else "0u"
        bf = F("cond", 150)
        bx = CX1 - text_w(d, big, bf)
        d.text((bx, s(Y_FOOT + 4)), big, font=bf, fill=WHITE)
        sub = f"NET UNITS · {stake_u(rk)} RISKED · {100 * pl / rk:+.1f}% ROI" if rk else "NET UNITS · FLAT 1U PER PICK"
        sf = F("mono_b", 18)
        d.text((CX1 - text_w(d, sub, sf), s(Y_FOOT + 180)), sub, font=sf, fill=WHITE)
        # footnote: other records, never blended into the headline
        nf = F("mono_b", 15)
        y = s(Y_FOOT + 16)
        maxw = bx - CX0 - s(36)
        for n in self.notes + ["MORELLOSIMS.COM"]:
            for line in wrap(d, n, nf, maxw):
                d.text((CX0, y), line, font=nf, fill=WHITE)
                y += s(24)
            y += s(10)

    def render(self):
        self.stock(); self.header(); self.plot(); self.wall(); self.foot()
        arr = np.asarray(self.img.resize((1080, 1350), Image.LANCZOS), dtype=np.float32).copy()
        arr[..., :3] = np.clip(arr[..., :3] + grain_layer((1080, 1350))[..., None], 0, 255)
        out = Image.fromarray(arr.astype(np.uint8))
        out.putalpha(card_mask())
        return on_background(out)


def wrap(d, text, fnt, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if text_w(d, t, fnt) <= maxw:
            cur = t
        else:
            lines.append(cur); cur = w
    return lines + [cur] if cur else lines


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sport", required=True, choices=["mlb", "nba", "nfl"])
    ap.add_argument("--out", default=os.path.join(REPO, "posters", "v2"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, f"ledger-{a.sport}-{datetime.now().strftime('%Y-%m-%d')}.png")
    LedgerCard(a.sport).render().save(path)
    print(path)

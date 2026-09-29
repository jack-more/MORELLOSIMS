#!/usr/bin/env python3
"""MorelloSims series card BACK — the blueprint.

Same stock and set number as the series card front, printed in one blue
with white line work: the home park drawn to scale from its published fence
distances, both starting lineups set as a wall of type, and the sim's run
distribution plus win probability.

  python3 scripts/video/render_card_back.py --pick-id 2026-09-26-mlb-TB-PHI-ml [--out DIR]

Data, and what is stored vs derived
-----------------------------------
Stored model output (picks/mlb.json, written by scripts/build_mlb_sim.py):
  sim_projection "TB 11.7 - PHI 8.4"   projected runs per side
  model_wp_calibrated 63.2             win probability of the picked side
The sim is a deterministic projection: it does NOT store a simulated score
distribution. The run distribution drawn here is DERIVED for display:
  each side's runs ~ NegativeBinomial(mean = stored projection, size = k),
  independent, with one shared k solved so that
  P(pick > opp) + 0.5 * P(tie) == stored win probability.
So the bars are consistent with the two stored numbers, but their shape is
an assumption (NB is the usual over-dispersed model for MLB run scoring),
not a model output. Seeded draws make every render identical.

Per-hitter matchup colour (stored model output, via mlbsim/lineup_scores/,
written by scripts/export_lineup_scores.py): each hitter's name sits on a
highlighter chip coloured by his MOMO vs today's opposing starter, scaled
within the game across both lineups (best = light green, worst = red). No
scores file -> plain white wall, no legend.

Sourced facts (sim_reference.py, MLB Stats API snapshots in data/reference/):
  fence distances  /api/v1/venues/{id}?hydrate=location,fieldInfo
  lineups          /api/v1/schedule?...&hydrate=lineups,probablePitcher + /api/v1/game/{pk}/boxscore
Geometry assumptions (not in the API): the seven fieldInfo distances are
placed at 45/30/15/0 degrees off dead centre (leftLine, left, leftCenter,
center, ...), and the fence between them is a smooth interpolation. Parks
that omit a key are drawn from the keys they do publish. Infield uses the
rulebook dimensions: 90 ft bases, 60 ft 6 in to the rubber.
"""

import argparse
import math
import os
import sys
from datetime import datetime

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from render_cards_v2 import REPO, font, text_w, fit_font  # noqa: E402
from render_series_card import load_picks, team_ref, BG, CREAM, YELLOW  # noqa: E402
import sim_reference as ref  # noqa: E402
from export_lineup_scores import INK, load_scores, scale_game  # noqa: E402

S = 2
W, H = 1080 * S, 1350 * S
BLUE = (18, 56, 214)          # Klein-ish print blue, #1238D6
WHITE = (247, 245, 238)
N_DRAWS = 20000

FENCE_ANGLES = {"leftLine": -45, "left": -30, "leftCenter": -15, "center": 0,
                "rightCenter": 15, "right": 30, "rightLine": 45}   # assumed, see docstring


def s(v):
    return int(round(v * S))


def F(kind, size):
    return font(kind, s(size))


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


# ── sim numbers ────────────────────────────────────────────────────────────

def parse_projection(pick):
    parts = (pick.get("sim_projection") or "").replace(" - ", " ").split()
    if len(parts) != 4:
        raise SystemExit(f"{pick['id']}: sim_projection not in 'AAA x - BBB y' form: {pick.get('sim_projection')!r}")
    return {parts[0]: float(parts[1]), parts[2]: float(parts[3])}


def _nb_pmf(mean, k, n=160):
    x = np.arange(n)
    if k is None:
        from math import lgamma
        return np.exp(-mean + x * math.log(mean) - np.array([lgamma(v + 1) for v in x]))
    p = k / (k + mean)
    lg = np.vectorize(math.lgamma)
    return np.exp(lg(x + k) - math.lgamma(k) - lg(x + 1) + k * math.log(p) + x * math.log(1 - p))


def _win_prob(a, b):
    cb = np.concatenate([[0], np.cumsum(b)[:-1]])          # P(B < x)
    return float((a * cb).sum() + 0.5 * (a * b).sum())


class SimDist:
    """Stored projection + win prob, and the NB run distribution derived from them."""

    def __init__(self, pick):
        proj = parse_projection(pick)
        self.side = pick["side"]
        self.opp = pick["home"] if self.side == pick["away"] else pick["away"]
        self.mu_side, self.mu_opp = proj[self.side], proj[self.opp]
        wp = pick.get("model_wp_calibrated") or pick.get("model_wp_raw")
        if wp is None:
            raise SystemExit(f"{pick['id']}: no stored model win probability")
        self.wp = float(wp)                                  # stored, percent
        target = self.wp / 100
        pois = _win_prob(_nb_pmf(self.mu_side, None), _nb_pmf(self.mu_opp, None))
        if target >= pois:
            self.k = None                                    # Poisson is the least dispersed option
        else:
            lo, hi = 0.2, 5000.0
            for _ in range(60):                              # WP rises monotonically with k
                mid = math.sqrt(lo * hi)
                if _win_prob(_nb_pmf(self.mu_side, mid), _nb_pmf(self.mu_opp, mid)) < target:
                    lo = mid
                else:
                    hi = mid
            self.k = math.sqrt(lo * hi)
        rng = np.random.default_rng(int(pick.get("game_pk") or 0))
        self.a = self._draw(rng, self.mu_side)
        self.b = self._draw(rng, self.mu_opp)
        # running estimate of P(side wins) over the draws (ties split)
        w = (self.a > self.b) + 0.5 * (self.a == self.b)
        self.running = np.cumsum(w) / np.arange(1, N_DRAWS + 1)

    def _draw(self, rng, mean):
        if self.k is None:
            return rng.poisson(mean, N_DRAWS)
        return rng.negative_binomial(self.k, self.k / (self.k + mean), N_DRAWS)

    def shown_wp(self, frac, lock):
        """WP readout during the parse: the running estimate over the draws so
        far, eased onto the stored number as `lock` goes 0->1. At lock=1 it is
        exactly the stored model value."""
        n = max(1, int(N_DRAWS * frac))
        est = self.running[n - 1] * 100
        lk = ease(lock)
        return est * (1 - lk) + self.wp * lk


# ── field geometry (feet, home plate at origin, +y to dead centre) ───────

def fence_knots(fi):
    knots = [(FENCE_ANGLES[k], float(fi[k]), k) for k in FENCE_ANGLES if fi.get(k) is not None]
    need = {"leftLine", "center", "rightLine"}
    if not need <= {k for _, _, k in knots}:
        raise SystemExit(f"fieldInfo lacks {need - {k for _, _, k in knots}}; refresh the venue snapshot")
    return knots


def fence_curve(knots, step=0.5):
    """Catmull-Rom through (angle, distance) knots, sampled every `step` degrees."""
    ang = [k[0] for k in knots]
    dist = [k[1] for k in knots]
    pts = []
    for i in range(len(knots) - 1):
        a0, a1 = ang[i], ang[i + 1]
        p0 = dist[max(i - 1, 0)]
        p1, p2 = dist[i], dist[i + 1]
        p3 = dist[min(i + 2, len(dist) - 1)]
        n = max(2, int((a1 - a0) / step))
        for j in range(n):
            t = j / n
            d = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                       + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)
            pts.append((a0 + (a1 - a0) * t, d))
    pts.append((ang[-1], dist[-1]))
    return pts


def polar(angle, d):
    return d * math.sin(math.radians(angle)), d * math.cos(math.radians(angle))


class Path:
    """Polyline in px with arc-length so it can draw itself on."""

    def __init__(self, pts, width, color=WHITE, dash=None):
        self.pts, self.width, self.color, self.dash = pts, width, color, dash
        seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        self.cum = np.concatenate([[0], np.cumsum(seg)])
        self.length = self.cum[-1]

    def partial(self, t):
        if t <= 0:
            return []
        if t >= 1:
            return self.pts
        L = self.length * t
        i = int(np.searchsorted(self.cum, L)) - 1
        i = max(0, min(i, len(self.pts) - 2))
        f = (L - self.cum[i]) / max(self.cum[i + 1] - self.cum[i], 1e-9)
        (x0, y0), (x1, y1) = self.pts[i], self.pts[i + 1]
        return self.pts[: i + 1] + [(x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)]

    def draw(self, d, t):
        pts = self.partial(t)
        if len(pts) < 2:
            return
        if not self.dash:
            d.line(pts, fill=self.color, width=self.width, joint="curve")
            return
        on, off = self.dash
        acc, draw_on = 0.0, True
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            seg = math.dist((x0, y0), (x1, y1))
            pos = 0.0
            while pos < seg:
                run = min((on if draw_on else off) - acc, seg - pos)
                if draw_on:
                    a, b = pos / seg, (pos + run) / seg
                    d.line((x0 + (x1 - x0) * a, y0 + (y1 - y0) * a, x0 + (x1 - x0) * b, y0 + (y1 - y0) * b),
                           fill=self.color, width=self.width)
                pos += run
                acc += run
                if acc >= (on if draw_on else off) - 1e-9:
                    acc, draw_on = 0.0, not draw_on


# ── the card ───────────────────────────────────────────────────────────────

CARD = (s(44), s(44), W - s(44), H - s(44))
FRAME = (s(92), s(92), W - s(92), H - s(92))
CX0, CX1 = s(136), W - s(136)

Y_HEAD = 122
Y_RULE1 = 236
FIELD_BOX = (136, 248, 944, 716)
Y_RULE2 = 726
WALL_BOX = (136, 744, 944, 998)
WALL_BOX_KEYED = (136, 776, 944, 1000)      # room for the matchup legend above the wall
Y_LEGEND = 744
Y_RULE3 = 1014
SIM_Y = 1030


def card_mask(scale=1):
    """Anti-aliased card-stock silhouette at `scale` (1 = 1080x1350)."""
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rounded_rectangle(CARD, radius=s(54), fill=255)
    return m.resize((W * scale // S, H * scale // S), Image.LANCZOS)


def grain_layer(size, seed=11, amount=3.0):
    rng = np.random.default_rng(seed)
    n = rng.normal(0, 1, (size[1] // 3 + 1, size[0] // 3 + 1)).astype(np.float32)
    im = Image.fromarray(np.clip(128 + n * 40, 0, 255).astype(np.uint8)).resize(size, Image.BILINEAR)
    return (np.asarray(im, dtype=np.float32) - 128) / 40 * amount


class CardBack:
    def __init__(self, pick):
        self.pick = pick
        picks = load_picks()
        self.set_no = next(i for i, p in enumerate(picks, 1) if p["id"] == pick["id"])
        self.year = pick["date"][:4]
        self.venue = ref.venue_for_team(pick["home"])
        self.lu = ref.lineups(pick)
        self.scale = self._matchup_scale()
        self.sim = SimDist(pick)
        self._field_geometry()
        self.base = self._base()
        self.wall, self.wall_words = self._wall()
        self.grain = grain_layer((1080, 1350))
        self.mask = card_mask()

    # static print: stock, blue, grid, header, rules, captions
    def _base(self):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
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
        img.alpha_composite(grid)
        d = ImageDraw.Draw(img)
        inset = s(14)
        d.rounded_rectangle((FRAME[0] + inset, FRAME[1] + inset, FRAME[2] - inset, FRAME[3] - inset),
                            radius=s(28), outline=WHITE, width=s(2))

        p = self.pick
        when = datetime.strptime(p["date"], "%Y-%m-%d").strftime("%b %-d").upper()
        d.text((CX0, s(Y_HEAD)), "MORELLO SIMS", font=F("black", 38), fill=WHITE)
        meta = f"{p['away']} @ {p['home']} · {when} · {p.get('game_time') or ''}".strip(" ·")
        d.text((CX0, s(Y_HEAD + 60)), meta, font=F("mono_b", 20), fill=WHITE)
        ser = f"{self.year} MLB SERIES"
        d.text((CX1 - text_w(d, ser, F("mono_b", 20)), s(Y_HEAD + 2)), ser, font=F("mono_b", 20), fill=WHITE)
        no = f"No. {self.set_no}"
        nf = F("cond", 68)
        d.text((CX1 - text_w(d, no, nf), s(Y_HEAD + 18)), no, font=nf, fill=WHITE)
        for y in (Y_RULE1, Y_RULE2, Y_RULE3):
            d.line((CX0, s(y), CX1, s(y)), fill=WHITE, width=s(2))

        # matchup legend above the lineup wall (only when per-hitter scores exist)
        if self.scale:
            from export_lineup_scores import ramp
            lf = F("mono_b", 16)
            d.text((CX0, s(Y_LEGEND)), "MATCHUP TODAY", font=lf, fill=WHITE)
            n, cw, ch, g = 7, s(20), s(13), s(4)
            xr = CX1 - text_w(d, "WORST", lf)
            d.text((xr, s(Y_LEGEND)), "WORST", font=lf, fill=WHITE)
            x = xr - s(12) - (n * cw + (n - 1) * g)
            cy = s(Y_LEGEND) + s(3)
            for i in range(n):
                d.rounded_rectangle((x, cy, x + cw, cy + ch), radius=s(2), fill=ramp(1 - i / (n - 1)) + (255,))
                x += cw + g
            xb = xr - s(12) - (n * cw + (n - 1) * g) - s(12) - text_w(d, "BEST", lf)
            d.text((xb, s(Y_LEGEND)), "BEST", font=lf, fill=WHITE)

        # field captions: park + scale bar in the empty lower corners of the fan
        bx0, by0, bx1, by1 = [s(v) for v in FIELD_BOX]
        v = self.venue
        d.text((bx0, by1 - s(66)), v["name"].upper(), font=F("cond", 30), fill=WHITE)
        place = f"{(v.get('city') or '').upper()}, {v.get('state') or ''}".strip(", ")
        d.text((bx0, by1 - s(30)), place, font=F("mono_b", 17), fill=WHITE)
        L = 100 * self.px_per_ft
        sx1 = bx1
        sx0 = sx1 - L
        y = by1 - s(34)
        d.line((sx0, y, sx1, y), fill=WHITE, width=s(3))
        for x in (sx0, sx0 + L / 2, sx1):
            d.line((x, y - s(8), x, y + s(8)), fill=WHITE, width=s(2))
        f = F("mono_b", 17)
        d.text((sx0 - text_w(d, "0", f) / 2, y + s(12)), "0", font=f, fill=WHITE)
        d.text((sx1 - text_w(d, "100 FT", f), y + s(12)), "100 FT", font=f, fill=WHITE)

        # sim block labels
        d.text((CX0, s(SIM_Y)), "SIM RUNS", font=F("mono_b", 18), fill=WHITE)
        side, opp = self.sim.side, self.sim.opp
        lf = F("mono_b", 18)
        lx = s(HIST_X1)
        t2 = f"{opp}"
        d.text((lx - text_w(d, t2, lf), s(SIM_Y)), t2, font=lf, fill=WHITE)
        x2 = lx - text_w(d, t2, lf) - s(12)
        d.rectangle((x2 - s(14), s(SIM_Y + 5), x2, s(SIM_Y + 19)), outline=WHITE, width=s(2))
        x3 = x2 - s(30)
        d.text((x3 - text_w(d, side, lf), s(SIM_Y)), side, font=lf, fill=YELLOW)
        x4 = x3 - text_w(d, side, lf) - s(12)
        d.rectangle((x4 - s(14), s(SIM_Y + 5), x4, s(SIM_Y + 19)), fill=YELLOW)

        wx = s(WP_X0)
        d.text((wx, s(SIM_Y)), f"{side} WIN PROB", font=F("mono_b", 18), fill=WHITE)
        odds = str(p.get("odds") or "")
        if odds and not odds.startswith(("+", "-")):
            odds = "+" + odds
        tail = f"ML {odds} · C{p.get('conf')}"
        d.text((CX1 - text_w(d, tail, F("mono_b", 18)), s(SIM_Y)), tail, font=F("mono_b", 18), fill=WHITE)
        return img

    # ── field ──
    def _field_geometry(self):
        fi = self.venue["fieldInfo"]
        self.knots = fence_knots(fi)
        self.fence_ad = fence_curve(self.knots)
        fence_ft = [polar(a, d) for a, d in self.fence_ad]
        bx0, by0, bx1, by1 = FIELD_BOX
        xs = [p[0] for p in fence_ft]
        ys = [p[1] for p in fence_ft]
        span_x = max(max(xs), -min(xs)) * 2
        top_pad, bot_pad = 40, 24                       # room for distance labels / plate
        scale = min((by1 - by0 - top_pad - bot_pad) / max(ys), (bx1 - bx0 - 120) / span_x)
        self.px_per_ft = scale * S
        hx, hy = (bx0 + bx1) / 2 * S, (by1 - bot_pad) * S
        self.home_px = (hx, hy)
        P = lambda x, y: (hx + x * self.px_per_ft, hy - y * self.px_per_ft)  # noqa: E731
        self.P = P

        # distance rings (faint, dashed) inside the fence: 200 and 300 ft
        fa = np.array([a for a, _ in self.fence_ad])
        fd = np.array([d for _, d in self.fence_ad])
        self.rings = []
        for r in (200, 300):
            angs = [a for a in np.arange(-45, 45.01, 0.5) if r < np.interp(a, fa, fd) - 8]
            pts = [P(*polar(a, r)) for a in angs]
            if len(pts) > 2:
                self.rings.append((r, Path(pts, S, WHITE + (90,), dash=(s(4), s(6)))))

        lf, rf = self.knots[0], self.knots[-1]
        self.paths = []                                    # (start, end) share of the draw-on
        self.paths.append((0.00, 0.22, Path([P(0, 0), P(*polar(lf[0], lf[1]))], s(3))))
        self.paths.append((0.00, 0.22, Path([P(0, 0), P(*polar(rf[0], rf[1]))], s(3))))
        self.fence = Path([P(x, y) for x, y in fence_ft], s(5))
        self.paths.append((0.18, 0.78, self.fence))
        # infield, rulebook dimensions
        b = 90 / math.sqrt(2)
        diamond = [P(0, 0), P(b, b), P(0, 2 * b), P(-b, b), P(0, 0)]
        self.paths.append((0.70, 0.92, Path(diamond, s(3))))
        arc = [P(*(np.array(polar(a, 95)) + np.array((0, 60.5)))) for a in np.arange(-72, 72.1, 2)]
        arc = [pt for pt in arc]
        self.paths.append((0.74, 0.96, Path(arc, s(2), WHITE + (190,))))
        self.mound = P(0, 60.5)

        # label anchor for each published distance, just outside the fence
        self.labels = []
        for a, dist, key in self.knots:
            fx, fy = polar(a, dist)
            ox, oy = polar(a, dist + 26 / scale)
            tx0, ty0 = P(*polar(a, dist - 7 / scale))
            tx1, ty1 = P(*polar(a, dist + 7 / scale))
            share = 0.18 + 0.60 * (a + 45) / 90             # when the fence pen reaches it
            self.labels.append({"key": key, "dist": int(dist), "at": P(ox, oy), "tick": (tx0, ty0, tx1, ty1),
                                "t": share})

    def _draw_field(self, img, t):
        d = ImageDraw.Draw(img)
        ring_t = ease(t / 0.3)
        for r, path in self.rings:
            path.draw(d, ring_t)
        rf = F("mono_b", 15)
        if ring_t >= 1:
            for r, path in self.rings:
                x, y = self.P(*polar(-41, r))                # just inside the left-field line
                d.text((x + s(4), y - s(22)), str(r), font=rf, fill=WHITE + (170,))
        for a, b, path in self.paths:
            path.draw(d, (t - a) / (b - a))
        if t > 0.9:
            mx, my = self.mound
            r = 9 * self.px_per_ft
            d.ellipse((mx - r, my - r, mx + r, my + r), outline=WHITE, width=s(2))
            hx, hy = self.home_px
            q = s(6)
            d.polygon([(hx - q, hy - q), (hx + q, hy - q), (hx + q, hy), (hx, hy + q), (hx - q, hy)], fill=WHITE)
        lf = F("cond", 30)
        for lab in self.labels:
            u = (t - lab["t"]) / 0.12
            if u <= 0:
                continue
            u = min(u, 1)
            d.line(lab["tick"], fill=WHITE, width=s(3))
            val = str(int(round(lab["dist"] * ease(u)))) if u < 1 else str(lab["dist"])
            x, y = lab["at"]
            tw = text_w(d, val, lf)
            bb = d.textbbox((0, 0), val, font=lf)
            d.text((x - tw / 2 - bb[0], y - (bb[3] + bb[1]) / 2), val, font=lf, fill=WHITE)

    # ── lineup wall ──
    def _matchup_scale(self):
        """{hitter id: colour/rank} from the stored per-hitter scores, or None."""
        scores = load_scores(self.pick)
        if not scores:
            print(f"  card back: no mlbsim/lineup_scores for {self.pick['id']}; "
                  "run scripts/export_lineup_scores.py to colour the lineup")
            return None
        scale = scale_game(scores)
        ids = {r["id"] for sd in ("away", "home") for r in self.lu[sd]["lineup"]}
        if ids != set(scale):
            raise SystemExit(f"{self.pick['id']}: lineup_scores hitters {sorted(set(scale) ^ ids)} "
                             "differ from the lineup snapshot; re-export the scores")
        return scale

    def _wall(self):
        """Both lineups as one justified wall: TEAM label, then NAME POS. NAME POS. ... SP NAME.

        With matchup scores each hitter's name sits on a chip in his matchup
        colour. Spacing rules: the gap inside a name is a plain word space (it
        may wrap, and the chip splits with it); a position is glued to the name
        it follows; only the gaps between entries stretch to justify a line."""
        sc = self.scale
        # parts: (text, colour, key, join) where join is how the part attaches to the
        # one before it: "unit" (stretchable, may wrap), "name" (word space, may wrap),
        # "glue" (word space, never wraps)
        paras = []
        for sd in ("away", "home"):
            t = self.lu[sd]
            abbr = self.pick[sd]
            city, name, _ = team_ref(abbr)
            label_col = YELLOW if abbr == self.pick["side"] else WHITE
            parts = [(w, label_col, None, "unit" if i == 0 else "name") for i, w in enumerate(name.split())]
            for r in t["lineup"]:
                key = r["id"] if sc else None
                col = INK if sc else WHITE
                ws = r["name"].upper().rstrip(".").split()
                parts += [(w, col, key, "unit" if i == 0 else ("name" if sc else "unit")) for i, w in enumerate(ws)]
                parts.append((f"{r['pos']}.", WHITE + (150,), None, "glue" if sc else "unit"))
            if t["sp"].get("name"):
                sp = t["sp"]["name"].upper().rstrip(".").split()
                parts.append(("SP", WHITE + (150,), None, "unit"))
                sp[-1] += "."
                parts += [(w, WHITE, None, "name") for w in sp]
            paras.append(parts)

        bx0, by0, bx1, by1 = [s(v) for v in (WALL_BOX_KEYED if sc else WALL_BOX)]
        dummy = ImageDraw.Draw(Image.new("L", (1, 1)))
        pad = s(4) if sc else 0                                  # chip overhang each side
        inner = (bx1 - bx0) - 2 * pad

        def layout(size):
            f = font("cond", size)
            sp = text_w(dummy, "  ", f) / 2 * 1.05
            gaps = {"unit": sp + 2 * pad, "name": sp, "glue": sp + pad}
            lh = size * (1.12 if sc else 1.02)
            lines = []
            for pi, parts in enumerate(paras):
                atoms = []                                       # glue-joined runs never split
                for p in parts:
                    w = text_w(dummy, p[0], f)
                    if p[3] == "glue" and atoms:
                        atoms[-1]["parts"].append((p, w))
                    else:
                        atoms.append({"join": p[3], "parts": [(p, w)]})
                for a in atoms:
                    a["w"] = sum(w for _, w in a["parts"]) + gaps["glue"] * (len(a["parts"]) - 1)
                cur, cw = [], 0
                for a in atoms:
                    g = gaps[a["join"]] if cur else 0
                    if cur and cw + g + a["w"] > inner:
                        lines.append((cur, False, pi))
                        cur, cw, g = [], 0, 0
                    cur.append(a)
                    cw += g + a["w"]
                lines.append((cur, True, pi))
            height = len(lines) * lh + (len(paras) - 1) * lh * 0.35
            return f, gaps, lh, lines, height

        lo, hi = s(16), s(60)
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if layout(mid)[4] <= (by1 - by0):
                lo = mid
            else:
                hi = mid
        f, gaps, lh, lines, height = layout(lo)
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        asc = d.textbbox((0, 0), "H", font=f)
        cap = asc[3] - asc[1]
        ct, cb = s(5), s(5)                                     # chip above / below the cap height
        placed = []                                             # (x, y, w, part)
        y = by0 + ((by1 - by0) - height) / 2
        prev_p = 0
        for atoms, last, pi in lines:
            if pi != prev_p:
                y += lh * 0.35
                prev_p = pi
            base = sum(a["w"] for a in atoms) + sum(gaps[a["join"]] for a in atoms[1:])
            n_stretch = sum(1 for a in atoms[1:] if a["join"] == "unit")
            extra = 0 if last or not n_stretch else (inner - base) / n_stretch
            x = bx0 + pad
            for i, a in enumerate(atoms):
                if i:
                    x += gaps[a["join"]] + (extra if a["join"] == "unit" else 0)
                for j, (p, w) in enumerate(a["parts"]):
                    if j:
                        x += gaps["glue"]
                    placed.append((x, y, w, p))
                    x += w
            y += lh

        # one chip per run of the same hitter's words on a line
        chips = []
        for x, y, w, p in placed:
            key = p[2]
            if key is None:
                continue
            if chips and chips[-1][0] == key and chips[-1][2] == y:
                chips[-1][3] = x + w
            else:
                chips.append([key, x, y, x + w])
        chip_at = {}
        for key, x0, y0, x1 in chips:
            box = (x0 - pad, y0 - ct, x1 + pad, y0 + cap + cb)
            d.rounded_rectangle(box, radius=s(3), fill=sc[key]["rgb"] + (255,))
            chip_at[(key, y0)] = box

        words = []
        for x, y, w, (txt, col, key, _) in placed:
            d.text((x, y - asc[1]), txt, font=f, fill=col)
            if key is not None:
                bx = chip_at[(key, y)]
                # reveal the chip from its left edge to this word: names sweep on
                # like a highlighter pass during the parse. Exact chip rows, so a
                # reveal never bleeds into the next line's chips.
                words.append((bx[0], bx[1], x + w + (pad if x + w + pad >= bx[2] - 1 else 0), bx[3]))
            else:
                words.append((x - s(2), y - s(4), x + w + s(2), y + cap + s(6)))
        return img, words

    def _draw_wall(self, img, t):
        if t <= 0:
            return
        if t >= 1:
            img.alpha_composite(self.wall)
            return
        n = int(len(self.wall_words) * t)
        m = Image.new("L", (W, H), 0)
        md = ImageDraw.Draw(m)
        for box in self.wall_words[:n]:                     # reveal boxes, already padded
            md.rectangle(box, fill=255)
        layer = self.wall.copy()
        layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", (W, H), 0), m))
        img.alpha_composite(layer)
        # cursor block on the next word
        if n < len(self.wall_words):
            x0, y0, x1, y1 = self.wall_words[n]
            ImageDraw.Draw(img).rectangle((x0 + s(2), y0 + s(2), x0 + s(14), y1 - s(4)), fill=YELLOW)

    # ── sim block ──
    def _draw_sim(self, img, frac, lock):
        d = ImageDraw.Draw(img)
        sim = self.sim
        n = int(N_DRAWS * min(max(frac, 0), 1))
        top, base = s(SIM_Y + 40), s(SIM_Y + 158)
        x0, x1 = s(HIST_X0), s(HIST_X1)
        nb = HIST_BINS + 1
        bw = (x1 - x0) / nb
        d.line((x0, base, x1, base), fill=WHITE, width=s(2))
        af = F("mono_b", 15)
        for v in range(0, HIST_BINS + 1, 5):
            cx = x0 + (v + 0.5) * bw
            lab = str(v)
            d.line((cx, base, cx, base + s(6)), fill=WHITE, width=s(2))
            d.text((cx - text_w(d, lab, af) / 2, base + s(10)), lab, font=af, fill=WHITE)
        ca = np.bincount(np.minimum(sim.a, HIST_BINS), minlength=nb).astype(float)
        cb = np.bincount(np.minimum(sim.b, HIST_BINS), minlength=nb).astype(float)
        peak = max(ca[:HIST_BINS].max(), cb[:HIST_BINS].max())
        if n > 0:
            # Bars are the empirical histogram of the first n seeded draws, as
            # a share of n (so the shape is readable from the first frames and
            # sharpens as draws accumulate), grown to full height as n -> N.
            k = n / N_DRAWS
            scale = (N_DRAWS / peak) * (0.35 + 0.65 * ease(k)) / n
            ha = np.bincount(np.minimum(sim.a[:n], HIST_BINS), minlength=nb) * scale
            hb = np.bincount(np.minimum(sim.b[:n], HIST_BINS), minlength=nb) * scale
            # the far tail (>= HIST_BINS runs) is truncated from the chart, not piled into a spike
            ha[HIST_BINS:] = 0
            hb[HIST_BINS:] = 0
            hmax = base - top

            def step(h):
                pts = [(x0, base)]
                for i in range(nb):
                    y = base - min(h[i], 1.15) * hmax
                    pts += [(x0 + i * bw, y), (x0 + (i + 1) * bw, y)]
                return pts + [(x1, base)]
            pa, pb = step(ha), step(hb)
            d.polygon(pa, fill=YELLOW)
            d.line(pb, fill=WHITE, width=s(3), joint="curve")
            d.line((x0, base, x1, base), fill=WHITE, width=s(2))
        # projected means (stored numbers), shown once the draws are in
        if lock > 0:
            mf = F("cond", 26)
            for mu, col, lab in ((sim.mu_side, YELLOW, f"{sim.mu_side:g}"), (sim.mu_opp, WHITE, f"{sim.mu_opp:g}")):
                mx = x0 + (mu + 0.5) * bw
                a = int(255 * ease(lock * 2))
                dd = ImageDraw.Draw(img)
                for yy in range(int(top - s(4)), int(base), s(10)):
                    dd.line((mx, yy, mx, min(yy + s(5), base)), fill=col + (a,), width=s(2))
                tw = text_w(dd, lab, mf)
                lx = mx - tw / 2
                dd.text((lx, top - s(34)), lab, font=mf, fill=col + (a,))

        # win probability readout (nothing until the first draws land)
        if n == 0:
            return
        wp = sim.shown_wp(frac, lock)
        txt = f"{wp:.1f}%"
        big = F("black", 92)
        wx = s(WP_X0)
        d.text((wx - s(4), s(SIM_Y + 34)), txt, font=big, fill=WHITE)
        # split bar pick / opp
        by = s(SIM_Y + 150)
        bh = s(14)
        bx0, bx1 = wx, CX1
        split = bx0 + (bx1 - bx0) * wp / 100
        d.rectangle((bx0, by, split, by + bh), fill=YELLOW)
        d.rectangle((split, by, bx1, by + bh), outline=WHITE, width=s(2))
        lf = F("mono_b", 15)
        d.text((bx0, by + bh + s(8)), sim.side, font=lf, fill=YELLOW)
        d.text((bx1 - text_w(d, sim.opp, lf), by + bh + s(8)), sim.opp, font=lf, fill=WHITE)

    # ── compose ──
    def card(self, field=1.0, wall=1.0, draws=1.0, lock=1.0):
        """Card-only RGBA at 1080x1350 (transparent outside the stock)."""
        img = self.base.copy()
        self._draw_field(img, field)
        self._draw_wall(img, wall)
        self._draw_sim(img, draws, lock)
        out = img.resize((1080, 1350), Image.LANCZOS)
        arr = np.asarray(out, dtype=np.float32).copy()
        arr[..., :3] = np.clip(arr[..., :3] + self.grain[..., None], 0, 255)
        out = Image.fromarray(arr.astype(np.uint8))
        out.putalpha(self.mask)
        return out


HIST_X0, HIST_X1, HIST_BINS = 136, 596, 30
WP_X0 = 640


def card_shadow():
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((CARD[0], CARD[1] + s(16), CARD[2], CARD[3] + s(16)),
                                         radius=s(54), fill=(0, 0, 0, 150))
    return sh.filter(ImageFilter.GaussianBlur(s(22))).resize((1080, 1350), Image.LANCZOS)


def on_background(card_rgba, shadow=True):
    img = Image.new("RGBA", (1080, 1350), BG + (255,))
    if shadow:
        img.alpha_composite(card_shadow())
    img.alpha_composite(card_rgba)
    return img.convert("RGB")


def render_back(pick):
    return on_background(CardBack(pick).card())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick-id", required=True)
    ap.add_argument("--out", default=os.path.join(REPO, "posters", "v2"))
    a = ap.parse_args()
    pick = next((p for p in load_picks() if p["id"] == a.pick_id), None)
    if not pick:
        raise SystemExit(f"pick id not found: {a.pick_id}")
    os.makedirs(a.out, exist_ok=True)
    cb = CardBack(pick)
    path = os.path.join(a.out, f"series-back-{pick['id']}.png")
    on_background(cb.card()).save(path)
    k = "Poisson" if cb.sim.k is None else f"NB size k={cb.sim.k:.3f}"
    print(path)
    print(f"stored: {pick['sim_projection']}, WP {cb.sim.wp}% ({pick['side']}); derived: {k}")

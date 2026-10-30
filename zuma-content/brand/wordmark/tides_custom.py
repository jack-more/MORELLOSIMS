# "tides" round 2: five custom constructions, no exit tails, optically spaced.
# Bowls are superellipses so they echo zuma's rounded-rectangle bowls. Units as zuma_wm.py: x-height 100, y down.
#   python3 tides_custom.py -> tides_custom.json for options/board_custom.py
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zuma_wm import word as zuma_word, to_d
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union
from shapely import affinity

AS = 36.0      # ascender above the x-height
N = 2.6        # superellipse exponent: rounder than a rectangle, squarer than an ellipse
SLANT = 11.0

def se(cx, cy, rx, ry, a0, a1, n=96):
    # superellipse arc, degrees, 90 = top (y down), counter-clockwise on the page
    out = []
    for k in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * k / n); c, s = math.cos(a), math.sin(a)
        out.append((cx + rx * math.copysign(abs(c) ** (2 / N), c), cy - ry * math.copysign(abs(s) ** (2 / N), s)))
    return out

class Pen:
    # monoline by default; k < 1 squeezes x before stroking, so verticals stay s wide and horizontals thin to k*s (broad-nib contrast)
    def __init__(self, s, k=1.0): self.s, self.k = s, k
    def line(self, pts, cap='flat'):
        g = LineString([(x * self.k, y) for x, y in pts]).buffer(self.s * self.k / 2, cap_style=cap, join_style='round', quad_segs=32)
        return affinity.scale(g, 1 / self.k, 1, origin=(0, 0))
    def ring(self, cx, cy, rx, ry):
        return self.line(se(cx, cy, rx, ry, 0, 360, 160))

# each glyph returns its upright geometry; spacing is computed later from the slanted shapes
def g_t(p, o):
    h = p.s / 2; sx = 12 + h
    top = -AS * 0.55
    stem = p.line([(sx, top), (sx, 100)])
    if o.get('chisel'): stem = stem.difference(chisel(sx, top, p.s))
    bar = Pen(p.s * 0.8).line([(sx - 13, h * 0.8), (sx + 15, h * 0.8)])
    if ('lig' in o):  # crossbar runs on and becomes the top of the i
        bar = Pen(p.s * 0.8).line([(sx - 13, h * 0.8), (sx + 20 + o['lig'], h * 0.8)])
    return unary_union([stem, bar])

def g_i(p, o):
    h = p.s / 2; x = h
    stem = p.line([(x, 0 if not ('lig' in o) else h * 0.9 - h), (x, 100)])
    if o.get('chisel'): stem = stem.difference(chisel(x, 0, p.s))
    if ('lig' in o): return stem
    if o.get('wave'):  # the dot becomes a small swell
        pts = [(x - p.s * 1.3 + t * p.s * 2.6 / 24, -AS * 0.55 - math.sin(t / 24 * 2 * math.pi) * p.s * 0.45) for t in range(25)]
        return unary_union([stem, Pen(p.s * 0.8).line(pts)])
    d = p.s * 1.15
    return unary_union([stem, box(x - d / 2, -AS * 0.55 - d / 2, x + d / 2, -AS * 0.55 + d / 2)])

RX = 29.0
def g_d(p, o):
    h = p.s / 2; cx = RX + h
    sx = cx + RX - h * 0.15
    stem = p.line([(sx, -AS), (sx, 100)])
    if o.get('chisel'): stem = stem.difference(chisel(sx, -AS, p.s))
    return unary_union([p.ring(cx, 50, RX, 50 - h), stem])

def g_e(p, o):
    h = p.s / 2; cx = RX + h; yb = 50 + h * 0.2
    bar = p.line([(cx - RX, yb), (cx + RX, yb)])
    bowl = p.line(se(cx, 50, RX, 50 - h, 0, 322, 140))
    return unary_union([bar, bowl])

def g_s(p, o):
    h = p.s / 2; rx = RX * 0.8; cx = rx + h; ry = (100 - p.s) / 4
    up = se(cx, h + ry, rx, ry, 32, 270, 80)
    lo = se(cx, 100 - h - ry, rx, ry, 90, -148, 80)
    return p.line(up + lo[1:])

def chisel(x, ytop, s):
    # a 30-degree cut across the top of a stem, high on the right
    d = s * math.tan(math.radians(30))
    return Polygon([(x - s, ytop - 50), (x + s, ytop - 50), (x + s, ytop + d / 2 - 1e-3), (x - s, ytop + d * 1.5)])

def rounded(pts, radii, n=24):
    # polyline through pts; corner k is rounded with radii[k] (0 = sharp)
    out = [pts[0]]
    for k in range(1, len(pts) - 1):
        (ax, ay), (bx, by), (cx, cy) = pts[k - 1], pts[k], pts[k + 1]; r = radii[k]
        if not r: out.append((bx, by)); continue
        u = ((ax - bx), (ay - by)); v = ((cx - bx), (cy - by))
        lu, lv = math.hypot(*u), math.hypot(*v); u = (u[0] / lu, u[1] / lu); v = (v[0] / lv, v[1] / lv)
        p0 = (bx + u[0] * r, by + u[1] * r); p2 = (bx + v[0] * r, by + v[1] * r)
        for j in range(n + 1):  # quadratic through the corner: a quarter round for right angles
            t = j / n; a = math.pi / 2 * t
            w0, w1 = 1 - math.sin(a), 1 - math.cos(a)
            out.append((p0[0] + (bx - p0[0]) * 0 + (p2[0] - bx) * w1 + (bx - p0[0]) * (1 - w0) * 1, p0[1] + (p2[1] - by) * w1 + (by - p0[1]) * (1 - w0)))
    out.append(pts[-1]); return out

def z_d(p, o):
    h = p.s / 2; x0, x1, y0, y1 = h, 52 + h, h, 100 - h; R = (y1 - y0) / 2
    bowl = p.line(rounded([(x1, y0), (x0, y0), (x0, y1), (x1, y1)], [0, R, R, 0]))
    return unary_union([bowl, p.line([(x1, -AS), (x1, 100)])])

def z_e(p, o):
    h = p.s / 2; x0, x1, y0, y1 = h, 54 + h, h, 100 - h; yb = 52; R = (y1 - y0) / 2
    pts = [(x0, yb), (x1, yb), (x1, y0), (x0, y0), (x0, y1), (x1 - 4, y1)]
    return p.line(rounded(pts, [0, 0, 16, R, R, 0]))

def z_s(p, o):
    h = p.s / 2; x0, x1 = h, 46 + h; ym = 50; r1 = (ym - h) / 2; r2 = (100 - h - ym) / 2
    pts = [(x1, h), (x0, h), (x0, ym), (x1, ym), (x1, 100 - h), (x0, 100 - h)]
    return p.line(rounded(pts, [0, r1, r1, r2, r2, 0]))

def waterline(g, y=62, gap=3.2):
    # one level cut runs through every letter: the tide line
    return g.difference(box(-1e3, y - gap / 2, 1e3, y + gap / 2))

GLYPHS = (g_t, g_i, g_d, g_e, g_s)
ZGLYPHS = (g_t, g_i, z_d, z_e, z_s)

def space(glyphs, gap, cap=26.0):
    # optical spacing: across the x-height band, the average horizontal gap between neighbours equals `gap`;
    # how deep each side can count is capped so open shapes (e's mouth, s's ends) don't drift away
    placed, x = [], 0.0
    for g in glyphs:
        if not placed:
            g = affinity.translate(g, -g.bounds[0], 0); placed.append(g); continue
        L = placed[-1]; ys = [6 + k * 2 for k in range(45)]
        rL, lR = [], []
        for y in ys:
            a = L.intersection(LineString([(-1e4, y), (1e4, y)])); b = g.intersection(LineString([(-1e4, y), (1e4, y)]))
            rL.append(max(a.bounds[2], L.bounds[2] - cap) if not a.is_empty else L.bounds[2] - cap)
            lR.append(min(b.bounds[0], g.bounds[0] + cap) if not b.is_empty else g.bounds[0] + cap)
        shift = gap - sum(l - r for l, r in zip(lR, rL)) / len(ys)
        placed.append(affinity.translate(g, shift, 0))
    return placed

def tides(s, k=1.0, gap=None, slant=SLANT, **o):
    p = Pen(s, k)
    raw = [f(p, o) for f in (ZGLYPHS if o.get('zb') else GLYPHS)]
    if o.get('water'): raw = [waterline(g) for g in raw]
    raw = [affinity.skew(g, xs=-slant, origin=(0, 100)) for g in raw]
    if ('lig' in o):  # t and i are one shape: space them as one
        ti = unary_union([raw[0], affinity.translate(raw[1], 12 + s / 2 + 20 + o['lig'] - s / 2, 0)])
        raw = [ti] + raw[2:]
    placed = space(raw, gap if gap is not None else 14 + s * 1.15)
    g = unary_union(placed)
    return affinity.translate(g, -g.bounds[0], 0), g.bounds[2] - g.bounds[0]

OPTIONS = {
    '1': dict(s=13.0, note='Clean — thin monoline, bowls in zuma\'s squared-round shape'),
    '2': dict(s=17.0, k=0.32, note='Hairline — full-weight stems, hairline curves and bars (fashion contrast)'),
    '3': dict(s=13.0, zb=True, note='Built from zuma — round on the left, square on the right, exactly zuma\'s letter logic, thin'),
    '4': dict(s=13.0, zb=True, lig=0, note='Built from zuma + ligature — the t bar runs on into the i'),
    '5': dict(s=13.0, zb=True, water=True, note='Tide line — one level cut runs through every letter'),
}

if __name__ == '__main__':
    zg, zw, _ = zuma_word()
    out = {'zuma': to_d(zg.simplify(.03)), 'zuma_w': zw, 'asc': AS, 'opts': {}}
    for key, o in OPTIONS.items():
        o = dict(o); note = o.pop('note')
        g, w = tides(**o)
        pl = space([zg, g], 40.0, cap=30)
        out['opts'][key] = dict(note=note, d=to_d(g.simplify(.03)), w=w, x=pl[1].bounds[0])
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tides_custom.json'), 'w'))
    print({k: (round(v['w']), round(v['x'])) for k, v in out['opts'].items()}, zw)

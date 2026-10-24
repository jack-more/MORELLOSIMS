# "zuma" as one custom wordmark: heavy lowercase, one stem weight, one bowl radius, soft corners.
# Units: x-height 100, y down (0 = top, 100 = baseline). Writes zuma_wm.json.
import math, json
from shapely.geometry import Polygon, box, MultiPolygon, Point
from shapely.ops import unary_union
from shapely import affinity

W  = 30.0          # stem
H  = 26.0          # horizontals of the z (optically thinner than stems)
C  = 26.0          # counter width
B  = W + C + W     # bowl letter width: 86
RO = B / 2         # outer bowl radius: 43
RI = C / 2         # counter radius: 13
SOFT, INNER = 5.0, 2.5     # outer corner radius, inside corner radius
TRACK = 8.0

def rbox(x0, y0, x1, y1, r, corners):
    """Box with the named corners (tl, tr, bl, br) rounded to radius r."""
    g = box(x0, y0, x1, y1)
    for c in corners:
        cx = x0 + r if 'l' in c else x1 - r
        cy = y0 + r if 't' in c else y1 - r
        sq = box(min(cx, x0 if 'l' in c else x1), min(cy, y0 if 't' in c else y1), max(cx, x0 if 'l' in c else x1), max(cy, y0 if 't' in c else y1))
        g = g.difference(sq).union(Point(cx, cy).buffer(r, 64).intersection(sq))
    return g

def z():
    w, d = 80.0, 40.0
    g = unary_union([box(0, 0, w, H), box(0, 100 - H, w, 100),
                     Polygon([(w - d, H - 1), (w, H - 1), (d, 100 - H + 1), (0, 100 - H + 1)])])
    return g, w

def u():
    g = rbox(0, 0, B, 100, RO, ['bl']).difference(rbox(W, -1, W + C, 100 - W, RI, ['bl', 'br']))
    return g, B

def m():
    x2 = W + C
    a1 = rbox(0, 0, B, 100, RO, ['tr']).difference(rbox(W, W, W + C, 101, RI, ['tl', 'tr']))
    a2 = rbox(x2, 0, x2 + B, 100, RO, ['tl', 'tr']).difference(rbox(x2 + W, W, x2 + W + C, 101, RI, ['tl', 'tr']))
    stem = box(x2, W + RI, x2 + W, 100)
    return unary_union([a1.difference(box(x2 + W, 0, x2 + B, 101)), a2, stem]), x2 + B

def a():
    g = rbox(0, 0, B, 100, RO, ['tl', 'bl']).difference(rbox(W, W, W + C, 100 - W, RI, ['tl', 'bl']))
    return g, B

def soften(g):
    return g.buffer(-SOFT, 64).buffer(SOFT, 64).buffer(INNER, 64).buffer(-INNER, 64)

LETTERS = (('z', z), ('u', u), ('m', m), ('a', a))

def word(track=TRACK, soft=True):
    x, parts, xs = 0.0, [], []
    for k, f in LETTERS:
        g, w = f(); g = soften(g) if soft else g
        parts.append(affinity.translate(g, x, 0)); xs.append((k, x, w)); x += w + track
    return unary_union(parts), x - track, xs

def stencil(g, xs):
    """Slits where a bowl meets its stem: u at the foot, m at the shoulder, a at both."""
    cuts = []
    for k, x, w in xs:
        if k == 'u': cuts.append(box(x + W + C - 1, 100 - W - 4, x + W + C + 3, 101))
        if k == 'm': cuts.append(box(x + W - 1, -1, x + W + 3, W + 4))
        if k == 'a': cuts += [box(x + W + C - 1, -1, x + W + C + 3, W + 4), box(x + W + C - 1, 100 - W - 4, x + W + C + 3, 101)]
    return g.difference(unary_union(cuts))

def to_d(g, prec=2):
    polys = list(g.geoms) if isinstance(g, MultiPolygon) else [g]
    f = lambda v: f'{v:.{prec}f}'.rstrip('0').rstrip('.')
    return ''.join('M' + ' '.join(f'{f(x)} {f(y)}' for x, y in list(r.coords)[:-1]) + 'Z' for p in polys for r in [p.exterior] + list(p.interiors))

def stripes(g, line=3.6, gap=2.4):
    rings, o = [], 0.0
    while o < W / 2:
        rings.append(g.buffer(-o, 48).difference(g.buffer(-(o + line), 48))); o += line + gap
    return unary_union(rings)

def outline(g, gap=5.0, line=3.5):
    return unary_union([g, g.buffer(gap + line, 48).difference(g.buffer(gap, 48))])

if __name__ == '__main__':
    g, wd, xs = word()
    raw, _, _ = word(soft=False)
    out = {'w': wd, 'xs': xs, 'W': W, 'H': H, 'C': C, 'RO': RO, 'RI': RI, 'soft': SOFT, 'track': TRACK,
           'solid': to_d(g.simplify(.03)), 'raw': to_d(raw.simplify(.03)), 'stencil': to_d(stencil(g, xs).simplify(.03)),
           'stripes': to_d(stripes(g).simplify(.03)), 'outline': to_d(outline(g).simplify(.03)), 'line': to_d(g.buffer(1.6).difference(g.buffer(-1.6)).simplify(.03))}
    json.dump(out, open('zuma_wm.json', 'w'))
    print('width', round(wd, 1))

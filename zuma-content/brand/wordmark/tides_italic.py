# "tides" as a skinny italic monoline beside the heavy zuma: one stroke weight, flat cut terminals, exit strokes on t, i and d.
# Units as zuma_wm.py: x-height 100, y down (0 = top of x-height, 100 = baseline). Letters are drawn upright, then slanted.
#   python3 tides_italic.py -> tides_italic.json (one entry per option) for the options board
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zuma_wm import word as zuma_word, to_d
from shapely.geometry import LineString, box
from shapely.ops import unary_union
from shapely import affinity

AS = 38.0     # ascender above the x-height, as tides_wm.py

def arc(cx, cy, rx, ry, a0, a1, n=48):
    # angles in degrees, 90 = top (y down), counter-clockwise as seen on the page
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * k / n)), cy - ry * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]

def stroke(pts, s):
    return LineString(pts).buffer(s / 2, cap_style='flat', join_style='round', quad_segs=24)

def hook(x, s, r, out):
    # stem bottom turning right into a short flat-cut exit along the baseline
    y = 100 - s / 2
    return arc(x + r, y - r, r, r, 180, 270)[:-1] + [(x + r, y), (x + r + out, y - out * 0.35)]

def t(s):
    sx = 14 + s / 2
    stem = [(sx, -AS * 0.62)] + [(sx, 100 - s / 2 - 14)] + hook(sx, s, 14, 9)[1:]
    return unary_union([stroke(stem, s), stroke([(sx - 14, s / 2), (sx + 22, s / 2)], s * 0.85)]), sx + 32

def i(s):
    sx = s / 2 + 2
    stem = [(sx, 0), (sx, 100 - s / 2 - 12)] + hook(sx, s, 12, 8)[1:]
    dot = box(sx - s * 0.6, -AS + 4, sx + s * 0.6, -AS + 4 + s * 1.2)
    return unary_union([stroke(stem, s), dot]), sx + 22

def d(s, rx=27):
    cx = rx + s / 2; ry = 50 - s / 2
    bowl = stroke(arc(cx, 50, rx, ry, 0, 360, 96), s)
    sx = cx + rx
    stem = [(sx, -AS), (sx, 100 - s / 2 - 12)] + hook(sx, s, 12, 8)[1:]
    return unary_union([bowl, stroke(stem, s)]), sx + 22

def e(s, rx=27):
    cx = rx + s / 2; ry = 50 - s / 2; yb = 54
    pts = [(cx - rx, yb), (cx + rx - 1, yb)] + arc(cx, 50, rx, ry, -8, 318, 96)
    return stroke(pts, s), cx + rx + s / 2

def s_(s, rx=21):
    cx = rx + s / 2; ry = 25 - s / 4
    up = arc(cx, s / 2 + ry, rx, ry, 28, 270, 64)
    lo = arc(cx, 100 - s / 2 - ry, rx, ry, 90, -152, 64)
    return stroke(up + lo[1:], s), cx + rx + s / 2

def tides(s, angle, track):
    x, parts = 0.0, []
    for f in (t, i, d, e, s_):
        g, w = f(s); parts.append(affinity.translate(g, x, 0)); x += w + track
    g = unary_union(parts)
    # slant about the baseline: y down, so the top moves right
    g = affinity.skew(g, xs=-angle, origin=(0, 100))
    minx = g.bounds[0]
    return affinity.translate(g, -minx, 0), g.bounds[2] - minx

OPTIONS = {
    'A': dict(s=13.5, angle=12, track=6,  note='45% stem · 12° · beside'),
    'B': dict(s=11.0, angle=12, track=6,  note='37% stem · 12° · beside (finest)'),
    'C': dict(s=16.0, angle=10, track=5,  note='53% stem · 10° · beside'),
    'D': dict(s=13.5, angle=15, track=3,  note='45% stem · 15° · tight'),
    'E': dict(s=11.0, angle=9,  track=14, note='37% stem · 9° · open tracking'),
    'F': dict(s=13.5, angle=12, track=6,  note='45% stem · 12° · stacked under zuma', stack=True),
}

if __name__ == '__main__':
    zg, zw, _ = zuma_word()
    out = {'zuma': to_d(zg.simplify(.03)), 'zuma_w': zw, 'asc': AS, 'opts': {}}
    for k, o in OPTIONS.items():
        g, w = tides(o['s'], o['angle'], o['track'])
        out['opts'][k] = dict(o, d=to_d(g.simplify(.03)), w=w)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tides_italic.json'), 'w'))
    print({k: round(v['w']) for k, v in out['opts'].items()}, zw)

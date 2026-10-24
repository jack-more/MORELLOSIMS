# "tides" drawn on the zuma wordmark's own system: one stem weight, one bowl radius, the z's flat terminals, soft corners.
# Units as zuma_wm.py: x-height 100, y down (0 = top of x-height, 100 = baseline); ascenders rise to -AS.
#   python3 tides_wm.py -> tides.json (paths for "tides" and the "zuma tides" lockup) and preview.html
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zuma_wm import W, H, C, B, RO, RI, TRACK, rbox, soften, to_d, word as zuma_word
from shapely.geometry import box, Polygon
from shapely.ops import unary_union
from shapely import affinity
AS = 38.0          # ascender above the x-height
GAP = 10.0         # between the i and its dot

def t():
    # a straight stem, shorter than the d's, the crossbar at the top of the x-height reaching both ways
    sx = 18.0
    g = unary_union([box(sx, -AS * 0.72, sx + W, 100), box(0, 0, sx + W + 22, H)])
    return g, sx + W + 22

def i():
    return unary_union([box(0, 0, W, 100), box(0, -AS, W, -AS + (AS - GAP))]), W

def d():
    # the a's bowl (round on the left, straight stem on the right) with the stem run up to the ascender
    g = rbox(0, 0, B, 100, RO, ['tl', 'bl']).difference(rbox(W, W, W + C, 100 - W, RI, ['tl', 'bl']))
    return unary_union([g, box(B - W, -AS, B, 100)]), B

E_T, E_BAR = 23.0, 19.0
def e():
    # round on the left and top right; the eye above a thin bar; below the bar the bowl opens to the right, the tail ends flat
    y0, y1 = 44.0, 44.0 + E_BAR
    outer = rbox(0, 0, B, 100, RO, ['tl', 'tr', 'bl'])
    eye = rbox(W, E_T, B - W, y0, 8, ['tl', 'tr', 'bl', 'br'])
    mouth = rbox(W, y1, B + 1, 100 - E_T, 8, ['tl', 'bl'])
    tail = box(B - 14, y1, B + 1, 101)
    return outer.difference(eye).difference(mouth).difference(tail), B

S_T = 23.0
def s():
    # two bowls sharing the middle bar: the top one open to the right, the bottom one open to the left; both ends flat
    w = 80.0; m0, m1 = 50 - S_T / 2, 50 + S_T / 2; r = m1 / 2; ri = 7.0
    up = rbox(0, 0, w, m1, r, ['tl', 'bl']).difference(rbox(W, S_T, w + 1, m0, ri, ['tl', 'bl']))
    lo = rbox(0, m0, w, 100, r, ['tr', 'br']).difference(rbox(-1, m1, w - W, 100 - S_T, ri, ['tr', 'br']))
    # each bowl's square corner at the shared bar would poke past the other bowl's curve: trim it so the turns run clean
    up = up.difference(box(w - W, m0 - 0.5, w + 1, m1 + 1)); lo = lo.difference(box(-1, m0 - 1, W, m1 + 0.5))
    return unary_union([up, lo]), w

LETTERS = (('t', t), ('i', i), ('d', d), ('e', e), ('s', s))
def word(track=TRACK):
    x, parts = 0.0, []
    for k, f in LETTERS:
        g, w = f(); parts.append(affinity.translate(soften(g), x, 0)); x += w + track
    return unary_union(parts), x - track

if __name__ == '__main__':
    tg, tw = word(); zg, zw, _ = zuma_word()
    SPACE = 46.0
    lock = unary_union([zg, affinity.translate(tg, zw + SPACE, 0)]); lw = zw + SPACE + tw
    out = {'tides': to_d(tg.simplify(.03)), 'tides_w': tw, 'zuma': to_d(zg.simplify(.03)), 'zuma_w': zw, 'lock': to_d(lock.simplify(.03)), 'lock_w': lw, 'asc': AS}
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tides.json'), 'w'))
    vb = f'-10 {-AS - 10} {lw + 20} {100 + AS + 20}'
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'preview.html'), 'w').write(
        f'<html><body style="margin:0;background:#fff;padding:40px"><svg viewBox="{vb}" style="width:1500px"><path fill="#000" fill-rule="evenodd" d="{out["lock"]}"/>'
        f'<line x1="-10" x2="{lw+10}" y1="0" y2="0" stroke="#f00" stroke-width=".4"/><line x1="-10" x2="{lw+10}" y1="100" y2="100" stroke="#f00" stroke-width=".4"/></svg></body></html>')
    print('zuma', round(zw, 1), 'tides', round(tw, 1), 'lockup', round(lw, 1))

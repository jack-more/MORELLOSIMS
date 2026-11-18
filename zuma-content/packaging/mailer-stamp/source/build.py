# ZUMA mailer stamp: three directions for a 2 in (50.8 mm) rubber stamp, one ink (Oxblood #6E1C2A) on brown kraft bubble mailers.
# Writes the stamp art as vector SVG (ink = black, mm units, type as outlines) for the stamp maker.
#   A  round seal: crest and ZUMA wordmark in the middle, zumatides.com round the bottom, a ring round the edge
#   B  block: crest beside the ZUMA wordmark, zumatides.com under it, in a rounded frame (50.8 x 26 mm)
#   C  crest only (50.8 mm wide)
# Never says "peptides" (same rule as mailer B). Usage: python build.py OUT_DIR FONT.ttf
import math, re, sys, os
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

OUT, FONT = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
CD = re.search(r' d="([^"]+)"', open(os.path.join(HERE, 'zuma-crest.svg')).read()).group(1)      # crest, viewBox 104.26 x 100
WD = re.search(r' d="([^"]+)"', open(os.path.join(HERE, 'zuma-wordmark.svg')).read()).group(1)   # wordmark, viewBox 267.52 x 64
CW, CH, WW, WH = 104.26, 100.0, 267.52, 64.0
D = 50.8
f = TTFont(FONT); gs = f.getGlyphSet(); cmap = f.getBestCmap(); hm = f['hmtx']

def glyph(c, a, b, cc, d, e, ff):
    """one glyph as an SVG path, through the affine (a b c d e f) from font units"""
    p = SVGPathPen(gs); gs[cmap[ord(c)]].draw(TransformPen(p, (a, b, cc, d, e, ff))); return p.getCommands()

def adv(c, size): return hm[cmap[ord(c)]][0] * size / 1000

def text_line(s, size, x, y, track=0.0):
    """left-aligned text, baseline at y (mm)"""
    out = []
    for c in s:
        if c != ' ': out.append(glyph(c, size / 1000, 0, 0, -size / 1000, x, y))
        x += adv(c, size) + track * size
    return ' '.join(out)

def arc_bottom(s, size, r, cx, cy, track=0.06):
    """letters round the bottom edge, upright, reading left to right; r = baseline radius"""
    advs = [adv(c, size) + track * size for c in s]; tot = sum(advs) - track * size
    x = 0; out = []; a0 = -tot / (2 * r)
    for c, a in zip(s, advs):
        al = a0 + (x + (a - track * size) / 2) / r; x += a
        w = adv(c, size); px, py = cx + r * math.sin(al), cy + r * math.cos(al)
        co, si = math.cos(-al), math.sin(-al)   # rotate by -al so the letter stays upright
        k = size / 1000
        # font units -> scale(k,-k) -> shift left by w/2 -> rotate -> translate to (px,py)
        A, B, C_, D_ = k * co, k * si, k * si, -k * co
        E = px + co * (-w / 2); F = py + si * (-w / 2)
        out.append(glyph(c, A, B, C_, D_, E, F))
    return ' '.join(out)

def svg(w, h, body, name):
    s = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}">\n'
         f'<title>ZUMA mailer stamp {name}: {w} x {h} mm, ink shown in black, mirror nothing (the maker flips it)</title>\n{body}\n</svg>\n')
    open(os.path.join(OUT, f'zuma-stamp-{name}.svg'), 'w').write(s)

def crest(x, y, width): s = width / CW; return f'<path fill="#000" fill-rule="evenodd" transform="translate({x:.3f} {y:.3f}) scale({s:.5f})" d="{CD}"/>'
def word(x, y, width): s = width / WW; return f'<path fill="#000" fill-rule="evenodd" transform="translate({x:.3f} {y:.3f}) scale({s:.5f})" d="{WD}"/>'

# A: round seal, 50.8 mm. Outer ring 1.1 mm, a hairline-free inner ring 0.45 mm (anything under 0.3 mm fills in on rubber).
c = D / 2; cw = 18.0; chh = CH * cw / CW; ww = 25.0; wh = WH * ww / WW; gap = 2.6
top = c - (chh + gap + wh) / 2 - 2.2
A = '\n'.join([
    f'<circle cx="{c}" cy="{c}" r="{c - 0.55 - 0.05:.3f}" fill="none" stroke="#000" stroke-width="1.1"/>',
    f'<circle cx="{c}" cy="{c}" r="{c - 2.3:.3f}" fill="none" stroke="#000" stroke-width="0.45"/>',
    crest(c - cw / 2, top, cw), word(c - ww / 2, top + chh + gap, ww),
    f'<path fill="#000" d="{arc_bottom("zumatides.com", 3.9, c - 3.9, c, c)}"/>'])
svg(D, D, A, 'A-round-seal')

# B: block, 50.8 x 26 mm. Rounded frame 0.9 mm; crest left; wordmark top right; zumatides.com under it.
H = 26.0; cw = 14.5; chh = CH * cw / CW; ww = 25.6; wh = WH * ww / WW
B = '\n'.join([
    f'<rect x="0.45" y="0.45" width="{D - 0.9}" height="{H - 0.9}" rx="3.2" fill="none" stroke="#000" stroke-width="0.9"/>',
    crest(4.6, (H - chh) / 2, cw),
    word(22.4, 6.9, ww),
    f'<path fill="#000" d="{text_line("zumatides.com", 3.7, 22.6, 6.9 + wh + 5.0, 0.03)}"/>'])
svg(D, H, B, 'B-block')

# C: crest only, 50.8 mm wide.
C = crest(0, 0, D)
svg(D, round(CH * D / CW, 2), C, 'C-crest')
print('ok')

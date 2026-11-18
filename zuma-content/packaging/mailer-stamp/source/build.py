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

# A: round seal, 50.8 mm, laid out by measured clearances (not by eye):
#   one 1.0 mm ring; zumatides.com round the bottom with its baseline 2.2 mm inside the ring;
#   the crest + wordmark group sits with the SAME gap above it (to the ring) and below it (to the top of the address's lowercase).
c = D / 2; RING = 1.0; Ri = c - RING                     # inside edge of the ring
US = 4.2; XH = 0.483 * US; RB = Ri - 2.2                 # address size, x-height, baseline radius
u_top = c + RB - XH                                      # top of the address's lowercase, at the bottom centre
cw = 22.0; chh = CH * cw / CW; ww = 28.0; wh = WH * ww / WW; gap = 3.0
hg = chh + gap + wh
TRK = 0.07
def url_top_under_word(word_bottom):
    """smallest vertical gap from the wordmark's bottom edge to any address letter under it (the arc rises at its ends)"""
    advs = [adv(ch, US) + TRK * US for ch in 'zumatides.com']; tot = sum(advs) - TRK * US; x = 0; best = 1e9
    for ch, a in zip('zumatides.com', advs):
        al = -tot / (2 * RB) + (x + (a - TRK * US) / 2) / RB; x += a; w = adv(ch, US)
        for dx in (-w / 2, w / 2):                       # the two top corners of the letter's x-height box
            for dy in (0, XH):
                # glyph box point (dx right, dy up toward the centre), turned by -al like the letter itself
                px = c + RB * math.sin(al) + math.cos(al) * dx - math.sin(al) * dy
                py = c + RB * math.cos(al) - math.sin(al) * dx - math.cos(al) * dy
                if abs(px - c) <= ww / 2 + 1.5: best = min(best, py - word_bottom)
    return best
# the gap under the wordmark falls one for one as the group moves down, so: top - RING == clearance(top)
K = url_top_under_word(hg)                               # clearance with the group's top at y = 0
top = (K + RING) / 2
print(f'A: ring inside edge {Ri:.2f} mm; gap ring->crest {top - RING:.2f} mm; tightest gap wordmark->address {url_top_under_word(top + hg):.2f} mm; '
      f'ring->address baseline {Ri - RB:.2f} mm; wordmark corner to ring {Ri - math.hypot(ww / 2, top + hg - c):.2f} mm')
A = '\n'.join([
    f'<circle cx="{c}" cy="{c}" r="{c - RING / 2:.3f}" fill="none" stroke="#000" stroke-width="{RING}"/>',
    crest(c - cw / 2, top, cw), word(c - ww / 2, top + chh + gap, ww),
    f'<path fill="#000" d="{arc_bottom("zumatides.com", US, RB, c, c, 0.07)}"/>'])
svg(D, D, A, 'A-round-seal')

# B: block, 50.8 x 26 mm. Rounded frame 0.9 mm; crest left; wordmark top right; zumatides.com under it.
# Laid out by measurement: the crest + text block is centred in the frame, so the left and right margins are equal,
# and the text block (wordmark over the address) is centred vertically, like the crest.
FR = 0.9; MG = 4.0                                     # frame weight, and the same 4 mm margin on all four sides
cw = 13.5; chh = CH * cw / CW; ww = 24.0; wh = WH * ww / WW; g = 3.5
H = round(chh + 2 * MG + 2 * FR, 2)                      # the crest is the tallest thing, so it sets the height
US_B = 3.3; TRK_B = 0.03; uw = sum(adv(ch, US_B) + TRK_B * US_B for ch in 'zumatides.com') - TRK_B * US_B
lsb = 24 / 1000 * US_B                                   # the address's first letter side bearing, so its ink lines up with the wordmark
tw = max(ww, uw - lsb); M = (D - 2 * FR - (cw + g + tw)) / 2
asc = 0.723 * US_B; g2 = 2.4; th = wh + g2 + asc; ty = (H - th) / 2
x_c = FR + M; x_t = x_c + cw + g
print(f'B: {D} x {H} mm; margin left = right {M:.2f} mm; crest top = bottom {(H - chh) / 2 - FR:.2f} mm; '
      f'text block {tw:.2f} x {th:.2f} mm, centred (top = bottom {ty - FR:.2f} mm)')
B = '\n'.join([
    f'<rect x="{FR / 2}" y="{FR / 2}" width="{D - FR}" height="{H - FR}" rx="3.2" fill="none" stroke="#000" stroke-width="{FR}"/>',
    crest(x_c, (H - chh) / 2, cw),
    word(x_t, ty, ww),
    f'<path fill="#000" d="{text_line("zumatides.com", US_B, x_t - lsb, ty + wh + g2 + asc, TRK_B)}"/>'])
svg(D, H, B, 'B-block')

# C: crest only, 50.8 mm wide.
C = crest(0, 0, D)
svg(D, round(CH * D / CW, 2), C, 'C-crest')
print('ok')

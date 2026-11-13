# Build YOJO Batch as a real font: every glyph is the halftone of a bold serif, dots sized by coverage on a fixed grid.
# Caps only (lowercase maps to caps). Output: YOJOBatch.ttf and YOJOBatch.woff2
import sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

SRC = '/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'YOJOBatch'
ROWS = 10                     # dots across the cap height
UPM = 1000; CAP = 700; CELL = CAP / ROWS
GAIN = 0.5                   # dot radius at full coverage, as a fraction of the cell
SIDE = 0.6                    # side bearing in cells
CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,'’-–!?&/:·()+%#@*\""
REN = 1200                    # render size for sampling
f = ImageFont.truetype(SRC, REN)
cap_px = f.getbbox('H')[3] - f.getbbox('H')[1]
scale = ROWS / cap_px          # rows per pixel
asc, desc = f.getmetrics()

def coverage(ch):
    # draw the glyph on a canvas whose baseline sits on a row boundary, sample cells of cap/ROWS px
    cell_px = cap_px / ROWS
    W = int(f.getlength(ch) + REN * 0.2); H = int(cap_px * 1.6)
    base = int(cap_px * 1.25)
    im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im); d.text((int(REN * 0.1), base), ch, font=f, fill=255, anchor='ls')
    bb = im.getbbox()
    if not bb: return None, 0, 0
    x0 = bb[0]; x1 = bb[2]
    cols = max(1, int(math.ceil((x1 - x0) / cell_px)))
    # rows from 3 below the baseline to 2 above the cap height
    top = base - cap_px - 2 * cell_px; nrows = ROWS + 5
    crop = im.crop((x0, int(top), int(x0 + cols * cell_px), int(top + nrows * cell_px)))
    a = np.asarray(crop.resize((cols, nrows), Image.BOX), np.float32) / 255
    return a, cols, nrows

def circle(pen, cx, cy, r, n=8):
    # a circle from n quadratic segments: on-curve points implied between off-curve control points
    k = 1 / math.cos(math.pi / n)
    pts = [(round(cx + r * k * math.cos(2 * math.pi * (i + 0.5) / n)), round(cy + r * k * math.sin(2 * math.pi * (i + 0.5) / n))) for i in range(n)]
    pen.qCurveTo(*pts, None); pen.closePath()

glyphs = {'.notdef': None, 'space': None}; widths = {'.notdef': (500, 0), 'space': (int(CELL * 3.2), 0)}; cmap = {32: 'space'}
order = ['.notdef', 'space']
for ch in CHARS:
    name = 'uni%04X' % ord(ch)
    a, cols, nrows = coverage(ch)
    pen = TTGlyphPen(None)
    if a is not None:
        for r in range(nrows):
            for c in range(cols):
                v = float(a[r, c])
                if v < 0.1: continue
                rr = CELL * GAIN * math.sqrt(v)
                cx = (SIDE + c + 0.5) * CELL
                cy = (ROWS + 2 - r - 0.5) * CELL - 0          # row 0 is 2 cells above the cap height
                circle(pen, cx, cy - 0, rr)
    g = pen.glyph(); glyphs[name] = g
    widths[name] = (int((cols + 2 * SIDE) * CELL), int(SIDE * CELL)); cmap[ord(ch)] = name; order.append(name)
    if ch.isalpha(): cmap[ord(ch.lower())] = name
for n in ('.notdef', 'space'): glyphs[n] = TTGlyphPen(None).glyph()

fb = FontBuilder(UPM, isTTF=True)
fb.setupGlyphOrder(order); fb.setupCharacterMap(cmap)
fb.setupGlyf({n: glyphs[n] for n in order}); fb.setupHorizontalMetrics({n: widths[n] for n in order})
fb.setupHorizontalHeader(ascent=900, descent=-250)
fb.setupNameTable({'familyName': 'YOJO Batch', 'styleName': 'Regular', 'uniqueFontIdentifier': 'YOJO Batch Regular', 'fullName': 'YOJO Batch',
                   'psName': 'YOJOBatch-Regular', 'version': 'Version 1.0',
                   'licenseDescription': 'Derived from GNU FreeSerif Bold. GPLv3 with the font exception.'})
fb.setupOS2(sTypoAscender=900, sTypoDescender=-250, usWinAscent=950, usWinDescent=300, sCapHeight=CAP, sxHeight=CAP)
fb.setupPost(); fb.setupDummyDSIG() if hasattr(fb, 'setupDummyDSIG') else None
fb.save(OUT + '.ttf')
from fontTools.ttLib import TTFont
t = TTFont(OUT + '.ttf'); t.flavor = 'woff2'; t.save(OUT + '.woff2')
print('glyphs', len(order), 'ok')

# Bold deboss maps for the capsule, a stamp or two facing the camera instead of an all-over scatter.
#   python3 cyc/capsule/pattern2.py MODE  -> pattern-MODE.html (screenshot + blur makes pattern-MODE.png)
#   one: a single big crest on the top half; two: a big crest on each half; imprint: crest on top, the wordmark along the bottom half, like a printed pill
import math, os, sys
CAP = os.path.dirname(os.path.abspath(__file__)); SP = os.path.dirname(os.path.dirname(CAP))
MODE = sys.argv[1]
R, L, T0 = 11.5, 64.0, 31.0; D0 = R - R * math.cos(math.radians(T0))
CIRC = 2 * math.pi * R; PX = 2400 / CIRC; W, H = 2400, round(L * PX)
SEAM = L / 2 - D0 / 2; TOP = ((L - R - D0) + SEAM) / 2; BOT = ((R - D0) + SEAM) / 2   # centres of the two body halves, mm from the seat
U = 0.5                                             # the side that faces the camera
defs = open(os.path.join(SP, 'site3/src/logo-slot.svg')).read()
def crest(zmm, w):
    s = w * PX; return '<svg style="position:absolute;left:%dpx;top:%dpx;width:%dpx;height:%dpx" viewBox="0 0 104.26 100"><use href="#zuma-mark" fill="#000"/></svg>' % (U * W - s / 2, H - zmm * PX - s / 2, s, s)
def word(zmm, length):
    # the wordmark alone (the logo's flower cropped off), turned to read up the capsule
    lw = length * PX; lh = lw * 100 / 268
    return '<svg style="position:absolute;left:%dpx;top:%dpx;width:%dpx;height:%dpx;transform:rotate(-90deg)" viewBox="120 0 268 100"><use href="#zuma-logo" width="388.1" height="100" fill="#000"/></svg>' % (U * W - lw / 2, H - zmm * PX - lh / 2, lw, lh)
def words(u):
    # ZUMA up the bottom half, TIDES up the top half, reading from the seat up; the seam falls in the gap between them
    out = ''
    for txt, zc in (('ZUMA', BOT), ('TIDES', TOP)):
        for dx in (-W, 0, W):
            out += '<div style="position:absolute;left:%dpx;top:%dpx;width:%dpx;height:%dpx;display:flex;align-items:center;justify-content:center;transform:rotate(-90deg);font:800 %dpx/1 Outfit,sans-serif;letter-spacing:.14em;color:#000">%s</div>' % (u * W + dx - 9 * PX, H - zc * PX - 2.6 * PX, 18 * PX, 5.2 * PX, 5.0 * PX, txt)
    return out
parts = {'side': crest(TOP, 13.5) + words(0.0), 'one': crest(TOP, 13.5), 'two': crest(TOP, 13.0) + crest(BOT, 13.0), 'imprint': crest(TOP, 12.5) + word(BOT, 17.5)}[MODE]
open(os.path.join(CAP, 'pattern-%s.html' % MODE), 'w').write('<html><head><link href="https://fonts.googleapis.com/css2?family=Outfit:wght@800&display=swap" rel="stylesheet"></head><body style="margin:0;background:#fff">%s<div style="position:relative;width:%dpx;height:%dpx;overflow:hidden">%s</div></body></html>' % (defs, W, H, parts))
print(MODE, W, H, 'top', round(TOP, 1), 'bot', round(BOT, 1))

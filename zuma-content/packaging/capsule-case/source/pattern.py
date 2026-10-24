# The deboss map for the capsule: small ZUMA crests in staggered rows on the straight body, clear of the seam and the domes.
#   python3 cyc/capsule/pattern.py   -> pattern.html, pattern-raw.png, pattern.png (blurred height map), stamps.json (positions for the spec)
# The map wraps once around the capsule (u) and runs its length (v = z / L). 2400 px = 72.26 mm of circumference, so 33.2 px/mm both ways.
import json, math, os, random, subprocess
CAP = os.path.dirname(os.path.abspath(__file__)); SP = os.path.dirname(os.path.dirname(CAP))
R, L, T0 = 11.5, 64.0, 31.0                       # mm
D0 = R - R * math.cos(math.radians(T0))
CIRC = 2 * math.pi * R; PX = 2400 / CIRC; W, H = 2400, round(L * PX)
CREST = 7.5                                       # crest width, mm
ROWS_MM = [16.0, 25.5, 38.0, 47.0]                 # crest centres up the capsule (z, mm from the bottom of the seat); the seam is at ~31.3
PER_ROW = 5
random.seed(11)
defs = open(os.path.join(SP, 'site3/src/logo-slot.svg')).read()
S = CREST * PX; stamps = []; out = []
for r, zmm in enumerate(ROWS_MM):
    for k in range(PER_ROW):
        u = (k + (0.5 if r % 2 else 0)) / PER_ROW; rot = random.choice([-1, 1]) * random.uniform(6, 24)
        stamps.append({'row': r, 'z_mm': zmm, 'arc_mm': round(u * CIRC, 2), 'deg_around': round(u * 360, 1), 'rot': round(rot, 1)})
        cx, cy = u * W, H - zmm * PX
        for dx in (-W, 0, W):
            out.append('<svg style="position:absolute;left:%dpx;top:%dpx;width:%dpx;height:%dpx;transform:rotate(%.1fdeg)" viewBox="0 0 104.26 100"><use href="#zuma-icon" fill="#000"/></svg>' % (cx + dx - S / 2, cy - S / 2, S, S, rot))
html = '<html><body style="margin:0;background:#fff">%s<div style="position:relative;width:%dpx;height:%dpx;overflow:hidden">%s</div></body></html>' % (defs, W, H, ''.join(out))
open(os.path.join(CAP, 'pattern.html'), 'w').write(html)
json.dump({'R': R, 'L': L, 'seat_d': round(2 * R * math.sin(math.radians(T0)), 1), 'seam_z': round(L / 2 - D0 / 2, 1), 'crest_w': CREST, 'stamps': stamps}, open(os.path.join(CAP, 'stamps.json'), 'w'), indent=1)
print(W, H, 'crest px', round(S), 'seam z', L / 2 - D0 / 2, 'body', R - D0, L - R - D0)

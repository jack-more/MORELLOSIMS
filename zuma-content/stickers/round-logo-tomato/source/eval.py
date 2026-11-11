# Evaluate a round logo sticker layout: clearances (mm) and logo/field contrast (WCAG ratio).
# usage: CREST_W=.. WORD_W=.. GAP=.. LIFT=.. python eval.py
import os, subprocess, sys, tempfile
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); PY = sys.executable
SP = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'
DPI = 600; PG = 53.8; R = 25.4; px = DPI / 25.4
td = tempfile.mkdtemp()

def raster(name, field, art, lb=None, env=None):
    args = [PY, f'{HERE}/build.py', td, name, field, art] + ([lb] if lb else [])
    subprocess.run(args, check=True, capture_output=True, env={**os.environ, **(env or {})})
    subprocess.run(['pdftoppm', '-r', str(DPI), '-png', f'{td}/zuma-round-logo-{name}-2in.pdf', f'{td}/{name}'], check=True)
    return np.asarray(Image.open(f'{td}/{name}-1.png').convert('RGB')).astype(float)

# geometry: art in white on black, no image field
m = raster('mask', '#000000', '#FFFFFF')[..., 1] > 128   # green channel: white art, not the magenta cut line
h, w = m.shape; cy, cx = h / 2, w / 2
yy, xx = np.mgrid[0:h, 0:w]; r = np.hypot(yy - cy, xx - cx) / px
inside = r < R
art = m & inside
edge = R - r[art].max()                                   # closest art to the cut line
# split logo (crest + wordmark) from the address (the bottom arc): the address sits in the outer band below centre
logo = (raster('logo', '#000000', '#FFFFFF', env={'NOURL': '1'})[..., 1] > 128) & inside
addr = art & ~logo
ly, lx = np.nonzero(logo); ay, ax = np.nonzero(addr)
logo_w = (lx.max() - lx.min()) / px; logo_h = (ly.max() - ly.min()) / px
gap_addr = (ay.min() - ly.max()) / px
logo_area = logo.sum() / inside.sum() * 100

def lum(c):
    c = c / 255; c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4); return c @ [0.2126, 0.7152, 0.0722]
print(f"logo block: {logo_w:.1f} x {logo_h:.1f} mm, {logo_area:.1f}% of the sticker face")
ledge = R - r[logo].max()
print(f"closest art to the cut line: {edge:.2f} mm (logo itself: {ledge:.2f} mm)   logo to address: {gap_addr:.2f} mm")
VARS = [('green-cream', '#0E9A5B', '#FBFAF6', 'green'), ('oxblood-lightblue', '#6E1C2A', '#BFE8FB', 'oxblood'),
        ('oxblood-white', '#6E1C2A', '#FFFFFF', 'oxblood'), ('blue-white', '#1E74A8', '#FFFFFF', 'blue')]
ring = np.zeros_like(logo)
from PIL import ImageFilter
dil = np.asarray(Image.fromarray((logo * 255).astype('uint8')).filter(ImageFilter.MaxFilter(41))) > 0
near = np.asarray(Image.fromarray((logo * 255).astype('uint8')).filter(ImageFilter.MaxFilter(9))) > 0
ring = dil & ~near & inside                               # the field around the logo, clear of its soft edge                               # the field right around the logo
for name, f, a, t in VARS:
    img = raster('ev-' + name, f, a, f'{SP}/rl/t-{t}.png')
    La = lum(np.array([int(a[i:i + 2], 16) for i in (1, 3, 5)], float))
    Lf = lum(img[ring])
    cr = (max(La, 0) + 0.05) / (Lf + 0.05)
    print(f"{name:18s} contrast logo/field: worst {cr.min():.1f}  5th pct {np.percentile(cr, 5):.1f}  median {np.median(cr):.1f}")

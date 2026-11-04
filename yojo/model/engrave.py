# Western bright-cut scroll engraving for the side of the head: our own scroll, drawn procedurally.
# white = raised bright metal, black = matted background (oxidises), mid lines = fine shading cuts
import math, numpy as np
from PIL import Image, ImageDraw, ImageFilter
rng = np.random.default_rng(3)
PX, SS = 40, 3; Wmm, Hmm = 113.1, 7.8; W, H = int(Wmm * PX), int(Hmm * PX); S = PX * SS
im = Image.new('L', (W * SS, H * SS), 0); d = ImageDraw.Draw(im)
def P(x, y): return (x * S, y * S)
def stroke(pts, w0, w1, fill=255):
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        w = (w0 + (w1 - w0) * i / max(1, n - 1)) * S / 2
        for off in (0, -Wmm, Wmm):
            X, Y = (x + off) * S, y * S
            if -w < X < W * SS + w: d.ellipse([X - w, Y - w, X + w, Y + w], fill=fill)
def leaf(base, ang, L, Wd, curl):
    # tapered blade along a curved centreline, with a cut vein
    t = np.linspace(0, 1, 40); a = ang + curl * t
    cx = base[0] + np.cumsum(np.cos(a)) * L / 40; cy = base[1] + np.cumsum(np.sin(a)) * L / 40
    wdt = Wd * np.sin(np.pi * t ** 0.8)
    nx, ny = -np.sin(a), np.cos(a)
    poly = [P(x + w * u, y + w * v) for x, y, w, u, v in zip(cx, cy, wdt, nx, ny)] + \
           [P(x - w * u, y - w * v) for x, y, w, u, v in zip(cx[::-1], cy[::-1], wdt[::-1], nx[::-1], ny[::-1])]
    for off in (0, -Wmm, Wmm): d.polygon([(px_ + off * S, py_) for px_, py_ in poly], fill=255)
    vein = list(zip(cx[3:-6], cy[3:-6])); stroke(vein, 0.09, 0.05, fill=95)
    # shading cuts across one side of the blade, the bright-cut look
    for k in range(6, 34, 5):
        x, y, w, u, v = cx[k], cy[k], wdt[k], nx[k], ny[k]
        stroke([(x + 0.1 * w * u, y + 0.1 * w * v), (x + 0.85 * w * u, y + 0.85 * w * v)], 0.06, 0.04, fill=110)
def spiral(start, a0, R, turns, sgn, w0):
    k = 0.42; t = np.linspace(0, 2 * np.pi * turns, 200); r = R * np.exp(-k * t)
    c = (start[0] - R * math.cos(a0), start[1] - R * math.sin(a0))
    pts = [(c[0] + rr * math.cos(a0 + sgn * tt), c[1] + rr * math.sin(a0 + sgn * tt)) for rr, tt in zip(r, t)]
    stroke(pts, w0, 0.12)
    return pts, c
B = 0.95                      # border height (mm)
yc = Hmm / 2; A = float(__import__('os').environ.get('SA', '1.15'))
N = int(__import__('os').environ.get('SN', '9')); U = Wmm / N          # one full wave per unit: crest up, crest down
SLOT_X = 0.75 * Wmm; SLOT_Y = (9 - 0.6) - 9 * 0.42
xs = np.linspace(0, Wmm, 4000); ys = yc - A * np.sin(2 * np.pi * xs / U)
stroke(list(zip(xs, ys)), 0.36, 0.36)
R = float(__import__('os').environ.get('SR', '1.45')); TURNS = 1.5; k = math.log(R / 0.22) / (2 * math.pi * TURNS)
for i in range(N):
    for half, s_ in ((0.25, 1), (0.75, -1)):          # s_=1: crest at top (small y), scroll hangs below
        xc = (i + half) * U; ysx = yc - s_ * A
        cen = (xc, ysx + s_ * R); th0 = -s_ * math.pi / 2
        t = np.linspace(0, 2 * math.pi * TURNS, 260); r = R * np.exp(-k * t)
        pts = [(cen[0] + rr * math.cos(th0 + s_ * tt), cen[1] + rr * math.sin(th0 + s_ * tt)) for rr, tt in zip(r, t)]
        stroke(pts, 0.36, 0.14)
        def tang(j): return math.atan2(pts[j + 1][1] - pts[j - 1][1], pts[j + 1][0] - pts[j - 1][0])
        def outward(j): return math.atan2(pts[j][1] - cen[1], pts[j][0] - cen[0])
        # leaves bursting off the outside of the scroll, sweeping with it
        for j, L_, W_ in ((30, 1.7, 0.55), (80, 1.35, 0.45), (130, 0.95, 0.34)):
            leaf(pts[j], (tang(j) + outward(j)) / 2 if abs(tang(j) - outward(j)) < math.pi else outward(j), L_, W_, s_ * 0.9)
        # a small leaf curling into the eye of the scroll
        leaf(pts[205], tang(205), 0.6, 0.22, s_ * 1.4)
        # stem leaves at the inflection, one each side
        xi = xc + U / 4 - 0.15; yi = yc
        leaf((xi, yi), -s_ * 2.0, 1.5, 0.48, s_ * 0.9); leaf((xi, yi), math.pi - s_ * 2.0, 1.2, 0.4, -s_ * 0.9)
a = np.asarray(im.resize((W, H), Image.LANCZOS), np.float32) / 255
y = (np.arange(H)[:, None] + 0.5) / PX; x = (np.arange(W)[None, :] + 0.5) / PX
# matted background: low, punched texture
mat = 0.08 + 0.12 * rng.random((H, W)).astype(np.float32)
mat = np.asarray(Image.fromarray((mat * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7)), np.float32) / 255
a = np.maximum(a, mat * (a < 0.5))
# bright-cut wheat borders: raised rails with alternating angled cuts
def wheat(y0, y1, flip):
    inside = (y >= y0) & (y < y1); v = (y - y0) / (y1 - y0)
    ph = ((x + (v - 0.5) * 0.5 * flip) / 0.42) % 1.0
    cut = np.abs(ph - 0.5) < 0.16
    return inside, np.where(cut, 0.45, 1.0)
for y0, y1, f in ((0.0, B, 1), (Hmm - B, Hmm, -1)):
    ins, val = wheat(y0, y1, f); a = np.where(ins, val, a)
a = np.where((np.abs(y - B) < 0.08) | (np.abs(y - (Hmm - B)) < 0.08), 0.0, a)   # fine cut line under each border
# plain oval plaque for the spout, with a fine cut outline
e = np.hypot((x - SLOT_X) / 2.6, (y - SLOT_Y) / 1.35)
a = np.where(e < 1.0, 1.0, a); a = np.where((e >= 1.0) & (e < 1.09), 0.0, a)
Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.5)).save('am-band-scroll.png')
print('ok')

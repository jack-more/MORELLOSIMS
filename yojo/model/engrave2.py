# Full-coverage western bright-cut engraving for the head band (original pattern).
# Big C-scrolls and acanthus leaves fill the band; every leaf is domed and covered in parallel shading cuts;
# the ground shows only in small punched gaps; faceted feather-cut borders top and bottom.
import math, os, numpy as np
from PIL import Image, ImageDraw, ImageFilter
rng = np.random.default_rng(5)
PX, SS = 40, 2; Wmm, Hmm = 113.1, 7.8; W, H = int(Wmm * PX), int(Hmm * PX); S = PX * SS
B = float(os.environ.get('SB', '1.7')); yc = Hmm / 2
N = int(os.environ.get('SN', '6')); U = Wmm / N
SLOT_X = 0.75 * Wmm; SLOT_Y = (9 - 0.6) - 9 * 0.42
shape = Image.new('L', (W * SS, H * SS), 0); ds = ImageDraw.Draw(shape)      # raised metal
cuts = Image.new('L', (W * SS, H * SS), 0); dc = ImageDraw.Draw(cuts)       # engraved lines inside raised metal
def P(x, y): return (x * S, y * S)
def dot(d, x, y, w, fill=255):
    for off in (0, -Wmm, Wmm):
        X, Y = (x + off) * S, y * S
        if -w < X < W * SS + w: d.ellipse([X - w, Y - w, X + w, Y + w], fill=fill)
def stroke(d, pts, w0, w1, fill=255):
    n = len(pts)
    if n == 2:
        for off in (0, -Wmm, Wmm): d.line([((pts[0][0] + off) * S, pts[0][1] * S), ((pts[1][0] + off) * S, pts[1][1] * S)], fill=fill, width=max(1, int(w0 * S)))
        return
    for i, (x, y) in enumerate(pts): dot(d, x, y, (w0 + (w1 - w0) * i / max(1, n - 1)) * S / 2, fill)
def poly(d, pts, fill=255):
    for off in (0, -Wmm, Wmm): d.polygon([((x + off) * S, y * S) for x, y in pts], fill=fill)
def leaf(base, ang, L, Wd, curl, lobes=3):
    # acanthus blade: lobed outline, domed later; shading cuts across the whole blade, central vein
    t = np.linspace(0, 1, 80); a = ang + curl * t
    cx = base[0] + np.cumsum(np.cos(a)) * L / 80; cy = base[1] + np.cumsum(np.sin(a)) * L / 80
    lob = 1 + 0.22 * np.abs(np.sin(np.pi * lobes * t))
    wdt = Wd * np.sin(np.pi * np.clip(t, 0, 1) ** 0.7) * lob
    nx, ny = -np.sin(a), np.cos(a)
    poly(ds, list(zip(cx + wdt * nx, cy + wdt * ny)) + list(zip((cx - wdt * nx)[::-1], (cy - wdt * ny)[::-1])))
    stroke(dc, list(zip(cx[4:-10], cy[4:-10])), 0.1, 0.05)
    for k in range(5, 76, 2):                       # parallel shading cuts, angled back toward the vein
        x, y, w = cx[k], cy[k], wdt[k] * 0.92
        for sd in (1, -1):
            if sd == -1 and k % 2: continue
            ex, ey = x + sd * w * nx[k] - 0.25 * w * math.cos(a[k]), y + sd * w * ny[k] - 0.25 * w * math.sin(a[k])
            stroke(dc, [(x + sd * 0.12 * nx[k], y + sd * 0.12 * ny[k]), (ex, ey)], 0.05, 0.035)
A = float(os.environ.get('SA', '0.55')); R = float(os.environ.get('SR', '2.25'))
xs = np.linspace(0, Wmm, 5000); ys = yc - A * np.sin(2 * np.pi * xs / U)
stroke(ds, list(zip(xs, ys)), 0.62, 0.62)
TURNS = 1.45; k = math.log(R / 0.3) / (2 * math.pi * TURNS)
for i in range(N):
    for half, s_ in ((0.25, 1), (0.75, -1)):
        xc = (i + half) * U; ysx = yc - s_ * A
        cen = (xc + 0.35 * s_, ysx + s_ * R * 0.92); th0 = math.atan2(ysx - cen[1], xc - cen[0])
        t = np.linspace(0, 2 * math.pi * TURNS, 320); r = R * np.exp(-k * t)
        pts = [(cen[0] + rr * math.cos(th0 + s_ * tt), cen[1] + rr * math.sin(th0 + s_ * tt)) for rr, tt in zip(r, t)]
        stroke(ds, pts, 0.62, 0.22)
        # engraved line riding the inside of the scroll
        inner = [(cen[0] + (rr - 0.12) * math.cos(th0 + s_ * tt), cen[1] + (rr - 0.12) * math.sin(th0 + s_ * tt)) for rr, tt in zip(r, t)][10:280]
        stroke(dc, inner, 0.07, 0.05)
        def tang(j): return math.atan2(pts[j + 1][1] - pts[j - 1][1], pts[j + 1][0] - pts[j - 1][0])
        # big leaves bursting off the outside of each scroll, overlapping
        for j, L_, W_ in ((25, 2.6, 0.95), (70, 2.2, 0.82), (120, 1.7, 0.66), (175, 1.1, 0.45)):
            leaf(pts[j], tang(j) - s_ * 0.55, L_, W_, s_ * 0.9)
        leaf(pts[250], tang(250), 0.7, 0.3, s_ * 1.5, 1)
        # stem leaves at the inflection, filling the opposite side
        xi = xc + U / 4; leaf((xi, yc), -s_ * 1.9, 2.4, 0.85, s_ * 0.8); leaf((xi - 0.6, yc), math.pi + s_ * 0.5, 1.8, 0.65, -s_ * 0.8)
def gaps():
    sm = np.asarray(shape.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3)), np.float32) / 255
    return sm
for it in range(6):
    sm = gaps(); hh, ww = sm.shape
    cand = np.argwhere(sm < 0.08)
    if len(cand) == 0: break
    rng.shuffle(cand)
    for (py_, px_) in cand[:60]:
        xm, ym = (px_ + 0.5) * 4 / PX, (py_ + 0.5) * 4 / PX
        if ym < B + 0.4 or ym > Hmm - B - 0.4: continue
        if sm[py_, px_] >= 0.08: continue
        sy_ = yc - A * math.sin(2 * math.pi * xm / U); slope = -A * 2 * math.pi / U * math.cos(2 * math.pi * xm / U)
        flow = math.atan(slope); side = 1 if ym > sy_ else -1
        leaf((xm - 0.5 * math.cos(flow), ym - 0.3 * side), flow + side * 0.55, rng.uniform(1.1, 1.5), rng.uniform(0.4, 0.52), -side * 0.7, 2)
        sm[max(0, py_ - 4):py_ + 5, max(0, px_ - 4):px_ + 5] = 1
shape = np.asarray(shape.resize((W, H), Image.LANCZOS), np.float32) / 255
cuts = np.asarray(cuts.resize((W, H), Image.LANCZOS), np.float32) / 255
# dome every raised shape: higher toward its middle
dome = np.asarray(Image.fromarray((shape * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(9)), np.float32) / 255
relief = shape * (0.55 + 0.45 * np.clip(dome * 1.4, 0, 1))
relief = relief - 0.4 * cuts * shape
y = (np.arange(H)[:, None] + 0.5) / PX; x = (np.arange(W)[None, :] + 0.5) / PX
gn = rng.random((H, W)).astype(np.float32)
gn = np.asarray(Image.fromarray((gn * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6)), np.float32) / 255
ground = float(os.environ.get('GROUND', '0.7')) + 0.06 * (gn - 0.5)          # matte metal, finely punched
a = np.where(shape > 0.5, np.maximum(relief, ground + 0.05), ground)
sb = np.asarray(Image.fromarray((shape * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.6)), np.float32) / 255
edge = (sb > 0.2) & (sb < 0.8)
a = np.where(edge, 0.12, a)                                                  # engraved outline round every shape
# feather-cut borders: faceted chevrons whose sloped faces catch light
def feather(y0, y1, flip):
    ins = (y >= y0) & (y < y1); v = (y - y0) / (y1 - y0)
    p = 0.75; u = (x / p + flip * v * 1.6) % 1.0
    strand = np.sqrt(np.clip(1 - (2 * u - 1) ** 2, 0, 1)); cord = np.sqrt(np.clip(1 - (2 * v - 1) ** 2, 0, 1))
    h = 0.35 + 0.65 * strand * (0.55 + 0.45 * cord)
    return ins, h
for y0, y1, f in ((0.0, B, 1), (Hmm - B, Hmm, -1)):
    ins, h = feather(y0, y1, f); a = np.where(ins, h, a)
a = np.where((np.abs(y - B) < 0.07) | (np.abs(y - (Hmm - B)) < 0.07), 0.0, a)
# spout cartouche: mirror plaque, cut line, twisted-rope oval frame, cut line
PA, PB = 2.2, 0.95
dx, dy = (x - SLOT_X), (y - SLOT_Y)
e = np.hypot(dx / PA, dy / PB); phi = np.arctan2(dy / PB, dx / PA)
RW = 0.55                                       # rope frame width, in units of the plaque ellipse
in_rope = (e >= 1.08) & (e < 1.08 + RW)
w = np.clip((e - 1.08) / RW, 0, 1)
u = (phi / (2 * np.pi) * 34 + w * 1.4) % 1.0
rope = 0.35 + 0.65 * np.sqrt(np.clip(1 - (2 * u - 1) ** 2, 0, 1)) * (0.55 + 0.45 * np.sqrt(np.clip(1 - (2 * w - 1) ** 2, 0, 1)))
a = np.where(e < 1.0, 1.0, a)
a = np.where((e >= 1.0) & (e < 1.08), 0.05, a)
a = np.where(in_rope, rope, a)
a = np.where((e >= 1.08 + RW) & (e < 1.16 + RW), 0.05, a)
Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.45)).save('am-band-scroll2.png')
print('ok')

import math, numpy as np
from PIL import Image, ImageFilter
rng = np.random.default_rng(11)
W, H, PX = int(113.1 * 40), int(7.8 * 40), 40
x = np.arange(W)[None, :] / PX; y = np.arange(H)[:, None] / PX
def save(a, n, blur=0.7): Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur)).save(n)
Y = np.asarray(Image.open('head-mask.png').convert('L'), np.float32) / 255
N = 1600; yy, xx = np.mgrid[0:N, 0:N]; X = (xx - 800) / 40; Yc = (800 - yy) / 40; R = np.hypot(X, Yc)
SLOT_Y = (9 - 0.6) - 9 * 0.42          # slot height, measured down from the top of the band (mm)
def dents(w_mm, h_mm, n, r0, r1, wrap):
    # hammered facets on a w x h mm patch, computed at 10 px/mm
    gx, gy = np.meshgrid(np.arange(int(w_mm * 10)) / 10, np.arange(int(h_mm * 10)) / 10)
    pts = np.c_[rng.uniform(0, w_mm, n), rng.uniform(0, h_mm, n)]; rad = rng.uniform(r0, r1, n); best = np.full(gx.shape, 9.0)
    for (px_, py_), r_ in zip(pts, rad):
        dx = np.abs(gx - px_)
        if wrap: dx = np.minimum(dx, w_mm - dx)
        best = np.minimum(best, np.hypot(dx, gy - py_) / r_)
    return np.clip(best ** 2, 0, 1)
def up(a, shape): return np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((shape[1], shape[0]), Image.BICUBIC), np.float32) / 255
# E rivets: polished band, two cut lines, 8 domed rivets clear of the slot
a = np.full((H, W), 0.62); a[(np.abs(y - 0.9) < 0.15).repeat(W, 1)] = 0; a[(np.abs(y - 6.9) < 0.15).repeat(W, 1)] = 0
a[(y < 0.75).repeat(W, 1)] = 1; a[(y > 7.05).repeat(W, 1)] = 1
for k in range(8):
    cx = (k / 8 + 1 / 16) * 113.1
    for off in (0, -113.1, 113.1):
        d = np.hypot(x - cx - off, y - 3.9)
        a = np.where(d < 1.55, 0.62 + 0.38 * np.sqrt(np.clip(1 - (d / 1.55) ** 2, 0, 1)), a)
        a = np.where((d >= 1.55) & (d < 1.8), 0.25, a)
save(a, 'am-band-rivet.png')
# F turned: four V grooves, the slot sits in the third
a = np.ones((H, W))
for gy_ in (SLOT_Y - 2 * 1.56, SLOT_Y - 1.56, SLOT_Y, SLOT_Y + 1.56):
    a = np.minimum(a, np.clip(np.abs(y - gy_) / 0.32, 0, 1) * np.ones((1, W)))
save(a, 'am-band-turned.png', 0.5)
tf = float(__import__('os').environ.get('TF0', '0.12')) + float(__import__('os').environ.get('TF1', '0.5')) * np.abs(np.sin(np.pi * R / 0.36))
save(np.maximum(np.where(R < 16.6, tf, 1.0), Y), 'am-top-turned.png', 0.5)
# G wriggle: zigzag of tight wriggle cuts between rails; cross-hatched field behind the Y on top
a = np.full((H, W), 1.0)
a[((np.abs(y - 0.8) < 0.13) | (np.abs(y - 7.0) < 0.13)).repeat(W, 1)] = 0
P, A = 113.1 / 18, 2.1
xs = np.linspace(0, 113.1, 40000); ph = (xs / P) % 1; zz = 3.9 + A * (np.abs(2 * ph - 1) * 2 - 1)
wr = 0.28 * np.sign(np.sin(2 * np.pi * xs / 0.55))
line = Image.new('L', (W, H), 255); from PIL import ImageDraw; d = ImageDraw.Draw(line)
pts = [(float(u * PX), float((v + w) * PX)) for u, v, w in zip(xs, zz, wr)]; d.line(pts, fill=0, width=10)
a = np.minimum(a, np.asarray(line, np.float32) / 255)
save(a, 'am-band-wriggle.png', 0.6)
h1 = np.abs(((X + Yc) / 0.5) % 1 - 0.5) < 0.12; h2 = np.abs(((X - Yc) / 0.5) % 1 - 0.5) < 0.12
hatch = np.where(h1 | h2, 0.15, 0.6)
ring = (np.abs(R - 15.6) < 0.22)
top = np.where(R < 15.2, hatch, np.where(ring, 0.0, 1.0)); save(np.maximum(top, Y), 'am-top-hatch.png', 0.6)
# H forged: hammered band and top
hb = dents(113.1, 7.8, 900, 0.9, 1.4, True); save(0.35 + 0.65 * up(hb, (H, W)), 'am-band-forged.png', 0.8)
ht = dents(40, 40, 1500, 0.9, 1.4, False); ht = up(ht, (N, N))
save(np.maximum(np.where(R < 16.6, 0.15 + 0.35 * ht, 1.0), Y), 'am-top-forged.png', 0.8)
print('ok')

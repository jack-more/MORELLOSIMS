# Americana silversmith vocabulary on YOJO's own Y: twisted rope, coin reeding, hand stamps, hammered fields, sunburst.
import math, numpy as np
from PIL import Image, ImageFilter
rng = np.random.default_rng(7)
Y = Image.open('head-mask.png').convert('L'); bb = Y.getbbox(); glyph = Y.crop(bb)
# ---------- side bands: 113.1 mm around x 7.8 mm tall, 40 px/mm ----------
W, H, PX = int(113.1 * 40), int(7.8 * 40), 40
x = np.arange(W)[None, :] / PX; y = np.arange(H)[:, None] / PX           # mm; y = 0 at top of band
def save(a, n, blur=0.7): Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur)).save(n)
def rope(xmm, wloc, hmm, strands, circ, d):
    # one twisted cord: rounded cross-section, diagonal strands
    c = np.sqrt(np.clip(1 - (2 * wloc - 1) ** 2, 0, 1))
    ph = (xmm * strands / circ + d * wloc * hmm * strands / circ * 1.0) % 1.0
    p = np.sqrt(np.clip(1 - (2 * ph - 1) ** 2, 0, 1))
    return c * (0.45 + 0.55 * p)
# A: double rope, opposite twist
v = y / 7.8
top_c = v < 0.5; w1 = np.where(top_c, v * 2, v * 2 - 1)
bandA = np.where(top_c, rope(x, w1, 3.9, 44, 113.1, 1), rope(x, w1, 3.9, 44, 113.1, -1))
save(bandA, 'am-band-rope.png')
# B: heavy coin reeding between two plain rails, a cut line under each rail
ph = (x * 84 / 113.1) % 1.0; reed = np.sqrt(np.clip(1 - (2 * ph - 1) ** 2, 0, 1)) * np.ones_like(y)
rail = (y < 0.7) | (y > 7.1); cut = ((y >= 0.7) & (y < 1.0)) | ((y > 6.8) & (y <= 7.1))
bandB = np.where(rail, 1.0, np.where(cut, 0.0, 0.15 + 0.85 * reed))
save(bandB, 'am-band-reed.png')
# C: one row of big Y's punched into a plain raised band
imC = Image.new('L', (W, H), 255); gh = int(4.4 * PX); gw = int(gh * glyph.width / glyph.height); g = glyph.resize((gw, gh), Image.LANCZOS)
n = 15
for i in range(n + 1):
    cx = (i + 0.5) * W / n
    for off in (0, -W): imC.paste(0, (int(cx - gw / 2 + off), int(H / 2 - gh / 2)), g)
a = np.asarray(imC, np.float32) / 255
a = np.where((y < 0.45) | (y > 7.35), 1.0, a)          # crisp rails
a = np.where(((y >= 0.45) & (y < 0.7)) | ((y > 7.1) & (y <= 7.35)), 0.0, a)
save(a, 'am-band-stamp.png', 0.9)
# ---------- tops: 1600 px = 40 mm, 40 px/mm, centre 800 ----------
N = 1600; yy, xx = np.mgrid[0:N, 0:N]; X = (xx - 800) / 40; Yc = (800 - yy) / 40; R = np.hypot(X, Yc); T = np.arctan2(Yc, X)
# hammered field: overlapping spherical dents (computed at 1/4 res)
n4 = 400; g4 = (np.mgrid[0:n4, 0:n4][::-1] * 4 + 2 - 800) / 40.0
pts = rng.uniform(-18, 18, (1500, 2)); rad = rng.uniform(0.8, 1.2, 1500)
best = np.full((n4, n4), 9.0)
for (px_, py_), r_ in zip(pts, rad):
    d = np.hypot(g4[0] - px_, -g4[1] - py_) / r_; best = np.minimum(best, d)
ham = Image.fromarray((np.clip(best ** 2, 0, 1) * 255).astype(np.uint8)).resize((N, N), Image.BICUBIC)
ham = np.asarray(ham, np.float32) / 255                     # 0 at dent centre, 1 on ridges
field = 0.10 + 0.14 * ham
ymask = np.asarray(Y, np.float32) / 255
def rope_ring(r0, r1, strands, d=1):
    w = np.clip((R - r0) / (r1 - r0), 0, 1); inside = (R >= r0) & (R <= r1)
    circ = 2 * math.pi * (r0 + r1) / 2
    return np.where(inside, rope(T * (r0 + r1) / 2, w, r1 - r0, strands, circ, d), 0)
rim = (R > 17.0).astype(np.float32)
# A concho: Y, hammered centre, sunburst ring of stamped rays, rope border
rays = (T / (2 * math.pi) * 48) % 1.0
groove = np.abs(rays - 0.5) < (0.16 * (R - 11.2) / 3.6 + 0.05)
sun = np.where((R > 11.2) & (R < 14.8), np.where(groove, 0.12, 0.72), 0)
sepr = ((R > 14.8) & (R < 15.15)) * 0.0
topA = np.where(R < 11.0, field, 0) + sun + rope_ring(15.25, 16.95, 64) + rim
topA = np.maximum(topA, ymask)
save(topA, 'am-top-concho.png', 0.8)
# B / C: Y on hammered field, rope border (B) or plain bevelled rim (C)
topB = np.maximum(np.where(R < 15.1, field, 0) + rope_ring(15.25, 16.95, 64) + rim, ymask); save(topB, 'am-top-rope.png', 0.8)
topC = np.maximum(np.where(R < 16.2, field, 0) + ((R >= 16.2) & (R < 16.5)) * 0.0 + (R >= 16.5) * 1.0, ymask); save(topC, 'am-top-plain.png', 0.8)
print('ok')

# The Build a set wall, after Casa Loewe: backlit panels of every size and every area colour. The wall is split again and again
# at random, so panels run from big squares to thin slivers, and each panel gets its own light: a shadow in a corner, a band,
# a streak, two spots, a leak from one edge, or an even glow. Oxblood bars run along some of the splits.
#   python3 cyc/lbset/loewe.py OUT.png [SEED] [W] [H]
import sys, numpy as np, random, colorsys
from scipy.ndimage import gaussian_filter
OUT = sys.argv[1]; SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 3
W = int(sys.argv[3]) if len(sys.argv) > 3 else 3000; H = int(sys.argv[4]) if len(sys.argv) > 4 else 1000
rng = random.Random(SEED); np.random.seed(SEED)
def hx(h): return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], float) / 255
PAL = {'coral': ('#FFB8A6', '#FF6A55', '#B8321F'), 'lemon': ('#FFE88A', '#FFCB3A', '#B9820C'), 'lime': ('#C9F0A6', '#6CC93A', '#2F7A16'),
       'sky': ('#BDE9FC', '#36B3E8', '#0E5A8C'), 'lilac': ('#E2D4FF', '#A57BF0', '#5A34B0'), 'cream': ('#FFF8EC', '#F6E9D2', '#C9AE86')}
HUES = ['lemon', 'coral', 'lime', 'sky', 'lilac', 'cream']; WEIGHT = [5, 3, 3, 3, 3, 1.5]
OX = hx('#6E1C2A')
def split(x0, y0, x1, y1, depth, minw):
    # guillotine split; long panels tend to be cut across, but not always, so strips and slivers survive
    w, h = x1 - x0, y1 - y0
    if depth == 0 or (w < 2 * minw and h < 2 * minw): return [(x0, y0, x1, y1)]
    vert = (w > h * 1.2) if rng.random() < 0.75 else (rng.random() < 0.5)
    if vert and w < 2 * minw: vert = False
    if not vert and h < 2 * minw: vert = True
    t = rng.choice([0.5, 0.38, 0.62, 0.25, 0.75, 0.15, 0.85, 0.33])
    if vert:
        c = int(x0 + max(minw, min(w - minw, w * t))); return split(x0, y0, c, y1, depth - 1, minw) + split(c, y0, x1, y1, depth - 1, minw)
    c = int(y0 + max(minw, min(h - minw, h * t))); return split(x0, y0, x1, c, depth - 1, minw) + split(x0, c, x1, y1, depth - 1, minw)
# big blocks first, each with one area colour; then each block breaks up to its own depth
blocks = split(0, 0, W, H, 4, 220); cells = []; last = None
for (x0, y0, x1, y1) in blocks:
    hue = rng.choices(HUES, WEIGHT)[0]
    while hue == last: hue = rng.choices(HUES, WEIGHT)[0]
    last = hue
    for c in split(x0, y0, x1, y1, rng.choice([1, 2, 3, 3, 4, 5]), rng.choice([40, 60, 90])):
        h_ = hue if rng.random() > 0.12 else rng.choices(HUES, WEIGHT)[0]    # now and then a panel in a neighbour's colour
        cells.append(c + (h_, (x0, y0, x1, y1)))
def shift(c, dh, ds, dv):
    h, s, v = colorsys.rgb_to_hsv(*c); return np.array(colorsys.hsv_to_rgb((h + dh) % 1, min(1, max(0, s * ds)), min(1, v * dv)))
img = np.zeros((H, W, 3))
for (x0, y0, x1, y1, hue, blk) in cells:
    lt, md, dp = (hx(v) for v in PAL[hue]); w, h = x1 - x0, y1 - y0
    dh = rng.uniform(-0.025, 0.025); lt, md, dp = shift(lt, dh, 1, 1), shift(md, dh, rng.uniform(0.85, 1.1), 1), shift(dp, dh * 2, 1, rng.uniform(0.8, 1.15))
    t = rng.uniform(0.15, 0.85); cell = np.ones((h, w, 3)) * (lt * (1 - t) + md * t)
    P = 120; m = np.zeros((h + 2 * P, w + 2 * P)); kind = rng.choices(['corner', 'band', 'streak', 'twin', 'blob', 'leak', 'flat'], [3, 2, 2, 2, 3, 2, 1])[0]
    def rect(cx, cy, bw, bh, val=1.0):
        a, b = int(P + cy - bh / 2), int(P + cx - bw / 2); m[max(0, a):max(0, a + int(bh)), max(0, b):max(0, b + int(bw))] = val
    if kind == 'corner': rect(rng.choice([0.15, 0.85]) * w, rng.choice([0.2, 0.8]) * h, rng.uniform(0.6, 1.1) * w, rng.uniform(0.6, 1.1) * h)
    elif kind == 'band': rect(w / 2, rng.uniform(0.25, 0.75) * h, w * 1.3, rng.uniform(0.15, 0.4) * h)
    elif kind == 'streak': rect(rng.uniform(0.25, 0.75) * w, h / 2, rng.uniform(0.15, 0.4) * w, h * 1.3)
    elif kind == 'twin':
        rect(rng.uniform(0.2, 0.4) * w, rng.uniform(0.25, 0.45) * h, 0.3 * w, 0.3 * h); rect(rng.uniform(0.6, 0.8) * w, rng.uniform(0.55, 0.8) * h, 0.35 * w, 0.3 * h, 0.8)
    elif kind == 'blob': rect(rng.uniform(0.35, 0.65) * w, rng.uniform(0.35, 0.65) * h, rng.uniform(0.35, 0.8) * w, rng.uniform(0.35, 0.8) * h)
    elif kind == 'leak':
        e = rng.choice('lrtb'); yy, xx = np.mgrid[0:h, 0:w]
        g = {'l': xx / w, 'r': 1 - xx / w, 't': yy / h, 'b': 1 - yy / h}[e]; m[P:P + h, P:P + w] = g ** 1.5
    sig = rng.uniform(0.1, 0.28) * min(w, h) + 4
    m = gaussian_filter(m, sig)[P:P + h, P:P + w]
    if m.max() > 0: m = m / max(m.max(), 0.6)
    k = (rng.uniform(0.45, 0.95) if hue != 'cream' else rng.uniform(0.2, 0.5)) * (0 if kind == 'flat' else 1)
    cell = cell * (1 - k * m[..., None]) + dp * (k * m[..., None])
    # a hot spot where the lamp sits nearest the diffuser, on some panels
    if rng.random() < 0.35:
        yy, xx = np.mgrid[0:h, 0:w]; hx_, hy_ = rng.uniform(0.2, 0.8) * w, rng.uniform(0.2, 0.8) * h
        s_ = np.exp(-(((xx - hx_) / (0.35 * w)) ** 2 + ((yy - hy_) / (0.35 * h)) ** 2))[..., None] * rng.uniform(0.2, 0.45)
        cell = cell * (1 - s_) + lt * s_
    yy, xx = np.mgrid[0:h, 0:w]; d = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy))
    r = np.exp(-d / rng.uniform(4, 9))[..., None] * 0.5                   # the pale seam where the panel meets its frame
    img[y0:y1, x0:x1] = cell * (1 - r) + (lt * 0.5 + 0.5) * r
# Oxblood bars along horizontal splits inside the coloured blocks, each running the width of its block or part of it
bars = np.zeros((H, W)); used = []
cand = [(y0, blk) for (x0, y0, x1, y1, hue, blk) in cells if y0 > 60 and hue != 'cream' and y0 > blk[1]]
rng.shuffle(cand)
for y, (bx0, by0, bx1, by1) in cand:
    if len(used) >= 12: break
    if any(abs(y - uy) < 60 and bx0 < ux1 and ux0 < bx1 for uy, ux0, ux1 in used): continue
    x0, x1 = (bx0, bx1) if rng.random() < 0.6 else (bx0, int(bx0 + (bx1 - bx0) * rng.uniform(0.4, 0.8)))
    used.append((y, x0, x1)); th = rng.choice([14, 18, 24, 30]); bars[y - th // 2:y + th // 2, x0:x1] = 1
bars = gaussian_filter(bars, 1.3)[..., None]
img = img * (1 - bars) + OX * bars
img += np.random.normal(0, 0.012, img.shape)
from PIL import Image
Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(OUT)
print(len(cells), 'cells,', len(blocks), 'blocks')

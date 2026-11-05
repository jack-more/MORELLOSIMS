# Snake rope band: a twisted rope weaving between the rope edges; leaf sprays + bright-cut fans in every pocket.
import math, os, numpy as np
from PIL import Image, ImageDraw, ImageFilter
rng = np.random.default_rng(5)
PX, SS = 40, 2; Wmm, Hmm = 113.1, 7.8; W, H = int(Wmm * PX), int(Hmm * PX); S = PX * SS
G = lambda k, d: float(os.environ.get(k, d))
B = G('SB', '1.5'); yc = Hmm / 2
N = int(G('SN', '6')); U = Wmm / N
RW = G('RW', '1.45')                     # snake rope width
A = (Hmm - 2 * B - RW) / 2 + G('KISS', '0.12')
SLOT_X = 0.75 * Wmm; SLOT_Y = (9 - 0.6) - 9 * 0.42
y = (np.arange(H)[:, None] + 0.5) / PX; x = (np.arange(W)[None, :] + 0.5) / PX
f = lambda xx: yc - A * np.cos(2 * np.pi * (xx - SLOT_X) / U)          # crest (rope high) over the spout
fp = lambda xx: A * 2 * np.pi / U * np.sin(2 * np.pi * (xx - SLOT_X) / U)
# ---------------- base: matte metal ----------------
a = np.full((H, W), 0.72, np.float32)
# ---------------- leaves (drawn as shape + cut layers) ----------------
shape = Image.new('L', (W * SS, H * SS), 0); ds = ImageDraw.Draw(shape)
cuts = Image.new('L', (W * SS, H * SS), 0); dc = ImageDraw.Draw(cuts)
def poly(d, pts):
    for off in (0, -Wmm, Wmm): d.polygon([((px_ + off) * S, py_ * S) for px_, py_ in pts], fill=255)
def line(d, p0, p1, w):
    for off in (0, -Wmm, Wmm): d.line([((p0[0] + off) * S, p0[1] * S), ((p1[0] + off) * S, p1[1] * S)], fill=255, width=max(1, int(w * S)))
def leaf(base, ang, L, Wd, curl, lobes=3):
    t = np.linspace(0, 1, 80); aa = ang + curl * t
    cx = base[0] + np.cumsum(np.cos(aa)) * L / 80; cy = base[1] + np.cumsum(np.sin(aa)) * L / 80
    wdt = Wd * np.sin(np.pi * t ** 0.7) * (1 + 0.22 * np.abs(np.sin(np.pi * lobes * t)))
    nx, ny = -np.sin(aa), np.cos(aa)
    poly(ds, list(zip(cx + wdt * nx, cy + wdt * ny)) + list(zip((cx - wdt * nx)[::-1], (cy - wdt * ny)[::-1])))
    for k in range(4, 70, 6): line(dc, (cx[k], cy[k]), (cx[k + 6], cy[k + 6]), 0.08)          # vein
    for k in range(6, 76, 2):                                                                   # shading cuts
        w = wdt[k] * 0.9
        for sd in (1, -1):
            if sd == -1 and k % 4: continue
            line(dc, (cx[k] + sd * 0.1 * nx[k], cy[k] + sd * 0.1 * ny[k]),
                 (cx[k] + sd * w * nx[k] - 0.3 * w * math.cos(aa[k]), cy[k] + sd * w * ny[k] - 0.3 * w * math.sin(aa[k])), 0.045)
pockets = []
for i in range(2 * N):
    xp = SLOT_X + i * U / 2; xp = xp % Wmm
    crest = (i % 2 == 0); s_ = 1 if crest else -1                  # crest: pocket below the rope (s_=+1, opens downward)
    edge_y = f(xp) + s_ * RW / 2
    pockets.append((xp, edge_y, s_, i == 0))
    if i == 0: continue                                            # the spout pocket gets the plaque
    down = s_ * math.pi / 2
    depth = 2 * A - RW * 0.2
    leaf((xp, edge_y - s_ * 0.2), down, depth * 0.95, 0.85, 0.0, 3)
    for sd in (1, -1):
        leaf((xp + sd * 0.3, edge_y - s_ * 0.15), down - s_ * sd * 1.05, 3.4, 0.8, s_ * sd * 0.75, 3)
        xq = xp + sd * U * 0.17; eq = f(xq) + s_ * RW / 2 * math.sqrt(1 + fp(xq) ** 2)
        leaf((xq, eq - s_ * 0.15), down - s_ * sd * 0.25, 2.4, 0.62, s_ * sd * 0.8, 3)
shape = np.asarray(shape.resize((W, H), Image.LANCZOS), np.float32) / 255
cuts = np.asarray(cuts.resize((W, H), Image.LANCZOS), np.float32) / 255
# ---------------- bright-cut fans behind the leaves ----------------
fan = np.zeros((H, W), np.float32)
for xp, ey, s_, _ in pockets:
    dx = x - xp; dx = (dx + Wmm / 2) % Wmm - Wmm / 2
    th = np.arctan2((y - ey) * s_, dx)                               # 0..pi inside the pocket
    g = np.abs(((th / math.pi) * 34) % 1.0 - 0.5) < 0.17
    near = (np.abs(dx) < U * 0.5) & ((y - ey) * s_ > 0) & (th > 0.18) & (th < math.pi - 0.18)
    fan = np.where(near & g, 1.0, fan)
a = np.where(fan > 0, 0.5, a)
# leaves on top: domed, cut, outlined
dome = np.asarray(Image.fromarray((shape * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(7)), np.float32) / 255
leafh = 0.8 + 0.2 * np.clip(dome * 1.5, 0, 1) - 0.35 * cuts
a = np.where(shape > 0.5, leafh, a)
sb = np.asarray(Image.fromarray((shape * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5)), np.float32) / 255
a = np.where((sb > 0.22) & (sb < 0.78), 0.1, a)
# ---------------- the snake rope ----------------
fy = f(x); slope = fp(x); c = 1 / np.sqrt(1 + slope ** 2)
dperp = (y - fy) * c                                                 # signed distance across the rope
xs = np.linspace(0, Wmm, 20001); sl = np.concatenate([[0], np.cumsum(np.sqrt(1 + fp(xs[:-1]) ** 2) * np.diff(xs))])
arc = np.interp(x, xs, sl)
L_tot = sl[-1]; strands = round(L_tot / 0.85)
w = np.clip(dperp / RW + 0.5, 0, 1); on = np.abs(dperp) < RW / 2
u = (arc / L_tot * strands + w * 1.5) % 1.0
rope = 0.4 + 0.6 * np.sqrt(np.clip(1 - (2 * u - 1) ** 2, 0, 1)) * (0.5 + 0.5 * np.sqrt(np.clip(1 - (2 * w - 1) ** 2, 0, 1)))
a = np.where(on, rope, a)
a = np.where((np.abs(dperp) >= RW / 2) & (np.abs(dperp) < RW / 2 + 0.08), 0.08, a)
# ---------------- rope edges top and bottom ----------------
def edge_rope(y0, y1, flip):
    ins = (y >= y0) & (y < y1); v = (y - y0) / (y1 - y0)
    uu = (x / 0.8 + flip * v * 1.5) % 1.0
    return ins, 0.4 + 0.6 * np.sqrt(np.clip(1 - (2 * uu - 1) ** 2, 0, 1)) * (0.5 + 0.5 * np.sqrt(np.clip(1 - (2 * v - 1) ** 2, 0, 1)))
for y0, y1, fl in ((0.0, B, 1), (Hmm - B, Hmm, -1)):
    ins, hh = edge_rope(y0, y1, fl); a = np.where(ins, hh, a)
a = np.where((np.abs(y - B) < 0.06) | (np.abs(y - (Hmm - B)) < 0.06), 0.06, a)
# ---------------- spout cartouche ----------------
PA, PB = G('PA', '2.1'), G('PB', '0.85')
e = np.hypot((x - SLOT_X) / PA, (y - SLOT_Y) / PB); phi = np.arctan2((y - SLOT_Y) / PB, (x - SLOT_X) / PA)
FW = 0.5; inr = (e >= 1.08) & (e < 1.08 + FW); ww = np.clip((e - 1.08) / FW, 0, 1)
uu = (phi / (2 * np.pi) * 32 + ww * 1.4) % 1.0
fr = 0.4 + 0.6 * np.sqrt(np.clip(1 - (2 * uu - 1) ** 2, 0, 1)) * (0.5 + 0.5 * np.sqrt(np.clip(1 - (2 * ww - 1) ** 2, 0, 1)))
a = np.where(e < 1.0, 1.0, a); a = np.where((e >= 1.0) & (e < 1.08), 0.05, a)
a = np.where(inr, fr, a); a = np.where((e >= 1.08 + FW) & (e < 1.14 + FW), 0.05, a)
# thin polished ring that separates the cartouche from the snake rope
a = np.where((e >= 1.14 + FW) & (e < 1.30 + FW), 1.0, a); a = np.where((e >= 1.30 + FW) & (e < 1.36 + FW), 0.05, a)
Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.45)).save('am-band-snake.png')
print('ok', 'A', round(A, 2))

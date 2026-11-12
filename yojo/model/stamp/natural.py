# Direction B, printed like a real stamp on a curved shell: pressure falloff, dot gain, mottled ink, voids, satellites.
import sys, math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
sys.argv += [] ; exec(open('dirs.py').read().split('lines = [')[0])          # reuse text_img / wordmark / coverage
def noise(W, H, scale, seed):
    r = np.random.default_rng(seed).random((max(2, H // scale), max(2, W // scale))).astype(np.float32)
    return np.asarray(Image.fromarray((r * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32) / 255
def stamp_B(lines, pitch=14, seed=5, pressure=0.3, gain=0.05, voids=0.15, curve=True, blur=0.6, void_scale=4, rows_y=16, rows_t=10):
    rnd = random.Random(seed); out = []
    for kind, txt in lines:
        src = wordmark(600) if kind == 'y' else text_img(txt, SERIF, 400, track=30)
        out.append(coverage(src, rows_y if kind == 'y' else rows_t))
    W = max(c.shape[1] for c in out) * pitch + 40; H = sum(c.shape[0] + 3 for c in out) * pitch + 20
    S = 3; im = Image.new('L', (W * S, H * S), 0); d = ImageDraw.Draw(im); y = 20
    for cov in out:
        for r in range(cov.shape[0]):
            for c in range(cov.shape[1]):
                v = cov[r, c]
                if v < 0.08: continue
                rr = pitch * 0.62 * math.sqrt(v) * (1 + gain) * rnd.uniform(0.9, 1.08)
                cx = 20 + (c + 0.5) * pitch + rnd.gauss(0, 0.05 * pitch); cy = y + (r + 0.5) * pitch + rnd.gauss(0, 0.05 * pitch)
                ax = rnd.uniform(0.88, 1.1)
                d.ellipse([S * (cx - rr * ax), S * (cy - rr / ax), S * (cx + rr * ax), S * (cy + rr / ax)], fill=int(255 * rnd.uniform(0.78, 1.0)))
                if rnd.random() < 0.06:                                   # a stray satellite droplet
                    a_ = rnd.uniform(0, 6.28); dd = rr + rnd.uniform(1.5, 3.5); sr = rnd.uniform(0.8, 1.6)
                    sx, sy = cx + dd * math.cos(a_), cy + dd * math.sin(a_)
                    d.ellipse([S * (sx - sr), S * (sy - sr), S * (sx + sr), S * (sy + sr)], fill=int(255 * rnd.uniform(0.5, 0.9)))
        y += (cov.shape[0] + 3) * pitch
    m = np.asarray(im.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(blur)), np.float32) / 255
    m = np.clip(m * 1.15, 0, 1)                                            # ink spread joins close dots
    # pressure: strongest in the middle of the stamp, fading to the edges, uneven
    yy, xx = np.mgrid[0:H, 0:W]; cxn = (xx / W - 0.5) * 2; cyn = (yy / H - 0.5) * 2
    press = 1 - pressure * np.clip((cxn ** 2 * 0.8 + cyn ** 2 * 0.5), 0, 1) if curve else np.ones((H, W))
    press = press * (0.82 + 0.3 * noise(W, H, 90, seed + 1))
    # shell texture: ink skips the high points
    shell = noise(W, H, void_scale, seed + 2) * 0.6 + noise(W, H, void_scale * 3, seed + 3) * 0.4
    hole = np.clip((shell - (1 - voids)) / 0.08, 0, 1)
    a = np.clip(m * press * (1 - 0.85 * hole) * (0.88 + 0.24 * noise(W, H, 5, seed + 4)), 0, 1)
    return Image.fromarray((a * 255).astype(np.uint8))
if __name__ == '__main__':
    lines = [('y', 'YOJO'), ('t', 'GHK-CU'), ('t', 'BATCH 0001'), ('t', '2026.11.12')]
    sets = [('light', dict(pressure=0.18, gain=0.03, voids=0.07, blur=0.5)),
            ('medium', dict(pressure=0.3, gain=0.05, voids=0.15, blur=0.6)),
            ('strong', dict(pressure=0.42, gain=0.08, voids=0.24, blur=0.75))]
    ims = []
    for n, kw in sets:
        m = stamp_B(lines, **kw); im = colorize(m, (22, 143, 224)); im.save(f'nat_{n}.png'); m.save(f'nat_{n}_mask.png'); ims.append((n, im))
    H = 520; rs = [(n, i.resize((int(i.width * H / i.height), H), Image.LANCZOS)) for n, i in ims]
    board = Image.new('RGB', (sum(i.width for _, i in rs) + 80, H + 60), (255, 255, 255)); x = 20
    d = ImageDraw.Draw(board); lab = ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-SemiBold.otf', 22)
    for n, im in rs: board.paste(im, (x, 50)); d.text((x, 14), n, fill=(20, 20, 20), font=lab); x += im.width + 20
    board.save('natural_board.png')
    z = []
    for n, im in ims: z.append(im.crop((0, 0, im.width // 2, im.height // 2)))
    zb = Image.new('RGB', (sum(i.width for i in z) + 40, z[0].height), (255, 255, 255)); x = 0
    for i in z: zb.paste(i, (x, 0)); x += i.width + 20
    zb.save('natural_zoom.png'); print('ok')

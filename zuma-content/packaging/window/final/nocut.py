# No-cutout variant of the Rev E Window box, compared with the window version. 2D, from window/geomE.json.
import os, json, math, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
S = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
W = os.path.join(S, 'window'); G = json.load(open(os.path.join(W, 'geomE.json'))); T = os.path.join(W, 'tex')
IW, IH = G['inside']['w'], G['inside']['h']; Q = 24
AH = {a['name']: a['hex'] for a in G['areas']}
SNOW = (252, 251, 248)
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'; FB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
DISP = os.path.join(S, 'zfonts', 'LexendExa-700.ttf')
def hx(s): s = s.lstrip('#'); return np.array([int(s[i:i + 2], 16) for i in (0, 2, 4)], np.float32)
WIN = G['windows'][0]

def base_panel(area):
    col = hx(AH[area]); pw, ph = round(IW * Q), round(IH * Q)
    im = np.ones((ph, pw, 3), np.float32) * hx('#F7F4EE')
    im += np.random.default_rng(1).normal(0, 2.0, (ph, pw, 1))
    Y = lambda z: ph - z * Q
    for p in G['panels']:
        a0, a1 = round(p['x0'] * Q), round(p['x1'] * Q); b0, b1 = round(Y(p['y1'])), round(Y(p['y0']))
        yy = (np.arange(b0, b1)[:, None] / Q) % G['rib']['pitch'] / G['rib']['pitch']
        r = np.cos(2 * math.pi * yy)
        im[b0:b1, a0:a1] = np.repeat(col[None, None, :] * (1.0 + 0.09 * r[..., None]), a1 - a0, axis=1)
    return im, col, Y

def fit(draw, text, font_path, max_w, max_h, start):
    s = start
    while s > 6:
        f = ImageFont.truetype(font_path, s); b = draw.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= max_w and b[3] - b[1] <= max_h: return f, b
        s -= 1
    f = ImageFont.truetype(font_path, 6); return f, draw.textbbox((0, 0), text, font=f)

def nocut_panel(area, name, dose):
    im, col, Y = base_panel(area); ph, pw = im.shape[:2]
    x0, x1 = round(WIN['x0'] * Q), round(WIN['x1'] * Q); y0, y1 = round(Y(WIN['y1'])), round(Y(WIN['y0']))
    w, h = x1 - x0, y1 - y0
    # smooth gloss panel: flat colour, soft diagonal sheen + top highlight (spot UV)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    sheen = np.exp(-(((xx - w * 0.15) + (yy - h * 0.1) * 0.55) ** 2) / (2 * (w * 0.16) ** 2)) * 0.22
    top = np.exp(-yy / (h * 0.06)) * 0.10
    darken = 1 - 0.06 * (yy / h)
    tile = col[None, None, :] * darken[..., None] + 255 * (sheen + top)[..., None] * 0.55
    im[y0:y1, x0:x1] = tile
    out = Image.fromarray(np.clip(im, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(out)
    pad = int(0.9 * Q); inner_w = w - 2 * pad
    # area caps (tiny) at top
    fa, ba = fit(d, area.upper(), FB, inner_w, int(0.9 * Q), int(0.75 * Q))
    d.text((x0 + (w - (ba[2] - ba[0])) / 2 - ba[0], y0 + int(1.0 * Q) - ba[1]), area.upper(), font=fa, fill=SNOW)
    # product name: one line if it fits at >= 2.4 mm cap, else two lines
    lines = [name]
    fn, bn = fit(d, name, DISP, inner_w, int(5.5 * Q), int(4.2 * Q))
    if (bn[3] - bn[1]) < 2.4 * Q and len(name) > 7:
        if ' ' in name: lines = name.split(' ', 1)
        else: mid = len(name) // 2 + 1; lines = [name[:mid] + '-', name[mid:]]
        fn = min((fit(d, l, DISP, inner_w, int(3.2 * Q), int(3.2 * Q))[0] for l in lines), key=lambda f: f.size)
    lh = [d.textbbox((0, 0), l, font=fn) for l in lines]
    total = sum(b[3] - b[1] for b in lh) + (len(lines) - 1) * int(0.5 * Q)
    fd, bd = fit(d, dose, FB, inner_w, int(1.4 * Q), int(1.25 * Q))
    gapd = int(0.9 * Q); blk = total + gapd + (bd[3] - bd[1])
    cy = y0 + (h - blk) / 2 + int(0.6 * Q)
    for l, b in zip(lines, lh):
        d.text((x0 + (w - (b[2] - b[0])) / 2 - b[0], cy - b[1]), l, font=fn, fill=SNOW); cy += (b[3] - b[1]) + int(0.5 * Q)
    cy += gapd - int(0.5 * Q)
    d.text((x0 + (w - (bd[2] - bd[0])) / 2 - bd[0], cy - bd[1]), dose, font=fd, fill=SNOW)
    return out

def window_panel():
    # crop the RT-3 card from the approved front-2d.png (exact same render)
    src = Image.open(os.path.join(W, 'final', 'front-2d.png')); pw, ph = round(IW * Q), round(IH * Q)
    return src.crop((80, 220, 80 + pw, 220 + ph))

def shadow_paste(out, im, x, y):
    pw, ph = im.size
    sh = Image.new('RGBA', (pw + 60, ph + 60), (0, 0, 0, 0)); ImageDraw.Draw(sh).rectangle((30, 30, pw + 30, ph + 30), fill=(60, 40, 30, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(18)); out.paste(sh, (x - 22, y - 14), sh)
    out.paste(im, (x, y)); ImageDraw.Draw(out).rectangle((x, y, x + pw - 1, y + ph - 1), outline=(200, 192, 180))

pw, ph = round(IW * Q), round(IH * Q)
ROW = [('Metabolic', 'RT-3', '10 MG'), ('Tissue', 'BPC+TB', '10 MG'), ('Dermal', 'GHK-Cu', '50 MG'),
       ('Endocrine', 'Tesamorelin', '10 MG'), ('Neuro', 'Selank', '10 MG'), ('Lab supplies', 'BAC Water', '10 ML')]
pad = 90; Wd = 2400
small = 0.62; spw, sph = int(pw * small), int(ph * small)
Hd = 1900 + sph + 780
out = Image.new('RGB', (Wd, Hd), (245, 240, 232)); d = ImageDraw.Draw(out)
f = lambda s, b=False: ImageFont.truetype(FB if b else FONT, s)
d.text((pad, 60), 'ZUMA TIDES · WINDOW CARTON · REV E · NO-CUTOUT VARIANT · FRONT PANEL 6:1', font=f(26), fill=(110, 28, 42))
d.text((pad, 104), 'Same box, no die-cut: the centre panel is printed, glossy, with the product name.', font=f(40, True), fill=(30, 20, 20))
# 1. side by side, large (scale 1.6)
big = 1.55; bw, bh = int(pw * big), int(ph * big)
L = [('WINDOW (die-cut)', window_panel().resize((bw, bh), Image.LANCZOS),
      'One die-cut window: you see the vial label and the coloured inside.'),
     ('NO CUTOUT (printed)', nocut_panel('Metabolic', 'RT-3', '10 MG').resize((bw, bh), Image.LANCZOS),
      'Centre panel printed solid, spot-UV gloss, name and dose in Snow.')]
gx = (Wd - 2 * bw) // 3
for i, (t, im, cap) in enumerate(L):
    x = gx + i * (bw + gx); y = 230
    d.text((x, y), t, font=f(30, True), fill=(110, 28, 42))
    shadow_paste(out, im, x, y + 60)
    d.text((x, y + 60 + bh + 26), cap, font=f(22), fill=(80, 70, 60))
# 2. six colours
y2 = 230 + 60 + bh + 120
d.text((pad, y2), 'NO-CUTOUT · ALL SIX AREA COLOURS', font=f(26, True), fill=(110, 28, 42))
gx2 = (Wd - 2 * pad - 6 * spw) // 5
for i, (a, n, ds) in enumerate(ROW):
    x = pad + i * (spw + gx2); y = y2 + 60
    shadow_paste(out, nocut_panel(a, n, ds).resize((spw, sph), Image.LANCZOS), x, y)
    d.text((x, y + sph + 20), a, font=f(24, True), fill=(30, 20, 20)); d.text((x, y + sph + 56), f'{n} · {ds.lower()}', font=f(20), fill=(110, 100, 90))
# 3. table
y3 = y2 + 60 + sph + 140
d.text((pad, y3), 'WINDOW vs NO CUTOUT', font=f(26, True), fill=(110, 28, 42))
rows = [('', 'Window (die-cut)', 'No cutout (printed)'),
        ('Customer sees', 'The real vial label and the coloured inside', 'A glossy colour panel with the name and dose'),
        ('Die / cost', 'Window cut in the die; one more step to inspect', 'Simpler die, no window: slightly cheaper and sturdier'),
        ('Print versions', '6 (one per area colour); the vial shows the product', '11 (one per product) because the name is printed'),
        ('Low-cost option', '—', 'Print 6 colour versions with a blank centre panel + a small per-product name sticker'),
        ('Unchanged', 'Ribs, side crest, foil, inside colour, back QR', 'Same')]
cw = [360, 900, 900]; ry = y3 + 56
for j, r in enumerate(rows):
    x = pad
    for k, c in enumerate(r):
        d.text((x, ry), c, font=f(22, j == 0 or k == 0), fill=(30, 20, 20) if j else (110, 28, 42)); x += cw[k]
    ry += 46; d.line((pad, ry - 10, Wd - pad, ry - 10), fill=(215, 205, 192), width=1)
d.text((pad, ry + 20), 'Main trade-off: printing the name means 11 print versions instead of 6. The sticker option keeps it at 6.', font=f(24, True), fill=(110, 28, 42))
out = out.crop((0, 0, Wd, ry + 90))
os.makedirs(os.path.join(W, 'final'), exist_ok=True)
out.save(os.path.join(W, 'final', 'nocut-board.png')); print('ok', out.size)

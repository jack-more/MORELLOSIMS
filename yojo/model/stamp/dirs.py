import numpy as np, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
INTER_BLACK = '/usr/share/fonts/opentype/inter/Inter-Black.otf'
SERIF = [p for p in __import__('glob').glob('/usr/share/fonts/**/FreeSerifBold.*', recursive=True)][0]
def text_img(txt, font, size, sx=1.0, track=0):
    f = ImageFont.truetype(font, size); asc, desc = f.getmetrics()
    w = int(sum(f.getlength(c) for c in txt) + track * len(txt) + size)
    im = Image.new('L', (w, asc + desc), 0); d = ImageDraw.Draw(im); x = 0
    for c in txt: d.text((x, 0), c, fill=255, font=f); x += f.getlength(c) + track
    im = im.crop(im.getbbox()); return im.resize((max(1, int(im.width * sx)), im.height), Image.LANCZOS)
def wordmark(h):
    im = Image.open('wordmark.png').convert('L'); im = im.crop(im.getbbox()); return im.resize((int(im.width * h / im.height), h), Image.LANCZOS)
def coverage(im, rows):
    cell = im.height / rows; cols = max(1, int(round(im.width / cell)))
    a = np.asarray(im.resize((cols, rows), Image.BOX), np.float32) / 255; return a
# ---- A: condensed square pixels, ink spread ----
def render_A(lines, ink):
    pitch, pad = 20, 0.14; out = []
    for i, (kind, txt) in enumerate(lines):
        src = text_img(txt, INTER_BLACK, 400, sx=0.62, track=40) if kind == 't' else text_img(txt, INTER_BLACK, 400, sx=0.62, track=40)
        cov = coverage(src, 11 if kind == 'y' else 8); out.append(cov)
    W = max(c.shape[1] for c in out) * pitch + 40; H = sum(c.shape[0] + 3 for c in out) * pitch + 20
    im = Image.new('L', (W * 2, H * 2), 0); d = ImageDraw.Draw(im); y = 20; rnd = random.Random(2)
    for cov in out:
        for r in range(cov.shape[0]):
            for c in range(cov.shape[1]):
                if cov[r, c] > 0.5:
                    x0 = 20 + c * pitch; y0 = y + r * pitch; g = pitch * pad
                    d.rectangle([2 * (x0 + g), 2 * (y0 + g), 2 * (x0 + pitch - g), 2 * (y0 + pitch - g)], fill=int(255 * rnd.uniform(0.82, 1)))
        y += (cov.shape[0] + 3) * pitch
    im = im.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(1.1)).point(lambda v: min(255, int(v * 1.25)))
    return colorize(im, ink)
# ---- B: halftone serif, YOJO from the real wordmark ----
def render_B(lines, ink):
    pitch = 14; out = []
    for kind, txt in lines:
        src = wordmark(600) if kind == 'y' else text_img(txt, SERIF, 400, track=30)
        out.append(coverage(src, 16 if kind == 'y' else 10))
    W = max(c.shape[1] for c in out) * pitch + 40; H = sum(c.shape[0] + 3 for c in out) * pitch + 20
    S = 3; im = Image.new('L', (W * S, H * S), 0); d = ImageDraw.Draw(im); y = 20
    for cov in out:
        for r in range(cov.shape[0]):
            for c in range(cov.shape[1]):
                v = cov[r, c]
                if v < 0.08: continue
                rr = pitch * 0.62 * np.sqrt(v); cx = 20 + (c + 0.5) * pitch; cy = y + (r + 0.5) * pitch
                d.ellipse([S * (cx - rr), S * (cy - rr), S * (cx + rr), S * (cy + rr)], fill=255)
        y += (cov.shape[0] + 3) * pitch
    return colorize(im.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.5)), ink)
# ---- C: wide heavy dots, double strike in two inks, off register ----
def render_C(lines, inks):
    pitch = 22; out = []
    for kind, txt in lines:
        src = text_img(txt, INTER_BLACK, 400, sx=1.45, track=60)
        out.append(coverage(src, 8 if kind == 'y' else 6))
    W = max(c.shape[1] for c in out) * pitch + 50; H = sum(c.shape[0] + 3 for c in out) * pitch + 30
    S = 3; im = Image.new('L', (W * S, H * S), 0); d = ImageDraw.Draw(im); y = 20
    for cov in out:
        for r in range(cov.shape[0]):
            for c in range(cov.shape[1]):
                if cov[r, c] < 0.5: continue
                cx = 20 + (c + 0.5) * pitch; cy = y + (r + 0.5) * pitch; rr = pitch * 0.40
                d.ellipse([S * (cx - rr), S * (cy - rr), S * (cx + rr), S * (cy + rr)], fill=255)
        y += (cov.shape[0] + 3) * pitch
    m = im.resize((W, H), Image.LANCZOS)
    paper = Image.new('RGB', (W, H), (238, 235, 222))
    for ink, off in zip(inks, ((0, 0), (8, 5))):
        layer = Image.new('L', (W, H), 0); layer.paste(m, off); multiply(paper, layer, ink)
    return paper
def multiply(paper, mask, ink):
    p = np.asarray(paper, np.float32) / 255; a = np.asarray(mask, np.float32)[..., None] / 255 * 0.88
    col = np.array(ink, np.float32) / 255; out = p * (1 - a) + p * col * a
    paper.paste(Image.fromarray((out * 255).astype(np.uint8)))
def colorize(mask, ink):
    paper = Image.new('RGB', mask.size, (238, 235, 222)); multiply(paper, mask, ink); return paper
lines = [('y', 'YOJO'), ('t', 'GHK-CU'), ('t', 'BATCH 0001'), ('t', '2026.11.12')]
SKY, COP = (22, 143, 224), (240, 106, 18)
a = render_A(lines, SKY); b = render_B(lines, SKY); c = render_C(lines, (SKY, COP))
for n, im in (('A', a), ('B', b), ('C', c)): im.save(f'dir_{n}.png')
H = 520; ims = [im.resize((int(im.width * H / im.height), H), Image.LANCZOS) for im in (a, b, c)]
board = Image.new('RGB', (sum(i.width for i in ims) + 80, H + 60), (255, 255, 255)); x = 20
d = ImageDraw.Draw(board); lab = ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-SemiBold.otf', 22)
for n, im in zip('ABC', ims): board.paste(im, (x, 50)); d.text((x, 14), n, fill=(20, 20, 20), font=lab); x += im.width + 20
board.save('dirs_board.png'); print(board.size)

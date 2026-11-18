# Preview: the three stamps inked in Oxblood on brown kraft, at the same scale, with a little rubber-stamp grain.
# Usage: python mock.py RENDER_DIR OUT.jpg   (RENDER_DIR holds the 40 px/mm black-on-white PNGs of the SVGs)
import sys, os, numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageFont
RD, OUT = sys.argv[1], sys.argv[2]
PX = 18                                     # px per mm in the preview
OX = np.array([0x6E, 0x1C, 0x2A], float) / 255
rng = np.random.default_rng(7)

def noise(w, h, scale, seed):
    r = np.random.default_rng(seed); n = r.random((h // scale + 2, w // scale + 2))
    return np.asarray(Image.fromarray((n * 255).astype('uint8')).resize((w, h), Image.BICUBIC), float) / 255

W, H = 3200, 1500
base = np.array([0xB4, 0x88, 0x5A], float) / 255                      # kraft
k = (noise(W, H, 60, 1) - .5) * .10 + (noise(W, H, 8, 2) - .5) * .07 + (rng.random((H, W)) - .5) * .05
fib = np.asarray(Image.fromarray((rng.random((H, W)) * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(0.6)).resize((W, H)), float) / 255
img = np.clip(base[None, None, :] * (1 + k[..., None]) + (fib[..., None] - .5) * .04, 0, 1)

names = [('zuma-stamp-A-round-seal', 'A  Round seal'), ('zuma-stamp-B-block', 'B  Block'), ('zuma-stamp-C-crest', 'C  Crest only')]
slot = W // 3
labels = []
for i, (n, lab) in enumerate(names):
    m = Image.open(os.path.join(RD, n + '.png')).convert('L')
    w, h = round(m.width * PX / 40), round(m.height * PX / 40)
    m = np.asarray(m.resize((w, h), Image.LANCZOS), float) / 255
    ink = 1 - m                                                         # 1 where the stamp prints
    grain = noise(w, h, 3, 10 + i) * .6 + noise(w, h, 40, 20 + i) * .4  # uneven pressure and rubber grain
    cov = np.clip(ink * (0.62 + 0.5 * grain), 0, 1) * (rng.random((h, w)) > 0.06)
    cov = np.asarray(Image.fromarray((cov * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(0.7)), float) / 255
    x0 = i * slot + (slot - w) // 2; y0 = (H - 160 - h) // 2 + 40
    reg = img[y0:y0 + h, x0:x0 + w]
    img[y0:y0 + h, x0:x0 + w] = reg * (1 - cov[..., None]) + (reg * OX[None, None, :] * 1.35) * cov[..., None]   # ink sinks into the kraft
    labels.append((i * slot + slot // 2, lab))

out = Image.fromarray((img * 255).astype('uint8'))
d = ImageDraw.Draw(out)
try: f = ImageFont.truetype(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Outfit-600.ttf'), 46)
except Exception: f = None
for x, lab in labels: d.text((x, H - 90), lab, fill=(58, 30, 20), font=f, anchor='mm')
out.save(OUT, quality=92)
print('ok')

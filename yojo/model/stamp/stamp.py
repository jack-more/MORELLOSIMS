# Render text in YOJO Batch as an inkjet egg stamp: round dots, uneven ink, a little bleed and drop-out.
import sys, math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, __import__('os').path.dirname(__file__)); from glyphs import G
def stamp(lines, dot=10, pitch=12, seed=1, ink=(0, 0, 0), dropout=0.02, align='left', track=1):
    rnd = random.Random(seed)
    cols = max(len(l) for l in lines); W = int((cols * (5 + track)) * pitch + 4 * pitch); H = int(len(lines) * 9 * pitch + 2 * pitch)
    S = 3; im = Image.new('L', (W * S, H * S), 0); d = ImageDraw.Draw(im)
    for li, line in enumerate(lines):
        x0 = 2 * pitch if align == 'left' else (W - len(line) * (5 + track) * pitch) / 2
        for ci, ch in enumerate(line.upper()):
            g = G.get(ch, G[' '])
            for r, row in enumerate(g):
                for c, v in enumerate(row):
                    if v != '#' or rnd.random() < dropout: continue
                    cx = x0 + (ci * (5 + track) + c + 0.5) * pitch + rnd.gauss(0, 0.07 * pitch)
                    cy = pitch + (li * 9 + r + 0.5) * pitch + rnd.gauss(0, 0.07 * pitch)
                    rr = dot / 2 * rnd.uniform(0.82, 1.12); a = int(255 * rnd.uniform(0.72, 1.0))
                    d.ellipse([(cx - rr) * S, (cy - rr * rnd.uniform(0.9, 1.1)) * S, (cx + rr) * S, (cy + rr) * S], fill=a)
    im = im.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.6))
    a = np.asarray(im, np.float32) / 255
    grain = np.asarray(Image.effect_noise((W, H), 60).filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255
    a = np.clip(a * (0.75 + 0.5 * grain), 0, 1)
    return Image.fromarray((a * 255).astype(np.uint8))
if __name__ == '__main__':
    s = stamp(['YOJO GHK-CU', 'BATCH 0001', '2026.11.12', 'ABCDEFGHIJKLM', 'NOPQRSTUVWXYZ', '0123456789 -./:&'], seed=3)
    s.save('specimen-mask.png')
    rgb = Image.new('RGB', s.size, (238, 235, 222)); ink = Image.new('RGB', s.size, (24, 150, 160)); rgb.paste(ink, (0, 0), s); rgb.save('specimen.png')

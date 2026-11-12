# Render YOJO Batch as an inkjet stamp. Letterforms are fixed; only the ink varies (density, a hair of bleed).
import sys, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from glyphs import G, YOJO
def _draw(rows_list, dot, pitch, seed, ink_var):
    rnd = random.Random(seed)
    W = int(max(len(r[0]) for r in rows_list) * pitch + 2 * pitch); H = int(sum(len(r) + 2 for r in rows_list) * pitch + pitch)
    S = 3; im = Image.new('L', (W * S, H * S), 0); d = ImageDraw.Draw(im); y0 = pitch
    for rows in rows_list:
        for r, row in enumerate(rows):
            for c, v in enumerate(row):
                if v != '#': continue
                cx = pitch + (c + 0.5) * pitch; cy = y0 + (r + 0.5) * pitch; rr = dot / 2
                a = int(255 * (1 - ink_var * rnd.random()))
                d.ellipse([(cx - rr) * S, (cy - rr) * S, (cx + rr) * S, (cy + rr) * S], fill=a)
        y0 += (len(rows) + 2) * pitch
    im = im.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.5))
    a = np.asarray(im, np.float32) / 255
    grain = np.asarray(Image.effect_noise((W, H), 40).filter(ImageFilter.GaussianBlur(0.7)), np.float32) / 255
    a = np.clip(a * (0.86 + 0.28 * grain), 0, 1)
    return Image.fromarray((a * 255).astype(np.uint8))
def text_rows(line, track=1):
    rows = ['' for _ in range(7)]
    for i, ch in enumerate(line.upper()):
        g = G.get(ch, G[' '])
        for r in range(7): rows[r] += g[r] + ('.' * track if i < len(line) - 1 else '')
    return rows
def stamp(lines, dot=9.5, pitch=12, seed=1, ink_var=0.18, yojo=False):
    blocks = ([YOJO] if yojo else []) + [text_rows(l) for l in lines]
    return _draw(blocks, dot, pitch, seed, ink_var)
if __name__ == '__main__':
    s = stamp(['GHK-CU', 'BATCH 0001', '2026.11.12', 'ABCDEFGHIJKLM', 'NOPQRSTUVWXYZ', '0123456789 -./:&'], seed=3, yojo=True)
    s.save('specimen-mask.png')
    rgb = Image.new('RGB', s.size, (238, 235, 222)); rgb.paste(Image.new('RGB', s.size, (22, 143, 224)), (0, 0), s); rgb.save('specimen.png')
    # before / after for the same line
    old = Image.open('specimen_v1.png') if os.path.exists('specimen_v1.png') else None

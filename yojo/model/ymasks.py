# YOJO's own carving: a knurl made of tiny Y's, and a head top with the official Y raised on a cut field.
import math, numpy as np
from PIL import Image, ImageFilter
Y = Image.open('head-mask.png').convert('L')
bb = Y.getbbox(); glyph = Y.crop(bb)                       # the official Y, tight crop
def yknurl(W, H, px_mm, gh_mm, cols, rows, out):
    im = Image.new('L', (W, H), 0)
    gh = int(gh_mm * px_mm); gw = int(gh * glyph.width / glyph.height)
    g = glyph.resize((gw, gh), Image.LANCZOS)
    pitch_x = W / cols; pitch_y = H / rows
    for r in range(rows):
        for c in range(cols + 1):
            x = (c + 0.5 * (r % 2)) * pitch_x; y = (r + 0.5) * pitch_y
            im.paste(255, (int(x - gw / 2), int(y - gh / 2)), g)
            if x + gw / 2 > W: im.paste(255, (int(x - gw / 2 - W), int(y - gh / 2)), g)   # wrap seam
    im.filter(ImageFilter.GaussianBlur(0.6)).save(out)
yknurl(int(113.1 * 40), int(7.8 * 40), 40, 1.45, 58, 4, 'head-yknurl.png')
PX, C = 40, 800
yy, xx = np.mgrid[0:1600, 0:1600]; r = np.hypot(xx - C, yy - C) / PX
top = np.asarray(Y, np.float32) / 255
top = np.maximum(top, ((r > 16.9)).astype(np.float32))                 # outer rim proud
top = np.maximum(top, ((r > 15.3) & (r < 15.7)).astype(np.float32))   # one thin ring
Image.fromarray((top * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)).save('head-top-y.png')
print('ok')

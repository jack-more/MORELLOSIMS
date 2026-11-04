# ZUMA tinted vacuum bag: supplier print files. 100 x 150 mm, 3 mm bleed (106 x 156 mm pages), 600 dpi rasters, vector white plate.
import os, sys, numpy as np
from PIL import Image
V = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad/vac'
OUT = sys.argv[1]; os.makedirs(OUT + '/print', exist_ok=True)
DPI = 600; MM = DPI / 25.4; W, H = round(106 * MM), round(156 * MM); B = round(3 * MM)
art = Image.open(V + '/ca-big-hi.png').convert('RGBA')                  # the Snow artwork, 1400 x 2100 = 100 x 150 mm trim
a = np.array(art.resize((W - 2 * B, H - 2 * B), Image.LANCZOS))[..., 3].astype(float) / 255
ko = np.zeros((H, W)); ko[B:H - B, B:W - B] = a                       # white-ink area on the page, for the knockout
FIELD = {'red': 'lbclean.png', 'blue': 'lb-metabolic.png', 'grey': 'lb-supplies.png'}
def save_pdf(im, path):
    im.save(path, 'PDF', resolution=DPI)
for n, f in FIELD.items():
    lb = np.array(Image.open(V + '/' + f).convert('RGB').resize((W, H), Image.LANCZOS)).astype(float)
    col = lb * (1 - ko[..., None]) + 255 * ko[..., None]               # the colour plate, knocked out under the white type (white = no ink)
    save_pdf(Image.fromarray(col.astype('uint8')), f'{OUT}/print/front-{n}-1-colour-transparent-ink.pdf')
    # the proof: how the front reads over the back (the type in white on top)
    prf = lb * (1 - ko[..., None]) + np.array([252, 251, 248]) * ko[..., None]
    Image.fromarray(prf.astype('uint8')).resize((W // 4, H // 4), Image.LANCZOS).save(f'{OUT}/print/front-{n}-proof.jpg', quality=90)
# the white plate is the same for all three fronts: black = white ink
wp = (255 * (1 - ko)).astype('uint8'); save_pdf(Image.fromarray(wp).convert('L'), f'{OUT}/print/front-all-2-white-ink.pdf')
# the back: opaque white flood over the whole panel, the palm shadow printed in grey (K) on it
sh = np.array(Image.open(V + '/back-shadow.png').convert('L').resize((W, H), Image.LANCZOS)).astype(float) / 255
k = np.clip((sh.max() - sh) / (sh.max() - sh.min()), 0, 1) * 0.72     # shadow density, 0..72% K
save_pdf(Image.fromarray((255 * (1 - k)).astype('uint8')).convert('L'), f'{OUT}/print/back-all-shadow-grey-K-on-white.pdf')
Image.fromarray((255 * (1 - k)).astype('uint8')).resize((W // 4, H // 4)).save(f'{OUT}/print/back-proof.jpg', quality=90)
print('ok', W, H)

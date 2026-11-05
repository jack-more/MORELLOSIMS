# Tomato Study mailer previews: green flood (shadow as deeper green) and cream film (shadow as a green tint); palm back, bamboo front.
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
S = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'; G = lambda f: np.array(Image.open(f).convert('L')).astype(float) / 255
palm = 1 - np.clip(G(S + '/vac/backmax-raw.png') / np.maximum(G(S + '/vac/backtiles-raw.png'), 1e-3), 0, 1); palm /= palm.max(); palm = np.clip((palm - 0.07) / 0.93, 0, 1)
bam = 1 - G(S + '/vac/bamboo-shadow.png'); bam /= bam.max(); bam = np.clip((bam - 0.09) / 0.91, 0, 1)
W, H = Image.open(S + '/tom/green-type.png').size; fw = W // 2; PXMM = fw / 152.4
def fit(a, w, h, fx, fy):
    im = Image.fromarray((a * 255).astype('uint8')); r = max(w / im.width, h / im.height); im = im.resize((round(im.width * r) + 1, round(im.height * r) + 1), Image.LANCZOS)
    x0, y0 = int((im.width - w) * fx), int((im.height - h) * fy); return np.array(im.crop((x0, y0, x0 + w, y0 + h))).astype(float) / 255
def bamboo_face():
    strip = bam[:, 640:1000]; w = round(strip.shape[1] * H / strip.shape[0] * 0.6)
    st = np.array(Image.fromarray((strip * 255).astype('uint8')).resize((w, H), Image.LANCZOS)).astype(float) / 255; out = np.zeros((H, fw)); stalk = round(290 / 360 * w)
    def put(a, x0):
        xs, xe = max(x0, 0), min(x0 + a.shape[1], fw); out[:, xs:xe] = np.maximum(out[:, xs:xe], a[:, xs - x0:xe - x0])
    put(st, fw - round(5 * PXMM) - stalk); put(st[::-1, ::-1], round(5 * PXMM) - (w - stalk)); return out
sh = [fit(palm, fw, H, 0.6, 0.3) ** 1.1, bamboo_face() ** 1.1]
GR = np.array([0x0E, 0x9A, 0x5B], float); GD = np.array([0x06, 0x5C, 0x36], float); CR = np.array([0xFB, 0xFA, 0xF6], float)
f = ImageFont.truetype(S + '/font/Outfit-600.ttf', 28); sm = lambda im: im.resize((im.width * 820 // im.height, 820), Image.LANCZOS)
tiles = []
for tag in ('green', 'cream'):
    T = Image.open(f'{S}/tom/{tag}-type.png').convert('RGBA'); a = np.array(T)[..., 3].astype(float) / 255
    for k, side in ((0, 'back, palm'), (1, 'front, bamboo')):
        ko = np.array(Image.fromarray((a[:, k * fw:(k + 1) * fw] * 255).astype('uint8')).filter(ImageFilter.MaxFilter(13)).filter(ImageFilter.GaussianBlur(6))).astype(float) / 255
        s = sh[k] * (1 - ko)
        base = GR * (1 - s[..., None] * 0.55) + GD * (s[..., None] * 0.55) if tag == 'green' else CR * (1 - s[..., None] * 0.30) + GR * (s[..., None] * 0.30)
        im = Image.fromarray(base.astype('uint8')).convert('RGBA'); im.alpha_composite(T.crop((k * fw, 0, (k + 1) * fw, H)))
        im.convert('RGB').save(f'{S}/tom/{tag}-{k}.png'); tiles.append((sm(im.convert('RGB')), f'{tag.capitalize()}: {side}'))
out = Image.new('RGB', (sum(c.width for c, _ in tiles) + 30 * 5 + 40, 920), '#E7E3DC'); d = ImageDraw.Draw(out); x = 30
for i, (c, n) in enumerate(tiles):
    if i == 2: x += 40
    out.paste(c, (x, 70)); d.text((x, 22), n, fill='#16181C', font=f); x += c.width + 30
out.save(S + '/tom/tomato-mailers.jpg', quality=90); print('ok')

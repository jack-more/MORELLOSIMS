# Mailer B: white film, one Oxblood ink. Flap side: the palm shadow; label side: bamboo. Shadows as an AM dot screen (~65 lpi), up to 28%.
import numpy as np
from PIL import Image, ImageDraw, ImageFont
S = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'
T = Image.open(S + '/mailer/B-type.png').convert('RGBA'); W, H = T.size; fw = W // 2
G = lambda f: np.array(Image.open(f).convert('L')).astype(float) / 255
palm = np.clip(G(S + '/vac/backmax-raw.png') / np.maximum(G(S + '/vac/backtiles-raw.png'), 1e-3), 0, 1)
bamboo = G(S + '/vac/bamboo-shadow.png')
def crop(sh, w, h, fx, fy):
    im = Image.fromarray((sh * 255).astype('uint8')); r = max(w / im.width, h / im.height); im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1))
    x0 = int((im.width - w) * fx); y0 = int((im.height - h) * fy); return np.array(im.crop((x0, y0, x0 + w, y0 + h))).astype(float) / 255
def halftone(dens, cell=4.7, ang=45):
    h, w = dens.shape; yy, xx = np.mgrid[0:h, 0:w].astype(float); t = np.radians(ang)
    u = (xx * np.cos(t) + yy * np.sin(t)) / cell; v = (-xx * np.sin(t) + yy * np.cos(t)) / cell
    return (np.hypot(u - np.round(u), v - np.round(v)) < np.sqrt(np.clip(dens, 0, 1) / np.pi)).astype(float)
OX = np.array([0x6E, 0x1C, 0x2A], float); PAPER = np.array([250, 250, 248], float)
faces = []
for sh, fx, fy in ((palm, 0.6, 0.3), (bamboo, 0.5, 0.4)):
    a = 1 - crop(sh, fw, H, fx, fy); a = np.clip(a / a.max(), 0, 1) ** 1.1 * 0.28
    d = halftone(a); faces.append(PAPER * (1 - d[..., None]) + OX * d[..., None])
img = Image.fromarray(np.concatenate(faces, 1).astype('uint8')).convert('RGBA'); img.alpha_composite(T); img.convert('RGB').save(S + '/mailer/B-print.png')
f = ImageFont.truetype(S + '/font/Outfit-600.ttf', 26); sm = lambda im: im.resize((im.width * 900 // im.height, 900))
z = img.crop((fw + 120, 330, fw + 620, 830)).convert('RGB')
rgb = img.convert('RGB'); sp = Image.new('RGB', (W + 60, H), '#E7E3DC'); sp.paste(rgb.crop((0, 0, fw, H)), (0, 0)); sp.paste(rgb.crop((fw, 0, W, H)), (fw + 60, 0)); a1 = sm(sp)
board = Image.new('RGB', (a1.width + 560, 990), '#E7E3DC'); board.paste(a1, (20, 60)); board.paste(z, (a1.width + 40, 60)); dr = ImageDraw.Draw(board)
dr.text((20, 16), 'Flap side: palm shadow', fill='#6E1C2A', font=f); dr.text((20 + a1.width // 2 + 10, 16), 'Label side: bamboo shadow', fill='#6E1C2A', font=f)
dr.text((a1.width + 40, 16), 'Close-up, enlarged', fill='#6E1C2A', font=f); board.save(S + '/mailer/B-board2.jpg', quality=90); print('ok')

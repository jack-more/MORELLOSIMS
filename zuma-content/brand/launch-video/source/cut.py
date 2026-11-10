# ZUMA launch cut, built only from our own assets. No stock, no AI footage.
# 128 BPM, cuts on the beat and on the half and quarter beat. 9:16, 1080 x 1920, 30 fps.
# usage: python cut.py <workdir with lb-*.png> <out.mp4>
import math, os, random, subprocess, sys, io, re, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import cairosvg

WD, OUT = sys.argv[1], sys.argv[2]
SP = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'
IMG = '/home/user/zuma/site/assets/img/'
MC = '/home/user/MORELLOSIMS/zuma-content/'
W, H, FPS, BPM = 1080, 1920, 30, 128
B = 60 / BPM                                   # one beat, seconds
SNOW, INK, OX, BLUE = (252, 251, 248), (22, 24, 28), (110, 28, 42), (30, 116, 168)
F9 = lambda s: ImageFont.truetype(SP + '/font/Outfit-900.ttf', s)
F6 = lambda s: ImageFont.truetype(SP + '/font/Outfit-600.ttf', s)
random.seed(7)

# ---------- assets ----------
cache = {}
def load(path, bg=None):
    if path not in cache:
        im = Image.open(path).convert('RGBA')
        if bg: b = Image.new('RGBA', im.size, bg); b.alpha_composite(im); im = b
        cache[path] = im.convert('RGB') if bg or im.getextrema()[3][0] == 255 else im
    return cache[path]
def svg(path, width, colour):
    s = open(path).read(); s = re.sub(r'<svg[^>]*?viewBox', '<svg xmlns="http://www.w3.org/2000/svg" viewBox', s, count=1)
    hexc = '#%02x%02x%02x' % colour; s = s.replace('currentColor', hexc); s = re.sub(r'fill="#[0-9A-Fa-f]{3,6}"', f'fill="{hexc}"', s)
    return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=s.encode(), output_width=width))).convert('RGBA')
AREAS = ['metabolic', 'tissue', 'dermal', 'endocrine', 'neuro', 'oxblood']
LB = {a: f'{WD}/lb-{a}.png' for a in AREAS}
VIALS = [IMG + f'vial-{n:02d}.webp' for n in range(1, 13)]
HEROV = [IMG + f'hero-vial-{n:02d}.webp' for n in (1, 2, 5, 6, 9, 11)]
SPIN = lambda n: [IMG + f'spin/{n:02d}-{k:02d}.webp' for k in (20, 21, 22, 23, 0, 1, 2, 3, 4)]   # the label's front arc only
LABELS = [MC + f'packaging/print-pack-vial-labels/art/zuma-label-{n:02d}-art.png' for n in (1, 5, 11, 9, 2, 6, 10, 12)]
BAGS = [MC + 'packaging/vacuum-bag/tinted/split-red-blue-grey-two-vials.jpg', MC + 'packaging/vacuum-bag/tinted/two-vials-100x150.jpg',
        MC + 'packaging/vacuum-bag/tinted/rail-shot-two-skus.jpg']
MAILER = MC + 'packaging/mailer-factory-B/mailer-proof.jpg'
STICK = [MC + 'stickers/round-logo-tomato/round-logo-lightbox-set.jpg', MC + 'stickers/round-compound/round-compound-stickers.jpg']
LINEUP = IMG + 'lineup-2400.webp'
CREST = svg(MC + 'packaging/capsule-case/zuma-crest-stamp.svg', 420, SNOW)
WORD = svg('/home/user/zuma/source/src/partials/wordmark.svg', 640, SNOW)

# ---------- frame helpers ----------
def cover(im, zoom=1.0, cx=0.5, cy=0.5, w=W, h=H):
    """fill w x h from im, zoomed, centred on (cx, cy)"""
    s = max(w / im.width, h / im.height) * zoom; nw, nh = int(im.width * s + 1), int(im.height * s + 1)
    r = im.resize((nw, nh), Image.BILINEAR)
    x = int(min(max(cx * nw - w / 2, 0), nw - w)); y = int(min(max(cy * nh - h / 2, 0), nh - h))
    return r.crop((x, y, x + w, y + h)).convert('RGB')
def contain(im, w, h, bg, zoom=1.0):
    s = min(w / im.width, h / im.height) * zoom; r = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    c = Image.new('RGB', (w, h), bg); c.paste(r, ((w - r.width) // 2, (h - r.height) // 2), r if r.mode == 'RGBA' else None); return c
def punch(p): return 1.0 + 0.10 * (1 - p) ** 3          # zoom punch at a cut, easing out over the shot
def ease(p): return 1 - (1 - p) ** 3
def shake(im, amt):
    if amt <= 0: return im
    dx, dy = random.randint(-amt, amt), random.randint(-amt, amt)
    c = Image.new('RGB', im.size, (0, 0, 0)); c.paste(im, (dx, dy)); return c
def grid(paths, cols, rows, gap=6, bg=(0, 0, 0)):
    c = Image.new('RGB', (W, H), bg); cw, ch = (W - gap * (cols + 1)) // cols, (H - gap * (rows + 1)) // rows
    for i, p in enumerate(paths[:cols * rows]):
        c.paste(cover(load(p), 1.0, 0.5, 0.55, cw, ch), (gap + (i % cols) * (cw + gap), gap + (i // cols) * (ch + gap)))
    return c

def pill(base, text, yf=0.5, size=68):
    if not text: return base
    im = base.convert('RGBA'); f = F6(size); d = ImageDraw.Draw(im)
    tw = d.textlength(text, font=f); a, ds = f.getmetrics(); px, py = 36, 22
    w, h = int(tw + 2 * px), int(a + ds + 2 * py - 8); x0, y0 = (W - w) // 2, int(H * yf) - h // 2
    sh = Image.new('RGBA', im.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle([x0, y0 + 8, x0 + w, y0 + h + 8], 24, fill=(0, 0, 0, 80))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)))
    d = ImageDraw.Draw(im); d.rounded_rectangle([x0, y0, x0 + w, y0 + h], 24, fill=(255, 255, 255, 245)); d.text((x0 + px, y0 + py - 6), text, font=f, fill=INK)
    return im.convert('RGB')
def bigword(text, bg, fg, size=330, scale=1.0, img=None):
    c = img.copy() if img is not None else Image.new('RGB', (W, H), bg); f = F9(int(size * scale)); d = ImageDraw.Draw(c)
    bb = d.textbbox((0, 0), text, font=f); tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((W - tw) / 2 - bb[0], (H - th) / 2 - bb[1]), text, font=f, fill=fg); return c

# ---------- the edit: a list of shots (start beat, length in beats, render(p, t) -> frame) ----------
SHOTS = []
def shot(beats, fn): SHOTS.append((beats, fn))
CAPS = []   # (start beat, end beat, line) typed a word per step
def cap(b0, b1, line, yf=0.5, step=0.5): CAPS.append((b0, b1, line, yf, step))

# A. 0-8: the Lightbox, every half beat, cycling the research areas, pushing in
for i in range(16):
    a = AREAS[i % 6]
    shot(0.5, lambda p, t, a=a, i=i: cover(load(LB[a]), punch(p) * (1.15 if i % 2 else 1.0), 0.5, 0.5))
cap(0, 8, "It's a new era", 0.5, 1.0)

# B. 8-12: the vials, every half beat; 12-14: 2 x 2 grid; 14-16: all twelve
for i in range(8):
    shot(0.5, lambda p, t, i=i: cover(load(VIALS[(i * 5) % 12]), punch(p) * 1.25, 0.5, 0.62))
shot(2, lambda p, t: grid([VIALS[k] for k in (0, 4, 10, 8)], 2, 2, 8, OX))
shot(2, lambda p, t: grid(VIALS, 3, 4, 6, OX))
cap(8, 16, 'of research.', 0.5, 1.0)

LBLUR = [cover(load(LABELS[k]), 1.6, 0.5, 0.5).filter(ImageFilter.GaussianBlur(28)) for k in range(3)]
# C. 16-19: the big words on the Rev 4 label art, one word per beat, with a slam
for k, wd in enumerate(['Tested', 'by', 'lot.']):
    shot(1, lambda p, t, k=k, wd=wd: shake(bigword(wd, OX, SNOW, 250, 1.0 + 0.15 * (1 - ease(min(p * 3, 1))),
                                                    img=Image.blend(cover(LBLUR[k], 1.0 + 0.08 * p, 0.5, 0.5), Image.new('RGB', (W, H), OX), 0.86)), int(18 * (1 - p))))
shot(1, lambda p, t: bigword('lot.', OX, SNOW, 250))

# D. 20-28: label art, quarter-beat cuts sliding across the Rev 4 labels
for i in range(16):
    lab = LABELS[i % len(LABELS)]
    shot(0.5, lambda p, t, lab=lab, i=i: cover(load(lab), 2.2 + 0.2 * p, (0.2 + 0.6 * ((i * 0.37) % 1)) + 0.08 * p, 0.45))
cap(20, 28, 'Every lot. Every report.', 0.78, 0.5)

# E. 28-32: the turntable at speed, then a split of two spinning vials
for k in range(8):
    fr = SPIN(1)
    shot(0.25, lambda p, t, k=k, fr=fr: cover(load(fr[k % len(fr)]), 1.35, 0.5, 0.55))
def split(p, t):
    c = Image.new('RGB', (W, H)); f1, f2 = SPIN(5), SPIN(11); k = int(p * 16) % len(f1)
    c.paste(cover(load(f1[k]), 1.3, 0.5, 0.55, W, H // 2), (0, 0)); c.paste(cover(load(f2[-1 - k]), 1.3, 0.5, 0.55, W, H // 2), (0, H // 2)); return c
shot(2, split)

# F. 32-36: the vacuum bag
for i in range(4):
    bg_ = BAGS[i % 3]
    shot(1, lambda p, t, bg_=bg_, i=i: cover(load(bg_), (1.2 if i % 2 else 1.6) + 0.15 * p, 0.35 + 0.3 * (i % 2), 0.5))
cap(32, 36, 'Vacuum packed.', 0.18, 1.0)

# G. 36-38: mailer and stickers, half-beat
for i in range(4):
    src = [MAILER, STICK[0], MAILER, STICK[1]][i]
    shot(0.5, lambda p, t, src=src, i=i: cover(load(src), 1.4 + 0.2 * p, 0.3 + 0.4 * (i % 2), 0.5))
cap(36, 38, 'Sealed. Shipped.', 0.18, 1.0)

# H. 38-42: build: everything on sixteenth notes, flashing
POOL = [LB[a] for a in AREAS] + VIALS[:6] + [LABELS[0], LABELS[2], BAGS[0], LINEUP]
for i in range(16):
    src = POOL[(i * 7) % len(POOL)]
    shot(0.25, lambda p, t, src=src, i=i: cover(load(src), 1.3 + 0.1 * (i % 3), 0.5, 0.5))

# I. 42-44: the drop: "here" / "now." on Oxblood and blue, slammed
shot(1, lambda p, t: shake(bigword('here', OX, SNOW, 330, 1.0 + 0.3 * (1 - ease(min(p * 4, 1)))), int(26 * (1 - p))))
shot(1, lambda p, t: shake(bigword('now.', BLUE, SNOW, 330, 1.0 + 0.3 * (1 - ease(min(p * 4, 1)))), int(26 * (1 - p))))

# J. 44-48: the crest turning with zumatides.com orbiting it on the blue Lightbox
def orbit(p, t):
    base = Image.blend(cover(load(LB['metabolic']), 1.05 + 0.05 * p), Image.new('RGB', (W, H), BLUE), 0.45).convert('RGBA')
    sc = 0.85 + 0.15 * ease(min(p * 2, 1)); cw = int(CREST.width * sc)
    cr = CREST.resize((cw, int(CREST.height * sc)), Image.LANCZOS).rotate(-ease(min(p * 1.6, 1)) * 360, resample=Image.BICUBIC, expand=True)
    base.alpha_composite(cr, ((W - cr.width) // 2, (H - cr.height) // 2 - 120)); return base.convert('RGB')
cap(44, 48, 'zumatides.com', 0.66, 0.25)
shot(4, orbit)

# K. 48-54: end card: ZUMA, zumatides.com, the research-use line
def end(p, t):
    c = Image.new('RGBA', (W, H), BLUE); c.alpha_composite(CREST.resize((260, int(260 * CREST.height / CREST.width))), ((W - 260) // 2, 540))
    c.alpha_composite(WORD, ((W - WORD.width) // 2, 900)); d = ImageDraw.Draw(c); f = F6(48); s = 'zumatides.com'
    d.text(((W - d.textlength(s, font=f)) / 2, 1120), s, font=f, fill=SNOW)
    d.rectangle([0, H - 200, W, H], fill=OX); f3 = ImageFont.truetype(SP + '/font/Outfit-500.ttf', 30)
    for i, s in enumerate(['For laboratory research use only.', 'Not for human or veterinary use.']):
        d.text(((W - d.textlength(s, font=f3)) / 2, H - 150 + i * 44), s, font=f3, fill=SNOW)
    return c.convert('RGB')
shot(6, end)

TOTAL = sum(b for b, _ in SHOTS)

# ---------- the music: 128 BPM, synthesised here (kick, clap, hats, sub bass, riser, impact) ----------
SR = 44100; N = int((TOTAL * B + 0.5) * SR); mix = np.zeros(N)
tt = lambda d: np.arange(int(d * SR)) / SR
def put(sig, at, g=1.0):
    i = int(at * SR); j = min(N, i + len(sig)); mix[i:j] += g * sig[:j - i]
def kick():
    t = tt(0.42); f = 48 + 110 * np.exp(-t * 28); ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 7.5) + 0.25 * np.sin(ph * 2) * np.exp(-t * 30)
def noise(d, decay, hp=True):
    n = np.random.default_rng(1).standard_normal(int(d * SR))
    if hp: n = np.diff(np.concatenate([[0], n]))
    return n * np.exp(-tt(d) * decay)
def clap(): return 0.5 * noise(0.25, 18) + 0.3 * np.concatenate([noise(0.02, 80), np.zeros(int(0.25 * SR) - int(0.02 * SR))])
def hat(): return 0.22 * noise(0.06, 70)
def bass(freq, d):
    t = tt(d); s = np.tanh(2.2 * np.sin(2 * np.pi * freq * t)) * np.minimum(1, t * 60) * np.exp(-t * 2.2); return s
K, C, HH = kick(), clap(), hat()
roots = [41.2, 41.2, 49.0, 36.7]                      # E1 E1 G1 D1, one bar each
for bt in range(int(TOTAL)):
    at = bt * B; sec = 'end' if bt >= 48 else 'drop' if 42 <= bt < 48 else 'build' if 38 <= bt < 42 else 'main'
    if sec == 'end':
        if bt == 48: put(K, at, 0.9)
        continue
    if bt >= 8 or bt % 2 == 0: put(K, at, 1.0)
    if bt >= 8 and bt % 2 == 1: put(C, at, 0.55)
    if bt >= 4:
        for q in range(2 if sec != 'build' else 4): put(HH, at + q * B / (2 if sec != 'build' else 4), 0.8 if q % 2 else 0.5)
    if bt >= 8 and sec != 'build':
        put(bass(roots[(bt // 4) % 4], B * 0.9), at + B * 0.5, 0.42)
    if sec == 'build': put(K, at + B / 2, 0.7)
# riser into the drop, and an impact on it
t = tt(4 * B); put(0.18 * noise(4 * B, 0, False) * (t / t[-1]) ** 2 * np.sin(2 * np.pi * (200 + 1400 * (t / t[-1]) ** 2) * t / 3), 38 * B)
put(1.2 * kick(), 42 * B); put(0.5 * noise(1.6, 2.5, False), 42 * B, 0.35)
# a soft pad under the end
t = tt(10 * B); pad = sum(np.sin(2 * np.pi * f * t) for f in (164.8, 196.0, 246.9)) / 3 * np.minimum(1, t * 2) * np.exp(-t * 0.35)
put(0.22 * pad, 44 * B)
mix = np.tanh(mix * 0.9); mix /= np.max(np.abs(mix)) * 1.12
with wave.open(f'{WD}/music.wav', 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype('<i2').tobytes())

# ---------- render ----------
def capt_at(beat):
    for b0, b1, line, yf, step in CAPS:
        if b0 <= beat < b1:
            if ' ' not in line: k = min(len(line), int((beat - b0) / (step / 4)) + 1); return line[:k], yf   # one word: type it letter by letter
            words = line.split(' '); k = min(len(words), int((beat - b0) / step) + 1); return ' '.join(words[:k]), yf
    return None, 0.5
p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                      '-i', f'{WD}/music.wav', '-c:v', 'libx264', '-crf', '17', '-preset', 'medium', '-pix_fmt', 'yuv420p',
                      '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', OUT], stdin=subprocess.PIPE)
nframes = int(round(TOTAL * B * FPS)); bstart = 0; idx = 0; starts = []
for b, _ in SHOTS: starts.append(bstart); bstart += b
for fi in range(nframes):
    beat = fi / FPS / B
    while idx + 1 < len(SHOTS) and beat >= starts[idx + 1]: idx += 1
    b, fn = SHOTS[idx]; pr = min(max((beat - starts[idx]) / b, 0), 0.999)
    fr = fn(pr, fi / FPS)
    txt, yf = capt_at(beat)
    if txt: fr = pill(fr, txt, yf)
    if fi > 0 and abs(beat - starts[idx]) < 1 / FPS / B and idx in (16, 28, 54, 70):   # a one-frame white flash on the big section changes
        fr = Image.blend(fr, Image.new('RGB', (W, H), (255, 255, 255)), 0.85)
    p.stdin.write(fr.tobytes())
p.stdin.close(); p.wait()
print('done', OUT, round(TOTAL * B, 2), 's', len(SHOTS), 'shots')

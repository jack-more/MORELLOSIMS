# ZUMA bubble mailer B: white film, ONE spot ink (ZUMA Oxblood). Face A (flap side): palm shadow. Face B (label side): bamboo at both edges.
# Writes spot-colour vector PDFs (+ .ai copies): type and logos as outlines, shadows as a tint image in the same spot ink (the printer screens it).
import json, io, math, sys, zlib, numpy as np
from PIL import Image, ImageFilter
sys.path.insert(0, '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad/lv')
from pdfw import PDFPen, svgpath, mm
from fontTools.ttLib import TTFont
S = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'; OUT = sys.argv[1]
L = json.load(open(S + '/mailer/layout.json'))
FW, FH, BL = 152.4, 254.0, 3.0; SX, SY = FW / 610, FH / 1016; MAXT = 0.28
F = {w: TTFont(f'{S}/font/Outfit-{w}.ttf') for w in (500, 600, 700, 800)}; GS = {w: f.getGlyphSet() for w, f in F.items()}
def glyph(ch, w):
    w = min(F, key=lambda k: abs(k - w)); p = PDFPen(GS[w]); GS[w][F[w].getBestCmap()[ord(ch)]].draw(p); return ' '.join(p.o)
M = lambda a: ' '.join(f'{v:.6f}' for v in a) + ' cm'
def rot(i):
    if i < 0: return ''
    r = L['rots'][i]; t = math.radians(r['a']); c, s = math.cos(t), math.sin(t); cx, cy = r['cx'], r['cy']
    return M([c, s, -s, c, cx - cx * c + cy * s, cy - cx * s - cy * c])
def face_of(x, r): return (L['rots'][r]['cx'] if r >= 0 else x) >= 610
def vector(face):
    dx = 610 if face else 0; o = ['/CS0 cs 1 scn', 'q ' + M([1, 0, 0, 1, BL, BL]) + ' ' + M([SX, 0, 0, SY, 0, 0]) + ' ' + M([1, 0, 0, 1, -dx, 0])]
    for g in L['glyphs']:
        if face_of(g['x'], g['rot']) != face: continue
        s = g['size'] / 1000; o.append(f'q {rot(g["rot"])} {M([s, 0, 0, -s, g["x"], g["top"] + g["size"]])} {glyph(g["ch"], g["w"])} f Q')
    for v in L['svgs']:
        if face_of(v['x'] + v['w'] / 2, v['rot']) != face: continue
        vx, vy, vw, vh = v['vb']; sx, sy = v['w'] / vw, v['h'] / vh
        o.append(f'q {rot(v["rot"])} {M([sx, 0, 0, sy, v["x"] - vx * sx, v["y"] - vy * sy])} {svgpath(v["d"])} ' + ('f*' if v['rule'] == 'evenodd' else 'f') + ' Q')
    o.append('Q')
    if face:   # the 4 x 6 in label area: a 0.3 mm outline, 1.5 mm corners
        x, y, w, h, r = BL + 102 * SX, BL + 240 * SY, 101.6, 152.4, 1.5; k = 0.5523 * r
        o.append(f'/CS0 CS 1 SCN 0.3 w {x + r} {y} m {x + w - r} {y} l {x + w - r + k} {y} {x + w} {y + r - k} {x + w} {y + r} c {x + w} {y + h - r} l '
                 f'{x + w} {y + h - r + k} {x + w - r + k} {y + h} {x + w - r} {y + h} c {x + r} {y + h} l {x + r - k} {y + h} {x} {y + h - r + k} {x} {y + h - r} c '
                 f'{x} {y + r} l {x} {y + r - k} {x + r - k} {y} {x + r} {y} c h S')
    return '\n'.join(o)
# ---- shadow fields, 400 dpi over the whole page (bleed included)
DPI = 400; PX = DPI / 25.4; PW, PH = round((FW + 2 * BL) * PX), round((FH + 2 * BL) * PX)
G = lambda f: np.array(Image.open(f).convert('L')).astype(float) / 255
palm = 1 - np.clip(G(S + '/vac/backmax-raw.png') / np.maximum(G(S + '/vac/backtiles-raw.png'), 1e-3), 0, 1); palm /= palm.max(); palm = np.clip((palm - 0.07) / 0.93, 0, 1)
bam = 1 - G(S + '/vac/bamboo-shadow.png'); bam /= bam.max(); bam = np.clip((bam - 0.09) / 0.91, 0, 1)   # drop the faint tile haze left by the shadow extraction
def fit(a, w, h, fx, fy):
    im = Image.fromarray((a * 255).astype('uint8')); r = max(w / im.width, h / im.height); im = im.resize((round(im.width * r) + 1, round(im.height * r) + 1), Image.LANCZOS)
    x0, y0 = int((im.width - w) * fx), int((im.height - h) * fy); return np.array(im.crop((x0, y0, x0 + w, y0 + h))).astype(float) / 255
def face_a():
    return fit(palm, PW, PH, 0.6, 0.3) ** 1.1
def face_b():   # one bamboo stalk with its leaves down each edge, leaves reaching in toward the label area but stopping short of it
    strip = bam[:, 640:1000]; h = PH; sc = h / strip.shape[0]; w = round(strip.shape[1] * sc * 0.6)
    st = np.array(Image.fromarray((strip * 255).astype('uint8')).resize((w, h), Image.LANCZOS)).astype(float) / 255   # the stalk is at its right edge
    out = np.zeros((PH, PW)); stalk = round((930 - 640) / 360 * w)
    def put(a, x0):
        x1 = x0 + a.shape[1]; xs, xe = max(x0, 0), min(x1, PW); out[:, xs:xe] = np.maximum(out[:, xs:xe], a[:, xs - x0:xe - x0])
    put(st, round((BL + FW - 5) * PX) - stalk)                                    # right edge: stalk 5 mm in from the trim, leaves pointing in
    left = st[::-1, ::-1]; put(left, round((BL + 5) * PX) - (w - stalk))     # left edge: mirrored and turned, so the two sides differ
    return out ** 1.1
def knock(tint, face):   # keep the shadow 2 mm clear of every letter, logo and the label outline
    t = Image.open(S + '/mailer/B-type.png').split()[-1]; fw = t.width // 2; t = t.crop((fw if face else 0, 0, (fw if face else 0) + fw, t.height))
    t = t.resize((610, 1016)).point(lambda v: 255 if v > 20 else 0).filter(ImageFilter.MaxFilter(13)).filter(ImageFilter.GaussianBlur(5))
    m = np.zeros((PH, PW)); b = round(BL * PX); m[b:PH - b, b:PW - b] = np.array(t.resize((PW - 2 * b, PH - 2 * b))).astype(float) / 255
    return tint * (1 - m)
def jpg(a):
    b = io.BytesIO(); Image.fromarray((np.clip(a, 0, 1) * 255).astype('uint8'), 'L').save(b, 'JPEG', quality=94); return b.getvalue()
def write(path, content, img):
    W, H, B = mm(FW + 2 * BL), mm(FH + 2 * BL), mm(BL); objs = []; add = lambda x: objs.append(x) or len(objs)
    fn = add(b'<< /FunctionType 2 /Domain [0 1] /C0 [1 1 1] /C1 [0.4314 0.1098 0.1647] /N 1 >>')
    cs = add(b'[/Separation /ZUMA_Oxblood /DeviceRGB %d 0 R]' % fn)
    im = add(b'<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace %d 0 R /BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n' % (PW, PH, cs, len(img)) + img + b'\nendstream')
    st = zlib.compress(content.encode('latin-1')); c = add(b'<< /Length %d /Filter /FlateDecode >>\nstream\n' % len(st) + st + b'\nendstream')
    pages = len(objs) + 2
    pg = add(f'<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 {W:.3f} {H:.3f}] /TrimBox [{B:.3f} {B:.3f} {W - B:.3f} {H - B:.3f}] /Resources << /ColorSpace << /CS0 {cs} 0 R >> /XObject << /Im0 {im} 0 R >> >> /Contents {c} 0 R >>'.encode())
    add(f'<< /Type /Pages /Kids [{pg} 0 R] /Count 1 >>'.encode()); cat = add(f'<< /Type /Catalog /Pages {pages} 0 R >>'.encode())
    out = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'; offs = []
    for i, o in enumerate(objs, 1): offs.append(len(out)); out += b'%d 0 obj\n' % i + o + b'\nendobj\n'
    x = len(out); out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1) + b''.join(b'%010d 00000 n \n' % o for o in offs)
    out += b'trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, cat, x); open(path, 'wb').write(out)
Gm = f'{mm(1):.8f} 0 0 {-mm(1):.8f} 0 {mm(FH + 2 * BL):.4f} cm'
IMG = f'q {FW + 2 * BL} 0 0 {-(FH + 2 * BL)} 0 {FH + 2 * BL} cm /Im0 Do Q'
for face, name, tint in ((0, 'side-A-flap-palm', face_a()), (1, 'side-B-label-bamboo', face_b())):
    t = knock(tint, face) * MAXT
    write(f'{OUT}/ZUMA-mailer-{name}.pdf', '\n'.join([Gm, IMG, vector(face)]), jpg(t))
    np.save(f'{OUT}/../tint-{face}.npy', t)
print('ok', PW, PH)

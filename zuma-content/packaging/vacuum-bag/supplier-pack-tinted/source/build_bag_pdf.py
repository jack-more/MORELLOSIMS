# Tinted bag vector files written directly (exact 106 x 156 mm page, TrimBox at 100 x 150): colour ink as a JPEG image,
# the white artwork as vector (type as outlines), the die line as thin strokes.
import json, io, math, sys, numpy as np
sys.path.insert(0, '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad/lv')
from pdfw import PDFPen, svgpath, write, mm
from PIL import Image
from fontTools.ttLib import TTFont
S = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'; V = S + '/vac'; OUT = sys.argv[1]
L = json.load(open(S + '/ai/layout.json'))
F = {w: TTFont(f'{S}/font/Outfit-{w}.ttf') for w in (500, 600, 700, 800)}; GS = {w: f.getGlyphSet() for w, f in F.items()}
def glyph(ch, w):
    w = min(F, key=lambda k: abs(k - w)); name = F[w].getBestCmap()[ord(ch)]; p = PDFPen(GS[w]); GS[w][name].draw(p); return ' '.join(p.o)
M = lambda a: ' '.join(f'{v:.6f}' for v in a) + ' cm'
def rot(i):
    if i < 0: return ''
    r = L['rots'][i]; t = math.radians(r['a']); c, s = math.cos(t), math.sin(t); cx, cy = r['cx'], r['cy']
    return M([c, s, -s, c, cx - cx * c + cy * s, cy - cx * s - cy * c])
def white(col):
    out = [f'{col} rg', 'q ' + M([1, 0, 0, 1, 3, 3]) + ' ' + M([100 / 1400, 0, 0, 100 / 1400, 0, 0])]
    for g in L['glyphs']:
        s = g['size'] / 1000; out.append(f'q {rot(g["rot"])} {M([s, 0, 0, -s, g["x"], g["top"] + g["size"]])} {glyph(g["ch"], g["w"])} f Q')
    for v in L['svgs']:
        vx, vy, vw, vh = v['vb']; sx, sy = v['w'] / vw, v['h'] / vh
        out.append(f'q {rot(v["rot"])} {M([sx, 0, 0, sy, v["x"] - vx * sx, v["y"] - vy * sy])} {svgpath(v["d"])} ' + ('f*' if v['rule'] == 'evenodd' else 'f') + ' Q')
    for r in L['rects']: out.append(f'q {rot(r["rot"])} {r["x"]:.3f} {r["y"]:.3f} {r["w"]:.3f} {r["h"]:.3f} re f Q')
    return '\n'.join(out + ['Q'])
DIE = '\n'.join(['q 0 0.6275 0.8784 RG 0.25 w [1 1] 0 d 0 0 106 156 re S Q',                       # bleed (blue dashes)
                 'q 0.902 0 0.4941 RG 0.35 w 3 3 100 150 re S Q',                                    # cut (pink)
                 'q 0 0.6039 0.2667 RG 0.25 w [1.2 0.8] 0 d 8 3 m 8 148 l 98 148 l 98 3 l S 3 8 m 103 8 l S Q',   # seals (green dashes)
                 'q 0.902 0 0.4941 RG 0.35 w 3 20 m 5.2 21.2 l 3 22.4 l S 103 20 m 100.8 21.2 l 103 22.4 l S Q'])  # tear notches
DPI = 600; PX = DPI / 25.4; W, H = round(106 * PX), round(156 * PX); B = round(3 * PX)
a = np.array(Image.open(V + '/ca-big-hi.png').convert('RGBA').resize((W - 2 * B, H - 2 * B), Image.LANCZOS))[..., 3].astype(float) / 255
ko = np.zeros((H, W)); ko[B:H - B, B:W - B] = a
def jpg(arr, mode):
    b = io.BytesIO(); Image.fromarray(arr).convert(mode).save(b, 'JPEG', quality=93, subsampling=0); return b.getvalue()
G = f'{mm(1):.8f} 0 0 {-mm(1):.8f} 0 {mm(156):.4f} cm'                                              # mm, y down
IMG = 'q 106 0 0 -156 0 156 cm /Im0 Do Q'
for n, f in {'red': 'lbclean.png', 'blue': 'lb-metabolic.png', 'grey': 'lb-supplies.png'}.items():
    lb = np.array(Image.open(V + '/' + f).convert('RGB').resize((W, H), Image.LANCZOS)).astype(float)
    col = (lb * (1 - ko[..., None]) + 255 * ko[..., None]).astype('uint8')
    write(f'{OUT}/ZUMA-bag-front-{n}.pdf', 106, 156, 3, '\n'.join([G, IMG, white('1 1 1'), DIE]), {'Im0': (jpg(col, 'RGB'), W, H, 'DeviceRGB')})
write(f'{OUT}/ZUMA-bag-front-white-ink-plate.pdf', 106, 156, 3, '\n'.join([G, '1 1 1 rg 0 0 106 156 re f', white('0 0 0'), DIE]))
sh = np.array(Image.open(V + '/back-shadow.png').convert('L').resize((W, H), Image.LANCZOS)).astype(float) / 255
k = np.clip((sh.max() - sh) / (sh.max() - sh.min()), 0, 1) * 0.72
write(f'{OUT}/ZUMA-bag-back.pdf', 106, 156, 3, '\n'.join([G, '1 1 1 rg 0 0 106 156 re f', IMG, DIE]), {'Im0': (jpg((255 * (1 - k)).astype('uint8'), 'L'), W, H, 'DeviceGray')})
print('ok')

# Round logo sticker (default Tomato Study green; args: out name field-hex art-hex): 2 in (50.8 mm), no border.
# Green flood, the crest and the ZUMA wordmark in cream, zumatides.com round the bottom edge in cream.
# Vector PDF/.ai: every shape as outlines, page = sticker + 1.5 mm bleed, TrimBox = the sticker, die cut as a CutContour spot stroke.
import math, re, sys, zlib
S = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'
sys.path.insert(0, S + '/lv')
from pdfw import PDFPen, svgpath, mm
from fontTools.ttLib import TTFont
OUT = sys.argv[1]
hx = lambda h: ' '.join(f'{int(h[i:i+2],16)/255:.4f}' for i in (1,3,5))
NAME = sys.argv[2] if len(sys.argv) > 2 else 'tomato-green'
D, BL = 50.8, 1.5; PG = D + 2 * BL; C = PG / 2; R = D / 2
GREEN = hx(sys.argv[3]) if len(sys.argv) > 3 else '0.0549 0.6039 0.3569'      # field, default Tomato green #0E9A5B
CREAM = hx(sys.argv[4]) if len(sys.argv) > 4 else '0.9843 0.9804 0.9647'      # art, default cream #FBFAF6
M = lambda a: ' '.join(f'{v:.6f}' for v in a) + ' cm'
f6 = TTFont(S + '/font/Outfit-600.ttf'); gs6 = f6.getGlyphSet(); cmap6 = f6.getBestCmap(); hm6 = f6['hmtx']; GLY6 = {}
CD = re.search(r' d="([^"]+)"', open('/home/user/MORELLOSIMS/zuma-content/packaging/capsule-case/zuma-crest-stamp.svg').read()).group(1)
WD = re.search(r' d="([^"]+)"', open('/home/user/zuma/source/src/partials/wordmark.svg').read()).group(1)

def arc_bottom(s, size, r, track=0.06):
    """letters round the bottom edge, upright, reading left to right"""
    adv = [hm6[cmap6[ord(c)]][0] * size / 1000 + track * size for c in s]; tot = sum(adv) - track * size
    a0 = -tot / (2 * r); x = 0; o = []
    for c, a in zip(s, adv):
        al = a0 + (x + (a - track * size) / 2) / r; x += a
        if c not in GLY6: p = PDFPen(gs6); gs6[cmap6[ord(c)]].draw(p); GLY6[c] = ' '.join(p.o)
        px, py = C + r * math.sin(al), C + r * math.cos(al); w = hm6[cmap6[ord(c)]][0]
        o.append(f'q {M([1, 0, 0, 1, px, py])} {M([math.cos(-al), math.sin(-al), -math.sin(-al), math.cos(-al), 0, 0])} '
                 f'{M([size / 1000, 0, 0, -size / 1000, -w * size / 2000, 0])} {GLY6[c]} f Q')
    return '\n'.join(o)

def circle(r):
    k = 0.5523 * r; c = C
    return (f'{c + r} {c} m {c + r} {c + k} {c + k} {c + r} {c} {c + r} c {c - k} {c + r} {c - r} {c + k} {c - r} {c} c '
            f'{c - r} {c - k} {c - k} {c - r} {c} {c - r} c {c + k} {c - r} {c + r} {c - k} {c + r} {c} c h')

def write(path, content):
    W = mm(PG); B = mm(BL); objs = []; add = lambda x: objs.append(x) or len(objs)
    fn = add(b'<< /FunctionType 2 /Domain [0 1] /C0 [0 0 0 0] /C1 [0 1 0 0] /N 1 >>')
    cs = add(b'[/Separation /CutContour /DeviceCMYK %d 0 R]' % fn)
    st = zlib.compress(content.encode('latin-1')); c = add(b'<< /Length %d /Filter /FlateDecode >>\nstream\n' % len(st) + st + b'\nendstream')
    pages = len(objs) + 2
    pg = add(f'<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 {W:.3f} {W:.3f}] /TrimBox [{B:.3f} {B:.3f} {W - B:.3f} {W - B:.3f}] /Resources << /ColorSpace << /Cut {cs} 0 R >> >> /Contents {c} 0 R >>'.encode())
    add(f'<< /Type /Pages /Kids [{pg} 0 R] /Count 1 >>'.encode()); cat = add(f'<< /Type /Catalog /Pages {pages} 0 R >>'.encode())
    out = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'; offs = []
    for i, o in enumerate(objs, 1): offs.append(len(out)); out += b'%d 0 obj\n' % i + o + b'\nendobj\n'
    x = len(out); out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1) + b''.join(b'%010d 00000 n \n' % o for o in offs)
    out += b'trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, cat, x); open(path, 'wb').write(out)

G = f'{mm(1):.8f} 0 0 {-mm(1):.8f} 0 {mm(PG):.4f} cm'
cw = 17.0; cs = cw / 104.26; ch = 100 * cs                       # crest 17 mm wide
ww = 26.0; ws = ww / 267.52; wh = 64.0 * ws                      # wordmark 26 mm wide
gap = 3.2; top = C - (ch + gap + wh) / 2 - 2.0                   # the pair sits a touch above centre, clear of the address
crest = f'q {M([cs, 0, 0, cs, C - cw / 2, top])} {svgpath(CD)} f* Q'
word = f'q {M([ws, 0, 0, ws, C - ww / 2, top + ch + gap])} {svgpath(WD)} f* Q'
url = arc_bottom('zumatides.com', 3.6, R - 3.4)
body = [G, f'{GREEN} rg 0 0 {PG} {PG} re f', f'{CREAM} rg', crest, word, url, f'/Cut CS 1 SCN 0.25 w {circle(R)} S']
write(OUT + f'/zuma-round-logo-{NAME}-2in.pdf', '\n'.join(body))
print('ok', round(top, 2), round(top + ch + gap + wh, 2))

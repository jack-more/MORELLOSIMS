# Round compound stickers, 16 mm, no border: the compound's research-area Lightbox, the crest in the middle, the name round the top edge.
# Vector PDF/.ai: the Lightbox as a 600 dpi image, the crest and every letter as Oxblood vector outlines, the die cut as a CutContour spot stroke.
import io, json, math, re, sys, zlib
sys.path.insert(0, '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad/lv')
from pdfw import PDFPen, svgpath, mm
from PIL import Image
from fontTools.ttLib import TTFont
S = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'; OUT = sys.argv[1]
P = json.load(open(S + '/rs/products.json'))
D, BL = 16.0, 1.0; PG = D + 2 * BL; C = PG / 2; R = D / 2
f = TTFont(S + '/font/Outfit-800.ttf'); gs = f.getGlyphSet(); cmap = f.getBestCmap(); hm = f['hmtx']
CD = re.search(r' d="([^"]+)"', open('/home/user/MORELLOSIMS/zuma-content/packaging/capsule-case/zuma-crest-stamp.svg').read()).group(1)
OXR = '0.4314 0.1098 0.1647'
M = lambda a: ' '.join(f'{v:.6f}' for v in a) + ' cm'
GLY = {}
def gpath(ch):
    if ch not in GLY: p = PDFPen(gs); gs[cmap[ord(ch)]].draw(p); GLY[ch] = ' '.join(p.o)
    return GLY[ch]
def arc_text(s, size, r, track=0.04):
    """letters on a circle of radius r (baseline), centred on the top, reading left to right"""
    adv = [hm[cmap[ord(c)]][0] * size / 1000 + track * size for c in s]; tot = sum(adv) - track * size
    a0 = -tot / (2 * r); x = 0; o = []
    for c, a in zip(s, adv):
        th = a0 + (x + (a - track * size) / 2) / r; x += a
        if c == ' ': continue
        px, py = C + r * math.sin(th), C - r * math.cos(th); w = hm[cmap[ord(c)]][0]
        o.append(f'q {M([1, 0, 0, 1, px, py])} {M([math.cos(th), math.sin(th), -math.sin(th), math.cos(th), 0, 0])} '
                 f'{M([size / 1000, 0, 0, -size / 1000, -w * size / 2000, 0])} {gpath(c)} f Q')
    return '\n'.join(o), math.degrees(tot / r)
def write(path, content, img, iw, ih):
    W = mm(PG); objs = []; add = lambda x: objs.append(x) or len(objs)
    cut_fn = add(b'<< /FunctionType 2 /Domain [0 1] /C0 [0 0 0 0] /C1 [0 1 0 0] /N 1 >>')
    cut_cs = add(b'[/Separation /CutContour /DeviceCMYK %d 0 R]' % cut_fn)
    im = add(b'<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n' % (iw, ih, len(img)) + img + b'\nendstream')
    st = zlib.compress(content.encode('latin-1')); c = add(b'<< /Length %d /Filter /FlateDecode >>\nstream\n' % len(st) + st + b'\nendstream')
    pages = len(objs) + 2; B = mm(BL)
    pg = add(f'<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 {W:.3f} {W:.3f}] /TrimBox [{B:.3f} {B:.3f} {W - B:.3f} {W - B:.3f}] /Resources << /ColorSpace << /Cut {cut_cs} 0 R >> /XObject << /Im0 {im} 0 R >> >> /Contents {c} 0 R >>'.encode())
    add(f'<< /Type /Pages /Kids [{pg} 0 R] /Count 1 >>'.encode()); cat = add(f'<< /Type /Catalog /Pages {pages} 0 R >>'.encode())
    out = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'; offs = []
    for i, o in enumerate(objs, 1): offs.append(len(out)); out += b'%d 0 obj\n' % i + o + b'\nendobj\n'
    x = len(out); out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1) + b''.join(b'%010d 00000 n \n' % o for o in offs)
    out += b'trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, cat, x); open(path, 'wb').write(out)
def circle(r):   # a circle as 4 Bezier arcs, centred on the sticker
    k = 0.5523 * r; c = C
    return (f'{c + r} {c} m {c + r} {c + k} {c + k} {c + r} {c} {c + r} c {c - k} {c + r} {c - r} {c + k} {c - r} {c} c '
            f'{c - r} {c - k} {c - k} {c - r} {c} {c - r} c {c + k} {c - r} {c + r} {c - k} {c + r} {c} c h')
G = f'{mm(1):.8f} 0 0 {-mm(1):.8f} 0 {mm(PG):.4f} cm'
report = []
for no, name, area in P:
    px = round(PG / 25.4 * 600); lb = Image.open(f'{S}/rs/lb-{no}.png').convert('RGB').resize((px, px), Image.LANCZOS)
    b = io.BytesIO(); lb.save(b, 'JPEG', quality=94, subsampling=0)
    cw = 7.4; cs = cw / 104.26                                                     # the crest, 7.4 mm wide
    crest = f'q {OXR} rg {M([cs, 0, 0, cs, C - cw / 2 + 0, C - 100 * cs / 2 + 0.55])} {svgpath(CD)} f* Q'
    size = min(2.3, 2.3 * 9.0 / max(len(name), 6))                                  # longer names set a little smaller
    txt, deg = arc_text(name, size, R - 0.75 - 0.72 * size)
    body = [G, f'q {PG} 0 0 {-PG} 0 {PG} cm /Im0 Do Q', crest, f'{OXR} rg', txt, f'/Cut CS 1 SCN 0.25 w {circle(R)} S']
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    write(f'{OUT}/zuma-round-{no}-{slug}.pdf', '\n'.join(body), b.getvalue(), px, px); report.append((no, name, round(deg)))
print(report)

# Vector print files for the tinted bag: type as outlines, logos as paths, the Lightbox ink and the back shadow as 600 dpi images.
# Layers (top-level groups): Dieline (do not print), White ink, Colour (transparent ink) / Back.
import json, base64, io, os, re, sys, numpy as np
from PIL import Image
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
S = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'; V = S + '/vac'; OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
L = json.load(open(S + '/ai/layout.json'))
FONTS = {w: TTFont(f'{S}/font/Outfit-{w}.ttf') for w in (500, 600, 700, 800)}
def glyph_d(ch, w):
    f = FONTS[min(FONTS, key=lambda k: abs(k - w))]; gs = f.getGlyphSet(); name = f.getBestCmap().get(ord(ch))
    if not name: raise SystemExit('missing glyph ' + ch)
    pen = SVGPathPen(gs); gs[name].draw(pen); return pen.getCommands()
def rotg(i):
    if i < 0: return ''
    r = L['rots'][i]; return f'rotate({r["a"]} {r["cx"]:.3f} {r["cy"]:.3f})'
def white(fill):
    by = {}
    for g in L['glyphs']:
        d = glyph_d(g['ch'], g['w']); s = g['size'] / 1000; base = g['top'] + g['size'] * 1.0   # Outfit: typo ascender 1000/1000
        by.setdefault(g['rot'], []).append(f'<path d="{d}" transform="matrix({s:.5f} 0 0 {-s:.5f} {g["x"]:.3f} {base:.3f})"/>')
    for v in L['svgs']:
        vx, vy, vw, vh = v['vb']; by.setdefault(v['rot'], []).append(
            f'<path fill-rule="{v["rule"]}" d="{v["d"]}" transform="translate({v["x"]:.3f} {v["y"]:.3f}) scale({v["w"] / vw:.6f} {v["h"] / vh:.6f}) translate({-vx} {-vy})"/>')
    for r in L['rects']: by.setdefault(r['rot'], []).append(f'<rect x="{r["x"]:.3f}" y="{r["y"]:.3f}" width="{r["w"]:.3f}" height="{r["h"]:.3f}"/>')
    inner = ''.join(f'<g transform="{rotg(k)}">{"".join(v)}</g>' for k, v in by.items())
    return f'<g id="White_ink" fill="{fill}"><g transform="translate(3 3) scale({100 / 1400:.8f})">{inner}</g></g>'
DIE = re.search(r'<svg[^>]*>(.*)</svg>', open(S + '/pack/dieline.html').read(), re.S).group(1)
DIE = re.sub(r'<text.*?</text>', '', DIE, flags=re.S)
def die(): return f'<g id="Dieline_do_not_print">{DIE}</g>'
def img(arr, mode='RGB'):
    b = io.BytesIO(); Image.fromarray(arr).convert(mode).save(b, 'JPEG', quality=93, subsampling=0)   # soft fields: JPEG keeps them small; the type is vector on top
    return f'<image x="0" y="0" width="106" height="156" preserveAspectRatio="none" href="data:image/jpeg;base64,{base64.b64encode(b.getvalue()).decode()}"/>'
DPI = 600; MM = DPI / 25.4; W, H = round(106 * MM), round(156 * MM); B = round(3 * MM)
a = np.array(Image.open(V + '/ca-big-hi.png').convert('RGBA').resize((W - 2 * B, H - 2 * B), Image.LANCZOS))[..., 3].astype(float) / 255
ko = np.zeros((H, W)); ko[B:H - B, B:W - B] = a
def svg(body): return f'<svg xmlns="http://www.w3.org/2000/svg" width="106mm" height="156mm" viewBox="0 0 106 156">{body}</svg>'
files = {}
for n, f in {'red': 'lbclean.png', 'blue': 'lb-metabolic.png', 'grey': 'lb-supplies.png'}.items():
    lb = np.array(Image.open(V + '/' + f).convert('RGB').resize((W, H), Image.LANCZOS)).astype(float)
    col = (lb * (1 - ko[..., None]) + 255 * ko[..., None]).astype('uint8')
    files[f'ZUMA-bag-front-{n}'] = svg(f'<g id="Colour_transparent_ink">{img(col)}</g>' + white('#FFFFFF') + die())
files['ZUMA-bag-front-white-ink-plate'] = svg('<rect width="106" height="156" fill="#fff"/>' + white('#000000') + die())
sh = np.array(Image.open(V + '/back-shadow.png').convert('L').resize((W, H), Image.LANCZOS)).astype(float) / 255
k = np.clip((sh.max() - sh) / (sh.max() - sh.min()), 0, 1) * 0.72
files['ZUMA-bag-back'] = svg('<g id="White_flood"><rect width="106" height="156" fill="#fff"/></g>' + f'<g id="Shadow_grey_K">{img((255 * (1 - k)).astype("uint8"), "L")}</g>' + die())
for name, s in files.items(): open(f'{OUT}/{name}.svg', 'w').write(s)
print('ok', list(files))

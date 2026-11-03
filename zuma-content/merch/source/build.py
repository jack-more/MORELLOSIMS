# ZUMA merch in the plain-box style, as apparel flats (front and back drawings, the way a tech pack shows them).
# Two directions per piece. Graphics are the box itself: the Lightbox panels in area tones, the crest, the Oxblood band and wordmark.
import json, os, re, base64
H = os.path.dirname(os.path.abspath(__file__))
FACES = json.load(open(os.path.join(H, 'mfaces.json')))
WM = json.load(open('/home/user/MORELLOSIMS/zuma-content/brand/wordmark/tides.json')); WW = WM['zuma_w']
CD = re.search(r' d="([^"]+)"', open('/home/user/MORELLOSIMS/zuma-content/packaging/capsule-case/zuma-crest-stamp.svg').read()).group(1)
OX, SNOW, INK = '#6E1C2A', '#FCFBF8', '#2A1A1C'
AREA = {'metabolic': '#1F4FD0', 'tissue': '#0E9A58', 'dermal': '#FF5A1F', 'endocrine': '#D08000', 'neuro': '#6E3FD8'}
uri = lambda svg: 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode()
def wm(x, y, w, c): return f'<svg x="{x}" y="{y}" width="{w}" height="{w * 100 / WW:.2f}" viewBox="0 0 {WW} 100"><path fill="{c}" fill-rule="evenodd" d="{WM["zuma"]}"/></svg>'
def crest(x, y, w, c): return f'<svg x="{x}" y="{y}" width="{w}" height="{w * 100 / 104.26:.2f}" viewBox="0 0 104.26 100"><path fill="{c}" fill-rule="evenodd" d="{CD}"/></svg>'
def face(area, x, y, w, ratio=37 / 20): return f'<image href="{uri(FACES[area])}" x="{x}" y="{y}" width="{w}" height="{w * ratio:.1f}"/>'
LINE = 'stroke="#3A2A2C" stroke-width="1.6" stroke-linejoin="round"'
STITCH = 'fill="none" stroke="#3A2A2C" stroke-width=".8" stroke-dasharray="3 2.5" opacity=".55"'

# ---------- the tee: boxy, dropped shoulder, heavyweight ----------
TEE = 'M150 40 Q200 62 250 40 L330 62 L382 150 L330 178 L318 150 L318 420 Q200 432 82 420 L82 150 L70 178 L18 150 L70 62 Z'
def tee(fill, inner, collar=None):
    collar = collar or fill
    return (f'<svg viewBox="0 0 400 450" class="g"><defs><clipPath id="tc{abs(hash(inner)) % 99999}"><path d="{TEE}"/></clipPath></defs>'
            f'<path d="{TEE}" fill="{fill}" {LINE}/>'
            f'<g clip-path="url(#tc{abs(hash(inner)) % 99999})">{inner}</g>'
            f'<path d="M150 40 Q200 70 250 40" fill="none" stroke="{collar}" stroke-width="9"/><path d="M150 40 Q200 62 250 40" fill="none" {LINE}/>'
            f'<path d="M318 150 L318 66 M82 150 L82 66" {STITCH}/><path d="M86 410 Q200 421 314 410" {STITCH}/><path d="M334 166 L380 142 M66 166 L20 142" {STITCH}/></svg>')

# ---------- shorts: sweatshort (cuffless, drawcord) and the mesh PE short (side panel, short inseam) ----------
SH = 'M70 40 L330 40 L350 260 L222 268 L200 120 L178 268 L50 260 Z'
def shorts(fill, inner, band=None, cord=True):
    band = band or fill
    k = abs(hash(inner + fill)) % 99999
    return (f'<svg viewBox="0 0 400 300" class="g"><defs><clipPath id="sc{k}"><path d="{SH}"/></clipPath></defs>'
            f'<path d="{SH}" fill="{fill}" {LINE}/><g clip-path="url(#sc{k})">{inner}</g>'
            f'<rect x="70" y="40" width="260" height="26" fill="{band}" {LINE}/>'
            + (f'<path d="M192 66 q-6 34 -14 46 M208 66 q6 34 14 46" fill="none" stroke="{SNOW if band != SNOW else INK}" stroke-width="2.4" stroke-linecap="round"/>' if cord else '')
            + f'<path d="M200 66 L200 120" {STITCH}/><path d="M56 246 L178 252 M344 246 L222 252" {STITCH}/></svg>')

# ---------- the hat: 5-panel, flat brim, side view + top ----------
def hat(crown, brim, front_art, top=None):
    top = top or crown
    return (f'<svg viewBox="0 0 400 260" class="g">'
            f'<path d="M74 196 Q80 70 200 62 Q320 70 326 196 Q200 182 74 196 Z" fill="{crown}" {LINE}/>'
            f'<path d="M140 70 Q150 130 146 190 M260 70 Q250 130 254 190" {STITCH}/>'
            f'<ellipse cx="200" cy="64" rx="10" ry="5" fill="{top}" {LINE}/>'
            f'{front_art}'
            f'<path d="M84 186 Q200 170 316 186 Q336 204 322 222 Q200 244 78 222 Q64 204 84 186 Z" fill="{brim}" {LINE}/>'
            f'<path d="M92 214 Q200 234 308 214" {STITCH}/></svg>')

def panels(area, x0, y0, s, alpha=1):
    """The box's Lightbox wall as a print: the front face of the carton (its panels, crest, band and wordmark), scaled."""
    return f'<g opacity="{alpha}">{face(area, x0, y0, s)}</g>'

items = []
def card(title, note, *svgs):
    items.append(f'<figure><div class="pair">{"".join(svgs)}</div><figcaption><b>{title}</b><span>{note}</span></figcaption></figure>')

# TEE · A: white heavyweight, small crest left chest; the back is the box front itself, big, between the shoulder blades
card('Tee · A · The box on the back', 'Snow heavyweight tee. Front: the crest small on the left chest in Oxblood. Back: the carton\'s Lightbox wall, crest and Oxblood band with the wordmark, big (Metabolic shown; one per area).',
     tee(SNOW, crest(236, 104, 34, OX)),
     tee(SNOW, face('metabolic', 130, 96, 140)))
# TEE · B: Oxblood tee, the Oxblood band language: wordmark across the chest in Snow, area panel strip down the back
card('Tee · B · Oxblood', 'Oxblood tee. Front: the ZUMA wordmark in Snow across the chest. Back: the carton wall in tonal Oxblood with the crest in Snow, like the mailer.',
     tee(OX, wm(124, 150, 152, SNOW), OX),
     tee(OX, face('oxblood', 130, 96, 140, 31 / 20)))
# SHORTS · A: Snow sweatshort with the Oxblood band as the hem panel, wordmark on the left leg
card('Sweatshort · A', 'Snow fleece sweatshort, Oxblood waistband and drawcord. The box band runs round the hem with the wordmark in Snow on the left leg.',
     shorts(SNOW, '<path d="M50 222 L178 230 L178 268 L50 260 Z" fill="%s"/><path d="M222 230 L350 222 L350 260 L222 268 Z" fill="%s"/>' % (OX, OX) + wm(70, 232, 76, SNOW), OX))
# SHORTS · B: mesh PE short in an area colour, Oxblood side panel, crest on the leg
card('Mesh PE short · B', 'Mesh gym short in an area colour (Metabolic blue shown; one per area). Oxblood side panels, Snow crest on the left leg, Oxblood waistband.',
     shorts(AREA['metabolic'], '<path d="M70 40 L96 40 L74 262 L50 260 Z" fill="%s"/><path d="M304 40 L330 40 L350 260 L326 262 Z" fill="%s"/>' % (OX, OX) + crest(104, 196, 34, SNOW)
            + ''.join(f'<circle cx="{x}" cy="{y}" r="1.1" fill="#000" opacity=".12"/>' for x in range(60, 345, 9) for y in range(70, 262, 9)), OX))
# HAT · A: Oxblood 5-panel, Snow crest front
card('Hat · A', 'Oxblood five-panel, flat brim. The crest in Snow on the front panel; the wordmark small in Snow at the back strap.',
     hat(OX, OX, crest(176, 104, 48, SNOW)))
# HAT · B: the box top: Snow crown, area-colour top button and brim, crest knocked out of the front panel
card('Hat · B · The box top', 'Snow five-panel with the area colour on the brim and button, like the carton top; the crest in the area colour on the front (Tissue green shown).',
     hat(SNOW, AREA['tissue'], crest(176, 104, 48, AREA['tissue']), AREA['tissue']))

CSS = '''body{margin:0;background:#E7E3DC;font-family:Outfit,sans-serif;color:#3A2328} section{padding:64px 72px}
h2{font:800 34px Outfit;color:#6E1C2A;margin:0 0 44px} .row{display:grid;grid-template-columns:repeat(2,1fr);gap:56px 64px}
figure{margin:0;background:#F3EFE8;border-radius:14px;padding:30px 30px 26px} .pair{display:flex;gap:18px;align-items:center;justify-content:center}
.g{width:100%;max-height:360px} figcaption{margin-top:16px;font:400 19px/1.45 Outfit} figcaption b{display:block;font:800 21px Outfit;color:#6E1C2A;margin-bottom:4px}'''
html = f'''<!doctype html><html><head><meta charset="utf-8"><title>ZUMA merch</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;800&display=swap" rel="stylesheet"><style>{CSS}</style></head><body>
<section><h2>Merch in the plain-box style</h2><div class="row">{''.join(items)}</div></section></body></html>'''
open(os.path.join(H, 'merch.html'), 'w').write(html); print('ok', len(items))

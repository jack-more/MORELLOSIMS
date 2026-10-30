# Plain box v2: two directions (Bands, Blocks). Panels drawn in mm, mocked up with CSS 3D, shot with Playwright.
import json, re, os
S = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'
OUT = S + '/plainbox/v3'
OX, SNOW, STUCCO, INK = '#6E1C2A', '#FCFBF8', '#EFE4D2', '#2A1A1C'
AREAS = {
  'metabolic': ('Metabolic research', '#1F4FD0'), 'tissue': ('Tissue research', '#0E9A58'),
  'dermal': ('Dermal research', '#FF5A1F'), 'endocrine': ('Endocrine research', '#D08000'),
  'neuro': ('Neuro research', '#6E3FD8'), 'supplies': ('Lab supplies', '#4E6077')}
PRODUCTS = [  # name, dose, area, full name
  ('RT-3', '10 mg', 'metabolic', 'Retatrutide'), ('TZ-2', '30 mg', 'metabolic', 'Tirzepatide'),
  ('MOTS-c', '10 mg', 'metabolic', 'MOTS-c peptide'), ('NAD+', '500 mg', 'metabolic', 'Nicotinamide adenine dinucleotide'),
  ('BPC+TB', '10 mg', 'tissue', 'BPC-157 + TB-500'), ('GHK-Cu', '50 mg', 'dermal', 'Copper tripeptide'),
  ('GHK+BT', '70 mg', 'dermal', 'GHK-Cu + BPC + TB'), ('TESAMORELIN', '10 mg', 'endocrine', 'Tesamorelin acetate'),
  ('CJC+IPA', '10 mg', 'endocrine', 'CJC-1295 + Ipamorelin'), ('SELANK', '10 mg', 'neuro', 'Selank acetate'),
  ('SEMAX', '10 mg', 'neuro', 'Semax acetate'), ('BAC WATER', '10 mL', 'supplies', 'Bacteriostatic water')]

def mix(a, b, t):
    a = [int(a[i:i+2], 16) for i in (1, 3, 5)]; b = [int(b[i:i+2], 16) for i in (1, 3, 5)]
    return '#' + ''.join('%02x' % round(x + (y - x) * t) for x, y in zip(a, b))

crest_src = open('/home/user/MORELLOSIMS/zuma-content/packaging/capsule-case/zuma-crest-stamp.svg').read()
CREST_VB = re.search(r'viewBox="([^"]+)"', crest_src).group(1)
CREST_PATHS = ''.join(re.findall(r'<path[^>]*/>', crest_src, re.S)).replace('fill="#000"', '')
wm_src = open('/home/user/MORELLOSIMS/zuma-content/brand/wordmark/zuma-tides-wordmark.svg').read()
WM_VB = re.search(r'viewBox="([^"]+)"', wm_src).group(1)
WM_PATHS = ''.join(re.findall(r'<path[^>]*/>', wm_src, re.S)).replace('fill="#6E1C2A"', '')
QR = json.load(open(S + '/window/final/src/qr.json'))

def crest(x, y, w, fill):
    vb = [float(v) for v in CREST_VB.split()]; h = w * vb[3] / vb[2]
    return f'<svg x="{x}" y="{y}" width="{w}" height="{h:.3f}" viewBox="{CREST_VB}"><g fill="{fill}">{CREST_PATHS}</g></svg>'
def wordmark(x, y, w, fill):
    vb = [float(v) for v in WM_VB.split()]; h = w * vb[3] / vb[2]
    return f'<svg x="{x}" y="{y}" width="{w}" height="{h:.3f}" viewBox="{WM_VB}"><g fill="{fill}">{WM_PATHS}</g></svg>'
def qr(x, y, size, fill):
    n = len(QR); c = size / n
    r = ''.join(f'<rect x="{x+j*c:.3f}" y="{y+i*c:.3f}" width="{c+0.01:.3f}" height="{c+0.01:.3f}"/>' for i, row in enumerate(QR) for j, v in enumerate(row) if v == '1')
    return f'<g fill="{fill}">{r}</g>'
def t(x, y, s, txt, fam='Figtree', w=500, fill=INK, anchor='start', ls=0, rot=None, extra=''):
    tr = f' transform="rotate({rot} {x} {y})"' if rot is not None else ''
    return (f'<text x="{x}" y="{y}" font-family="{fam}" font-weight="{w}" font-size="{s}" fill="{fill}" '
            f'text-anchor="{anchor}" letter-spacing="{ls}"{tr} {extra}>{txt}</text>')
PT = 0.3528  # mm per point
W, H = 20, 40   # panel size, mm

GRAIN = ('<svg xmlns="http://www.w3.org/2000/svg" width="0" height="0" style="position:absolute"><filter id="grain">'
         '<feTurbulence type="fractalNoise" baseFrequency="1.6" numOctaves="2" stitchTiles="stitch"/>'
         '<feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .55 0"/></filter>'
         '<filter id="fibre"><feTurbulence type="fractalNoise" baseFrequency="0.035 0.9" numOctaves="3"/>'
         '<feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .35 0"/></filter></svg>')
FONTS = ('<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600'
         '&family=Outfit:wght@500;600;700;800&display=swap" rel="stylesheet">')

def face_svg(inner, w, h, grain=0.10):
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" style="width:100%;height:100%;display:block">{inner}'
            f'<rect width="{w}" height="{h}" filter="url(#grain)" opacity="{grain}"/>'
            f'<rect width="{w}" height="{h}" filter="url(#fibre)" opacity="{grain*0.8}"/></svg>')

def box_html(d, p, k, ry, rx, extra=''):
    pan, top = DIRS[d]
    w, h = 20 * k, 40 * k
    face = lambda tr, inner, fw, fh, shade: (
        f'<div class="f" style="width:{fw}px;height:{fh}px;transform:{tr}">{face_svg(inner, fw / k, fh / k)}'
        f'<div class="sh" style="background:{shade}"></div></div>')
    return (f'<div class="box" style="width:{w}px;height:{h}px;transform:rotateX({rx}deg) rotateY({ry}deg);{extra}">'
            + face(f'translateZ({w/2}px)', pan(p, 'front'), w, h, 'linear-gradient(90deg,rgba(255,255,255,.04),rgba(0,0,0,.05))')
            + face(f'rotateY(90deg) translateZ({w/2}px)', pan(p, 'right'), w, h, 'linear-gradient(90deg,rgba(0,0,0,.20),rgba(0,0,0,.30))')
            + face(f'rotateY(-90deg) translateZ({w/2}px)', pan(p, 'left'), w, h, 'rgba(0,0,0,.25)')
            + face(f'rotateY(180deg) translateZ({w/2}px)', pan(p, 'back'), w, h, 'rgba(0,0,0,.3)')
            + face(f'rotateX(90deg) translateZ({w/2}px)', top(p), w, w, 'linear-gradient(180deg,rgba(255,255,255,.10),rgba(255,255,255,0))')
            + '</div>')

CSS = ('*{margin:0;box-sizing:border-box}body{font-family:Figtree,sans-serif;-webkit-font-smoothing:antialiased}'
       '.stage{display:flex;align-items:flex-end;justify-content:center;perspective:5200px}'
       '.slot{position:relative;display:flex;justify-content:center}'
       '.box{position:relative;transform-style:preserve-3d}'
       '.f{position:absolute;left:0;top:0;backface-visibility:hidden;overflow:hidden}'
       '.sh{position:absolute;inset:0;pointer-events:none}'
       '.shadow{position:absolute;bottom:-14px;left:50%;transform:translateX(-30%) skewX(-40deg);border-radius:50%;filter:blur(14px)}'
       '.cap{font:600 13px "IBM Plex Mono";letter-spacing:.14em;text-transform:uppercase}')

def page(body, bg, w, h):
    return (f'<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>{CSS} body{{background:{bg};width:{w}px;height:{h}px;overflow:hidden}}</style></head>'
            f'<body>{GRAIN}{body}</body></html>')


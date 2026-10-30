# Plain box v2: two directions (Bands, Blocks). Panels drawn in mm, mocked up with CSS 3D, shot with Playwright.
import json, re, os
S = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'
OUT = S + '/plainbox/v2'
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

# ---------------- Direction 1: Bands ----------------
B_TOP, B_BAND, B_FIELD, B_BOT = (0, 6), (6, 15), (15, 34), (34, 40)
def bands_panel(p, side):
    name, dose, area, full = p; label, col = AREAS[area]
    g = [f'<rect width="{W}" height="{H}" fill="{STUCCO}"/>',
         f'<rect y="0" width="{W}" height="6" fill="{SNOW}"/>',
         f'<rect y="6" width="{W}" height="9" fill="{col}"/>',
         f'<rect y="34" width="{W}" height="6" fill="{OX}"/>']
    m = 1.6
    if side == 'front':
        g += [t(m, 3.6, 3.4 * PT, 'Research compound', w=500, fill=INK),
              t(m, 9.6, 6.5 * PT * min(1, 10.0 / len(name)), name, 'Outfit', 700, SNOW, ls=0.05 if len(name) < 8 else 0),
              t(m, 13.0, 3.2 * PT, label, w=500, fill=SNOW),
              t(W - m, 13.0, 3.6 * PT, dose.upper(), 'IBM Plex Mono', 600, SNOW, 'end'),
              wordmark(m, 28.6, W - 2 * m, OX),
              t(m, 36.5, 2.6 * PT, 'For laboratory research use only.', w=500, fill=SNOW),
              t(m, 37.75, 2.6 * PT, 'Not for human or veterinary use.', w=500, fill=SNOW),
              t(W - m, 39.0, 2.6 * PT, '3 mL vial · lyophilized', 'IBM Plex Mono', 500, mix(SNOW, OX, .35), 'end')]
    elif side == 'right':
        g += [t(m, 3.6, 3.4 * PT, 'Research compound', w=500, fill=INK),
              t(m, 9.6, 3.6 * PT, full, w=600, fill=SNOW),
              t(m, 13.0, 3.2 * PT, label, w=500, fill=SNOW),
              t(4.2, 32.6, 3.6 * PT, 'Research, refined.', 'Outfit', 700, OX, rot=-90),
              t(7.4, 32.6, 2.8 * PT, 'Every lot tested before it ships.', w=500, fill=INK, rot=-90),
              t(8.7, 32.6, 2.8 * PT, 'Reports: zumatides.com/lots', 'IBM Plex Mono', 500, INK, rot=-90),
              t(m, 37.6, 2.6 * PT, 'Store sealed, cold and away from light.', w=500, fill=SNOW)]
    elif side == 'back':
        g += [t(m, 3.35, 3.2 * PT, 'zuma tides', w=600, fill=OX),
              t(m, 9.6, 3.6 * PT, f'{name} · {dose}', 'Outfit', 600, SNOW),
              t(m, 13.0, 3.2 * PT, 'Lot reports', w=500, fill=SNOW),
              qr(m, 17.2, 9.5, OX),
              t(m, 29.0, 2.8 * PT, 'Scan for lot reports', w=600, fill=INK),
              t(m, 30.3, 2.8 * PT, 'zumatides.com/lots', 'IBM Plex Mono', 500, INK),
              t(m, 36.5, 2.6 * PT, 'For laboratory research use only.', w=500, fill=SNOW),
              t(m, 37.75, 2.6 * PT, 'Not for human or veterinary use.', w=500, fill=SNOW),
              t(W - m, 39.0, 2.6 * PT, 'zumatides.com', 'IBM Plex Mono', 500, mix(SNOW, OX, .35), 'end')]
    else:  # left
        g += [t(W - m, 3.35, 3.2 * PT, label.split()[0], w=500, fill=INK, anchor='end'),
              t(m, 9.6, 3.6 * PT, label, w=600, fill=SNOW),
              t(4.2, 32.6, 3.6 * PT, full, 'Outfit', 600, OX, rot=-90),
              t(7.4, 32.6, 2.8 * PT, f'{name} · {dose} · 3 mL vial', 'IBM Plex Mono', 500, INK, rot=-90),
              crest(W - 6.2, 17.0, 4.4, mix(STUCCO, OX, .18)),
              t(m, 37.6, 2.6 * PT, 'Made for the lab.', w=500, fill=SNOW)]
    return ''.join(g)
def bands_top(p): return f'<rect width="20" height="20" fill="{OX}"/>' + crest(5.5, 5.7, 9, '#b98b6c')
def bands_inside(p): return AREAS[p[2]][1]

# ---------------- Direction 2: Blocks ----------------
def blocks_panel(p, side):
    name, dose, area, full = p; label, col = AREAS[area]
    lt, lt2, dp = mix(col, SNOW, .55), mix(col, SNOW, .78), mix(col, '#1a1012', .35)
    g = [f'<rect width="{W}" height="{H}" fill="{SNOW}"/>']
    m = 1.5
    if side == 'front':
        g += [f'<rect x="7.5" y="6" width="12.5" height="22" fill="{col}"/>',          # tall rect, wraps onto the right side
              f'<rect x="1.6" y="15" width="8.4" height="8.4" fill="{lt2}"/>',
              f'<rect x="5.2" y="18.6" width="5.6" height="5.6" fill="{dp}"/>',
              t(m, 3.6, 3 * PT, 'zuma tides', w=600, fill=OX),
              t(9.0, 8.9, 5.6 * PT * min(1, 7.0 / len(name)), name, 'Outfit', 700, SNOW, ls=0.03),
              t(9.0, 10.6, 3 * PT, dose.upper(), 'IBM Plex Mono', 600, SNOW),
              t(9.0, 26.4, 2.6 * PT, label, w=500, fill=SNOW),
              t(6.2, 23.4, 2.4 * PT, dose.split()[0], 'IBM Plex Mono', 600, SNOW),
              wordmark(m, 35.2, 8.6, OX),
              t(W - m, 38.6, 2.4 * PT, 'Research use only', w=500, fill=mix(INK, SNOW, .35), anchor='end'),
              f'<rect x="19.35" y="32" width="0.65" height="8" fill="{col}"/>']
    elif side == 'right':
        g += [f'<rect x="0" y="6" width="5.5" height="22" fill="{col}"/>',
              f'<rect x="0" y="32" width="0.65" height="8" fill="{col}"/>',
              t(9.5, 27.0, 3.2 * PT, f'{name}  ·  {dose}  ·  {label}', 'Outfit', 600, OX, rot=-90),
              t(12.0, 27.0, 2.6 * PT, 'Every lot tested before it ships.', w=500, fill=INK, rot=-90),
              t(13.3, 27.0, 2.6 * PT, 'Store sealed, cold and away from light.', w=500, fill=INK, rot=-90),
              t(m + 4, 38.6, 2.4 * PT, '3 mL vial · lyophilized', 'IBM Plex Mono', 500, mix(INK, SNOW, .35))]
    elif side == 'back':
        g += [f'<rect x="1.5" y="6" width="10" height="10" fill="{lt2}"/>',
              qr(5.0, 9.5, 9.0, OX),
              t(m, 23.0, 3.2 * PT, f'{name} · {dose}', 'Outfit', 700, OX),
              t(m, 24.5, 2.6 * PT, full, w=500, fill=INK),
              t(m, 27.6, 2.6 * PT, 'Scan for lot reports', w=600, fill=INK),
              t(m, 28.8, 2.6 * PT, 'zumatides.com/lots', 'IBM Plex Mono', 500, INK),
              f'<rect x="1.5" y="33.2" width="17" height="0.15" fill="{mix(INK, SNOW, .6)}"/>',
              t(m, 35.2, 2.6 * PT, 'For laboratory research use only.', w=500, fill=INK),
              t(m, 36.4, 2.6 * PT, 'Not for human or veterinary use.', w=500, fill=INK),
              t(m, 38.6, 2.4 * PT, 'zumatides.com', 'IBM Plex Mono', 500, mix(INK, SNOW, .35))]
    else:  # left: blind-embossed crest only
        g += [crest(4.5, 13.5, 11, mix(SNOW, '#bdb6aa', .55)),
              f'<rect x="0" y="32" width="0.0" height="8"/>']
    return ''.join(g)
def blocks_top(p): return f'<rect width="20" height="20" fill="{AREAS[p[2]][1]}"/>' + crest(6, 6.2, 8, mix(AREAS[p[2]][1], '#1a1012', .3))
def blocks_inside(p): return AREAS[p[2]][1]

DIRS = {'bands': (bands_panel, bands_top), 'blocks': (blocks_panel, blocks_top)}
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

ROW = [PRODUCTS[i] for i in (0, 3, 4, 5, 7, 8, 10, 11, 1, 6)]

def row(d, bg, fg, k=13, ry=-15, rx=-7):
    slots = ''.join(f'<div class="slot" style="margin:0 {k*1.6}px">'
                    f'<div class="shadow" style="width:{k*34}px;height:{k*8}px;background:rgba(0,0,0,{.55 if bg[1]<"8" else .22})"></div>'
                    f'{box_html(d, p, k, ry, rx)}</div>' for p in ROW)
    title = (f'<div class="cap" style="position:absolute;left:70px;top:60px;color:{fg};opacity:.75">zuma tides · plain carton · '
             f'{"Bands" if d=="bands" else "Blocks"}</div>')
    return page(f'{title}<div class="stage" style="position:absolute;inset:0;align-items:center;padding-top:60px">{slots}</div>', bg, 3900, 1100)

def trio(d, bg, fg, k=26):
    ps = [PRODUCTS[0], PRODUCTS[4], PRODUCTS[5]] if d == 'bands' else [PRODUCTS[9], PRODUCTS[0], PRODUCTS[5]]
    slots = ''.join(f'<div class="slot" style="margin:0 {k*6}px"><div class="shadow" style="width:{k*40}px;height:{k*9}px;'
                    f'background:rgba(0,0,0,{.5 if bg[1]<"8" else .2})"></div>{box_html(d, p, k, -30, -10)}</div>' for p in ps)
    return page(f'<div class="stage" style="position:absolute;inset:0;padding-bottom:260px">{slots}</div>', bg, 3000, 2000)

def panels(d, p, bg='#EDE8E0'):
    pan, top = DIRS[d]; k = 22
    lab = lambda s: f'<div class="cap" style="color:#5a4a48;margin-top:16px;font-size:16px">{s}</div>'
    cell = lambda inner, w, h, l: (f'<div style="display:flex;flex-direction:column;align-items:flex-start">'
                                   f'<div style="width:{w*k}px;height:{h*k}px;box-shadow:0 2px 14px rgba(0,0,0,.12)">{face_svg(inner, w, h, .06)}</div>{lab(l)}</div>')
    row_ = ''.join(cell(pan(p, s), 20, 40, l) for s, l in (('left', 'Left side · P1'), ('front', 'Front · P2'), ('right', 'Right side · P3'), ('back', 'Back · P4')))
    tops = (cell(top(p), 20, 20, 'Top flap') + cell(f'<rect width="20" height="20" fill="{DIRS[d][1] and AREAS[p[2]][1]}"/>', 20, 20, 'Inside (flood)'))
    head = (f'<div style="position:absolute;left:80px;top:60px"><div class="cap" style="color:#6E1C2A;font-size:18px">ZUMA TIDES · PLAIN CARTON · '
            f'{"BANDS" if d=="bands" else "BLOCKS"} · {p[0]} {p[1].upper()} · PANELS AT ABOUT 6:1</div>'
            f'<div style="font:800 64px Outfit;color:#1a1012;margin-top:14px">{"Bands" if d=="bands" else "Blocks"}</div>'
            f'<div style="font:500 22px Figtree;color:#3a2e2c;margin-top:8px;max-width:1900px">'
            + ('Nala-style colour bands that wrap all four sides: Snow line band, area-colour product band, Stucco field with the Oxblood crest, Oxblood band with the research-use line. Uncoated textured board; Oxblood top flap with the foil crest; inside flooded in the area colour.'
               if d == 'bands' else
               'Snow carton with one tall area-colour block that wraps onto the right side, two smaller overlapping blocks (tint and shade of the same colour, a nod to the Lightbox wall), tiny type, a thin area-colour line down the front corner. Area-colour top and inside; blind crest on the left side.')
            + '</div></div>')
    body = (head + f'<div style="position:absolute;left:80px;top:300px;display:flex;gap:56px;align-items:flex-start">{row_}'
            f'<div style="display:flex;flex-direction:column;gap:40px">{tops}</div></div>')
    return page(body, bg, 3000, 1400)

jobs = {
  'row-bands': row('bands', '#121011', '#e9e0d6'),
  'row-blocks': row('blocks', '#E9E5DE', '#3a2e2c'),
  'trio-bands': trio('bands', '#1a1718', '#e9e0d6'),
  'trio-blocks': trio('blocks', '#E6E2DB', '#3a2e2c'),
  'panels-bands-rt3': panels('bands', PRODUCTS[0]),
  'panels-blocks-rt3': panels('blocks', PRODUCTS[0]),
}
for n, html in jobs.items(): open(f'{OUT}/{n}.html', 'w').write(html)
print('\n'.join(jobs))

# ZUMA throw-in sticker pack: nine die-cut stickers for orders.
# Each sticker is an SVG in mm x 10 units with a 2 mm white die-cut border built in (the printer cuts around the outside).
#   python3 build_stickers.py -> stickers.html (all nine, for the preview sheet and the per-sticker PNG export in export.cjs)
import json, math, os, re
HERE = os.path.dirname(os.path.abspath(__file__)); BRAND = os.path.join(HERE, '..', 'brand')
OX, SNOW, STUCCO, INK = '#6E1C2A', '#FCFBF8', '#EFE4D2', '#2A1A1C'
SKY, LIME, CORAL, LEMON, LILAC, SLATE = '#36B3E8', '#6CC93A', '#FF6A55', '#F4D63A', '#A57BF0', '#9AA8B6'
HEAD, MONO = "Outfit, 'Helvetica Neue', Arial, sans-serif", "'IBM Plex Mono', ui-monospace, monospace"

crest_src = open(os.path.join(HERE, '..', 'packaging', 'capsule-case', 'zuma-crest-stamp.svg')).read()
CREST_D = re.search(r' d="([^"]+)"', crest_src).group(1)          # viewBox 0 0 104.26 100
WM = json.load(open(os.path.join(BRAND, 'wordmark', 'tides.json'))); WM_D, WM_W = WM['zuma'], WM['zuma_w']   # 418 x 100

def crest(cx, cy, w, fill):
    s = w / 104.26
    return f'<path fill="{fill}" fill-rule="evenodd" transform="translate({cx - w / 2:.2f} {cy - 50 * s:.2f}) scale({s:.4f})" d="{CREST_D}"/>'
def wordmark(cx, y, w, fill):
    s = w / WM_W
    return f'<path fill="{fill}" fill-rule="evenodd" transform="translate({cx - w / 2:.2f} {y:.2f}) scale({s:.4f})" d="{WM_D}"/>'
def text(x, y, size, s, fill, family=HEAD, weight=800, anchor='middle', ls=0, extra=''):
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-weight="{weight}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" letter-spacing="{ls}" {extra}>{s}</text>')

def sticker(key, w, h, body, border=20):
    # w, h in mm x 10. The die-cut: the artwork's silhouette grown by 2 mm, in white, with a soft shadow only on the preview.
    pad = border + 30
    return (f'<svg class="st" data-key="{key}" xmlns="http://www.w3.org/2000/svg" viewBox="{-pad} {-pad} {w + 2 * pad} {h + 2 * pad}" '
            f'style="width:{(w + 2 * pad) / 10}mm;height:{(h + 2 * pad) / 10}mm">'
            f'<defs><filter id="cut-{key}" x="-20%" y="-20%" width="140%" height="140%">'
            f'<feMorphology in="SourceAlpha" operator="dilate" radius="{border}" result="grow"/>'
            f'<feFlood flood-color="#FFFFFF"/><feComposite in2="grow" operator="in" result="white"/>'
            f'<feGaussianBlur in="grow" stdDeviation="9" result="blur"/><feOffset in="blur" dx="0" dy="8" result="sh"/>'
            f'<feFlood class="shadow" flood-color="#000" flood-opacity=".22"/><feComposite in2="sh" operator="in" result="shadow"/>'
            f'<feMerge><feMergeNode in="shadow"/><feMergeNode in="white"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
            f'<g filter="url(#cut-{key})">{body}</g></svg>')

S = {}
# 1. Crest seal, 60 mm: Oxblood disc, Snow crest, the brand line running round the rim
r = 300; ring = 252
S['crest-seal'] = sticker('crest-seal', 600, 600,
    f'<circle cx="300" cy="300" r="{r}" fill="{OX}"/><circle cx="300" cy="300" r="{ring - 34}" fill="none" stroke="{SNOW}" stroke-width="4"/>'
    f'<defs><path id="rim" d="M300,300 m-{ring},0 a{ring},{ring} 0 1,1 {2 * ring},0 a{ring},{ring} 0 1,1 -{2 * ring},0"/></defs>'
    f'<text font-family="{MONO}" font-weight="600" font-size="34" fill="{SNOW}" letter-spacing="0">'
    f'<textPath href="#rim" startOffset="0" textLength="1560" lengthAdjust="spacing">ZUMA · RESEARCH, REFINED · EST. 2026 · ZUMATIDES.COM ·</textPath></text>'
    + crest(300, 300, 270, SNOW))

# 2. Lightbox, 70 x 50 mm: the window box's panel grid in Oxblood tones, wordmark reversed out on the deep band
def lb(x, y, w, h, c, gid):
    return (f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2=".35" y2="1"><stop offset="0" stop-color="#ffffff" stop-opacity=".22"/>'
            f'<stop offset=".6" stop-color="#ffffff" stop-opacity="0"/></linearGradient></defs>'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}"/><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{gid})"/>')
T1, T2, T3, T4 = '#E9C9CE', '#C98D97', '#9C4352', '#4A0F1A'
S['lightbox'] = sticker('lightbox', 700, 500,
    f'<rect width="700" height="500" rx="26" fill="{SNOW}"/>'
    + lb(40, 40, 70, 300, T2, 'g1') + lb(130, 40, 340, 110, T1, 'g2') + lb(130, 170, 340, 170, OX, 'g3')
    + lb(490, 40, 170, 110, T3, 'g4') + lb(490, 170, 70, 170, T2, 'g5') + lb(580, 170, 80, 170, T1, 'g6')
    + crest(300, 255, 120, SNOW)
    + f'<rect x="40" y="360" width="620" height="100" fill="{T4}"/>' + wordmark(350, 375, 270, SNOW))

# 3. Vial, 28 x 70 mm die-cut silhouette: Oxblood cap, crimp, glass with a coral label band
S['vial'] = sticker('vial', 280, 700,
    f'<rect x="60" y="0" width="160" height="120" rx="22" fill="{OX}"/><rect x="74" y="16" width="132" height="22" rx="8" fill="#8E2A3A"/>'
    f'<rect x="44" y="110" width="192" height="70" rx="10" fill="#C9C2BE"/><rect x="44" y="132" width="192" height="8" fill="#B3ABA6"/>'
    f'<path d="M70 180 L70 200 Q20 215 20 270 L20 660 Q20 700 60 700 L220 700 Q260 700 260 660 L260 270 Q260 215 210 200 L210 180 Z" fill="#E8F1F4"/>'
    f'<path d="M48 280 L48 640" stroke="#FFFFFF" stroke-width="16" stroke-linecap="round" opacity=".85"/>'
    f'<rect x="20" y="380" width="240" height="250" fill="{CORAL}"/><rect x="20" y="380" width="240" height="60" fill="#FFC9BE"/>'
    f'<rect x="20" y="590" width="240" height="40" fill="{OX}"/>' + crest(140, 410, 44, OX) + wordmark(140, 462, 150, OX)
    + text(140, 560, 30, 'RESEARCH', OX, MONO, 600, ls=4))

# 4. The new era strip, 100 x 24 mm
S['new-era'] = sticker('new-era', 1000, 240,
    f'<rect width="1000" height="240" rx="120" fill="{OX}"/>' + crest(125, 120, 120, SNOW)
    + text(215, 114, 56, 'THE NEW ERA OF RESEARCH', SNOW, HEAD, 800, 'start', extra='textLength="730" lengthAdjust="spacingAndGlyphs"')
    + text(217, 168, 28, 'ZUMATIDES.COM  ·  EST. 2026', '#E9C9CE', MONO, 600, 'start', ls=6))

# 5. Six areas, 86 x 30 mm: one dot per research area
AREAS = [(SKY, 'METABOLIC'), (LIME, 'TISSUE'), (CORAL, 'DERMAL'), (LEMON, 'ENDOCRINE'), (LILAC, 'NEURO'), (SLATE, 'SUPPLIES')]
dots = ''.join(f'<circle cx="{95 + i * 134}" cy="135" r="52" fill="{c}"/>' + text(95 + i * 134, 230, 20, n, OX, MONO, 600, ls=2) for i, (c, n) in enumerate(AREAS))
S['six-areas'] = sticker('six-areas', 860, 300,
    f'<rect width="860" height="300" rx="34" fill="{SNOW}" stroke="{OX}" stroke-width="8"/>'
    + text(430, 60, 26, 'SIX AREAS · ONE STANDARD', OX, MONO, 600, ls=8) + dots)

# 6. Lot-tested stamp, 50 x 62 mm: a postage stamp with a scalloped edge
w, h, rr, step = 500, 620, 16, 44
scallop = ''.join(f'<circle cx="{x}" cy="{y}" r="{rr}" fill="#000"/>' for x in range(22, w, step) for y in (0, h)) + \
          ''.join(f'<circle cx="{x}" cy="{y}" r="{rr}" fill="#000"/>' for y in range(22, h, step) for x in (0, w))
S['lot-stamp'] = sticker('lot-stamp', w, h, border=1, body=
    f'<defs><mask id="perf"><rect x="-20" y="-20" width="{w + 40}" height="{h + 40}" fill="#fff"/>{scallop.replace("#000", "#000")}</mask></defs>'
    f'<rect width="{w}" height="{h}" fill="{SNOW}" mask="url(#perf)"/>'
    f'<rect x="40" y="40" width="{w - 80}" height="{h - 80}" fill="{STUCCO}" stroke="{OX}" stroke-width="5"/>'
    + crest(250, 210, 190, OX)
    + text(250, 380, 44, 'EVERY LOT', OX, HEAD, 900) + text(250, 428, 44, 'TESTED', OX, HEAD, 900)
    + f'<rect x="90" y="458" width="320" height="3" fill="{OX}"/>'
    + text(250, 500, 24, 'HPLC · MASS SPEC', OX, MONO, 600, ls=3) + text(250, 534, 22, 'REPORTS AT /LOTS', OX, MONO, 600, ls=3)
    + text(250, 92, 22, 'ZUMA · No. 001', OX, MONO, 600, ls=4))

# 7. Zuma Beach, 62 x 62 mm: sun, sea in the area colours, sand, coordinates
S['zuma-beach'] = sticker('zuma-beach', 620, 620,
    f'<defs><clipPath id="sq"><rect width="620" height="620" rx="60"/></clipPath></defs><g clip-path="url(#sq)">'
    f'<rect width="620" height="620" fill="#FBE3D6"/><circle cx="310" cy="300" r="150" fill="{CORAL}"/><circle cx="310" cy="300" r="150" fill="{OX}" opacity=".0"/>'
    + ''.join(f'<rect x="0" y="{300 + i * 46}" width="620" height="46" fill="{c}"/>' for i, c in enumerate([SKY, '#1F7FB8', SKY, '#0E5A8C']))
    + ''.join(f'<path d="M0 {300 + i * 46 + 23} q 40 -12 80 0 t 80 0 t 80 0 t 80 0 t 80 0 t 80 0 t 80 0 t 80 0" fill="none" stroke="{SNOW}" stroke-width="4" opacity=".55"/>' for i in range(4))
    + f'<path d="M0 470 Q 310 430 620 470 L620 620 L0 620 Z" fill="{STUCCO}"/>'
    + wordmark(310, 500, 230, OX) + text(310, 590, 22, 'ZUMA BEACH, CA · 34.02°N 118.82°W', OX, MONO, 600, ls=2)
    + f'</g><rect width="620" height="620" rx="60" fill="none" stroke="{OX}" stroke-width="10"/>')

# 8. Lab label, 70 x 40 mm: a working label researchers can write on
S['lab-label'] = sticker('lab-label', 700, 400,
    f'<rect width="700" height="400" rx="18" fill="#FFFFFF" stroke="{OX}" stroke-width="10"/>'
    f'<rect x="5" y="5" width="690" height="92" rx="13" fill="{OX}"/>' + crest(56, 51, 58, SNOW) + wordmark(185, 28, 140, SNOW)
    + text(668, 64, 24, 'LAB LABEL', '#E9C9CE', MONO, 600, 'end', ls=6)
    + ''.join(text(40, 170 + i * 72, 26, f, OX, MONO, 600, 'start', ls=3) + f'<rect x="{200}" y="{176 + i * 72}" width="460" height="3" fill="{OX}"/>'
              for i, f in enumerate(['SAMPLE', 'DATE', 'INITIALS'])))

# 9. Wordmark, 80 mm: the plain Oxblood die-cut
S['wordmark'] = sticker('wordmark', 800, 192, wordmark(400, 0, 800, OX), border=24)

NAMES = {'crest-seal': 'Crest seal · Ø 60 mm', 'lightbox': 'Lightbox · 70 × 50 mm', 'vial': 'Vial · 28 × 70 mm', 'new-era': 'The new era · 100 × 24 mm',
         'six-areas': 'Six areas · 86 × 30 mm', 'lot-stamp': 'Lot-tested stamp · 50 × 62 mm', 'zuma-beach': 'Zuma Beach · 62 × 62 mm',
         'lab-label': 'Lab label (write-on) · 70 × 40 mm', 'wordmark': 'Wordmark · 80 × 19 mm'}
cells = ''.join(f'<figure>{svg}<figcaption>{NAMES[k]}</figcaption></figure>' for k, svg in S.items())
html = f'''<!doctype html><html><head><meta charset="utf-8"><title>ZUMA sticker pack</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@700;800;900&family=IBM+Plex+Mono:wght@600&display=swap" rel="stylesheet">
<style>body{{margin:0;background:#E7DFD3;font-family:Outfit,sans-serif;color:{INK}}} .wrap{{padding:60px 70px}} h1{{font:900 54px Outfit;color:{OX};margin:0}}
p{{font:500 18px 'IBM Plex Mono';color:#7A5A60;margin:8px 0 40px}} .grid{{zoom:2.2;display:flex;flex-wrap:wrap;gap:46px 40px;align-items:flex-end}}
figure{{margin:0;display:flex;flex-direction:column;align-items:center}} figcaption{{font:600 15px 'IBM Plex Mono';color:#7A5A60;margin-top:6px}}
.st{{display:block}}</style></head><body><div class="wrap"><h1>ZUMA sticker pack</h1><p>Nine die-cut throw-ins · 2 mm white border · matte vinyl</p>
<div class="grid">{cells}</div></div></body></html>'''
open(os.path.join(HERE, 'stickers.html'), 'w').write(html)
print('ok', len(S))

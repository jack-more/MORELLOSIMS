# Print art for the 12 vacuum-pouch versions. 75 x 105 mm at 20 px/mm = 1500 x 2100. Top of the art = the vial's cap end.
# Each version writes v-NN.html; ?mask renders the base layer (white = frosted / foil / white underlay) for masks.py.
import json, os, re, urllib.parse
H = os.path.dirname(os.path.abspath(__file__))
WM = json.load(open('/home/user/MORELLOSIMS/zuma-content/brand/wordmark/tides.json')); WW = WM['zuma_w']
CD = re.search(r' d="([^"]+)"', open('/home/user/MORELLOSIMS/zuma-content/packaging/capsule-case/zuma-crest-stamp.svg').read()).group(1)
QR = json.load(open(os.path.join(os.path.dirname(H), 'bag', 'qrlots.json')))
OX, SNOW, PINK = '#6E1C2A', '#FCFBF8', '#E9C9CE'
SEEDS = {'metabolic': (3, 'palm', 5), 'dermal': (11, 'bamboo', 4), 'endocrine': (5, 'palm', 9), 'tissue': (14, 'bamboo', 6), 'neuro': (21, 'palm', 8), 'supplies': (34, 'bamboo', 7), 'oxblood': (8, 'palm', 12)}
# vial footprint (art px): axis x = 650, cap end at y = 448, base at y = 1652, 24 mm wide
WIN = (344, 380, 956, 1720, 150)     # clear window round the vial: x0 y0 x1 y1 radius

def rr(x0, y0, x1, y1, r):
    return f'M{x0+r} {y0}H{x1-r}A{r} {r} 0 0 1 {x1} {y0+r}V{y1-r}A{r} {r} 0 0 1 {x1-r} {y1}H{x0+r}A{r} {r} 0 0 1 {x0} {y1-r}V{y0+r}A{r} {r} 0 0 1 {x0+r} {y0}Z'
WINCLIP = f"clip-path:path(evenodd,'M0 0H1500V2100H0Z {rr(*WIN)}')"

def wm_tall(cx, cy, length, color, rot=-90):
    t = length * 100 / WW
    return (f'<svg viewBox="0 0 {WW} 100" style="position:absolute;width:{length}px;height:{t:.0f}px;left:{cx-length/2:.0f}px;top:{cy-t/2:.0f}px;transform:rotate({rot}deg)">'
            f'<path fill="{color}" fill-rule="evenodd" d="{WM["zuma"]}"/></svg>')
def crest(x, y, w, color):
    return f'<svg viewBox="0 0 104.26 100" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{w*100/104.26:.0f}px"><path fill="{color}" fill-rule="evenodd" d="{CD}"/></svg>'
def lb(area, cols=3, rows=5, bars=0, st=''):
    s, b, bs = SEEDS[area]
    return f'<canvas data-lb="{area}" data-seed="{s}" data-cols="{cols}" data-rows="{rows}" data-bars="{bars}" data-behind="{b}" data-bseed="{bs}" style="position:absolute;inset:0;width:100%;height:100%;{st}"></canvas>'

def stamps(c, x=128, y=1420):
    """The lab marks: a ruled lot block (rotated, reads bottom-up), a ring stamp with the crest, a QR to the lot reports."""
    q = f'<svg viewBox="-1 -1 {QR["n"]+2} {QR["n"]+2}" style="width:150px;height:150px;display:block" shape-rendering="crispEdges"><path fill="{c}" d="{QR["p"]}"/></svg>'
    lot = (f'<div class="blk" style="left:{x}px;top:{y}px;border-color:{c};color:{c}"><div>ZUMA RESEARCH</div><div class="ln">LOT <i style="border-color:{c}"></i></div>'
           f'<div class="ln">SEALED <i style="border-color:{c}"></i></div><div class="sm">FOR LABORATORY RESEARCH USE ONLY</div></div>')
    ring = (f'<svg style="position:absolute;left:1075px;top:140px;width:250px;height:250px;transform:rotate(-14deg)" viewBox="0 0 290 290">'
            f'<defs><path id="rc" d="M145 145 m-112 0 a112 112 0 1 1 224 0 a112 112 0 1 1 -224 0"/></defs>'
            f'<circle cx="145" cy="145" r="138" fill="none" stroke="{c}" stroke-width="5"/><circle cx="145" cy="145" r="86" fill="none" stroke="{c}" stroke-width="3"/>'
            f'<text font-family="IBM Plex Mono" font-weight="600" font-size="23" letter-spacing="5" fill="{c}"><textPath href="#rc">VACUUM SEALED · EVERY LOT TESTED · </textPath></text>'
            f'<g transform="translate(95 97) scale(0.96)"><path fill="{c}" fill-rule="evenodd" d="{CD}"/></g></svg>')
    qr = (f'<div class="qrb" style="left:1080px;top:1720px;color:{c};border-color:{c}">{q}<div>ZUMATIDES.COM/LOTS</div></div>')
    return lot + ring + qr

# each version: (key, name, vial no, film, ground, body html, note)
V = []
def add(key, name, no, film, ground, body, note): V.append(dict(key=key, name=name, no=no, film=film, ground=ground, body=body, note=note))
BASEALL = '<div class="base"></div>'
BASEWIN = f'<div class="base" style="{WINCLIP}"></div>'

add('clear-ox', 'Clear, Oxblood ink', '01', 'clear', '#DCD8D2', wm_tall(1200, 1050, 1240, OX) + stamps(OX),
    'Clear film, Oxblood ink only: tall wordmark, the lot block, the sealed ring, the QR to the lot reports.')
add('clear-snow', 'Clear, Snow ink, night', '09', 'clear', '#3B1219', wm_tall(1200, 1050, 1240, SNOW) + stamps(SNOW),
    'The same in white ink, shot on Oxblood: how it reads on a dark counter.')
add('frost', 'Frosted, clear window', '04', 'frosted', '#DCD8D2', BASEWIN + wm_tall(1200, 1050, 1240, OX) + stamps(OX),
    'Frosted film all over, a clear window round the vial.')
add('frost-meta', 'Frosted Lightbox, Metabolic', '01', 'frosted', '#DCD8D2', BASEWIN + f'<div class="ink" style="{WINCLIP};opacity:.82">{lb("metabolic")}</div>' + wm_tall(1200, 1050, 1240, OX) + stamps(OX),
    'The Lightbox printed translucent over frosted film, window round the vial.')
add('frost-ox', 'Frosted Lightbox, Oxblood lane', '05', 'frosted', '#DCD8D2', BASEWIN + f'<div class="ink" style="{WINCLIP};opacity:.86">{lb("oxblood")}</div>' + wm_tall(1200, 1050, 1240, SNOW) + stamps(SNOW),
    'The Oxblood lane over frosted film, Snow type: the one generic bag.')
add('silver', 'Silver foil, window', '11', 'silver', '#DCD8D2', BASEWIN + wm_tall(1200, 1050, 1240, OX) + stamps(OX),
    'Metallised silver film with a clear window; Oxblood print.')
add('oxfoil', 'Oxblood foil, window', '01', 'oxfoil', '#DCD8D2', BASEWIN + wm_tall(1200, 1050, 1240, SNOW) + stamps(PINK),
    'Metallised film tinted Oxblood, clear window, Snow wordmark.')
add('lb-dermal', 'Full Lightbox, Dermal', '05', 'white', '#DCD8D2', BASEWIN + f'<div class="ink" style="{WINCLIP}">{lb("dermal")}</div>' + wm_tall(1200, 1050, 1240, OX) + stamps(OX),
    'Opaque Lightbox print (white underlay), window round the vial. One per area.')
add('tint-neuro', 'Tinted clear, Neuro', '11', 'clear', '#DCD8D2', f'<div class="ink" style="opacity:.5">{lb("neuro")}</div>' + wm_tall(1200, 1050, 1240, OX) + stamps(OX),
    'The Lightbox printed as tinted ink straight on clear film: the vial is seen through the colour.')
add('lane', 'Lane strip, Endocrine', '04', 'clear', '#DCD8D2',
    f'<div class="base" style="left:1010px;top:0;width:380px;height:2100px"></div><div class="ink" style="left:1010px;width:380px;right:auto">{lb("endocrine", 1, 6)}</div>' + wm_tall(1200, 1050, 1240, OX) + stamps(OX).split('<svg style="position:absolute;left:1075px')[0],
    'Clear bag, a Lightbox lane runs the full height behind the wordmark.')
lanes = ''.join(f'<div style="position:relative;flex:1">{lb(a, 1, 2)}</div>' for a in ('metabolic', 'dermal', 'endocrine', 'oxblood', 'tissue', 'neuro', 'supplies'))
add('index', 'The index, all areas', '09', 'clear', '#DCD8D2',
    f'<div class="base" style="left:150px;top:150px;width:120px;height:1800px"></div><div class="ink idx" style="left:150px;top:150px;width:120px;height:1800px">{lanes}</div>'
    + wm_tall(1200, 1050, 1240, OX) + stamps(OX, 290, 1420), 'Clear bag; seven lanes down the edge (six areas and Oxblood) as a colour index. Generic.')
wmmask = 'data:image/svg+xml,' + urllib.parse.quote(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1500 2100"><defs><mask id="m"><rect width="1500" height="2100" fill="#fff"/>'
                                                    f'<g transform="translate(650 1050) rotate(-90) translate({-1720/2} {-1720*50/WW:.1f}) scale({1720/WW:.4f})"><path fill="#000" fill-rule="evenodd" d="{WM["zuma"]}"/></g></mask></defs><rect width="1500" height="2100" mask="url(#m)"/></svg>')
# the knockout: lightbox everywhere except inside the letters; built as rect minus letters (letter counters stay printed)
KO = f"-webkit-mask:url('{wmmask}') 0 0/100% 100%"
add('letters', 'Through the letters', '01', 'white', '#DCD8D2',
    f'<div class="base" style="{KO}"></div><div class="ink" style="{KO}">{lb("oxblood", 3, 6)}</div>' + stamps(SNOW).replace('left:1080px;top:1720px', 'left:1150px;top:1720px'),
    'Oxblood Lightbox all over; the wordmark is the window, and the vial sits behind the letters.')

CSS = f'''html,body{{margin:0;width:1500px;height:2100px;background:transparent;overflow:hidden}} .pg{{position:relative;width:1500px;height:2100px}}
.base,.ink{{position:absolute;inset:0}} body:not(.mask) .base{{background:transparent}}
.blk{{position:absolute;transform:rotate(-90deg);transform-origin:0 0;border:4px solid;padding:18px 26px;font:600 38px/1.45 'IBM Plex Mono';letter-spacing:.1em;width:640px;margin-top:0}}
.blk .ln{{display:flex;gap:16px;align-items:flex-end}} .blk .ln i{{flex:1;border-bottom:3px solid;height:36px}} .blk .sm{{font-size:19px;margin-top:8px;letter-spacing:.14em}}
.qrb{{position:absolute;border:4px solid;padding:16px;font:600 15px 'IBM Plex Mono';letter-spacing:.12em;display:flex;flex-direction:column;align-items:center;gap:10px}}
.idx{{display:flex;flex-direction:column}}
body.mask{{background:#000}} body.mask .base{{background:#fff}} body.mask .ink, body.mask svg, body.mask .blk, body.mask .qrb{{visibility:hidden}}'''
for i, v in enumerate(V, 1):
    open(os.path.join(H, f'v-{i:02d}.html'), 'w').write(f'''<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@600&display=swap" rel="stylesheet"><style>{CSS}</style></head>
<body><script>if(location.search.includes('mask'))document.body.className='mask'</script><div class="pg">{v['body']}</div><script src="ombre.js"></script></body></html>''')
json.dump([{k: v[k] for k in ('key', 'name', 'no', 'film', 'ground', 'note')} for v in V], open(os.path.join(H, 'versions.json'), 'w'), indent=1)
print(len(V))

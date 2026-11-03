# Pouch round 3: twelve versions off the two winners (5 Tall type, one area per bag; 6 Tall type, Oxblood lane).
import os, json, base64, urllib.parse
H = os.path.dirname(os.path.abspath(__file__))
ns = {'__file__': os.path.join(H, 'build2.py')}
exec(open(os.path.join(H, 'build2.py')).read(), ns)          # helpers + css from round 2
wm, crest, bag, RUO, css, WM, WW, CD = ns['wm'], ns['crest'], ns['bag'], ns['RUO'], ns['css'], ns['WM'], ns['WW'], ns['CD']
OX, SNOW, PINK = '#6E1C2A', '#FCFBF8', '#E9C9CE'
SEEDS = {'metabolic': (3, 'palm', 5), 'dermal': (11, 'bamboo', 4), 'endocrine': (5, 'palm', 9), 'tissue': (14, 'bamboo', 6), 'neuro': (21, 'palm', 8), 'supplies': (34, 'bamboo', 7), 'oxblood': (8, 'palm', 12)}
DEEP = {'metabolic': '#0E5A8C', 'dermal': '#A8281F', 'endocrine': '#9A7A06', 'tissue': '#2F6E14', 'neuro': '#4B2A9A', 'supplies': '#3D4956', 'oxblood': '#3E0A15'}
NAME = {'metabolic': 'METABOLIC RESEARCH', 'dermal': 'DERMAL RESEARCH', 'endocrine': 'ENDOCRINE RESEARCH', 'tissue': 'TISSUE RESEARCH', 'neuro': 'NEURO RESEARCH', 'supplies': 'LAB SUPPLIES', 'oxblood': 'RESEARCH, REFINED'}
QR = json.load(open(os.path.join(H, 'qrlots.json')))
def lb(a, c=3, r=5, bars=0, st=''):
    s, b, bs = SEEDS[a]
    return f'<canvas data-lb="{a}" data-seed="{s}" data-cols="{c}" data-rows="{r}" data-bars="{bars}" data-behind="{b}" data-bseed="{bs}" style="position:absolute;inset:0;width:100%;height:100%;{st}"></canvas>'
TALL = 'position:absolute;left:-265px;top:358px;transform:rotate(-90deg)'          # the winning placement (730 long)
def side(text, c, right=58, top=520): return f'<div class="varea" style="color:{c};right:{right}px;top:{top}px">{text}</div>'
def stock(a, wmc, txtc, ruoc, extra='', wmst=TALL, wl=730, field=None, mark=True):
    face = f'<div class="fill">{field or lb(a)}</div>{wm(wl, wmc, wmst)}{side(NAME[a], txtc)}'
    if mark: face += crest(90, txtc, 'position:absolute;right:46px;top:82px')
    return face + extra + RUO(ruoc)
F = []
def add(face, cap, note): F.append(bag(face, cap, note))

# 1 · Snow on the area: the wordmark knocked to white on the Lightbox
add(stock('metabolic', SNOW, SNOW, 'rgba(252,251,248,.85)'), '1 · Snow on the area', 'Tall type in Snow on the area Lightbox. Metabolic shown.')
# 2 · Bleed: the wordmark bigger than the bag, cropped by the left edge and the seal
add(stock('tissue', OX, OX, OX, wmst='position:absolute;left:-520px;top:395px;transform:rotate(-90deg)', wl=1080, mark=True),
    '2 · Bleed', 'The wordmark is bigger than the bag and runs off the left edge. Tissue shown.')
# 3 · Mirror: the wordmark on the right reading top-down, the line on the left
add(f'<div class="fill">{lb("endocrine")}</div>{wm(730, OX, "position:absolute;left:-30px;top:358px;transform:rotate(90deg)")}'
    f'<div class="varea" style="color:{OX};left:58px;right:auto;top:520px;transform:translate(-50%,-50%) rotate(90deg)">{NAME["endocrine"]}</div>'
    f'{crest(90, OX, "position:absolute;left:46px;top:82px")}{RUO(OX)}', '3 · Mirror', 'Flipped: the wordmark reads top-down on the right. Endocrine shown.')
# 4 · Lit letters: the Oxblood lane bag; the letters are cut as windows onto an area Lightbox
mask = 'data:image/svg+xml,' + urllib.parse.quote(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WW} 100"><path fill-rule="evenodd" d="{WM["zuma"]}"/></svg>')
T = 730 * 100 / WW
add(f'<div class="fill">{lb("oxblood")}</div><div style="position:absolute;left:-265px;top:358px;width:730px;height:{T:.0f}px;transform:rotate(-90deg);-webkit-mask:url(\'{mask}\') 0 0/100% 100% no-repeat">{lb("neuro", 1, 2)}</div>'
    f'{side("NEURO RESEARCH", SNOW)}{crest(90, SNOW, "position:absolute;right:46px;top:82px")}{RUO("rgba(252,251,248,.85)")}',
    '4 · Lit letters', 'The Oxblood lane bag; the letters are windows onto the area Lightbox. Neuro shown.')
# 5 · Split: the area above, the Oxblood lane below, the wordmark crossing both
add(f'<div class="fill">{lb("metabolic")}</div><div style="position:absolute;left:0;right:0;bottom:0;height:330px;overflow:hidden">{lb("oxblood", 3, 1)}</div>'
    f'{wm(730, SNOW, TALL)}{side("METABOLIC RESEARCH", OX, 58, 400)}{crest(90, OX, "position:absolute;right:46px;top:82px")}{RUO("rgba(252,251,248,.85)")}',
    '5 · Split lane', 'The area on top, the Oxblood lane across the bottom, Snow wordmark crossing both.')
# 6 · Frosted window: a frosted clear panel shows the vial inside
vial = 'data:image/png;base64,' + base64.b64encode(open(os.path.join(os.path.dirname(H), 'stk', 'hero-vial-05.png'), 'rb').read()).decode()
add(stock('dermal', OX, OX, OX, extra=f'<div class="fwin"><img src="{vial}"></div>'),
    '6 · Frosted window', 'A frosted clear window over the vial: you see it inside, softly. Dermal shown.')
# 7 · Lab marks: the lot block, the sealed ring and the QR to the lot reports
q = f'<svg viewBox="-1 -1 {QR["n"]+2} {QR["n"]+2}" style="width:82px;height:82px;display:block" shape-rendering="crispEdges"><path fill="{OX}" d="{QR["p"]}"/></svg>'
marks = (f'<div class="lot" style="color:{OX};border-color:{OX}"><div>LOT <i></i></div><div>SEALED <i></i></div></div>'
         f'<div class="qrm" style="border-color:{OX};color:{OX}">{q}<span>ZUMATIDES.COM/LOTS</span></div>')
add(stock('supplies', OX, OX, OX, extra=marks), '7 · Lab marks', 'Adds a ruled lot block and a QR to the lot reports, stamped at packing. Lab supplies shown.')
# 8 · Tone on tone: the wordmark in the area's own deep tone, pressed in
add(stock('dermal', DEEP['dermal'], DEEP['dermal'], DEEP['dermal'], wmst=TALL + ';filter:drop-shadow(-2px -2px 0 rgba(255,255,255,.35)) drop-shadow(2px 2px 2px rgba(0,0,0,.25))'),
    '8 · Tone on tone', 'The wordmark in the deep tone of the area, as if pressed into the film. Dermal shown.')
# 9 · Oxblood, tone on tone
add(stock('oxblood', DEEP['oxblood'], SNOW, 'rgba(252,251,248,.8)', wmst=TALL + ';filter:drop-shadow(-2px -2px 0 rgba(255,255,255,.18)) drop-shadow(2px 2px 2px rgba(0,0,0,.3))'),
    '9 · Oxblood, tone on tone', 'The Oxblood lane with the wordmark pressed in deep Oxblood; Snow only for the small type.')
# 10 · Bars: the Lightbox with its Oxblood bars on, running under the letters
add(stock('tissue', OX, OX, OX, field=lb('tissue', 3, 5, 1), mark=False), '10 · With the bars', 'The Lightbox with its Oxblood bars on; they run into the letters (crest left off so nothing clashes). Tissue shown.')
# 11 · One bag, a seal per area: the Oxblood lane bag, the area's circle seal stuck on at packing
seal = 'data:image/png;base64,' + base64.b64encode(open('/home/user/MORELLOSIMS/zuma-content/stickers/print/zuma-sticker-seal-metabolic.png', 'rb').read()).decode()
add(stock('oxblood', SNOW, SNOW, 'rgba(252,251,248,.8)', mark=False, extra=f'<img src="{seal}" style="position:absolute;right:30px;top:72px;width:170px;transform:rotate(-8deg);filter:drop-shadow(0 4px 6px rgba(0,0,0,.3))">'),
    '11 · One bag, a seal per area', 'Stock only the Oxblood bag; the area\'s circle seal (we already have them) goes on at packing.')
# 12 · The set: seven bags side by side
mini = ''.join(f'<div class="mini">{"".join([f"<div class=fill>{lb(a)}</div>", wm(196, SNOW if a in ("oxblood",) else OX, "position:absolute;left:-62px;top:84px;transform:rotate(-90deg)")])}</div>'
               for a in ('metabolic', 'dermal', 'endocrine', 'tissue', 'neuro', 'supplies', 'oxblood'))
F.append(f'<figure style="width:600px"><div class="set">{mini}</div><figcaption><b>12 · The system</b><span>Six area bags and the Oxblood lane bag for mixed orders.</span></figcaption></figure>')

css3 = css + f'''
.fwin{{position:absolute;left:250px;top:250px;width:210px;height:420px;border-radius:105px;overflow:hidden;background:rgba(240,236,232,.55);backdrop-filter:blur(2px);box-shadow:inset 0 0 0 2px rgba(255,255,255,.35)}}
.fwin img{{position:absolute;width:520px;left:-170px;top:-30px;transform:rotate(6deg);filter:blur(7px);opacity:.85}}
.lot{{position:absolute;left:250px;top:705px;border:3px solid;padding:10px 14px;font:600 15px/1.7 'IBM Plex Mono';letter-spacing:.14em;width:170px}}
.lot div{{display:flex;gap:8px;align-items:flex-end}} .lot i{{flex:1;border-bottom:2px solid;height:16px}}
.qrm{{position:absolute;left:250px;top:560px;border:3px solid;padding:8px;display:flex;flex-direction:column;align-items:center;gap:6px;font:600 8px 'IBM Plex Mono';letter-spacing:.1em}}
.set{{display:flex;gap:10px;flex-wrap:wrap;width:600px}} .mini{{position:relative;width:140px;height:210px;border-radius:6px;overflow:hidden;box-shadow:0 10px 20px rgba(60,30,20,.2)}}'''
html = f'''<!doctype html><html><head><meta charset="utf-8"><title>ZUMA pouch round 3</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;800&family=IBM+Plex+Mono:wght@600&display=swap" rel="stylesheet"><style>{css3}</style></head><body>
<section><h2>POUCH · ROUND 3 · OFF THE WINNERS (TALL TYPE)</h2><div class="row">{''.join(F)}</div></section><script src="ombre.js"></script></body></html>'''
open(os.path.join(H, 'bags3.html'), 'w').write(html); print('ok', len(F))

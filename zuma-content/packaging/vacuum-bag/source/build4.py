# Style 10 (tall type with the Lightbox bars) across the set: six areas + the Oxblood lane, and the back.
import os, json
H = os.path.dirname(os.path.abspath(__file__))
ns = {'__file__': os.path.join(H, 'build3.py')}
exec(open(os.path.join(H, 'build3.py')).read(), ns)
wm, bag, RUO, css3, side, NAME, TALL, SEEDS, QR, crest = (ns[k] for k in ('wm', 'bag', 'RUO', 'css3', 'side', 'NAME', 'TALL', 'SEEDS', 'QR', 'crest'))
OX, SNOW = '#6E1C2A', '#FCFBF8'
RUO = lambda c: f'<div class="ruo2" style="color:{c}">For laboratory research use only. Not for human or veterinary use.</div>'
side = lambda *a, **k: ''
def lb(a, seed=None, c=3, r=5, bars=1):
    s, b, bs = SEEDS[a]
    return f'<canvas data-lb="{a}" data-seed="{seed or s}" data-cols="{c}" data-rows="{r}" data-bars="{bars}" data-behind="{b}" data-bseed="{bs}" style="position:absolute;inset:0;width:100%;height:100%"></canvas>'
# bars placed by hand: they run in from the right edge and stop clear of the letters, and never cross the side line (y 370-670)
BARS = {'metabolic': [(262, 300), (770, 380)], 'dermal': [(250, 262)], 'endocrine': [(256, 340), (730, 300)], 'tissue': [(250, 300)],
        'neuro': [(300, 360)], 'supplies': [(268, 280), (785, 430)], 'oxblood': [(270, 320)]}
def bars(a):
    c = '#3E0A15' if a == 'oxblood' else OX
    return ''.join(f'<div style="position:absolute;left:{x}px;right:0;top:{y}px;height:13px;background:{c}"></div>' for y, x in BARS[a])
CST = 'position:absolute;right:44px;top:84px'
AREAS = ['metabolic', 'dermal', 'endocrine', 'tissue', 'neuro', 'supplies', 'oxblood']
LABEL = {'metabolic': 'Metabolic', 'dermal': 'Dermal', 'endocrine': 'Endocrine', 'tissue': 'Tissue', 'neuro': 'Neuro', 'supplies': 'Lab supplies', 'oxblood': 'Oxblood · mixed orders'}
F = []
for a in AREAS:
    c = SNOW if a == 'oxblood' else OX
    F.append(bag(f'<div class="fill">{lb(a, bars=0)}</div>{bars(a)}{wm(730, c, TALL)}{side(NAME[a], c)}{crest(96, c, CST)}{RUO(c if a != "oxblood" else SNOW)}', LABEL[a], 'Front'))
# the back: same field, an Oxblood panel with the QR to the lot reports and a lot line
q = f'<svg viewBox="-1 -1 {QR["n"]+2} {QR["n"]+2}" style="width:170px;height:170px;display:block" shape-rendering="crispEdges"><rect x="-1" y="-1" width="{QR["n"]+2}" height="{QR["n"]+2}" fill="{SNOW}"/><path fill="{OX}" d="{QR["p"]}"/></svg>'
back = (f'<div class="fill">{lb("tissue", 61, bars=0)}</div><div class="bkp">{crest(70, SNOW, "margin:0 auto 22px")}<div class="bkt">Every lot tested.<br>Scan for the report.</div>{q}'
        f'<div class="bku">zumatides.com/lots</div><div class="bkl"><span>Lot</span><b></b></div></div>{RUO(OX)}')
F.append(bag(back, 'Back (every bag)', 'Same Lightbox as the front; an Oxblood panel carries the QR to the lot reports and a lot line to stamp.'))
css4 = css3 + f'''
.ruo2{{position:absolute;left:0;right:0;bottom:42px;text-align:center;font:500 13px Outfit}}
.bkp{{position:absolute;left:110px;right:110px;top:150px;background:{OX};padding:44px 40px 40px;display:flex;flex-direction:column;align-items:center}}
.bkt{{font:800 30px/1.2 Outfit;color:{SNOW};text-align:center;margin-bottom:24px}}
.bku{{margin-top:16px;font:500 20px Outfit;color:#E9C9CE}}
.bkl{{margin-top:30px;width:100%;display:flex;gap:14px;align-items:flex-end;font:500 18px Outfit;color:#E9C9CE}} .bkl b{{flex:1;border-bottom:2px solid rgba(233,201,206,.7);height:20px}}'''
html = f'''<!doctype html><html><head><meta charset="utf-8"><title>ZUMA pouch style 10</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;800&family=IBM+Plex+Mono:wght@600&display=swap" rel="stylesheet"><style>{css4}</style></head><body>
<section><h2>POUCH · STYLE 10 · THE SET</h2><div class="row">{''.join(F)}</div></section><script src="ombre.js"></script></body></html>'''
open(os.path.join(H, 'bags4.html'), 'w').write(html); print('ok', len(F))

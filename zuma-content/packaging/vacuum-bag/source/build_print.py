# Vacuum bag print files: the approved style 10 set, unchanged, at size. Finished bag 70 x 105 mm, 2 mm bleed all round (page 74 x 109 mm).
# The design is laid out on the 600 x 900 grid it was approved on (1 px = 70/600 mm) and scaled to millimetres; the Lightbox fields
# run into the bleed, type and marks stay where they were approved. Front and back per version, one PDF each.
import os, json
H = os.path.dirname(os.path.abspath(__file__))
ns = {'__file__': os.path.join(H, 'build4.py')}
exec(open(os.path.join(H, 'build4.py')).read(), ns)
wm, crest, TALL, CST, BARS, SEEDS, QR = (ns[k] for k in ('wm', 'crest', 'TALL', 'CST', 'BARS', 'SEEDS', 'QR'))
OX, SNOW, PINK = '#6E1C2A', '#FCFBF8', '#E9C9CE'
W_MM, H_MM, BLEED = 70.0, 105.0, 2.0
PX = W_MM / 600                      # mm per design px
B = BLEED / PX                       # bleed in design px
CSSMM = 96 / 25.4                    # css px per mm
SCALE = PX * CSSMM                   # design px -> css px
AREAS = ['metabolic', 'dermal', 'endocrine', 'tissue', 'neuro', 'supplies', 'oxblood']
NAME = {'metabolic': 'Metabolic', 'dermal': 'Dermal', 'endocrine': 'Endocrine', 'tissue': 'Tissue', 'neuro': 'Neuro', 'supplies': 'Lab supplies', 'oxblood': 'Oxblood'}
def field(a):
    s, b, bs = SEEDS[a]
    return f'<canvas data-lb="{a}" data-seed="{s}" data-cols="3" data-rows="5" data-bars="0" data-behind="{b}" data-bseed="{bs}" data-scale="3" style="position:absolute;inset:0;width:100%;height:100%"></canvas>'
RUO = lambda c: f'<div style="position:absolute;left:0;right:0;bottom:42px;text-align:center;font:500 13px Outfit;color:{c}">For laboratory research use only. Not for human or veterinary use.</div>'
def page(a, inner):
    return (f'<section class="pg"><div class="art" style="width:{600 + 2 * B:.2f}px;height:{900 + 2 * B:.2f}px;">'
            f'<div class="fld">{field(a)}</div>{inner}</div></section>')
def front(a):
    c = SNOW if a == 'oxblood' else OX
    bars = ''.join(f'<div style="position:absolute;left:{B + x:.2f}px;right:0;top:{B + y:.2f}px;height:13px;background:{"#3E0A15" if a == "oxblood" else OX}"></div>' for y, x in BARS[a])
    return page(a, f'{bars}<div class="d">{wm(730, c, TALL)}{crest(96, c, CST)}{RUO(c)}</div>')
def back(a):
    c = SNOW if a == 'oxblood' else OX
    q = f'<svg viewBox="-1 -1 {QR["n"]+2} {QR["n"]+2}" style="width:170px;height:170px;display:block" shape-rendering="crispEdges"><rect x="-1" y="-1" width="{QR["n"]+2}" height="{QR["n"]+2}" fill="{SNOW}"/><path fill="{OX}" d="{QR["p"]}"/></svg>'
    panel = (f'<div class="bkp">{crest(70, SNOW, "margin:0 auto 22px")}<div class="bkt">Every lot tested.<br>Scan for the report.</div>{q}'
             f'<div class="bku">zumatides.com/lots</div><div class="bkl"><span>Lot</span><b></b></div></div>')
    return page(a, f'<div class="d">{panel}{RUO(c)}</div>')
CSS = f'''html,body{{margin:0;padding:0}}
.pg{{width:{600 + 2 * B:.2f}px;height:{900 + 2 * B:.2f}px;position:relative;overflow:hidden}}
.art{{position:absolute;left:0;top:0;transform-origin:0 0;overflow:hidden}} .fld{{position:absolute;inset:0}}
.d{{position:absolute;left:{B:.2f}px;top:{B:.2f}px;width:600px;height:900px}}
.bkp{{position:absolute;left:110px;right:110px;top:150px;background:{OX};padding:44px 40px 40px;display:flex;flex-direction:column;align-items:center}}
.bkt{{font:800 30px/1.2 Outfit;color:{SNOW};text-align:center;margin-bottom:24px}}
.bku{{margin-top:16px;font:500 20px Outfit;color:{PINK}}}
.bkl{{margin-top:30px;width:100%;display:flex;gap:14px;align-items:flex-end;font:500 18px Outfit;color:{PINK}}} .bkl b{{flex:1;border-bottom:2px solid rgba(233,201,206,.7);height:20px}}'''
OUT = os.path.join(H, 'print'); os.makedirs(OUT, exist_ok=True)
for a in AREAS:
    open(os.path.join(OUT, f'bag-{a}.html'), 'w').write(f'''<!doctype html><html><head><meta charset="utf-8"><title>ZUMA vacuum bag · {NAME[a]}</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;800&display=swap" rel="stylesheet"><style>{CSS}</style></head><body>
{front(a)}{back(a)}<script src="../ombre.js"></script></body></html>''')
json.dump({'areas': AREAS, 'w': W_MM, 'h': H_MM, 'bleed': BLEED}, open(os.path.join(OUT, 'meta.json'), 'w'))
print('ok', len(AREAS))

# The mixed bag after Casa Loewe: separate Lightbox fields of different sizes on a cream ground, cream gaps between,
# the type sits in the cream. Each field is one area (never blended); the Oxblood bars live inside the big field only.
import os
H = os.path.dirname(os.path.abspath(__file__))
ns = {'__file__': os.path.join(H, 'build4.py')}
exec(open(os.path.join(H, 'build4.py')).read(), ns)
wm, bag, RUO, css4, TALL, crest, lb = (ns[k] for k in ('wm', 'bag', 'RUO', 'css4', 'TALL', 'crest', 'lb'))
OX, SNOW, CREAM = '#6E1C2A', '#FCFBF8', '#F3EADC'
def field(a, x, y, w, h, c=3, r=3, bars=0, seed=None):
    return f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;overflow:hidden">{lb(a, seed, c, r, bars)}</div>'
def cream(x, y, w, h): return f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:{CREAM}"></div>'
def wmh(x, y, w, c=OX): return wm(w, c, f'position:absolute;left:{x}px;top:{y}px')
def ruo(x, y, c=OX, al='left', w=260): return f'<div style="position:absolute;left:{x}px;top:{y}px;font:500 12px/1.35 Outfit;color:{c};text-align:{al};width:{w}px">For laboratory research use only.<br>Not for human or veterinary use.</div>'
GROUND = f'<div class="fill" style="background:{CREAM}"></div>'
F = []
# L1 · the poster: a narrow Dermal column top left, a Tissue block top right, the wordmark in the cream between,
#      Metabolic as the big field below with its bars, two cream tiles left out at the bottom right
L1 = (GROUND + field('dermal', 0, 0, 104, 360, 2, 3) + field('tissue', 438, 0, 162, 360, 3, 3)
      + field('metabolic', 0, 374, 600, 526, 5, 4, 1, 17) + cream(318, 742, 282, 22) + cream(300, 862, 300, 38)
      + crest(64, OX, 'position:absolute;left:138px;top:92px') + wmh(136, 176, 276) + ruo(138, 272))
F.append(bag(L1, 'L1 · The poster', 'Three areas as separate fields on cream: a narrow Dermal column, a Tissue block, Metabolic below with the bars.'))
# L2 · the Oxblood lane as the big field; Endocrine and Neuro as the two accents
L2 = (GROUND + field('neuro', 0, 0, 170, 330, 2, 3) + field('endocrine', 496, 0, 104, 330, 1, 3)
      + field('oxblood', 0, 344, 600, 556, 5, 4, 1, 23) + cream(0, 760, 250, 22) + cream(420, 856, 180, 44)
      + crest(64, OX, 'position:absolute;left:204px;top:92px') + wmh(202, 176, 262) + ruo(204, 268))
F.append(bag(L2, 'L2 · Oxblood below', 'The Oxblood lane as the big field, two areas as accents above, the wordmark in the cream.'))
# L3 · tall type in a cream column; the areas stacked as fields down the right, cream gaps between
L3 = (GROUND + wm(730, OX, TALL) + field('tissue', 236, 0, 364, 250, 3, 2) + field('dermal', 236, 264, 364, 280, 3, 3, 1, 31)
      + field('metabolic', 236, 558, 240, 342, 2, 3) + field('neuro', 490, 558, 110, 342, 1, 3)
      + crest(90, OX, 'position:absolute;right:44px;top:84px') + ruo(22, 832, OX, 'left', 200))
F.append(bag(L3, 'L3 · Tall type, on cream', 'The winning tall wordmark in a cream column; four areas stacked as fields beside it.'))
# L4 · all six as one wall of fields with cream gaps; the wordmark in a cream band across the top
cols = [('metabolic', 0, 196), ('dermal', 210, 120), ('endocrine', 344, 256)]
row2 = [('tissue', 0, 300), ('neuro', 314, 140), ('supplies', 468, 132)]
L4 = (GROUND + ''.join(field(a, x, 300, w, 290, 2, 3) for a, x, w in cols) + ''.join(field(a, x, 604, w, 296, 2, 3, 1 if a == 'tissue' else 0, 41) for a, x, w in row2)
      + crest(64, OX, 'position:absolute;left:64px;top:96px') + wmh(150, 100, 300) + ruo(152, 196))
F.append(bag(L4, 'L4 · The wall', 'All six areas as their own fields, cream gaps between, the wordmark in the cream above.'))
html = f'''<!doctype html><html><head><meta charset="utf-8"><title>ZUMA mixed bag, Loewe</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;800&family=IBM+Plex+Mono:wght@600&display=swap" rel="stylesheet"><style>{css4}</style></head><body>
<section><h2>POUCH · THE MIXED BAG · AFTER CASA LOEWE</h2><div class="row">{''.join(F)}</div></section><script src="ombre.js"></script></body></html>'''
open(os.path.join(H, 'bags6.html'), 'w').write(html); print('ok', len(F))

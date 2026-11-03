# The mixed bag, three takes (style 10 grammar: tall wordmark, crest top right, side line, Oxblood bars as seams). Areas never blend.
import os
H = os.path.dirname(os.path.abspath(__file__))
ns = {'__file__': os.path.join(H, 'build4.py')}
exec(open(os.path.join(H, 'build4.py')).read(), ns)
wm, bag, RUO, css4, side, NAME, TALL, crest, lb, CST, BARS, bars = (ns[k] for k in ('wm', 'bag', 'RUO', 'css4', 'side', 'NAME', 'TALL', 'crest', 'lb', 'CST', 'BARS', 'bars'))
OX, SNOW = '#6E1C2A', '#FCFBF8'
def clip(a, poly, seed=None, c=3, r=5):
    return f'<div class="fill" style="clip-path:polygon({poly})">{lb(a, seed, c, r, bars=0)}</div>'
def seam(x1, y1, x2, y2, w=13, c=OX):
    import math
    L = math.hypot(x2 - x1, y2 - y1); ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
    return f'<div style="position:absolute;left:{x1}px;top:{y1 - w/2}px;width:{L:.0f}px;height:{w}px;background:{c};transform-origin:0 50%;transform:rotate({ang:.2f}deg)"></div>'
def SEAMS(h): return f'<div class="fill" style="clip-path:polygon(222px 0,600px 0,600px 838px,222px 838px)">{h}</div>'
def front(field, wmc=OX, line='RESEARCH, REFINED', extra=''):
    return f'{field}{extra}{wm(730, wmc, TALL)}{side(line, wmc) if line else ""}{crest(96, wmc, CST)}{RUO(wmc)}'
F = []
# A · Two-faced: dermal on the front, metabolic on the back, same layout on both
F.append(bag(front(f'<div class="fill">{lb("dermal", bars=0)}</div>' + bars('dermal')), 'A · Two-faced · front', 'One area on the front...'))
F.append(bag(front(f'<div class="fill">{lb("metabolic", bars=0)}</div>' + bars('metabolic')), 'A · Two-faced · back', '...another on the back. Mixed orders get a pairing.'))
# B · Split: two areas side by side, the seam is an Oxblood bar, the wordmark crosses it
B = clip('endocrine', '0 0,300px 0,300px 900px,0 900px') + clip('neuro', '300px 0,600px 0,600px 900px,300px 900px') + SEAMS(seam(300, 0, 300, 900))
F.append(bag(front(B), 'B · Split', 'Two areas, one bag: the Oxblood seam down the middle, the wordmark over both.'))
# B2 · Split on the diagonal
B2 = clip('tissue', '0 0,600px 0,600px 330px,0 640px') + clip('oxblood', '0 640px,600px 330px,600px 900px,0 900px') + SEAMS(seam(0, 640, 600, 330))
F.append(bag(front(B2, SNOW, None), 'B · Split, diagonal', 'The area above, the Oxblood lane below, cut on a slope.'))
# C · Patchwork: all six areas and Oxblood as panels; the bars are the seams
P = [('metabolic', '0 0,330px 0,280px 300px,0 340px'), ('dermal', '330px 0,600px 0,600px 260px,280px 300px'),
     ('endocrine', '0 340px,280px 300px,330px 560px,0 610px'), ('neuro', '280px 300px,600px 260px,600px 520px,330px 560px'),
     ('tissue', '0 610px,330px 560px,250px 900px,0 900px'), ('supplies', '330px 560px,600px 520px,600px 900px,250px 900px')]
C = ''.join(clip(a, p) for a, p in P) + SEAMS(seam(330, 0, 280, 300) + seam(0, 340, 600, 260) + seam(280, 300, 330, 560) + seam(0, 610, 600, 520) + seam(330, 560, 250, 900))
F.append(bag(front(C, OX, None), 'C · Patchwork', 'All six areas as cut panels; the Oxblood bars are the seams. Every area stays its own.'))
# C2 · Patchwork, calmer: three wide bands
C2 = clip('metabolic', '0 0,600px 0,600px 300px,0 300px') + clip('dermal', '0 300px,600px 300px,600px 600px,0 600px') + clip('tissue', '0 600px,600px 600px,600px 900px,0 900px') + SEAMS(seam(0, 300, 600, 300) + seam(0, 600, 600, 600))
F.append(bag(front(C2, OX, None), 'C · Bands', 'Calmer: three areas stacked, bars as the seams. Any three per order.'))
html = f'''<!doctype html><html><head><meta charset="utf-8"><title>ZUMA mixed bag</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;800&family=IBM+Plex+Mono:wght@600&display=swap" rel="stylesheet"><style>{css4}</style></head><body>
<section><h2>POUCH · STYLE 10 · THE MIXED BAG</h2><div class="row">{''.join(F)}</div></section><script src="ombre.js"></script></body></html>'''
open(os.path.join(H, 'bags5.html'), 'w').write(html); print('ok', len(F))

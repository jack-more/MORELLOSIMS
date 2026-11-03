# The PE kit: a white tee with the collar and sleeve cuffs in an area colour and a small Oxblood crest on the chest,
# worn with the mesh short and Cap B in the same area colour.
import os
H = os.path.dirname(os.path.abspath(__file__))
ns = {'__file__': os.path.join(H, 'build.py')}; exec(open(os.path.join(H, 'build.py')).read(), ns)
crest, wm, shorts, hat, AREA, OX, SNOW, LINE, STITCH, CSS = (ns[k] for k in ('crest', 'wm', 'shorts', 'hat', 'AREA', 'OX', 'SNOW', 'LINE', 'STITCH', 'CSS'))
BODY = 'M160 44 {neck} 240 44 L272 52 L360 132 L330 168 L296 150 L300 420 Q200 428 100 420 L104 150 L70 168 L40 132 L128 52 Z'
def kit_tee(col, back=False):
    neck = 'Q200 58' if back else 'Q200 84'
    path = BODY.format(neck=neck)
    cuffL = '<path d="M40 132 L70 168 L82 156 L53 120 Z" fill="%s" %s/>' % (col, LINE)
    cuffR = '<path d="M360 132 L330 168 L318 156 L347 120 Z" fill="%s" %s/>' % (col, LINE)
    art = wm(181, 74, 38, OX) if back else crest(232, 118, 30, OX)
    return (f'<svg viewBox="0 0 400 450" class="g"><path d="{path}" fill="{SNOW}" {LINE}/>{cuffL}{cuffR}'
            f'<path d="M160 44 {neck} 240 44" fill="none" stroke="{col}" stroke-width="13" stroke-linecap="round"/>'
            f'<path d="M160 44 {neck} 240 44" fill="none" {LINE}/>{art}'
            f'<path d="M104 150 L128 56 M296 150 L272 56" {STITCH}/><path d="M104 410 Q200 418 296 410" {STITCH}/></svg>')
def mesh(col):
    return shorts(col, '<path d="M70 40 L96 40 L74 262 L50 260 Z" fill="%s"/><path d="M304 40 L330 40 L350 260 L326 262 Z" fill="%s"/>' % (OX, OX)
                  + crest(104, 196, 34, SNOW) + ''.join(f'<circle cx="{x}" cy="{y}" r="1.1" fill="#000" opacity=".12"/>' for x in range(60, 345, 9) for y in range(70, 262, 9)), OX)
def cap(col): return hat(SNOW, col, crest(176, 104, 48, col), col)
cards = [f'<figure><div class="pair">{kit_tee(AREA["metabolic"])}{kit_tee(AREA["metabolic"], True)}</div><figcaption><b>PE kit tee</b>'
         f'<span>White heavyweight tee. The collar and sleeve cuffs in the area colour, a small crest on the chest and the ZUMA wordmark at the nape, both in Oxblood. Metabolic blue shown, one per area.</span></figcaption></figure>']
for a in ('metabolic', 'tissue', 'dermal'):
    c = AREA[a]
    cards.append(f'<figure><div class="kit">{cap(c)}{kit_tee(c)}{mesh(c)}</div><figcaption><b>The kit · {a.capitalize()}</b>'
                 f'<span>Cap B, the PE kit tee and the mesh short in one area colour.</span></figcaption></figure>')
css = CSS + '.kit{display:flex;flex-direction:column;align-items:center;gap:6px}.kit .g{max-height:250px}'
html = f'''<!doctype html><html><head><meta charset="utf-8"><title>ZUMA PE kit</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;800&display=swap" rel="stylesheet"><style>{css}</style></head><body>
<section><h2>The PE kit</h2><div class="row" style="grid-template-columns:2fr 1fr 1fr 1fr">{''.join(cards)}</div></section></body></html>'''
open(os.path.join(H, 'kit.html'), 'w').write(html); print('ok')

# Round stickers. No borders, die-cut on the circle, brand sans only.
#  Compound rounds (38 mm): the research colour solid (the vial label's colour), the crest and the name in Oxblood, the area small.
#  Throw-ins (50 mm): zumatides.com set round the edge in the brand sans, the crest or the wordmark in the middle.
import json, os, re
H = os.path.dirname(os.path.abspath(__file__))
WM = json.load(open('/home/user/MORELLOSIMS/zuma-content/brand/wordmark/tides.json')); WW = WM['zuma_w']
CD = re.search(r' d="([^"]+)"', open('/home/user/MORELLOSIMS/zuma-content/packaging/capsule-case/zuma-crest-stamp.svg').read()).group(1)
OX, SNOW = '#6E1C2A', '#FCFBF8'
COL = {'metabolic': '#36B3E8', 'dermal': '#FF6A55', 'endocrine': '#F4D63A', 'tissue': '#6CC93A', 'neuro': '#A57BF0', 'zuma': '#9AA8B6'}
P = [('RT-3', 'metabolic', 'Metabolic research'), ('TZ-2', 'metabolic', 'Metabolic research'), ('BAC water', 'zuma', 'Bacteriostatic water'),
     ('Tesamorelin', 'endocrine', 'Endocrine research'), ('GHK-Cu', 'dermal', 'Dermal research'), ('MOTS-c', 'metabolic', 'Metabolic research'),
     ('CJC+IPA', 'endocrine', 'Endocrine research'), ('NAD+', 'metabolic', 'Metabolic research'), ('BPC+TB', 'tissue', 'Tissue research'),
     ('KLOW', 'dermal', 'Dermal research'), ('Selank', 'neuro', 'Neuro research'), ('Semax', 'neuro', 'Neuro research')]
def crest(cx, cy, w, c): return f'<g transform="translate({cx - w/2} {cy - w*100/104.26/2}) scale({w/104.26})"><path fill="{c}" fill-rule="evenodd" d="{CD}"/></g>'
def wm(cx, cy, w, c): return f'<g transform="translate({cx - w/2} {cy - w*50/WW}) scale({w/WW})"><path fill="{c}" fill-rule="evenodd" d="{WM["zuma"]}"/></g>'
def compound(name, area, line):
    c = COL[area]; fs = min(150, 1500 / max(len(name), 4) * 0.62)
    return (f'<svg viewBox="0 0 760 760" class="r"><circle cx="380" cy="380" r="380" fill="{c}"/>' + crest(380, 210, 170, OX)
            + f'<text x="380" y="{420 + fs * 0.32:.0f}" text-anchor="middle" font-family="Outfit" font-weight="800" font-size="{fs:.0f}" fill="{OX}">{name}</text>'
            + f'<text x="380" y="560" text-anchor="middle" font-family="Outfit" font-weight="600" font-size="44" fill="{OX}">{line}</text></svg>')
def ring_text(r, text, c, size, start=90, k=0):
    # the address round the bottom, reading left to right
    return (f'<defs><path id="t{k}" d="M{500 - r} 500 A{r} {r} 0 0 0 {500 + r} 500"/></defs>'
            f'<text font-family="Outfit" font-weight="700" font-size="{size}" fill="{c}" letter-spacing="2" text-anchor="middle"><textPath href="#t{k}" startOffset="50%">{text}</textPath></text>')
def throw(kind, k):
    if kind == 'ox':      # Oxblood disc, Snow crest, the address round the bottom
        body = f'<circle cx="500" cy="500" r="500" fill="{OX}"/>' + crest(500, 430, 430, SNOW) + ring_text(420, 'zumatides.com', SNOW, 84, k=k)
    elif kind == 'snow':  # Snow disc, the wordmark big, the address under it
        body = f'<circle cx="500" cy="500" r="500" fill="{SNOW}"/>' + wm(500, 470, 680, OX) + f'<text x="500" y="640" text-anchor="middle" font-family="Outfit" font-weight="700" font-size="72" fill="{OX}">zumatides.com</text>'
    else:                 # a research colour, Oxblood crest, the address round the bottom
        body = f'<circle cx="500" cy="500" r="500" fill="{COL[kind]}"/>' + crest(500, 430, 430, OX) + ring_text(420, 'zumatides.com', OX, 84, k=k)
    return f'<svg viewBox="0 0 1000 1000" class="t">{body}</svg>'
comp = ''.join(f'<figure>{compound(*p)}</figure>' for p in P)
thr = ''.join(f'<figure>{throw(k, i)}</figure>' for i, k in enumerate(['ox', 'snow', 'metabolic', 'dermal', 'endocrine', 'tissue', 'neuro']))
CSS = '''body{margin:0;background:#E7E3DC;font-family:Outfit} section{padding:60px 70px} h2{font:800 40px Outfit;color:#6E1C2A;margin:0 0 8px} p{font:500 22px Outfit;color:#5A4448;margin:0 0 34px}
.grid{display:flex;flex-wrap:wrap;gap:36px} figure{margin:0} .r{width:300px;height:300px;filter:drop-shadow(0 10px 14px rgba(60,30,20,.22))} .t{width:330px;height:330px;filter:drop-shadow(0 10px 14px rgba(60,30,20,.22))}'''
open(os.path.join(H, 'round.html'), 'w').write(f'''<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@600;700;800&display=swap" rel="stylesheet"><style>{CSS}</style></head><body>
<section><h2>Compound rounds</h2><p>38 mm, the research colour of each vial label, the crest and the name in Oxblood. BAC water in ZUMA grey.</p><div class="grid">{comp}</div></section>
<section><h2>Throw-ins</h2><p>50 mm, for orders: zumatides.com on every one. Oxblood, Snow, and the five research colours.</p><div class="grid">{thr}</div></section></body></html>''')
print('ok')

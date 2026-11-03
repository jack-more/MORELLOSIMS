# Compound stickers: Snow, the name in Oxblood (brand sans, Outfit 800), corners rounded. Two sizes:
#   bag 26 x 10 mm: name + the research area (BAC water: Bacteriostatic water)
#   box 14 x 6 mm:  name only (sits on the 20 mm box front)
# 1 mm bleed all round in the files; the cut line is the rounded rectangle at trim (README states size and radius).
import os, json
H = os.path.dirname(os.path.abspath(__file__))
P = [('01', 'RT-3', 'Metabolic research'), ('02', 'TZ-2', 'Metabolic research'), ('03', 'BAC water', 'Bacteriostatic water'),
     ('04', 'Tesamorelin', 'Endocrine research'), ('05', 'GHK-Cu', 'Dermal research'), ('06', 'MOTS-c', 'Metabolic research'),
     ('07', 'CJC+IPA', 'Endocrine research'), ('08', 'NAD+', 'Metabolic research'), ('09', 'BPC+TB', 'Tissue research'),
     ('10', 'KLOW', 'Dermal research'), ('11', 'Selank', 'Neuro research'), ('12', 'Semax', 'Neuro research')]
SIZES = {'bag': (26.0, 10.0, 1.6), 'box': (14.0, 6.0, 1.0)}   # w, h, corner radius (mm)
BLEED = 1.0
PX = 40   # css px per mm in the layout (screenshot scale brings it to 600 dpi)
OX, SNOW = '#6E1C2A', '#FCFBF8'
pages = []
for size, (w, h, r) in SIZES.items():
    for no, name, line in P:
        W, Hh = (w + 2 * BLEED) * PX, (h + 2 * BLEED) * PX
        if size == 'bag':
            inner = (f'<div class="n" style="font-size:{min(5.2, 22.0 / max(len(name), 4) * 1.55) * PX:.0f}px">{name}</div>'
                     f'<div class="l" style="font-size:{1.55 * PX:.0f}px">{line}</div>')
        else:
            inner = f'<div class="n" style="font-size:{min(3.2, 11.4 / max(len(name), 4) * 1.45) * PX:.0f}px">{name}</div>'
        pages.append(f'<div class="pg" id="{size}-{no}" style="width:{W:.0f}px;height:{Hh:.0f}px"><div class="s" style="left:{BLEED*PX}px;top:{BLEED*PX}px;width:{w*PX}px;height:{h*PX}px;border-radius:{r*PX}px">{inner}</div></div>')
CSS = f'''body{{margin:0;background:#fff}} .pg{{position:relative;background:{SNOW};margin:0 0 20px}}
.s{{position:absolute;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:{0.5*PX}px;color:{OX}}}
.n{{font-family:Outfit;font-weight:800;line-height:1;letter-spacing:.01em;white-space:nowrap}} .l{{font-family:Outfit;font-weight:500;line-height:1}}
body.cut .s{{outline:2px solid #e0007a;outline-offset:0}}'''
open(os.path.join(H, 'stickers.html'), 'w').write(f'''<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;800&display=swap" rel="stylesheet"><style>{CSS}</style></head>
<body><script>if(location.search.includes('cut'))document.body.className='cut'</script>{''.join(pages)}</body></html>''')
json.dump({'P': P, 'SIZES': SIZES, 'BLEED': BLEED, 'PX': PX}, open(os.path.join(H, 'meta.json'), 'w'))
print('ok', len(pages))

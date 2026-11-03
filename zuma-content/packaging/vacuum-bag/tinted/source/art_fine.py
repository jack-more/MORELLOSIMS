# Fine-print front: clear Oxblood-tinted film, Snow print only (logos, hairlines, small copy). No sticker.
# 70 x 105 mm at 20 px/mm. The vial sits centre, a little low (VY 0.8 cm): keep x 520-880, y 820-1600 clear of print.
import json, os, re
H = os.path.dirname(os.path.abspath(__file__))
WM = json.load(open('/home/user/MORELLOSIMS/zuma-content/brand/wordmark/tides.json')); WW = WM['zuma_w']
CD = re.search(r' d="([^"]+)"', open('/home/user/MORELLOSIMS/zuma-content/packaging/capsule-case/zuma-crest-stamp.svg').read()).group(1)
SN = '#FCFBF8'
def wm(x, y, w, st=''): return f'<svg viewBox="0 0 {WW} 100" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{w*100/WW:.1f}px;{st}"><path fill="{SN}" fill-rule="evenodd" d="{WM["zuma"]}"/></svg>'
def crest(x, y, w): return f'<svg viewBox="0 0 104.26 100" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{w*100/104.26:.1f}px"><path fill="{SN}" fill-rule="evenodd" d="{CD}"/></svg>'
def t(x, y, txt, size=26, w=None, weight=500, align='left', st=''):
    ww = f'width:{w}px;' if w else 'white-space:nowrap;'
    return f'<div style="position:absolute;left:{x}px;top:{y}px;{ww}font:{weight} {size}px/1.38 Outfit;color:{SN};text-align:{align};{st}">{txt}</div>'
def rule(x, y, w, h=3): return f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:{SN}"></div>'
BLURB = ('ZUMA makes research peptides for laboratories. Each vial is filled, capped and sealed under vacuum in this bag, '
         'and every lot is tested before it ships. The report for your lot is at zumatides.com/lots. '
         'Store the sealed bag cold, dry and out of the light. Open at the notch. '
         'For laboratory research use only. Not for human or veterinary use. Keep out of reach of children.')
P = [
  t(1000, 120, 'zumatides.com', 28),
  crest(640, 290, 120),
  wm(450, 450, 500),
  t(0, 600, 'Research peptides, tested by lot', 34, w=1400, align='center'),
  rule(600, 680, 200),
  # the blurb set on its side up the left edge, like a folded leaflet seen through the film
  f'<div style="position:absolute;left:-380px;top:1150px;width:1000px;transform:rotate(-90deg)">'
  + f'<div style="font:600 30px/1.3 Outfit;color:{SN};margin-bottom:14px">ZUMA research peptides</div>'
  + f'<div style="font:500 22px/1.42 Outfit;color:{SN}">{BLURB}</div></div>',
  rule(330, 700, 3, 1000) if False else '',
  # right column: lot box
  t(1010, 1180, 'Lot', 26), rule(1010, 1230, 240, 3),
  t(1010, 1260, 'Packed', 26), rule(1010, 1310, 240, 3),
  # bottom
  rule(120, 1840, 1160, 3),
  t(120, 1866, 'For laboratory research use only. Not for human or veterinary use.', 24),
  t(120, 1904, 'ZUMA vacuum pack, 70 x 105 mm', 24),
  t(1280, 1904, 'zumatides.com', 24, st='transform:translateX(-100%)'),
]
open(os.path.join(H, 'c-fine.html'), 'w').write(f'''<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;800&display=swap" rel="stylesheet">
<style>html,body{{margin:0;width:1400px;height:2100px;background:transparent;overflow:hidden}}.pg{{position:relative;width:1400px;height:2100px}}</style></head>
<body><div class="pg">{"".join(P)}</div></body></html>''')
print('ok')

# SKU A (red): the tall ZUMA up the left (style 10), the crest top right, fine print round the vial. Snow print on the tinted film.
# The vial sits right of centre (VX 0.6 cm): keep x 640-1000, y 820-1600 clear.
import os
H = os.path.dirname(os.path.abspath(__file__))
ns = {'__file__': os.path.join(H, 'art_fine.py')}
src = open(os.path.join(H, 'art_fine.py')).read(); src = src[:src.index('P = [')]
exec(src, ns); wm, crest, t, rule, SN, BLURB, WW = ns['wm'], ns['crest'], ns['t'], ns['rule'], ns['SN'], ns['BLURB'], ns['WW']
P = [
  wm(-540, 870, 1500, 'transform:rotate(-90deg)'),
  crest(1130, 110, 150),
  t(1205, 290, 'zumatides.com', 26, st='transform:translateX(-50%)'),
  # the blurb on its side down the right edge
  f'<div style="position:absolute;left:820px;top:1100px;width:900px;transform:rotate(90deg)">'
  + f'<div style="font:600 28px/1.3 Outfit;color:{SN};margin-bottom:12px">ZUMA research peptides</div>'
  + f'<div style="font:500 21px/1.42 Outfit;color:{SN}">{BLURB}</div></div>',
  t(470, 560, 'Research peptides,<br>tested by lot', 34, weight=600),
  rule(470, 680, 160),
  rule(470, 1840, 830, 3),
  t(470, 1866, 'For laboratory research use only.<br>Not for human or veterinary use.', 23),
  t(470, 1950, 'ZUMA vacuum pack, 70 x 105 mm', 23),
  t(1010, 1866, 'Lot', 23), rule(1060, 1890, 240, 3),
  t(1010, 1912, 'Packed', 23), rule(1100, 1936, 200, 3),
]
open(os.path.join(H, 'c-big.html'), 'w').write(f'''<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;800&display=swap" rel="stylesheet">
<style>html,body{{margin:0;width:1400px;height:2100px;background:transparent;overflow:hidden}}.pg{{position:relative;width:1400px;height:2100px}}</style></head>
<body><div class="pg">{"".join(P)}</div></body></html>''')
print('ok')

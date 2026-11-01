# Two sticker directions, one sticker each, 70 x 100 mm (1 mm = 10 css px). Built from the site's own parts: ombre.js (stucco + palm
# shadow, the Lightbox field), the logo symbols, a real vial render. Brand rules kept: logo Oxblood on Stucco/Snow, never on the tile.
import json, os, base64
H = os.path.dirname(os.path.abspath(__file__))
defs = open('/home/user/MORELLOSIMS/zuma-content/brand/logo-defs.svg').read()
qr = json.load(open(os.path.join(H, 'qr.json')))
vial = 'data:image/png;base64,' + base64.b64encode(open(os.path.join(H, 'hero-vial-01.png'), 'rb').read()).decode()
OX, SNOW, STUCCO = '#6E1C2A', '#FCFBF8', '#EFE4D2'
SKY = ['#BFE8FB', '#36B3E8', '#0E5A8C']
def qrsvg(size, fill):
    n = qr['n']
    return f'<svg viewBox="-2 -2 {n + 4} {n + 4}" style="width:{size}px;height:{size}px;display:block" shape-rendering="crispEdges"><path fill="{fill}" d="{qr["p"]}"/></svg>'

A = f'''<div class="st"><canvas class="wall" data-shadow="palm" data-seed="6"></canvas>
  <svg class="logo" style="color:{OX}"><use href="#zuma-logo"/></svg>
  <div class="win"><canvas data-lb="metabolic" data-seed="3" data-cols="4" data-rows="4" data-bars="1" data-behind="palm" data-bseed="5"></canvas></div>
  <img class="vial" src="{vial}">
  <div class="url">zumatides.com</div>
  <div class="foot">{qrsvg(150, OX)}<div class="line">Research,<br>refined.</div></div>
</div>'''

# B: the same layout, flat. Tiles in the area's three tones, Oxblood bars, Snow ground. No imagery.
tiles = [  # x, y, w, h, tone (0 light, 1 bright, 2 deep, 3 mid)
    (0, 0, 230, 200, 1), (240, 0, 120, 200, 0), (370, 0, 190, 90, 2), (370, 100, 190, 100, 3),
    (0, 210, 110, 300, 0), (120, 210, 240, 300, 1), (370, 210, 90, 300, 3), (470, 210, 90, 300, 0)]
def mix(a, b, t):
    a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]; b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join('%02x' % round(x + (y - x) * t) for x, y in zip(a, b))
TONE = [SKY[0], SKY[1], SKY[2], mix(SKY[1], SKY[0], .45)]
flat = ''.join(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{TONE[t]}"/>' for x, y, w, h, t in tiles)
flat += f'<rect x="120" y="196" width="440" height="18" fill="{OX}"/><rect x="0" y="352" width="360" height="14" fill="{OX}"/>'
B = f'''<div class="st flat"><svg class="logo" style="color:{OX}"><use href="#zuma-logo"/></svg>
  <svg class="win" viewBox="0 0 560 510" preserveAspectRatio="none" style="height:460px">{flat}</svg>
  <div class="url">zumatides.com</div>
  <div class="foot">{qrsvg(150, OX)}<div class="line">Research,<br>refined.</div></div>
</div>'''

css = f'''body{{margin:0;background:#E3DACD;font-family:Outfit,sans-serif}} .row{{display:flex;gap:90px;padding:70px 90px;align-items:flex-start}}
figure{{margin:0}} figcaption{{font:600 20px 'IBM Plex Mono';color:#7A5A60;margin-top:22px;letter-spacing:.06em}}
.st{{position:relative;width:700px;height:1000px;border-radius:50px;overflow:hidden;background:{STUCCO};
  box-shadow:0 0 0 22px #fff,0 26px 50px 22px rgba(60,30,20,.22)}}
.st.flat{{background:{SNOW}}}
.wall{{position:absolute;inset:0;width:100%;height:100%}}
.logo{{position:absolute;left:70px;top:72px;width:330px;height:85px}}
.win{{position:absolute;left:70px;top:200px;width:560px;height:460px;display:block}}
.win canvas{{width:100%;height:100%;display:block}}
.vial{{position:absolute;width:470px;left:175px;top:135px;transform:rotate(4deg);filter:drop-shadow(-18px 30px 26px rgba(40,20,10,.35))}}
.url{{position:absolute;left:66px;right:66px;top:690px;font:900 84px/1 Outfit;color:{OX};letter-spacing:-.035em}}
.foot{{position:absolute;left:70px;bottom:52px;right:70px;display:flex;align-items:flex-end;gap:28px}}
.foot svg{{background:transparent}}
.line{{font:900 46px/1.02 Outfit;color:{OX};letter-spacing:-.02em;margin-left:auto;text-align:right}}'''
html = f'''<!doctype html><html><head><meta charset="utf-8"><title>ZUMA stickers · two directions</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@900&family=IBM+Plex+Mono:wght@600&display=swap" rel="stylesheet">
<style>{css}</style></head><body>{defs}
<div class="row"><figure>{A}<figcaption>A · BRAND LIGHT (STUCCO, PALM, LIGHTBOX, REAL VIAL)</figcaption></figure>
<figure>{B}<figcaption>B · FLAT (SNOW, TONAL TILES, NO IMAGERY)</figcaption></figure></div>
<script src="ombre.js"></script></body></html>'''
open(os.path.join(H, 'directions.html'), 'w').write(html); print('ok')

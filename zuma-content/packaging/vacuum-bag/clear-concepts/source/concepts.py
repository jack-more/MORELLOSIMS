# Three clear-vacuum-bag concepts, 70 x 105 mm at 20 px/mm (1400 x 2100). The RT-3 vial lies 8 mm below centre (16 x 35 mm: x 540-860, y 860-1560).
# Every element is either PRINTED SOLID (white underlay, class "base") or INK ON CLEAR FILM (no underlay). ?mask renders the underlay plate.
import json, os, re
H = os.path.dirname(os.path.abspath(__file__))
WM = json.load(open('/home/user/MORELLOSIMS/zuma-content/brand/wordmark/tides.json')); WW = WM['zuma_w']
CD = re.search(r' d="([^"]+)"', open('/home/user/MORELLOSIMS/zuma-content/packaging/capsule-case/zuma-crest-stamp.svg').read()).group(1)
OX, SNOW = '#6E1C2A', '#FCFBF8'
def wm(x, y, w, c, rot=0):
    h = w * 100 / WW
    return f'<svg viewBox="0 0 {WW} 100" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h:.0f}px;transform:rotate({rot}deg)"><path fill="{c}" fill-rule="evenodd" d="{WM["zuma"]}"/></svg>'
def crest(x, y, w, c): return f'<svg viewBox="0 0 104.26 100" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{w*100/104.26:.0f}px"><path fill="{c}" fill-rule="evenodd" d="{CD}"/></svg>'
def lb(area, st, cols=3, rows=4): return f'<div class="base" style="{st}"><canvas data-lb="{area}" data-seed="3" data-cols="{cols}" data-rows="{rows}" data-bars="0" data-behind="palm" data-bseed="5" data-scale="2"></canvas></div>'
def sticker(x, y, name='RT-3', line='Metabolic research'):
    return (f'<div class="base stk" style="left:{x}px;top:{y}px"><b>{name}</b><span>{line}</span></div>')
def ruo(x, y, c=OX, al='left', w=900): return f'<div class="ink small" style="left:{x}px;top:{y}px;width:{w}px;color:{c};text-align:{al}">For laboratory research use only. Not for human or veterinary use.</div>'
C = {}
# 1 · The fade band (after Prada): the Lightbox printed solid across the top, fading to clear film over the vial; the wordmark big across the fade
C['band'] = (lb('metabolic', 'left:0;top:0;width:1400px;height:980px;-webkit-mask:linear-gradient(#000 62%,transparent 100%)', 4, 3)
             + crest(1170, 150, 120, SNOW) + wm(160, 610, 1080, OX) + sticker(440, 1650) + ruo(0, 1930, OX, 'center', 1400))
# 2 · Clear (after retaW): no print but Oxblood ink on clear film; the name on a sticker
C['clear'] = (wm(440, 300, 520, OX) + crest(650, 160, 100, OX)
              + f'<div class="ink" style="left:0;top:460px;width:1400px;text-align:center;font:500 44px Outfit;color:{OX}">Research, refined.</div>'
              + sticker(440, 1650) + ruo(150, 1880, OX, 'left', 700)
              + f'<div class="ink small" style="left:850px;top:1880px;width:400px;text-align:right;color:{OX}">zumatides.com/lots</div>')
# 3 · Style 10 on clear: the Lightbox as a solid lane down the left under the tall wordmark; crest, bar and type in Oxblood on clear film
C['lane'] = (lb('metabolic', 'left:0;top:0;width:420px;height:2100px', 1, 5)
             + wm(210 - 750, 1050 - 180, 1500, OX, -90) + crest(1150, 150, 140, OX)
             + f'<div class="ink" style="left:930px;right:0;top:560px;height:28px;background:{OX}"></div>'
             + sticker(780, 1650) + ruo(470, 1930, OX, 'left', 900))
CSS = '''html,body{margin:0;width:1400px;height:2100px;background:transparent;overflow:hidden}.pg{position:relative;width:1400px;height:2100px}
.base,.ink{position:absolute} .base canvas{position:absolute;inset:0;width:100%;height:100%}
.stk{width:520px;height:200px;border-radius:24px;background:#FCFBF8;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:4px}
.stk b{font:800 92px/1 Outfit;color:#6E1C2A;letter-spacing:.01em} .stk span{font:500 30px Outfit;color:#6E1C2A}
.small{font:500 26px/1.3 Outfit}
body.mask{background:#000} body.mask .base{background:#fff!important;-webkit-mask:none} body.mask .base>*,body.mask .ink,body.mask svg{visibility:hidden}
body.mask .base[style*="mask:linear"]{background:linear-gradient(#fff 62%,#000 100%)!important}'''
for k, body in C.items():
    open(os.path.join(H, f'c-{k}.html'), 'w').write(f'''<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;800&display=swap" rel="stylesheet"><style>{CSS}</style></head>
<body><script>if(location.search.includes('mask'))document.body.className='mask'</script><div class="pg">{body}</div><script src="ombre.js"></script></body></html>''')
print('ok', list(C))

# ---- four more ----
import base64 as _b
SEAL = 'data:image/png;base64,' + _b.b64encode(open('/home/user/MORELLOSIMS/zuma-content/stickers/print/zuma-sticker-seal-metabolic.png', 'rb').read()).decode()
D = {}
# 4 · Tinted film: the whole bag in translucent area colour (no underlay), the vial seen through it; wordmark and crest solid Oxblood
D['tint'] = (f'<div class="ink" style="inset:0;background:#36B3E8;opacity:.42"></div>' + wm(440, 300, 520, OX) + crest(650, 160, 100, OX)
             + sticker(440, 1650) + ruo(0, 1930, OX, 'center', 1400))
# 5 · The window: the Lightbox printed solid all over, one clear window cut round the vial (a Lightbox tile with the glass left out)
WIN = 'M470 760 H930 V1620 H470 Z'
D['window'] = (f'<div class="base" style="inset:0;clip-path:path(evenodd,\'M0 0H1400V2100H0Z {WIN}\')"><canvas data-lb="metabolic" data-seed="3" data-cols="3" data-rows="5" data-bars="0" data-behind="palm" data-bseed="5" data-scale="2"></canvas></div>'
               + f'<div class="ink" style="left:470px;top:760px;width:460px;height:860px;box-shadow:0 0 0 14px {OX}"></div>'
               + wm(330, 330, 740, OX) + crest(1170, 150, 120, SNOW) + sticker(440, 1690) + ruo(0, 1950, OX, 'center', 1400))
# 6 · Stickers only (after Hello Star): an unprinted clear bag; the round area seal and the compound tag do all the work; one line printed
D['stickers'] = (f'<img class="base" src="{SEAL}" style="left:150px;top:330px;width:520px;height:520px;transform:rotate(-8deg);border-radius:50%">'
                 + sticker(760, 1450).replace('class="base stk"', 'class="base stk" data-r="1"').replace('style="left:760px;top:1450px"', 'style="left:760px;top:1450px;transform:rotate(6deg)"')
                 + ruo(0, 1930, OX, 'center', 1400))
# 7 · The panel (after Maxema): a solid Lightbox panel nearly the size of the bag, the vial pressed into it, the wordmark stacked in Oxblood
rows = ''.join(wm(160, 120 + i * 300, 900, OX) for i in range(5))
D['panel'] = (f'<div class="base" style="left:90px;top:200px;width:1220px;height:1760px"><canvas data-lb="metabolic" data-seed="3" data-cols="3" data-rows="5" data-bars="0" data-behind="palm" data-bseed="5" data-scale="2"></canvas></div>'
              + f'<div class="ink" style="left:90px;top:200px;width:1220px;height:1760px;opacity:.86">{rows}</div>'
              + crest(1170, 240, 100, SNOW) + sticker(440, 1740) + ruo(0, 1990, OX, 'center', 1400))
for k, body in D.items():
    open(os.path.join(H, f'c-{k}.html'), 'w').write(f'''<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;800&display=swap" rel="stylesheet"><style>{CSS} img.base{{position:absolute}}</style></head>
<body><script>if(location.search.includes('mask'))document.body.className='mask'</script><div class="pg">{body}</div><script src="ombre.js"></script></body></html>''')
print('more', list(D))

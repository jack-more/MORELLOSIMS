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

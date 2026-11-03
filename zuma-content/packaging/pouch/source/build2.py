# Pouch round 2: five Lightbox experiments on the same 120 x 180 mm heat-seal pouch (1 mm = 5 px).
import json, os, re, base64, urllib.parse
H = os.path.dirname(os.path.abspath(__file__)); S = os.path.dirname(H)
WM = json.load(open('/home/user/MORELLOSIMS/zuma-content/brand/wordmark/tides.json'))
CD = re.search(r' d="([^"]+)"', open('/home/user/MORELLOSIMS/zuma-content/packaging/capsule-case/zuma-crest-stamp.svg').read()).group(1)
OX, SNOW, PINK = '#6E1C2A', '#FCFBF8', '#E9C9CE'
AREAS = [('metabolic', 'Metabolic', 'palm', 3, 5), ('dermal', 'Dermal', 'bamboo', 11, 4), ('endocrine', 'Endocrine', 'palm', 5, 9),
         ('tissue', 'Tissue', 'bamboo', 14, 6), ('neuro', 'Neuro', 'palm', 21, 8), ('supplies', 'Lab supplies', 'bamboo', 34, 7), ('oxblood', 'ZUMA', 'palm', 8, 12)]
img = lambda n: 'data:image/png;base64,' + base64.b64encode(open(f'{S}/stk/hero-vial-{n}.png', 'rb').read()).decode()
WW = WM['zuma_w']
wm = lambda w, c=SNOW, st='': f'<svg viewBox="0 0 {WW} 100" style="width:{w}px;height:{w*100/WW:.1f}px;display:block;{st}"><path fill="{c}" fill-rule="evenodd" d="{WM["zuma"]}"/></svg>'
crest = lambda w, c, st='': f'<svg viewBox="0 0 104.26 100" style="width:{w}px;height:{w*100/104.26:.1f}px;display:block;{st}"><path fill="{c}" fill-rule="evenodd" d="{CD}"/></svg>'
def lb(i, c=3, r=4, bars=0, st=''):
    k, n, b, s, bs = AREAS[i]
    return f'<canvas data-lb="{k}" data-seed="{s}" data-cols="{c}" data-rows="{r}" data-bars="{bars}" data-behind="{b}" data-bseed="{bs}" style="{st}"></canvas>'
RUO = lambda c='rgba(233,201,206,.8)': f'<div class="ruo" style="color:{c}">FOR LABORATORY RESEARCH USE ONLY · NOT FOR HUMAN OR VETERINARY USE</div>'
def bag(face, cap, note):
    return (f'<figure><div class="bag"><div class="face">{face}</div><div class="crimp"></div><div class="crimp b"></div><i class="n l"></i><i class="n r"></i><div class="sheen"></div></div>'
            f'<figcaption><b>{cap}</b><span>{note}</span></figcaption></figure>')
F = []

# 1 · The wall, edge to edge: six panes fill the bag, the Oxblood mullions are the only frame, the wordmark sits across them in Oxblood
panes = ''.join(f'<div class="pane">{lb(i, 2, 2)}</div>' for i in range(6)) + f'<div class="pane ox7">{lb(6, 4, 1)}<div class="w7">{wm(470, SNOW)}</div></div>'
F.append(bag(f'<div class="wall1">{panes}</div>{RUO()}',
             '1 · The wall', 'Six area panes plus an Oxblood lane across the bottom that carries the wordmark. The mullions are the frame.'))

# 2 · Bloom: the crest is the centre of the bag; its five petals and its core split the bag into six panes, one area each
cx, cy, cw = 300, 400, 420
ang = [-90 + 36 + 72 * k for k in range(6)]
import math
def pt(a, r=1400): return f'{cx + r*math.cos(math.radians(a)):.0f}px {cy + r*math.sin(math.radians(a)):.0f}px'
wedges = ''.join(f'<div class="abs">{lb(k, 3, 4, 0, f"clip-path:polygon({cx}px {cy}px,{pt(ang[k])},{pt(ang[k]+36)},{pt(ang[k+1])})")}</div>' for k in range(5))
core = f'<div class="abs">{lb(6, 2, 2, 0, f"clip-path:circle({cw*0.2:.0f}px at {cx}px {cy}px)")}</div>'
spokes = ''.join(f'<line x1="{cx}" y1="{cy}" x2="{cx + 1400*math.cos(math.radians(a)):.0f}" y2="{cy + 1400*math.sin(math.radians(a)):.0f}"/>' for a in ang[:5])
F.append(bag(f'<div class="fill ox"></div>{wedges}{core}<svg class="abs" viewBox="0 0 600 900"><g stroke="{OX}" stroke-width="12">{spokes}</g></svg>'
             f'{crest(cw, OX, f"position:absolute;left:{cx-cw/2}px;top:{cy-cw*100/104.26/2:.0f}px")}'
             f'<div class="foot tall">{wm(400, SNOW)}</div>{RUO()}',
             '2 · Bloom', 'The crest sits at the centre; each petal opens onto a research area, the core onto the Oxblood lane.'))

# 3 · Wordmark window: an Oxblood bag, the wordmark runs the full height and is cut as a window onto six panes
mask = 'data:image/svg+xml,' + urllib.parse.quote(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WW} 100"><path fill-rule="evenodd" d="{WM["zuma"]}"/></svg>')
L, T = 730, int(730 * 100 / WW)
cols = ''.join(f'<div class="col">{lb(i, 1, 2)}</div>' for i in [0, 1, 2, 6, 3, 4, 5])
F.append(bag(f'<div class="fill ox"></div><div class="wwin" style="width:{L}px;height:{T}px;-webkit-mask:url(\'{mask}\') 0 0/100% 100% no-repeat;'
             f'transform:translate({300 - L/2 - 40}px,{445 - T/2}px) rotate(-90deg)">{cols}</div>'
             f'<div class="vurl">ZUMATIDES.COM · RESEARCH, REFINED</div>{crest(64, PINK, "position:absolute;right:52px;top:80px")}{RUO()}',
             '3 · Through the letters', 'Oxblood bag; the wordmark runs the full height and is cut as a window onto seven lanes, Oxblood in the middle.'))

# 4 · Frosted: the Lightbox printed on frosted clear film, so the vials inside show through as shapes behind the glass
vials = ''.join(f'<img class="ghost" src="{img(v)}" style="left:{x}px;top:{y}px;transform:rotate({r}deg)">' for v, x, y, r in [('01', -40, 120, -8), ('09', 150, 160, 4), ('11', 300, 110, 10)])
F.append(bag(f'<div class="fill" style="background:#E9EEF0"></div>{vials}<div class="fill frost">{lb(0, 3, 4, 1)}</div>'
             f'<div class="foot tall">{wm(400, SNOW)}</div>{RUO()}',
             '4 · Frosted', 'Printed on frosted clear film: the vials inside show as shapes behind the glass. One area shown.'))

# 5 · Tall type, one area per bag: full-bleed Lightbox, the wordmark set vertically up the whole bag in Oxblood
F.append(bag(f'<div class="fill">{lb(1, 3, 5, 0)}</div>{wm(730, OX, f"position:absolute;left:{-365+100}px;top:{445-87}px;transform:rotate(-90deg)")}'
             f'<div class="varea">DERMAL RESEARCH</div>{crest(90, OX, "position:absolute;right:46px;top:82px")}{RUO(OX)}',
             '5 · Tall type', 'One area per bag. The wordmark runs up the whole bag in Oxblood. Dermal shown.'))

F.append(bag(f'<div class="fill">{lb(6, 3, 5, 0)}</div>{wm(730, SNOW, f"position:absolute;left:{-365+100}px;top:{445-87}px;transform:rotate(-90deg)")}'
             f'<div class="varea" style="color:{SNOW}">RESEARCH, REFINED</div>{crest(90, SNOW, "position:absolute;right:46px;top:82px")}{RUO(PINK)}',
             '6 · Tall type, Oxblood lane', 'The same bag in the Oxblood Lightbox: the one generic bag if each area also gets its own.'))
css = f'''body{{margin:0;background:#E7DFD3;font-family:Outfit,sans-serif}} section{{padding:70px 80px}}
h2{{font:600 30px 'IBM Plex Mono';letter-spacing:.08em;margin:0 0 50px;color:{OX}}}
.row{{display:flex;gap:56px;flex-wrap:wrap}} figure{{margin:0;width:600px}}
figcaption{{margin-top:22px;font:400 21px/1.4 Outfit;color:#5A4448}} figcaption b{{display:block;font:600 21px 'IBM Plex Mono';letter-spacing:.06em;color:{OX};text-transform:uppercase;margin-bottom:6px}}
.bag{{position:relative;width:600px;height:900px;border-radius:14px;overflow:hidden;box-shadow:0 30px 60px rgba(60,30,20,.25),0 4px 10px rgba(60,30,20,.15)}}
.face,.fill,.abs{{position:absolute;inset:0}} .fill canvas,.abs canvas{{position:absolute;inset:0;width:100%;height:100%;display:block}} .ox{{background:{OX}}}
.crimp{{position:absolute;left:0;right:0;top:0;height:50px;background:repeating-linear-gradient(90deg,rgba(255,255,255,.16) 0 2px,rgba(0,0,0,.12) 2px 5px);border-bottom:1px solid rgba(0,0,0,.18)}}
.crimp.b{{top:auto;bottom:0;height:30px;border-bottom:0;border-top:1px solid rgba(0,0,0,.18)}}
.n{{position:absolute;top:82px;width:16px;height:16px;border-radius:50%;background:#E7DFD3}} .n.l{{left:-8px}} .n.r{{right:-8px}}
.sheen{{position:absolute;inset:0;pointer-events:none;background:linear-gradient(115deg,rgba(255,255,255,.10) 0%,rgba(255,255,255,0) 32%,rgba(255,255,255,.06) 55%,rgba(0,0,0,.10) 100%),radial-gradient(120% 70% at 50% 50%,rgba(255,255,255,0) 60%,rgba(0,0,0,.16) 100%)}}
.ruo{{position:absolute;left:0;right:0;bottom:40px;text-align:center;font:600 10.5px 'IBM Plex Mono';letter-spacing:.14em}}
.wall1{{position:absolute;inset:0;background:{OX};display:grid;grid-template-columns:1fr 1fr;grid-template-rows:repeat(3,1fr);gap:12px;padding:50px 0 76px}}
.pane{{position:relative;overflow:hidden}} .pane canvas{{position:absolute;inset:0;width:100%;height:100%}}
.ox7{{grid-column:1 / 3}} .w7{{position:absolute;left:65px;top:50%;transform:translateY(-50%)}} .wall1{{grid-template-rows:1fr 1fr 1fr 1.25fr!important}}
.mid{{position:absolute;left:40px;top:357px;padding:0}}
.foot{{position:absolute;left:0;right:0;bottom:0;height:76px;background:{OX}}} .foot.tall{{height:200px;padding:42px 100px 0}}
.wwin{{position:absolute;left:0;top:0;display:flex;transform-origin:50% 50%}} .col{{position:relative;flex:1}} .col canvas{{position:absolute;inset:0;width:100%;height:100%}}
.vurl{{position:absolute;right:58px;top:460px;transform:translate(50%,-50%) rotate(-90deg);font:600 17px 'IBM Plex Mono';letter-spacing:.36em;color:{PINK};white-space:nowrap}}
.ghost{{position:absolute;width:360px;filter:blur(7px) saturate(.6);opacity:.75}}
.frost{{opacity:.62;mix-blend-mode:multiply}}
.varea{{position:absolute;right:58px;top:520px;transform:translate(50%,-50%) rotate(-90deg);font:600 20px 'IBM Plex Mono';letter-spacing:.4em;color:{OX};white-space:nowrap}}'''
html = f'''<!doctype html><html><head><meta charset="utf-8"><title>ZUMA pouch round 2</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;800&family=IBM+Plex+Mono:wght@600&display=swap" rel="stylesheet"><style>{css}</style></head><body>
<section><h2>POUCH · ROUND 2 · LIGHTBOX EXPERIMENTS</h2><div class="row">{''.join(F)}</div></section><script src="ombre.js"></script></body></html>'''
open(os.path.join(H, 'bags2.html'), 'w').write(html); print('ok')

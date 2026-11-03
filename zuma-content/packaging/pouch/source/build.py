# ZUMA heat-seal pouch, 120 x 180 mm flat (1 mm = 5 px): 10 mm crimp seal on top with tear notches, 6 mm seal at the bottom.
# Three directions: A one bag per research area, B solid Oxblood, C the six areas as one lightbox wall.
import json, os, re, base64
H = os.path.dirname(os.path.abspath(__file__)); S = os.path.dirname(H)
WM = json.load(open('/home/user/MORELLOSIMS/zuma-content/brand/wordmark/tides.json'))
CD = re.search(r' d="([^"]+)"', open('/home/user/MORELLOSIMS/zuma-content/packaging/capsule-case/zuma-crest-stamp.svg').read()).group(1)
QR = json.load(open(os.path.join(H, 'qrlots.json')))
OX, SNOW, PINK = '#6E1C2A', '#FCFBF8', '#E9C9CE'
AREAS = [('metabolic', 'Metabolic', '01', 'palm', 3, 5), ('dermal', 'Dermal', '05', 'bamboo', 11, 4), ('endocrine', 'Endocrine', '04', 'palm', 5, 9),
         ('tissue', 'Tissue', '09', 'bamboo', 14, 6), ('neuro', 'Neuro', '11', 'palm', 21, 8), ('supplies', 'Lab supplies', '03', 'bamboo', 34, 7)]
img = lambda n: 'data:image/png;base64,' + base64.b64encode(open(f'{S}/stk/hero-vial-{n}.png', 'rb').read()).decode()
wm = lambda w, c=SNOW: f'<svg viewBox="0 0 {WM["zuma_w"]} 100" style="width:{w}px;height:{w*100/WM["zuma_w"]:.1f}px;display:block"><path fill="{c}" fill-rule="evenodd" d="{WM["zuma"]}"/></svg>'
crest = lambda w, c, extra='': f'<svg viewBox="0 0 104.26 100" style="width:{w}px;height:{w*100/104.26:.1f}px;display:block;{extra}"><path fill="{c}" fill-rule="evenodd" d="{CD}"/></svg>'
lb = lambda k, s, b, bs, c=3, r=5, bars=1: f'<canvas data-lb="{k}" data-seed="{s}" data-cols="{c}" data-rows="{r}" data-bars="{bars}" data-behind="{b}" data-bseed="{bs}"></canvas>'
RUO = '<div class="ruo">FOR LABORATORY RESEARCH USE ONLY · NOT FOR HUMAN OR VETERINARY USE</div>'

def bag(face, cap, seal='light'):
    return f'<figure><div class="bag {seal}"><div class="face">{face}</div><div class="crimp"></div><div class="crimp b"></div><i class="n l"></i><i class="n r"></i><div class="sheen"></div></div><figcaption>{cap}</figcaption></figure>'

def back(bg):
    q = f'<svg viewBox="-2 -2 {QR["n"]+4} {QR["n"]+4}" style="width:150px;height:150px;display:block" shape-rendering="crispEdges"><rect x="-2" y="-2" width="{QR["n"]+4}" height="{QR["n"]+4}" fill="{SNOW}"/><path fill="{OX}" d="{QR["p"]}"/></svg>'
    return (f'<div class="fill" style="background:{bg}"></div><div class="bk">{crest(92, SNOW)}'
            f'<div class="bk-t">EVERY LOT TESTED.<br>SCAN FOR THE REPORT.</div>{q}<div class="bk-u">ZUMATIDES.COM/LOTS</div>'
            f'<div class="lot"><span>LOT</span><b></b><span>PACKED</span><b></b></div></div>{RUO}')

# A. one bag per research area
A = []
for k, name, v, b, s, bs in AREAS:
    lab = (name if k == 'supplies' else name + ' research').upper()
    A.append(bag(f'<div class="fill">{lb(k, s, b, bs, 3, 5, 0)}</div>{crest(300, OX, "position:absolute;left:150px;top:150px")}'
                 f'<div class="band">{wm(470)}<div class="area">{lab}</div></div>{RUO}', name))
# B. solid Oxblood: the crest in spot gloss bleeding off the right edge, the wordmark in Snow, the Lightbox printed inside
B = [bag(f'<div class="fill ox"></div>{crest(760, "#5A1421", "position:absolute;right:-300px;top:330px;filter:drop-shadow(0 0 0.6px rgba(255,255,255,.35))")}'
         f'<div class="gloss"></div><div style="position:absolute;left:58px;top:120px">{wm(400)}</div>'
         f'<div class="url" style="left:62px;top:250px">ZUMATIDES.COM</div>{RUO}', 'Front · matte soft-touch, crest in spot gloss'),
     bag(back(OX), 'Back'),
     bag(f'<div class="fill">{lb("metabolic", 3, "palm", 5, 4, 6)}</div><div class="inside">INSIDE PRINT</div>', 'Inside · Lightbox, seen when torn open')]
# C. the six areas as one lightbox wall: six pure fields behind Oxblood mullions, the wordmark under
tiles = ''.join(f'<div class="tile">{lb(k, s, b, bs, 2, 3, 0)}<span>{name.upper()}</span></div>' for k, name, v, b, s, bs in AREAS)
C = [bag(f'<div class="fill ox"></div><div class="wall">{tiles}</div><div class="band c">{wm(470)}<div class="area">SIX AREAS OF RESEARCH</div></div>{RUO}', 'Front'),
     bag(back(OX), 'Back')]

css = f'''body{{margin:0;background:#E7DFD3;font-family:Outfit,sans-serif;color:#3A2328}}
h2{{font:600 34px 'IBM Plex Mono';letter-spacing:.08em;margin:0 0 6px;color:{OX}}} p.d{{font:400 24px/1.4 Outfit;margin:0 0 40px;max-width:1500px;color:#5A4448}}
section{{padding:80px 90px 40px}} .row{{display:flex;gap:56px;align-items:flex-start;flex-wrap:wrap}} figure{{margin:0}}
figcaption{{font:600 20px 'IBM Plex Mono';color:#7A5A60;margin-top:22px;letter-spacing:.06em;text-transform:uppercase}}
.bag{{position:relative;width:600px;height:900px;border-radius:14px;overflow:hidden;box-shadow:0 30px 60px rgba(60,30,20,.25),0 4px 10px rgba(60,30,20,.15)}}
.face{{position:absolute;inset:0}} .fill{{position:absolute;inset:0}} .fill canvas{{width:100%;height:100%;display:block}} .ox{{background:{OX}}}
.crimp{{position:absolute;left:0;right:0;top:0;height:50px;background:repeating-linear-gradient(90deg,rgba(255,255,255,.16) 0 2px,rgba(0,0,0,.12) 2px 5px);border-bottom:1px solid rgba(0,0,0,.18)}}
.crimp.b{{top:auto;bottom:0;height:30px;border-bottom:0;border-top:1px solid rgba(0,0,0,.18)}}
.n{{position:absolute;top:82px;width:16px;height:16px;border-radius:50%;background:#E7DFD3}} .n.l{{left:-8px}} .n.r{{right:-8px}}
.sheen{{position:absolute;inset:0;pointer-events:none;background:linear-gradient(115deg,rgba(255,255,255,.10) 0%,rgba(255,255,255,0) 32%,rgba(255,255,255,.06) 55%,rgba(0,0,0,.10) 100%),
  radial-gradient(120% 70% at 50% 50%,rgba(255,255,255,0) 60%,rgba(0,0,0,.16) 100%)}}
.vial{{position:absolute;width:560px;left:30px;top:70px;transform:rotate(6deg);filter:drop-shadow(-20px 30px 28px rgba(30,10,10,.38))}}
.band{{position:absolute;left:0;right:0;bottom:30px;height:250px;background:{OX};padding:44px 65px 0}}
.band.c{{height:260px}}
.area{{margin-top:20px;font:600 21px 'IBM Plex Mono';letter-spacing:.32em;color:{PINK}}}
.ruo{{position:absolute;left:0;right:0;bottom:40px;text-align:center;font:600 10.5px 'IBM Plex Mono';letter-spacing:.14em;color:rgba(233,201,206,.75)}}
.url{{position:absolute;font:600 22px 'IBM Plex Mono';letter-spacing:.42em;color:{PINK}}}
.gloss{{position:absolute;right:-300px;top:330px;width:760px;height:729px;pointer-events:none;background:linear-gradient(130deg,rgba(255,255,255,.0) 30%,rgba(255,255,255,.09) 48%,rgba(255,255,255,0) 62%)}}
.bk{{position:absolute;left:0;right:0;top:110px;display:flex;flex-direction:column;align-items:center;gap:26px}}
.bk-t{{font:800 30px/1.25 Outfit;color:{SNOW};text-align:center;letter-spacing:.04em}} .bk-u{{font:600 18px 'IBM Plex Mono';letter-spacing:.3em;color:{PINK}}}
.lot{{display:grid;grid-template-columns:auto 260px;gap:14px 16px;align-items:end;margin-top:20px;font:600 16px 'IBM Plex Mono';letter-spacing:.2em;color:{PINK}}}
.lot b{{border-bottom:2px solid rgba(233,201,206,.6);height:24px}}
.inside{{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);font:600 18px 'IBM Plex Mono';letter-spacing:.3em;color:{OX};background:rgba(252,251,248,.85);padding:10px 18px}}
.wall{{position:absolute;left:36px;right:36px;top:86px;height:494px;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:repeat(3,1fr);gap:14px}}
.tile{{position:relative;overflow:hidden;border-radius:3px}} .tile canvas{{width:100%;height:100%;display:block}}
.tile span{{position:absolute;left:14px;bottom:11px;font:600 13px 'IBM Plex Mono';letter-spacing:.24em;color:{OX}}}'''
html = f'''<!doctype html><html><head><meta charset="utf-8"><title>ZUMA pouch directions</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;800;900&family=IBM+Plex+Mono:wght@600&display=swap" rel="stylesheet"><style>{css}</style></head><body>
<section><h2>A · BY RESEARCH AREA</h2><p class="d">Six bags, one per area. The area's Lightbox fills the bag with the crest on it (no product or dose, so one bag fits every compound in the area), and the Oxblood band carries the wordmark. Six printed versions to stock.</p><div class="row">{''.join(A)}</div></section>
<section><h2>B · OXBLOOD</h2><p class="d">One bag for every order. Matte soft-touch Oxblood, with the crest in spot gloss so it shows only when it catches the light. The Lightbox is printed on the inside and appears when the bag is torn open. Note: the mailer is Oxblood too.</p><div class="row">{''.join(B)}</div></section>
<section><h2>C · THE LIGHTBOX WALL</h2><p class="d">One bag for every order. The six areas sit as six separate Lightbox panes behind Oxblood mullions, each one pure (never blended), with the wordmark under.</p><div class="row">{''.join(C)}</div></section>
<script src="ombre.js"></script></body></html>'''
open(os.path.join(H, 'bags.html'), 'w').write(html); print('ok')

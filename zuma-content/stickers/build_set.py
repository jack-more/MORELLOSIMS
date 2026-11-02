# ZUMA sticker set, direction A (brand light), Post Spanish: six area stickers + one family sticker, 70 x 100 mm (1 mm = 10 css px).
# Built from the site's own parts: ombre.js (the clean lit stucco wall and the Lightbox field with the plant behind the glass),
# the logo symbol and the real vial renders. The wall carries no cast shadow where the Lightbox sits on it (brandbook rule).
import json, os, base64
H = os.path.dirname(os.path.abspath(__file__))
defs = open('/home/user/MORELLOSIMS/zuma-content/brand/logo-defs.svg').read()
qr = json.load(open(os.path.join(H, 'qr.json')))
OX, STUCCO = '#6E1C2A', '#EFE4D2'
AREAS = [  # key, area, vial render, plant behind, seeds
    ('metabolic', 'Metabolic research', '01', 'palm', 3, 5), ('dermal', 'Dermal research', '05', 'bamboo', 11, 4),
    ('endocrine', 'Endocrine research', '04', 'palm', 5, 9), ('tissue', 'Tissue research', '09', 'bamboo', 14, 6),
    ('neuro', 'Neuro research', '11', 'palm', 21, 8), ('supplies', 'Lab supplies', '03', 'bamboo', 34, 7)]
img = lambda n: 'data:image/png;base64,' + base64.b64encode(open(os.path.join(H, f'hero-vial-{n}.png'), 'rb').read()).decode()

def qrsvg(size):
    n = qr['n']
    return f'<svg viewBox="-2 -2 {n + 4} {n + 4}" style="width:{size}px;height:{size}px;display:block" shape-rendering="crispEdges"><path fill="{OX}" d="{qr["p"]}"/></svg>'

def frame(key, window):
    return (f'<div class="cut" data-key="{key}"><div class="st">{window}'
            f'<div class="band"><svg class="logo"><use href="#zuma-logo"/></svg><div class="url">zumatides.com</div>'
            f'<div class="qr">{qrsvg(132)}</div></div></div></div>')

cards = []
for key, name, vial, behind, seed, bseed in AREAS:
    w = (f'<div class="win"><canvas data-lb="{key}" data-seed="{seed}" data-cols="4" data-rows="6" data-bars="1" data-behind="{behind}" data-bseed="{bseed}"></canvas></div>'
         f'<img class="vial" src="{img(vial)}">')
    cards.append((key, name, frame(key, w)))
# the family: the six areas side by side, each its own Lightbox strip (one area per strip, never blended)
strips = ''.join(f'<div class="strip"><canvas data-lb="{k}" data-seed="{s}" data-cols="1" data-rows="7" data-bars="1" data-behind="{b}" data-bseed="{bs}"></canvas></div>'
                 for k, n, v, b, s, bs in AREAS)
cards.append(('family', 'The family · all six areas', frame('family', f'<div class="win fam">{strips}</div>')))

css = f'''body{{margin:0;background:#E3DACD;font-family:Outfit,sans-serif}} .grid{{display:flex;flex-wrap:wrap;gap:70px 60px;padding:70px}}
figure{{margin:0}} figcaption{{font:600 20px 'IBM Plex Mono';color:#7A5A60;margin-top:18px;letter-spacing:.06em;text-transform:uppercase}}
.cut{{background:#fff;padding:22px;border-radius:72px;box-shadow:0 26px 50px rgba(60,30,20,.22)}}
.st{{position:relative;width:700px;height:1000px;border-radius:50px;overflow:hidden;background:{STUCCO}}}
.win{{position:absolute;left:0;top:0;width:100%;height:100%}} .win canvas{{width:100%;height:100%;display:block}}
.fam{{display:flex;gap:0}} .strip{{flex:1;height:100%}}
.vial{{position:absolute;width:620px;left:80px;top:40px;transform:rotate(6deg);filter:drop-shadow(-22px 34px 30px rgba(30,10,10,.38))}}
.band{{position:absolute;left:0;right:0;bottom:0;height:226px;background:{OX};padding:40px 0 0 54px;color:#FCFBF8}}
.band .logo{{display:block;width:250px;height:64px;color:#FCFBF8}}
.band .url{{font:900 54px/1 Outfit;letter-spacing:-.03em;margin-top:24px}}
.band .qr{{position:absolute;right:42px;top:38px;background:#FCFBF8;border-radius:14px;padding:12px}}
body.export{{background:transparent}} body.export .grid{{padding:0;gap:0}} body.export figcaption{{display:none}} body.export .cut{{box-shadow:none}}'''
html = f'''<!doctype html><html><head><meta charset="utf-8"><title>ZUMA stickers · Post Spanish set</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@900&family=IBM+Plex+Mono:wght@600&display=swap" rel="stylesheet">
<style>{css}</style></head><body>{defs}<div class="grid">
{''.join(f'<figure>{c}<figcaption>{n}</figcaption></figure>' for k, n, c in cards)}
</div><script src="ombre.js"></script></body></html>'''
open(os.path.join(H, 'set.html'), 'w').write(html); print('ok', len(cards))

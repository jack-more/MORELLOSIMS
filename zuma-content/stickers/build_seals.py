# Circle seals: an Oxblood rim carrying the line in Snow (the label), inside it the area's Lightbox glowing with the plant behind,
# the crest in Oxblood at the centre. Six areas + the original all-Oxblood seal. 60 mm (600 css px).
import os, re
H = os.path.dirname(os.path.abspath(__file__))
crest = open('/home/user/MORELLOSIMS/zuma-content/packaging/capsule-case/zuma-crest-stamp.svg').read()
CD = re.search(r' d="([^"]+)"', crest).group(1)
OX, SNOW = '#6E1C2A', '#FCFBF8'
AREAS = [('metabolic', 'palm', 3, 5), ('dermal', 'bamboo', 11, 4), ('endocrine', 'palm', 5, 9), ('tissue', 'bamboo', 14, 6), ('neuro', 'palm', 21, 8), ('supplies', 'bamboo', 34, 7)]
R, RIM = 300, 74
def seal(key, inner):
    t = 'ZUMA · RESEARCH, REFINED · ZUMATIDES.COM · '
    rr = R - RIM / 2
    return (f'<div class="cut" data-key="seal-{key}"><div class="seal">{inner}'
            f'<svg class="ov" viewBox="0 0 600 600"><defs><path id="rim-{key}" d="M300,300 m-{rr},0 a{rr},{rr} 0 1,1 {2*rr},0 a{rr},{rr} 0 1,1 -{2*rr},0"/>'
            f'<mask id="m-{key}"><rect width="600" height="600" fill="#fff"/><circle cx="300" cy="300" r="{R - RIM}" fill="#000"/></mask></defs>'
            f'<circle cx="300" cy="300" r="{R}" fill="{OX}" mask="url(#m-{key})"/>'
            f'<text font-family="IBM Plex Mono" font-weight="600" font-size="31" fill="{SNOW}" dominant-baseline="middle">'
            f'<textPath href="#rim-{key}" textLength="{2*3.14159*rr - 6:.0f}" lengthAdjust="spacing">{t}</textPath></text>'
            f'<path fill="{OX}" fill-rule="evenodd" transform="translate({300-130} {300-130/104.26*50}) scale({260/104.26:.4f})" d="{CD}"/></svg></div></div>')
cells = [seal(k, f'<canvas data-lb="{k}" data-seed="{s}" data-cols="3" data-rows="3" data-bars="0" data-behind="{b}" data-bseed="{bs}"></canvas>') for k, b, s, bs in AREAS]
cells.append(seal('oxblood', f'<div style="position:absolute;inset:0;background:{OX}"></div>').replace(f'fill="{OX}" fill-rule="evenodd"', f'fill="{SNOW}" fill-rule="evenodd"'))
css = '''body{margin:0;background:#E3DACD} .grid{display:flex;flex-wrap:wrap;gap:60px;padding:70px;max-width:2900px}
.cut{background:#fff;padding:22px;border-radius:50%;box-shadow:0 24px 46px rgba(60,30,20,.22)}
.seal{position:relative;width:600px;height:600px;border-radius:50%;overflow:hidden} .seal canvas{position:absolute;inset:0;width:100%;height:100%}
.ov{position:absolute;inset:0;width:100%;height:100%} body.export{background:transparent} body.export .grid{padding:0;gap:0} body.export .cut{box-shadow:none}'''
html = f'''<!doctype html><html><head><meta charset="utf-8"><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@600&display=swap" rel="stylesheet">
<style>{css}</style></head><body><div class="grid">{''.join(cells)}</div><script src="ombre.js"></script></body></html>'''
open(os.path.join(H, 'seals.html'), 'w').write(html); print('ok', len(cells))

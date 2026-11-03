# Vial label, simple and tight (no QR): three directions at 43 x 20 mm (40 px/mm, 1720 x 800), RT-3 / GHK-Cu / Selank shown.
# The front (the middle ~22 mm) carries the name; the wrap ends carry the lot box and the research-use line.
import json, os, re
H = os.path.dirname(os.path.abspath(__file__))
WM = json.load(open('/home/user/MORELLOSIMS/zuma-content/brand/wordmark/tides.json')); WW = WM['zuma_w']
CD = re.search(r' d="([^"]+)"', open('/home/user/MORELLOSIMS/zuma-content/packaging/capsule-case/zuma-crest-stamp.svg').read()).group(1)
OX, SNOW = '#6E1C2A', '#FCFBF8'
A = {'metabolic': ('#36B3E8', '#BFE8FB'), 'dermal': ('#FF6A55', '#FFC9BE'), 'neuro': ('#A57BF0', '#E4D8FF')}
P = [('RT-3', '10 mg', 'metabolic', 'Metabolic research'), ('GHK-Cu', '50 mg', 'dermal', 'Dermal research'), ('Selank', '10 mg', 'neuro', 'Neuro research')]
def wm(x, y, w, c, st=''): return f'<svg viewBox="0 0 {WW} 100" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{w*100/WW:.0f}px;{st}"><path fill="{c}" fill-rule="evenodd" d="{WM["zuma"]}"/></svg>'
def crest(x, y, w, c, st=''): return f'<svg viewBox="0 0 104.26 100" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{w*100/104.26:.0f}px;{st}"><path fill="{c}" fill-rule="evenodd" d="{CD}"/></svg>'
def lot(x, y, c, bg): return f'<div style="position:absolute;left:{x}px;top:{y}px;width:300px;height:96px;border:3px solid {c};border-radius:10px;background:{bg};font:700 30px Outfit;color:{c};padding:0 14px;box-sizing:border-box;display:flex;align-items:center">Lot</div>'
def ruo(c, y=700): return f'<div style="position:absolute;left:0;right:0;top:{y}px;text-align:center;font:600 30px Outfit;color:{c}">For laboratory research use only. Not for human or veterinary use.</div>'
HOLO = 'linear-gradient(115deg,#f7c6d9,#c7d8ff 25%,#c8f3e6 45%,#fff3b8 65%,#f2c6ff 85%)'
def L1(n, d, a, line):   # Tight: the area colour, the name big, the wordmark, one Oxblood band
    c, l = A[a]
    return (f'<div class="lb" style="background:{c}">' + wm(700, 70, 320, OX) + f'<div class="nm" style="color:{OX};top:200px">{n}</div>'
            f'<div class="sub" style="color:{OX};top:450px">{d} · {line}</div>' + lot(80, 90, OX, l) + crest(1360, 70, 120, OX)
            + f'<div style="position:absolute;left:0;right:0;top:640px;height:160px;background:{OX}"></div>' + ruo(SNOW, 700) + '</div>')
def L2(n, d, a, line):   # Oxblood with foil: Oxblood label, the name in Snow, the crest in gold foil, a thin area-colour stripe
    c, l = A[a]
    return (f'<div class="lb" style="background:{OX}">' + f'<div style="position:absolute;left:0;right:0;top:0;height:34px;background:{c}"></div>'
            + crest(780, 70, 150, '#C9A24A', 'filter:drop-shadow(0 0 1px #fff6) drop-shadow(1px 1px 0 #8c6a1f)')
            + f'<div class="nm" style="color:{SNOW};top:250px">{n}</div><div class="sub" style="color:#E9C9CE;top:500px">{d} · {line}</div>'
            + lot(80, 90, '#E9C9CE', 'transparent') + wm(1300, 100, 300, SNOW) + ruo('#E9C9CE', 690) + '</div>')
def L3(n, d, a, line):   # Holo: Snow label, a holographic band with the wordmark, the name in the area colour
    c, l = A[a]
    return (f'<div class="lb" style="background:{SNOW}">' + f'<div style="position:absolute;left:0;right:0;top:0;height:190px;background:{HOLO}"></div>'
            + wm(700, 50, 320, OX) + f'<div class="nm" style="color:{c};top:250px">{n}</div>'
            + f'<div class="sub" style="color:{OX};top:500px">{d} · {line}</div>' + lot(80, 230, OX, SNOW) + crest(1360, 230, 120, c)
            + ruo(OX, 690) + '</div>')
CSS = '''body{margin:0;background:#E7E3DC;font-family:Outfit} .grid{display:grid;grid-template-columns:repeat(3,1720px);gap:60px;padding:60px}
.lb{position:relative;width:1720px;height:800px;border-radius:40px;overflow:hidden}
.nm{position:absolute;left:0;right:0;text-align:center;font:800 230px/1 Outfit;letter-spacing:.01em}
.sub{position:absolute;left:0;right:0;text-align:center;font:600 64px Outfit} h3{font:800 60px Outfit;color:#6E1C2A;margin:0 0 20px}'''
rows = ''
for title, f in (('1 · Tight', L1), ('2 · Oxblood + gold foil', L2), ('3 · Holographic', L3)):
    rows += f'<div style="grid-column:1/-1"><h3>{title}</h3></div>' + ''.join(f(*p) for p in P)
open(os.path.join(H, 'labels.html'), 'w').write(f'''<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@600;700;800&display=swap" rel="stylesheet"><style>{CSS}</style></head><body><div class="grid">{rows}</div></body></html>''')
print('ok')

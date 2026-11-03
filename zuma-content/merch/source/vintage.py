# ZUMA track & trail: 70s track-club cuts and trims, 80s trail fabrics and patches. Faded, garment-dyed colour; cracked prints;
# woven and felt patches. Drawn as textured flats.
import os
H = os.path.dirname(os.path.abspath(__file__))
ns = {'__file__': os.path.join(H, 'build.py')}; exec(open(os.path.join(H, 'build.py')).read(), ns)
WM, WW, CD = ns['WM'], ns['WW'], ns['CD']
OX = '#6E1C2A'
# sun-faded versions of the brand: vintage white, washed Oxblood, faded area colours
VW, VOX, CREAM = '#EEE5D3', '#7A3440', '#E4D6BC'
FADE = {'metabolic': '#5E7FB8', 'tissue': '#5E8E68', 'dermal': '#D9805A', 'endocrine': '#C9A04A', 'neuro': '#8471B0', 'oxblood': VOX}
LINE = 'stroke="#3A2A2C" stroke-width="1.6" stroke-linejoin="round"'
STITCH = 'fill="none" stroke="#3A2A2C" stroke-width=".8" stroke-dasharray="3 2.5" opacity=".5"'
DEFS = '''<defs>
<filter id="fab" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="3" seed="4"/>
 <feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .16 0"/><feComposite in2="SourceGraphic" operator="in"/><feBlend in="SourceGraphic" mode="multiply"/></filter>
<filter id="crack"><feTurbulence type="fractalNoise" baseFrequency="1.6" numOctaves="2" seed="9" result="n"/>
 <feColorMatrix in="n" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2.0 1.9" result="m"/><feComposite in="SourceGraphic" in2="m" operator="in"/></filter>
<filter id="felt"><feTurbulence type="fractalNoise" baseFrequency="2.4" numOctaves="2" seed="2"/><feDisplacementMap in="SourceGraphic" scale="1.6"/></filter>
<pattern id="mesh" width="6" height="6" patternUnits="userSpaceOnUse"><circle cx="3" cy="3" r="1.2" fill="#000" opacity=".13"/></pattern>
<pattern id="cord" width="5" height="40" patternUnits="userSpaceOnUse"><rect width="2.6" height="40" fill="#000" opacity=".12"/></pattern>
</defs>'''
def wm(x, y, w, c, filt='crack'):
    return f'<svg x="{x}" y="{y}" width="{w}" height="{w * 100 / WW:.2f}" viewBox="0 0 {WW} 100"><path fill="{c}" fill-rule="evenodd" d="{WM["zuma"]}" filter="url(#{filt})"/></svg>'
def crest(x, y, w, c, filt='crack'):
    return f'<svg x="{x}" y="{y}" width="{w}" height="{w * 100 / 104.26:.2f}" viewBox="0 0 104.26 100"><path fill="{c}" fill-rule="evenodd" d="{CD}" filter="url(#{filt})"/></svg>'
def arch(cx, cy, r, text, size, c, filt='crack'):
    k = abs(hash(text + str(cx))) % 9999
    return (f'<defs><path id="a{k}" d="M{cx - r} {cy} A{r} {r} 0 0 1 {cx + r} {cy}"/></defs>'
            f'<text font-family="Outfit" font-weight="800" font-size="{size}" fill="{c}" letter-spacing="2" text-anchor="middle" filter="url(#{filt})">'
            f'<textPath href="#a{k}" startOffset="50%">{text}</textPath></text>')
def patch(cx, cy, w, h, bg, fg, kind='woven'):
    """A woven (fine, sharp edge, merrowed border) or felt (soft, chain-stitched) patch with the crest and the wordmark."""
    bord = (f'<rect x="{cx - w/2}" y="{cy - h/2}" width="{w}" height="{h}" rx="{h*.18}" fill="{bg}" stroke="{fg}" stroke-width="2.4" stroke-dasharray="1.2 1"/>'
            if kind == 'woven' else f'<rect x="{cx - w/2}" y="{cy - h/2}" width="{w}" height="{h}" rx="{h*.5}" fill="{bg}" filter="url(#felt)"/>')
    return bord + crest(cx - w/2 + h*.18, cy - h*.32, h*.64, fg, 'none') + wm(cx - w/2 + h*.95, cy - h*.13, w - h*1.2, fg, 'none')

def svg(vb, inner): return f'<svg viewBox="{vb}" class="g">{DEFS}{inner}</svg>'
# ---- ringer tee, 70s cut (shorter, slimmer) in vintage white, garment-dyed; arched ZUMA over the crest, cracked print
TEE = 'M162 46 {neck} 238 46 L270 54 L352 128 L326 160 L294 144 L296 400 Q200 408 104 400 L106 144 L74 160 L48 128 L130 54 Z'
def ringer(trim, back=False, body=VW):
    neck = 'Q200 58' if back else 'Q200 84'; p = TEE.format(neck=neck)
    cuffs = (f'<path d="M48 128 L74 160 L85 149 L59 117 Z" fill="{trim}" {LINE}/><path d="M352 128 L326 160 L315 149 L341 117 Z" fill="{trim}" {LINE}/>')
    art = (wm(166, 70, 68, VOX) if back else arch(200, 196, 70, 'ZUMA', 38, VOX) + crest(176, 176, 48, VOX) + f'<text x="200" y="250" text-anchor="middle" font-family="Outfit" font-weight="600" font-size="13" fill="{VOX}" letter-spacing="3" filter="url(#crack)">EST. 2026</text>')
    return svg('0 0 400 430', f'<path d="{p}" fill="{body}" {LINE} filter="url(#fab)"/>{cuffs}'
               f'<path d="M162 46 {neck} 238 46" fill="none" stroke="{trim}" stroke-width="12" stroke-linecap="round"/><path d="M162 46 {neck} 238 46" fill="none" {LINE}/>{art}'
               f'<path d="M106 144 L130 58 M294 144 L270 58" {STITCH}/><path d="M108 390 Q200 398 292 390" {STITCH}/>')
# ---- 70s split-hem track short: nylon, rounded side splits, contrast binding; crest small on the left leg
SPLIT = 'M80 40 L320 40 L332 196 Q326 206 312 200 Q300 218 222 222 L200 128 L178 222 Q100 218 88 200 Q74 206 68 196 Z'
def track_short(body, bind):
    return svg('0 0 400 250', f'<path d="{SPLIT}" fill="{body}" {LINE} filter="url(#fab)"/>'
               f'<path d="M68 196 Q74 206 88 200 Q100 218 178 222 M332 196 Q326 206 312 200 Q300 218 222 222" fill="none" stroke="{bind}" stroke-width="7" stroke-linecap="round"/>'
               f'<path d="M88 200 L80 150 M312 200 L320 150" fill="none" stroke="{bind}" stroke-width="5"/>'
               f'<rect x="80" y="40" width="240" height="22" fill="{bind}" {LINE}/><path d="M200 62 L200 128" {STITCH}/>' + crest(100, 156, 36, VW))
# ---- 80s trail short: heavier nylon, webbing belt with a buckle, side pocket, woven patch
TRAIL = 'M76 40 L324 40 L338 228 L222 234 L200 120 L178 234 L62 228 Z'
def trail_short(body):
    return svg('0 0 400 260', f'<path d="{TRAIL}" fill="{body}" {LINE} filter="url(#fab)"/>'
               f'<rect x="76" y="40" width="248" height="20" fill="#2F2A26" {LINE}/><rect x="186" y="37" width="28" height="26" rx="4" fill="#1E1B19" stroke="#888" stroke-width="2"/>'
               f'<path d="M92 70 Q110 120 96 168 M308 70 Q290 120 304 168" {STITCH}/><path d="M200 60 L200 120" {STITCH}/>'
               + patch(126, 196, 92, 30, CREAM, VOX))
# ---- 80s trail five-panel: corduroy crown, nylon brim, woven patch front
def cap(crown, brim):
    return svg('0 0 400 250', f'<path d="M78 196 Q84 74 200 64 Q316 74 322 196 Q200 182 78 196 Z" fill="{crown}" {LINE} filter="url(#fab)"/>'
               f'<path d="M78 196 Q84 74 200 64 Q316 74 322 196 Q200 182 78 196 Z" fill="url(#cord)" opacity=".7"/>'
               f'<path d="M150 70 Q160 130 154 190 M250 70 Q240 130 246 190" {STITCH}/>'
               f'<path d="M86 188 Q200 172 314 188 Q334 206 320 222 Q200 244 80 222 Q66 206 86 188 Z" fill="{brim}" {LINE}/><path d="M94 214 Q200 234 306 214" {STITCH}/>'
               + patch(200, 136, 128, 40, CREAM, VOX))
# ---- tube socks, two stripes
def sock(s1, s2):
    return svg('0 0 200 320', f'<path d="M70 20 L130 20 L130 230 Q130 290 80 296 L40 296 Q20 296 22 276 Q24 258 52 250 L70 238 Z" fill="{VW}" {LINE} filter="url(#fab)"/>'
               f'<rect x="70" y="40" width="60" height="14" fill="{s1}"/><rect x="70" y="62" width="60" height="14" fill="{s2}"/><rect x="70" y="20" width="60" height="12" fill="#E2D8C4" {LINE}/>' + crest(86, 96, 28, VOX))

cards = []
def card(t, note, *svgs, span=1): cards.append(f'<figure style="grid-column:span {span}"><div class="pair">{"".join(svgs)}</div><figcaption><b>{t}</b><span>{note}</span></figcaption></figure>')
card('Ringer tee', 'Vintage white, garment-dyed, a slim 70s cut. The collar and cuffs in a faded area colour. Front: ZUMA arched over the crest, EST. 2026, a cracked print in washed Oxblood. Back: the wordmark at the nape.',
     ringer(FADE['metabolic']), ringer(FADE['metabolic'], True), span=2)
card('Split track short', '70s nylon split-hem short, faded area colour, Oxblood binding round the hem and splits, small crest on the leg.',
     track_short(FADE['metabolic'], VOX), track_short(FADE['tissue'], VOX))
card('Trail short', '80s trail short in heavier nylon, black webbing belt, a woven ZUMA patch on the leg.',
     trail_short('#8C7A5E'), trail_short(FADE['oxblood']))
card('Trail five-panel', 'Corduroy crown, nylon brim, the woven ZUMA patch front.', cap(VOX, '#4A2A2E'), cap('#8C7A5E', '#5A4A36'))
card('Tube socks', 'Vintage white, two stripes in the area colour and Oxblood, the crest on the cuff.', sock(FADE['metabolic'], VOX), sock(FADE['dermal'], VOX))
CSS = ns['CSS'] + '.row{grid-template-columns:repeat(2,1fr)}'
html = f'''<!doctype html><html><head><meta charset="utf-8"><title>ZUMA track and trail</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800&display=swap" rel="stylesheet"><style>{CSS}</style></head><body>
<section><h2>ZUMA track &amp; trail</h2><div class="row">{''.join(cards)}</div></section></body></html>'''
open(os.path.join(H, 'vintage.html'), 'w').write(html); print('ok')

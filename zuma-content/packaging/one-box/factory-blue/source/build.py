# The ONE box in ZUMA blue (#1E74A8): the approved plain carton v3 B, no compound name (the round sticker names it), every face vector.
# Writes the factory art (outside print + cut + crease + notes), the inside flood and the master die line as SVG and exact-size PDF/.ai.
import os, re, sys
S = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'; OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
os.environ['BOXCOL'] = BLUE = '#1E74A8'; os.environ['BOXTAG'] = 'onebox'
src = open(S + '/gbox/colour.py').read(); src = src.split("for mode in ('sticker', 'bare'):")[0]
ns = {'__name__': 'onebox', '__file__': S + '/gbox/colour.py'}; exec(src, ns)
P, G = ns['P'], ns['G']
front = lambda p, v: ns['front'](p, v, None); right, back, left = ns['right'], ns['back'], G['left']
SNOW, OX, crest = G['SNOW'], G['OX'], G['crest']
def panel(fn, x): return f'<svg x="{x}" y="40" width="20" height="40" viewBox="0 0 20 40" overflow="visible">{fn(("", "", "supplies", ""), "B")}</svg>'
pr = [f'<rect x="9" y="39" width="89" height="42" fill="{SNOW}"/>', f'<rect x="9" y="74" width="89" height="7" fill="{OX}"/>',
      panel(left, 17), panel(front, 37), panel(right, 57), panel(back, 77), f'<rect x="9" y="74" width="8" height="7" fill="{OX}"/>',
      f'<rect x="76" y="9" width="22" height="31" fill="{BLUE}"/>', f'<g transform="rotate(180 87 30)">{crest(87 - 4.5, 30 - 4.5 * 0.96, 9, SNOW)}</g>']
notes = ('<g font-family="Helvetica, Arial" font-size="1.6" fill="#555">'
         '<text x="10" y="6">ZUMA box · ONE design for every product · ZUMA blue #1E74A8 · the round sticker names the compound · 1:1 mm · bleed 1 mm</text>'
         '<text x="10" y="100">CMYK + Oxblood #6E1C2A (match) · top crest knocked out to white board · all type outlined 文字已转曲</text></g>')
art = (f'<svg {P.NS} viewBox="{P.VB}" width="107mm" height="104mm">' + P.layer('PRINT_CMYK', 'PRINT 印刷', ''.join(pr)) + P.cut() + P.crease()
       + '</svg>')   # notes live in the README, so the print file carries no live text
inside = (f'<svg {P.NS} viewBox="{P.VB}" width="107mm" height="104mm">' + P.layer('PRINT_INSIDE', f'INSIDE 内面 · 100% flood {BLUE}', f'<rect x="9" y="9" width="89" height="86" fill="{BLUE}"/>')
          + f'<g transform="translate(107 0) scale(-1 1)">{P.cut()}{P.crease()}</g>' + '</svg>')
files = {'ZUMA-box-blue-outside': art, 'ZUMA-box-blue-inside': inside, 'ZUMA-box-dieline-master': P.master()}
import cairosvg
for n, s in files.items():
    open(f'{OUT}/{n}.svg', 'w').write(s); cairosvg.svg2pdf(bytestring=s.encode(), write_to=f'{OUT}/{n}.pdf')
print('ok', list(files))

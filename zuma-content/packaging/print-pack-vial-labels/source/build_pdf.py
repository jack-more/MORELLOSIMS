# Rev 4 vial labels, vector PDF: exact page (46 x 23 mm, or 69.53 x 34.77 mm for 03/08), TrimBox at the cut, type as outlines.
import json, re, sys
sys.path.insert(0, '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad/lv')
from pdfw import PDFPen, svgpath, rgb, write, mm
from fontTools.ttLib import TTFont
S = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'; OUT = sys.argv[1]
OPS = json.load(open(S + '/lv/ops.json'))
F = {('outfit', w): TTFont(f'{S}/font/Outfit-{w}.ttf') for w in (700, 800, 900)}; F[('plex', 600)] = TTFont(f'{S}/font/PlexMono-600.ttf')
GS = {k: f.getGlyphSet() for k, f in F.items()}; CACHE = {}
def glyph(fk, ch):
    if (fk, ch) not in CACHE:
        name = F[fk].getBestCmap().get(ord(ch))
        if name is None: raise SystemExit(f'missing {ch!r} in {fk}')
        p = PDFPen(GS[fk]); GS[fk][name].draw(p); CACHE[fk, ch] = ' '.join(p.o)
    return CACHE[fk, ch]
def fontkey(font):
    m = re.match(r'(\d+)\s+([\d.]+)px\s+"?([^",]+)', font); fam = m.group(3).lower()
    return (('plex', 600) if 'plex' in fam else ('outfit', int(m.group(1)))), float(m.group(2))
def cm(m): return 'cm'.join([' '.join(f'{v:.6f}' for v in m) + ' ', ''])
for no, ops in OPS.items():
    k = 65 / 43 if no in ('03', '08') else 1; w, h = 46 * k, 23 * k; sx = mm(w) / 3080
    c = [f'{sx:.8f} 0 0 {-sx:.8f} 0 {mm(h):.4f} cm', '0 0 3080 1540 re W n']          # canvas px -> points, y down; clip to the page
    for o in ops:
        c.append('q ' + cm(o['m']))
        if o['k'] == 'rect': c.append(f'{rgb(o["fill"])} rg {o["x"]} {o["y"]} {o["w"]} {o["h"]} re f')
        elif o['k'] == 'srect': c.append(f'{rgb(o["stroke"])} RG {o["lw"]} w {o["x"]} {o["y"]} {o["w"]} {o["h"]} re S')
        elif o['k'] == 'path': c.append(f'{rgb(o["fill"])} rg {svgpath(o["d"])} ' + ('f*' if o['rule'] == 'evenodd' else 'f'))
        elif o['k'] == 'text':
            fk, size = fontkey(o['font']); s = size / 1000; c.append(f'{rgb(o["fill"])} rg')
            for ch, a in zip(o['s'], o['adv']):
                if not ch.isspace(): c.append(f'q {s:.6f} 0 0 {-s:.6f} {o["x"] + a:.4f} {o["y"]:.4f} cm {glyph(fk, ch)} f Q')
        c.append('Q')
    write(f'{OUT}/zuma-label-{no}-vector.pdf', w, h, 1.5 * k, '\n'.join(c))
print('ok', len(OPS))

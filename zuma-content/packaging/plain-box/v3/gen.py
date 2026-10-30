# Plain box v3: the Lightbox grid printed flat in tonal steps of the area colour, crest on the front.
# A = Lightbox (Snow board, grid is the hero). B = Lightbox + band (Nala-style Oxblood band, slim Snow top band).
import os
HERE = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(HERE, 'base.py')).read())

DARK = '#1a1012'
# Window-box panel layout (geomE), converted to SVG coords (y down, panel 20 x 40 mm).
# The die-cut window and the panel above it merge into one tall printed centre panel.
GRID = {  # id: (x, y, w, h, tone)
    'tall':  (5.0, 10.5, 10.0, 22.0, 'base'),
    'wide':  (5.0, 4.0, 10.0, 4.5, 'tint1'),
    'left':  (1.5, 4.0, 2.0, 17.5, 'tint2'),
    'right': (16.5, 10.5, 2.0, 17.0, 'shade'),
    'rtop':  (16.5, 4.0, 2.0, 4.5, 'tint1'),
    'small': (5.0, 34.5, 6.5, 2.2, 'shade'),
}

def tones(col):
    return {'base': col, 'tint1': mix(col, SNOW, .38), 'tint2': mix(col, SNOW, .62),
            'shade': mix(col, DARK, .28), 'deep': mix(col, DARK, .45)}

def lit(gid, x, y, w, h, c):
    """A panel that reads as lit: a faint diagonal glow over the flat ink."""
    hi = mix(c, '#ffffff', .16)
    return (f'<defs><linearGradient id="g{gid}" x1="0" y1="0" x2="0.35" y2="1">'
            f'<stop offset="0" stop-color="{hi}"/><stop offset=".55" stop-color="{c}"/><stop offset="1" stop-color="{mix(c, DARK, .06)}"/>'
            f'</linearGradient></defs><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#g{gid})"/>')

def name_size(name, width_mm, max_pt):
    # Outfit 700 caps run about 0.62 em per glyph; fit the name to the panel width.
    return min(max_pt, width_mm / (0.62 * max(len(name), 1)) / PT)

def front(p, variant):
    name, dose, area, full = p; label, col = AREAS[area]; T = tones(col)
    g = [f'<rect width="{W}" height="{H}" fill="{SNOW}"/>']
    for k, (x, y, w, h, tone) in GRID.items():
        if variant == 'B' and k == 'small':
            continue  # the Oxblood band sits where the small bottom panel was
        g.append(lit(f'{k}{area}{variant}', x, y, w, h, T[tone]))
    x, y, w, h, _ = GRID['tall']
    cx = x + w / 2
    # Crest reversed out of the tall panel (Snow), Nala-sized: it owns the front.
    g.append(crest(cx - 3.6, y + 2.2, 7.2, SNOW))
    # Product name and dose at the foot of the tall panel.
    s = name_size(name, w - 1.6, 7.2)
    g.append(t(cx, y + h - 4.1, s * PT, name, 'Outfit', 700, SNOW, anchor='middle', ls=0.04))
    g.append(t(cx, y + h - 2.2, 3.1 * PT, dose.upper(), 'IBM Plex Mono', 600, SNOW, anchor='middle', ls=0.06))
    g.append(f'<rect x="{x + 1.4}" y="{y + h - 7.3}" width="{w - 2.8}" height="0.12" fill="{SNOW}" opacity=".55"/>')
    g.append(t(cx, y + h - 6.2, 1.9 * PT, label.upper(), 'IBM Plex Mono', 600, SNOW, anchor='middle', ls=0.06))
    if variant == 'A':
        g.append(wordmark(12.6, 35.0, 5.9, OX))
    else:
        g += [f'<rect x="0" y="0" width="{W}" height="2.4" fill="{SNOW}"/>',
              t(W / 2, 1.75, 2.2 * PT, 'RESEARCH COMPOUND', 'IBM Plex Mono', 600, mix(INK, SNOW, .35), anchor='middle', ls=0.18),
              f'<rect x="0" y="34.0" width="{W}" height="6.0" fill="{OX}"/>',
              wordmark(W / 2 - 4.2, 35.2, 8.4, SNOW),
              t(W / 2, 39.05, 2.0 * PT, 'FOR LABORATORY RESEARCH USE ONLY', 'IBM Plex Mono', 500, mix(SNOW, OX, .25), anchor='middle', ls=0.06)]
    return ''.join(g)

def right(p, variant):
    """The wall continues round the corner: panels on the same rows, plus the product line set vertically."""
    name, dose, area, full = p; label, col = AREAS[area]; T = tones(col)
    g = [f'<rect width="{W}" height="{H}" fill="{SNOW}"/>',
         lit(f'r1{area}{variant}', 1.5, 4.0, 9.0, 4.5, T['tint2']),
         lit(f'r2{area}{variant}', 1.5, 10.5, 4.0, 17.0, T['tint1']),
         lit(f'r3{area}{variant}', 12.0, 4.0, 6.5, 4.5, T['base']),
         t(9.6, 32.0, 3.6 * PT, f'{name}  ·  {dose}', 'Outfit', 700, OX, rot=-90, ls=0.03),
         t(12.2, 32.0, 2.5 * PT, f'{full}  ·  {label}', w=500, fill=INK, rot=-90),
         t(14.6, 32.0, 2.4 * PT, 'Every lot tested before it ships.', w=500, fill=mix(INK, SNOW, .25), rot=-90),
         t(16.6, 32.0, 2.4 * PT, '3 mL vial · lyophilized', 'IBM Plex Mono', 500, mix(INK, SNOW, .25), rot=-90)]
    if variant == 'B':
        g += [f'<rect x="0" y="0" width="{W}" height="2.4" fill="{SNOW}"/>',
              f'<rect x="0" y="34.0" width="{W}" height="6.0" fill="{OX}"/>',
              t(W / 2, 37.6, 2.2 * PT, 'NOT FOR HUMAN OR VETERINARY USE', 'IBM Plex Mono', 500, mix(SNOW, OX, .25), anchor='middle', ls=0.05)]
    return ''.join(g)

def left(p, variant):
    g = [f'<rect width="{W}" height="{H}" fill="{SNOW}"/>', crest(4.0, 13.0, 12, mix(SNOW, '#bdb6aa', .5))]
    if variant == 'B':
        g += [f'<rect x="0" y="0" width="{W}" height="2.4" fill="{SNOW}"/>', f'<rect x="0" y="34.0" width="{W}" height="6.0" fill="{OX}"/>']
    return ''.join(g)

def back(p, variant):
    name, dose, area, full = p; label, col = AREAS[area]; T = tones(col)
    m = 1.5
    bot = 33.0 if variant == 'B' else 38.6
    g = [f'<rect width="{W}" height="{H}" fill="{SNOW}"/>',
         lit(f'b1{area}{variant}', m, 4.0, 17.0, 1.2, T['base']),
         qr(m, 7.0, 8.0, OX),
         t(11.0, 9.0, 2.5 * PT, 'Scan for', w=600, fill=INK),
         t(11.0, 10.2, 2.5 * PT, 'lot reports', w=600, fill=INK),
         t(11.0, 12.6, 2.2 * PT, 'zumatides.com/lots', 'IBM Plex Mono', 500, INK),
         t(m, 19.4, 3.4 * PT, f'{name} · {dose}', 'Outfit', 700, OX),
         t(m, 20.9, 2.5 * PT, full, w=500, fill=INK),
         t(m, 22.1, 2.5 * PT, label, w=500, fill=mix(INK, SNOW, .3)),
         f'<rect x="{m}" y="24.4" width="17" height="0.12" fill="{mix(INK, SNOW, .6)}"/>',
         t(m, 26.3, 2.5 * PT, 'For laboratory research use only.', w=600, fill=INK),
         t(m, 27.5, 2.5 * PT, 'Not for human or veterinary use.', w=600, fill=INK),
         t(m, 29.6, 2.3 * PT, 'Store sealed, cold and away from light.', w=500, fill=mix(INK, SNOW, .25))]
    if variant == 'B':
        g += [f'<rect x="0" y="0" width="{W}" height="2.4" fill="{SNOW}"/>', f'<rect x="0" y="34.0" width="{W}" height="6.0" fill="{OX}"/>',
              t(W / 2, 37.6, 2.6 * PT, 'zumatides.com', 'IBM Plex Mono', 500, mix(SNOW, OX, .15), anchor='middle', ls=0.05)]
    else:
        g.append(t(m, bot, 2.3 * PT, 'zumatides.com', 'IBM Plex Mono', 500, mix(INK, SNOW, .35)))
    return ''.join(g)

def top(p):
    col = AREAS[p[2]][1]
    return f'<rect width="20" height="20" fill="{col}"/>' + crest(5.5, 5.7, 9, OX)

def mk(variant):
    sides = {'front': front, 'right': right, 'left': left, 'back': back}
    return (lambda p, side: sides[side](p, variant)), top

TRIO = [PRODUCTS[0], PRODUCTS[4], PRODUCTS[5]]  # RT-3 Metabolic, BPC+TB Tissue, GHK-Cu Dermal

def look(v, bg='#E7E3DC', k=24):
    global DIRS
    DIRS = {v: mk(v)}
    slots = ''.join(f'<div class="slot" style="margin:0 {k*5.2}px"><div class="shadow" style="width:{k*34}px;height:{k*8}px;'
                    f'background:rgba(40,30,25,.24)"></div>{box_html(v, p, k, -32, -9)}</div>' for p in TRIO)
    return page(f'<div class="stage" style="position:absolute;inset:0;align-items:center;padding-top:120px">{slots}</div>', bg, 3000, 2000)

def flat(v, p=PRODUCTS[0], bg='#EDE8E0', k=24):
    global DIRS
    DIRS = {v: mk(v)}
    pan, tp = DIRS[v]
    lab = lambda s: f'<div class="cap" style="color:#5a4a48;margin-top:16px;font-size:16px">{s}</div>'
    cell = lambda inner, w, h, l: (f'<div style="display:flex;flex-direction:column;align-items:flex-start">'
                                   f'<div style="width:{w*k}px;height:{h*k}px;box-shadow:0 2px 14px rgba(0,0,0,.12)">{face_svg(inner, w, h, .06)}</div>{lab(l)}</div>')
    row_ = ''.join(cell(pan(p, s), 20, 40, l) for s, l in (('left', 'Left side · P1'), ('front', 'Front · P2'), ('right', 'Right side · P3'), ('back', 'Back · P4')))
    col = AREAS[p[2]][1]
    tops = cell(tp(p), 20, 20, 'Top flap · Oxblood foil crest') + cell(f'<rect width="20" height="20" fill="{col}"/>', 20, 20, 'Inside · area colour flood')
    title = 'Lightbox' if v == 'A' else 'Lightbox + band'
    desc = ('The window box\'s Lightbox grid, printed flat in tonal steps of the area colour. The crest is reversed out of the tall '
            'panel in Snow, so the brand owns the front; the product name sits at the foot of that panel. The wall continues round '
            'the corner onto the side. Top flap in the area colour with the Oxblood foil crest; inside flooded in the area colour.'
            if v == 'A' else
            'The same grid, plus a Nala-style Oxblood band that wraps all four sides with the zuma tides wordmark in Snow and the '
            'research-use line, and a slim Snow top band. Top flap in the area colour with the Oxblood foil crest; inside flooded.')
    head = (f'<div style="position:absolute;left:80px;top:60px"><div class="cap" style="color:#6E1C2A;font-size:18px">ZUMA TIDES · PLAIN CARTON V3 · '
            f'{title.upper()} · {p[0]} {p[1].upper()} · PANELS AT ABOUT 6:1</div>'
            f'<div style="font:800 64px Outfit;color:#1a1012;margin-top:14px">{title}</div>'
            f'<div style="font:500 22px Figtree;color:#3a2e2c;margin-top:8px;max-width:2000px">{desc}</div></div>')
    body = (head + f'<div style="position:absolute;left:80px;top:300px;display:flex;gap:56px;align-items:flex-start">{row_}'
            f'<div style="display:flex;flex-direction:column;gap:40px">{tops}</div></div>')
    return page(body, bg, 3300, 1400)

jobs = {'look-A': look('A'), 'look-B': look('B'), 'flat-A': flat('A'), 'flat-B': flat('B')}
for n, html in jobs.items(): open(f'{OUT}/{n}.html', 'w').write(html)
print('\n'.join(jobs))

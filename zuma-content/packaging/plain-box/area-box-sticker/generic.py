# The plain box without the compound name (one box per research area); the name comes on a sticker, put on at packing.
# Two sticker options: A Snow with Oxblood name, B Oxblood with Snow name. Builds look-generic-A/B.html (same 3D preview as look-B).
import os, sys, importlib.util
S = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'
SRC = S + '/plainbox/v3-pack/src'; sys.path.insert(0, SRC); sys.argv = ['x']
spec = importlib.util.spec_from_file_location('pack', os.path.join(SRC, 'pack.py')); P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
G = P.G
GRID, lit, tones, crest, t, wordmark, mix, AREAS = (G[k] for k in ('GRID', 'lit', 'tones', 'crest', 't', 'wordmark', 'mix', 'AREAS'))
SNOW, OX, INK, W, H, PT = (G[k] for k in ('SNOW', 'OX', 'INK', 'W', 'H', 'PT'))
orig_right, orig_back = G['right'], G['back']
STYLE = {'A': (SNOW, OX), 'B': (OX, SNOW)}

def sticker(name, style):
    bg, fg = STYLE[style]
    x, y, w, h, _ = GRID['tall']
    sw, sh = w - 1.6, 4.6; sx, sy = x + 0.8, y + h - sh - 0.9
    s = G['name_size'](name, sw - 1.4, 6.4)
    return (f'<g><rect x="{sx + 0.12}" y="{sy + 0.18}" width="{sw}" height="{sh}" rx="0.6" fill="#000" opacity=".18"/>'
            f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="0.6" fill="{bg}"/>'
            + t(sx + sw / 2, sy + sh / 2 + s * PT * 0.36, s * PT, name, 'Outfit', 700, fg, anchor='middle', ls=0.03) + '</g>')

def front_generic(p, variant, style=None):
    name, dose, area, full = p; label, col = AREAS[area]; T = tones(col)
    g = [f'<rect width="{W}" height="{H}" fill="{SNOW}"/>']
    for k, (x, y, w, h, tone) in GRID.items():
        if k == 'small': continue
        g.append(lit(f'{k}{area}{variant}', x, y, w, h, T[tone]))
    x, y, w, h, _ = GRID['tall']; cx = x + w / 2
    g.append(crest(cx - 3.6, y + 2.2, 7.2, SNOW))
    # the area line stays printed; the name space is left for the sticker
    g.append(f'<rect x="{x + 1.4}" y="{y + h - 7.3}" width="{w - 2.8}" height="0.12" fill="{SNOW}" opacity=".55"/>')
    g.append(t(cx, y + h - 6.2, 1.9 * PT, label.upper(), 'IBM Plex Mono', 600, SNOW, anchor='middle', ls=0.06))
    g += [f'<rect x="0" y="0" width="{W}" height="2.4" fill="{SNOW}"/>',
          t(W / 2, 1.75, 2.2 * PT, 'RESEARCH COMPOUND', 'IBM Plex Mono', 600, mix(INK, SNOW, .35), anchor='middle', ls=0.18),
          f'<rect x="0" y="34.0" width="{W}" height="6.0" fill="{OX}"/>', wordmark(W / 2 - 6.5, 34.75, 13.0, SNOW),
          t(W / 2, 39.2, 2.0 * PT, 'FOR LABORATORY RESEARCH USE ONLY', 'IBM Plex Mono', 500, mix(SNOW, OX, .25), anchor='middle', ls=0.06)]
    if style: g.append(sticker(name, style))
    return ''.join(g)

def right_generic(p, variant):
    name, dose, area, full = p; label, col = AREAS[area]; T = tones(col)
    g = [f'<rect width="{W}" height="{H}" fill="{SNOW}"/>',
         lit(f'r1{area}{variant}', 1.5, 4.0, 9.0, 4.5, T['tint2']), lit(f'r2{area}{variant}', 1.5, 10.5, 4.0, 17.0, T['tint1']),
         lit(f'r3{area}{variant}', 12.0, 4.0, 6.5, 4.5, T['base']),
         t(9.6, 32.0, 3.6 * PT, label, 'Outfit', 700, OX, rot=-90, ls=0.03),
         t(12.2, 32.0, 2.4 * PT, 'Every lot tested before it ships.', w=500, fill=mix(INK, SNOW, .25), rot=-90),
         f'<rect x="0" y="0" width="{W}" height="2.4" fill="{SNOW}"/>', f'<rect x="0" y="34.0" width="{W}" height="6.0" fill="{OX}"/>',
         t(W / 2, 37.6, 2.2 * PT, 'NOT FOR HUMAN OR VETERINARY USE', 'IBM Plex Mono', 500, mix(SNOW, OX, .25), anchor='middle', ls=0.05)]
    return ''.join(g)

TRIO = [pp for pp in P.PRODUCTS if pp[0] in ('RT-3', 'BPC+TB', 'GHK-Cu')]
TRIO = sorted(TRIO, key=lambda pp: ['RT-3', 'BPC+TB', 'GHK-Cu'].index(pp[0]))
for style in ('none', 'A', 'B'):
    G['front'] = (lambda p, v, s=style: front_generic(p, v, None if s == 'none' else s))
    G['right'] = right_generic
    G['TRIO'] = TRIO
    html = G['look']('B')
    open(f'{S}/gbox/look-generic-{style}.html', 'w').write(html)
print('ok')

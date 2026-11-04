# ONE box for every vial: the plain box in the ZUMA grey (the family / shop colour), no compound name, no area line.
# The compound sticker (Snow, Oxblood name) goes on the front panel at packing.
import os, sys
S = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'
ns = {'__name__': 'g'}; exec(open(S + '/gbox/generic.py').read().split('TRIO = [pp for pp')[0], ns)
G, P = ns['G'], ns['P']
GRID, lit, tones, crest, t, wordmark, mix, AREAS = (G[k] for k in ('GRID', 'lit', 'tones', 'crest', 't', 'wordmark', 'mix', 'AREAS'))
SNOW, OX, INK, W, H, PT = (G[k] for k in ('SNOW', 'OX', 'INK', 'W', 'H', 'PT'))
GREY = os.environ['BOXCOL']; TAG = os.environ['BOXTAG']
def front(p, v, name=None):
    T = tones(GREY); g = [f'<rect width="{W}" height="{H}" fill="{SNOW}"/>']
    for k, (x, y, w, h, tone) in GRID.items():
        if k == 'small': continue
        g.append(lit(f'{k}grey', x, y, w, h, T[tone]))
    x, y, w, h, _ = GRID['tall']; cx = x + w / 2
    g.append(crest(cx - 3.6, y + 2.2, 7.2, SNOW))
    g += [f'<rect x="0" y="0" width="{W}" height="2.4" fill="{SNOW}"/>', f'<rect x="0" y="34.0" width="{W}" height="6.0" fill="{OX}"/>',
          wordmark(W / 2 - 6.5, 34.75, 13.0, SNOW),
          t(W / 2, 39.2, 2.1 * PT, 'For laboratory research use only', 'Figtree', 600, mix(SNOW, OX, .2), anchor='middle')]
    if name: g.append(ns['sticker'](name, 'A'))
    return ''.join(g)
def right(p, v):
    T = tones(GREY)
    return ''.join([f'<rect width="{W}" height="{H}" fill="{SNOW}"/>', lit('r1grey', 1.5, 4.0, 9.0, 4.5, T['tint2']), lit('r2grey', 1.5, 10.5, 4.0, 17.0, T['tint1']),
                    lit('r3grey', 12.0, 4.0, 6.5, 4.5, T['base']), t(9.6, 32.0, 3.6 * PT, 'Research, refined.', 'Outfit', 700, OX, rot=-90),
                    t(12.2, 32.0, 2.4 * PT, 'Every lot tested before it ships.', w=500, fill=mix(INK, SNOW, .25), rot=-90),
                    f'<rect x="0" y="0" width="{W}" height="2.4" fill="{SNOW}"/>', f'<rect x="0" y="34.0" width="{W}" height="6.0" fill="{OX}"/>',
                    t(W / 2, 37.6, 2.2 * PT, 'Not for human or veterinary use', 'Figtree', 600, mix(SNOW, OX, .2), anchor='middle')])
def back(p, v):
    T = tones(GREY); m = 1.5; qr = G['qr']
    return ''.join([f'<rect width="{W}" height="{H}" fill="{SNOW}"/>', lit('b1grey', m, 4.0, 17.0, 1.2, T['base']), qr(m, 7.0, 8.0, OX),
        t(11.0, 9.0, 2.5 * PT, 'Scan for', w=600, fill=INK), t(11.0, 10.2, 2.5 * PT, 'lot reports', w=600, fill=INK),
        t(11.0, 12.6, 2.2 * PT, 'zumatides.com/lots', w=600, fill=INK),
        t(m, 19.4, 3.4 * PT, 'Research, refined.', 'Outfit', 700, OX), t(m, 20.9, 2.5 * PT, 'The compound is named on the sticker', w=500, fill=INK),
        t(m, 22.1, 2.5 * PT, 'and on the vial label.', w=500, fill=INK),
        f'<rect x="{m}" y="24.4" width="17" height="0.12" fill="{mix(INK, SNOW, .6)}"/>',
        t(m, 26.3, 2.5 * PT, 'For laboratory research use only.', w=600, fill=INK), t(m, 27.5, 2.5 * PT, 'Not for human or veterinary use.', w=600, fill=INK),
        t(m, 29.6, 2.3 * PT, 'Store sealed, cold and away from light.', w=500, fill=mix(INK, SNOW, .25)),
        f'<rect x="0" y="0" width="{W}" height="2.4" fill="{SNOW}"/>', f'<rect x="0" y="34.0" width="{W}" height="6.0" fill="{OX}"/>',
        t(W / 2, 37.6, 2.6 * PT, 'zumatides.com', w=600, fill=mix(SNOW, OX, .15), anchor='middle')])
G['back'] = back
PR = {p[0]: p for p in P.PRODUCTS}
TRIO = [('RT-3', '', 'supplies', ''), ('BPC+TB', '', 'supplies', ''), ('GHK-Cu', '', 'supplies', '')]
G['TRIO'] = TRIO; G['right'] = right
G['top'] = lambda p: f'<rect width="20" height="20" fill="{GREY}"/>' + crest(5.5, 5.7, 9, SNOW)
for mode in ('sticker', 'bare'):
    G['front'] = (lambda p, v, m=mode: front(p, v, p[0] if m == 'sticker' else None))
    open(f'{S}/gbox/{TAG}-{mode}.html', 'w').write(G['look']('B'))
print('ok', GREY)

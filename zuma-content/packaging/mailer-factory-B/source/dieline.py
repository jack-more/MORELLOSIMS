# Mailer die line / layout sheet (vector, text as outlines): front (side B) with the 44 mm flap, back (side A) with the flap zone marked.
import sys
sys.path.insert(0, '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad/lv')
from pdfw import PDFPen, write, mm
from fontTools.ttLib import TTFont
S = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'
f = TTFont(S + '/font/Outfit-500.ttf'); gs = f.getGlyphSet(); cmap = f.getBestCmap(); hm = f['hmtx']
def text(s, x, y, size, center=False):   # x, y in mm (y down, baseline); outlines
    w = sum(hm[cmap[ord(c)]][0] for c in s) * size / 1000; x0 = x - w / 2 if center else x; o = []; cx = x0
    for c in s:
        n = cmap[ord(c)]
        if c != ' ': p = PDFPen(gs); gs[n].draw(p); o.append(f'q {size / 1000:.5f} 0 0 {-size / 1000:.5f} {cx:.3f} {y:.3f} cm {" ".join(p.o)} f Q')
        cx += hm[n][0] * size / 1000
    return '\n'.join(o)
W, H = 360, 330; G = f'{mm(1):.8f} 0 0 {-mm(1):.8f} 0 {mm(H):.4f} cm'
bx, by = 20, 30            # front (side B): flap 44 mm above the 254 mm face
ax, ay = 190, 74          # back (side A)
c = [G, '0.902 0 0.4941 RG 0.35 w',
     f'{bx} {by} 152.4 {44 + 254} re S', f'{ax} {ay} 152.4 254 re S',
     f'q [2 1.5] 0 d 0 0.6039 0.2667 RG {bx} {by + 44} m {bx + 152.4} {by + 44} l S {ax} {ay + 44} m {ax + 152.4} {ay + 44} l S Q',
     f'q 0.85 0.85 0.85 rg {bx + 4} {by + 6} {152.4 - 8} 22 re f Q',
     '0.2 0.2 0.2 rg',
     text('Side B: front, label side (bamboo)', bx + 76.2, by + 44 + 127, 4.2, True),
     text('Flap 44 mm: folds back onto side A', bx + 76.2, by + 36, 3.4, True),
     text('Self-seal strip', bx + 76.2, by + 19, 3.4, True),
     text('Side A: back (palm)', ax + 76.2, ay + 127, 4.2, True),
     text('Top 44 mm: covered by the flap when sealed', ax + 76.2, ay + 24, 3.4, True),
     text('Pink: cut / outside size 152.4 x 254 mm (#0, 6 x 10 in) + 44 mm flap. Green dashes: the fold.', 20, 15, 3.6),
     text('Print both sides in one spot ink, ZUMA Oxblood (#6E1C2A). Flap and inside: unprinted white.', 20, 21, 3.6)]
write(sys.argv[1], W, H, 0, '\n'.join(c)); print('ok')

# Generates src/partials/wheel.svg: the $ZUMA flywheel (five steps on a ring, the coin in the middle, one dashed proposal).
import math, os
CX, CY, R, NR = 290, 292, 190, 58
steps = [('01', 'Hold'), ('02', 'Pay'), ('03', 'Fill'), ('04', 'Publish'), ('05', 'Verify')]
ang = [-90 + 72 * i for i in range(5)]
P = lambda a, r=R: (CX + r * math.cos(math.radians(a)), CY + r * math.sin(math.radians(a)))
f = lambda v: f'{v:.1f}'
d = math.degrees(math.asin((NR + 12) / R))
out = ['<svg viewBox="0 0 690 664" role="img" aria-labelledby="wheel-t wheel-d" xmlns="http://www.w3.org/2000/svg">',
       '<title id="wheel-t">The $ZUMA loop</title>',
       '<desc id="wheel-d">Five steps in a loop around the $ZUMA token: hold, pay, fill, publish, verify, then back to hold. A dashed branch from pay leads to treasury buybacks, under legal review and not part of launch.</desc>',
       '<defs><marker id="ah" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="3.4" markerHeight="3.4" orient="auto"><path d="M0 0L10 5L0 10z" fill="#BFC3CE"/></marker>',
       '<marker id="ahd" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10z" fill="#BFC3CE" fill-opacity=".8"/></marker></defs>',
       f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" stroke="#1E2129" stroke-width="22"/>',
       f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" stroke="#111319" stroke-width="6"/>']
for i in range(5):
    a1, a2 = ang[i] + d, ang[(i + 1) % 5] - d + (360 if i == 4 else 0)
    (x1, y1), (x2, y2) = P(a1), P(a2)
    out.append(f'<path d="M{f(x1)} {f(y1)}A{R} {R} 0 0 1 {f(x2)} {f(y2)}" fill="none" stroke="#BFC3CE" stroke-width="7" marker-end="url(#ah)"/>')
# the coin: house colours (the token is not a research area)
out += [f'<circle cx="{CX}" cy="{CY}" r="104" fill="#F7F4EE"/>', f'<circle cx="{CX}" cy="{CY}" r="88" fill="#111319"/>', f'<circle cx="{CX}" cy="{CY}" r="70" fill="#1E2129"/>',
        f'<text x="{CX}" y="{CY + 10}" text-anchor="middle" font-family="Schibsted Grotesk, Helvetica Neue, Arial, sans-serif" font-weight="900" font-size="34" fill="#F7F4EE">$ZUMA</text>',
        f'<text x="{CX}" y="{CY + 36}" text-anchor="middle" font-family="IBM Plex Mono, Menlo, monospace" font-weight="600" font-size="13" letter-spacing="1" fill="#BFC3CE">MEMBERS</text>']
for (no, word), a in zip(steps, ang):
    x, y = P(a)
    out += [f'<circle cx="{f(x)}" cy="{f(y)}" r="{NR}" fill="#F7F4EE"/>', f'<circle cx="{f(x)}" cy="{f(y)}" r="{NR - 7}" fill="none" stroke="#BFC3CE" stroke-width="3"/>',
            f'<text x="{f(x)}" y="{f(y - 12)}" text-anchor="middle" font-family="IBM Plex Mono, Menlo, monospace" font-weight="600" font-size="15" fill="#4A4E59">{no}</text>',
            f'<text x="{f(x)}" y="{f(y + 18)}" text-anchor="middle" font-family="Schibsted Grotesk, Helvetica Neue, Arial, sans-serif" font-weight="900" font-size="{24 if len(word) > 5 else 27}" fill="#111319">{word}</text>']
# the dashed proposal, off the Pay node, outside the loop
px, py = P(ang[1])
bx, by, bw, bh = 440, 536, 244, 118
out += [f'<path d="M{f(px + 30)} {f(py + 50)}C{f(px + 120)} {f(py + 120)} {f(bx + 160)} {f(by - 110)} {f(bx + 150)} {by - 10}" fill="none" stroke="#BFC3CE" stroke-opacity=".8" stroke-width="3" stroke-dasharray="9 8" marker-end="url(#ahd)"/>',
        f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="#111319" stroke="#BFC3CE" stroke-width="3" stroke-dasharray="10 8"/>',
        f'<text x="{bx + 16}" y="{by + 34}" font-family="Schibsted Grotesk, Helvetica Neue, Arial, sans-serif" font-weight="900" font-size="20" fill="#F7F4EE">Treasury buybacks</text>',
        f'<text x="{bx + 16}" y="{by + 60}" font-family="IBM Plex Mono, Menlo, monospace" font-weight="600" font-size="14" fill="#BFC3CE">UNDER LEGAL REVIEW</text>',
        f'<text x="{bx + 16}" y="{by + 81}" font-family="IBM Plex Mono, Menlo, monospace" font-weight="600" font-size="14" fill="#BFC3CE">NOT PART OF LAUNCH</text>']
out.append('</svg>')
os.makedirs(os.path.join(os.path.dirname(__file__), '..', 'src', 'partials'), exist_ok=True)
open(os.path.join(os.path.dirname(__file__), '..', 'src', 'partials', 'wheel.svg'), 'w').write('\n'.join(out) + '\n')
print('ok', len('\n'.join(out)))

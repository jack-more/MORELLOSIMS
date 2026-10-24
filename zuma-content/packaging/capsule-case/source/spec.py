# The capsule deboss spec sheet: true-size crest, the unrolled stamp map drawn to scale in mm, the stamp table, the colours.
#   python3 cyc/capsule/spec.py -> spec.html (print to A4 landscape with spec.cjs)
import json, math, os
CAP = os.path.dirname(os.path.abspath(__file__)); SP = os.path.dirname(os.path.dirname(CAP))
d = json.load(open(os.path.join(CAP, 'stamps.json'))); R, L = d['R'], d['L']
T0 = 31.0; D0 = R - R * math.cos(math.radians(T0)); HT = L - D0; CIRC = 2 * math.pi * R
BODY0, BODY1 = R - D0, L - R - D0; SEAM = d['seam_z']; CW = d['crest_w']; CH = CW * 100 / 104.26
s = open(os.path.join(SP, 'site3/src/logo-slot.svg')).read(); a = s.index('<symbol id="zuma-icon"'); icon = s[a:s.index('</symbol>', a) + 9]
COLS = [('Dermal', 'Coral', '#FF6A55'), ('Endocrine', 'Lemon', '#F4D63A'), ('Tissue', 'Lime', '#6CC93A'), ('Metabolic', 'Sky', '#36B3E8'), ('Neuro', 'Lilac', '#A57BF0'), ('House', 'Oxblood', '#6E1C2A')]
# unrolled map: x = arc around (0 at the seam-line datum), y = height from the seat, drawn top = top of capsule
M = 3.2  # px per mm on screen; the SVG viewBox is in mm
def Y(z): return HT - z
uses = []
for st in d['stamps']:
    for dx in (-CIRC, 0, CIRC):
        x = st['arc_mm'] + dx
        if -CW < x < CIRC + CW:
            uses.append(f'<g transform="translate({x:.2f} {Y(st["z_mm"]):.2f}) rotate({st["rot"]})"><use href="#zuma-icon" x="{-CW/2:.2f}" y="{-CH/2:.2f}" width="{CW}" height="{CH:.2f}" fill="#6E1C2A"/></g>')
dim = lambda x1, y1, x2, y2, t, tx, ty: f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="dm"/><text x="{tx}" y="{ty}" class="dt" text-anchor="end">{t}</text>'
mapsvg = f'''<svg class="map" viewBox="-12 -4 {CIRC + 30:.2f} {HT + 13:.2f}" width="{(CIRC + 30) * M:.0f}" height="{(HT + 14) * M:.0f}">
<defs><clipPath id="cl"><rect x="0" y="0" width="{CIRC:.2f}" height="{HT:.2f}"/></clipPath></defs>
<rect x="0" y="0" width="{CIRC:.2f}" height="{HT:.2f}" class="sk"/>
<rect x="0" y="{Y(BODY0):.2f}" width="{CIRC:.2f}" height="{BODY0:.2f}" class="ko"/><rect x="0" y="0" width="{CIRC:.2f}" height="{Y(BODY1):.2f}" class="ko"/>
<rect x="0" y="{Y(SEAM) - 1.5:.2f}" width="{CIRC:.2f}" height="3" class="ko"/>
<line x1="0" y1="{Y(SEAM):.2f}" x2="{CIRC:.2f}" y2="{Y(SEAM):.2f}" class="seam"/>
<g clip-path="url(#cl)">{''.join(uses)}</g>
{''.join(dim(-3, Y(z), -1, Y(z), f'{z:g}', -4, Y(z) + 1.2) for z in sorted({st['z_mm'] for st in d['stamps']}))}
<text x="{CIRC + 2:.2f}" y="{Y(SEAM) + 1.2:.2f}" class="dt" text-anchor="start">seam {SEAM}</text>
<text x="{CIRC + 2:.2f}" y="{Y(BODY1) - 0.5:.2f}" class="dt" text-anchor="start">dome {BODY1:.1f}</text>
<text x="{CIRC + 2:.2f}" y="{Y(BODY0) + 1.5:.2f}" class="dt" text-anchor="start">dome {BODY0:.1f}</text>
<text x="{CIRC/2:.2f}" y="{HT + 5.5:.2f}" class="dt" text-anchor="middle">around: {CIRC:.2f} (Ø {2*R:g}) · up: height from seat</text>
</svg>'''
rows = ''.join(f'<tr><td>{i+1}</td><td>{st["row"]+1}</td><td>{st["z_mm"]:g}</td><td>{st["deg_around"]:g}°</td><td>{st["arc_mm"]:.2f}</td><td>{st["rot"]:+.1f}°</td></tr>' for i, st in enumerate(d['stamps']))
sw = ''.join(f'<div class="sw"><i style="background:{h}"></i><b>{n}</b><span>{a} · {h}</span></div>' for a, n, h in COLS)
html = f'''<!doctype html><html><head><meta charset="utf-8"><title>ZUMA capsule case · deboss spec</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;700;900&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<style>@page{{size:A4 landscape;margin:0}}body{{margin:0;font-family:Outfit,sans-serif;color:#2B1A1D;background:#fff}}
.pg{{width:297mm;height:210mm;box-sizing:border-box;padding:11mm 13mm;position:relative;page-break-after:always;overflow:hidden}}
h1{{font:900 24pt/1 Outfit;color:#6E1C2A;margin:0 0 2mm}} h2{{font:700 11pt Outfit;color:#6E1C2A;margin:0 0 2.5mm;text-transform:uppercase;letter-spacing:.06em}}
.sub{{font:500 10pt Outfit;color:#7A5A60;margin:0 0 7mm}} .mono,td,.dt{{font-family:'JetBrains Mono',monospace}}
.g{{display:grid;grid-template-columns:1.35fr 1fr;gap:10mm}} ul{{margin:0;padding-left:4.5mm;font-size:9.5pt;line-height:1.5}} li b{{color:#6E1C2A}}
.crest{{display:flex;gap:8mm;align-items:flex-end;margin:3mm 0 6mm}} .crest figure{{margin:0;text-align:center;font-size:8pt;color:#7A5A60}}
.crest svg{{display:block;margin:0 auto 2mm;color:#6E1C2A}}
.sk{{fill:#FBF5EC;stroke:#6E1C2A;stroke-width:.25}} .ko{{fill:#E9DCDF}} .seam{{stroke:#6E1C2A;stroke-width:.35;stroke-dasharray:1.2 .8}}
.dm{{stroke:#6E1C2A;stroke-width:.2}} .dt{{font-size:2.3px;fill:#6E1C2A}} .map{{width:100%;height:auto;display:block}}
table{{border-collapse:collapse;font-size:7.6pt;width:100%}} th{{text-align:left;font:700 7.6pt Outfit;color:#6E1C2A;border-bottom:.3mm solid #6E1C2A;padding:1mm 1.4mm}} td{{padding:.7mm 1.4mm;border-bottom:.1mm solid #E9DCDF}}
.sws{{display:grid;grid-template-columns:repeat(3,1fr);gap:3mm}} .sw{{display:grid;grid-template-columns:9mm 1fr;column-gap:2.5mm;align-items:center;font-size:8.5pt}} .sw i{{grid-row:span 2;width:9mm;height:9mm;border-radius:2mm}} .sw span{{font-family:'JetBrains Mono';font-size:7.5pt;color:#7A5A60}}
.ft{{position:absolute;left:13mm;right:13mm;bottom:7mm;display:flex;justify-content:space-between;font:500 7.5pt 'JetBrains Mono';color:#9A8288}}
.key{{display:flex;gap:6mm;font-size:8pt;color:#7A5A60;margin-top:2mm}} .key i{{display:inline-block;width:4mm;height:3mm;vertical-align:-.4mm;margin-right:1.5mm}}</style></head><body>
<svg width="0" height="0" style="position:absolute">{icon}</svg>
<section class="pg"><h1>Capsule case · deboss spec</h1><p class="sub">ZUMA Tides · silicone travel case for one 3 mL vial · Rev A · all dimensions in mm</p>
<div class="g"><div><h2>Stamp map, unrolled, drawn to scale</h2>{mapsvg}
<div class="key"><span><i style="background:#FBF5EC;border:.2mm solid #6E1C2A"></i>stamp zone</span><span><i style="background:#E9DCDF"></i>keep-out (domes, seam ±1.5)</span><span><i style="border-top:.35mm dashed #6E1C2A;height:0"></i>parting seam</span></div></div>
<div><h2>The stamp</h2><div class="crest">
<figure><svg viewBox="0 0 104.26 100" style="width:{CW}mm;height:{CH:.2f}mm"><use href="#zuma-icon" fill="currentColor"/></svg>true size<br>{CW} × {CH:.2f}</figure>
<figure><svg viewBox="0 0 104.26 100" style="width:{CW*5}mm;height:{CH*5:.2f}mm"><use href="#zuma-icon" fill="currentColor"/></svg>5× for reference</figure></div>
<ul><li><b>Artwork:</b> ZUMA crest, small-size cut (<span class="mono">zuma-crest-stamp.svg</span>, vector). Do not redraw or thicken.</li>
<li><b>Size:</b> {CW} mm across the petal tips, {CH:.2f} mm tall. Same size on every stamp.</li>
<li><b>Deboss depth:</b> 0.40 mm (±0.05), flat floor, 10° draft on the walls, 0.10 mm radius on the top edge.</li>
<li><b>Finish:</b> body matte (VDI 3400 Ref 27–30), stamp floor polished smoother so the crest reads by sheen as well as depth.</li>
<li><b>Count:</b> 20 stamps: 4 rows × 5, rows 2 and 4 turned 36° so the crests sit in a brick pattern.</li>
<li><b>Tilt:</b> each crest turned by the angle in the table (6° to 24°, either way). Keep the angles: they make the pattern look tossed, not printed.</li>
<li><b>Keep-outs:</b> nothing on the domes, nothing within 1.5 mm of the seam, nothing on the flat seat.</li></ul></div></div>
<div class="ft"><span>ZUMA · capsule case deboss spec · Rev A</span><span>Sample for approval before tooling</span><span>1 / 2</span></div></section>
<section class="pg"><div class="g"><div><h2>Capsule</h2><ul>
<li><b>Outside:</b> Ø {2*R:g} mm; {HT:.1f} mm tall standing ({L:g} mm tip to tip before the seat is cut).</li>
<li><b>Ends:</b> full hemispheres, R {R:g}. The bottom is cut flat to a seat Ø {d['seat_d']} mm so the case stands upright.</li>
<li><b>Halves:</b> two halves join at a fine parting seam {SEAM} mm above the seat; 0.3 mm wide, 0.3 mm deep groove.</li>
<li><b>Cavity:</b> fits one 3 mL vial with its crimp cap, snug, no rattle. Confirm against a physical vial.</li>
<li><b>Material:</b> silicone, Shore 40–50A, opaque, colour through the body.</li></ul>
<h2 style="margin-top:7mm">Colours, one per research area</h2><div class="sws">{sw}</div>
<p style="font-size:8.5pt;color:#7A5A60;margin-top:4mm">Match to the hex values. Send a moulded swatch of each colour for approval before the run.</p></div>
<div><h2>Stamp table</h2><table><tr><th>#</th><th>Row</th><th>Height (mm)</th><th>Around</th><th>Arc (mm)</th><th>Tilt</th></tr>{rows}</table>
<p style="font-size:7.5pt;color:#7A5A60;margin-top:2mm">Height is from the flat seat to the crest centre. Around is measured from a datum line along the body; arc is the same distance along the surface.</p></div></div>
<div class="ft"><span>ZUMA · capsule case deboss spec · Rev A</span><span>Sample for approval before tooling</span><span>2 / 2</span></div></section></body></html>'''
open(os.path.join(CAP, 'spec.html'), 'w').write(html); print('ok', len(uses))

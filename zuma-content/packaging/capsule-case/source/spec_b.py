# Capsule deboss spec, Rev B: one big crest on the front, the "zuma tides" wordmark up the back.
#   python3 cyc/capsule/spec_b.py -> spec-b.html (print to A4 landscape with spec.cjs)
import json, math, os
CAP = os.path.dirname(os.path.abspath(__file__)); SP = os.path.dirname(os.path.dirname(CAP))
R, L, T0 = 11.5, 64.0, 31.0; D0 = R - R * math.cos(math.radians(T0)); HT = L - D0; CIRC = 2 * math.pi * R
BODY0, BODY1 = R - D0, L - R - D0; SEAM = L / 2 - D0 / 2; TOP = (BODY1 + SEAM) / 2; SEAT = 2 * R * math.sin(math.radians(T0))
CW = 13.5; CH = CW * 100 / 104.26; LL = 36.0
t = json.load(open(os.path.join(SP, 'wm3', 'tides.json'))); K = LL / t['lock_w']; LH = (100 + t['asc']) * K; XH = 100 * K
GAPC = (t['zuma_w'] + t['lock_w'] - t['tides_w']) / 2
s = open(os.path.join(SP, 'site3/src/logo-slot.svg')).read(); a = s.index('<symbol id="zuma-mark"'); mark = s[a:s.index('</symbol>', a) + 9]
COLS = [('Dermal', 'Coral', '#FF6A55'), ('Endocrine', 'Lemon', '#F4D63A'), ('Tissue', 'Lime', '#6CC93A'), ('Metabolic', 'Sky', '#36B3E8'), ('Neuro', 'Lilac', '#A57BF0'), ('House', 'Oxblood', '#6E1C2A')]
def Y(z): return HT - z
a2 = s.index('<symbol id="zuma-icon"'); icon = s[a2:s.index('</symbol>', a2) + 9]
FW, FN = 4.0, 12; rows = []
for k in range(8):
    for zc in (SEAM - 2.9 - 5.5 * k, SEAM + 2.9 + 5.5 * k):
        if BODY0 + 1.8 < zc < BODY1 - 2.4: rows.append(zc)
rows.sort(); FIELD = []
for r, zc in enumerate(rows):
    for k in range(FN):
        u = (k + (0.5 if r % 2 else 0)) / FN
        du = min(abs(u - 0.5), 1 - abs(u - 0.5)) * CIRC; db = min(u, 1 - u) * CIRC
        if (du ** 2 + (zc - TOP) ** 2) ** .5 < CW / 2 + 2.6: continue
        if db < 5.9 / 2 + 2.6 and abs(zc - SEAM) < 36 / 2 + 2.0: continue
        FIELD.append((r, zc, u))
cx = CIRC / 2
lock = lambda x: f'<g transform="translate({x:.2f} {Y(SEAM):.2f}) rotate(-90) scale({K:.5f}) translate({-GAPC:.2f} -50)"><path fill="#6E1C2A" fill-rule="evenodd" d="{t["lock"]}"/></g>'
mapsvg = f'''<svg class="map" viewBox="-12 -4 {CIRC + 30:.2f} {HT + 13:.2f}">
<defs><clipPath id="cl"><rect x="0" y="0" width="{CIRC:.2f}" height="{HT:.2f}"/></clipPath></defs>
<rect x="0" y="0" width="{CIRC:.2f}" height="{HT:.2f}" class="sk"/>
<rect x="0" y="{Y(BODY0):.2f}" width="{CIRC:.2f}" height="{BODY0:.2f}" class="ko"/><rect x="0" y="0" width="{CIRC:.2f}" height="{Y(BODY1):.2f}" class="ko"/>
<line x1="0" y1="{Y(SEAM):.2f}" x2="{CIRC:.2f}" y2="{Y(SEAM):.2f}" class="seam"/>
<g clip-path="url(#cl)">{''.join(f'<use href="#zuma-icon" x="{u_ * CIRC - FW / 2 + dx:.2f}" y="{Y(z_) - FW * .48:.2f}" width="{FW}" height="{FW * .96:.2f}" style="color:#C7A3A9"/>' for r_, z_, u_ in FIELD for dx in (-CIRC, 0, CIRC))}<use href="#zuma-mark" x="{cx - CW/2:.2f}" y="{Y(TOP) - CH/2:.2f}" width="{CW}" height="{CH:.2f}" fill="#6E1C2A"/>{lock(0)}{lock(CIRC)}</g>
<line x1="{cx:.2f}" x2="{cx:.2f}" y1="-2" y2="{HT + 1:.2f}" class="ax"/><line x1="0" x2="0" y1="-2" y2="{HT + 1:.2f}" class="ax"/><line x1="{CIRC:.2f}" x2="{CIRC:.2f}" y1="-2" y2="{HT + 1:.2f}" class="ax"/>
<text x="{cx:.2f}" y="-1.2" class="dt" text-anchor="middle">FRONT 180°</text><text x="0" y="-1.2" class="dt" text-anchor="middle">BACK 0°</text><text x="{CIRC:.2f}" y="-1.2" class="dt" text-anchor="middle">360°</text>
<line x1="-3" x2="-1" y1="{Y(TOP):.2f}" y2="{Y(TOP):.2f}" class="dm"/><text x="-4" y="{Y(TOP) + .8:.2f}" class="dt" text-anchor="end">{TOP:.1f}</text>
<text x="{CIRC + 2:.2f}" y="{Y(SEAM) + .8:.2f}" class="dt">seam {SEAM:.1f}</text>
<text x="{CIRC + 2:.2f}" y="{Y(BODY1) - .5:.2f}" class="dt">dome {BODY1:.1f}</text><text x="{CIRC + 2:.2f}" y="{Y(BODY0) + 1.5:.2f}" class="dt">dome {BODY0:.1f}</text>
<text x="{CIRC/2:.2f}" y="{HT + 5.5:.2f}" class="dt" text-anchor="middle">around: {CIRC:.2f} (Ø {2*R:g}) · up: height from seat</text></svg>'''
sw = ''.join(f'<div class="sw"><i style="background:{h}"></i><b>{n}</b><span>{a_} · {h}</span></div>' for a_, n, h in COLS)
html = f'''<!doctype html><html><head><meta charset="utf-8"><title>ZUMA capsule case · deboss spec Rev B</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;700;900&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<style>@page{{size:A4 landscape;margin:0}}body{{margin:0;font-family:Outfit,sans-serif;color:#2B1A1D;background:#fff}}
.pg{{width:297mm;height:210mm;box-sizing:border-box;padding:11mm 13mm;position:relative;page-break-after:always;overflow:hidden}}
h1{{font:900 24pt/1 Outfit;color:#6E1C2A;margin:0 0 2mm}} h2{{font:700 11pt Outfit;color:#6E1C2A;margin:0 0 2.5mm;text-transform:uppercase;letter-spacing:.06em}}
.sub{{font:500 10pt Outfit;color:#7A5A60;margin:0 0 6mm}} .mono,.dt{{font-family:'JetBrains Mono',monospace}}
.g{{display:grid;grid-template-columns:1.3fr 1fr;gap:10mm}} ul{{margin:0;padding-left:4.5mm;font-size:9.3pt;line-height:1.48}} li b{{color:#6E1C2A}}
.art{{display:flex;gap:7mm;align-items:flex-end;margin:2mm 0 5mm}} .art figure{{margin:0;text-align:center;font-size:7.5pt;color:#7A5A60}} .art svg{{display:block;margin:0 auto 1.5mm}}
.sk{{fill:#FBF5EC;stroke:#6E1C2A;stroke-width:.25}} .ko{{fill:#E9DCDF}} .seam{{stroke:#6E1C2A;stroke-width:.35;stroke-dasharray:1.2 .8}} .ax{{stroke:#6E1C2A;stroke-width:.12;stroke-dasharray:.6 .6}}
.dm{{stroke:#6E1C2A;stroke-width:.2}} .dt{{font-size:2.3px;fill:#6E1C2A}} .map{{width:100%;height:auto;display:block}}
.sws{{display:grid;grid-template-columns:repeat(3,1fr);gap:3mm}} .sw{{display:grid;grid-template-columns:9mm 1fr;column-gap:2.5mm;align-items:center;font-size:8.5pt}} .sw i{{grid-row:span 2;width:9mm;height:9mm;border-radius:2mm}} .sw span{{font-family:'JetBrains Mono';font-size:7.5pt;color:#7A5A60}}
.ft{{position:absolute;left:13mm;right:13mm;bottom:7mm;display:flex;justify-content:space-between;font:500 7.5pt 'JetBrains Mono';color:#9A8288}}
.key{{display:flex;gap:6mm;font-size:8pt;color:#7A5A60;margin-top:2mm}} .key i{{display:inline-block;width:4mm;height:3mm;vertical-align:-.4mm;margin-right:1.5mm}}</style></head><body>
<svg width="0" height="0" style="position:absolute">{mark}{icon}</svg>
<section class="pg"><h1>Capsule case · deboss spec</h1><p class="sub">ZUMA Tides · silicone travel case for one 3 mL vial · Rev B · all dimensions in mm · replaces Rev A</p>
<div class="g"><div><h2>Stamp map, unrolled, drawn to scale</h2>{mapsvg}
<div class="key"><span><i style="background:#FBF5EC;border:.2mm solid #6E1C2A"></i>stamp zone</span><span><i style="background:#E9DCDF"></i>keep-out (domes)</span><span><i style="background:#C7A3A9"></i>monogram (shallow)</span><span><i style="border-top:.35mm dashed #6E1C2A;height:0"></i>parting seam</span></div></div>
<div><h2>Two deep stamps on a shallow monogram</h2><div class="art">
<figure><svg viewBox="0 0 104.26 100" style="width:{CW}mm;height:{CH:.2f}mm"><use href="#zuma-mark" fill="#6E1C2A"/></svg>crest, true size<br>{CW} × {CH:.1f}</figure>
<figure><svg viewBox="0 {-t['asc']} {t['lock_w']:.1f} {100 + t['asc']}" style="width:{LL}mm;height:{LH:.2f}mm"><path fill="#6E1C2A" fill-rule="evenodd" d="{t['lock']}"/></svg>wordmark, true size<br>{LL:g} × {LH:.1f} (x-height {XH:.2f})</figure>
<figure><svg viewBox="0 0 104.26 100" style="width:{FW}mm;height:{FW*.96:.2f}mm;color:#C7A3A9"><use href="#zuma-icon" fill="currentColor"/></svg>monogram<br>{FW:g} mm</figure></div>
<ul><li><b>Front (180°):</b> the ZUMA crest, {CW} mm wide, centred on the top half at {TOP:.1f} mm above the seat. Upright.</li>
<li><b>Back (0°):</b> the "zuma tides" wordmark, {LL:g} mm long, reading up from the seat. The parting seam falls in the space between the two words: no letter crosses it.</li>
<li><b>Monogram:</b> {len(FIELD)} small crests ({FW:g} mm, small-size cut), {FN} to a row, rows {5.5:g} mm apart and turned half a step on alternate rows. Pressed shallow, 0.12 mm, so they read tone on tone. A clear margin of 2.6 mm around both deep stamps.</li>
<li><b>Artwork:</b> vector files <span class="mono">zuma-crest-13_5mm.svg</span>, <span class="mono">zuma-tides-wordmark.svg</span> and <span class="mono">zuma-monogram-4mm.svg</span>. Do not redraw, thicken or swap the lettering for a font.</li>
<li><b>Deboss:</b> crest and wordmark 0.40 mm deep (±0.05), flat floor, 10° draft, 0.10 mm radius on the top edge. Smallest feature in the crest is about 0.3 mm: hold it; if the tool cannot, tell us before cutting.</li>
<li><b>Finish:</b> body matte (VDI 3400 Ref 27–30); stamp floors polished smoother so the marks read by sheen as well as depth.</li>
<li><b>Keep-outs:</b> nothing on the domes or the flat seat.</li></ul></div></div>
<div class="ft"><span>ZUMA · capsule case deboss spec · Rev B</span><span>Sample for approval before tooling</span><span>1 / 2</span></div></section>
<section class="pg"><div class="g"><div><h2>Capsule</h2><ul>
<li><b>Outside:</b> Ø {2*R:g} mm; {HT:.1f} mm tall standing ({L:g} mm tip to tip before the seat is cut).</li>
<li><b>Ends:</b> full hemispheres, R {R:g}. The bottom is cut flat to a seat Ø {SEAT:.1f} mm so the case stands upright.</li>
<li><b>Halves:</b> two halves join at a fine parting seam {SEAM:.1f} mm above the seat; 0.3 mm wide, 0.3 mm deep groove.</li>
<li><b>Cavity:</b> fits one 3 mL vial with its crimp cap, snug, no rattle. Confirm against a physical vial.</li>
<li><b>Wall:</b> 3.0 mm minimum all round, ends included. The case ships in a padded mailer with no box, so it is the vial's only crush and drop protection: it must survive a 1.2 m drop onto concrete and a 20 kg load across the body with the vial unbroken.</li>
<li><b>Closure:</b> the two halves press-fit on an internal lip and stay shut through the drop test; supplier to design and prove it on the sample.</li>
<li><b>Material:</b> silicone, Shore 40–50A, opaque, colour through the body.</li></ul>
<h2 style="margin-top:7mm">Colours, one per research area</h2><div class="sws">{sw}</div>
<p style="font-size:8.5pt;color:#7A5A60;margin-top:4mm">Match to the hex values. Send a moulded swatch of each colour for approval before the run.</p></div>
<div><h2>Stamp positions</h2><ul>
<li><b>Crest:</b> centre {TOP:.1f} mm above the seat, at 180° (the front). Width {CW} mm. Upright.</li>
<li><b>Wordmark:</b> centre of the word space on the seam ({SEAM:.1f} mm above the seat), at 0° (the back). {LL:g} mm long, runs from {SEAM - LL * (GAPC / t['lock_w']):.1f} to {SEAM + LL * (1 - GAPC / t['lock_w']):.1f} mm. Reads bottom to top; the tops of the letters face the left as you look at the back.</li>
<li><b>Monogram rows</b> (height above the seat): {', '.join(f'{z_:.1f}' for z_ in rows)}. Odd rows start at 0°, even rows at {360 / FN / 2:g}°; pitch {360 / FN:g}° ({CIRC / FN:.2f} mm). Positions inside the margins are left out.</li>
<li><b>Datum:</b> 0° is the centre line of the back; the front is opposite at 180°.</li></ul></div></div>
<div class="ft"><span>ZUMA · capsule case deboss spec · Rev B</span><span>Sample for approval before tooling</span><span>2 / 2</span></div></section></body></html>'''
open(os.path.join(CAP, 'spec-b.html'), 'w').write(html); print('ok', round(LH, 2), round(XH, 2))

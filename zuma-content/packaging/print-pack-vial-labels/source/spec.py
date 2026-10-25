# The vial label print spec and order sheet (Option C wrap label).  python3 spec.py -> label-spec.html (print with ../capsule/spec.cjs)
import os, base64
D = os.path.dirname(os.path.abspath(__file__))
SKUS = [('01','RT-3','Retatrutide','10 mg','Metabolic','#36B3E8'),('02','TZ-2','Tirzepatide','15 mg','Metabolic','#36B3E8'),('04','Tesamorelin','Tesamorelin','10 mg','Endocrine','#F4D63A'),
 ('05','GHK-Cu','Copper peptide GHK-Cu','50 mg','Dermal','#FF6A55'),('06','MOTS-c','MOTS-c','10 mg','Metabolic','#36B3E8'),('07','CJC+IPA','CJC-1295 + Ipamorelin','10 mg','Endocrine','#F4D63A'),
 ('08','NAD+','NAD+','500 mg','Metabolic','#36B3E8'),('09','BPC+TB','BPC-157 + TB-500','10 mg','Tissue','#6CC93A'),('10','GHK+BT','GHK-Cu + BPC + TB','70 mg','Dermal','#FF6A55'),
 ('11','Selank','Selank','10 mg','Neuro','#A57BF0'),('12','Semax','Semax','10 mg','Neuro','#A57BF0')]
CODE = {'01':'RT3','02':'TZ2','04':'TES','05':'GHK','06':'MOT','07':'CJI','08':'NAD','09':'BPT','10':'GBT','11':'SEL','12':'SMX'}
img = lambda f: 'data:image/jpeg;base64,' + base64.b64encode(open(os.path.join(D, f), 'rb').read()).decode()
rows = ''.join(f'<tr><td>{n}</td><td><b>{p}</b></td><td>{f}</td><td>{fl}</td><td><i style="background:{h}"></i>{a}</td><td class="m">zuma-label-{n}-print.pdf</td><td class="m">lots#{CODE[n]}-</td></tr>' for n, p, f, fl, a, h in SKUS)
proofs = ''.join(f'<figure><img src="{img(f"zuma-label-{n}-proof.jpg")}"><figcaption>{n} · {p} · {fl}</figcaption></figure>' for n, p, f, fl, a, h in SKUS)
html = f'''<!doctype html><html><head><meta charset="utf-8"><title>ZUMA vial label · print spec</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;700;900&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<style>@page{{size:A4 landscape;margin:0}}body{{margin:0;font-family:Outfit,sans-serif;color:#2B1A1D}}
.pg{{width:297mm;height:210mm;box-sizing:border-box;padding:11mm 13mm;position:relative;page-break-after:always;overflow:hidden}}
h1{{font:900 23pt/1 Outfit;color:#6E1C2A;margin:0 0 2mm}} h2{{font:700 10.5pt Outfit;color:#6E1C2A;margin:0 0 2.5mm;text-transform:uppercase;letter-spacing:.06em}}
.sub{{font:500 10pt Outfit;color:#7A5A60;margin:0 0 6mm}} .m{{font-family:'JetBrains Mono',monospace;font-size:7.6pt}}
.g{{display:grid;grid-template-columns:1fr 1fr;gap:10mm}} table{{border-collapse:collapse;width:100%;font-size:8.6pt}}
th{{text-align:left;font:700 8pt Outfit;color:#6E1C2A;border-bottom:.3mm solid #6E1C2A;padding:1.2mm 1.5mm;vertical-align:bottom}} td{{padding:1.1mm 1.5mm;border-bottom:.1mm solid #E9DCDF;vertical-align:top;white-space:nowrap}} .kv td{{white-space:normal}}
.kv td:first-child{{font-weight:700;color:#6E1C2A;width:30mm}} td i{{display:inline-block;width:3mm;height:3mm;border-radius:.6mm;margin-right:1.5mm;vertical-align:-.4mm}}
.dia{{margin:2mm 0 5mm}} .ft{{position:absolute;left:13mm;right:13mm;bottom:7mm;display:flex;justify-content:space-between;font:500 7.5pt 'JetBrains Mono';color:#9A8288}}
.proofs{{display:grid;grid-template-columns:repeat(4,1fr);gap:5mm 4mm}} figure{{margin:0}} figure img{{width:100%;display:block;border-radius:1mm}} figcaption{{font:600 7.5pt Outfit;color:#6E1C2A;margin-top:1mm}}
.note{{font-size:8.3pt;color:#7A5A60;line-height:1.45}} ul{{margin:0;padding-left:4.5mm;font-size:9pt;line-height:1.5}} li b{{color:#6E1C2A}}</style></head><body>
<section class="pg"><h1>Vial label · print spec</h1><p class="sub">ZUMA Tides · wrap label for the 3 mL vial (Option C: plain clear vial, Oxblood cap) · eleven SKUs · Rev 1 · 25 Oct 2026</p>
<div class="g"><div><h2>The label</h2><table class="kv">
<tr><td>Size</td><td>43.0 × 20.0 mm trim, corners rounded 1.0 mm. Wraps a Ø 16 mm vial with a 7 mm gap at the back.</td></tr>
<tr><td>Bleed</td><td>1.5 mm all round. Each print file is a 46 × 23 mm page with the bleed built in; no crop marks.</td></tr>
<tr><td>Safe area</td><td>1.0 mm inside the trim. Nothing that matters sits outside it.</td></tr>
<tr><td>Material</td><td>White polypropylene film (BOPP), permanent acrylic adhesive rated for −20 °C storage, matte laminate. Must hold through freezer storage, condensation and an alcohol wipe.</td></tr>
<tr><td>Print</td><td>Digital CMYK, full bleed, one design per SKU. No white ink, no spot colours.</td></tr>
<tr><td>Colour</td><td>Match the hex values below. Oxblood #6E1C2A is the brand colour on every label: hard proof it before the run.</td></tr>
<tr><td>Lot box</td><td>The white box top-left (LOT / FILLED, 11.3 × 3.4 mm) stays blank for the lot number and fill date: inkjet or thermal transfer at filling. If thermal transfer, order the laminate as TT-receptive.</td></tr>
<tr><td>QR code</td><td>9.6 mm, links to that product's lot reports (zumatides.com/lots#CODE-). Scan the proof before approving.</td></tr>
<tr><td>Supply</td><td>Rolls for an applicator (76 mm core, one across, 3 mm gap; confirm unwind direction with the applicator) or sheets for hand labelling. Order vials + 10% per SKU for set-up and spoilage.</td></tr>
</table></div>
<div><h2>On the vial</h2>
<svg class="dia" viewBox="0 0 120 70" style="width:100%"><g fill="none" stroke="#6E1C2A" stroke-width=".35">
<rect x="18" y="16" width="16" height="46" rx="1.5"/><rect x="21" y="8" width="10" height="8" fill="#6E1C2A"/><rect x="20" y="13" width="12" height="4" fill="#C9C2BE" stroke="none"/>
<rect x="18" y="39" width="16" height="20" fill="#FF6A55" fill-opacity=".35"/>
<line x1="38" x2="38" y1="39" y2="59"/><line x1="36" x2="40" y1="39" y2="39"/><line x1="36" x2="40" y1="59" y2="59"/>
<line x1="38" x2="38" y1="59" y2="62"/><line x1="36" x2="40" y1="62" y2="62"/>
<rect x="56" y="34" width="43" height="20" rx="1" fill="#FF6A55" fill-opacity=".35"/><line x1="56" x2="99" y1="58" y2="58"/><line x1="56" x2="56" y1="56" y2="60"/><line x1="99" x2="99" y1="56" y2="60"/>
<line x1="103" x2="103" y1="34" y2="54"/><line x1="101" x2="105" y1="34" y2="34"/><line x1="101" x2="105" y1="54" y2="54"/><line x1="77.5" x2="77.5" y1="31" y2="57" stroke-dasharray="1 1"/></g>
<g font-family="JetBrains Mono" font-size="2.6" fill="#6E1C2A"><text x="41" y="50">20.0</text><text x="41" y="61.6">3.0</text><text x="12" y="66">Ø 16 · 35 mm with cap</text>
<text x="72" y="62">43.0 mm</text><text x="106" y="45">20.0</text><text x="70.5" y="30">front centre</text><text x="56" y="22" font-family="Outfit" font-weight="700" font-size="3">Label flat, trim line</text></g></svg>
<ul><li><b>Placement:</b> bottom edge 3.0 mm above the base of the vial; the ZUMA logo and product name centred on the front; the gap at the back.</li>
<li><b>Cap:</b> 13 mm flip-off, Oxblood #6E1C2A, on every SKU; silver aluminium crimp; grey butyl lyophilization stopper.</li>
<li><b>Vial:</b> 3 mL clear borosilicate, Ø 16 mm, 35 mm tall with the cap, 13 mm crimp neck.</li></ul>
<h2 style="margin-top:6mm">Colours</h2><p class="note">Oxblood #6E1C2A · Coral #FF6A55 (Dermal) · Lemon #F4D63A (Endocrine) · Lime #6CC93A (Tissue) · Sky #36B3E8 (Metabolic) · Lilac #A57BF0 (Neuro). Each label also uses the light tint of its colour for the top band; the files carry the exact values.</p></div></div>
<div class="ft"><span>ZUMA · vial label print spec · Rev 1</span><span>Hard proof before the run</span><span>1 / 3</span></div></section>
<section class="pg"><h2>The eleven labels · proofs</h2><p class="note" style="margin:0 0 4mm">Blue: trim. Pink: safe area. Outside the blue line is bleed. The proofs carry the lines; the print files do not.</p>
<div class="proofs">{proofs}</div><div class="ft"><span>ZUMA · vial label print spec · Rev 1</span><span>Hard proof before the run</span><span>2 / 3</span></div></section>
<section class="pg"><div class="g" style="grid-template-columns:1.75fr 1fr"><div><h2>Files and SKUs</h2><table><tr><th>No.</th><th>Label</th><th>Compound</th><th>Fill</th><th>Area</th><th>Print file</th><th>QR</th></tr>{rows}</table>
<p class="note" style="margin-top:3mm">Also in the pack: zuma-label-NN-art.png (the same art, 3080 × 1540 px, 1702 dpi) and zuma-label-NN-proof.jpg.</p></div>
<div><h2>To confirm before ordering</h2><ul>
<li><b>Lot coding:</b> who prints the lot and fill date in the box, and how (inkjet or thermal transfer).</li>
<li><b>NAD+ 500 mg:</b> confirm the fill fits the 3 mL vial; if it moves to a larger vial it needs its own label size.</li>
<li><b>Bacteriostatic water:</b> sold in a 10 mL vial, so not in this pack. Send its vial size and it gets its own label.</li>
<li><b>Quantities</b> per SKU, and rolls or sheets.</li></ul>
<h2 style="margin-top:6mm">Research use</h2><p class="note">Every label carries: For laboratory research use only. Not for human or veterinary use. Keep it on every reprint.</p></div></div>
<div class="ft"><span>ZUMA · vial label print spec · Rev 1</span><span>Hard proof before the run</span><span>3 / 3</span></div></section></body></html>'''
open(os.path.join(D, 'label-spec.html'), 'w').write(html); print('ok')

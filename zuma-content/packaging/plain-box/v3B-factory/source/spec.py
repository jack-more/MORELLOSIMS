# Plain carton v3 B production spec (bilingual EN / 简体中文), A4 landscape, printed to PDF by spec.cjs
import os, json, base64
PK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = json.load(open(PK + '/versions.json'))
def b64(f): return 'data:image/png;base64,' + base64.b64encode(open(PK + '/preview/' + f, 'rb').read()).decode()
def pg(title, body):
    return (f'<section class="pg"><header><div class="k">ZUMA · PLAIN CARTON v3 B 无窗彩盒 · PRODUCTION SPEC 生产规格书 · REV 1 (FOR QUOTE 报价)</div><h2>{title}</h2></header>{body}'
            '<footer>Chinese terms for reference; confirm with supplier. 中文术语仅供参考，请与供应商确认。 · zumatides.com</footer></section>')
TOT = sum(v.get('qty', 0) for v in V)
rows = ''.join(f'<tr><td>{i+1}</td><td><b>{v["name"]}</b></td><td>{v["dose"]}</td><td>{v["full"]}</td><td><span class="chip" style="background:{v["hex"]}"></span>{v["area"]}</td><td><b>{v.get("qty", "")}</b></td><td class="m">{v["file"]}</td></tr>' for i, v in enumerate(V))
P = [
pg('What it is 产品概述', f'''<div class="two"><img src="{b64('look-B.png')}" style="width:100%">
<div><p class="big">A small white tuck-top carton with an auto-lock bottom, ONE sheet of 400 gsm board. <b>No window.</b> The outside is printed: a grid of flat panels in tonal steps of the product's area colour, the crest reversed out in white, the product name, and an Oxblood band round the bottom with the ZUMA wordmark. The inside is flooded in the area colour.</p>
<p class="zh">白色小插舌盒，自动锁底，单张400g白卡。<b>无开窗。</b>外面印刷：区域色的深浅色块格纹、白色反白花徽、品名，底部一圈酒红色带配ZUMA字标。内面满版区域色。</p>
<table><tr><td>Size 尺寸</td><td>inside 内尺寸 20 × 20 × 40 mm</td></tr>
<tr><td>Board 纸</td><td>400 gsm SBS white 白卡纸</td></tr>
<tr><td>Structure 结构</td><td>tuck top, 10 mm tongue, 1 mm friction-lock nicks 插舌顶+防松卡口; auto-lock bottom, pre-glued 自动锁底预糊. Same die as our window carton Rev F, without the window 与开窗盒Rev F同刀模（无窗）</td></tr>
<tr><td>Outside 外面</td><td>CMYK 4-colour + Oxblood #6E1C2A (spot or matched CMYK), matte aqueous or soft-touch film 哑光水油或触感膜</td></tr>
<tr><td>Top flap 顶盖</td><td>area colour flood + crest 9 mm Oxblood matte hot foil + deboss, one hit 区域色满版+9mm花徽酒红哑光烫金压凹一次成型</td></tr>
<tr><td>Inside 内面</td><td>100% flood, area colour (6 PMS) 内面满版区域专色</td></tr>
<tr><td>Versions 版本</td><td>12 outside versions (one per product) on ONE die; 6 inside colours 外面12版（每品一版），内面6色</td></tr></table></div></div>'''),
pg('Panels 展开图 (example RT-3 10 mg)', f'''<img src="{b64('plainB-art-rt-3-10-mg.png')}" style="height:150mm;display:block;margin:0 auto">
<p class="cap">Outside print, 1:1 file 外面印刷1:1文件: svg/plainB-art-*.svg. Layers 图层: PRINT_CMYK, HOT_FOIL, DEBOSS, CUT, CREASE, NOTES (do not print 不印). All type is outlined 文字已转曲. Bleed 1 mm past every outside cut 外切线出血1mm. The top-flap art is rotated 180° so it reads upright from the front when closed 顶盖图案旋转180°，合盖后从正面看为正向.</p>'''),
pg('Band and wordmark 色带与字标', f'''<div class="two"><img src="{b64('flat-B.png')}" style="width:100%">
<div><p class="big">The Oxblood band is 6 mm tall and wraps all four sides and the glue flap, bleeding 1 mm past the bottom crease. Front: ZUMA wordmark in white (Snow #FCFBF8), <b>13 mm wide × 3.1 mm tall</b>, centred, top at 0.75 mm inside the band; under it "FOR LABORATORY RESEARCH USE ONLY".</p>
<p class="zh">酒红色带高6mm，环绕四个面及糊口，出血至底部压痕外1mm。正面：白色ZUMA字标，<b>宽13mm × 高3.1mm</b>，居中；下方"FOR LABORATORY RESEARCH USE ONLY"。</p>
<p class="big">Colours 颜色: Oxblood #6E1C2A · Snow #FCFBF8 · area colours: Metabolic #1F4FD0 (PMS 2728 C), Tissue #0E9A58 (PMS 340 C), Dermal #FF5A1F (PMS Orange 021 C), Endocrine #D08000 (PMS 1385 C), Neuro #6E3FD8 (PMS 2665 C), Lab supplies #4E6077 (PMS 7545 C). Panel tints are printed as CMYK screens of the area colour 色块深浅为区域色CMYK网点.</p></div></div>'''),
pg('Dieline 刀模 + inside 内面', f'''<div class="two"><div><img src="{b64('plainB-dieline-master.png')}" style="width:100%"><p class="cap">Master dieline 刀模: svg/plainB-dieline-master.svg (CUT, CREASE, NOTES). Auto-lock drawn schematically: use your standard crash-lock die for a 20 × 20 base 锁底为示意，请用标准扣底刀模.</p></div>
<div><img src="{b64('plainB-inside-metabolic.png')}" style="width:100%"><p class="cap">Inside 内面 (mirrored 镜像), example Metabolic: svg/plainB-inside-*.svg, 6 colours. 100% flood, bleed past every cut 满版出血. Knock out on glue areas if your glue needs it 如需要糊盒位留白.</p></div></div>'''),
pg('Versions 版本清单 (12)', f'''<table class="v"><tr><th>#</th><th>Name 品名</th><th>Size 规格</th><th>Full name 全称</th><th>Area / inside colour 区域/内面色</th><th>Qty 数量</th><th>Outside file 外面文件</th></tr>{rows}<tr><td></td><td><b>TOTAL 合计</b></td><td></td><td></td><td></td><td><b>{TOT}</b></td><td>one run, versions mixed 一次生产混单</td></tr></table>
<p class="big" style="margin-top:6mm">All versions share ONE die, ONE foil/deboss plate and the same back panel (QR → https://zumatides.com/lots). Only the outside print and the inside colour change. 所有版本共用一套刀模、一块烫金压凹版、相同背面（二维码）。只有外面印刷和内面颜色不同。</p>'''),
]
CSS = '''@page{size:297mm 210mm;margin:0}*{box-sizing:border-box}body{margin:0;font-family:Helvetica,Arial,"WenQuanYi Zen Hei Mono",sans-serif;color:#1a1012}
.pg{width:297mm;height:210mm;padding:12mm 14mm;position:relative;page-break-after:always;overflow:hidden;background:#fff}
.k{font:600 8pt monospace;letter-spacing:.08em;color:#6E1C2A}h2{font-size:20pt;margin:2mm 0 5mm}
.two{display:grid;grid-template-columns:1.25fr 1fr;gap:8mm;align-items:start}.big{font-size:10.5pt;line-height:1.45;margin:0 0 3mm}.zh{font-size:9.5pt;color:#444;margin:0 0 4mm}
table{border-collapse:collapse;width:100%;font-size:8.6pt}td,th{border-top:.2mm solid #ccc;padding:1.6mm 2mm;text-align:left;vertical-align:top}
.v td,.v th{font-size:9.5pt}.m{font-family:monospace;font-size:8pt}.chip{display:inline-block;width:4mm;height:4mm;vertical-align:-0.8mm;margin-right:2mm;border:.2mm solid #333}
.cap{font-size:9pt;color:#333;line-height:1.4}footer{position:absolute;bottom:6mm;left:14mm;right:14mm;font-size:7pt;color:#888}'''
open(PK + '/spec.html', 'w').write(f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{"".join(P)}</body></html>')
print('spec pages', len(P))

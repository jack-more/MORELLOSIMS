import re, json, random, base64, io
from PIL import Image
S = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'
OX = '#6E1C2A'; SN = '#FCFBF8'; ST = '#EFE4D2'
G = json.load(open(S + '/window/geom.json'))
AREAS = [(a['name'], a['hex'], a.get('skus', '')) for a in G['areas']]
LABEL = {'Metabolic': '01', 'Tissue': '09', 'Dermal': '05', 'Endocrine': '04', 'Neuro': '11', 'Lab supplies': '01'}

def inner(p):
    s = open(p).read(); s = re.sub(r'<\?xml[^>]*>', '', s); s = re.sub(r'<svg[^>]*>', '', s); s = s.replace('</svg>', '')
    return re.sub(r'fill="#[0-9A-Fa-f]{3,6}"', 'fill="currentColor"', s)
CREST = inner('/home/user/MORELLOSIMS/zuma-content/packaging/capsule-case/zuma-crest-stamp.svg')
WM = inner('/home/user/MORELLOSIMS/zuma-content/brand/wordmark/zuma-tides-wordmark.svg')

def mix(h, t, k):
    a = [int(h[i:i + 2], 16) for i in (1, 3, 5)]; b = [int(t[i:i + 2], 16) for i in (1, 3, 5)]
    return '#%02X%02X%02X' % tuple(round(x + (y - x) * k) for x, y in zip(a, b))

# ---- geometry (mm, front panel 20 x 40, origin bottom-left, from the v1 dieline / loved hero) ----
PW, PH = 20.0, 40.0
PANELS = [  # id, x0, y0, x1, y1
    ('P1', 5.0, 7.5, 15.0, 29.5),    # tall centre (holds the window)
    ('P2', 5.0, 31.5, 15.0, 36.0),   # wide top
    ('P3', 1.5, 18.5, 3.5, 36.0),    # left strip
    ('P4', 16.5, 12.5, 18.5, 29.5),  # right strip
    ('P5', 16.5, 31.5, 18.5, 36.0),  # right top
    ('P6', 5.0, 3.3, 11.5, 5.5),     # bottom small
]
# the one real window: centred on the label's crest + "zuma" lockup
# label art 3080x1540 px = 46 x 23 mm incl. 1.5 mm bleed -> 66.96 px/mm. Lockup px x1096-1982, y174-403
# -> on the 43 x 20 label: x 14.9-28.1 (centre 21.5 = label front centre), y 1.1-4.5 mm from label top.
# label band on the vial (geom.json) y 2.6-22.6 from floor -> lockup y 18.1-21.5. Projected width on the
# 16 mm vial ~11.8 mm. Window 9 x 5 inside the 10 mm centre panel frames the crest and "zum"; the vial rotates
# freely so the exact crop varies.
WIN = (7.0, 17.5, 13.0, 23.5)
CREST_X = 16.7  # crest centre on the flat label (mm from label left edge); vial goes in crest-forward
LAB_TOP = 22.6; PXMM = 3080 / 46.0; BLEED = 1.5

def label_crop_b64(code, w_mm, h_mm, y_top_from_label_top):
    im = Image.open(f'{S}/cyc/printpack/zuma-label-{code}-art.png').convert('RGB')
    cx = (CREST_X + BLEED) * PXMM
    x0 = cx - w_mm / 2 * PXMM; x1 = cx + w_mm / 2 * PXMM
    y0 = (y_top_from_label_top + BLEED) * PXMM; y1 = y0 + h_mm * PXMM
    c = im.crop((int(x0), int(y0), int(x1), int(y1)))
    b = io.BytesIO(); c.save(b, 'PNG'); return base64.b64encode(b.getvalue()).decode()

def defs(uid, col):
    hi = mix(col, '#FFFFFF', .35); lo = mix(col, '#000000', .35)
    return f'''<defs>
<symbol id="crest{uid}" viewBox="0 0 104.26 100">{CREST}</symbol>
<symbol id="wm{uid}" viewBox="0 -38 848 138">{WM}</symbol>
<pattern id="ribs{uid}" width="1" height="0.6" patternUnits="userSpaceOnUse">
 <rect width="1" height="0.6" fill="{col}"/><rect y="0" width="1" height="0.14" fill="{hi}" opacity=".85"/>
 <rect y="0.38" width="1" height="0.16" fill="{lo}" opacity=".55"/></pattern>
<pattern id="linen{uid}" width="0.36" height="0.36" patternUnits="userSpaceOnUse">
 <rect width="0.36" height="0.36" fill="{col}"/>
 <rect x="0" y="0.02" width="0.17" height="0.06" fill="{hi}" opacity=".35"/><rect x="0.18" y="0.2" width="0.17" height="0.06" fill="{hi}" opacity=".35"/>
 <rect x="0.02" y="0.18" width="0.06" height="0.17" fill="{lo}" opacity=".22"/><rect x="0.2" y="0" width="0.06" height="0.17" fill="{lo}" opacity=".22"/></pattern>
<linearGradient id="gloss{uid}" x1="0" y1="0" x2="1" y2="1">
 <stop offset="0" stop-color="#fff" stop-opacity=".05"/><stop offset=".38" stop-color="#fff" stop-opacity=".05"/>
 <stop offset=".47" stop-color="#fff" stop-opacity=".55"/><stop offset=".53" stop-color="#fff" stop-opacity=".12"/>
 <stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<radialGradient id="cave{uid}" cx=".5" cy=".55" r=".75"><stop offset="0" stop-color="{mix(col, '#000000', .25)}"/><stop offset="1" stop-color="{mix(col, '#000000', .7)}"/></radialGradient>
<filter id="soft{uid}" x="-5%" y="-5%" width="110%" height="110%"><feTurbulence type="fractalNoise" baseFrequency="2.2" numOctaves="2" seed="4"/>
 <feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .06 0"/><feComposite in2="SourceGraphic" operator="in"/><feBlend in="SourceGraphic" mode="multiply"/></filter>
<filter id="emb{uid}"><feGaussianBlur in="SourceAlpha" stdDeviation=".12"/><feOffset dx="-.1" dy="-.1" result="a"/>
 <feSpecularLighting in="a" surfaceScale="1.2" specularConstant=".9" specularExponent="18" lighting-color="#fff" result="s"><feDistantLight azimuth="225" elevation="40"/></feSpecularLighting>
 <feComposite in="s" in2="SourceAlpha" operator="in"/></filter>
<filter id="inset{uid}"><feFlood flood-color="#000" flood-opacity=".55"/><feComposite in2="SourceAlpha" operator="out"/><feGaussianBlur stdDeviation=".35"/><feOffset dx=".25" dy=".35"/><feComposite in2="SourceAlpha" operator="in"/></filter>
<clipPath id="wclip{uid}"><rect x="{WIN[0]}" y="{PH - WIN[3]}" width="{WIN[2] - WIN[0]}" height="{WIN[3] - WIN[1]}"/></clipPath>
</defs>'''

def rect_svg(x0, y0, x1, y1, **kw):
    a = ' '.join(f'{k.replace("_", "-")}="{v}"' for k, v in kw.items())
    return f'<rect x="{x0}" y="{PH - y1}" width="{x1 - x0}" height="{y1 - y0}" {a}/>'

_uid = [0]
def front(col, area, tex='A', scale=14, legend=False):
    _uid[0] += 1; u = _uid[0]
    fill = {'A': f'url(#ribs{u})', 'B': col, 'C': f'url(#linen{u})'}[tex]
    p = [defs(u, col), f'<rect x="0" y="0" width="{PW}" height="{PH}" fill="{SN}" filter="url(#soft{u})"/>']
    # printed panels, centre panel drawn with a hole for the window (evenodd path)
    for pid, x0, y0, x1, y1 in PANELS:
        if pid == 'P1':
            wx0, wy0, wx1, wy1 = WIN
            d = (f'M{x0} {PH - y1}H{x1}V{PH - y0}H{x0}Z '
                 f'M{wx0} {PH - wy1}V{PH - wy0}H{wx1}V{PH - wy1}Z')
            p.append(f'<path d="{d}" fill="{fill}" fill-rule="evenodd"/>')
            if tex == 'B': p.append(f'<path d="{d}" fill="url(#gloss{u})" fill-rule="evenodd"/>')
        else:
            p.append(rect_svg(x0, y0, x1, y1, fill=fill))
            if tex == 'B': p.append(rect_svg(x0, y0, x1, y1, fill=f'url(#gloss{u})'))
    if tex == 'C' or tex == 'A':  # raised emboss edge: light top-left, dark bottom-right
        for pid, x0, y0, x1, y1 in PANELS:
            p.append(f'<path d="M{x0} {PH - y0}V{PH - y1}H{x1}" fill="none" stroke="#fff" stroke-opacity=".7" stroke-width=".12"/>')
            p.append(f'<path d="M{x1} {PH - y1}V{PH - y0}H{x0}" fill="none" stroke="#000" stroke-opacity=".28" stroke-width=".12"/>')
    if tex == 'B':
        for pid, x0, y0, x1, y1 in PANELS:
            p.append(rect_svg(x0, y0, x1, y1, fill='none', stroke='#fff', stroke_opacity='.45', stroke_width='.08'))
    # the one window: coloured interior in shadow + label lockup
    wx0, wy0, wx1, wy1 = WIN; ww, wh = wx1 - wx0, wy1 - wy0
    lab_h = min(wy1, LAB_TOP) - wy0
    b64 = label_crop_b64(LABEL[area], ww, lab_h, LAB_TOP - min(wy1, LAB_TOP))
    p.append(f'<g clip-path="url(#wclip{u})">'
             + rect_svg(wx0, wy0, wx1, wy1, fill=f'url(#cave{u})')
             + f'<image x="{wx0}" y="{PH - min(wy1, LAB_TOP)}" width="{ww}" height="{lab_h}" preserveAspectRatio="none" href="data:image/png;base64,{b64}" opacity=".92"/>'
             + f'<rect x="{wx0}" y="{PH - wy1}" width="{ww}" height="{wy1 - LAB_TOP}" fill="url(#cave{u})" opacity=".85"/>'
             + f'<rect x="{wx0}" y="{PH - LAB_TOP - .06}" width="{ww}" height=".12" fill="#fff" opacity=".35"/>'
             + f'<rect x="{wx0}" y="{PH - wy1}" width="{ww}" height="{wh}" fill="none" stroke="#000" stroke-opacity=".0"/>'
             + f'<linearGradient id="vg{u}" x1="0" x2="1"><stop offset="0" stop-color="#000" stop-opacity=".55"/><stop offset=".22" stop-color="#000" stop-opacity="0"/><stop offset=".78" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".55"/></linearGradient>'
             + rect_svg(wx0, wy0, wx1, wy1, fill=f'url(#vg{u})')
             + rect_svg(wx0, wy0, wx1, wy1, fill='#000', filter=f'url(#inset{u})')
             + '</g>')
    p.append(rect_svg(wx0, wy0, wx1, wy1, fill='none', stroke='#000', stroke_opacity='.35', stroke_width='.08'))
    svg = f'<svg viewBox="-0.6 -0.6 {PW + 1.2} {PH + 1.2}" width="{(PW + 1.2) * scale}" height="{(PH + 1.2) * scale}">' + ''.join(p)
    if legend:
        svg += (rect_svg(wx0, wy0, wx1, wy1, fill='none', stroke='#13A54B', stroke_width='.25', stroke_dasharray='.6 .4'))
    svg += f'<rect x="0" y="0" width="{PW}" height="{PH}" fill="none" stroke="#000" stroke-opacity=".12" stroke-width=".1"/></svg>'
    return svg

def side_panel(scale=14):
    u = 900
    return (f'<svg viewBox="-0.6 -0.6 {PW + 1.2} {PH + 1.2}" width="{(PW + 1.2) * scale}" height="{(PH + 1.2) * scale}">'
            f'<defs><symbol id="cs" viewBox="0 0 104.26 100">{CREST}</symbol><symbol id="ws" viewBox="0 -38 848 138">{WM}</symbol>'
            f'<filter id="e"><feGaussianBlur in="SourceAlpha" stdDeviation=".18"/><feSpecularLighting surfaceScale="2" specularConstant="1" specularExponent="16" lighting-color="#fff"><feDistantLight azimuth="225" elevation="35"/></feSpecularLighting><feComposite in2="SourceAlpha" operator="in"/></filter>'
            f'<filter id="d"><feGaussianBlur in="SourceAlpha" stdDeviation=".18"/><feOffset dx=".18" dy=".22"/><feComposite in2="SourceAlpha" operator="out"/><feFlood flood-color="#000" flood-opacity=".22"/><feComposite operator="in" in2="SourceAlpha"/></filter></defs>'
            f'<rect width="{PW}" height="{PH}" fill="{SN}"/>'
            f'<g color="{mix(SN, "#000000", .06)}"><use href="#cs" x="3" y="{PH - 20 - 7}" width="14" height="13.4"/></g>'
            f'<g color="#fff" opacity=".9" filter="url(#e)"><use href="#cs" x="3" y="{PH - 20 - 7}" width="14" height="13.4"/></g>'
            f'<g color="{OX}"><use href="#ws" x="6" y="{PH - 6 - 1.3}" width="8" height="1.3"/></g>'
            f'<rect width="{PW}" height="{PH}" fill="none" stroke="#000" stroke-opacity=".12" stroke-width=".1"/></svg>')

def dieline(scale=7.2):
    # simplified flat: P1 left, P2 front, P3 right, P4 back + glue + tucks (inside size)
    W = 7 + 20 * 4; H = 100
    o = []
    X = lambda i: 7 + 20 * i
    o.append(f'<path d="M0 32 L7 30 V70 L0 68Z" fill="#fff" stroke="#000" stroke-width=".25"/>')
    o.append(f'<rect x="7" y="30" width="80" height="40" fill="#fff" stroke="#000" stroke-width=".25"/>')
    for i in (1, 2, 3): o.append(f'<line x1="{X(i)}" y1="30" x2="{X(i)}" y2="70" stroke="#E4007C" stroke-width=".25" stroke-dasharray="1.2 .8"/>')
    o.append(f'<line x1="7" y1="30" x2="7" y2="70" stroke="#E4007C" stroke-width=".25" stroke-dasharray="1.2 .8"/>')
    # tucks
    o.append(f'<path d="M{X(3)} 30 V10 H{X(4)} V30" fill="#fff" stroke="#000" stroke-width=".25"/><path d="M{X(3)} 10 q0 -8 6 -8 h8 q6 0 6 8" fill="#fff" stroke="#000" stroke-width=".25"/>')
    o.append(f'<path d="M{X(1)} 70 V90 H{X(2)} V70" fill="#fff" stroke="#000" stroke-width=".25"/><path d="M{X(1)} 90 q0 8 6 8 h8 q6 0 6 -8" fill="#fff" stroke="#000" stroke-width=".25"/>')
    for i in (0, 2):
        o.append(f'<path d="M{X(i) + 1} 30 L{X(i) + 3} 22 H{X(i) + 17} L{X(i) + 19} 30" fill="#fff" stroke="#000" stroke-width=".25"/>')
        o.append(f'<path d="M{X(i) + 1} 70 L{X(i) + 3} 78 H{X(i) + 17} L{X(i) + 19} 70" fill="#fff" stroke="#000" stroke-width=".25"/>')
    # front panel = P2 at X(1); printed panels + window
    fx, fy = X(1), 30
    for pid, x0, y0, x1, y1 in PANELS:
        o.append(f'<rect x="{fx + x0}" y="{fy + PH - y1}" width="{x1 - x0}" height="{y1 - y0}" fill="#1F4FD0" fill-opacity=".85"/>')
    wx0, wy0, wx1, wy1 = WIN
    o.append(f'<rect x="{fx + wx0}" y="{fy + PH - wy1}" width="{wx1 - wx0}" height="{wy1 - wy0}" fill="#fff" stroke="#000" stroke-width=".3"/>')
    o.append(f'<rect x="{fx + wx0}" y="{fy + PH - wy1}" width="{wx1 - wx0}" height="{wy1 - wy0}" fill="url(#hatch)"/>')
    # left side emboss marker
    o.append(f'<circle cx="{X(0) + 10}" cy="{30 + 20}" r="7" fill="none" stroke="#2A6BFF" stroke-width=".3" stroke-dasharray=".8 .6"/>')
    o.append(f'<rect x="{X(0) + 6}" y="{70 - 7.3}" width="8" height="1.3" fill="{OX}"/>')
    # dims
    t = lambda x, y, s, sz=1.7, a='middle': f'<text x="{x}" y="{y}" font-size="{sz}" text-anchor="{a}" font-family="IBM Plex Mono,monospace" fill="#222">{s}</text>'
    o.append(t(X(1) + 10, 74, 'P2 FRONT 正面'))
    o.append(t(X(0) + 10, 74, 'P1 LEFT 左侧'))
    o.append(t(X(2) + 10, 74, 'P3 RIGHT 右侧'))
    o.append(t(X(3) + 10, 74, 'P4 BACK 背面'))
    o.append(t(X(3) + 10, 46, 'inside face 内面:'))
    o.append(t(X(3) + 10, 49, '100% area colour'))
    o.append(t(X(3) + 10, 52, '满版专色'))
    o.append(f'<line x1="7" y1="103" x2="87" y2="103" stroke="#222" stroke-width=".2"/>' + t(47, 107, '87 flat 展开 · panels 20 × 40 (inside)', 2.2))
    hatch = '<defs><pattern id="hatch" width="1.2" height="1.2" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width=".45" height="1.2" fill="#13A54B"/></pattern></defs>'
    return f'<svg viewBox="-2 0 92 110" width="{92 * scale}" height="{110 * scale}">{hatch}{"".join(o)}</svg>'

FONT = "<link href='https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;600;800&family=IBM+Plex+Mono:wght@400;500&display=swap' rel='stylesheet'>"
CSS = f'''<style>*{{box-sizing:border-box}}body{{margin:0;background:#F4F0EA;font-family:'Inter Tight',sans-serif;color:#1a1414}}
.pg{{width:1600px;padding:56px}}.eb{{font:500 13px 'IBM Plex Mono';letter-spacing:.18em;color:#6b5f5a}}
h1{{font-size:64px;margin:10px 0 6px;letter-spacing:-.02em}}h1 i{{display:inline-block;width:20px;height:20px;border-radius:50%;background:{OX};margin-right:14px;vertical-align:middle}}
.lede{{font-size:19px;line-height:1.5;max-width:1150px;color:#3a302d}}h2{{font:500 13px 'IBM Plex Mono';letter-spacing:.18em;margin:44px 0 14px;color:#6b5f5a}}
.card{{background:#fff;border-radius:6px;padding:26px}}.row{{display:flex;gap:22px;align-items:flex-start}}
.cap{{font-size:15px;margin-top:12px;line-height:1.45}}.cap b{{font-weight:800}}.mono{{font:400 12px 'IBM Plex Mono';color:#6b5f5a}}
.key{{display:flex;gap:28px;font-size:15px;margin:6px 0 18px}}.sw{{display:inline-block;width:22px;height:16px;vertical-align:-3px;margin-right:8px;border-radius:2px}}
table{{border-collapse:collapse;font-size:14px;width:100%}}td{{border-top:1px solid #e6dfd6;padding:7px 8px;vertical-align:top}}</style>'''

def board1():
    met = AREAS[0]
    tex = [('A', 'Raised rib emboss', 'Fine horizontal ribs, 0.6 mm pitch, blind-embossed into the printed panels. Reads as tide lines and feels ridged under the thumb.', '击凸细横纹 0.6 mm'),
           ('B', 'Gloss spot-UV on soft-touch', 'Box is soft-touch matte; only the colour panels get gloss UV, so they catch light like lit glass and feel slick against the velvet board.', '局部UV（触感膜底）'),
           ('C', 'Raised linen emboss', 'A linen-weave texture embossed into the colour panels only. Warm and tactile, the most "paper" of the three.', '布纹压纹')]
    cards = ''
    for k, n, d, zh in tex:
        cards += f'<div class="card" style="flex:1"><div class="row" style="gap:14px">{front(met[1], met[0], k, 15.5, legend=True)}</div><div class="cap"><b>{k} · {n}</b> <span class="mono">{zh}</span><br>{d}</div></div>'
    cw = ''
    for n, h, sk in AREAS:
        cw += f'<div style="text-align:center">{front(h, n, "A", 8.6)}<div class="cap" style="margin-top:8px"><b>{n}</b><br><span class="mono">{sk}</span></div></div>'
    wx0, wy0, wx1, wy1 = WIN
    tbl = ''.join(f'<tr><td><b>{pid}</b></td><td>{x1 - x0:g} × {y1 - y0:g}</td><td>x {x0:g}–{x1:g}, y {y0:g}–{y1:g}</td><td>Printed area colour 印刷色块 (not cut)</td></tr>' for pid, x0, y0, x1, y1 in PANELS)
    tbl = (f'<tr><td><b style="color:#13A54B">W · window</b></td><td>{wx1 - wx0:g} × {wy1 - wy0:g}</td><td>x {wx0:g}–{wx1:g}, y {wy0:g}–{wy1:g}</td><td><b>The ONLY die-cut 唯一开窗</b>, inside P1</td></tr>' + tbl)
    html = f'''<!doctype html><html><head><meta charset="utf-8">{FONT}{CSS}</head><body><div class="pg">
<div class="eb">ZUMA TIDES · PACKAGING · WINDOW CARTON · ONE-WINDOW VERSION</div>
<h1><i></i>One window, printed panels</h1>
<div class="lede">Same panel layout as the hero render. Only <b>one small window</b> is cut, in the middle of the tall centre panel: through it you see the crest on the vial label and, above the label, the coloured inside of the box in shadow through the glass. Every other panel is <b>printed</b> solid area colour on the Snow board. The whole inside of the sheet is flood-printed in the area colour. One sheet, no sleeve, no liner.</div>
<h2>01 · FRONT PANEL, ABOUT 6:1 · THREE PANEL TEXTURES</h2>
<div class="key"><span><span class="sw" style="background:repeating-linear-gradient(45deg,#13A54B 0 3px,#fff 3px 6px);border:1px solid #13A54B"></span><b>Green dashed</b> = the one die-cut window (open)</span><span><span class="sw" style="background:#1F4FD0"></span><b>Colour</b> = printed panel (not cut)</span><span><span class="sw" style="background:{SN};border:1px solid #ccc"></span><b>Snow</b> = soft-touch board</span></div>
<div class="row">{cards}</div>
<h2>02 · ALL SIX AREA COLOURS · TEXTURE A</h2>
<div class="card"><div class="row" style="justify-content:space-between">{cw}</div></div>
<h2>03 · SIMPLIFIED DIELINE · LEFT SIDE · PANEL MAP (mm, from the front panel's bottom-left corner)</h2>
<div class="row"><div class="card">{dieline(6.6)}</div>
<div style="flex:1;display:flex;flex-direction:column;gap:22px"><div class="card row" style="gap:20px">{side_panel(11)}<div class="cap" style="margin:0"><b>Left side P1</b><br>Crest blind-embossed 14 mm, no ink (击凸)<br>"zuma tides" Oxblood hot foil, 8 mm wide (烫金)<br><br><b>Inside of the sheet</b><br>100% flood in the area colour (内面满版专色)<br><br><b>Window</b><br>6 × 6 mm, x 7–13, y 17.5–23.5. Frames the crest on the vial label (crest at y 18.1–21.5) with clear glass above the label top (y 22.6), where the coloured inside shows in shadow. Vial goes in crest-forward 药瓶花徽朝窗口.</div></div>
<div class="card"><table><tr><td class="mono">ID</td><td class="mono">W × H</td><td class="mono">Position</td><td class="mono">Type</td></tr>{tbl}</table>
<div class="mono" style="margin-top:10px">Front panel 20 × 40 (inside size). Panels P1–P6 from the v1 hero layout. Printed panels can be thin (2 mm strips are fine: print, not cut).</div></div></div></div>
</div></body></html>'''
    open('box-onewindow.html', 'w').write(html)

# ---------------- mailers ----------------
def guillo(x, y, w, h, d, rnd, out):
    if d > 6 or (w < 1.0 and h < 1.0) or (d > 2 and rnd.random() < .22):
        out.append((x, y, w, h)); return
    if w > h * rnd.uniform(.7, 1.4):
        s = rnd.uniform(.3, .7) * w; guillo(x, y, s, h, d + 1, rnd, out); guillo(x + s, y, w - s, h, d + 1, rnd, out)
    else:
        s = rnd.uniform(.3, .7) * h; guillo(x, y, w, s, d + 1, rnd, out); guillo(x, y + s, w, h - s, d + 1, rnd, out)

def tonal_grid(W, H, seed, gap=.06):
    rnd = random.Random(seed); out = []; guillo(0, 0, W, H, 0, rnd, out)
    tones = [mix(OX, '#000000', .16), OX, mix(OX, '#FFFFFF', .09), mix(OX, '#000000', .07)]
    return ''.join(f'<rect x="{x + gap / 2:.3f}" y="{y + gap / 2:.3f}" width="{max(w - gap, .01):.3f}" height="{max(h - gap, .01):.3f}" fill="{rnd.choice(tones)}"/>' for x, y, w, h in out)

def bubbles(W, H, dark=True):
    return (f'<pattern id="bb{W}{H}{int(dark)}" width=".44" height=".38" patternUnits="userSpaceOnUse"><circle cx=".22" cy=".19" r=".16" fill="#fff" opacity="{.05 if dark else .2}"/>'
            f'<circle cx=".17" cy=".14" r=".05" fill="#fff" opacity="{.09 if dark else .5}"/><circle cx=".22" cy=".19" r=".16" fill="none" stroke="#000" stroke-opacity="{.07 if dark else .04}" stroke-width=".015"/></pattern>')

def mailer(kind, face, scale=48):
    W, H = 6.0, 10.0; FL = 1.73  # in; flap 44 mm
    hh = H + (FL if face == 'back' else 0)
    p = [f'<defs><symbol id="c{kind}{face}" viewBox="0 0 104.26 100">{CREST}</symbol><symbol id="w{kind}{face}" viewBox="0 -38 848 138">{WM}</symbol>{bubbles(W, H)}{bubbles(W, H, False)}'
         f'<clipPath id="cl{kind}{face}"><rect width="{W}" height="{hh}" rx=".08"/></clipPath></defs><g clip-path="url(#cl{kind}{face})">']
    if face == 'inside':
        p.append(f'<rect width="{W}" height="{H}" fill="{SN}"/><rect width="{W}" height="{H}" fill="url(#bb{W}{H}0)"/>')
        p.append(f'<text x="{W / 2}" y="{H * .42}" text-anchor="middle" font-family="Inter Tight" font-weight="800" font-size=".42" fill="{OX}">Research, refined.</text>')
        p.append(f'<g color="{OX}"><use href="#c{kind}{face}" x="{W / 2 - .3}" y="{H * .47}" width=".6" height=".58"/></g>')
    elif face == 'front':
        if kind == 'grid':
            p.append(f'<rect width="{W}" height="{H}" fill="{OX}"/>' + tonal_grid(W, H, 21))
            p.append(f'<g color="{SN}"><use href="#c{kind}{face}" x="{W - 3.3}" y="{H - 7.3}" width="6.6" height="6.33"/></g>')
            p.append(f'<g color="{SN}"><use href="#w{kind}{face}" x=".45" y=".55" width="1.9" height=".31"/></g>')
            p.append(f'<text x="{W / 2}" y="{H - .3}" text-anchor="middle" font-family="IBM Plex Mono" font-size=".095" letter-spacing=".01" fill="{SN}" opacity=".85">FOR LABORATORY RESEARCH USE ONLY · NOT FOR HUMAN OR VETERINARY USE</text>')
        else:  # window mailer: six Snow rectangles mirroring the box panel layout, scaled up
            p.append(f'<rect width="{W}" height="{H}" fill="{OX}"/>')
            k = 0.115; ox, oy = (W - PW * k) / 2, 1.6
            for pid, x0, y0, x1, y1 in PANELS:
                p.append(f'<rect x="{ox + x0 * k:.3f}" y="{oy + (PH - y1) * k:.3f}" width="{(x1 - x0) * k:.3f}" height="{(y1 - y0) * k:.3f}" fill="{SN}"/>')
            wx0, wy0, wx1, wy1 = WIN
            p.append(f'<rect x="{ox + wx0 * k:.3f}" y="{oy + (PH - wy1) * k:.3f}" width="{(wx1 - wx0) * k:.3f}" height="{(wy1 - wy0) * k:.3f}" fill="{OX}"/>')
            p.append(f'<g color="{SN}"><use href="#c{kind}{face}" x="{ox + wx0 * k + (wx1 - wx0) * k / 2 - .22}" y="{oy + (PH - wy1) * k + .06}" width=".44" height=".42"/></g>')
            p.append(f'<g color="{SN}"><use href="#w{kind}{face}" x="{W / 2 - 1.05}" y="{oy + PH * k + .55}" width="2.1" height=".34"/></g>')
            p.append(f'<text x="{W / 2}" y="{H - .3}" text-anchor="middle" font-family="IBM Plex Mono" font-size=".095" letter-spacing=".01" fill="{SN}" opacity=".85">FOR LABORATORY RESEARCH USE ONLY · NOT FOR HUMAN OR VETERINARY USE</text>')
        p.append(f'<rect width="{W}" height="{H}" fill="url(#bb{W}{H}1)"/>')
        p.append(f'<rect width="{W}" height="{H}" fill="url(#gl)" opacity=".0"/>')
    else:  # back with flap
        if kind == 'grid':
            p.append(f'<rect width="{W}" height="{hh}" fill="{OX}"/>' + tonal_grid(W, hh, 7))
        else:
            p.append(f'<rect width="{W}" height="{hh}" fill="{OX}"/>')
        p.append(f'<line x1="0" y1="{FL}" x2="{W}" y2="{FL}" stroke="#000" stroke-opacity=".35" stroke-width=".02"/>')
        p.append(f'<rect x="0" y="{FL - .45}" width="{W}" height=".25" fill="{SN}" opacity=".18"/>')
        p.append(f'<text x="{W / 2}" y="{FL - .27}" text-anchor="middle" font-family="IBM Plex Mono" font-size=".1" fill="{SN}" opacity=".8">PEEL &amp; SEAL · TEAR STRIP</text>')
        p.append(f'<rect x="1" y="{FL + 1.4}" width="4" height="6" fill="{SN}" rx=".04"/><text x="3" y="{FL + 4.4}" text-anchor="middle" font-family="IBM Plex Mono" font-size=".16" fill="#aaa">SHIPPING LABEL · 4 × 6 IN</text>')
        p.append(f'<g color="{SN}"><use href="#c{kind}{face}" x="{W / 2 - .22}" y=".5" width=".44" height=".42"/></g>')
        p.append(f'<text x="{W / 2}" y="{hh - .3}" text-anchor="middle" font-family="IBM Plex Mono" font-size=".12" fill="{SN}" opacity=".8">zumatides.com · FOR LABORATORY RESEARCH USE ONLY</text>')
        p.append(f'<rect width="{W}" height="{hh}" fill="url(#bb{W}{H}1)"/>')
    p.append('</g>')
    return f'<svg viewBox="-.05 -.05 {W + .1} {hh + .1}" width="{(W + .1) * scale}" height="{(hh + .1) * scale}" style="filter:drop-shadow(0 6px 10px rgba(0,0,0,.18))">{"".join(p)}</svg>'

def board2():
    def block(kind, title, desc, ink):
        return (f'<div class="card" style="flex:1"><div class="row" style="align-items:flex-end;gap:18px;justify-content:center">'
                f'<div style="text-align:center">{mailer(kind, "front", 40)}<div class="mono">FRONT</div></div>'
                f'<div style="text-align:center">{mailer(kind, "back", 40)}<div class="mono">BACK · FLAP</div></div>'
                f'<div style="text-align:center">{mailer(kind, "inside", 40)}<div class="mono">INSIDE</div></div></div>'
                f'<div class="cap"><b>{title}</b><br>{desc}<br><span class="mono">{ink}</span></div></div>')
    html = f'''<!doctype html><html><head><meta charset="utf-8">{FONT}{CSS}</head><body><div class="pg" style="width:1800px">
<div class="eb">ZUMA TIDES · PACKAGING · BUBBLE MAILER · #0, 6 × 10 IN, 44 MM FLAP</div>
<h1><i></i>Mailer: pick vs option 1</h1>
<div class="lede">Left is your pick: tone-on-tone Lightbox grid with the giant Snow crest cropped off the right edge. Right is option 1, the Window mailer, updated so its Snow rectangles mirror the new one-window box layout (the small Oxblood window with the crest sits in the tall centre panel, just like the box).</div>
<h2>01 · SIDE BY SIDE</h2>
<div class="row">{block('grid', 'Your pick · Tone-on-tone grid + giant crest', 'Oxblood film, Lightbox grid in tonal Oxblood all over (matte base, gloss tones), oversized Snow crest cropped off the right edge, small zuma tides top-left, research-use line along the bottom. Inside Snow: "Research, refined."', 'Matte Oxblood film + gloss tonal print + 1 Snow ink · inside 1 ink')}
{block('win', 'Option 1 · Window mailer (updated)', 'Oxblood with six Snow panels in the exact box layout; the centre panel carries a small Oxblood window with the Snow crest, like the box. zuma tides wordmark below.', '1 Snow ink on Oxblood film · inside 1 ink')}</div>
</div></body></html>'''
    open('mailer-compare.html', 'w').write(html)

board1(); board2()

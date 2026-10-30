# Rev F insert board: U-cradle with a fold-forward shelf. All numbers in mm, from geomE.json.
import json, os, math
HERE = os.path.dirname(os.path.abspath(__file__))
G = json.load(open(os.path.join(HERE, '..', 'geomE.json')))
OX, SNOW, STUCCO = '#6E1C2A', '#FCFBF8', '#EFE4D2'
AREAS = [(a['name'], a['zh'], a['hex']) for a in G['areas']]
MET = AREAS[0][2]
IN = G['inside']['w']; T = 0.45                     # carton inside 20 x 20; insert board ~0.45
W = G['windows'][0]; WY1 = W['y1']                  # window top 22.5
LAB = G['vial']['label_band_y']                     # 2.6-22.6
SH = 23.0                                           # shelf underside height (body is straight to 23.5)
OUT = 19.4                                          # insert outer width/depth (0.3 mm clearance per side)
SHELF = OUT - 2 * T                                 # 18.5 between the side walls
HOLE = 16.5; LIP = 2.5

def iso(x, y, z, s=7, ox=0, oy=0):                  # x right, y depth, z up
    return (ox + (x - y) * s * 0.866, oy + (x + y) * s * 0.5 - z * s)

def poly(pts, fill, stroke='#2b2b2b', sw=1.2, op=1, extra=''):
    return f'<polygon points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" fill-opacity="{op}" stroke-linejoin="round" {extra}/>'

def box_iso(x0, y0, z0, w, d, h, top, left, right, s, ox, oy, op=1):
    P = lambda x, y, z: iso(x, y, z, s, ox, oy)
    out = poly([P(x0, y0 + d, z0), P(x0 + w, y0 + d, z0), P(x0 + w, y0 + d, z0 + h), P(x0, y0 + d, z0 + h)], left, op=op)
    out += poly([P(x0 + w, y0, z0), P(x0 + w, y0 + d, z0), P(x0 + w, y0 + d, z0 + h), P(x0 + w, y0, z0 + h)], right, op=op)
    out += poly([P(x0, y0, z0 + h), P(x0 + w, y0, z0 + h), P(x0 + w, y0 + d, z0 + h), P(x0, y0 + d, z0 + h)], top, op=op)
    return out

def exploded():
    s = 6.2; o = []
    # carton (white, window on the left-facing front x-face shown as the "y+d" face)
    ox, oy = 170, 270
    o.append(box_iso(0, 0, 0, 20, 20, 40, '#f1eee8', '#ffffff', '#e4e0d8', s, ox, oy))
    P = lambda x, y, z: iso(x, y, z, s, ox, oy)
    o.append(poly([P(W['x0'], 20, W['y0']), P(W['x1'], 20, W['y0']), P(W['x1'], 20, W['y1']), P(W['x0'], 20, W['y1'])], '#cfd8e6', '#2b2b2b', 1.2))
    # insert: U walls + shelf (raised for explode)
    ox2, oy2 = 500, 290
    P2 = lambda x, y, z: iso(x, y, z, s, ox2, oy2)
    c = MET
    # back wall (y=0 plane, far), side walls x=0 and x=OUT
    o.append(poly([P2(0, 0, 0), P2(OUT, 0, 0), P2(OUT, 0, SH), P2(0, 0, SH)], c, op=0.95))
    o.append(poly([P2(0, 0, 0), P2(0, OUT, 0), P2(0, OUT, SH), P2(0, 0, SH)], c, op=0.85))
    o.append(poly([P2(OUT, 0, 0), P2(OUT, OUT, 0), P2(OUT, OUT, SH), P2(OUT, 0, SH)], c, op=0.75))
    # shelf lifted 8 mm to show it, with hole and up-turned lip
    z = SH + 6
    o.append(poly([P2(T, 0, z), P2(OUT - T, 0, z), P2(OUT - T, SHELF, z), P2(T, SHELF, z)], c))
    o.append(poly([P2(T, SHELF, z), P2(OUT - T, SHELF, z), P2(OUT - T, SHELF, z + LIP), P2(T, SHELF, z + LIP)], c, op=0.8))
    hx, hy = OUT / 2, SHELF - 10 + T
    pts = [P2(hx + HOLE / 2 * math.cos(a), hy + HOLE / 2 * math.sin(a), z) for a in [i * math.pi / 24 for i in range(48)]]
    o.append(poly(pts, '#ffffff', '#2b2b2b', 1.2))
    a, b = P2(0, 0, SH), P2(T, 0, z)
    o.append(f'<path d="M{P2(OUT/2,1,SH)[0]:.0f},{P2(OUT/2,1,SH)[1]:.0f} C {P2(OUT/2,1,SH)[0]-30:.0f},{P2(OUT/2,1,SH)[1]-30:.0f} {P2(OUT/2,1,z)[0]-30:.0f},{P2(OUT/2,1,z)[1]:.0f} {P2(OUT/2,1,z)[0]:.0f},{P2(OUT/2,1,z)[1]:.0f}" stroke="#2b2b2b" fill="none" stroke-dasharray="4 3" marker-end="url(#ar)"/>')
    # vial
    vx, vy = 830, 150
    o.append(vial_side(vx, vy, 6.2))
    # arrows between
    o.append(f'<path d="M770,280 L690,280" stroke="#2b2b2b" stroke-width="1.6" marker-end="url(#ar)"/><path d="M430,280 L350,280" stroke="#2b2b2b" stroke-width="1.6" marker-end="url(#ar)"/>')
    return f'<svg viewBox="0 0 1000 430" width="1100" height="473">{DEFS}{"".join(o)}</svg><div class="caps"><div><b>A · Carton 外盒</b>400 gsm SBS, plain white inside 内面白色</div><div><b>B · Insert 内卡</b>U-cradle + fold-forward shelf 支架; area colour</div><div><b>C · Vial 药瓶</b>Ø16 × 35 mm, label-forward 标签朝前</div></div>'

def vial_side(x, y, s, label_col=MET, cut=False):
    # side silhouette from the model: body Ø16 to 23.5, shoulder to 26, neck 27.4, lip 29.5, cap to 35
    def Y(mm): return y + (35 - mm) * s
    r = 8 * s; cx = x
    o = [f'<rect x="{cx-r}" y="{Y(23.5)}" width="{2*r}" height="{23.5*s}" rx="{1.5*s}" fill="#eef4f8" stroke="#2b2b2b" stroke-width="1.2"/>',
         f'<path d="M{cx-r},{Y(23.5)} Q{cx-r},{Y(26)} {cx-5.4*s},{Y(26.6)} L{cx+5.4*s},{Y(26.6)} Q{cx+r},{Y(26)} {cx+r},{Y(23.5)} Z" fill="#eef4f8" stroke="#2b2b2b" stroke-width="1.2"/>',
         f'<rect x="{cx-label_w(s)}" y="{Y(LAB[1])}" width="{2*label_w(s)}" height="{(LAB[1]-LAB[0])*s}" fill="{label_col}" opacity=".9"/>',
         f'<rect x="{cx-6.5*s}" y="{Y(29.5)}" width="{13*s}" height="{2.9*s}" fill="#c9c9c9" stroke="#2b2b2b" stroke-width="1"/>',
         f'<rect x="{cx-6.8*s}" y="{Y(35)}" width="{13.6*s}" height="{5.5*s}" rx="{1*s}" fill="{OX}" stroke="#2b2b2b" stroke-width="1"/>']
    return ''.join(o)
def label_w(s): return 8 * s

def section():
    s = 11; x0, yb = 70, 560; o = []
    Y = lambda mm: yb - mm * s
    # carton walls (front on the left, back on the right), floor
    o.append(f'<rect x="{x0-T*s}" y="{Y(40)}" width="{T*s}" height="{40*s}" fill="#bdbdbd"/>')
    o.append(f'<rect x="{x0+IN*s}" y="{Y(40)}" width="{T*s}" height="{40*s}" fill="#bdbdbd"/>')
    o.append(f'<rect x="{x0-T*s}" y="{yb}" width="{(IN+2*T)*s}" height="{T*s}" fill="#bdbdbd"/>')
    # window gap in the front wall
    o.append(f'<rect x="{x0-T*s-1}" y="{Y(WY1)}" width="{T*s+2}" height="{(WY1-W["y0"])*s}" fill="#fff"/>')
    o.append(f'<rect x="{x0-T*s-26}" y="{Y(WY1)}" width="18" height="{(WY1-W["y0"])*s}" fill="url(#hatch)" stroke="#0E9A58"/>')
    # insert: back wall + shelf with hole + lip
    ix = x0 + (IN - OUT) / 2 * s
    o.append(f'<rect x="{ix+(OUT-T)*s}" y="{Y(SH)}" width="{T*s}" height="{SH*s}" fill="{MET}"/>')
    o.append(f'<rect x="{ix}" y="{Y(SH+T)}" width="{(OUT/2-HOLE/2)*s}" height="{T*s}" fill="{MET}"/>')
    o.append(f'<rect x="{ix+(OUT/2+HOLE/2)*s}" y="{Y(SH+T)}" width="{(OUT/2-HOLE/2)*s}" height="{T*s}" fill="{MET}"/>')
    o.append(f'<rect x="{ix}" y="{Y(SH+T+LIP)}" width="{T*s}" height="{LIP*s}" fill="{MET}"/>')
    # vial (centred)
    o.append(vial_side(x0 + IN / 2 * s, Y(35), s))
    # dims
    def dim(y_mm, text, col='#333', dx=0):
        yy = Y(y_mm); return f'<line x1="{x0-T*s-40}" x2="{x0+IN*s+60+dx}" y1="{yy}" y2="{yy}" stroke="{col}" stroke-dasharray="3 3" stroke-width=".8"/><text x="{x0+IN*s+64+dx}" y="{yy+4}" class="dim" fill="{col}">{text}</text>'
    o.append(dim(W['y0'], f'window bottom 开窗下沿 {W["y0"]}', '#0E9A58'))
    o.append(dim(WY1, f'window top 开窗上沿 {WY1}', '#0E9A58').replace('y="'+str(Y(WY1)+4)+'"','y="'+str(Y(WY1)+30)+'"'))
    o.append(dim(LAB[1], f'label top 标签上沿 {LAB[1]}', '#555', 0).replace('y="'+str(Y(LAB[1])+4)+'"','y="'+str(Y(LAB[1])+16)+'"'))
    o.append(dim(SH, f'shelf underside 支架下沿 {SH}', MET).replace('y="'+str(Y(SH)+4)+'"','y="'+str(Y(SH)-6)+'"'))
    o.append(dim(SH + T + LIP, f'lip top 翻边上沿 {SH+T+LIP:.2f}', MET).replace('y="'+str(Y(SH+T+LIP)+4)+'"','y="'+str(Y(SH+T+LIP)-4)+'"'))
    o.append(f'<text x="{x0-T*s-30}" y="{Y(W["y0"])+22}" class="sub" fill="#0E9A58">front 正面</text>')
    o.append(f'<text x="{x0+IN*s-10}" y="{yb+40}" class="sub">back 背面</text>')
    o.append(f'<text x="{x0}" y="{yb+40}" class="sub">floor 盒底</text>')
    clr = SH - WY1
    o.append(f'<text x="{x0-30}" y="{Y(43)}" class="cap">Shelf sits {clr:.1f} mm above the window top, behind solid board</text><text x="{x0-30}" y="{Y(43)+20}" class="sub">支架高于开窗{clr:.1f}mm，在实心纸板后，不外露</text>')
    return f'<svg viewBox="0 0 640 620" width="640" height="620">{DEFS}{"".join(o)}</svg>'

def topdown(col, s=14, label=True, ox=0, oy=0, w=None):
    # looking straight down into the opened carton: white interior, coloured shelf, vial cap + shoulder
    o = []; m = 14
    x0, y0 = ox + m, oy + m
    o.append(f'<rect x="{x0-T*s}" y="{y0-T*s}" width="{(IN+2*T)*s}" height="{(IN+2*T)*s}" fill="#d9d5cc" rx="2"/>')
    o.append(f'<rect x="{x0}" y="{y0}" width="{IN*s}" height="{IN*s}" fill="#ffffff"/>')
    ix = x0 + (IN - OUT) / 2 * s; iy = y0 + (IN - OUT) / 2 * s
    o.append(f'<rect x="{ix}" y="{iy}" width="{OUT*s}" height="{OUT*s}" fill="{col}"/>')
    o.append(f'<rect x="{ix}" y="{iy}" width="{OUT*s}" height="{OUT*s}" fill="url(#shade)"/>')
    o.append(f'<rect x="{ix+T*s}" y="{iy+(OUT-T-LIP*0.35)*s}" width="{SHELF*s}" height="{LIP*0.35*s}" fill="#000" opacity=".12"/>')
    cx, cy = x0 + IN / 2 * s, y0 + IN / 2 * s
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{HOLE/2*s}" fill="#0b0b0b" opacity=".35"/>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{8*s}" fill="#e9f0f4" stroke="#9fb0bb" stroke-width="1"/>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{6.8*s}" fill="{OX}"/>')
    o.append(f'<circle cx="{cx-1.8*s}" cy="{cy-1.8*s}" r="{4*s}" fill="#ffffff" opacity=".10"/>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{6.8*s}" fill="none" stroke="#4a1019" stroke-width="{0.4*s}"/>')
    if label:
        o.append(f'<text x="{x0+IN*s/2}" y="{y0+IN*s+0.45*s+26}" text-anchor="middle" class="sub">front / window side 正面（开窗）</text>')
    return ''.join(o)

def dieline():
    s = 9; ox, oy = 40, 30; o = []
    X = lambda mm: ox + mm * s; Y = lambda mm: oy + mm * s
    col = MET
    # flat: [L side][Back][R side] across, 19.4 each, height SH; shelf above back (SHELF x SHELF), lip above shelf
    yW = LIP + SHELF                     # walls start below the shelf+lip
    pieces = [(0, yW, OUT, SH, 'L SIDE 左侧'), (OUT, yW, OUT, SH, 'BACK 背板'), (2 * OUT, yW, OUT, SH, 'R SIDE 右侧'),
              (OUT + T, LIP, SHELF, SHELF, 'SHELF 支架'), (OUT + T, 0, SHELF, LIP, 'LIP 翻边')]
    for x, y, w, h, n in pieces:
        o.append(f'<rect x="{X(x)}" y="{Y(y)}" width="{w*s}" height="{h*s}" fill="{col}" fill-opacity=".9"/>')
        o.append(f'<text x="{X(x+w/2)}" y="{Y(y+h/2)+4}" text-anchor="middle" class="dl" fill="#fff">{n}</text>')
    # outline cut
    path = (f'M{X(0)},{Y(yW)} L{X(OUT)},{Y(yW)} L{X(OUT)},{Y(yW)} L{X(OUT+T)},{Y(yW)} L{X(OUT+T)},{Y(0)} L{X(OUT+T+SHELF)},{Y(0)} '
            f'L{X(OUT+T+SHELF)},{Y(yW)} L{X(3*OUT)},{Y(yW)} L{X(3*OUT)},{Y(yW+SH)} L{X(0)},{Y(yW+SH)} Z')
    o.append(f'<path d="{path}" fill="none" stroke="#000" stroke-width="1.6"/>')
    # hole
    hcx, hcy = X(OUT + T + SHELF / 2), Y(LIP + SHELF - (SHELF - (10 - (IN - OUT) / 2 - T)))
    hcy = Y(LIP + (10 - (IN - OUT) / 2 - T))  # centre 10 mm from carton front -> measured from lip crease
    o.append(f'<circle cx="{hcx}" cy="{hcy}" r="{HOLE/2*s}" fill="#fff" stroke="#000" stroke-width="1.6"/>')
    # creases
    for (x1, y1, x2, y2) in [(OUT, yW, OUT, yW + SH), (2 * OUT, yW, 2 * OUT, yW + SH), (OUT + T, yW, OUT + T + SHELF, yW), (OUT + T, LIP, OUT + T + SHELF, LIP)]:
        o.append(f'<line x1="{X(x1)}" y1="{Y(y1)}" x2="{X(x2)}" y2="{Y(y2)}" stroke="#E4007C" stroke-width="1.4" stroke-dasharray="6 4"/>')
    # dims
    def hd(xa, xb, yy, t): return f'<line x1="{X(xa)}" x2="{X(xb)}" y1="{yy}" y2="{yy}" stroke="#333" marker-start="url(#tk)" marker-end="url(#tk)"/><text x="{(X(xa)+X(xb))/2}" y="{yy+16}" text-anchor="middle" class="dim">{t}</text>'
    def vd(ya, yb_, xx, t): return f'<line y1="{Y(ya)}" y2="{Y(yb_)}" x1="{xx}" x2="{xx}" stroke="#333" marker-start="url(#tk)" marker-end="url(#tk)"/><text x="{xx+8}" y="{(Y(ya)+Y(yb_))/2+4}" class="dim">{t}</text>'
    yy = Y(yW + SH) + 18
    o += [hd(0, OUT, yy, f'{OUT}'), hd(OUT, 2 * OUT, yy, f'{OUT}'), hd(2 * OUT, 3 * OUT, yy, f'{OUT}'), hd(0, 3 * OUT, yy + 30, f'{3*OUT:.1f} flat 展开')]
    xx = X(3 * OUT) + 18
    o += [vd(0, LIP, xx, f'{LIP} lip'), vd(LIP, LIP + SHELF, xx, f'{SHELF} shelf'), vd(yW, yW + SH, xx, f'{SH} walls')]
    o.append(f'<text x="{hcx}" y="{hcy+4}" text-anchor="middle" class="dim">Ø{HOLE}</text>')
    o.append(f'<text x="{X(0)}" y="{Y(yW+SH)+82}" class="sub">Printed side shown (area colour, 1 side) 印刷面（单面专色） · inner face unprinted 内面不印</text>')
    o.append(f'<text x="{X(0)}" y="{Y(yW+SH)+100}" class="sub">— cut 裁切 &#160;&#160; - - crease 压痕 &#160;&#160; Ø{HOLE} hole centred 10 mm from the carton front 孔心距外盒正面10mm</text>')
    return f'<svg viewBox="0 0 760 {int(Y(yW+SH)+120)}" width="760" height="{int(Y(yW+SH)+120)}">{DEFS}{"".join(o)}</svg>'

def steps():
    o = []
    labs = [('1', 'Insert in 放入内卡', 'shelf at the back-top, open side to the window'), ('2', 'Label faces the window 标签朝开窗', 'turn the vial so the name centres in W'), ('3', 'Vial in, close top 放入药瓶，合盖', 'vial drops through the hole to the floor')]
    for i, (n, t, sub) in enumerate(labs):
        x = 20 + i * 330
        o.append(f'<g transform="translate({x},10)"><circle cx="22" cy="22" r="18" fill="{OX}"/><text x="22" y="29" text-anchor="middle" fill="#fff" class="cap">{n}</text>'
                 f'<text x="52" y="20" class="cap">{t}</text><text x="52" y="40" class="sub">{sub}</text></g>')
    return f'<svg viewBox="0 0 1000 70" width="1000" height="70">{"".join(o)}</svg>'

DEFS = f'''<defs><marker id="ar" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#2b2b2b"/></marker>
<marker id="tk" markerWidth="2" markerHeight="10" refX="1" refY="5" orient="auto"><rect width="1.5" height="10" fill="#333"/></marker>
<pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="#e8f6ee"/><line x1="0" y1="0" x2="0" y2="6" stroke="#0E9A58" stroke-width="2"/></pattern>
<radialGradient id="shade" cx="50%" cy="45%" r="70%"><stop offset="60%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity=".22"/></radialGradient></defs>'''

def hero_top():
    s = 16
    return f'<svg viewBox="0 0 360 380" width="380" height="400">{DEFS}{topdown(MET, s)}</svg>'

def colourways():
    o = []
    for i, (n, zh, c) in enumerate(AREAS):
        o.append(f'<div class="cw"><svg viewBox="0 0 230 230" width="150" height="150">{DEFS}{topdown(c, 9.6, False, 8, 8)}</svg><b>{n}</b><span>{zh} · {c}</span></div>')
    return ''.join(o)

rows = [('Insert board 内卡纸板', '300–350 gsm SBS, printed 1 side solid area colour (PMS per area), matte'),
        ('Construction 结构', f'U-cradle (back + 2 sides, {SH} mm tall) + fold-forward shelf {SHELF}×{SHELF} mm with Ø{HOLE} hole + {LIP} mm up-turned lip; no glue'),
        ('Fit 配合', f'Outer {OUT}×{OUT} mm in the 20×20 carton (0.3 mm per side); hole centred on the box ±0.3 mm'),
        ('Window clearance 开窗间隙', f'Shelf underside {SH} mm vs window top {WY1} mm: {SH-WY1:.1f} mm above, behind solid board; nothing of the insert shows in the window'),
        ('Carton change 外盒变更', '400 gsm SBS; inside unprinted white (1-side print); auto-lock bottom; tuck top with friction-lock slits'),
        ('Packing 包装', 'Factory quote both: flat inserts (we pack) or pre-inserted')]
table = ''.join(f'<tr><td>{a}</td><td>{b}</td></tr>' for a, b in rows)

html = f'''<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:Lex;src:url(file://{HERE}/../../zfonts/LexendExa-700.ttf)}}
body{{margin:0;background:#F5F1EA;font-family:Inter,Helvetica,Arial,'Noto Sans CJK SC',sans-serif;color:#1d1d1d;width:1240px}}
.wrap{{padding:44px 48px}} .k{{font:600 12px/1 monospace;letter-spacing:.18em;color:{OX};text-transform:uppercase}}
h1{{font:800 44px/1.05 Inter,Helvetica,Arial,sans-serif;margin:10px 0 10px;letter-spacing:-.02em}} h1:before{{content:'';display:inline-block;width:16px;height:16px;border-radius:50%;background:{OX};margin-right:14px;vertical-align:middle}}
.lead{{font-size:15px;line-height:1.5;max-width:980px;color:#333}} h2{{font:600 12px monospace;letter-spacing:.18em;color:#555;text-transform:uppercase;margin:34px 0 12px}}
.card{{background:#fff;border-radius:6px;padding:18px;box-shadow:0 1px 0 #e5ded2}} .row{{display:flex;gap:20px;align-items:flex-start}}
.cap{{font:700 15px Inter,Helvetica,Arial,'Noto Sans CJK SC',sans-serif;fill:#1d1d1d}} .sub{{font:400 12.5px Inter,Helvetica,Arial,'Noto Sans CJK SC',sans-serif;fill:#555}}
.dim{{font:500 12px monospace;fill:#333}} .dl{{font:700 11px Inter,Helvetica,Arial,'Noto Sans CJK SC',sans-serif}}
.cws{{display:flex;gap:12px;flex-wrap:nowrap}} .cw{{background:#fff;border-radius:6px;padding:10px 6px 12px;text-align:center;width:160px}} .cw b{{display:block;font-size:13px;margin-top:4px}} .cw span{{font:11px monospace;color:#777}}
.caps{{display:flex;justify-content:space-around;font-size:13px;color:#555;margin-top:6px}} .caps b{{display:block;color:#1d1d1d;font-size:14px}} .reveal{{display:flex;gap:24px;align-items:center}} .reveal p{{font-size:14px;line-height:1.55;color:#333;max-width:360px}}
table{{border-collapse:collapse;width:100%;font-size:13.5px}} td{{padding:9px 10px;border-bottom:1px solid #e4ddd0;vertical-align:top}} td:first-child{{font-weight:700;width:250px}}
.note{{margin-top:16px;background:#f6e9eb;border-left:4px solid {OX};padding:12px 16px;font-size:13.5px}}
</style></head><body><div class="wrap">
<div class="k">ZUMA Tides · Window carton · Rev F · insert 内卡 · draft for approval</div>
<h1>The insert: a coloured cradle</h1>
<p class="lead">One die-cut card folds into a U (back + two sides) with a shelf on top. The vial drops through a Ø{HOLE} mm hole in the shelf and stands on the box floor, centred and label-forward in the window. The shelf sits just above the label, behind solid board, so nothing of the insert shows in the window. Open the top and the vial is nested in solid area colour. The carton inside goes back to plain white.</p>
<h2>01 · Exploded 分解图</h2><div class="card">{exploded()}</div>
<div class="row"><div style="flex:0 0 676px"><h2>02 · Section through the front 侧剖面</h2><div class="card">{section()}</div></div>
<div style="flex:1"><h2>03 · Opened, from above 开盒俯视</h2><div class="card reveal"><div>{hero_top()}</div></div>
<p class="lead" style="max-width:380px;margin-top:14px">The reveal: lift the tuck and the Oxblood cap sits in a solid square of the area colour, with a thin white edge of the carton around it.</p></div></div>
<h2>04 · Insert dieline 内卡刀模图 (scale 9:1)</h2><div class="card">{dieline()}</div>
<h2>05 · Six colourways 六色</h2><div class="cws">{colourways()}</div>
<h2>06 · Packing 包装步骤</h2><div class="card">{steps()}</div>
<h2>07 · Spec 规格</h2><div class="card"><table>{table}</table>
<div class="note">Construction choice: a U-cradle with a fold-forward shelf. One piece, no glue, nothing in front of the window; the shelf rests on the side walls and its up-turned lip braces against the carton front, so it can't sag. Shelf height {SH} mm (not 24): the vial body is straight only to 23.5 mm, so the hole grips the body, not the shoulder.</div></div>
</div></body></html>'''
open(os.path.join(HERE, 'insert-board.html'), 'w').write(html)
print('ok')

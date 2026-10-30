# Plain carton v3 option B ("Lightbox + band") - factory pack.
# Same die as the window carton Rev F with NO window: tuck top + auto-lock bottom, inside 20 x 20 x 40 mm, 400 gsm SBS.
# The box carries the ZUMA wordmark alone (no "tides"), 13 mm wide in the Oxblood band. All type outlined.
# Builds: master dieline, 12 per-product art SVGs, 6 inside-print SVGs, look/flat previews (HTML), spec.html.
import os, sys, json, re, base64
HERE = os.path.dirname(os.path.abspath(__file__)); PK = os.path.dirname(HERE)
S = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'
V3 = S + '/plainbox/v3'
sys.path.insert(0, HERE)
from outline import text_path

# v3 art, with three changes: ZUMA-only wordmark, outlined type, bigger wordmark in the band
src = open(V3 + '/base.py').read() + open(V3 + '/gen.py').read().split("exec(open(os.path.join(HERE, 'base.py')).read())")[1]
src = src.split("jobs = {")[0]
src = src.replace("wordmark(W / 2 - 4.2, 35.2, 8.4, SNOW)", "wordmark(W / 2 - 6.5, 34.75, 13.0, SNOW)")
src = src.replace("t(W / 2, 39.05, 2.0 * PT, 'FOR LABORATORY RESEARCH USE ONLY'", "t(W / 2, 39.2, 2.0 * PT, 'FOR LABORATORY RESEARCH USE ONLY'")
src = src.replace("with the zuma tides wordmark in Snow", "with the ZUMA wordmark in Snow")
src = src.replace("OUT = S + '/plainbox/v3'", "OUT = '" + PK + "'")
G = {'__name__': 'plainart'}
exec(compile(src, 'plainart', 'exec'), G)
WMJ = json.load(open('/home/user/MORELLOSIMS/zuma-content/brand/wordmark/tides.json'))
G['WM_VB'] = f"0 0 {WMJ['zuma_w']} 100"; G['WM_PATHS'] = f'<path fill-rule="evenodd" d="{WMJ["zuma"]}"/>'
def t_out(x, y, s, txt, fam='Figtree', w=500, fill='#2A1A1C', anchor='start', ls=0, rot=None, extra=''):
    return text_path(x, y, s, txt, fam, w, fill, anchor, ls, rot)
G['t'] = t_out
front, right, left, back, crest, AREAS, PRODUCTS, OX, SNOW = (G[k] for k in ('front', 'right', 'left', 'back', 'crest', 'AREAS', 'PRODUCTS', 'OX', 'SNOW'))
G['DIRS'] = {'B': G['mk']('B')}

# die geometry: identical to window Rev F (window/final-F/src/gen.py) minus the window
FG = open(S + '/window/final-F/src/gen.py').read()
BOT = re.search(r"BOT = \((.*?)\)\n", FG, re.S).group(1); BOT = ''.join(re.findall(r"'([^']*)'", BOT))
CUTP = ('M17,40 L10,42 L10,78 L17,80 M17,40 L18.5,31 L35.5,31 L37,40 M57,40 L58.5,31 L75.5,31 L77,40 M37,40 L57,40 '
        'M77,40 L77,20 L78,20 Q78,10 81,10 L93,10 Q96,10 96,20 L97,20 L97,40 L97,80 ' + BOT)
CREASEL = [(17,40,17,80),(37,40,37,80),(57,40,57,80),(77,40,77,80),(17,40,37,40),(57,40,77,40),(77,40,97,40),(77,20,97,20),
           (17,80,37,80),(37,80,57,80),(57,80,77,80),(77,80,97,80),(37,80,23,94),(77,80,63,94)]
CRED = '#E30613'; VB = '0 0 107 104'
NS = 'xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"'
def layer(i, label, inner): return f'<g id="{i}" inkscape:label="{label}" inkscape:groupmode="layer">{inner}</g>'
def cut(): return layer('CUT', 'CUT 裁切', f'<path d="{CUTP}" fill="none" stroke="#000" stroke-width="0.25"/>')
def crease(): return layer('CREASE', 'CREASE 压痕', ''.join(f'<line x1="{a}" y1="{b}" x2="{c}" y2="{d}" stroke="{CRED}" stroke-width="0.25" stroke-dasharray="1.2 0.8"/>' for a, b, c, d in CREASEL))
def panel(fn, p, x): return f'<svg x="{x}" y="40" width="20" height="40" viewBox="0 0 20 40" overflow="visible">{fn(p, "B")}</svg>'
def slug(p): return re.sub(r'[^a-z0-9]+', '-', (p[0] + '-' + p[1]).lower()).strip('-')

def art(p):
    name, dose, area, full = p; col = AREAS[area][1]
    pr = [f'<rect x="9" y="39" width="89" height="42" fill="{SNOW}"/>',                       # body + glue flap, 1 mm bleed
          f'<rect x="9" y="74" width="89" height="7" fill="{OX}"/>',                          # the band wraps all round, bleeds 1 mm past the bottom crease
          panel(left, p, 17), panel(front, p, 37), panel(right, p, 57), panel(back, p, 77),
          f'<rect x="9" y="74" width="8" height="7" fill="{OX}"/>',
          f'<rect x="76" y="9" width="22" height="31" fill="{col}"/>']                        # top flap + tongue flood, 1 mm bleed
    # top flap reads upright from the front once folded: rotate its art 180 about the flap centre
    foil = f'<g transform="rotate(180 87 30)">{crest(87 - 4.5, 30 - 4.5 * 0.96, 9, OX)}</g>'
    deb = f'<g transform="rotate(180 87 30)">{crest(87 - 4.5, 30 - 4.5 * 0.96, 9, "none")}</g>'.replace('<g fill="none">', '<g fill="none" stroke="#7A3EB0" stroke-width="2.5">')
    notes = (f'<g font-family="Helvetica, Arial" font-size="1.6" fill="#555">'
             f'<text x="10" y="6">ZUMA plain carton v3 B · {name} {dose} · {AREAS[area][0]} · outside print 外面印刷 · 1:1 mm · bleed 出血 1 mm</text>'
             f'<text x="10" y="100">CMYK 4c + Oxblood #6E1C2A (match) · top crest: Oxblood matte hot foil + deboss 顶盖花徽酒红烫金压凹 · all type outlined 文字已转曲</text></g>')
    return (f'<svg {NS} viewBox="{VB}" width="107mm" height="104mm">'
            + layer('PRINT_CMYK', 'PRINT 印刷 (CMYK + Oxblood)', ''.join(pr))
            + layer('HOT_FOIL', 'HOT_FOIL 烫金 · top crest 9 mm, Oxblood matte foil', foil)
            + layer('DEBOSS', 'DEBOSS 压凹 · same outline as the foil crest, one hit', deb)
            + cut() + crease() + layer('NOTES', 'NOTES 说明 (do not print 不印)', notes) + '</svg>')

def master():
    lab = [(27, 60, 'P1 LEFT 左侧'), (47, 60, 'P2 FRONT 正面'), (67, 60, 'P3 RIGHT 右侧'), (87, 60, 'P4 BACK 背面'), (13.5, 60, 'GLUE 糊口'),
           (87, 30, 'TOP FLAP 顶盖 (hinged on P4)'), (87, 15, 'TONGUE 插舌 10'), (27, 36, 'dust flap 防尘翼'), (67, 36, 'dust flap 防尘翼'),
           (47, 86, 'lock flap 锁底翼'), (27, 86, 'glue flap 糊底翼')]
    t = ''.join(f'<text x="{x}" y="{y}" text-anchor="middle">{s}</text>' for x, y, s in lab)
    dims = ('<g stroke="#0057FF" stroke-width="0.15" fill="#0057FF" font-size="1.5"><line x1="37" y1="84" x2="57" y2="84"/><text x="47" y="83.4" text-anchor="middle" stroke="none">20</text>'
            '<line x1="100" y1="40" x2="100" y2="80"/><text x="101" y="61" stroke="none">40</text></g>')
    return (f'<svg {NS} viewBox="{VB}" width="107mm" height="104mm"><rect x="0" y="0" width="107" height="104" fill="#fff"/>' + cut() + crease()
            + layer('NOTES', 'NOTES 说明', f'<g font-family="Helvetica, Arial" font-size="1.7" fill="#333">{t}</g>{dims}'
            '<text x="10" y="6" font-family="Helvetica, Arial" font-size="1.8" fill="#000">ZUMA plain carton v3 B · MASTER DIELINE 刀模 · inside 内尺寸 20 × 20 × 40 mm · 400 gsm SBS · tuck top + auto-lock bottom · NO window 无开窗 · 1:1 mm</text>'
            '<text x="10" y="100" font-family="Helvetica, Arial" font-size="1.6" fill="#555">Same die as window carton Rev F without the window. Auto-lock drawn schematically: use your standard crash-lock die for a 20 × 20 base. 与开窗盒Rev F同一刀模（去掉窗口）；锁底为示意，请用标准扣底刀模。</text>') + '</svg>')

def inside(area):
    label, col = AREAS[area]
    # seen from the inside the sheet is mirrored: x -> 107 - x
    return (f'<svg {NS} viewBox="{VB}" width="107mm" height="104mm">'
            + layer('PRINT_INSIDE', f'INSIDE 内面 · 100% flood {label} {col}', f'<rect x="9" y="9" width="89" height="86" fill="{col}"/>')
            + f'<g transform="translate(107 0) scale(-1 1)">{cut()}{crease()}</g>'
            + layer('NOTES', 'NOTES', f'<text x="10" y="6" font-family="Helvetica, Arial" font-size="1.8">INSIDE 内面 (mirrored 镜像) · {label} · 100% flood {col} 满版 · bleed past every cut 出血</text>') + '</svg>')

if __name__ == '__main__':
    os.makedirs(PK + '/svg', exist_ok=True)
    open(PK + '/svg/plainB-dieline-master.svg', 'w').write(master())
    for p in PRODUCTS: open(PK + f'/svg/plainB-art-{slug(p)}.svg', 'w').write(art(p))
    for a in AREAS: open(PK + f'/svg/plainB-inside-{a}.svg', 'w').write(inside(a))
    open(PK + '/look-B.html', 'w').write(G['look']('B')); open(PK + '/flat-B.html', 'w').write(G['flat']('B'))
    json.dump([dict(name=p[0], dose=p[1], area=AREAS[p[2]][0], hex=AREAS[p[2]][1], full=p[3], file=f'plainB-art-{slug(p)}.svg') for p in PRODUCTS],
              open(PK + '/versions.json', 'w'), indent=1)
    print('ok', len(PRODUCTS), 'versions')

# ZUMA single-vial carton: writes one HTML atlas per product (4080 x 3300 px at 300 px/cm).
# Atlas: four wall panels left to right (front, right, back, left), 1020 x 2280 each; top and bottom flaps in the row below.
import json, os, re, io, base64, qrcode, qrcode.image.svg
HERE = os.path.dirname(os.path.abspath(__file__)); SP = os.path.dirname(HERE)
cat = json.load(open(os.path.join(SP, 'site3/src/data/catalog.json'))); P = cat['products'] if isinstance(cat, dict) else cat
sym = re.search(r'<symbol id="zuma-logo".*?</symbol>', open(os.path.join(SP, 'site3/src/logo-slot.svg')).read(), re.S).group(0)
TONES = {'metabolic': ('#A3CEFF', '#1F4FD8', '#0B1F5C'), 'tissue': ('#ABE9C3', '#0E9A5B', '#0A3B26'), 'dermal': ('#FFB7C5', '#FF5A1F', '#9E1717'), 'endocrine': ('#FFE97A', '#F5A300', '#5E3C00')}
SUBT = {'bpc-157': 'Pentadecapeptide', 'tb-500': 'Thymosin β4 fragment', 'mots-c': 'Mitochondrial-derived peptide', 'ipamorelin': 'Ghrelin-receptor agonist'}
SITE = 'https://kaleidoscopic-lollipop-7a87dd.netlify.app/'
def qr_svg(url, ink):
    q = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M); q.add_data(url); q.make(fit=True); m = q.get_matrix(); n = len(m)
    d = ''.join(f'M{x} {y}h1v1h-1z' for y, row in enumerate(m) for x, v in enumerate(row) if v)
    return f'<svg viewBox="0 0 {n} {n}" shape-rendering="crispEdges"><path fill="{ink}" d="{d}"/></svg>'
LOGO = '<svg class="{c}" viewBox="0 0 320 100"><use href="#zuma-logo"/></svg>'
PALM = '<svg class="{c}" viewBox="0 0 68 100"><use href="#zuma-logo" width="320" height="100"/></svg>'
for p in P:
    lt, md, dp = TONES[p['area']]; on = dp if p['area'] == 'endocrine' else '#FFFFFF'; sub = dp if p['area'] == 'endocrine' else lt
    lot = p['code'] + '-2610A'; mg = p['sizes'][p['def']][0].upper(); area = p['area'].capitalize() + ' research'
    spec = ''.join(f'<div class="row"><span>{k}</span><b>{v}</b></div>' for k, v in p['spec'].items())
    html = f'''<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:SG;font-weight:100 900;src:url(../fonts/SchibstedGrotesk-800.woff2) format('woff2')}}
@font-face{{font-family:PM;font-weight:500;src:url(../fonts/IBMPlexMono-500.woff2) format('woff2')}}
@font-face{{font-family:PM;font-weight:600;src:url(../fonts/IBMPlexMono-600.woff2) format('woff2')}}
*{{box-sizing:border-box;margin:0}} body{{width:4080px;height:3300px;position:relative;font-family:SG;background:{dp};overflow:hidden}}
.pn{{position:absolute;top:0;width:1020px;height:2280px;overflow:hidden}} .fl{{position:absolute;top:2280px;width:1020px;height:1020px;overflow:hidden}}
.mono{{font-family:PM;font-weight:600;text-transform:uppercase;letter-spacing:.14em}}
/* front */
.front{{left:0;background:{md};color:{on}}}
.front .logo{{position:absolute;left:110px;top:210px;width:800px;height:250px;color:{on}}}
.front .area{{position:absolute;left:0;right:0;top:650px;text-align:center;font-weight:800;font-size:48px;letter-spacing:.2em;text-transform:uppercase;color:{sub}}}
.front .rule{{position:absolute;left:130px;right:130px;top:575px;height:6px;background:{sub};opacity:.85}}
.front .name{{position:absolute;left:40px;right:40px;top:740px;text-align:center;font-weight:900;font-size:250px;line-height:1;letter-spacing:-.035em;white-space:nowrap;height:280px;display:flex;align-items:center;justify-content:center}}
.front .mg{{position:absolute;left:0;right:0;top:1060px;text-align:center;font-weight:900;font-size:150px;letter-spacing:-.01em}}
.front .full{{position:absolute;left:60px;right:60px;top:1290px;text-align:center;font-weight:700;font-size:46px;color:{sub}}}
.front .vial{{position:absolute;left:0;right:0;top:1380px;text-align:center;font-size:32px;color:{sub}}}
.front .band{{position:absolute;left:0;right:0;bottom:0;height:560px;background:{dp};color:#fff;text-align:center;padding-top:130px}}
.front .band b{{display:block;font-weight:900;font-size:86px;letter-spacing:.02em}} .front .band i{{display:block;font-style:normal;font-weight:800;font-size:40px;letter-spacing:.12em;text-transform:uppercase;color:{lt};margin-top:22px}}
.front .band .mono{{display:block;font-size:30px;color:{lt};margin-top:60px;opacity:.9}}
/* right: lot record */
.right{{left:1020px;background:{lt};color:{dp};padding:150px 110px}}
.right .palm{{width:96px;height:141px;color:{dp}}}
.right h3{{font-weight:900;font-size:78px;letter-spacing:-.01em;margin-top:60px}}
.row{{display:flex;justify-content:space-between;gap:20px;border-top:3px solid {dp}33;padding:22px 0;font-size:36px}} .row span{{font-family:PM;font-weight:600;text-transform:uppercase;letter-spacing:.1em;font-size:28px;padding-top:6px}} .row b{{font-weight:800;text-align:right}}
.right .rows{{margin-top:40px}} .right .qr{{width:400px;height:400px;margin-top:70px}} .right .qrc{{font-size:30px;margin-top:22px}}
.right .ruo{{position:absolute;left:110px;right:110px;bottom:120px;font-weight:800;font-size:38px;line-height:1.3}}
/* back */
.back{{left:2040px;background:{dp};color:#fff;padding:170px 110px}}
.back .palm{{width:300px;height:441px;color:{md}}}
.back h3{{font-weight:900;font-size:120px;line-height:.98;letter-spacing:-.03em;margin-top:90px}}
.back p{{font-weight:600;font-size:44px;line-height:1.35;color:{lt};margin-top:50px}}
.back .rows{{margin-top:80px}} .back .row{{border-color:#ffffff33}}
.back .foot{{position:absolute;left:110px;right:110px;bottom:120px;display:flex;justify-content:space-between;align-items:end}} .back .foot .logo{{width:330px;height:103px;color:#fff}} .back .foot .mono{{font-size:28px;color:{lt}}}
/* left: the name, standing */
.left{{left:3060px;background:{md};color:{on}}}
.left .v{{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%) rotate(-90deg);white-space:nowrap;font-weight:900;font-size:300px;letter-spacing:-.04em}}
.left .logo{{position:absolute;left:180px;bottom:150px;width:660px;height:206px;color:{sub}}}
.left .mono{{position:absolute;left:0;right:0;top:150px;text-align:center;font-size:34px;color:{sub}}}
/* flaps */
.top{{left:0;background:{dp}}} .top .palm{{position:absolute;left:390px;top:290px;width:240px;height:353px;color:{md}}} .top .mono{{position:absolute;left:0;right:0;bottom:120px;text-align:center;font-size:30px;color:{lt}}}
.bot{{left:1020px;background:{lt};color:{dp}}} .bot .mono{{position:absolute;left:0;right:0;top:470px;text-align:center;font-size:34px}}
</style></head><body>
<svg width="0" height="0" style="position:absolute">{sym}</svg>
<section class="pn front">{LOGO.format(c='logo')}<div class="rule"></div><div class="area">{area}</div><div class="name" data-fit="940">{p['name']}</div><div class="mg">{mg}</div>
<div class="full">{SUBT.get(p['slug'], p['full'])}</div><div class="vial mono">Lyophilized powder · 1 vial</div>
<div class="band"><b>RESEARCH USE ONLY</b><i>Not for human or veterinary use</i><span class="mono">Lot {lot} · Store at −20 °C</span></div></section>
<section class="pn right">{PALM.format(c='palm')}<h3>Lot record</h3><div class="rows">
<div class="row"><span>Lot</span><b>{lot}</b></div><div class="row"><span>Filled</span><b>10.10.2026</b></div><div class="row"><span>Fill</span><b>{p['sizes'][p['def']][0]}</b></div><div class="row"><span>Storage</span><b>−20 °C, dark</b></div></div>
<div class="qr">{qr_svg(SITE + p['slug'] + '.html', dp)}</div><div class="qrc mono">Scan for this lot's report</div>
<p class="ruo">For laboratory research use only. Not for human or veterinary use.</p></section>
<section class="pn back">{PALM.format(c='palm')}<h3>Every lot tested.</h3><p>HPLC for purity, mass spectrometry for identity. The report for this lot is published before it ships.</p>
<div class="rows">{spec}</div><div class="foot">{LOGO.format(c='logo')}<span class="mono">Est. 2026</span></div></section>
<section class="pn left"><div class="mono">{area}</div><div class="v" data-fitv="1900">{p['name']}</div>{LOGO.format(c='logo')}</section>
<section class="fl top">{PALM.format(c='palm')}<div class="mono">ZUMA · {p['name']}</div></section>
<section class="fl bot"><div class="mono">Research use only</div></section>
<script>document.fonts.ready.then(()=>{{document.querySelectorAll('[data-fit]').forEach(e=>{{let s=250;while(e.scrollWidth>+e.dataset.fit&&s>60){{s-=4;e.style.fontSize=s+'px'}}e.style.left=e.style.right='0';}});
document.querySelectorAll('[data-fitv]').forEach(e=>{{let s=300;while(e.getBoundingClientRect().height>+e.dataset.fitv&&s>60){{s-=6;e.style.fontSize=s+'px'}}}});document.body.dataset.ready=1}});</script>
</body></html>'''
    open(os.path.join(HERE, 'html', f"carton-{p['no']}.html"), 'w').write(html)
print('ok', len(P))

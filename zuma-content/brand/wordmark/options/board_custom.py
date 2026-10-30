import json, os
H = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(H, '..', 'tides_custom.json')))
OX, SN = '#6E1C2A', '#FCFBF8'
zw, AS = D['zuma_w'], D['asc']
def lock(o, fill):
    w = o['x'] + o['w']
    return f'<svg viewBox="-10 {-AS-12} {w+20} {100+AS+24}"><path fill="{fill}" fill-rule="evenodd" d="{D["zuma"]}"/><path transform="translate({o["x"]} 0)" fill="{fill}" fill-rule="evenodd" d="{o["d"]}"/></svg>'
def solo(o, fill):
    return f'<svg viewBox="-8 {-AS-10} {o["w"]+16} {100+AS+20}"><path fill="{fill}" fill-rule="evenodd" d="{o["d"]}"/></svg>'
rows = []
for k, o in D['opts'].items():
    rows.append(f'''<div class="row"><div class="lab"><b>{k}</b><span>{o["note"]}</span></div>
<div class="cell snow big">{solo(o, OX)}</div><div class="cell snow">{lock(o, OX)}</div><div class="cell ox">{lock(o, SN)}</div>
<div class="cell small snow"><div style="height:30px">{lock(o, OX)}</div><em>8 mm</em></div></div>''')
html = f'''<!doctype html><meta charset=utf8><style>
body{{margin:0;background:#EFEAE2;font:14px/1.35 -apple-system,Helvetica,Arial;color:#222;padding:30px;width:1940px}}
h1{{font-size:22px;margin:0 0 4px}} p{{margin:0 0 20px;color:#555}}
.row{{display:grid;grid-template-columns:170px 300px 1fr 1fr 190px;gap:14px;margin-bottom:14px}}
.lab b{{font-size:30px;display:block}} .lab span{{color:#555}}
.cell{{display:flex;align-items:center;justify-content:center;padding:22px 26px;border-radius:6px}}
.cell svg{{width:100%;height:auto;max-height:130px}} .big svg{{max-height:150px}} .snow{{background:{SN}}} .ox{{background:{OX}}}
.small{{flex-direction:column;align-items:flex-start}} .small svg{{height:100%;width:auto}} .small em{{font-size:11px;color:#888;margin-top:6px}}
</style><h1>zuma tides — round 2: custom “tides”</h1><p>No tails. Each design spaced optically (measured gaps, not fixed numbers). Bowls use zuma's squared-round shape, drawn thin and slanted 11°.</p>{"".join(rows)}'''
open(os.path.join(H, 'board_custom.html'), 'w').write(html)

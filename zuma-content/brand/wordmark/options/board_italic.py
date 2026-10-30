import json, os
D = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'tides_italic.json')))
OX, SN = '#6E1C2A', '#FCFBF8'
zw, AS = D['zuma_w'], D['asc']
def lock(o, fill):
    if o.get('stack'):
        w = max(zw, o['w']); vb = f"-10 {-AS-10} {w+20} {100+AS+100+60}"
        return f'<svg viewBox="{vb}"><path fill="{fill}" fill-rule="evenodd" d="{D["zuma"]}"/><g transform="translate({zw-o["w"]} {AS+100+14})"><path fill="{fill}" d="{o["d"]}"/></g></svg>', w
    sp = 40; w = zw + sp + o['w']
    return f'<svg viewBox="-10 {-AS-10} {w+20} {100+AS+20}"><path fill="{fill}" fill-rule="evenodd" d="{D["zuma"]}"/><g transform="translate({zw+sp} 0)"><path fill="{fill}" d="{o["d"]}"/></g></svg>', w
rows = []
for k, o in D['opts'].items():
    a, w = lock(o, OX); b, _ = lock(o, SN)
    # 8 mm tall lockup at ~96 px/in screen = ~30 px x-height+asc
    rows.append(f'''<div class="row"><div class="lab"><b>{k}</b><span>{o["note"]}</span></div>
<div class="cell snow">{a}</div><div class="cell ox">{b}</div>
<div class="cell small snow"><div style="height:30px">{a}</div><div style="height:30px;margin-top:10px;background:{OX};padding:6px">{b}</div><em>8 mm</em></div></div>''')
html = f'''<!doctype html><meta charset=utf8><style>
body{{margin:0;background:#EFEAE2;font:14px/1.3 -apple-system,Helvetica,Arial;color:#222;padding:30px;width:1740px}}
h1{{font-size:22px;margin:0 0 4px}} p{{margin:0 0 20px;color:#555}}
.row{{display:grid;grid-template-columns:150px 1fr 1fr 230px;gap:14px;margin-bottom:14px;align-items:stretch}}
.lab b{{font-size:30px;display:block}} .lab span{{color:#555}}
.cell{{display:flex;align-items:center;justify-content:center;padding:26px 30px;border-radius:6px}}
.cell svg{{width:100%;height:auto;max-height:150px}} .snow{{background:{SN}}} .ox{{background:{OX}}}
.small{{flex-direction:column;align-items:flex-start}} .small svg{{height:100%;width:auto}} .small em{{font-size:11px;color:#888;margin-top:6px}}
</style><h1>zuma tides — skinny italic “tides”</h1><p>Custom monoline italic, flat-cut terminals, exit strokes on t · i · d. ZUMA unchanged. Pick a letter (or mix: e.g. “B weight at D slant”).</p>{"".join(rows)}'''
open(os.path.join(os.path.dirname(__file__), 'board_italic.html'), 'w').write(html)

# Top flap options side by side, three areas each: current (Oxblood foil on area colour), A (Snow top + Oxblood foil crest),
# B (area colour + crest knocked out to white board)
import os, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location('pack', os.path.join(HERE, 'pack.py')); P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
crest, OX, SNOW, AREAS = P.crest, P.OX, P.SNOW, P.AREAS
OPTS = [('Now: Oxblood foil on the area colour', lambda c: f'<rect width="20" height="20" fill="{c}"/>' + crest(5.5, 5.7, 9, OX)),
        ('A: Snow top, Oxblood foil crest (matches the window box)', lambda c: f'<rect width="20" height="20" fill="{SNOW}"/>' + crest(5.5, 5.7, 9, OX)),
        ('B: area colour, crest knocked out to white (no foil)', lambda c: f'<rect width="20" height="20" fill="{c}"/>' + crest(5.5, 5.7, 9, SNOW))]
cells = []
for title, f in OPTS:
    tiles = ''.join(f'<svg viewBox="0 0 20 20" width="300" height="300" style="box-shadow:0 2px 10px rgba(0,0,0,.15)">{f(AREAS[a][1])}</svg>' for a in ('metabolic', 'tissue', 'dermal'))
    cells.append(f'<div style="margin-bottom:34px"><div style="font:600 22px Helvetica;margin-bottom:12px;color:#2a1a1c">{title}</div><div style="display:flex;gap:26px">{tiles}</div></div>')
open('/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad/plainbox/top-opts/top-options.html', 'w').write(
    f'<!doctype html><body style="margin:0;padding:40px;background:#EDE8E0;width:1050px">{"".join(cells)}</body>')

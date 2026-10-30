# Export the v3 B faces of three products as standalone SVGs (60 px/mm when rasterised) for the 3D render.
import os, sys
sys.argv = ['faces']
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import importlib.util
spec = importlib.util.spec_from_file_location('pack', os.path.join(HERE, 'pack.py')); P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
OUT = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad/plainbox/texB'
PR = {p[0]: p for p in P.PRODUCTS}
for no, name in (('01', 'RT-3'), ('09', 'BPC+TB'), ('05', 'GHK-Cu')):
    p = PR[name]
    for side, fn, h in (('front', P.front, 40), ('left', P.left, 40), ('right', P.right, 40), ('back', P.back, 40)):
        open(f'{OUT}/{side}-{no}.svg', 'w').write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 {h}" width="1200" height="{h*60}">{fn(p, "B")}</svg>')
    open(f'{OUT}/top-{no}.svg', 'w').write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" width="1200" height="1200"><g transform="rotate(180 10 10)">{P.G["top"](p)}</g></svg>')
print('faces ok')

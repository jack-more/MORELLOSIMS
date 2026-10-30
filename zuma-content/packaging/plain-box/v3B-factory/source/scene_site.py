# Site stills of the plain carton v3 B, built on scene_plainB.py (its set-up only, not its shots):
#   ZNO=NN  one closed box of product NN (catalog number), 3:4 for the product page gallery
#   ZSET=1  four closed boxes in a row (Metabolic, Tissue, Dermal, Neuro) for the build-a-set page
# bpyenv/bin/python plainbox/build/scene_site.py OUT W H SAMPLES
import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__)); PB = os.path.dirname(HERE)
SRC = os.path.join(HERE, 'scene_plainB.py')
src = open(SRC).read(); src = src[:src.index("if os.environ.get('ZCLOSED')")]
G = {'__file__': SRC, '__name__': '__main__'}
exec(compile(src, SRC, 'exec'), G)
globals().update(G)

# inside flood colour for every catalog number (scene_w6 only knows 01, 05 and 09)
HEX = {'metabolic': '#1F4FD0', 'tissue': '#0E9A58', 'dermal': '#FF5A1F', 'endocrine': '#D08000', 'neuro': '#6E3FD8', 'supplies': '#4E6077'}
AREA_OF = {'01': 'metabolic', '02': 'metabolic', '03': 'supplies', '04': 'endocrine', '05': 'dermal', '06': 'metabolic',
           '07': 'endocrine', '08': 'metabolic', '09': 'tissue', '10': 'dermal', '11': 'neuro', '12': 'neuro'}
for k, a in AREA_OF.items(): G['AREA'][k] = (HEX[a], HEX[a])
# the vial is hidden inside a closed box; products without a vial label texture borrow one
_vial = G['vial']
G['vial'] = lambda no: _vial(no if os.path.exists(os.path.join(WT, f'vial-label-{no}.png')) else '01')

def lights():
    world(0.22)
    area('soft', 60, (40, -50, 40), 5200, look=(0, 0, 2), col=(1.0, 0.97, 0.93))
    area('fill', 40, (-30, -60, 12), 900, look=(0, 0, 2)); rake()

if os.environ.get('ZSET'):
    for k, (no, x) in enumerate((('01', -4.5), ('09', -1.5), ('05', 1.5), ('11', 4.5))):
        boxB(no, (x, 0.3 * (k % 2), 0), -14, 0, closed=True)
    lights()
    cl = Vector((-9.0, -26.0, 12.5)); look_ = Vector((0.0, 0.3, 2.1))
    camera(tuple(cl), tuple(look_), 90, fstop=11, focus=(look_ - cl).length)
    render(NSAMP, RW, RH, exposure=0.7); raise SystemExit

no = os.environ.get('ZNO', '01')
boxB(no, (0, 0, 0), float(os.environ.get('ZROT', '-14')), 0, closed=True)
lights()
cl = Vector((-7.6, -12.6, 8.6)); look_ = Vector((0.0, 0.0, 2.05))
camera(tuple(cl), tuple(look_), 90, fstop=11, focus=(look_ - cl).length)
render(NSAMP, RW, RH, exposure=0.7)

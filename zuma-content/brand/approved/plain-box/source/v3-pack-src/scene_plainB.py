# ZUMA plain carton v3 B render: the window box Rev F scene (scene_w6 + geomF.json) with NO window, every outside face
# printed from the v3 B artwork (../texB/<side>-NN.png), inside flooded in the area colour, white U-cradle insert.
# Default = hero (one open, two closed); ZCLOSED=1 one closed box. bpyenv/bin/python plainbox/build/scene_plainB.py OUT W H SAMPLES
import os, sys, math
PB = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); TB = os.path.join(PB, 'texB')
W6 = os.path.join(os.path.dirname(PB), 'window', 'build', 'scene_w6.py')
src = open(W6).read()
src = src[:src.index("if os.environ.get('ZVERIFY')")]
src = src.replace("'geomE.json'", "'geomF.json'")
src = src.replace("WINS = [(w['x0'], w['y0'], w['x1'], w['y1']) for w in GJ['windows']]", "WINS = []          # plain box: no window")
assert "WINS = []" in src and "'geomF.json'" in src
G = {'__file__': W6, '__name__': '__main__'}
exec(compile(src, W6, 'exec'), G)
globals().update(G)

def print_m(path):     # printed board: the face artwork, matte aqueous, fine paper tooth
    m, b = mat(os.path.basename(path), **{'Roughness': 0.6}); nt = m.node_tree
    tx = tnode(nt, path, 'sRGB', ext='CLIP'); L(nt, tx.outputs['Color'], b.inputs['Base Color'])
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 900; nz.inputs['Detail'].default_value = 6
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.25; bp.inputs['Distance'].default_value = 0.01
    L(nt, nz.outputs['Fac'], bp.inputs['Height']); L(nt, bp.outputs['Normal'], b.inputs['Normal'])
    return m
G['decal_m'] = lambda no: print_m(os.path.join(TB, f'front-{no}.png'))

def face(name, m, loc, rot, size, parent):
    bpy.ops.mesh.primitive_plane_add(size=1); o = bpy.context.active_object; o.name = name
    o.scale = (size[0], size[1], 1); o.rotation_euler = rot; o.location = loc
    o.data.materials.append(m); o.visible_shadow = False; o.parent = parent; return o

INS = GJ['insert']
INS_T = INS['thickness'] / 10; INS_W = INS['outside'] / 10; INS_H = INS['walls_h'] / 10
SHELF_D = INS['shelf'] / 10; HOLE_R = INS['hole'] / 20; LIP = INS['lip'] / 10
INSM, _b = mat('insertwhite', **{'Base Color': lin('#F2EFE8'), 'Roughness': 0.8})

def slab(name, sx, sy, sz, loc, m):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.active_object; o.name = name; o.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bv = o.modifiers.new('bv', 'BEVEL'); bv.width = 0.006; bv.segments = 1
    o.data.materials.append(m); return o

def cradle(root):
    m = INSM; z0 = TH; hw = INS_W / 2; parts = []
    by = BD / 2 - TH - INS_T / 2
    yc = by + INS_T / 2 - hw
    parts.append(slab('ins_back', INS_W, INS_T, INS_H, (0, by, z0 + INS_H / 2), m))
    for s in (-1, 1):
        parts.append(slab('ins_side', INS_T, INS_W, INS_H, (s * (hw - INS_T / 2), yc, z0 + INS_H / 2), m))
    sy0 = by - INS_T / 2; sy1 = sy0 - SHELF_D; sz = z0 + INS_H + INS_T / 2
    sh = slab('ins_shelf', INS_W - 2 * INS_T, SHELF_D, INS_T, (0, (sy0 + sy1) / 2, sz), m)
    bpy.ops.mesh.primitive_cylinder_add(radius=HOLE_R, depth=0.4, vertices=96, location=(0, 0, sz)); hc = bpy.context.active_object; hc.hide_render = True
    md = sh.modifiers.new('hole', 'BOOLEAN'); md.operation = 'DIFFERENCE'; md.object = hc; md.solver = 'EXACT'
    sh.modifiers.move(len(sh.modifiers) - 1, 0)
    parts += [sh, hc, slab('ins_lip', INS_W - 2 * INS_T, INS_T, LIP, (0, sy1 + INS_T / 2, sz + LIP / 2), m)]
    for p in parts: p.parent = root

E = 0.0015   # print planes sit just proud of the board
def boxB(no, loc, rotz, vrot, **kw):
    r = carton(no, loc, rotz, vxy=(0.0, 0.0), vrot=vrot, **kw); cradle(r)
    face('left' + no, print_m(os.path.join(TB, f'left-{no}.png')), (-BW / 2 - E, 0, BH / 2), (math.radians(90), 0, math.radians(-90)), (BD, BH), r)
    face('right' + no, print_m(os.path.join(TB, f'right-{no}.png')), (BW / 2 + E, 0, BH / 2), (math.radians(90), 0, math.radians(90)), (BD, BH), r)
    face('back' + no, print_m(os.path.join(TB, f'back-{no}.png')), (0, BD / 2 + E, BH / 2), (math.radians(90), 0, math.radians(180)), (BW, BH), r)
    fl = bpy.data.objects.get('flap' + no)
    if fl is not None:   # area-colour top with the Oxblood crest, on the flap's outer face (flap local: hinge at y=0, top at z=TH)
        face('top' + no, print_m(os.path.join(TB, f'top-{no}.png')), (0, BD / 2, TH + E), (0, 0, 0), (BW, BD), fl)
    return r

def rake(energy=6.5, d=(0.82, -0.50, -0.34)):
    sun = bpy.data.lights.new('rake', 'SUN'); sun.energy = energy; sun.angle = math.radians(0.6); sun.color = (1.0, 0.86, 0.68)
    so = bpy.data.objects.new('rake', sun); sc.collection.objects.link(so)
    so.rotation_euler = (-Vector(d).normalized()).to_track_quat('Z', 'Y').to_euler()

if os.environ.get('ZCLOSED'):
    boxB('01', (0, 0, 0), 0, -14, closed=True)
    world(0.22)
    area('soft', 60, (40, -50, 40), 5200, look=(0, 0, 2), col=(1.0, 0.97, 0.93))
    area('fill', 40, (-30, -60, 12), 900, look=(0, 0, 2)); rake()
    cl = Vector((-7.0, -9.4, 10.6)); look_ = Vector((0.0, 0.0, 2.15))
    camera(tuple(cl), tuple(look_), 90, fstop=11, focus=(look_ - cl).length)
    render(NSAMP, RW, RH, exposure=0.7); raise SystemExit

if os.environ.get('ZOPEN'):   # one open box from above: the area-colour inside, white insert, vial cap
    boxB('01', (0, 0, 0), 0, -6, open_top=True)
    fl = bpy.data.objects['flap01']; fl.rotation_euler = (math.radians(192), 0, math.radians(180))
    bpy.data.objects['tuck01'].rotation_euler = (0, 0, 0)
    world(0.35)
    area('soft', 60, (30, -45, 45), 4200, look=(0, 0, 2.5), col=(1.0, 0.97, 0.93))
    area('key', 10, (0.5, -1.0, 30), 4500, look=(0, 0, 2.0))
    area('fill', 40, (-30, -50, 15), 700, look=(0, 0, 2)); rake(4.0, (0.82, -0.50, -0.55))
    look_ = Vector((0.0, 0.45, 3.0)); el = math.radians(62); az = math.radians(-24); dist = 12.0
    cl = look_ + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * dist
    camera(tuple(cl), tuple(look_), 68, fstop=16, focus=dist)
    render(NSAMP, RW, RH, exposure=0.7); raise SystemExit

# hero: 01 open (area-colour inside + white insert + vial lifted through the shelf hole), 09 + 05 closed
boxB('01', (-4.05, -0.75, 0), 24, float(os.environ.get('ZV1', '14')), vial_up=0.5, open_top=True)
boxB('09', (0.35, 0.9, 0), 26, 0, closed=True)
boxB('05', (4.1, -0.2, 0), 18, 0, closed=True)
world(0.22)
area('soft', 60, (40, -50, 40), 5200, look=(0, 0, 2), col=(1.0, 0.97, 0.93))
area('fill', 40, (-30, -60, 12), 900, look=(0, 0, 2)); rake()
cl = Vector((-12.5, -27.5, float(os.environ.get('ZCAMZ', '13.5')))); look_ = Vector((0.2, 0.2, 2.25))
camera(tuple(cl), tuple(look_), 90, fstop=11, focus=(Vector((-1.6, -0.6, 2.2)) - cl).length)
render(NSAMP, RW, RH, exposure=0.7)

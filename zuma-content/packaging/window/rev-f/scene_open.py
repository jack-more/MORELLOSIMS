# Opened-box comparison (Rev E.2 + Rev F insert): one RT-3 box, top flap folded fully back, looking down into it.
# ZINSIDE=colour|white picks the carton's inside print; the insert is always printed in the area colour. Panels are flat (no ribs).
# bpyenv/bin/python window/build/scene_open.py OUT W H SAMPLES
import os, sys, math
WB = os.path.dirname(os.path.abspath(__file__)); W6 = os.path.join(WB, 'scene_w6.py')
src = open(W6).read()
src = src[:src.index("if os.environ.get('ZVERIFY')")]
# flat printed panels: no rib bump
src = src.replace("bp.inputs['Strength'].default_value = 1.0; bp.inputs['Distance'].default_value = 0.012",
                  "bp.inputs['Strength'].default_value = 0.0; bp.inputs['Distance'].default_value = 0.012")
# inside print: area colour or plain white board
src = src.replace("m, b = mat('inside' + no, **{'Base Color': lin(mid), 'Roughness': 0.85}); return m",
                  "m, b = mat('inside' + no, **{'Base Color': lin('#F4F1EA' if os.environ.get('ZINSIDE') == 'white' else mid), 'Roughness': 0.85}); return m")
G = {'__file__': W6, '__name__': '__main__'}
exec(compile(src, W6, 'exec'), G)
globals().update(G)

INS_T = 0.04                        # insert board, cm (~0.4 mm)
INS_W = 1.94; INS_H = 2.30          # outside 19.4 mm square, walls 23 mm
SHELF_D = 1.85; HOLE_R = 0.825; LIP = 0.25

def insert_m(no):
    mid, tint = AREA[no]
    m, b = mat('insert' + no, **{'Base Color': lin(mid), 'Roughness': 0.8}); return m

def slab(name, sx, sy, sz, loc, m):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.active_object; o.name = name; o.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bv = o.modifiers.new('bv', 'BEVEL'); bv.width = 0.006; bv.segments = 1
    o.data.materials.append(m); return o

def cradle(no):
    m = insert_m(no); z0 = TH; hw = INS_W / 2; parts = []
    by = hw - INS_T / 2                                                    # back wall (+y = back)
    parts.append(slab('ins_back', INS_W, INS_T, INS_H, (0, by, z0 + INS_H / 2), m))
    for s in (-1, 1):
        parts.append(slab('ins_side', INS_T, INS_W, INS_H, (s * (hw - INS_T / 2), 0, z0 + INS_H / 2), m))
    # shelf: folds forward from the back wall top, 18.5 mm deep, with a Ø16.5 hole centred in the box
    sy0 = hw; sy1 = hw - SHELF_D; sz = z0 + INS_H + INS_T / 2
    sh = slab('ins_shelf', INS_W - 2 * INS_T, SHELF_D, INS_T, (0, (sy0 + sy1) / 2, sz), m)
    bpy.ops.mesh.primitive_cylinder_add(radius=HOLE_R, depth=0.4, vertices=96, location=(0, 0, sz)); hc = bpy.context.active_object; hc.hide_render = True
    md = sh.modifiers.new('hole', 'BOOLEAN'); md.operation = 'DIFFERENCE'; md.object = hc; md.solver = 'EXACT'
    sh.modifiers.move(len(sh.modifiers) - 1, 0)
    parts.append(sh); parts.append(hc)
    # 2.5 mm lip turned up along the shelf front edge
    parts.append(slab('ins_lip', INS_W - 2 * INS_T, INS_T, LIP, (0, sy1 + INS_T / 2, sz + LIP / 2), m))
    return parts

root = carton('01', (0, 0, 0), 0, open_top=True, vxy=(0.0, 0.0), vrot=-6)
for p in cradle('01'): p.parent = root
# fold the top flap fully back (inner face up, tipping slightly down behind the box)
fl = [o for o in sc.objects if o.name.startswith('flap01')][0]
fl.rotation_euler = (math.radians(192), 0, math.radians(180))
tk = [o for o in sc.objects if o.name.startswith('tuck01')][0]; tk.rotation_euler = (0, 0, 0)

world(0.35)
area('soft', 60, (30, -45, 45), 4200, look=(0, 0, 2.5), col=(1.0, 0.97, 0.93))
area('key', 14, (2, -3, 30), 1500, look=(0, 0, 2.5))                      # gentle key from above, so the shelf reads
area('fill', 40, (-30, -50, 15), 700, look=(0, 0, 2))
sun = bpy.data.lights.new('rake', 'SUN'); sun.energy = 4.0; sun.angle = math.radians(1.5); sun.color = (1.0, 0.88, 0.72)
so = bpy.data.objects.new('rake', sun); sc.collection.objects.link(so)
d = Vector((0.82, -0.50, -0.55)).normalized(); so.rotation_euler = (-d).to_track_quat('Z', 'Y').to_euler()
look_ = Vector((0.0, 0.45, 3.0)); el = math.radians(60); az = math.radians(-16); dist = 12.8
cl = look_ + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * dist
camera(tuple(cl), tuple(look_), 68, fstop=16, focus=dist)
render(NSAMP, RW, RH, exposure=0.55)

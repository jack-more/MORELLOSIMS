# A real six-egg carton in molded pulp: rounded-square cups, cone posts, domed lid with a flat label strip, hinge and latch tab.
import os, sys, math, json
import numpy as np
import bpy, mathutils
from PIL import Image, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__)); E = os.environ.get; G = lambda k, d: float(E(k, d))
OUT = E('OUT', os.path.join(HERE, 'carton2.png')); RX, RY = int(E('RX', '960')), int(E('RY', '640')); SAMPLES = int(E('SAMPLES', '24'))
MM = 0.001
bpy.ops.wm.read_factory_settings(use_empty=True); scene = bpy.context.scene
def s2l(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)
def mat(name, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    for k, v in kw.items():
        if k in b.inputs: b.inputs[k].default_value = v
    return m, b
def skinmat(name, lin):
    m, b = mat(name, **{'Base Color': lin, 'Roughness': 0.62, 'Sheen Weight': 0.55, 'Sheen Roughness': 0.35, 'Sheen Tint': (1, 1, 1, 1),
                       'Subsurface Weight': 0.06, 'Subsurface Scale': 0.002, 'Specular IOR Level': 0.35})
    return m
lin = lambda n: tuple(map(float, json.load(open(os.path.join(HERE, f'cm_{n}.json')))['SKIN_LIN'].split(','))) + (1.0,)
SK = {'sky': lin('sky'), 'rose': lin('rose'), 'sage': lin('sage'), 'cloud': lin('cloud'), 'cobalt': s2l('#1A5FD6')}
def carved_metal(name, base, ox, rough, aniso=0.0):
    m, b = mat(name, **{'Base Color': base, 'Metallic': 1.0, 'Roughness': rough, 'Anisotropic': aniso})
    t = m.node_tree
    if aniso > 0:
        tg = t.nodes.new('ShaderNodeTangent'); tg.direction_type = 'RADIAL'; tg.axis = 'Z'; t.links.new(tg.outputs['Tangent'], b.inputs['Tangent'])
    at = t.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'carve'
    cr = t.nodes.new('ShaderNodeMapRange'); t.links.new(at.outputs['Fac'], cr.inputs['Value']); cr.inputs['From Min'].default_value = 0.25; cr.inputs['From Max'].default_value = 0.6
    mc = t.nodes.new('ShaderNodeMix'); mc.data_type = 'RGBA'; t.links.new(cr.outputs['Result'], mc.inputs['Factor'])
    mc.inputs[6].default_value = base; mc.inputs[7].default_value = ox; t.links.new(mc.outputs[2], b.inputs['Base Color'])
    mr = t.nodes.new('ShaderNodeMapRange'); t.links.new(cr.outputs['Result'], mr.inputs['Value']); mr.inputs['To Min'].default_value = rough; mr.inputs['To Max'].default_value = 0.62
    t.links.new(mr.outputs['Result'], b.inputs['Roughness'])
    return m
head_m = carved_metal('head', (0.96, 0.92, 0.86, 1), (0.018, 0.018, 0.02, 1), 0.1)
body_brushed = carved_metal('body_brushed', (0.93, 0.92, 0.9, 1), (0.3, 0.3, 0.32, 1), G('BRUSH_R', '0.24'), G('ANISO', '0.9'))
blackm, _ = mat('slot', **{'Base Color': (0.01, 0.01, 0.01, 1), 'Roughness': 0.4})
threadm, _ = mat('thread', **{'Base Color': (0.80, 0.78, 0.75, 1), 'Metallic': 1.0, 'Roughness': 0.32})

# ---------------- egg geometry from the model, and where it seats ----------------
with bpy.data.libraries.load(os.path.join(HERE, 'mk', E('EGGFILE', 'egg_c.blend'))) as (src, dst):
    dst.objects = [n for n in src.objects if n in ('skin', 'head', 'slot', 'thread', 'sleeve_core', 'collar')]
lib = {o.name: o for o in dst.objects}
sv = np.empty(len(lib['skin'].data.vertices) * 3, np.float32); lib['skin'].data.vertices.foreach_get('co', sv); sv = sv.reshape(-1, 3) / MM
er = np.hypot(sv[:, 0], sv[:, 1]); ez = sv[:, 2]
EGG_TOP = 86.6
# ---------------- carton dimensions ----------------
P = 76.0; CW, CD = 3, 2
TW, TD = CW * P + 12, CD * P + 12
H = G('CUP_H', '34')                                     # rim height
RO, RB, ZB = 34.5, 17.0, 3.0                             # cup: half-opening at rim, half-floor, floor height
cells = [((i - 1) * P, (j - 0.5) * P) for j in range(CD) for i in range(CW)]
def sq(dx, dy, p=3.2): return (np.abs(dx) ** p + np.abs(dy) ** p) ** (1 / p)
def cup_r(z): return RB + (RO - RB) * np.clip((z - ZB) / (H - ZB), 0, 1) ** 0.8
# seat: lowest offset s where the egg touches the cup wall
zs = np.linspace(0, 40, 400); best = None
for s in np.linspace(0, 30, 301):
    zz = ez + s; m = zz < H
    if not m.any(): continue
    if np.all(er[m] <= cup_r(zz[m]) + 1e-6) and np.all(zz >= ZB): best = s; break
SEAT = best if best is not None else 10.0
print('egg seat', round(SEAT, 2))
LID_H = SEAT + EGG_TOP - H + G('CLEAR', '4')
def rrect(x, y, w, d, r):
    qx = np.abs(x) - (w / 2 - r); qy = np.abs(y) - (d / 2 - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
def shell(name, Z, X, Y, keep, thick, m_):
    ny, nx = Z.shape
    V = np.stack([X, Y, Z], -1).reshape(-1, 3) * MM
    idx = np.arange(nx * ny).reshape(ny, nx)
    F = np.stack([idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]], -1).reshape(-1, 4)
    F = F[keep.reshape(-1)[F].all(1)]
    me = bpy.data.meshes.new(name); me.from_pydata(V.tolist(), [], F.tolist()); me.update(); me.shade_smooth()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob); me.materials.append(m_)
    so = ob.modifiers.new('t', 'SOLIDIFY'); so.thickness = thick * MM; so.offset = -1
    return ob
# pulp material: matte, fibrous
PULP = s2l(E('PULP', '#E9E4DA'))
pulp, pb = mat('pulp', **{'Base Color': PULP, 'Roughness': 0.95, 'Specular IOR Level': 0.15, 'Sheen Weight': 0.4, 'Sheen Roughness': 0.6,
                          'Subsurface Weight': 0.05, 'Subsurface Scale': 0.002})
t = pulp.node_tree; tc = t.nodes.new('ShaderNodeTexCoord')
n1 = t.nodes.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = 900; n1.inputs['Detail'].default_value = 8; t.links.new(tc.outputs['Object'], n1.inputs['Vector'])
n2 = t.nodes.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 90; n2.inputs['Detail'].default_value = 4; t.links.new(tc.outputs['Object'], n2.inputs['Vector'])
mx = t.nodes.new('ShaderNodeMath'); mx.operation = 'ADD'; t.links.new(n1.outputs['Fac'], mx.inputs[0]); t.links.new(n2.outputs['Fac'], mx.inputs[1])
bp = t.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.25; bp.inputs['Distance'].default_value = 0.0004
t.links.new(mx.outputs[0], bp.inputs['Height']); t.links.new(bp.outputs['Normal'], pb.inputs['Normal'])
cv = t.nodes.new('ShaderNodeMix'); cv.data_type = 'RGBA'; t.links.new(n2.outputs['Fac'], cv.inputs['Factor'])
cv.inputs[6].default_value = tuple(c * 0.93 for c in PULP[:3]) + (1,); cv.inputs[7].default_value = PULP; t.links.new(cv.outputs[2], pb.inputs['Base Color'])

# ---------------- base tray ----------------
N = (int(TW * 3), int(TD * 3))
xs = np.linspace(-TW / 2 - 14, TW / 2 + 2, N[0] + 50); ys = np.linspace(-TD / 2 - 2, TD / 2 + 2, N[1] + 12); X, Y = np.meshgrid(xs, ys)
Z = np.full(X.shape, H)
for cx, cy in cells:
    d = sq(X - cx, Y - cy)
    # invert cup_r: height for a given radius
    zc = ZB + (H - ZB) * np.clip((d - RB) / (RO - RB), 0, 1) ** (1 / 0.8)
    Z = np.minimum(Z, np.where(d < RO, zc, H))
# cone posts at the two inner crossings, reaching up to hold the lid
PH = LID_H - 3
for px in (-P / 2, P / 2):
    d = np.hypot(X - px, Y)
    Z = np.maximum(Z, np.where(d < 13, H + PH * np.clip(1 - (d - 4) / 9, 0, 1) ** 1.0, Z))
    Z = np.where(d < 4, H + PH, Z)
# outer skirt: rim lip, then the wall drops to the table
ed = rrect(X, Y, TW, TD, 10)
Z = np.where(ed > -5, H, Z)                                   # thin flat flange round the outside; cups hang below it
# latch tab at the front: a flap with two holes
tab = (Y < -TD / 2 + 1) & (Y > -TD / 2 - 1) & (np.abs(X) < 40)
keep_b = (ed <= 0.5)
base = shell('base', Z, X, Y, keep_b, G('WALL', '1.8'), pulp)
# front tab as its own strip standing proud of the rim
bpy.ops.mesh.primitive_cube_add(size=1); tb = bpy.context.active_object; tb.scale = (70 * MM, 1.8 * MM, 16 * MM); tb.location = (0, (-TD / 2 - 0.9) * MM, (H - 5) * MM)
tb.data.materials.append(pulp)
for hx in (-18, 18):
    bpy.ops.mesh.primitive_cylinder_add(radius=4 * MM, depth=10 * MM, location=(hx * MM, (-TD / 2 - 0.9) * MM, (H - 4) * MM), rotation=(math.pi / 2, 0, 0))
    hole = bpy.context.active_object; bo = tb.modifiers.new('h', 'BOOLEAN'); bo.object = hole; bo.operation = 'DIFFERENCE'; hole.hide_render = True
bv = tb.modifiers.new('b', 'BEVEL'); bv.width = 0.6 * MM; bv.segments = 3

# ---------------- lid: a dome over each egg, flat label strip on top ----------------
xs2 = np.linspace(-TW / 2 - 2, TW / 2 + 2, N[0] + 12); ys2 = np.linspace(-TD / 2 - 2, TD / 2 + 2, N[1] + 12); X2, Y2 = np.meshgrid(xs2, ys2)
ed2 = rrect(X2, Y2, TW, TD, 10)
Zl = np.zeros(X2.shape)
for cx, cy in cells:
    d = np.hypot(X2 - cx, Y2 - cy) / (P * 0.62)
    Zl = np.maximum(Zl, (LID_H + 6) * np.sqrt(np.clip(1 - d ** 2, 0, 1)))
Zl = np.minimum(Zl, LID_H)                                     # flat label plateau
Zl = np.maximum(Zl, (LID_H * 0.55) * np.clip(-ed2 / 14, 0, 1) ** 0.6)   # sides fill out to the rim
Zl = Zl * np.clip(-ed2 / 2.5, 0, 1) ** 0.5
# YOJO pressed into the plateau
lm = np.asarray(Image.open(os.path.join(HERE, 'lid-mask.png')).convert('L').filter(ImageFilter.GaussianBlur(1.5)), np.float32) / 255
hh, ww = lm.shape; px_ = (X2 / (TW * 0.55) + 0.5) * (ww - 1); py_ = (0.5 - Y2 / (TD * 0.55)) * (hh - 1)
ins = (px_ >= 0) & (px_ <= ww - 1) & (py_ >= 0) & (py_ <= hh - 1)
mk = np.zeros_like(X2); mk[ins] = lm[py_[ins].astype(int), px_[ins].astype(int)]
Zl = Zl - 1.2 * mk * (Zl > LID_H - 0.5)
lid = shell('lid', Zl, X2, Y2 - TD / 2, ed2 <= 0.5, G('WALL', '1.8'), pulp)
lid.location = (0, TD / 2 * MM, H * MM); lid.rotation_euler = (math.radians(-G('OPEN', '112')), 0, 0)
# hinge strip
bpy.ops.mesh.primitive_cylinder_add(radius=2.2 * MM, depth=(TW - 30) * MM, location=(0, (TD / 2) * MM, (H + 0.5) * MM), rotation=(0, math.pi / 2, 0))
bpy.context.active_object.data.materials.append(pulp)

# ---------------- eggs ----------------
order = E('ORDER', 'sky,rose,brushed,sage,cloud,cobalt').split(',')
spin = [6, -10, 4, -8, 10, -4]
for k, (cx, cy) in enumerate(cells):
    root = bpy.data.objects.new(f'egg_{k}', None); bpy.context.collection.objects.link(root)
    body = body_brushed if order[k] == 'brushed' else skinmat(f'skin_{k}', SK[order[k]])
    for nm_, mt in (('skin', body), ('head', head_m), ('slot', blackm), ('thread', threadm), ('sleeve_core', threadm), ('collar', threadm)):
        if nm_ not in lib: continue
        o = lib[nm_].copy(); bpy.context.collection.objects.link(o)
        for sl in o.material_slots: sl.link = 'OBJECT'; sl.material = mt
        o.parent = root
    root.location = (cx * MM, cy * MM, SEAT * MM); root.rotation_euler = (0, 0, math.radians(spin[k]))

# ---------------- studio ----------------
BG = s2l(E('BG', '#BFE3FA'))
bgm, _ = mat('backdrop', **{'Base Color': BG, 'Roughness': 0.95, 'Specular IOR Level': 0.2})
bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 0, 0)); bpy.context.active_object.data.materials.append(bgm)
world = bpy.data.worlds.new('w'); scene.world = world; world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = BG; world.node_tree.nodes['Background'].inputs['Strength'].default_value = G('WORLD', '0.25')
def area(name, loc, a, b, e, tgt=(0, 0, 0.03)):
    ld = bpy.data.lights.new(name, 'AREA'); ld.shape = 'RECTANGLE'; ld.size = a; ld.size_y = b; ld.energy = e
    ob = bpy.data.objects.new(name, ld); bpy.context.collection.objects.link(ob); ob.location = loc
    ob.rotation_euler = mathutils.Vector(np.array(tgt) - np.array(loc)).to_track_quat('-Z', 'Y').to_euler(); ob.visible_camera = False
area('key', (-0.6, -0.5, 0.9), 1.2, 1.2, G('KEY', '10'))
area('fill', (0.7, -0.4, 0.5), 1.0, 1.0, G('FILL', '2.5'))
area('top', (0.0, 0.1, 1.1), 0.8, 0.8, G('TOP', '4'))
area('strip', (0.30, 0.10, 0.30), 0.05, 0.4, G('STRIP', '1.2'), tgt=(0.04, 0, 0.07))
cam_d = bpy.data.cameras.new('cam'); cam_d.lens = G('LENS', '40'); cam_d.sensor_fit = 'VERTICAL'; cam_d.sensor_height = 24
cam = bpy.data.objects.new('cam', cam_d); bpy.context.collection.objects.link(cam); scene.camera = cam
tgt = mathutils.Vector((0, G('TY', '0.02'), G('TZ', '0.06'))); el = math.radians(G('EL', '34')); th = math.radians(G('TH', '-104')); d = G('D', '0.78')
cam.location = tgt + mathutils.Vector((d * math.cos(el) * math.cos(th), d * math.cos(el) * math.sin(th), d * math.sin(el)))
cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = SAMPLES; scene.cycles.use_denoising = True
scene.cycles.use_adaptive_sampling = True; scene.render.resolution_x = RX; scene.render.resolution_y = RY
scene.view_settings.view_transform = 'Standard'; scene.view_settings.look = 'None'; scene.view_settings.exposure = G('EXPO', '-0.6')
scene.render.filepath = OUT; bpy.ops.render.render(write_still=True); print('done', OUT)

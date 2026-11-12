# A grid of YOJO pods with inkjet batch stamps; one egg-white egg carries the batch message in copper ink.
import os, math, json
import numpy as np
import bpy, mathutils
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ST = os.environ.get('STAMPDIR', os.path.join(HERE, '..', 'stamp'))
E = os.environ.get; G = lambda k, d: float(E(k, d)); MM = 0.001
OUT = E('OUT', os.path.join(ST, 'grid.png')); RX, RY = int(E('RX', '736')), int(E('RY', '920')); SAMPLES = int(E('SAMPLES', '24'))
bpy.ops.wm.read_factory_settings(use_empty=True); scene = bpy.context.scene; C = bpy.context.collection
def s2l(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)
def load(fn, names):
    with bpy.data.libraries.load(os.path.join(HERE, 'mk', fn)) as (src, dst):
        want = [n for n in src.objects if n in names]; dst.objects = list(want)
    return dict(zip(want, dst.objects))
pod = load(E('PODFILE', 'egg_lo.blend'), ('skin',)); eg = load(E('PODFILE', 'egg_lo.blend'), ('head', 'slot'))
def mat(name, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    for k, v in kw.items():
        if k in b.inputs: b.inputs[k].default_value = v
    return m, b
def head_mat():
    m, b = mat('head', **{'Base Color': (0.96, 0.92, 0.86, 1), 'Metallic': 1.0, 'Roughness': 0.1}); t = m.node_tree
    at = t.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'carve'; mc = t.nodes.new('ShaderNodeMix'); mc.data_type = 'RGBA'
    t.links.new(at.outputs['Fac'], mc.inputs['Factor']); mc.inputs[6].default_value = (0.96, 0.92, 0.86, 1); mc.inputs[7].default_value = (0.02, 0.02, 0.02, 1)
    t.links.new(mc.outputs[2], b.inputs['Base Color']); return m
HM = head_mat(); BLK, _ = mat('slot', **{'Base Color': (0.01, 0.01, 0.01, 1)})

def skin_with_stamp(name, base, ink, img, w_mm, rot, cx, cz, h_over_w):
    """Silicone skin with an ink stamp projected straight onto the front of the egg (object space, X/Z plane)."""
    m, b = mat(name, **{'Base Color': base, 'Roughness': 0.62, 'Sheen Weight': 0.55, 'Sheen Roughness': 0.35, 'Sheen Tint': (1, 1, 1, 1),
                        'Subsurface Weight': 0.06, 'Subsurface Scale': 0.002, 'Specular IOR Level': 0.35})
    t = m.node_tree; N_ = t.nodes; L_ = t.links
    tc = N_.new('ShaderNodeTexCoord'); sp = N_.new('ShaderNodeSeparateXYZ'); L_.new(tc.outputs['Object'], sp.inputs['Vector'])
    cb = N_.new('ShaderNodeCombineXYZ'); L_.new(sp.outputs['X'], cb.inputs['X']); L_.new(sp.outputs['Z'], cb.inputs['Y'])
    # centre on the stamp, rotate it, scale metres to the stamp's size, shift to the middle of the image
    off = N_.new('ShaderNodeVectorMath'); off.operation = 'SUBTRACT'; off.inputs[1].default_value = (cx * MM, cz * MM, 0); L_.new(cb.outputs[0], off.inputs[0])
    rt = N_.new('ShaderNodeVectorRotate'); rt.rotation_type = 'Z_AXIS'; rt.inputs['Angle'].default_value = math.radians(-rot); L_.new(off.outputs[0], rt.inputs['Vector'])
    sc = N_.new('ShaderNodeVectorMath'); sc.operation = 'MULTIPLY'; sc.inputs[1].default_value = (1 / (w_mm * MM), 1 / (w_mm * h_over_w * MM), 1); L_.new(rt.outputs[0], sc.inputs[0])
    add = N_.new('ShaderNodeVectorMath'); add.operation = 'ADD'; add.inputs[1].default_value = (0.5, 0.5, 0); L_.new(sc.outputs[0], add.inputs[0])
    tx = N_.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load(img); tx.image.colorspace_settings.name = 'Non-Color'; tx.extension = 'CLIP'
    L_.new(add.outputs[0], tx.inputs['Vector'])
    geo = N_.new('ShaderNodeNewGeometry'); dt = N_.new('ShaderNodeVectorMath'); dt.operation = 'DOT_PRODUCT'; dt.inputs[1].default_value = (0, -1, 0)
    L_.new(geo.outputs['Normal'], dt.inputs[0]); fr = N_.new('ShaderNodeMapRange'); L_.new(dt.outputs['Value'], fr.inputs['Value'])
    fr.inputs['From Min'].default_value = 0.2; fr.inputs['From Max'].default_value = 0.45
    mul = N_.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; L_.new(tx.outputs['Color'], mul.inputs[0]); L_.new(fr.outputs['Result'], mul.inputs[1])
    mc = N_.new('ShaderNodeMix'); mc.data_type = 'RGBA'; L_.new(mul.outputs[0], mc.inputs['Factor']); mc.inputs[6].default_value = base; mc.inputs[7].default_value = ink
    L_.new(mc.outputs[2], b.inputs['Base Color'])
    rg = N_.new('ShaderNodeMapRange'); L_.new(mul.outputs[0], rg.inputs['Value']); rg.inputs['To Min'].default_value = 0.62; rg.inputs['To Max'].default_value = 0.8
    L_.new(rg.outputs['Result'], b.inputs['Roughness'])
    return m

spec = json.load(open(os.path.join(ST, 'spec.json')))
EGG = s2l(E('EGGC', '#D9D3C6')); WHITE = s2l(E('WHITEC', '#F6F4EE')); INK = s2l(E('INK', '#2A8FC7')); COPPER = s2l(E('COPPER', '#E0701E'))
PX, PZ = G('PX', '78'), G('PZ', '102')
for s in spec:
    i = s['i']; col, row = i % 4, i // 4
    img = os.path.join(ST, f"s{i:02d}.png"); w, h = Image.open(img).size
    base, ink = (WHITE, COPPER) if s['big'] else (EGG, INK)
    sm = skin_with_stamp(f'sk{i}', base, ink, img, s['w'], s['rot'], s['x'], s['z'], h / w)
    root = bpy.data.objects.new('egg', None); C.objects.link(root)
    for nm_, mt, src in (('skin', sm, pod), ('head', HM, eg), ('slot', BLK, eg)):
        o = src[nm_].copy(); C.objects.link(o)
        for sl in o.material_slots: sl.link = 'OBJECT'; sl.material = mt
        o.parent = root
    root.location = ((col - 1.5) * PX * MM, 0, (1.5 - row) * PZ * MM - 0.043)
bgm, _ = mat('bg', **{'Base Color': s2l(E('BG', '#8FB2AE')), 'Roughness': 0.95, 'Specular IOR Level': 0.1})
bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0.045, 0), rotation=(math.pi / 2, 0, 0)); bpy.context.active_object.data.materials.append(bgm)
world = bpy.data.worlds.new('w'); scene.world = world; world.use_nodes = True; world.node_tree.nodes['Background'].inputs['Strength'].default_value = G('WORLD', '0.3')
def area(n, loc, s, e):
    ld = bpy.data.lights.new(n, 'AREA'); ld.size = s; ld.energy = e; ob = bpy.data.objects.new(n, ld); C.objects.link(ob); ob.location = loc; ob.visible_camera = False
    ob.rotation_euler = (mathutils.Vector((0, 0, 0)) - mathutils.Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
area('key', (-0.35, -0.9, 0.55), 1.0, G('KEY', '60')); area('fill', (0.5, -0.9, -0.2), 1.0, G('FILL', '18'))
cd = bpy.data.cameras.new('cam'); cd.type = 'ORTHO'; cd.ortho_scale = G('ORTHO', '0.41'); cd.sensor_fit = 'VERTICAL'
cam = bpy.data.objects.new('cam', cd); C.objects.link(cam); scene.camera = cam; cam.location = (0, -1.0, 0); cam.rotation_euler = (math.pi / 2, 0, 0)
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = SAMPLES; scene.cycles.use_denoising = True
scene.render.resolution_x = RX; scene.render.resolution_y = RY; scene.view_settings.view_transform = 'Standard'; scene.view_settings.exposure = G('EXPO', '0')
scene.render.filepath = OUT; bpy.ops.render.render(write_still=True); print('done', OUT)

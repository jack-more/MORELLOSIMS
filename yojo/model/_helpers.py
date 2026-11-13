# Editorial stills for the site. SCENE = hero | cream | water | gel | light
import os, math, json
import numpy as np
import bpy, mathutils
HERE = os.path.dirname(os.path.abspath(__file__)); E = os.environ.get; G = lambda k, d: float(E(k, d)); MM = 0.001
SCENE = E('SCENE', 'hero'); OUT = E('OUT', os.path.join(HERE, 'ed_' + SCENE + '.png'))
RX, RY = int(E('RX', '1600')), int(E('RY', '900')); SAMPLES = int(E('SAMPLES', '32'))
bpy.ops.wm.read_factory_settings(use_empty=True); scene = bpy.context.scene; C = bpy.context.collection
def s2l(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)
lin = lambda n: tuple(map(float, json.load(open(os.path.join(HERE, f'cm_{n}.json')))['SKIN_LIN'].split(','))) + (1.0,)
def mat(name, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    for k, v in kw.items():
        if k in b.inputs: b.inputs[k].default_value = v
    return m, b
def stone(name, base, vein, scale=6.0, rough=0.75, bump=0.25):
    m, b = mat(name, **{'Roughness': rough, 'Specular IOR Level': 0.3}); t = m.node_tree; N_ = t.nodes; L_ = t.links
    tc = N_.new('ShaderNodeTexCoord'); mp = N_.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1, 1, 6); L_.new(tc.outputs['Object'], mp.inputs['Vector'])
    wv = N_.new('ShaderNodeTexWave'); wv.wave_type = 'BANDS'; wv.bands_direction = 'Z'; wv.inputs['Scale'].default_value = scale; wv.inputs['Distortion'].default_value = 6; wv.inputs['Detail'].default_value = 6
    L_.new(mp.outputs[0], wv.inputs['Vector'])
    nz = N_.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 140; nz.inputs['Detail'].default_value = 8; L_.new(tc.outputs['Object'], nz.inputs['Vector'])
    rp = N_.new('ShaderNodeValToRGB'); L_.new(wv.outputs['Fac'], rp.inputs['Fac']); rp.color_ramp.elements[0].color = base; rp.color_ramp.elements[1].color = vein
    L_.new(rp.outputs['Color'], b.inputs['Base Color'])
    pits = N_.new('ShaderNodeMath'); pits.operation = 'GREATER_THAN'; pits.inputs[1].default_value = 0.68; L_.new(nz.outputs['Fac'], pits.inputs[0])
    bp = N_.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = bump; bp.inputs['Distance'].default_value = 0.0006; L_.new(pits.outputs[0], bp.inputs['Height'])
    L_.new(bp.outputs['Normal'], b.inputs['Normal']); return m
def plaster(name, col):
    m, b = mat(name, **{'Base Color': col, 'Roughness': 0.92, 'Specular IOR Level': 0.2}); t = m.node_tree
    nz = t.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 60; nz.inputs['Detail'].default_value = 10
    bp = t.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.12; t.links.new(nz.outputs['Fac'], bp.inputs['Height']); t.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m
def box(size, loc, m_, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.active_object; o.scale = size; bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(m_)
    if bevel: bv = o.modifiers.new('b', 'BEVEL'); bv.width = bevel; bv.segments = 4
    return o
def camera(loc, tgt, lens, dof=None):
    cd = bpy.data.cameras.new('cam'); cd.lens = lens; cam = bpy.data.objects.new('cam', cd); C.objects.link(cam); scene.camera = cam
    cam.location = loc; cam.rotation_euler = (mathutils.Vector(tgt) - mathutils.Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    if dof: cd.dof.use_dof = True; cd.dof.focus_distance = (mathutils.Vector(tgt) - mathutils.Vector(loc)).length; cd.dof.aperture_fstop = dof
def sun(rot, e, col=(1.0, 0.9, 0.78), angle=1.5):
    s = bpy.data.lights.new('sun', 'SUN'); s.energy = e; s.color = col; s.angle = math.radians(angle)
    o = bpy.data.objects.new('sun', s); C.objects.link(o); o.rotation_euler = rot; return o
def area(n, loc, s, e, tgt=(0, 0, 0), col=(1, 1, 1)):
    ld = bpy.data.lights.new(n, 'AREA'); ld.size = s; ld.energy = e; ld.color = col
    ob = bpy.data.objects.new(n, ld); C.objects.link(ob); ob.location = loc; ob.visible_camera = False
    ob.rotation_euler = (mathutils.Vector(tgt) - mathutils.Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
world = bpy.data.worlds.new('w'); scene.world = world; world.use_nodes = True
bgn = world.node_tree.nodes['Background']; bgn.inputs['Color'].default_value = s2l('#E9E2D6'); bgn.inputs['Strength'].default_value = G('WORLD', '0.35')

def load_egg(skin_col, metal='sterling'):
    with bpy.data.libraries.load(os.path.join(HERE, 'mk', E('EGGFILE', 'egg_c.blend'))) as (src, dst):
        want = [n for n in src.objects if n in ('skin', 'head', 'slot')]; dst.objects = list(want)
    lib = dict(zip(want, dst.objects))
    sk, _ = mat('skin', **{'Base Color': skin_col, 'Roughness': 0.62, 'Sheen Weight': 0.55, 'Sheen Roughness': 0.35, 'Sheen Tint': (1, 1, 1, 1),
                          'Subsurface Weight': 0.06, 'Subsurface Scale': 0.002, 'Specular IOR Level': 0.35})
    hm, hb = mat('head', **{'Base Color': (0.96, 0.92, 0.86, 1), 'Metallic': 1.0, 'Roughness': 0.1}); t = hm.node_tree
    at = t.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'carve'; cr = t.nodes.new('ShaderNodeMapRange'); t.links.new(at.outputs['Fac'], cr.inputs['Value'])
    cr.inputs['From Min'].default_value = 0.25; cr.inputs['From Max'].default_value = 0.6
    mc = t.nodes.new('ShaderNodeMix'); mc.data_type = 'RGBA'; t.links.new(cr.outputs['Result'], mc.inputs['Factor'])
    mc.inputs[6].default_value = (0.96, 0.92, 0.86, 1); mc.inputs[7].default_value = (0.018, 0.018, 0.02, 1); t.links.new(mc.outputs[2], hb.inputs['Base Color'])
    mr = t.nodes.new('ShaderNodeMapRange'); t.links.new(cr.outputs['Result'], mr.inputs['Value']); mr.inputs['To Min'].default_value = 0.1; mr.inputs['To Max'].default_value = 0.62
    t.links.new(mr.outputs['Result'], hb.inputs['Roughness'])
    blk, _ = mat('slot', **{'Base Color': (0.01, 0.01, 0.01, 1)})
    root = bpy.data.objects.new('egg', None); C.objects.link(root)
    for nm_, mt in (('skin', sk), ('head', hm), ('slot', blk)):
        o = lib[nm_]; C.objects.link(o); o.data.materials.clear(); [o.data.materials.append(mt) for _ in range(3 if nm_ == 'head' else 1)]; o.parent = root
    return root

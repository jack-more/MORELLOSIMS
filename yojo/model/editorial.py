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

if SCENE == 'hero':
    # limestone wall, travertine plinth, low warm sun through window slats
    wall = plaster('wall', s2l('#E6DCCD')); box((3.0, 0.05, 2.0), (0, 0.45, 0.6), wall); box((3.0, 1.6, 0.02), (0, -0.3, -0.31), wall)
    trav = stone('trav', s2l('#E7DCCB'), s2l('#D3C3AA'))
    box((0.30, 0.30, 0.30), (0, 0.05, -0.15), trav, bevel=0.002)
    egg = load_egg(lin('sky')); egg.location = (0, 0.05, 0.0); egg.rotation_euler = (0, 0, math.radians(-10))
    for i in range(9):   # blinds: thin slats between the sun and the wall
        box((1.4, 0.004, 0.022), (-0.9, -0.55, 0.25 + i * 0.05), wall).visible_camera = False
    s = sun((math.radians(62), 0, math.radians(-128)), G('SUN', '5.5'))
    area('fill', (0.6, -1.0, 0.4), 1.2, G('FILL', '12'), tgt=(0, 0, 0.05), col=(0.9, 0.93, 1.0))
    camera((0.16, -0.95, 0.10), (0.02, 0.05, 0.035), G('LENS', '50'), dof=G('FSTOP', '5.6'))
elif SCENE == 'cream':
    # a swirl of blue copper-peptide cream on a glass slab, from above
    glass, _ = mat('glass', **{'Base Color': (0.95, 0.97, 0.98, 1), 'Roughness': 0.05, 'Transmission Weight': 1.0, 'IOR': 1.5})
    box((0.5, 0.5, 0.01), (0, 0, -0.005), glass); box((2, 2, 0.01), (0, 0, -0.03), plaster('under', s2l('#EDE7DC')))
    cu = bpy.data.curves.new('swirl', 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 0.006; cu.bevel_resolution = 10; cu.use_fill_caps = True
    sp = cu.splines.new('NURBS'); pts = []
    for k in range(60):
        t = k / 59; a = t * 4.6 * math.pi; r = 0.05 * (1 - 0.82 * t) + 0.004
        pts.append((r * math.cos(a), r * math.sin(a), 0.004 + 0.012 * t ** 2))
    sp.points.add(len(pts) - 1)
    for p, c in zip(sp.points, pts): p.co = (*c, 1)
    sp.use_endpoint_u = True; sp.order_u = 4
    ob = bpy.data.objects.new('swirl', cu); C.objects.link(ob); ob.scale = (1, 1, 0.55)
    cm, _ = mat('cream', **{'Base Color': s2l('#3D86D6'), 'Roughness': 0.22, 'Subsurface Weight': 0.5, 'Subsurface Scale': 0.004, 'Coat Weight': 0.4, 'Coat Roughness': 0.12})
    cu.materials.append(cm)
    area('key', (-0.25, -0.2, 0.5), 0.5, G('KEY', '30'), tgt=(0, 0, 0)); area('rim', (0.3, 0.25, 0.25), 0.15, G('RIM', '18'), tgt=(0, 0, 0))
    camera((0.02, -0.06, 0.32), (0, 0, 0.005), G('LENS', '65'), dof=G('FSTOP', '4'))
elif SCENE == 'water':
    # still water, one ring of ripples, warm light
    me = bpy.data.meshes.new('w'); bpy.ops.mesh.primitive_grid_add(x_subdivisions=400, y_subdivisions=400, size=0.6); o = bpy.context.active_object
    tx = bpy.data.textures.new('rip', 'WOOD'); tx.wood_type = 'RINGNOISE'; tx.noise_basis_2 = 'SIN'; tx.turbulence = 0.4; tx.noise_scale = 0.06
    dp = o.modifiers.new('d', 'DISPLACE'); dp.texture = tx; dp.strength = 0.0012; o.modifiers.new('s', 'SUBSURF').levels = 1
    bpy.ops.object.shade_smooth()
    wm, _ = mat('water', **{'Base Color': s2l('#DDE6E8'), 'Roughness': 0.04, 'Transmission Weight': 0.9, 'IOR': 1.33}); o.data.materials.append(wm)
    box((2, 2, 0.01), (0, 0, -0.02), plaster('bed', s2l('#D9D2C6')))
    area('key', (-0.3, 0.4, 0.5), 0.3, G('KEY', '40'), tgt=(0, 0, 0)); area('fill', (0.4, -0.4, 0.6), 1.0, G('FILL', '6'), tgt=(0, 0, 0))
    camera((0, -0.15, 0.5), (0, 0, 0), G('LENS', '50'))
elif SCENE == 'gel':
    # a clear gel drop on stone, a dewy sheen
    box((1, 1, 0.02), (0, 0, -0.01), stone('st', s2l('#E4DACB'), s2l('#CDBEA6'), scale=3))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.03, segments=96, ring_count=48, location=(0, 0, 0)); d = bpy.context.active_object; d.scale = (1.3, 1, 0.38); bpy.ops.object.shade_smooth()
    gm, _ = mat('gel', **{'Base Color': (0.98, 0.99, 1, 1), 'Roughness': 0.02, 'Transmission Weight': 1.0, 'IOR': 1.36}); d.data.materials.append(gm)
    for k in range(9):
        a = k * 2.4; r = 0.06 + 0.02 * (k % 3)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.004 + 0.002 * (k % 2), location=(r * math.cos(a), r * math.sin(a), 0)); s = bpy.context.active_object; s.scale = (1, 1, 0.45); s.data.materials.append(gm); bpy.ops.object.shade_smooth()
    area('key', (-0.3, -0.25, 0.35), 0.4, G('KEY', '30'), tgt=(0, 0, 0)); area('back', (0.2, 0.35, 0.2), 0.2, G('BACK', '14'), tgt=(0, 0, 0))
    camera((0.0, -0.32, 0.2), (0, 0, 0.004), G('LENS', '85'), dof=G('FSTOP', '3.5'))
elif SCENE == 'light':
    # morning sun through slats on limestone: the SPF step
    wall = plaster('wall', s2l('#E8DFD1')); box((2, 0.05, 2), (0, 0.025, 0), wall)
    for i in range(12): box((2.0, 0.004, 0.03), (-0.2, -0.6, -0.3 + i * 0.07), wall).visible_camera = False
    sun((math.radians(70), math.radians(8), math.radians(-150)), G('SUN', '6'))
    camera((0, -1.0, 0), (0, 0, 0), G('LENS', '50'))
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = SAMPLES; scene.cycles.use_denoising = True
scene.cycles.use_adaptive_sampling = True; scene.render.resolution_x = RX; scene.render.resolution_y = RY
scene.view_settings.view_transform = E('VT', 'AgX'); scene.view_settings.look = E('VLOOK', 'AgX - Base Contrast') if E('VT', 'AgX') == 'AgX' else 'None'
scene.view_settings.exposure = G('EXPO', '0')
scene.render.filepath = OUT; bpy.ops.render.render(write_still=True); print('done', OUT)

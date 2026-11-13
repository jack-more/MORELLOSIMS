# YOJO logo family: ITEM = lockup | coin
import os, math
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_helpers.py')).read())
ITEM = E('ITEM', 'lockup'); OUT = E('OUT', os.path.join(HERE, 'fam_' + ITEM + '.png'))
ASSETS = '/home/user/MORELLOSIMS/yojo/site-live/assets/'
# studio world for chrome: navy floor, bright horizon strip, ice sky
wt = world.node_tree; tc = wt.nodes.new('ShaderNodeTexCoord'); sx = wt.nodes.new('ShaderNodeSeparateXYZ'); wt.links.new(tc.outputs['Generated'], sx.inputs[0])
mr = wt.nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = -1; wt.links.new(sx.outputs['Z'], mr.inputs['Value'])
rp = wt.nodes.new('ShaderNodeValToRGB'); wt.links.new(mr.outputs['Result'], rp.inputs['Fac']); r = rp.color_ramp
# Generated Z for the world runs 0 (down) .. 1 (up) around 0.5 at the horizon
r.elements[0].position = 0.0; r.elements[0].color = s2l('#0F2033'); r.elements[1].position = 1.0; r.elements[1].color = s2l('#0F2033')
for p, c in ((0.45, '#3B536D'), (0.5, '#FFFFFF'), (0.53, '#0F2033'), (0.6, '#163049'), (0.66, '#7FA6C4'), (0.76, '#EAF6FD'), (0.86, '#A8D3EF'), (0.95, '#24384F')): e = r.elements.new(p); e.color = s2l(c)
wt.links.new(rp.outputs['Color'], bgn.inputs['Color']); bgn.inputs['Strength'].default_value = 1.0

def svg(path, depth, bevel, size):
    try: bpy.ops.preferences.addon_enable(module='io_curve_svg')
    except Exception: pass
    before = set(bpy.data.objects); bpy.ops.import_curve.svg(filepath=path); new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        o.select_set(True); bpy.context.view_layer.objects.active = o
        o.data.extrude = depth; o.data.bevel_depth = bevel; o.data.bevel_resolution = 8; o.data.fill_mode = 'BOTH'
    bpy.ops.object.convert(target='MESH')
    if len(new) > 1: bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS'); o.location = (0, 0, 0)
    d = max(o.dimensions.x, o.dimensions.y); o.scale = (size / d,) * 3; bpy.ops.object.transform_apply(scale=True)
    return o
def silver(rough=0.08, col=(0.95, 0.96, 0.98, 1)):
    m, b = mat('silver', **{'Base Color': col, 'Metallic': 1.0, 'Roughness': rough}); return m, b

if ITEM == 'lockup':
    o = svg(ASSETS + 'wordmark.svg', 0.004, float(E('BEV', '0.0026')), 0.30)       # 30 cm wide, letters 9 mm deep each side
    o.rotation_euler = (math.radians(84), 0, math.radians(-6))
    m, b = silver(0.06); o.data.materials.clear(); o.data.materials.append(m)
    bv = o.modifiers.new('bv', 'BEVEL'); bv.width = 0.0004; bv.segments = 3
    cam = camera((0.0, -0.62, -0.03), (0, 0, 0.0), 52)
    RES = (2000, 900)
elif ITEM == 'coin':
    m, b = silver(0.24, (0.86, 0.88, 0.9, 1))
    t = m.node_tree; N_, L_ = t.nodes, t.links; tc2 = N_.new('ShaderNodeTexCoord')
    # turned micro rings on the face, reeding on the edge
    wv = N_.new('ShaderNodeTexWave'); wv.wave_type = 'RINGS'; wv.inputs['Scale'].default_value = 60; L_.new(tc2.outputs['Object'], wv.inputs['Vector'])
    wv2 = N_.new('ShaderNodeTexWave'); wv2.wave_type = 'BANDS'; wv2.bands_direction = 'X'; wv2.wave_profile = 'SAW'
    ln = N_.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; L_.new(tc2.outputs['Object'], ln.inputs[0])
    mm = N_.new('ShaderNodeMath'); mm.operation = 'MULTIPLY'; mm.inputs[1].default_value = 2 * math.pi / 0.0006; L_.new(ln.outputs['Value'], mm.inputs[0])
    sn = N_.new('ShaderNodeMath'); sn.operation = 'SINE'; L_.new(mm.outputs[0], sn.inputs[0])
    gr = N_.new('ShaderNodeTexGradient'); gr.gradient_type = 'RADIAL'; L_.new(tc2.outputs['Object'], gr.inputs['Vector'])
    m2 = N_.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'; m2.inputs[1].default_value = 2 * math.pi * 180; L_.new(gr.outputs['Fac'], m2.inputs[0])
    s2 = N_.new('ShaderNodeMath'); s2.operation = 'SINE'; L_.new(m2.outputs[0], s2.inputs[0])
    nm = N_.new('ShaderNodeNewGeometry'); sz = N_.new('ShaderNodeSeparateXYZ'); L_.new(nm.outputs['Normal'], sz.inputs[0])
    ab = N_.new('ShaderNodeMath'); ab.operation = 'ABSOLUTE'; L_.new(sz.outputs['Z'], ab.inputs[0])
    # world normal z is not object z once tilted; use the object-space normal instead
    vt = N_.new('ShaderNodeVectorTransform'); vt.vector_type = 'NORMAL'; vt.convert_from = 'WORLD'; vt.convert_to = 'OBJECT'; L_.new(nm.outputs['Normal'], vt.inputs[0]); L_.new(vt.outputs[0], sz.inputs[0])
    st = N_.new('ShaderNodeMath'); st.operation = 'GREATER_THAN'; st.inputs[1].default_value = 0.9; L_.new(ab.outputs[0], st.inputs[0])
    mix = N_.new('ShaderNodeMix'); mix.data_type = 'FLOAT'; L_.new(st.outputs[0], mix.inputs['Factor']); L_.new(s2.outputs[0], mix.inputs[2]); L_.new(sn.outputs[0], mix.inputs[3])
    bp = N_.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.35; bp.inputs['Distance'].default_value = 0.00012; L_.new(mix.outputs[0], bp.inputs['Height']); L_.new(bp.outputs['Normal'], b.inputs['Normal'])
    bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=0.008, vertices=256); coin = bpy.context.active_object; coin.data.materials.append(m); bpy.ops.object.shade_smooth()
    bv = coin.modifiers.new('bv', 'BEVEL'); bv.width = 0.0012; bv.segments = 6; coin.modifiers.new('ws', 'WEIGHTED_NORMAL')
    y = svg(ASSETS + 'y.svg', 0.0012, 0.0004, 0.062); y.location = (0, 0.002, 0.0047)
    ym, _ = silver(0.03, (0.98, 0.98, 0.99, 1)); y.data.materials.clear(); y.data.materials.append(ym)
    for o in (coin, y): o.rotation_euler = (math.radians(62), 0, math.radians(-18))
    y.location = (0, 0, 0); y.parent = coin; y.matrix_parent_inverse = coin.matrix_world.inverted(); y.location = (0, 0.002, 0.0047); y.rotation_euler = (0, 0, 0)
    coin.location = (0, 0, 0.0)
    cam = camera((0, -0.36, 0.0), (0, 0, 0.0), 85)
    RES = (1600, 1600)
area('strip', (0.45, -0.25, 0.25), 0.02, float(E('STRIP', '3')), tgt=(0, 0, 0))
scene.render.film_transparent = True
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = SAMPLES; scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = int(E('RX', RES[0])), int(E('RY', RES[1])); scene.render.image_settings.color_mode = 'RGBA'
scene.view_settings.view_transform = 'AgX'; scene.view_settings.look = 'AgX - Medium High Contrast'
scene.render.filepath = OUT; bpy.ops.render.render(write_still=True); print('done', OUT)

# Hero set blockouts for "Young forever". SET = pool | diner | cake
import os, math, random
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_helpers.py')).read())
SET = E('SET', 'pool'); OUT = E('OUT', os.path.join(HERE, 'set_' + SET + '.png')); random.seed(4)
def cyl(r, h, loc, m_, verts=64):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, location=loc, vertices=verts); o = bpy.context.active_object; o.data.materials.append(m_); bpy.ops.object.shade_smooth(); return o
def ball(r, loc, m_):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=24, ring_count=12); o = bpy.context.active_object; o.data.materials.append(m_); bpy.ops.object.shade_smooth(); return o
def tiles(name, c1, c2, grout, size):
    m, b = mat(name, **{'Roughness': 0.12, 'Coat Weight': 0.6}); t = m.node_tree; N_, L_ = t.nodes, t.links
    tc = N_.new('ShaderNodeTexCoord'); br = N_.new('ShaderNodeTexBrick'); br.offset = 0; br.squash_frequency = 1
    br.inputs['Color1'].default_value = c1; br.inputs['Color2'].default_value = c2; br.inputs['Mortar'].default_value = grout
    br.inputs['Scale'].default_value = 1 / size; br.inputs['Mortar Size'].default_value = 0.06; br.inputs['Brick Width'].default_value = 1; br.inputs['Row Height'].default_value = 1
    br.inputs['Bias'].default_value = 0
    # project on the dominant axis so walls and floors both get squares
    sep = N_.new('ShaderNodeSeparateXYZ'); L_.new(tc.outputs['Object'], br.inputs['Vector'])
    L_.new(br.outputs['Color'], b.inputs['Base Color'])
    bp = N_.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.4; bp.invert = True; L_.new(br.outputs['Fac'], bp.inputs['Height']); L_.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m
def tilebox(size, loc, m_):
    o = box(size, loc, m_); return o
def chrome(rough=0.06):
    m, _ = mat('chrome', **{'Base Color': (0.92, 0.93, 0.95, 1), 'Metallic': 1, 'Roughness': rough}); return m
def tube(pts, r, m_):
    cu = bpy.data.curves.new('tube', 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = r; cu.bevel_resolution = 6
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts): p.co = (*q, 1)
    o = bpy.data.objects.new('tube', cu); C.objects.link(o); cu.materials.append(m_); return o

egg = load_egg(lin('sky')); egg.rotation_euler = (0, 0, math.radians(-8))

if SET == 'pool':
    # the fountain of youth: a pastel tiled pool, the egg on a tiled plinth rising out of the water
    bgn.inputs['Color'].default_value = s2l('#BFE3FF'); bgn.inputs['Strength'].default_value = 0.6
    t_ice = tiles('tile', s2l('#9FD2F2'), s2l('#AFDAF5'), s2l('#F4F7F8'), 0.016)
    t_white = tiles('tile_w', s2l('#F2F4F2'), s2l('#ECEFEC'), s2l('#D8DEDF'), 0.016)
    box((1.6, 1.4, 0.02), (0, 0.1, -0.11), t_ice)                       # pool floor
    box((1.6, 0.04, 0.6), (0, 0.42, 0.15), t_ice)                       # back wall
    box((0.04, 1.4, 0.2), (-0.36, 0.1, -0.02), t_ice); box((0.04, 1.4, 0.2), (0.36, 0.1, -0.02), t_ice)
    box((1.6, 0.12, 0.02), (0, 0.34, 0.075), t_white)                   # coping ledge at the back
    box((0.085, 0.085, 0.10), (0, 0, -0.05), t_white)                   # plinth, top at z=0
    wm, wb = mat('water', **{'Base Color': s2l('#D6F0FF'), 'Roughness': 0.03, 'Transmission Weight': 1.0, 'IOR': 1.33}); t = wm.node_tree
    nz = t.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 18; nz.inputs['Detail'].default_value = 3
    bp = t.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.35; t.links.new(nz.outputs['Fac'], bp.inputs['Height']); t.links.new(bp.outputs['Normal'], wb.inputs['Normal'])
    w = box((0.68, 1.3, 0.001), (0, 0.05, -0.03), wm)                    # water surface
    cm = chrome()
    for x in (0.16, 0.22):                                              # pool ladder over the back ledge
        tube([(x, 0.33, -0.10), (x, 0.33, 0.10), (x, 0.36, 0.125), (x, 0.395, 0.10), (x, 0.395, 0.085)], 0.0035, cm)
    for z in (-0.07, -0.04): box((0.06, 0.012, 0.004), (0.19, 0.33, z), cm)
    sun((math.radians(38), 0, math.radians(-35)), 4.5, col=(1.0, 0.96, 0.9), angle=1.0)
    camera((0.06, -0.42, 0.06), (0.0, 0.0, 0.035), 48)
elif SET == 'diner':
    # a pastel diner counter: chrome edge, checker wall, a milkshake that never melts
    bgn.inputs['Color'].default_value = s2l('#FFE6EE'); bgn.inputs['Strength'].default_value = 0.4
    fm, fb = mat('formica', **{'Roughness': 0.25, 'Coat Weight': 0.4}); t = fm.node_tree
    nz = t.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 400; rp = t.nodes.new('ShaderNodeValToRGB')
    t.links.new(nz.outputs['Fac'], rp.inputs['Fac']); rp.color_ramp.elements[0].position = 0.62; rp.color_ramp.elements[0].color = s2l('#F2B6C8'); rp.color_ramp.elements[1].position = 0.66; rp.color_ramp.elements[1].color = s2l('#FFFFFF')
    t.links.new(rp.outputs['Color'], fb.inputs['Base Color'])
    box((1.4, 0.36, 0.03), (0, 0.03, -0.015), fm)
    rib, rb = mat('rib', **{'Base Color': (0.93, 0.94, 0.96, 1), 'Metallic': 1, 'Roughness': 0.12}); t = rib.node_tree
    wv = t.nodes.new('ShaderNodeTexWave'); wv.bands_direction = 'Z'; wv.inputs['Scale'].default_value = 60; bp = t.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.6
    tc = t.nodes.new('ShaderNodeTexCoord'); t.links.new(tc.outputs['Object'], wv.inputs['Vector']); t.links.new(wv.outputs['Fac'], bp.inputs['Height']); t.links.new(bp.outputs['Normal'], rb.inputs['Normal'])
    box((1.4, 0.012, 0.04), (0, -0.152, -0.02), rib, bevel=0.003)        # ribbed chrome edge
    ck, cb = mat('checker', **{'Roughness': 0.15, 'Coat Weight': 0.5}); t = ck.node_tree
    ch = t.nodes.new('ShaderNodeTexChecker'); ch.inputs['Scale'].default_value = 26; ch.inputs['Color1'].default_value = s2l('#C3DBA8'); ch.inputs['Color2'].default_value = s2l('#FBFAF6')
    tc = t.nodes.new('ShaderNodeTexCoord'); t.links.new(tc.outputs['Object'], ch.inputs['Vector']); t.links.new(ch.outputs['Color'], cb.inputs['Base Color'])
    box((1.6, 0.02, 0.8), (0, 0.24, 0.3), ck)
    box((0.07, 0.045, 0.085), (-0.19, 0.1, 0.0425), chrome(0.18), bevel=0.006)   # napkin dispenser
    gl, _ = mat('glass', **{'Base Color': (1, 1, 1, 1), 'Roughness': 0.02, 'Transmission Weight': 1.0, 'IOR': 1.45})
    shake, _ = mat('shake', **{'Base Color': s2l('#F7C9D6'), 'Roughness': 0.6, 'Subsurface Weight': 0.3})
    cream, _ = mat('cream', **{'Base Color': s2l('#FFFDF8'), 'Roughness': 0.7}); cherry, _ = mat('cherry', **{'Base Color': s2l('#D3123A'), 'Roughness': 0.15, 'Coat Weight': 1})
    cyl(0.03, 0.11, (0.19, 0.1, 0.055), gl); cyl(0.027, 0.095, (0.19, 0.1, 0.05), shake); ball(0.03, (0.19, 0.1, 0.11), cream); ball(0.008, (0.19, 0.1, 0.142), cherry)
    tube([(0.2, 0.1, 0.06), (0.21, 0.1, 0.17)], 0.003, chrome(0.2))
    area('key', (0.1, -0.35, 0.45), 0.5, 40, col=(1, 0.95, 0.9)); area('neon', (0, 0.2, 0.35), 0.6, 18, col=(1, 0.55, 0.7))
    camera((0.0, -0.5, 0.07), (0.0, 0.0, 0.04), 52)
else:
    # the birthday that never ends: the egg crowned on a frosted cake, candles that never burn down
    wall = plaster('wall', s2l('#F2BFCC')); box((2.0, 0.05, 1.2), (0, 0.4, 0.3), wall); box((2.0, 1.4, 0.02), (0, 0, -0.17), plaster('table', s2l('#ECE6DB')))
    fr, fb = mat('frost', **{'Base Color': s2l('#F7D3DD'), 'Roughness': 0.55, 'Subsurface Weight': 0.2, 'Sheen Weight': 0.3})
    bead, _ = mat('bead', **{'Base Color': s2l('#FFFFFF'), 'Roughness': 0.5, 'Subsurface Weight': 0.2})
    cyl(0.13, 0.09, (0, 0, -0.045), fr, 128)
    for k in range(70):
        a = 2 * math.pi * k / 70; ball(0.0075, (0.13 * math.cos(a), 0.13 * math.sin(a), 0.0), bead); ball(0.0075, (0.13 * math.cos(a), 0.13 * math.sin(a), -0.088), bead)
    stand, _ = mat('stand', **{'Base Color': s2l('#A8D3EF'), 'Roughness': 0.3, 'Coat Weight': 0.8})
    cyl(0.16, 0.008, (0, 0, -0.094), stand, 128); cyl(0.025, 0.07, (0, 0, -0.13), stand)
    st, sb = mat('candle', **{'Roughness': 0.4}); t = st.node_tree
    wv = t.nodes.new('ShaderNodeTexWave'); wv.bands_direction = 'Z'; wv.inputs['Scale'].default_value = 3; wv.inputs['Distortion'].default_value = 0
    tc = t.nodes.new('ShaderNodeTexCoord'); t.links.new(tc.outputs['Object'], wv.inputs['Vector']); rp = t.nodes.new('ShaderNodeValToRGB'); rp.color_ramp.interpolation = 'CONSTANT'
    rp.color_ramp.elements[1].position = 0.5; rp.color_ramp.elements[0].color = s2l('#FFFFFF'); rp.color_ramp.elements[1].color = s2l('#1A5FD6')
    t.links.new(wv.outputs['Fac'], rp.inputs['Fac']); t.links.new(rp.outputs['Color'], sb.inputs['Base Color'])
    fl, flb = mat('flame', **{'Emission Color': s2l('#FFC46B'), 'Emission Strength': 25})
    for k in range(6):
        a = 2 * math.pi * k / 6 + 0.3; x, y = 0.085 * math.cos(a), 0.085 * math.sin(a)
        c = cyl(0.004, 0.06, (x, y, 0.03), st, 16); f = ball(0.005, (x, y, 0.069), fl); f.scale = (1, 1, 1.9)
        pl = bpy.data.lights.new('f', 'POINT'); pl.energy = 0.4; pl.color = (1, 0.75, 0.4); pl.shadow_soft_size = 0.004; po = bpy.data.objects.new('f', pl); C.objects.link(po); po.location = (x, y, 0.072)
    cols = ['#60B0E0', '#8AB469', '#FFFFFF', '#1A5FD6', '#D7D1C6']; sms = [mat('spr' + c, **{'Base Color': s2l(c), 'Roughness': 0.3})[0] for c in cols]
    for k in range(260):
        r = random.uniform(0.045, 0.12); a = random.uniform(0, 2 * math.pi)
        o = cyl(0.0016, 0.007, (r * math.cos(a), r * math.sin(a), 0.0016), random.choice(sms), 8); o.rotation_euler = (math.pi / 2, 0, random.uniform(0, math.pi))
    sun((math.radians(45), 0, math.radians(-30)), 3.0, col=(1, 0.93, 0.85), angle=4)
    area('fill', (-0.4, -0.4, 0.2), 0.6, 8)
    camera((0.0, -0.6, 0.12), (0.0, 0.0, 0.02), 50)

scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = SAMPLES; scene.cycles.use_denoising = True
scene.cycles.use_adaptive_sampling = True; scene.render.resolution_x = RX; scene.render.resolution_y = RY
scene.view_settings.view_transform = 'AgX'; scene.view_settings.look = 'AgX - Medium High Contrast'
scene.render.filepath = OUT; bpy.ops.render.render(write_still=True); print('done', OUT)

# YOJO "silversmith's egg stand": shop sign, hang tags, and the shopfront. SCENE = sign | tag | front
import os, math, json
import numpy as np
import bpy, bmesh, mathutils
HERE = os.path.dirname(os.path.abspath(__file__)); SHOP = os.path.join(HERE, '..', 'shop')
E = os.environ.get; G = lambda k, d: float(E(k, d))
SCENE = E('SCENE', 'sign'); OUT = E('OUT', os.path.join(SHOP, SCENE + '.png'))
RX, RY = int(E('RX', '900')), int(E('RY', '1200')); SAMPLES = int(E('SAMPLES', '24'))
bpy.ops.wm.read_factory_settings(use_empty=True); scene = bpy.context.scene; C = bpy.context.collection
def s2l(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)
def mat(name, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    for k, v in kw.items():
        if k in b.inputs: b.inputs[k].default_value = v
    return m, b
lin = lambda n: tuple(map(float, json.load(open(os.path.join(HERE, f'cm_{n}.json')))['SKIN_LIN'].split(','))) + (1.0,)
SKY = lin('sky')
def foil(name, base_kw, mask, foil_col=(0.86, 0.87, 0.89, 1), uvmap=True):
    # base material with silver foil wherever the mask is white; foil slightly raised
    m, b = mat(name, **base_kw); t = m.node_tree
    tx = t.nodes.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load(mask); tx.image.colorspace_settings.name = 'Non-Color'; tx.extension = 'CLIP'
    fb = t.nodes.new('ShaderNodeBsdfPrincipled'); fb.inputs['Base Color'].default_value = foil_col; fb.inputs['Metallic'].default_value = 1.0; fb.inputs['Roughness'].default_value = G('FOILR', '0.22')
    mx = t.nodes.new('ShaderNodeMixShader'); t.links.new(tx.outputs['Color'], mx.inputs['Fac'])
    out = t.nodes['Material Output']; t.links.new(b.outputs[0], mx.inputs[1]); t.links.new(fb.outputs[0], mx.inputs[2]); t.links.new(mx.outputs[0], out.inputs['Surface'])
    bp = t.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.6; bp.inputs['Distance'].default_value = 0.0004
    t.links.new(tx.outputs['Color'], bp.inputs['Height']); t.links.new(bp.outputs['Normal'], fb.inputs['Normal'])
    return m
def box(name, size, loc, m_, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.active_object; o.name = name; o.scale = size
    bpy.ops.object.transform_apply(scale=True); o.data.materials.append(m_)
    if bevel: bv = o.modifiers.new('b', 'BEVEL'); bv.width = bevel; bv.segments = 3
    return o
def uv_front(o, axis='y'):
    # planar UV over the object's bounding box, facing -y (or +z for 'z')
    me = o.data
    while me.uv_layers: me.uv_layers.remove(me.uv_layers[0])
    uv = me.uv_layers.new(name='UVMap'); vs = np.array([v.co for v in me.vertices])
    a, b_ = (0, 2) if axis == 'y' else (0, 1)
    lo, hi = vs.min(0), vs.max(0)
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = ((co[a] - lo[a]) / (hi[a] - lo[a]), (co[b_] - lo[b_]) / (hi[b_] - lo[b_]))
plaster, pb = mat('plaster', **{'Base Color': s2l('#F3F2EF'), 'Roughness': 0.9, 'Specular IOR Level': 0.2})
nz = plaster.node_tree.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 300; nz.inputs['Detail'].default_value = 6
bpn = plaster.node_tree.nodes.new('ShaderNodeBump'); bpn.inputs['Strength'].default_value = 0.08
plaster.node_tree.links.new(nz.outputs['Fac'], bpn.inputs['Height']); plaster.node_tree.links.new(bpn.outputs['Normal'], pb.inputs['Normal'])
chrome, _ = mat('chrome', **{'Base Color': (0.93, 0.94, 0.95, 1), 'Metallic': 1.0, 'Roughness': 0.08})
acrylic_kw = {'Base Color': SKY, 'Roughness': 0.12, 'Coat Weight': 1.0, 'Coat Roughness': 0.03, 'Specular IOR Level': 0.5}
def plaque(w, h, t, loc, mask):
    p = box('plaque', (w, t, h), loc, foil('plaque', acrylic_kw, mask), bevel=0.002); uv_front(p)
    for sx in (-1, 1):
        for sz in (-1, 1):
            bpy.ops.mesh.primitive_cylinder_add(radius=0.009, depth=0.022, vertices=48, location=(loc[0] + sx * (w / 2 - 0.035), loc[1] - t / 2 - 0.006, loc[2] + sz * (h / 2 - 0.035)), rotation=(math.pi / 2, 0, 0))
            s = bpy.context.active_object; s.data.materials.append(chrome); bv = s.modifiers.new('b', 'BEVEL'); bv.width = 0.002; bv.segments = 4
    return p
def area(n, loc, s, e, col=(1, 1, 1), tgt=(0, 0, 0), sy=None):
    ld = bpy.data.lights.new(n, 'AREA'); ld.size = s; ld.energy = e; ld.color = col
    if sy: ld.shape = 'RECTANGLE'; ld.size_y = sy
    ob = bpy.data.objects.new(n, ld); C.objects.link(ob); ob.location = loc; ob.visible_camera = False
    ob.rotation_euler = mathutils.Vector(np.array(tgt) - np.array(loc)).to_track_quat('-Z', 'Y').to_euler()
def camera(loc, tgt, lens):
    cd = bpy.data.cameras.new('cam'); cd.lens = lens; cam = bpy.data.objects.new('cam', cd); C.objects.link(cam); scene.camera = cam
    cam.location = loc; cam.rotation_euler = (mathutils.Vector(tgt) - mathutils.Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
world = bpy.data.worlds.new('w'); scene.world = world; world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = s2l(E('SKYC', '#EEF1F4')); world.node_tree.nodes['Background'].inputs['Strength'].default_value = G('WORLD', '0.6')

if SCENE == 'sign':
    box('wall', (2.0, 0.05, 2.0), (0, 0.025, 0), plaster)
    plaque(0.30, 0.40, 0.008, (0, -0.024, 0), os.path.join(SHOP, 'sign-mask.png'))
    area('key', (-1.2, -1.4, 1.2), 1.6, G('KEY', '18'), tgt=(0, 0, 0))
    area('fill', (1.4, -1.6, 0.2), 1.6, G('FILL', '5'), tgt=(0, 0, 0))
    camera((0.32, -0.95, 0.05), (0.0, 0, -0.005), G('LENS', '55'))
elif SCENE == 'tag':
    box('table', (2.0, 2.0, 0.02), (0, 0, -0.01), plaster)
    # back card in sky, front card white with foil; a strap with the three icons
    back, _ = mat('backcard', **{'Base Color': SKY, 'Roughness': 0.8, 'Sheen Weight': 0.3})
    card_w, card_h = 0.055, 0.095
    def card(name, m_, loc, rz):
        o = box(name, (card_w, card_h, 0.0008), loc, m_, bevel=0.0004); o.rotation_euler = (0, 0, math.radians(rz)); uv_front(o, 'z'); return o
    card('back', back, (0.012, 0.004, 0.0006), -9)
    fm = foil('front', {'Base Color': s2l('#F7F7F4'), 'Roughness': 0.85}, os.path.join(SHOP, 'tag-mask.png'), foil_col=(0.62, 0.63, 0.66, 1))
    card('front', fm, (-0.006, 0.0, 0.0016), 3)
    sm = foil('strap', {'Base Color': s2l('#FBFBF9'), 'Roughness': 0.55, 'Sheen Weight': 0.6}, os.path.join(SHOP, 'strap-mask.png'), foil_col=(0.45, 0.46, 0.5, 1))
    s = box('strap', (0.016, 0.068, 0.0012), (0.026, -0.006, 0.0026), sm, bevel=0.0005); s.rotation_euler = (0, 0, math.radians(-14)); uv_front(s, 'z')
    # cord through the card holes, tied in a loop
    cu = bpy.data.curves.new('cord', 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 0.0009; cu.bevel_resolution = 6
    sp = cu.splines.new('BEZIER'); pts = [(0.0, 0.046, 0.003), (0.006, 0.07, 0.004), (0.028, 0.085, 0.004), (0.045, 0.072, 0.003), (0.038, 0.05, 0.003), (0.018, 0.04, 0.003)]
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts): bp.co = p; bp.handle_left_type = bp.handle_right_type = 'AUTO'
    cord = bpy.data.objects.new('cord', cu); C.objects.link(cord); cm_, _ = mat('cord', **{'Base Color': SKY, 'Roughness': 0.6, 'Sheen Weight': 0.8}); cu.materials.append(cm_)
    area('key', (-0.5, -0.4, 0.9), 0.8, G('KEY', '3'), tgt=(0, 0, 0)); area('fill', (0.6, 0.3, 0.5), 0.8, G('FILL', '0.8'), tgt=(0, 0, 0))
    camera((0.02, -0.04, 0.32), (0.012, 0.012, 0), G('LENS', '70'))
elif SCENE == 'skins':
    sw, _ = mat('sweep', **{'Base Color': s2l('#F2F3F4'), 'Roughness': 0.95})
    bpy.ops.mesh.primitive_plane_add(size=6); bpy.context.active_object.data.materials.append(sw)
    box('wallb', (6, 0.02, 3), (0, 0.6, 1.5), sw)
    with bpy.data.libraries.load(os.path.join(HERE, 'mk', 'egg_c.blend')) as (src, dst):
        want = [n for n in src.objects if n in ('skin', 'head', 'slot')]; dst.objects = list(want)
    lib = dict(zip(want, dst.objects))
    hm, hb = mat('head', **{'Base Color': (0.96, 0.92, 0.86, 1), 'Metallic': 1.0, 'Roughness': 0.1})
    t = hm.node_tree; at = t.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'carve'; mc = t.nodes.new('ShaderNodeMix'); mc.data_type = 'RGBA'
    t.links.new(at.outputs['Fac'], mc.inputs['Factor']); mc.inputs[6].default_value = (0.96, 0.92, 0.86, 1); mc.inputs[7].default_value = (0.02, 0.02, 0.02, 1); t.links.new(mc.outputs[2], hb.inputs['Base Color'])
    blk, _ = mat('slot', **{'Base Color': (0.01, 0.01, 0.01, 1)})
    for i, cname in enumerate(['sky', 'rose', 'sage', 'cloud', 'cobalt']):
        col = s2l('#1A5FD6') if cname == 'cobalt' else lin(cname)
        sk, _ = mat('sk' + cname, **{'Base Color': col, 'Roughness': 0.62, 'Sheen Weight': 0.55, 'Sheen Roughness': 0.35, 'Subsurface Weight': 0.06, 'Subsurface Scale': 0.002})
        root = bpy.data.objects.new('egg', None); C.objects.link(root)
        for nm_, mt in (('skin', sk), ('head', hm), ('slot', blk)):
            o = lib[nm_].copy(); C.objects.link(o)
            for sl in o.material_slots: sl.link = 'OBJECT'; sl.material = mt
            o.parent = root
        root.location = ((i - 2) * 0.085, 0, 0)
    area('key', (-0.8, -1.0, 1.0), 1.4, G('KEY', '14'), tgt=(0, 0, 0.04)); area('fill', (1.0, -0.8, 0.4), 1.2, G('FILL', '4'), tgt=(0, 0, 0.04))
    area('top', (0, -0.1, 1.2), 0.8, G('TOP', '6'), tgt=(0, 0, 0.05))
    camera((0.0, -0.95, 0.24), (0, 0, 0.045), G('LENS', '50'))
elif SCENE == 'front':
    FW, FH = 6.0, 4.2
    WX0, WX1, WZ0, WZ1 = -0.6, 1.9, 0.75, 2.75          # window opening
    DX0, DX1, DZ1 = -1.75, -0.85, 2.75                  # door opening
    # facade built from slabs round the openings
    T = 0.25
    def slab(x0, x1, z0, z1): box('f', (x1 - x0, T, z1 - z0), ((x0 + x1) / 2, T / 2, (z0 + z1) / 2), plaster)
    slab(-FW / 2, DX0, 0, FH); slab(DX1, WX0, 0, FH); slab(WX1, FW / 2, 0, FH); slab(DX0, DX1, DZ1, FH); slab(WX0, WX1, WZ1, FH); slab(WX0, WX1, 0, WZ0)
    box('cornice', (FW, 0.36, 0.22), (0, -0.05, FH - 0.32), plaster, bevel=0.01); box('cornice2', (FW, 0.30, 0.06), (0, -0.03, FH - 0.48), plaster)
    skyp, _ = mat('frame', **{'Base Color': SKY, 'Roughness': 0.35, 'Coat Weight': 0.6, 'Coat Roughness': 0.1})
    fw = 0.09
    def frame(x0, x1, z0, z1, depth=0.12):
        for (cx, cz, sx, sz) in (((x0 + x1) / 2, z1 - fw / 2, x1 - x0, fw), ((x0 + x1) / 2, z0 + fw / 2, x1 - x0, fw), (x0 + fw / 2, (z0 + z1) / 2, fw, z1 - z0), (x1 - fw / 2, (z0 + z1) / 2, fw, z1 - z0)):
            box('fr', (sx, depth, sz), (cx, -0.02, cz), skyp)
    frame(WX0, WX1, WZ0, WZ1); frame(DX0, DX1, 0, DZ1)
    box('kick', (WX1 - WX0 + 0.06, 0.08, WZ0), ((WX0 + WX1) / 2, -0.06, WZ0 / 2), skyp, bevel=0.004)
    box('doorrail', (DX1 - DX0 - 2 * fw, 0.05, 0.08), ((DX0 + DX1) / 2, -0.01, 1.05), skyp)
    # glass
    gl, _ = mat('glass', **{'Base Color': (1, 1, 1, 1), 'Roughness': 0.0, 'Transmission Weight': 1.0, 'IOR': 1.05})
    box('glassW', (WX1 - WX0, 0.006, WZ1 - WZ0), ((WX0 + WX1) / 2, 0.02, (WZ0 + WZ1) / 2), gl); box('glassD', (DX1 - DX0, 0.006, DZ1), ((DX0 + DX1) / 2, 0.02, DZ1 / 2), gl)
    # the room behind: white walls, pale floor, ceiling strip lights
    RD = 2.6; floor_m, _ = mat('floor', **{'Base Color': s2l('#E7E8EA'), 'Roughness': 0.35})
    box('rfloor', (FW, RD, 0.02), (0, T + RD / 2, -0.01), floor_m); box('rback', (FW, 0.05, FH), (0, T + RD, FH / 2), plaster)
    box('rceil', (FW, RD, 0.05), (0, T + RD / 2, 3.2), plaster)
    box('rl', (0.05, RD, FH), (-FW / 2, T + RD / 2, FH / 2), plaster); box('rr', (0.05, RD, FH), (FW / 2, T + RD / 2, FH / 2), plaster)
    emm = bpy.data.materials.new('strip'); emm.use_nodes = True; en = emm.node_tree.nodes; en.remove(en['Principled BSDF'])
    es = en.new('ShaderNodeEmission'); es.inputs['Strength'].default_value = G('STRIP', '5'); emm.node_tree.links.new(es.outputs[0], en['Material Output'].inputs['Surface'])
    for yy in (0.8, 1.6, 2.3): box('led', (3.4, 0.05, 0.02), (0.4, T + yy, 3.17), emm)
    # display: a long white plinth in the window with five eggs and a sky sign on the back wall
    box('plinth', (2.2, 0.55, 0.85), ((WX0 + WX1) / 2, T + 0.45, 0.425), plaster, bevel=0.01)
    with bpy.data.libraries.load(os.path.join(HERE, 'mk', 'egg_c.blend')) as (src, dst):
        want = [n for n in src.objects if n in ('skin', 'head', 'slot')]; dst.objects = list(want)
    lib = dict(zip(want, dst.objects))
    def carved(name):
        m, b = mat(name, **{'Base Color': (0.96, 0.92, 0.86, 1), 'Metallic': 1.0, 'Roughness': 0.1})
        t = m.node_tree; at = t.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'carve'
        mc = t.nodes.new('ShaderNodeMix'); mc.data_type = 'RGBA'; t.links.new(at.outputs['Fac'], mc.inputs['Factor'])
        mc.inputs[6].default_value = (0.96, 0.92, 0.86, 1); mc.inputs[7].default_value = (0.02, 0.02, 0.02, 1); t.links.new(mc.outputs[2], b.inputs['Base Color']); return m
    hm = carved('head'); blk, _ = mat('slot', **{'Base Color': (0.01, 0.01, 0.01, 1)})
    cols = ['sage', 'rose', 'sky', 'cloud', 'cobalt']
    for i, cname in enumerate(cols):
        col = s2l('#1A5FD6') if cname == 'cobalt' else lin(cname)
        sk, _ = mat('sk' + cname, **{'Base Color': col, 'Roughness': 0.62, 'Sheen Weight': 0.55, 'Sheen Roughness': 0.35, 'Subsurface Weight': 0.06, 'Subsurface Scale': 0.002})
        root = bpy.data.objects.new('egg', None); C.objects.link(root)
        for nm_, mt in (('skin', sk), ('head', hm), ('slot', blk)):
            o = lib[nm_].copy(); C.objects.link(o)
            for sl in o.material_slots: sl.link = 'OBJECT'; sl.material = mt
            o.parent = root
        root.scale = (G('EGG_S', '4.2'),) * 3      # display eggs scaled up so they read from the street
        root.location = ((WX0 + WX1) / 2 + (i - 2) * 0.42, T + 0.42, 0.85); root.rotation_euler = (0, 0, math.radians(-90 + 90))
    plaque(1.0, 1.3, 0.02, ((WX0 + WX1) / 2, T + RD - 0.04, 1.85), os.path.join(SHOP, 'sign-mask.png'))
    # outside sign by the window, and the pavement
    plaque(0.42, 0.56, 0.012, (WX1 + 0.55, -0.02, 1.9), os.path.join(SHOP, 'sign-mask.png'))
    pave, ppb = mat('pave', **{'Base Color': s2l('#CFCFCD'), 'Roughness': 0.85})
    br = pave.node_tree.nodes.new('ShaderNodeTexBrick'); br.inputs['Scale'].default_value = 1.4; br.inputs['Mortar Size'].default_value = 0.005
    br.inputs['Color1'].default_value = s2l('#D2D2D0'); br.inputs['Color2'].default_value = s2l('#C6C6C4'); br.inputs['Mortar'].default_value = s2l('#B5B5B3')
    pave.node_tree.links.new(br.outputs['Color'], ppb.inputs['Base Color'])
    box('pavement', (12, 4, 0.04), (0, -2, -0.02), pave)
    sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = G('SUN', '1.6'); sun.angle = math.radians(8); sun.color = (1.0, 0.97, 0.92)
    so = bpy.data.objects.new('sun', sun); C.objects.link(so); so.rotation_euler = (math.radians(55), 0, math.radians(-30))
    area('fill', (0, -6, 2.5), 6, G('FILL', '60'), tgt=(0, 0, 1.6))
    area('inside', (0.4, T + 1.2, 3.0), 2.5, G('INSIDE', '40'), tgt=(0.4, T + 1.2, 0))
    # neighbours either side so the shop sits in a street
    nb, _ = mat('nb', **{'Base Color': s2l('#E4E1DC'), 'Roughness': 0.9}); box('nl', (3, 0.3, 5), (-4.5, 0.15, 2.5), nb); box('nr', (3, 0.3, 5), (4.5, 0.15, 2.5), nb)
    camera((0.1, -5.6, 1.5), (0.1, 0, 1.9), G('LENS', '30'))
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = SAMPLES; scene.cycles.use_denoising = True
scene.cycles.use_adaptive_sampling = True; scene.render.resolution_x = RX; scene.render.resolution_y = RY
scene.view_settings.view_transform = 'Standard'; scene.view_settings.exposure = G('EXPO', '0')
scene.render.filepath = OUT; bpy.ops.render.render(write_still=True); print('done', OUT)

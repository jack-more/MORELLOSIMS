# ZUMA vial, rendered physically (Blender Cycles via the bpy module).
#   bpyenv/bin/python cyc/vial.py SHOT NO OUT [W H SAMPLES]
#   SHOT: front | lot | float | spin:<frame>/<frames>
# Units are centimetres: a 10 mL tubular vial, 24 mm body, 20 mm aluminium crimp, flip-off cap, freeze-dried cake.
# Light: a studio HDRI, a big soft box camera-left, a strip camera-right, and low sun through palm fronds on the sweep.
import bpy, bmesh, math, sys, os, random
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__)); TEX = os.path.join(HERE, 'tex')
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
SHOT, NO, OUT = args[0], args[1], args[2]
W, H, SAMPLES = (int(args[3]), int(args[4]), int(args[5])) if len(args) > 5 else (720, 960, 160)
AREA = {'01': 'metabolic', '02': 'tissue', '03': 'tissue', '04': 'dermal', '05': 'endocrine', '06': 'metabolic'}[NO.split('+')[0]]
TONES = {'metabolic': ('#A3CEFF', '#1F4FD8', '#0B1F5C'), 'tissue': ('#ABE9C3', '#0E9A5B', '#0A3B26'), 'dermal': ('#FFB7C5', '#FF5A1F', '#9E1717'), 'endocrine': ('#FFE97A', '#F5A300', '#5E3C00')}
# the sweep: a dusty mid tone of the area, darker than the label's light band so the label always separates from it
SWEEP = {'metabolic': '#5E7FBE', 'tissue': '#5F8F77', 'dermal': '#B9706B', 'endocrine': '#B8914A'}
def lin(hexc):
    h = hexc.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c) + (1.0,)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ---------- geometry helpers ----------
def lathe(name, prof, seg=160, closed=False, smooth=True):
    """prof: [(r, y), ...] in order; revolves around the Y axis (Blender Z up: r in XY plane, y -> Z)."""
    bm = bmesh.new(); rings = []
    for (r, y) in prof:
        ring = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), y)))
        rings.append(ring)
    n = len(rings)
    for i in range(n - 1 + (1 if closed else 0)):
        A, B = rings[i], rings[(i + 1) % n]
        for k in range(seg):
            try: bm.faces.new((A[k], A[(k + 1) % seg], B[(k + 1) % seg], B[k]))
            except ValueError: pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    if smooth:
        for p in me.polygons: p.use_smooth = True
    return ob

def mat(name, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    for k, v in kw.items():
        b.inputs[k].default_value = v
    return m, b

def make_vial(NO):
    AREA = {'01': 'metabolic', '02': 'tissue', '03': 'tissue', '04': 'dermal', '05': 'endocrine', '06': 'metabolic'}[NO.split('+')[0]]
    # ---------- the vial (Z up). Body 0 .. 4.55, shoulder to the neck, crimp and cap on top ----------
    R, T = 1.2, 0.11            # outer radius, wall thickness
    BODY = 4.55                 # height of the straight body
    outer = [(0.0, 0.05), (0.9, 0.03), (1.08, 0.0), (1.17, 0.04), (1.2, 0.14)] + [(R, BODY)] + \
            [(1.19, BODY + 0.12), (1.14, BODY + 0.26), (1.03, BODY + 0.4), (0.9, BODY + 0.5), (0.86, BODY + 0.58), (0.86, BODY + 0.82), (0.98, BODY + 0.86), (1.0, BODY + 0.95), (1.0, BODY + 1.12), (0.75, BODY + 1.14)]
    inner = [(0.75 - T + 0.02, BODY + 1.14), (0.75, BODY + 1.1), (0.75, BODY + 0.55), (0.79, BODY + 0.48), (0.93, BODY + 0.37), (1.04, BODY + 0.24), (R - T, BODY + 0.08), (R - T, 0.26), (1.03, 0.19), (0.8, 0.2), (0.0, 0.22)]
    glass = lathe('glass', outer + inner, seg=192)
    gm, gb = mat('glass', **{'Base Color': (1, 1, 1, 1), 'Roughness': 0.0, 'IOR': 1.51, 'Transmission Weight': 1.0})
    gb.inputs['Specular IOR Level'].default_value = 0.5
    # light passes through the glass to the cake and stopper (shadow and diffuse rays see clear glass), the camera still sees real glass
    gnt = gm.node_tree; out = gnt.nodes['Material Output']; lp = gnt.nodes.new('ShaderNodeLightPath'); mx = gnt.nodes.new('ShaderNodeMixShader'); tr = gnt.nodes.new('ShaderNodeBsdfTransparent')
    orr = gnt.nodes.new('ShaderNodeMath'); orr.operation = 'MAXIMUM'; gnt.links.new(lp.outputs['Is Shadow Ray'], orr.inputs[0]); gnt.links.new(lp.outputs['Is Diffuse Ray'], orr.inputs[1])
    gnt.links.new(orr.outputs['Value'], mx.inputs['Fac']); gnt.links.new(gb.outputs['BSDF'], mx.inputs[1]); gnt.links.new(tr.outputs['BSDF'], mx.inputs[2]); gnt.links.new(mx.outputs['Shader'], out.inputs['Surface'])
    glass.data.materials.append(gm)

    # label: full wrap, art 3200 x 1340, so its height follows the circumference
    LR = R + 0.004; circ = 2 * math.pi * LR; LH = circ * 1340 / 3200; LZ0 = (BODY - LH) / 2 + 0.08
    lab = lathe('label', [(LR, LZ0), (LR, LZ0 + LH)], seg=256)
    # UVs: u around, v up. Rotate so the front panel (art x = 1600 of 3200) faces the camera (-Y)
    me = lab.data; uv = me.uv_layers.new(name='UV')
    for poly in me.polygons:
        for li in poly.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co; a = math.atan2(v.y, v.x)
            u = ((a + math.pi / 2) / (2 * math.pi) + 0.5) % 1.0
            uv.data[li].uv = (u, (v.z - LZ0) / LH)
    # fix the seam: faces that straddle u=0/1 get their small u's lifted past 1
    for poly in me.polygons:
        us = [uv.data[li].uv[0] for li in poly.loop_indices]
        if max(us) - min(us) > 0.5:
            for li in poly.loop_indices:
                if uv.data[li].uv[0] < 0.5: uv.data[li].uv = (uv.data[li].uv[0] + 1, uv.data[li].uv[1])
    lm, lb = mat('label', **{'Roughness': 0.38, 'Coat Weight': 0.35, 'Coat Roughness': 0.18})
    nt = lm.node_tree; img = nt.nodes.new('ShaderNodeTexImage'); img.image = bpy.data.images.load(os.path.join(TEX, f'label-{NO}.png')); img.interpolation = 'Cubic'; img.extension = 'CLIP'
    nt.links.new(img.outputs['Color'], lb.inputs['Base Color']); nt.links.new(img.outputs['Alpha'], lb.inputs['Alpha'])
    # paper tooth: a fine noise bump
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 900; bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.06
    nt.links.new(nz.outputs['Fac'], bump.inputs['Height']); nt.links.new(bump.outputs['Normal'], lb.inputs['Normal'])
    lm.blend_method = 'HASHED' if hasattr(lm, 'blend_method') else None
    # the back of the label is plain white paper (seen through the clear gap at the seam)
    lout = nt.nodes['Material Output']; geo = nt.nodes.new('ShaderNodeNewGeometry'); wp = nt.nodes.new('ShaderNodeBsdfDiffuse'); wp.inputs['Color'].default_value = lin('#EFEDE7')
    lmx = nt.nodes.new('ShaderNodeMixShader'); nt.links.new(geo.outputs['Backfacing'], lmx.inputs['Fac']); nt.links.new(lb.outputs['BSDF'], lmx.inputs[1]); nt.links.new(wp.outputs['BSDF'], lmx.inputs[2])
    tr2 = nt.nodes.new('ShaderNodeBsdfTransparent'); amx = nt.nodes.new('ShaderNodeMixShader'); nt.links.new(img.outputs['Alpha'], amx.inputs['Fac']); nt.links.new(tr2.outputs['BSDF'], amx.inputs[1]); nt.links.new(lmx.outputs['Shader'], amx.inputs[2])
    nt.links.new(amx.outputs['Shader'], lout.inputs['Surface'])
    lab.data.materials.append(lm)

    # rubber stopper in the neck (seen through the glass, under the crimp)
    stp = lathe('stopper', [(0.0, BODY + 0.5), (0.72, BODY + 0.5), (0.74, BODY + 0.62), (0.74, BODY + 1.1), (0.95, BODY + 1.12), (0.95, BODY + 1.2), (0.0, BODY + 1.2)], seg=96)
    sm, sb = mat('rubber', **{'Base Color': lin('#9A9C9E'), 'Roughness': 0.62}); stp.data.materials.append(sm)
    # aluminium crimp: rolled under the lip, brushed
    crimp = lathe('crimp', [(0.0, BODY + 1.47), (0.62, BODY + 1.47), (1.03, BODY + 1.46), (1.055, BODY + 1.42), (1.055, BODY + 0.93), (1.03, BODY + 0.88), (0.95, BODY + 0.86), (0.93, BODY + 0.9)], seg=160)
    cm, cb = mat('alu', **{'Base Color': lin('#D7DADD'), 'Metallic': 1.0, 'Roughness': 0.16, 'Anisotropic': 0.7})
    crimp.data.materials.append(cm)
    # flip-off cap: glossy moulded plastic in the area's deep tone, slightly domed
    capc = TONES[AREA][2]
    cap = lathe('cap', [(0.0, BODY + 1.48), (1.06, BODY + 1.48), (1.1, BODY + 1.52), (1.11, BODY + 1.6), (1.1, BODY + 1.79), (1.07, BODY + 1.83), (0.95, BODY + 1.845), (0.0, BODY + 1.86)], seg=160)
    pm, pb = mat('cap', **{'Base Color': lin(capc), 'Roughness': 0.22, 'Coat Weight': 0.7, 'Coat Roughness': 0.08})
    cap.data.materials.append(pm)

    # the freeze-dried cake: a porous puck, shrunk away from the wall, a slightly sunken cracked top
    cake = lathe('cake', [(0.0, 0.24), (0.96, 0.24), (0.99, 0.3), (0.99, 0.98), (0.95, 1.03), (0.6, 1.0), (0.0, 0.97)], seg=128)
    tex = bpy.data.textures.new('cakeNoise', 'CLOUDS'); tex.noise_scale = 0.18
    sub = cake.modifiers.new('sub', 'SUBSURF'); sub.levels = 2; sub.render_levels = 3
    dsp = cake.modifiers.new('disp', 'DISPLACE'); dsp.texture = tex; dsp.strength = 0.03; dsp.mid_level = 0.5
    km, kb = mat('cake', **{'Base Color': lin('#F2EFE8'), 'Roughness': 0.95, 'Subsurface Weight': 0.35, 'Subsurface Scale': 0.05})
    knt = km.node_tree; vor = knt.nodes.new('ShaderNodeTexVoronoi'); vor.feature = 'DISTANCE_TO_EDGE'; vor.inputs['Scale'].default_value = 3.2
    crk = knt.nodes.new('ShaderNodeMapRange'); crk.inputs['From Min'].default_value = 0.0; crk.inputs['From Max'].default_value = 0.035
    pore = knt.nodes.new('ShaderNodeTexNoise'); pore.inputs['Scale'].default_value = 140; pore.inputs['Detail'].default_value = 8
    mix = knt.nodes.new('ShaderNodeMath'); mix.operation = 'MULTIPLY'
    kbmp = knt.nodes.new('ShaderNodeBump'); kbmp.inputs['Strength'].default_value = 0.55
    knt.links.new(vor.outputs['Distance'], crk.inputs['Value']); knt.links.new(crk.outputs['Result'], mix.inputs[0]); knt.links.new(pore.outputs['Fac'], mix.inputs[1])
    knt.links.new(mix.outputs['Value'], kbmp.inputs['Height']); knt.links.new(kbmp.outputs['Normal'], kb.inputs['Normal'])
    # cracks read slightly darker
    ramp = knt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color = lin('#D9D3C7'); ramp.color_ramp.elements[1].color = lin('#F4F1EA')
    knt.links.new(crk.outputs['Result'], ramp.inputs['Fac']); knt.links.new(ramp.outputs['Color'], kb.inputs['Base Color'])
    cake.data.materials.append(km)

    vial = [glass, lab, stp, crimp, cap, cake]
    root = bpy.data.objects.new('vial', None); sc.collection.objects.link(root)
    for o in vial: o.parent = root
    return root, vial

if SHOT == 'lineup':
    roots = []
    for k, n in enumerate(['01', '02', '03', '04', '05', '06']):
        rr, _ = make_vial(n); rr.location.x = (k - 2.5) * 3.05; rr.rotation_euler = (0, 0, math.radians(-12 + k * 4)); roots.append(rr)
    root, vial = roots[2], []
elif SHOT == 'pair':
    a_, b_ = NO.split('+')
    r1, _ = make_vial(a_); r2, _ = make_vial(b_)
    r1.location = (-1.55, 0, 0); r1.rotation_euler = (0, 0, math.radians(-10))
    r2.location = (1.75, 2.2, 0); r2.rotation_euler = (0, 0, math.radians(8))
    root, vial = r1, []
elif SHOT == 'box':
    # the Collection: white board tray, a cut insert holding six vials upright, the printed lid leaning behind
    BX, BY, BZ, WT = 21.4, 7.6, 1.7, 0.16
    board, bbsdf = mat('board', **{'Base Color': lin('#F4F2EC'), 'Roughness': 0.72})
    bnt = board.node_tree; bn = bnt.nodes.new('ShaderNodeTexNoise'); bn.inputs['Scale'].default_value = 260; bbp = bnt.nodes.new('ShaderNodeBump'); bbp.inputs['Strength'].default_value = 0.05
    bnt.links.new(bn.outputs['Fac'], bbp.inputs['Height']); bnt.links.new(bbp.outputs['Normal'], bbsdf.inputs['Normal'])
    def cube(name, size, loc, m):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.active_object; o.name = name; o.scale = size; bpy.ops.object.transform_apply(scale=True)
        bv = o.modifiers.new('bev', 'BEVEL'); bv.width = 0.03; bv.segments = 3; o.data.materials.append(m); return o
    tray = cube('tray', (BX, BY, BZ), (0, 0, BZ / 2), board)
    cut = cube('cut', (BX - 2 * WT, BY - 2 * WT, BZ), (0, 0, BZ / 2 + WT), board)
    bl = tray.modifiers.new('hollow', 'BOOLEAN'); bl.object = cut; bl.operation = 'DIFFERENCE'; cut.hide_render = True; cut.hide_viewport = True
    ins = cube('insert', (BX - 2 * WT - 0.02, BY - 2 * WT - 0.02, 0.5), (0, 0, BZ - 0.55), board)
    xs = [(k - 2.5) * 3.35 for k in range(6)]
    for k, x in enumerate(xs):
        bpy.ops.mesh.primitive_cylinder_add(radius=1.27, depth=2, location=(x, 0, BZ - 0.55)); h = bpy.context.active_object; h.hide_render = True; h.hide_viewport = True
        m_ = ins.modifiers.new('hole%d' % k, 'BOOLEAN'); m_.object = h; m_.operation = 'DIFFERENCE'
    roots = []
    for k, n in enumerate(['01', '02', '03', '04', '05', '06']):
        rr, _ = make_vial(n); rr.location = (xs[k], 0, WT); rr.rotation_euler = (0, 0, math.radians(-6 + k * 2)); roots.append(rr)
    # lid: a shallow box, the printed top facing the camera, leaning on the back of the tray
    lid = cube('lid', (BX + 0.3, BY + 0.3, 0.7), (0, 0, 0), board)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0.352)); top = bpy.context.active_object; top.scale = (BX + 0.26, BY + 0.26, 1); bpy.ops.object.transform_apply(scale=True)
    lm2, lb2 = mat('lidprint', **{'Roughness': 0.55, 'Coat Weight': 0.15}); li = lm2.node_tree.nodes.new('ShaderNodeTexImage'); li.image = bpy.data.images.load(os.path.join(TEX, 'lid.png')); li.interpolation = 'Cubic'
    lm2.node_tree.links.new(li.outputs['Color'], lb2.inputs['Base Color']); top.data.materials.append(lm2); top.parent = lid
    lid.location = (0.4, BY / 2 + 3.4, 5.5); lid.rotation_euler = (math.radians(74), 0, math.radians(-2))
    root, vial = roots[2], []
elif SHOT.startswith('pack'):
    # one vial standing in front of its own carton on a stone ledge (pack = the vial's own carton; packset = four cartons)
    def carton(no, loc, rz):
        CW, CD, CH = 3.4, 3.4, 7.6; hw, hd = CW / 2, CD / 2
        bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UV')
        def V(x, y, z): return bm.verts.new((x, y, z))
        A = 4080.0; B = 3300.0
        def face(ps, uvs):
            f = bm.faces.new([V(*q) for q in ps])
            for lp, (px, py) in zip(f.loops, uvs): lp[uvl].uv = (px / A, 1 - py / B)
        # walls, each listed bottom-left, bottom-right, top-right, top-left as seen from outside
        face([(-hw, -hd, 0), (hw, -hd, 0), (hw, -hd, CH), (-hw, -hd, CH)], [(0, 2280), (1020, 2280), (1020, 0), (0, 0)])             # front -Y
        face([(hw, -hd, 0), (hw, hd, 0), (hw, hd, CH), (hw, -hd, CH)], [(1020, 2280), (2040, 2280), (2040, 0), (1020, 0)])           # right +X
        face([(hw, hd, 0), (-hw, hd, 0), (-hw, hd, CH), (hw, hd, CH)], [(2040, 2280), (3060, 2280), (3060, 0), (2040, 0)])           # back +Y
        face([(-hw, hd, 0), (-hw, -hd, 0), (-hw, -hd, CH), (-hw, hd, CH)], [(3060, 2280), (4080, 2280), (4080, 0), (3060, 0)])       # left -X
        face([(-hw, -hd, CH), (hw, -hd, CH), (hw, hd, CH), (-hw, hd, CH)], [(0, 3300), (1020, 3300), (1020, 2280), (0, 2280)])        # top
        face([(-hw, hd, 0), (hw, hd, 0), (hw, -hd, 0), (-hw, -hd, 0)], [(1020, 2280), (2040, 2280), (2040, 3300), (1020, 3300)])      # bottom
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new('carton'); bm.to_mesh(me); bm.free(); ob = bpy.data.objects.new('carton', me); sc.collection.objects.link(ob)
        bv = ob.modifiers.new('bev', 'BEVEL'); bv.width = 0.035; bv.segments = 3; bv.harden_normals = True
        cm_, cb_ = mat('carton%s' % no, **{'Roughness': 0.58, 'Coat Weight': 0.12, 'Coat Roughness': 0.35})
        cnt = cm_.node_tree; ci = cnt.nodes.new('ShaderNodeTexImage'); ci.image = bpy.data.images.load(os.path.join(TEX, 'carton-%s.png' % no)); ci.interpolation = 'Cubic'
        cnt.links.new(ci.outputs['Color'], cb_.inputs['Base Color'])
        cnz = cnt.nodes.new('ShaderNodeTexNoise'); cnz.inputs['Scale'].default_value = 700; cbp = cnt.nodes.new('ShaderNodeBump'); cbp.inputs['Strength'].default_value = 0.05
        cnt.links.new(cnz.outputs['Fac'], cbp.inputs['Height']); cnt.links.new(cbp.outputs['Normal'], cb_.inputs['Normal'])
        ob.data.materials.append(cm_); ob.location = loc; ob.rotation_euler = (0, 0, math.radians(rz)); return ob
    if SHOT == 'pack':
        carton(NO, (2.15, 1.7, 0), -24)
        root, vial = make_vial(NO); root.location = (-1.75, -1.9, 0); root.rotation_euler = (0, 0, math.radians(-9))
    else:
        nos = NO.split('+')
        for k, n in enumerate(nos):
            carton(n, ((k - (len(nos) - 1) / 2) * 4.25 + 2.2, 1.8 + (k % 2) * 0.7, 0), -14 + k * 7)
        rr, _ = make_vial(nos[0]); rr.location = (-7.7, -1.6, 0); rr.rotation_euler = (0, 0, math.radians(-8))
        root, vial = rr, []
else:
    root, vial = make_vial(NO)

# ---------- world, light, set ----------
world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True; wn = world.node_tree
env = wn.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(os.path.join(TEX, 'studio.hdr'))
mp = wn.nodes.new('ShaderNodeMapping'); tc = wn.nodes.new('ShaderNodeTexCoord'); mp.inputs['Rotation'].default_value[2] = math.radians(70)
wn.links.new(tc.outputs['Generated'], mp.inputs['Vector']); wn.links.new(mp.outputs['Vector'], env.inputs['Vector'])
bg = wn.nodes['Background']; bg.inputs['Strength'].default_value = 0.35; wn.links.new(env.outputs['Color'], bg.inputs['Color'])

def area(name, size, loc, power, look=(0, 0, 3.2), sx=None):
    l = bpy.data.lights.new(name, 'AREA'); l.shape = 'RECTANGLE'; l.size = size; l.size_y = sx or size; l.energy = power
    o = bpy.data.objects.new(name, l); sc.collection.objects.link(o); o.location = loc
    d = Vector(look) - Vector(loc); o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); return o
area('key', 6, (-14, -12, 10), 5200, sx=14)            # tall soft box camera-left: the long highlight down the glass
area('strip', 1.2, (13, -6, 6), 1800, sx=16)           # thin strip camera-right: the second highlight on the edge
area('top', 8, (0, 2, 18), 1600)                       # overhead fill on the cap and crimp

floating = SHOT == 'float' or SHOT.startswith('floatspin:')
PACK = SHOT.startswith('pack')
if not floating:
    # sweep: floor running into a curved wall, in the area's dusty mid tone
    prof = [(-40, 0.0, -30)] + [(0, 0, 0)]
    bm = bmesh.new(); pts = []
    for i in range(41):
        t = i / 40; yy = -30 + 50 * t
        pts.append((yy, 0.0)) if yy < 10 else None
    ys = [-40 + i for i in range(50)]
    path = []
    for y in ys:
        if y < 8: path.append((y, 0.0))
    for k in range(1, 25):
        a = k / 24 * math.pi / 2; path.append((8 + 10 * math.sin(a), 10 * (1 - math.cos(a))))
    for z in range(11, 60, 2): path.append((18, z))
    rows = []
    for (y, z) in path:
        rows.append([bm.verts.new((x, y, z)) for x in (-60, 60)])
    for i in range(len(rows) - 1):
        bm.faces.new((rows[i][0], rows[i][1], rows[i + 1][1], rows[i + 1][0]))
    sme = bpy.data.meshes.new('sweep'); bm.to_mesh(sme); bm.free(); sw = bpy.data.objects.new('sweep', sme); sc.collection.objects.link(sw)
    for p in sme.polygons: p.use_smooth = True
    if PACK: sw.hide_render = True
    wm_, wb = mat('sweep', **{'Base Color': lin('#D8CDB8' if SHOT in ('lineup', 'box') else SWEEP[AREA]), 'Roughness': 0.85}); sw.data.materials.append(wm_)
    # low sun through palm fronds: a cut-out between the sun and the set casts the leaf shadows
    sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 5.0; sun.angle = math.radians(1.2); sun.color = (1.0, 0.94, 0.84)
    so = bpy.data.objects.new('sun', sun); sc.collection.objects.link(so); so.rotation_euler = (math.radians(52), 0, math.radians(-38))
    fr = bpy.data.objects.new('fronds', None)
    pl = bpy.ops.mesh.primitive_plane_add(size=36, location=(-6, -2, 26)); g = bpy.context.active_object; g.name = 'gobo'
    g.rotation_euler = so.rotation_euler; g.rotation_euler.rotate_axis('Z', math.radians(25))
    fm, fb = mat('fronds', **{'Base Color': (0, 0, 0, 1), 'Roughness': 1.0}); fnt = fm.node_tree
    fi = fnt.nodes.new('ShaderNodeTexImage'); fi.image = bpy.data.images.load(os.path.join(TEX, 'fronds.png')); fnt.links.new(fi.outputs['Alpha'], fb.inputs['Alpha'])
    g.data.materials.append(fm); g.visible_camera = False; g.visible_glossy = False; g.visible_transmission = False; g.visible_diffuse = False
    if PACK:
        # travertine ledge: warm stone, open pores, a soft front edge the camera sees
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 3.5, -2.0)); led = bpy.context.active_object; led.scale = (70, 17, 4); bpy.ops.object.transform_apply(scale=True)
        lbv = led.modifiers.new('bev', 'BEVEL'); lbv.width = 0.35; lbv.segments = 6
        tm, tb = mat('travertine', **{'Roughness': 0.82}); tnt = tm.node_tree
        tco = tnt.nodes.new('ShaderNodeTexCoord'); tmp = tnt.nodes.new('ShaderNodeMapping'); tmp.inputs['Scale'].default_value = (1.0, 0.3, 1.0); tnt.links.new(tco.outputs['Object'], tmp.inputs['Vector'])
        tn = tnt.nodes.new('ShaderNodeTexNoise'); tn.inputs['Scale'].default_value = 0.35; tn.inputs['Detail'].default_value = 3; tnt.links.new(tmp.outputs['Vector'], tn.inputs['Vector'])
        tr_ = tnt.nodes.new('ShaderNodeValToRGB'); tr_.color_ramp.elements[0].color = lin('#D3BFA0'); tr_.color_ramp.elements[1].color = lin('#E9DCC5')
        tnt.links.new(tn.outputs['Fac'], tr_.inputs['Fac']); tnt.links.new(tr_.outputs['Color'], tb.inputs['Base Color'])
        tv = tnt.nodes.new('ShaderNodeTexVoronoi'); tv.inputs['Scale'].default_value = 3.2; tnt.links.new(tmp.outputs['Vector'], tv.inputs['Vector'])
        tpr = tnt.nodes.new('ShaderNodeMapRange'); tpr.inputs['From Min'].default_value = 0.0; tpr.inputs['From Max'].default_value = 0.16; tnt.links.new(tv.outputs['Distance'], tpr.inputs['Value'])
        tfn = tnt.nodes.new('ShaderNodeTexNoise'); tfn.inputs['Scale'].default_value = 18; tml = tnt.nodes.new('ShaderNodeMath'); tml.operation = 'MULTIPLY'
        tnt.links.new(tpr.outputs['Result'], tml.inputs[0]); tnt.links.new(tfn.outputs['Fac'], tml.inputs[1])
        tbp = tnt.nodes.new('ShaderNodeBump'); tbp.inputs['Strength'].default_value = 0.35; tnt.links.new(tml.outputs['Value'], tbp.inputs['Height']); tnt.links.new(tbp.outputs['Normal'], tb.inputs['Normal'])
        led.data.materials.append(tm)
        # plaster wall behind, warm off-white with a hand-trowelled bump
        bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 12, 20)); wal = bpy.context.active_object; wal.scale = (90, 50, 1); wal.rotation_euler = (math.radians(90), 0, 0)
        pm_, pb_ = mat('plaster', **{'Base Color': lin('#EDE2D3'), 'Roughness': 0.9}); pnt = pm_.node_tree
        pn = pnt.nodes.new('ShaderNodeTexNoise'); pn.inputs['Scale'].default_value = 0.35; pn.inputs['Detail'].default_value = 4; pbp = pnt.nodes.new('ShaderNodeBump'); pbp.inputs['Strength'].default_value = 0.18
        pnt.links.new(pn.outputs['Fac'], pbp.inputs['Height']); pnt.links.new(pbp.outputs['Normal'], pb_.inputs['Normal']); wal.data.materials.append(pm_)
        # hard late sun from camera left, low, through the fronds onto wall, carton and stone
        for nm, k in (('key', 0.18), ('strip', 0.35), ('top', 0.12)): bpy.data.objects[nm].data.energy *= k
        bg.inputs['Strength'].default_value = 0.12
        sun.color = (1.0, 0.86, 0.68)
        sun.energy = 9.0; sun.angle = math.radians(0.5); so.rotation_euler = (math.radians(58), 0, math.radians(-48))
        g.location = (-10, -10, 24); g.rotation_euler = so.rotation_euler; g.rotation_euler.rotate_axis('Z', math.radians(15)); g.scale = (1.4, 1.4, 1)

# ---------- camera and pose ----------
cam = bpy.data.cameras.new('cam'); co = bpy.data.objects.new('cam', cam); sc.collection.objects.link(co); sc.camera = co
cam.sensor_width = 36; cam.dof.use_dof = True; cam.dof.aperture_fstop = 8
if floating:
    for o in vial: o.location.z = -3.3           # pivot at the middle of the vial
    cam.lens = 85; co.location = (0, -20.5, 0); co.rotation_euler = (math.radians(90), 0, 0)
    spin = 0.0
    if SHOT.startswith('floatspin:'):
        f, n = SHOT[10:].split('/'); spin = 360.0 * int(f) / int(n)
    tilt = bpy.data.objects.new('tilt', None); sc.collection.objects.link(tilt); root.parent = tilt
    tilt.rotation_euler = (math.radians(-10), math.radians(-24), 0); root.rotation_euler = (0, 0, math.radians(-6 + spin))
    bg.inputs['Strength'].default_value = 0.9
    cam.dof.focus_distance = 20.5; cam.dof.aperture_fstop = 11
    sc.render.film_transparent = True; sc.cycles.film_transparent_glass = True
elif SHOT == 'pair':
    cam.lens = 85; co.location = (0.2, -36, 6.4); co.rotation_euler = (math.radians(85), 0, 0); cam.dof.focus_distance = 36
elif SHOT == 'box':
    cam.lens = 55; co.location = (8, -40, 17); cam.dof.focus_distance = 44; cam.dof.aperture_fstop = 11
    d = Vector((0, 2.4, 3.6)) - co.location; co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); sc.view_settings.exposure = -0.35
elif PACK:
    cam.lens = 85 if SHOT == 'pack' else 55
    co.location = (-2.0, -29, 6.2) if SHOT == 'pack' else (-0.6, -35, 6.6)
    d = Vector((0.25 if SHOT == 'pack' else 0.6, 0.0, 3.3 if SHOT == 'pack' else 3.5)) - co.location; co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.dof.focus_distance = (Vector((0, -1, 3.5)) - co.location).length; cam.dof.aperture_fstop = 5.6
elif SHOT == 'lineup':
    cam.lens = 70; co.location = (0, -40, 7.0); co.rotation_euler = (math.radians(84.5), 0, 0); cam.dof.focus_distance = 40
else:
    cam.lens = 100; co.location = (0, -31, 5.3); co.rotation_euler = (math.radians(86.0), 0, 0)
    cam.dof.focus_distance = 31
    turn = 0.0
    if SHOT == 'lot': turn = 90.0
    if SHOT.startswith('spin:'):
        f, n = SHOT[5:].split('/'); turn = 360.0 * int(f) / int(n)
    root.rotation_euler = (0, 0, math.radians(-7 + turn))

# ---------- render ----------
r = sc.render; r.engine = 'CYCLES'; r.resolution_x, r.resolution_y = W, H; r.resolution_percentage = 100
sc.cycles.device = 'CPU'; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 16; sc.cycles.transmission_bounces = 16; sc.cycles.glossy_bounces = 8; sc.cycles.transparent_max_bounces = 16; sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
sc.view_settings.view_transform = 'AgX'
if SHOT == 'box': sc.view_settings.exposure = -0.35
try: sc.view_settings.look = 'AgX - Punchy'
except Exception: pass
r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGBA' if floating else 'RGB'; r.filepath = OUT
bpy.ops.render.render(write_still=True)
print('rendered', OUT)

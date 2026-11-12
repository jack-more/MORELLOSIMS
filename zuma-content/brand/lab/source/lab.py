# ZUMA lab: a post-modern mission-style concrete lab whose arched windows are glazed with the Lightboxes.
# Cycles via bpy. Units: cm.  usage: python lab.py OUT.png [W H SAMPLES]
import sys, os, math
args = sys.argv[1:]
OUT = args[0]; W, H, SAMPLES = (int(args[1]), int(args[2]), int(args[3])) if len(args) > 3 else (1080, 1920, 96)
SP = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad'
TEXD = os.environ.get('LABTEX', SP + '/lab/tex'); LBD = os.environ.get('LBDIR', SP + '/cut')
WINDOWS = os.environ.get('WINDOWS', 'tissue,metabolic,neuro').split(',')
VIALS = os.environ.get('LABVIALS', '05@-7,01@0,11@7').split(',')

# reuse the site's vial (geometry, glass, label, cap) from zuma/render/vial.py
VP = '/home/user/zuma/render/vial.py'
src = open(VP).read(); src = src[:src.index("if SHOT == 'lineup'")].replace("'..', 'site3', 'src', 'data'", "'..', 'source', 'src', 'data'")
sys.argv = ['vial.py', 'float', '01', OUT]
g = {'__file__': VP, '__name__': 'vialmod'}; exec(compile(src, VP, 'exec'), g)
bpy, lin, make_vial, sc = g['bpy'], g['lin'], g['make_vial'], g['sc']
from mathutils import Vector
import bmesh

def tex_mat(name, base, scale=1.0, rough_bias=0.0, tint=(1, 1, 1)):
    m = bpy.data.materials.new(name); m.use_nodes = True; N = m.node_tree.nodes; L = m.node_tree.links
    p = N['Principled BSDF']; tc = N.new('ShaderNodeTexCoord'); mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (scale, scale, scale)
    L.new(tc.outputs['Object'], mp.inputs['Vector'])
    def img(suffix, cs):
        t = N.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(f'{TEXD}/{base}_{suffix}.jpg'); t.image.colorspace_settings.name = cs
        t.projection = 'BOX'; t.projection_blend = 0.25; L.new(mp.outputs['Vector'], t.inputs['Vector']); return t
    d = img('Diffuse', 'sRGB'); r = img('Rough', 'Non-Color'); n = img('nor_gl', 'Non-Color')
    tn = N.new('ShaderNodeMixRGB'); tn.blend_type = 'MULTIPLY'; tn.inputs['Fac'].default_value = 1.0; tn.inputs['Color2'].default_value = (*tint, 1)
    L.new(d.outputs['Color'], tn.inputs['Color1']); L.new(tn.outputs['Color'], p.inputs['Base Color'])
    ra = N.new('ShaderNodeMath'); ra.operation = 'ADD'; ra.use_clamp = True; ra.inputs[1].default_value = rough_bias; L.new(r.outputs['Color'], ra.inputs[0]); L.new(ra.outputs[0], p.inputs['Roughness'])
    nm = N.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = 0.8; L.new(n.outputs['Color'], nm.inputs['Color']); L.new(nm.outputs['Normal'], p.inputs['Normal'])
    if os.environ.get('TIES') and name in ('wall', 'plinth'):
        # Ando-style board-formed concrete: panel seams every 180 x 90 cm and form-tie holes, in world space
        g = N.new('ShaderNodeTexCoord'); sepw = N.new('ShaderNodeSeparateXYZ'); L.new(g.outputs['Object'], sepw.inputs[0])
        def axis_sum(a, b):
            ad = N.new('ShaderNodeMath'); ad.operation = 'ADD'; L.new(sepw.outputs[a], ad.inputs[0]); L.new(sepw.outputs[b], ad.inputs[1]); return ad
        u = axis_sum('X', 'Y'); v = sepw.outputs['Z']
        def frac_dist(src, period, off=0.0):
            dv = N.new('ShaderNodeMath'); dv.operation = 'DIVIDE'; L.new(src if not hasattr(src, 'outputs') else src.outputs[0], dv.inputs[0]); dv.inputs[1].default_value = period
            ad = N.new('ShaderNodeMath'); ad.operation = 'ADD'; L.new(dv.outputs[0], ad.inputs[0]); ad.inputs[1].default_value = off
            fr = N.new('ShaderNodeMath'); fr.operation = 'FRACT'; L.new(ad.outputs[0], fr.inputs[0])
            sb = N.new('ShaderNodeMath'); sb.operation = 'SUBTRACT'; L.new(fr.outputs[0], sb.inputs[0]); sb.inputs[1].default_value = 0.5
            ab = N.new('ShaderNodeMath'); ab.operation = 'ABSOLUTE'; L.new(sb.outputs[0], ab.inputs[0])
            ml = N.new('ShaderNodeMath'); ml.operation = 'MULTIPLY'; L.new(ab.outputs[0], ml.inputs[0]); ml.inputs[1].default_value = period; return ml   # distance (cm) to the cell centre
        du = frac_dist(u, 180.0, 0.5); dvv = frac_dist(v, 90.0, 0.5)                                   # distance to the panel seams = period/2 - this
        def seam(dn, period):
            sb = N.new('ShaderNodeMath'); sb.operation = 'SUBTRACT'; sb.inputs[0].default_value = period / 2; L.new(dn.outputs[0], sb.inputs[1])
            lt = N.new('ShaderNodeMath'); lt.operation = 'LESS_THAN'; L.new(sb.outputs[0], lt.inputs[0]); lt.inputs[1].default_value = 0.35; return lt
        su = seam(du, 180.0); sv = seam(dvv, 90.0)
        sm = N.new('ShaderNodeMath'); sm.operation = 'MAXIMUM'; L.new(su.outputs[0], sm.inputs[0]); L.new(sv.outputs[0], sm.inputs[1])
        hu = frac_dist(u, 60.0, 0.0); hv = frac_dist(v, 45.0, 0.0)                                      # tie holes on a 60 x 45 cm grid
        hx = N.new('ShaderNodeCombineXYZ'); L.new(hu.outputs[0], hx.inputs['X']); L.new(hv.outputs[0], hx.inputs['Y'])
        hl = N.new('ShaderNodeVectorMath'); hl.operation = 'LENGTH'; L.new(hx.outputs[0], hl.inputs[0])
        hole = N.new('ShaderNodeMath'); hole.operation = 'LESS_THAN'; L.new(hl.outputs['Value'], hole.inputs[0]); hole.inputs[1].default_value = 1.5
        mk = N.new('ShaderNodeMath'); mk.operation = 'MAXIMUM'; L.new(sm.outputs[0], mk.inputs[0]); L.new(hole.outputs[0], mk.inputs[1])
        dk = N.new('ShaderNodeMixRGB'); dk.blend_type = 'MULTIPLY'; L.new(mk.outputs[0], dk.inputs['Fac']); dk.inputs['Color2'].default_value = (0.35, 0.34, 0.33, 1)
        L.new(tn.outputs['Color'], dk.inputs['Color1']); L.new(dk.outputs['Color'], p.inputs['Base Color'])
        bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.6; bp.inputs['Distance'].default_value = 0.6; bp.invert = True
        L.new(mk.outputs[0], bp.inputs['Height']); L.new(nm.outputs['Normal'], bp.inputs['Normal']); L.new(bp.outputs['Normal'], p.inputs['Normal'])
    return m

def box(name, size, loc, mat_):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.active_object; o.name = name; o.scale = size
    bpy.ops.object.transform_apply(scale=True); o.data.materials.append(mat_); return o

WALL = tex_mat('wall', 'concrete_wall_008', float(os.environ.get('WSCALE', '0.006')), 0.0, (0.86, 0.84, 0.80))
FLOOR = tex_mat('floor', 'concrete_floor_02', 0.004, -0.55 if os.environ.get('POLISH') else -0.25, (0.62, 0.60, 0.58) if os.environ.get('POLISH') else (0.80, 0.78, 0.75))
PLINTH = tex_mat('plinth', 'concrete_wall_008', 0.02, 0.05, (0.90, 0.88, 0.84))

# ---------- the room ----------
RW, RD, RH = 760, 900, int(os.environ.get('RH', '560'))         # width, depth, height
box('floor', (RW, RD, 10), (0, 150, -5), FLOOR)
box('ceiling', (RW, RD, 30), (0, 150, RH + 15), WALL)
box('wall_l', (40, RD, RH), (-RW / 2 - 20, 150, RH / 2), WALL)
box('wall_r', (40, RD, RH), (RW / 2 + 20, 150, RH / 2), WALL)
box('wall_front', (RW, 40, RH), (0, -320, RH / 2), WALL)
# the back wall, 70 cm deep, cut with tall round-arched openings (mission arches)
YB, TB = 450, 70
back = box('wall_back', (RW, TB, RH), (0, YB + TB / 2, RH / 2), WALL)
AW, AH, SPACE = int(os.environ.get('AW', '150')), int(os.environ.get('AH', '400')), int(os.environ.get('SPACE', '230'))      # arch width, height to the crown, centre spacing
xs = [(i - (len(WINDOWS) - 1) / 2) * SPACE for i in range(len(WINDOWS))]
for x in xs:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, YB + TB / 2, (AH - AW / 2) / 2 + 6)); c = bpy.context.active_object; c.scale = (AW, TB + 40, AH - AW / 2); bpy.ops.object.transform_apply(scale=True)
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=AW / 2, depth=TB + 40, location=(x, YB + TB / 2, AH - AW / 2 + 6), rotation=(math.pi / 2, 0, 0)); cy = bpy.context.active_object
    for cut in (c, cy):
        mod = back.modifiers.new('cut', 'BOOLEAN'); mod.operation = 'DIFFERENCE'; mod.object = cut; bpy.context.view_layer.objects.active = back; bpy.ops.object.modifier_apply(modifier=mod.name)
        cut.hide_render = True; cut.hide_viewport = True
# the Lightbox glass behind each arch: a self-lit pane with the Lightbox image, plus a frosted glass sheet in the reveal
for x, area in zip(xs, WINDOWS):
    PW_, PH_ = AW + 140, AH + 320                                  # much larger than the opening: the deep reveal is seen from below
    bpy.ops.mesh.primitive_plane_add(size=1, location=(x, YB + TB + 25, PH_ / 2 - 40), rotation=(math.pi / 2, 0, 0)); p = bpy.context.active_object
    p.scale = (PW_, PH_, 1); bpy.ops.object.transform_apply(scale=True)
    m = bpy.data.materials.new('lb-' + area); m.use_nodes = True; N = m.node_tree.nodes; L = m.node_tree.links
    for n in list(N):
        if n.type != 'OUTPUT_MATERIAL': N.remove(n)
    t = N.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(f'{LBD}/lb-{area}.png'); t.extension = 'EXTEND'
    uv = N.new('ShaderNodeUVMap'); mp = N.new('ShaderNodeMapping')
    a_img = 1080 / 1920; a_pane = PW_ / PH_; sx = a_pane / a_img            # cover: crop the Lightbox's width to the pane
    mp.inputs['Scale'].default_value = (sx, 1, 1); mp.inputs['Location'].default_value = ((1 - sx) / 2, 0, 0)
    L.new(uv.outputs['UV'], mp.inputs['Vector']); L.new(mp.outputs['Vector'], t.inputs['Vector'])
    em = N.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = float(os.environ.get('LBSTR', '6.0')); L.new(t.outputs['Color'], em.inputs['Color'])
    L.new(em.outputs[0], N['Material Output'].inputs['Surface']); p.data.materials.append(m)

# ---------- the plinth and the vials ----------
PZ = 98
if os.environ.get('FLOAT'):   # a thick slab that floats on a recessed dark base
    DARK = tex_mat('base', 'concrete_wall_008', 0.02, 0.1, (0.30, 0.29, 0.28))
    box('plinth_base', (52, 26, PZ - 14), (0, 0, (PZ - 14) / 2), DARK)
    box('plinth', (96, 50, 14), (0, 0, PZ - 7), PLINTH)
else:
    box('plinth', (80, 46, PZ), (0, 0, PZ / 2), PLINTH)
if os.environ.get('BEVEL'):
    for o in list(sc.objects):
        if o.type == 'MESH' and (o.name.startswith('wall') or o.name.startswith('plinth') or o.name in ('floor', 'ceiling')):
            bv = o.modifiers.new('bevel', 'BEVEL'); bv.width = 1.2; bv.segments = 3; bv.limit_method = 'ANGLE'
for it in VIALS:
    no, vx = it.split('@'); root, vial = make_vial(no); root.scale = (1, 1, 1); root.location = (float(vx), 2, PZ); root.rotation_euler = (0, 0, math.radians(float(os.environ.get('VROT', '0'))))

if os.environ.get('BAGS'):
    BD = os.environ.get('BAGDIR', SP + '/lab/bags'); nos = os.environ['BAGS'].split(',')
    CY, CZ_, GAPX = float(os.environ.get('CORDY', '40')), float(os.environ.get('CORDZ', '138')), float(os.environ.get('BAGGAP', '15'))
    span = (len(nos) - 1) * GAPX + 40
    sag = float(os.environ.get('SAG', '3'))
    cv = bpy.data.curves.new('cord', 'CURVE'); cv.dimensions = '3D'; cv.bevel_depth = 0.12; cv.bevel_resolution = 3
    sp_ = cv.splines.new('BEZIER'); sp_.bezier_points.add(2)
    for i_, (px_, pz_) in enumerate([(-span / 2 - 30, CZ_ + 4), (0, CZ_ - sag), (span / 2 + 30, CZ_ + 4)]):
        bp_ = sp_.bezier_points[i_]; bp_.co = (px_, CY, pz_); bp_.handle_left_type = bp_.handle_right_type = 'AUTO'
    cord = bpy.data.objects.new('cord', cv); sc.collection.objects.link(cord)
    rope = bpy.data.materials.new('rope'); rope.use_nodes = True; rope.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.82, 0.78, 0.70, 1); rope.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9; cv.materials.append(rope)
    wood = bpy.data.materials.new('peg'); wood.use_nodes = True; wp = wood.node_tree.nodes['Principled BSDF']; wp.inputs['Base Color'].default_value = (0.55, 0.38, 0.22, 1); wp.inputs['Roughness'].default_value = 0.7
    def cord_z(px_):   # the line's height at x (a parabola through the three points)
        t_ = px_ / (span / 2 + 30); return CZ_ - sag + (sag + 4) * t_ * t_
    for k_, no_ in enumerate(nos):
        bx = (k_ - (len(nos) - 1) / 2) * GAPX
        with bpy.data.libraries.load(f'{BD}/bag-{no_}.blend') as (src_, dst_):
            dst_.objects = [n_ for n_ in src_.objects if n_ not in ('top', 'strip', 'streak', 'streak2', 'key', 'cam', 'ground', 'Plane')]
        hold = bpy.data.objects.new(f'bag{no_}', None); sc.collection.objects.link(hold)
        for o_ in dst_.objects:
            if o_ is None: continue
            sc.collection.objects.link(o_)
            if o_.parent is None: o_.parent = hold
        top_z = cord_z(bx) - 0.8
        hold.rotation_euler = (math.radians(90), 0, math.radians(float(os.environ.get('BAGTWIST', '0')) * (k_ % 2 * 2 - 1)))
        hold.location = (bx, CY + 0.4, top_z - 7.5)   # the bag's top edge (+7.5 cm along its length) sits just under the line
        for dx_ in (-3.0, 3.0):   # two wooden pegs
            bpy.ops.mesh.primitive_cube_add(size=1, location=(bx + dx_, CY, cord_z(bx + dx_) - 1.4)); pg = bpy.context.active_object; pg.scale = (0.9, 1.1, 5.2)
            bpy.ops.object.transform_apply(scale=True); b2 = pg.modifiers.new('b', 'BEVEL'); b2.width = 0.2; b2.segments = 2; pg.data.materials.append(wood)

# ---------- light: the windows light the room; a little fill so the concrete reads ----------
world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True; world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.02, 0.02, 0.022, 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.4
def area(name, size, loc, power, color=(1, 1, 1), sy=None, target=(0, 0, 100)):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = power; ld.shape = 'RECTANGLE'; ld.size = size; ld.size_y = sy or size; ld.color = color
    o = bpy.data.objects.new(name, ld); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return o
area('fill', 200, (-150, -260, 380), float(os.environ.get('FILL', '60000')), (1.0, 0.97, 0.93))
if float(os.environ.get('BAGKEY', '0')) > 0:   # a soft key on the hanging bags so the print and film read
    area('bagkey', 70, (-70, -70, 170), float(os.environ['BAGKEY']), (1.0, 0.98, 0.96), target=(0, float(os.environ.get('CORDY', '40')), float(os.environ.get('CORDZ', '138')) - 8))
area('rim', 60, (220, 180, 300), float(os.environ.get('RIM', '30000')), (1.0, 0.98, 0.95), target=(0, 0, PZ + 3))
if float(os.environ.get('FOG', '0')) > 0:   # a whisper of haze so the window light reads in the air
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 150, RH / 2)); fg = bpy.context.active_object; fg.scale = (RW - 2, RD - 2, RH - 2)
    fm = bpy.data.materials.new('fog'); fm.use_nodes = True; fN = fm.node_tree.nodes
    for n in list(fN):
        if n.type != 'OUTPUT_MATERIAL': fN.remove(n)
    vs = fN.new('ShaderNodeVolumeScatter'); vs.inputs['Density'].default_value = float(os.environ['FOG']); fm.node_tree.links.new(vs.outputs[0], fN['Material Output'].inputs['Volume'])
    fg.data.materials.append(fm)

# ---------- camera: eye level with the plinth top, the arches behind ----------
cam = bpy.data.cameras.new('cam'); co = bpy.data.objects.new('cam', cam); sc.collection.objects.link(co); sc.camera = co
cam.lens = float(os.environ.get('LENS', '40')); cam.sensor_fit = 'VERTICAL'; cam.sensor_height = 36
co.location = (float(os.environ.get('CX', '0')), -float(os.environ.get('CDIST', '95')), float(os.environ.get('CZ', '108')))
tgt = Vector((0, YB, float(os.environ.get('TZ', '205')))); co.rotation_euler = (tgt - co.location).to_track_quat('-Z', 'Y').to_euler()
cam.dof.use_dof = True; cam.dof.focus_distance = (Vector((0, 2, PZ + 2)) - co.location).length; cam.dof.aperture_fstop = float(os.environ.get('FSTOP', '2.8'))
r = sc.render; r.engine = 'CYCLES'; r.resolution_x, r.resolution_y = W, H; r.resolution_percentage = 100
sc.cycles.device = 'CPU'; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 10; sc.cycles.transmission_bounces = 12; sc.cycles.transparent_max_bounces = 24
sc.view_settings.view_transform = 'AgX'
try: sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception: pass
sc.view_settings.exposure = float(os.environ.get('EXPOSURE', '0'))
r.image_settings.file_format = 'PNG'; r.filepath = OUT
bpy.ops.render.render(write_still=True)
print('rendered', OUT)

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
    return m

def box(name, size, loc, mat_):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.active_object; o.name = name; o.scale = size
    bpy.ops.object.transform_apply(scale=True); o.data.materials.append(mat_); return o

WALL = tex_mat('wall', 'concrete_wall_008', float(os.environ.get('WSCALE', '0.006')), 0.0, (0.86, 0.84, 0.80))
FLOOR = tex_mat('floor', 'concrete_floor_02', 0.004, -0.25, (0.80, 0.78, 0.75))
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
    bpy.ops.mesh.primitive_plane_add(size=1, location=(x, YB + TB + 25, (AH + 12) / 2), rotation=(math.pi / 2, 0, 0)); p = bpy.context.active_object
    p.scale = (AW + 20, AH + 12, 1); bpy.ops.object.transform_apply(scale=True)
    m = bpy.data.materials.new('lb-' + area); m.use_nodes = True; N = m.node_tree.nodes; L = m.node_tree.links
    for n in list(N):
        if n.type != 'OUTPUT_MATERIAL': N.remove(n)
    t = N.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(f'{LBD}/lb-{area}.png'); t.extension = 'EXTEND'
    uv = N.new('ShaderNodeUVMap'); mp = N.new('ShaderNodeMapping')
    a_img = 1080 / 1920; a_pane = (AW + 20) / (AH + 12); sx = a_pane / a_img            # cover: crop the Lightbox's width to the pane
    mp.inputs['Scale'].default_value = (sx, 1, 1); mp.inputs['Location'].default_value = ((1 - sx) / 2, 0, 0)
    L.new(uv.outputs['UV'], mp.inputs['Vector']); L.new(mp.outputs['Vector'], t.inputs['Vector'])
    em = N.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = float(os.environ.get('LBSTR', '6.0')); L.new(t.outputs['Color'], em.inputs['Color'])
    L.new(em.outputs[0], N['Material Output'].inputs['Surface']); p.data.materials.append(m)

# ---------- the plinth and the vials ----------
PZ = 98
box('plinth', (80, 46, PZ), (0, 0, PZ / 2), PLINTH)
for it in VIALS:
    no, vx = it.split('@'); root, vial = make_vial(no); root.scale = (1, 1, 1); root.location = (float(vx), 2, PZ); root.rotation_euler = (0, 0, math.radians(float(os.environ.get('VROT', '0'))))

# ---------- light: the windows light the room; a little fill so the concrete reads ----------
world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True; world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.02, 0.02, 0.022, 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.4
def area(name, size, loc, power, color=(1, 1, 1), sy=None, target=(0, 0, 100)):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = power; ld.shape = 'RECTANGLE'; ld.size = size; ld.size_y = sy or size; ld.color = color
    o = bpy.data.objects.new(name, ld); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return o
area('fill', 200, (-150, -260, 380), float(os.environ.get('FILL', '60000')), (1.0, 0.97, 0.93))
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

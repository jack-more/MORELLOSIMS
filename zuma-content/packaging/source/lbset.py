# One vial in front of its Lightbox: the lit tiles of its research area behind, a glossy Oxblood plinth below (Blender Cycles via bpy).
#   ZNO=05 ZOPT=P2 ZCAP=ox ZTINT=vol bpyenv/bin/python cyc/lbset/lbset.py OUT W H SAMPLES
# Units are centimetres. The vial and its print come from label3d.py; the palette from pal.py; the tiles from tex.cjs.
import bpy, math, os, sys
from mathutils import Vector

SET = os.path.dirname(os.path.abspath(__file__)); HERE = os.path.dirname(SET); TEX = os.path.join(HERE, 'tex'); LB = os.path.join(HERE, 'lab3')
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
SARGS = list(args); OUT = SARGS[0]; NO = os.environ.get('ZNO', '05'); OPT = os.environ.get('ZOPT', 'P2')
src = open(os.path.join(HERE, 'vial.py')).read()
sys.argv = ['vial.py', 'front', NO, OUT]
__file__ = os.path.join(HERE, 'vial.py')          # vial.py finds its data next to itself
exec(compile(src[:src.index("if SHOT == 'lineup':")], 'vial.py', 'exec'))
SET = os.path.join(HERE, 'lbset'); W, H, SAMPLES = int(SARGS[1]), int(SARGS[2]), int(SARGS[3])
exec(open(os.path.join(SET, 'pal.py')).read()); TONES.update(PAL)
l3 = open(os.path.join(HERE, 'label3d.py')).read()
exec(compile(l3[l3.index('R = 0.8'):l3.index('def stucco')], 'label3d.py', 'exec'))
AREA = AREA_OF[NO]

# the Lightbox: a wall of lit tiles well behind the vial, so the lens softens it
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 11, 3.2), rotation=(math.radians(90), 0, 0)); bk = bpy.context.active_object
bk.scale = (17, 17, 1); bpy.ops.object.transform_apply(scale=True)
em = bpy.data.materials.new('lightbox'); em.use_nodes = True; nt = em.node_tree; nt.nodes.clear()
o = nt.nodes.new('ShaderNodeOutputMaterial'); es = nt.nodes.new('ShaderNodeEmission'); es.inputs['Strength'].default_value = float(os.environ.get('ZLB', '1.0'))
ti = nt.nodes.new('ShaderNodeTexImage'); ti.image = bpy.data.images.load(os.path.join(SET, 'lb-%s.png' % AREA))
nt.links.new(ti.outputs['Color'], es.inputs['Color']); nt.links.new(es.outputs['Emission'], o.inputs['Surface']); bk.data.materials.append(em)

# the plinth: Oxblood lacquer, a deep gloss that mirrors the vial
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -4.0, -2.5)); pl = bpy.context.active_object
pl.scale = (40, 21, 5); bpy.ops.object.transform_apply(scale=True)
bv = pl.modifiers.new('soft', 'BEVEL'); bv.width = 0.25; bv.segments = 8
for f in pl.data.polygons: f.use_smooth = True
lm_, lb_ = mat('lacquer', **{'Base Color': lin(OX), 'Roughness': 0.34, 'Coat Weight': 0.5, 'Coat Roughness': 0.2}); pl.data.materials.append(lm_)

v = vial3(NO); v.location = (0, 0, 0); v.rotation_euler = (0, 0, math.radians(float(os.environ.get('ZROT', '0'))))

world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True; wn = world.node_tree
env = wn.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(os.path.join(TEX, 'studio.hdr'))
bg = wn.nodes['Background']; bg.inputs['Strength'].default_value = 0.25; wn.links.new(env.outputs['Color'], bg.inputs['Color'])
def area(name, size, loc, power, look=(0, 0, 1.7), sx=None, col=(1, 1, 1)):
    l = bpy.data.lights.new(name, 'AREA'); l.shape = 'RECTANGLE'; l.size = size; l.size_y = sx or size; l.energy = power; l.color = col
    ob = bpy.data.objects.new(name, l); sc.collection.objects.link(ob); ob.location = loc
    d = Vector(look) - Vector(loc); ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); return ob
area('key', 14, (-14, -16, 10), 2600, col=(1.0, 0.97, 0.93))
area('strip', 1.2, (8, -6, 3), 90, sx=12)            # a tall soft strip: the long highlight down the glass
area('top', 6, (0, -2, 14), 120)
for ob in [o_ for o_ in sc.objects if o_.type == 'LIGHT']: ob.visible_glossy = True

cam = bpy.data.cameras.new('cam'); co = bpy.data.objects.new('cam', cam); sc.collection.objects.link(co); sc.camera = co
cam.sensor_width = 36; cam.lens = 85; co.location = (0, -21, 2.9); look = Vector((0, 0, 1.55))
d = look - co.location; co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
cam.dof.use_dof = True; cam.dof.focus_distance = (Vector((0, -0.6, 1.6)) - co.location).length; cam.dof.aperture_fstop = 2.8

r = sc.render; r.engine = 'CYCLES'; r.resolution_x, r.resolution_y = W, H; r.resolution_percentage = 100
sc.cycles.device = 'CPU'; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 16; sc.cycles.transmission_bounces = 16; sc.cycles.glossy_bounces = 8; sc.cycles.transparent_max_bounces = 24
sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
sc.view_settings.view_transform = os.environ.get('ZVT', 'Standard')
r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGB'; r.filepath = OUT
bpy.ops.render.render(write_still=True)
print('rendered', OUT)

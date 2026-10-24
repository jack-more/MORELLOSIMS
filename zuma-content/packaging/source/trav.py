# Travertine niche set for the 3 mL vials, rendered physically (Blender Cycles via the bpy module).
#   ZOPT=G ZCAP=deep ZNOS=05,01,09 bpyenv/bin/python cyc/trav.py OUT W H SAMPLES
# A travertine wall with a wide niche, its top corners rounded, sized to the vials. A warm light glows from inside
# the niche; the vials stand on its floor. Units are centimetres. The vial model and labels come from label3d.py.
import bpy, math, os, sys
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__)); TEX = os.path.join(HERE, 'tex'); LB = os.path.join(HERE, 'lab3')
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
TARGS = list(args); OUT = TARGS[0]
OPT = os.environ.get('ZOPT', 'G'); NOS = os.environ.get('ZNOS', '05,01,09').split(',')
src = open(os.path.join(HERE, 'vial.py')).read()
sys.argv = ['vial.py', 'front', NOS[0], OUT]
exec(compile(src[:src.index("if SHOT == 'lineup':")], 'vial.py', 'exec'))
W, H, SAMPLES = int(TARGS[1]), int(TARGS[2]), int(TARGS[3])
l3 = open(os.path.join(HERE, 'label3d.py')).read()
exec(compile(l3[l3.index('R = 0.8'):l3.index('def stucco')], 'label3d.py', 'exec'))   # vial3(), the true 3 mL vial with its label

def travertine(name, base='#E4D6BF'):
    m, b = mat(name, **{'Roughness': 0.8}); nt = m.node_tree
    co = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (0.25, 0.25, 2.2)
    nt.links.new(co.outputs['Object'], mp.inputs['Vector'])
    band = nt.nodes.new('ShaderNodeTexNoise'); band.inputs['Scale'].default_value = 0.6; band.inputs['Detail'].default_value = 6; band.inputs['Roughness'].default_value = 0.6
    nt.links.new(mp.outputs['Vector'], band.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color = lin('#DCCDB4'); ramp.color_ramp.elements[1].color = lin('#F4ECDF')
    nt.links.new(band.outputs['Fac'], ramp.inputs['Fac'])
    # open pores: small dark voids, stretched along the strata
    pm_ = nt.nodes.new('ShaderNodeMapping'); pm_.inputs['Scale'].default_value = (0.45, 0.45, 1.6); nt.links.new(co.outputs['Object'], pm_.inputs['Vector'])
    vor = nt.nodes.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 2.4; nt.links.new(pm_.outputs['Vector'], vor.inputs['Vector'])
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = 0.0; mr.inputs['From Max'].default_value = 0.11; mr.clamp = True
    nt.links.new(vor.outputs['Distance'], mr.inputs['Value'])
    pore = nt.nodes.new('ShaderNodeMixRGB'); pore.blend_type = 'MULTIPLY'; pore.inputs['Color2'].default_value = lin('#5E4A36')
    inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0; nt.links.new(mr.outputs['Result'], inv.inputs[1])
    # a second, finer layer of pits so the pores vary in size
    vor2 = nt.nodes.new('ShaderNodeTexVoronoi'); vor2.inputs['Scale'].default_value = 7.5; nt.links.new(pm_.outputs['Vector'], vor2.inputs['Vector'])
    mr2 = nt.nodes.new('ShaderNodeMapRange'); mr2.inputs['From Min'].default_value = 0.0; mr2.inputs['From Max'].default_value = 0.06; mr2.clamp = True
    nt.links.new(vor2.outputs['Distance'], mr2.inputs['Value'])
    both = nt.nodes.new('ShaderNodeMath'); both.operation = 'MINIMUM'; nt.links.new(mr.outputs['Result'], both.inputs[0]); nt.links.new(mr2.outputs['Result'], both.inputs[1])
    nt.links.new(both.outputs['Value'], inv.inputs[1])
    nt.links.new(inv.outputs['Value'], pore.inputs['Fac']); nt.links.new(ramp.outputs['Color'], pore.inputs['Color1'])
    nt.links.new(pore.outputs['Color'], b.inputs['Base Color'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.3; nt.links.new(both.outputs['Value'], bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal']); return m

def box(name, size, loc):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.active_object; o.name = name
    o.scale = size; bpy.ops.object.transform_apply(scale=True); return o
def cut(target, cutter):
    m = target.modifiers.new('cut', 'BOOLEAN'); m.operation = 'DIFFERENCE'; m.object = cutter; m.solver = 'EXACT'
    bpy.context.view_layer.objects.active = target; bpy.ops.object.modifier_apply(modifier=m.name); bpy.data.objects.remove(cutter, do_unlink=True)

# the wall and its niche: 9.6 wide, 6.2 tall, 4.2 deep, top corners rounded at 2.4
NW, NH, ND, NR, WY = 9.6, 6.2, 4.2, 2.4, 2.4
wall = box('wall', (60, 8, 40), (0, WY + 4, 3))
for c in [box('c1', (NW, ND + 1, NH - NR), (0, WY + ND / 2 - 0.5, (NH - NR) / 2)), box('c2', (NW - 2 * NR, ND + 1, NR + 0.01), (0, WY + ND / 2 - 0.5, NH - NR / 2))]:
    cut(wall, c)
for x in (-NW / 2 + NR, NW / 2 - NR):
    bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=NR, depth=ND + 1, location=(x, WY + ND / 2 - 0.5, NH - NR), rotation=(math.radians(90), 0, 0)); cut(wall, bpy.context.active_object)
bv = wall.modifiers.new('soft', 'BEVEL'); bv.width = 0.12; bv.segments = 5; bv.limit_method = 'ANGLE'
for p_ in wall.data.polygons: p_.use_smooth = True
wall.data.materials.append(travertine('trav'))
fl = box('floor', (80, 40, 1), (0, -10, -14)); fl.data.materials.append(travertine('trav2', '#E0D2BB'))   # out of frame, catches bounce

# a warm light hidden at the top front of the niche, washing the back wall and the vials
l = bpy.data.lights.new('glow', 'AREA'); l.shape = 'RECTANGLE'; l.size = NW - 1.0; l.size_y = 0.6; l.energy = 220; l.color = (1.0, 0.8, 0.58)
o = bpy.data.objects.new('glow', l); sc.collection.objects.link(o); o.location = (0, WY + 0.6, NH - 0.5)
d = Vector((0, WY + ND, 0.5)) - o.location; o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

for no, x, rot in zip(NOS, (-2.5, 0.0, 2.5), (-4, 0, 4)):
    v = vial3(no); v.location = (x, WY + ND / 2 + 0.2, 0); v.rotation_euler = (0, 0, math.radians(rot))

world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True; wn = world.node_tree
env = wn.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(os.path.join(TEX, 'studio.hdr'))
bg = wn.nodes['Background']; bg.inputs['Strength'].default_value = 0.3; wn.links.new(env.outputs['Color'], bg.inputs['Color'])
def area(name, size, loc, power, look=(0, WY + 2, 2), sx=None, col=(1, 1, 1)):
    l = bpy.data.lights.new(name, 'AREA'); l.shape = 'RECTANGLE'; l.size = size; l.size_y = sx or size; l.energy = power; l.color = col
    o = bpy.data.objects.new(name, l); sc.collection.objects.link(o); o.location = loc
    d = Vector(look) - Vector(loc); o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); return o
area('fill', 40, (10, -60, 20), 6200, col=(1.0, 0.96, 0.9))
area('front', 6, (-2, -18, 4), 160, look=(0, WY + 2, 1.6))
area('kiss', 2.5, (-12, -2, 8), 300, sx=10)

cam = bpy.data.cameras.new('cam'); co = bpy.data.objects.new('cam', cam); sc.collection.objects.link(co); sc.camera = co
cam.sensor_width = 36; cam.lens = 85; co.location = (0, -27, 3.2); look = Vector((0, WY + 1, 2.9))
d = look - co.location; co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
cam.dof.use_dof = True; cam.dof.focus_distance = (Vector((0, WY + ND / 2, 1.8)) - co.location).length; cam.dof.aperture_fstop = 8

r = sc.render; r.engine = 'CYCLES'; r.resolution_x, r.resolution_y = W, H; r.resolution_percentage = 100
sc.cycles.device = 'CPU'; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 16; sc.cycles.transmission_bounces = 16; sc.cycles.glossy_bounces = 8; sc.cycles.transparent_max_bounces = 24
sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
sc.view_settings.view_transform = 'AgX'
try: sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception: pass
r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGB'; r.filepath = OUT
bpy.ops.render.render(write_still=True)
print('rendered', OUT)

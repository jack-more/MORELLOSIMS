# Site images for one product (Blender Cycles via bpy): Lightbox photos, spin frames and tilted cutouts.
#   ZNO=05 bpyenv/bin/python cyc/lbset/siteimg.py OUTDIR
# Built on the Lightbox set (lbset.py). One process renders every shot for the product.
# One vial in front of its Lightbox: the lit tiles of its research area behind, a glossy Oxblood plinth below (Blender Cycles via bpy).
#   ZNO=05 ZOPT=P2 ZCAP=ox ZTINT=vol bpyenv/bin/python cyc/lbset/lbset.py OUT W H SAMPLES
# Units are centimetres. The vial and its print come from label3d.py; the palette from pal.py; the tiles from tex.cjs.
import bpy, math, os, sys
from mathutils import Vector

SET = os.path.dirname(os.path.abspath(__file__)); HERE = os.path.dirname(SET); TEX = os.path.join(HERE, 'tex'); LB = os.path.join(HERE, 'lab3')
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
SARGS = list(args); OUTD = SARGS[0]; OUT = os.path.join(OUTD, 'x.png'); NO = os.environ.get('ZNO', '05'); OPT = os.environ.get('ZOPT', 'P2')
src = open(os.path.join(HERE, 'vial.py')).read()
sys.argv = ['vial.py', 'front', NO, OUT]
__file__ = os.path.join(HERE, 'vial.py')          # vial.py finds its data next to itself
exec(compile(src[:src.index("if SHOT == 'lineup':")], 'vial.py', 'exec'))
SET = os.path.join(HERE, 'lbset'); W, H, SAMPLES = 720, 960, 48
exec(open(os.path.join(SET, 'pal.py')).read()); TONES.update(PAL)
l3 = open(os.path.join(HERE, 'label3d.py')).read()
exec(compile(l3[l3.index('R = 0.8'):l3.index('def stucco')], 'label3d.py', 'exec'))
AREA = AREA_OF[NO]

# the Lightbox: a wall of lit tiles well behind the vial, so the lens softens it
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 11, 3.2), rotation=(math.radians(90), 0, 0)); bk = bpy.context.active_object
bk.scale = (17, 17, 1) if not os.environ.get('ZNOS') else (70, 40, 1); bpy.ops.object.transform_apply(scale=True)
em = bpy.data.materials.new('lightbox'); em.use_nodes = True; nt = em.node_tree; nt.nodes.clear()
o = nt.nodes.new('ShaderNodeOutputMaterial'); es = nt.nodes.new('ShaderNodeEmission'); es.inputs['Strength'].default_value = float(os.environ.get('ZLB', '1.0'))
ti = nt.nodes.new('ShaderNodeTexImage'); tp = os.path.join(SET, 'lb-%s.png' % NO); ti.image = bpy.data.images.load(tp if os.path.exists(tp) else os.path.join(SET, 'lb-%s.png' % AREA))
nt.links.new(ti.outputs['Color'], es.inputs['Color']); nt.links.new(es.outputs['Emission'], o.inputs['Surface']); bk.data.materials.append(em)
WHITE = os.environ.get('ZBG') == 'white'          # plain white studio, for the factory: the true tint with nothing behind it
if WHITE: nt.links.remove(es.inputs['Color'].links[0]); es.inputs['Color'].default_value = (1, 1, 1, 1)

# the plinth: Oxblood lacquer, a deep gloss that mirrors the vial
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -4.0, -2.5)); pl = bpy.context.active_object
pl.scale = (40, 21, 5); bpy.ops.object.transform_apply(scale=True)
bv = pl.modifiers.new('soft', 'BEVEL'); bv.width = 0.25; bv.segments = 8
for f in pl.data.polygons: f.use_smooth = True
lm_, lb_ = mat('lacquer', **{'Base Color': lin(OX), 'Roughness': 0.34, 'Coat Weight': 0.5, 'Coat Roughness': 0.2})
if WHITE: lb_.inputs['Base Color'].default_value = lin('#F3F2F0'); lb_.inputs['Roughness'].default_value = 0.45; lb_.inputs['Coat Weight'].default_value = 0.25
pl.data.materials.append(lm_)

LINE = os.environ.get('ZNOS')                     # a lineup: several vials in a row, the camera pulled back to hold them
if LINE:
    nos = LINE.split(','); gap = 2.5
    for i, n_ in enumerate(nos):
        v = vial3(n_); v.location = ((i - (len(nos) - 1) / 2) * gap, 0, 0)
else:
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


if NO == '03':                                      # BAC water is a liquid: no freeze-dried cake in the vial
    for o_ in [o_ for o_ in v.children if o_.name.startswith('cake')]: bpy.data.objects.remove(o_, do_unlink=True)
cam = bpy.data.cameras.new('cam'); co = bpy.data.objects.new('cam', cam); sc.collection.objects.link(co); sc.camera = co; cam.sensor_width = 36
r = sc.render; r.engine = 'CYCLES'; r.resolution_percentage = 100
sc.cycles.device = 'CPU'; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 16; sc.cycles.transmission_bounces = 16; sc.cycles.glossy_bounces = 8; sc.cycles.transparent_max_bounces = 24
sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
sc.view_settings.view_transform = 'Standard'; r.image_settings.file_format = 'PNG'
def aim(loc, look, lens, fstop, focus):
    co.location = loc; d = Vector(look) - Vector(loc); co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); cam.lens = lens
    cam.dof.use_dof = True; cam.dof.aperture_fstop = fstop; cam.dof.focus_distance = (Vector(focus) - Vector(loc)).length
def shot(path, w, h, samples, alpha=False):
    r.resolution_x, r.resolution_y = w, h; sc.cycles.samples = samples; r.film_transparent = alpha
    r.image_settings.color_mode = 'RGBA' if alpha else 'RGB'; r.filepath = path; bpy.ops.render.render(write_still=True); print('shot', path, flush=True)
J = os.environ.get('ZJOBS', 'pdp,spin,cut').split(',')
os.makedirs(OUTD, exist_ok=True)
# the Lightbox set: product page photos and the drag-to-turn frames (frame 6 is the lot side, a quarter turn)
aim((0, -21, 2.9), (0, 0, 1.55), 85, 2.8, (0, -0.6, 1.6))
if 'pdp' in J:
    for rot, nm in ((0, ''), (90, '-back')):
        v.rotation_euler = (0, 0, math.radians(rot)); shot(os.path.join(OUTD, 'vial-%s%s.png' % (NO, nm)), 720, 960, 48)
if 'spin' in J:
    for k in range(24):
        v.rotation_euler = (0, 0, math.radians(k * 15)); shot(os.path.join(OUTD, 'spin-%s-%02d.png' % (NO, k)), 540, 720, 24)
# cutouts: the vial alone, tilted and floating, on a transparent ground
if 'cut' in J or 'hspin' in J:
    for o_ in (bk, pl): o_.hide_render = True
    piv = bpy.data.objects.new('pivot', None); sc.collection.objects.link(piv); piv.location = (0, 0, 0); piv.rotation_mode = 'ZYX'
    v.parent = piv; v.location = (0, 0, -1.75); v.rotation_euler = (0, 0, 0)
    aim((0, -12.5, 0), (0, 0, 0), 85, 8, (0, 0, 0))
    def pose(spin): piv.rotation_euler = (math.radians(-14), math.radians(-28), math.radians(spin))
    if 'cut' in J: pose(0); shot(os.path.join(OUTD, 'hero-vial-%s.png' % NO), 1000, 1250, 48, alpha=True)
    if 'hspin' in J:
        for k in range(24): pose(k * 15); shot(os.path.join(OUTD, 'hspin-%s-%02d.png' % (NO, k)), 760, 950, 24, alpha=True)
print('siteimg done', NO)

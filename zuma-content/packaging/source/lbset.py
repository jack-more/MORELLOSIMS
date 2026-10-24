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
bk.scale = (17, 17, 1) if not os.environ.get('ZNOS') else (36, 21, 1) if os.environ.get('ZWALL') else (70, 40, 1); bpy.ops.object.transform_apply(scale=True)
if os.environ.get('ZWS'):                          # wall size and height for a lineup: sx, sz, z (so a dense grid fits the frame)
    sx_, sz_, z_ = map(float, os.environ['ZWS'].split(','))
    for v_ in bk.data.vertices: v_.co.x *= sx_ / 36; v_.co.z = z_ + (v_.co.z - 3.2) * sz_ / 21   # the mesh is already baked in place
em = bpy.data.materials.new('lightbox'); em.use_nodes = True; nt = em.node_tree; nt.nodes.clear()
o = nt.nodes.new('ShaderNodeOutputMaterial'); es = nt.nodes.new('ShaderNodeEmission'); es.inputs['Strength'].default_value = float(os.environ.get('ZLB', '1.0'))
ti = nt.nodes.new('ShaderNodeTexImage'); tp = os.environ.get('ZWALL') or os.path.join(SET, 'lb-%s.png' % NO); ti.image = bpy.data.images.load(tp if os.path.exists(tp) else os.path.join(SET, 'lb-%s.png' % AREA))
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
FLOOR = os.environ.get('ZFLOOR', 'ox')            # floor test: ox (lacquer), trav, saltillo, stucco, snow
if FLOOR == 'trav':
    t_ = open(os.path.join(HERE, 'trav.py')).read(); exec(compile(t_[t_.index('def travertine'):t_.index('def box')], 'trav.py', 'exec')); lm_ = travertine('travfloor')
    for nd in [nd for nd in lm_.node_tree.nodes if nd.type == 'MAPPING']:   # the wall's strata run vertically; on a floor they run along the slab, finer
        sx, sy, sz = nd.inputs['Scale'].default_value; nd.inputs['Scale'].default_value = (sx * 1.6, sz * 1.3, sx * 1.6)
elif FLOOR == 'saltillo':
    lm_, b_ = mat('saltillo', **{'Roughness': 0.62}); n_ = lm_.node_tree
    tc = n_.nodes.new('ShaderNodeTexCoord'); br = n_.nodes.new('ShaderNodeTexBrick'); br.offset = 0.0; br.inputs['Scale'].default_value = 0.42
    br.inputs['Mortar Size'].default_value = 0.006; br.inputs['Brick Width'].default_value = 1.0; br.inputs['Row Height'].default_value = 1.0
    br.inputs['Color1'].default_value = lin('#B8643E'); br.inputs['Color2'].default_value = lin('#A9532F'); br.inputs['Mortar'].default_value = lin('#9C7A5E')
    nz = n_.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.6; nz.inputs['Detail'].default_value = 10
    mx_ = n_.nodes.new('ShaderNodeMixRGB'); mx_.blend_type = 'MULTIPLY'; mx_.inputs['Fac'].default_value = 0.5
    n_.links.new(tc.outputs['Object'], br.inputs['Vector']); n_.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    n_.links.new(br.outputs['Color'], mx_.inputs['Color1']); n_.links.new(nz.outputs['Color'], mx_.inputs['Color2']); n_.links.new(mx_.outputs['Color'], b_.inputs['Base Color'])
    bp_ = n_.nodes.new('ShaderNodeBump'); bp_.inputs['Strength'].default_value = 0.25; n_.links.new(br.outputs['Fac'], bp_.inputs['Height']); n_.links.new(bp_.outputs['Normal'], b_.inputs['Normal'])
    b_.inputs['Coat Weight'].default_value = 0.2; b_.inputs['Coat Roughness'].default_value = 0.3
elif FLOOR == 'stucco':
    lm_, b_ = mat('stuccofloor', **{'Base Color': lin('#EFE4D2'), 'Roughness': 0.9}); n_ = lm_.node_tree
    n1 = n_.nodes.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = 0.6; n1.inputs['Detail'].default_value = 6
    n2 = n_.nodes.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 18; n2.inputs['Detail'].default_value = 8
    ma = n_.nodes.new('ShaderNodeMath'); ma.operation = 'MULTIPLY_ADD'; ma.inputs[1].default_value = 0.35
    n_.links.new(n2.outputs['Fac'], ma.inputs[0]); n_.links.new(n1.outputs['Fac'], ma.inputs[2])
    bp_ = n_.nodes.new('ShaderNodeBump'); bp_.inputs['Strength'].default_value = 0.55; n_.links.new(ma.outputs['Value'], bp_.inputs['Height'])
    cv_ = n_.nodes.new('ShaderNodeMixRGB'); cv_.inputs['Color1'].default_value = lin('#EFE4D2'); cv_.inputs['Color2'].default_value = lin('#DCCBB0')   # hand-trowelled: soft clouds of a deeper tone
    n_.links.new(n1.outputs['Fac'], cv_.inputs['Fac']); n_.links.new(cv_.outputs['Color'], b_.inputs['Base Color']); n_.links.new(bp_.outputs['Normal'], b_.inputs['Normal'])
elif FLOOR in ('hinoki', 'yakisugi'):
    # Japanese wood: long planks with a fine straight grain; hinoki pale and oiled, yakisugi charred cedar
    dark = FLOOR == 'yakisugi'
    lm_, b_ = mat(FLOOR, **{'Roughness': 0.78 if dark else 0.42, 'Coat Weight': 0.0 if dark else 0.35, 'Coat Roughness': 0.25}); n_ = lm_.node_tree
    tc = n_.nodes.new('ShaderNodeTexCoord')
    # grain: fine straight bands running away from the camera, wandering a little
    mp_ = n_.nodes.new('ShaderNodeMapping'); mp_.inputs['Scale'].default_value = (26.0, 0.9, 1.0); n_.links.new(tc.outputs['Object'], mp_.inputs['Vector'])
    wv = n_.nodes.new('ShaderNodeTexNoise'); wv.inputs['Scale'].default_value = 1.0; wv.inputs['Detail'].default_value = 12; wv.inputs['Roughness'].default_value = 0.62
    wv.inputs['Distortion'].default_value = 0.4; n_.links.new(mp_.outputs['Vector'], wv.inputs['Vector'])   # stretched noise: long, irregular streaks of grain
    rp = n_.nodes.new('ShaderNodeValToRGB'); rp.color_ramp.elements[0].position = 0.3; rp.color_ramp.elements[1].position = 0.7
    rp.color_ramp.elements[0].color = lin('#140D0A' if dark else '#CDAA78'); rp.color_ramp.elements[1].color = lin('#3A2B23' if dark else '#ECD7B3')
    n_.links.new(wv.outputs['Fac'], rp.inputs['Fac'])
    # planks: long boards running away from the camera, a hairline seam between them
    pm2 = n_.nodes.new('ShaderNodeMapping'); pm2.inputs['Rotation'].default_value = (0, 0, math.radians(90)); n_.links.new(tc.outputs['Object'], pm2.inputs['Vector'])
    pk = n_.nodes.new('ShaderNodeTexBrick'); pk.inputs['Scale'].default_value = 0.3; pk.inputs['Brick Width'].default_value = 12.0; pk.inputs['Row Height'].default_value = 1.0
    pk.inputs['Mortar Size'].default_value = 0.006; pk.inputs['Color1'].default_value = (1, 1, 1, 1); pk.inputs['Color2'].default_value = (0.86, 0.86, 0.86, 1); pk.inputs['Mortar'].default_value = (0.25, 0.25, 0.25, 1)
    n_.links.new(pm2.outputs['Vector'], pk.inputs['Vector'])
    mm = n_.nodes.new('ShaderNodeMixRGB'); mm.blend_type = 'MULTIPLY'; mm.inputs['Fac'].default_value = 1.0
    n_.links.new(rp.outputs['Color'], mm.inputs['Color1']); n_.links.new(pk.outputs['Color'], mm.inputs['Color2']); n_.links.new(mm.outputs['Color'], b_.inputs['Base Color'])
    bp_ = n_.nodes.new('ShaderNodeBump'); bp_.inputs['Strength'].default_value = 0.22 if dark else 0.05
    n_.links.new(wv.outputs['Fac'], bp_.inputs['Height']); n_.links.new(bp_.outputs['Normal'], b_.inputs['Normal'])
elif FLOOR == 'snow':
    lb_.inputs['Base Color'].default_value = lin('#FCFBF8'); lb_.inputs['Roughness'].default_value = 0.12; lb_.inputs['Coat Weight'].default_value = 1.0; lb_.inputs['Coat Roughness'].default_value = 0.03
pl.data.materials.append(lm_)

LINE = os.environ.get('ZNOS')                     # a lineup: several vials in a row, the camera pulled back to hold them
if LINE:
    nos = LINE.split(','); gap = 2.5; rows = int(os.environ.get('ZROWS', '1'))
    per = (len(nos) + rows - 1) // rows
    for i, n_ in enumerate(nos):
        v = vial3(n_)
        if rows == 1: v.location = ((i - (len(nos) - 1) / 2) * gap, 0, 0)
        else:                                      # two staggered rows: the back row sits half a step over and further back
            r_, k_ = divmod(i, per); v.location = ((k_ - (per - 1) / 2) * 3.4 + (0.0 if r_ else 1.7) - 0.85, 2.6 if r_ == 0 else -1.4, 0)
            v.rotation_euler = (0, 0, math.radians((k_ * 37 % 11) - 5))
        if n_ == '03':                             # BAC water is a liquid: no cake
            for o_ in [o_ for o_ in v.children if o_.name.startswith('cake')]: bpy.data.objects.remove(o_, do_unlink=True)
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

cam = bpy.data.cameras.new('cam'); co = bpy.data.objects.new('cam', cam); sc.collection.objects.link(co); sc.camera = co
cam.sensor_width = 36; cam.lens = 85; co.location = tuple(map(float, os.environ['ZCAM'].split(','))) if os.environ.get('ZCAM') else (0, -21, 2.9) if not LINE else (0, -40, 4.4); look = Vector(tuple(map(float, os.environ['ZLOOK'].split(','))) if os.environ.get('ZLOOK') else (0, 0, 1.55))
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

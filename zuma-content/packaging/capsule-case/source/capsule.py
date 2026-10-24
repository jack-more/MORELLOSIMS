# A silicone capsule case for one vial, the ZUMA crest pressed into it all over (Blender Cycles via bpy).
#   ZCOL=#6E1C2A ZBG=lb-01 bpyenv/bin/python cyc/capsule/capsule.py OUT W H SAMPLES
# Matte silicone, two halves meeting at a fine seam, leaning on a Snow carton in front of a Lightbox. Units are centimetres.
import bpy, math, os, sys
from mathutils import Vector
CAP = os.path.dirname(os.path.abspath(__file__)); HERE = os.path.dirname(CAP); TEX = os.path.join(HERE, 'tex')
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
CARGS = list(args); OUT = CARGS[0]
src = open(os.path.join(HERE, 'vial.py')).read(); sys.argv = ['vial.py', 'front', '05', OUT]
__file__ = os.path.join(HERE, 'vial.py'); exec(compile(src[:src.index("if SHOT == 'lineup':")], 'vial.py', 'exec'))
W, H, SAMPLES = int(CARGS[1]), int(CARGS[2]), int(CARGS[3])
COL = os.environ.get('ZCOL', '#6E1C2A')

# the capsule: hemispherical ends, a straight body, a hairline seam at the middle
R, L = 1.15, 6.4
T0 = 31.0; D0 = R - R * math.cos(math.radians(T0))     # a flat seat ~12 mm across under the bottom end, so it stands on its own
prof = [(0.0, 0.0)] + [(R * math.sin(math.radians(t)), R - R * math.cos(math.radians(t)) - D0) for t in [T0] + list(range(35, 91, 5))]
prof += [(R, L / 2 - 0.05 - D0 / 2), (R - 0.03, L / 2 - 0.012 - D0 / 2), (R - 0.03, L / 2 + 0.012 - D0 / 2), (R, L / 2 + 0.05 - D0 / 2), (R, L - R - D0)]
prof += [(R * math.cos(math.radians(t)), L - R - D0 + R * math.sin(math.radians(t))) for t in range(5, 91, 5)]
def make_capsule(COL, name='capsule'):
    cap = lathe(name, prof, seg=256)
    me = cap.data; uv = me.uv_layers.new(name='UV')
    for poly in me.polygons:
        for li in poly.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co; a = math.atan2(v.y, v.x)
            uv.data[li].uv = (((a + math.pi / 2) / (2 * math.pi) + 0.5) % 1.0, v.z / L)
    for poly in me.polygons:
        us = [uv.data[li].uv[0] for li in poly.loop_indices]
        if max(us) - min(us) > 0.5:
            for li in poly.loop_indices:
                if uv.data[li].uv[0] < 0.5: uv.data[li].uv = (uv.data[li].uv[0] + 1, uv.data[li].uv[1])
    m, b = mat(name + '-sil', **{'Base Color': lin(COL), 'Roughness': 0.58, 'Specular IOR Level': 0.35, 'Subsurface Weight': 0.08, 'Subsurface Radius': (0.1, 0.05, 0.04)})
    nt = m.node_tree; img = nt.nodes.new('ShaderNodeTexImage'); img.image = bpy.data.images.load(os.path.join(CAP, 'pattern.png')); img.image.colorspace_settings.name = 'Non-Color'
    img.interpolation = 'Cubic'; bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 1.0; bp.inputs['Distance'].default_value = 0.06
    nt.links.new(img.outputs['Color'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    # the pressed shapes sit a touch darker, the way silicone reads where it is thinner
    dk = nt.nodes.new('ShaderNodeMixRGB'); dk.blend_type = 'MULTIPLY'; dk.inputs['Color1'].default_value = lin(COL)
    inv = nt.nodes.new('ShaderNodeInvert'); nt.links.new(img.outputs['Color'], inv.inputs['Color'])
    mr = nt.nodes.new('ShaderNodeMath'); mr.operation = 'MULTIPLY'; mr.inputs[1].default_value = 0.32; nt.links.new(inv.outputs['Color'], mr.inputs[0])
    dk.inputs['Color2'].default_value = (0.55, 0.55, 0.55, 1); nt.links.new(mr.outputs['Value'], dk.inputs['Fac']); nt.links.new(dk.outputs['Color'], b.inputs['Base Color'])
    cap.data.materials.append(m)

    return cap
MULTI = os.environ.get('ZMULTI')                     # several capsules lying side by side, one per colour
if not MULTI:
    cap = make_capsule(COL)
    piv = bpy.data.objects.new('piv', None); sc.collection.objects.link(piv); cap.parent = piv
    piv.location = (0.9, -0.6, 0); piv.rotation_euler = (0, 0, math.radians(-25))
else:
    cols = MULTI.split(',')
    for i, c_ in enumerate(cols):
        cp = make_capsule(c_, 'cap%d' % i); pv = bpy.data.objects.new('pv%d' % i, None); sc.collection.objects.link(pv); cp.parent = pv
        pv.location = ((i - (len(cols) - 1) / 2) * 3.0, (i % 2) * 1.4 - 0.7, 0); pv.rotation_euler = (0, 0, math.radians(-20 + (i * 37) % 40))

def box(name, size, loc, col, rough=0.8):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.active_object; o.name = name; o.scale = size
    bpy.ops.object.transform_apply(scale=True); bv = o.modifiers.new('b', 'BEVEL'); bv.width = 0.06; bv.segments = 4
    mm, bb = mat(name, **{'Base Color': lin(col), 'Roughness': rough}); o.data.materials.append(mm); return o
box('floor', (60, 60, 1), (0, 10, -0.5), '#E9EEF2', 0.7)
if not MULTI: box('carton', (3.2, 3.2, 9.5), (-1.55, 1.6, 4.75), '#FCFBF8', 0.65)
# the Lightbox far behind, soft through the lens
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 20, 9), rotation=(math.radians(90), 0, 0)); bk = bpy.context.active_object; bk.scale = (46, 30, 1)
em = bpy.data.materials.new('lb'); em.use_nodes = True; ent = em.node_tree; ent.nodes.clear(); o_ = ent.nodes.new('ShaderNodeOutputMaterial'); es = ent.nodes.new('ShaderNodeEmission')
ti = ent.nodes.new('ShaderNodeTexImage'); ti.image = bpy.data.images.load(os.path.join(HERE, 'lbset', os.environ.get('ZBG', 'lb-01') + '.png'))
ent.links.new(ti.outputs['Color'], es.inputs['Color']); ent.links.new(es.outputs['Emission'], o_.inputs['Surface']); bk.data.materials.append(em)

world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True; wn = world.node_tree
env = wn.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(os.path.join(TEX, 'studio.hdr'))
bg = wn.nodes['Background']; bg.inputs['Strength'].default_value = 0.35; wn.links.new(env.outputs['Color'], bg.inputs['Color'])
def area(name, size, loc, power, look=(0.4, 0, 3), sx=None, col=(1, 1, 1)):
    l = bpy.data.lights.new(name, 'AREA'); l.shape = 'RECTANGLE'; l.size = size; l.size_y = sx or size; l.energy = power; l.color = col
    ob = bpy.data.objects.new(name, l); sc.collection.objects.link(ob); ob.location = loc
    d = Vector(look) - Vector(loc); ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
area('key', 16, (-16, -18, 16), 3200, col=(1, 0.97, 0.93))
area('rim', 4, (12, 4, 10), 900, sx=14)
area('fill', 30, (10, -40, 6), 1400)
cam = bpy.data.cameras.new('cam'); co = bpy.data.objects.new('cam', cam); sc.collection.objects.link(co); sc.camera = co
cam.sensor_width = 36; cam.lens = 85; co.location = (2.0, -27, 4.4) if not MULTI else (0, -52, 10.5); look = Vector((0.3, 0, 3.4)) if not MULTI else Vector((0, 0.4, 3.0))
d = look - co.location; co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
cam.dof.use_dof = True; cam.dof.focus_distance = (Vector((1.1, 0, 3.2)) - co.location).length if not MULTI else (look - co.location).length; cam.dof.aperture_fstop = 4
r = sc.render; r.engine = 'CYCLES'; r.resolution_x, r.resolution_y = W, H; r.resolution_percentage = 100
sc.cycles.device = 'CPU'; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True; sc.view_settings.view_transform = 'Standard'
r.image_settings.file_format = 'PNG'; r.filepath = OUT
bpy.ops.render.render(write_still=True); print('rendered', OUT)

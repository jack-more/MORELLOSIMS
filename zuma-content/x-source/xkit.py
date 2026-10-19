# X profile kit, rendered physically (Blender Cycles via the bpy module).
#   bpyenv/bin/python cyc/xkit.py pfp|banner OUT W H SAMPLES
# pfp: the flower mark as a raised piano-black lacquer inlay on warm cotton paper, raking light from top left.
# banner: one vial per area in a row on a paper sweep, low sun from behind right throwing long shadows across the empty left.
import bpy, math, os, sys, json, addon_utils
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__)); TEX = os.path.join(HERE, 'tex')
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
XARGS = list(args); KIND, OUT = XARGS[0], XARGS[1]

# borrow the vial, materials and helpers from vial.py: run its header (everything before the shot set-ups)
src = open(os.path.join(HERE, 'vial.py')).read()
sys.argv = ['vial.py', 'front', '01', OUT]
exec(compile(src[:src.index("if SHOT == 'lineup':")], 'vial.py', 'exec'))
W, H, SAMPLES = int(XARGS[2]), int(XARGS[3]), int(XARGS[4])   # the header set its own defaults and args

def area(name, size, loc, power, look=(0, 0, 3.2), sx=None):
    l = bpy.data.lights.new(name, 'AREA'); l.shape = 'RECTANGLE'; l.size = size; l.size_y = sx or size; l.energy = power
    o = bpy.data.objects.new(name, l); sc.collection.objects.link(o); o.location = loc
    d = Vector(look) - Vector(loc); o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); return o

def paper(name, hexc, tooth=0.05):
    m, b = mat(name, **{'Base Color': lin(hexc), 'Roughness': 0.88}); nt = m.node_tree
    fine = nt.nodes.new('ShaderNodeTexNoise'); fine.inputs['Scale'].default_value = 420; fine.inputs['Detail'].default_value = 6
    soft = nt.nodes.new('ShaderNodeTexNoise'); soft.inputs['Scale'].default_value = 6
    add = nt.nodes.new('ShaderNodeMath'); add.operation = 'MULTIPLY_ADD'; add.inputs[1].default_value = 0.15
    nt.links.new(soft.outputs['Fac'], add.inputs[0]); nt.links.new(fine.outputs['Fac'], add.inputs[2])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = tooth
    nt.links.new(add.outputs['Value'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m

world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True; wn = world.node_tree
env = wn.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(os.path.join(TEX, 'studio.hdr'))
bg = wn.nodes['Background']; wn.links.new(env.outputs['Color'], bg.inputs['Color'])
cam = bpy.data.cameras.new('cam'); co = bpy.data.objects.new('cam', cam); sc.collection.objects.link(co); sc.camera = co; cam.sensor_width = 36

def aim(o, target): d = Vector(target) - o.location; o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

if KIND == 'pfp':
    # the mark as geometry: SVG -> 2D curve with even-odd holes -> extruded, bevelled
    F = json.load(open(os.path.join(HERE, '..', 'ad', 'final.json')))
    svg = os.path.join(HERE, 'mark-tmp.svg')
    open(svg, 'w').write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {F["mw"]} 110"><path fill-rule="evenodd" fill="#000" d="{F["mark"]}"/></svg>')
    addon_utils.enable('io_curve_svg', default_set=True)
    before = set(bpy.data.objects); bpy.ops.import_curve.svg(filepath=svg)
    curves = [o for o in bpy.data.objects if o not in before and o.type == 'CURVE']
    bpy.ops.object.select_all(action='DESELECT')
    for o in curves: o.select_set(True)
    bpy.context.view_layer.objects.active = curves[0]
    if len(curves) > 1: bpy.ops.object.join()
    mk = bpy.context.view_layer.objects.active; mk.name = 'mark'
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    s = 15.0 / mk.dimensions.x; mk.scale = (s, s, s); mk.location = (0, 0, 0); mk.rotation_euler = (0, 0, 0)
    cu = mk.data; cu.dimensions = '2D'; cu.fill_mode = 'BOTH'
    cu.extrude = 0.05 / s; cu.bevel_depth = 0.075 / s; cu.bevel_resolution = 6;   # domed enamel strokes: the round tops catch highlights cu.resolution_u = 24
    mk.location.z = 0.05 + 0.02
    lac, lb = mat('lacquer', **{'Base Color': lin('#0B0B0D'), 'Roughness': 0.1, 'Coat Weight': 1.0, 'Coat Roughness': 0.02})
    cu.materials.append(lac)
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0)); pp = bpy.context.active_object; pp.data.materials.append(paper('paper', '#F6F3EC', 0.06))
    # light: a long soft box raking from top left, a faint fill from the right, a strip that draws the lacquer's edge highlight
    area('key', 12, (-26, 18, 11), 26000, look=(0, 0, 0), sx=30)
    area('fill', 20, (26, -14, 30), 5000, look=(0, 0, 0))
    area('top', 40, (0, -30, 80), 14000, look=(0, 0, 0))     # the broad soft reflection that makes the lacquer read glossy
    area('rim', 1.0, (10, 22, 6), 2400, look=(0, 0, 0), sx=30)
    bg.inputs['Strength'].default_value = 0.25
    cam.lens = 85; co.location = (0, -5.0, 62); aim(co, (0, 0.2, 0))
    cam.dof.use_dof = True; cam.dof.focus_distance = (co.location - Vector((0, 0, 0))).length; cam.dof.aperture_fstop = 5.6
    sc.view_settings.exposure = -0.3

else:
    NOS = ['01', '09', '05', '04', '11', '03']            # one per area: metabolic, tissue, dermal, endocrine, neuro, supplies
    xs = [3.0 + k * 3.55 for k in range(len(NOS))]
    for k, n in enumerate(NOS):
        rr, _ = make_vial(n); rr.location = (xs[k], (k % 2) * 0.9, 0); rr.rotation_euler = (0, 0, math.radians(-14 + k * 5))
    # paper sweep: floor curving up into a wall far behind
    import bmesh
    bm = bmesh.new(); path = [(y, 0.0) for y in range(-60, 14)]
    for k in range(1, 25): a = k / 24 * math.pi / 2; path.append((14 + 14 * math.sin(a), 14 * (1 - math.cos(a))))
    path += [(28, z) for z in range(16, 80, 3)]
    rows = [[bm.verts.new((x, y, z)) for x in (-120, 120)] for (y, z) in path]
    for i in range(len(rows) - 1): bm.faces.new((rows[i][0], rows[i][1], rows[i + 1][1], rows[i + 1][0]))
    me = bpy.data.meshes.new('sweep'); bm.to_mesh(me); bm.free(); sw = bpy.data.objects.new('sweep', me); sc.collection.objects.link(sw)
    for p in me.polygons: p.use_smooth = True
    sw.data.materials.append(paper('sweep', '#EFE9DE', 0.03))
    # low late sun from behind right: long shadows run forward and left over the empty side of the frame
    sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 20.0; sun.angle = math.radians(0.6); sun.color = (1.0, 0.88, 0.72)
    so = bpy.data.objects.new('sun', sun); sc.collection.objects.link(so)
    so.rotation_euler = Vector((-1.0, 0.42, -0.26)).to_track_quat('-Z', 'Y').to_euler()   # from front right, low: shadows run back and left
    area('fill', 18, (-30, -30, 14), 500, look=(8, 0, 3))
    area('strip', 1.2, (30, -8, 7), 1200, look=(10, 0, 3), sx=18)
    bg.inputs['Strength'].default_value = 0.22
    sc.view_settings.exposure = 0.0
    cam.lens = 50; co.location = (6.5, -52, 9.0); aim(co, (6.5, 2, 3.4))
    cam.dof.use_dof = True; cam.dof.focus_distance = 52; cam.dof.aperture_fstop = 8

r = sc.render; r.engine = 'CYCLES'; r.resolution_x, r.resolution_y = W, H; r.resolution_percentage = 100
sc.cycles.device = 'CPU'; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 16; sc.cycles.transmission_bounces = 16; sc.cycles.glossy_bounces = 8; sc.cycles.transparent_max_bounces = 16
sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
sc.view_settings.view_transform = 'Standard' if KIND == 'pfp' else 'AgX'     # the pfp needs a true white paper
if KIND != 'pfp':
    try: sc.view_settings.look = 'AgX - Punchy'
    except Exception: pass
r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGB'; r.filepath = OUT
bpy.ops.render.render(write_still=True)
print('rendered', OUT)

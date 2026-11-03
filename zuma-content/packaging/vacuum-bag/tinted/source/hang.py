# ZUMA rail shot: the 12 vacuum bags hung from two black rails by binder clips on wire rings (Cycles).
#   bpyenv/bin/python hang.py OUT W H SAMPLES
import bpy, sys, os, math, glob, random
from mathutils import Vector, Matrix
OUT, W, H, SAMP = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hang')
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = SAMP; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = W, H; sc.render.film_transparent = False
sc.view_settings.view_transform = 'AgX'
sc.cycles.max_bounces = 16; sc.cycles.transparent_max_bounces = 32; sc.cycles.transmission_bounces = 16
def srgb(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c) + (1,)
def pmat(name, col, rough=0.4, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = col; b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal; return m
BLACK = pmat('clip', srgb('#141414'), 0.28); STEEL = pmat('wire', (0.8, 0.8, 0.82, 1), 0.18, 1.0); RAIL = pmat('rail', srgb('#0F0F10'), 0.32)
WALL = pmat('wall', srgb('#D9D8D5'), 0.9)
random.seed(5)
PITCH, ROWZ = 11.5, (0.0, -21.0)
def bag(path, loc, yaw):
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    hold = bpy.data.objects.new('hold', None); sc.collection.objects.link(hold)
    for o in dst.objects:
        if o is None or o.type in ('LIGHT', 'CAMERA'): continue
        if o.type == 'MESH' and max(o.dimensions) > 30: continue
        sc.collection.objects.link(o)
    for o in dst.objects:
        if o is None or o.name not in sc.collection.objects: continue
        if o.parent is None:
            o.parent = hold; o.matrix_parent_inverse = Matrix.Identity(4)
    # stand the bag up: the cap end (+y) goes up, the printed front (+z) faces the camera (-y)
    hold.rotation_euler = (math.radians(90), 0, math.radians(yaw)); hold.location = loc
    return hold
def tube(name, pts, r, m):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = r; cu.bevel_resolution = 4
    sp = cu.splines.new('BEZIER'); sp.bezier_points.add(len(pts) - 1)
    for p, c in zip(sp.bezier_points, pts): p.co = c; p.handle_left_type = p.handle_right_type = 'AUTO'
    o = bpy.data.objects.new(name, cu); o.data.materials.append(m); sc.collection.objects.link(o); return o
def clip(cx, cz, yaw):
    # a 25 mm black binder clip gripping the top seal, its two wire arms up to a ring round the rail
    g = bpy.data.objects.new('clipg', None); sc.collection.objects.link(g)
    bpy.ops.mesh.primitive_cube_add(size=1); b = bpy.context.active_object; b.scale = (2.5, 0.75, 1.0); b.location = (0, 0, 5.25 - 0.1)
    bv = b.modifiers.new('bv', 'BEVEL'); bv.width = 0.06; bv.segments = 3; b.data.materials.append(BLACK)
    # the clip tapers to its jaws: pinch the bottom
    for v in b.data.vertices:
        if v.co.z < 0: v.co.y *= 0.25
    b.parent = g
    for s in (-1, 1):
        a = tube('arm', [Vector((s * 1.05, 0, 5.75)), Vector((s * 0.9, 0, 6.6)), Vector((s * 0.25, 0, 7.4))], 0.045, STEEL); a.parent = g
    g.rotation_euler = (0, 0, math.radians(yaw)); g.location = (cx, 0, cz); return g
files = sorted(glob.glob(os.path.join(D, 'bag-*.blend')))
RAILR, RAILZ = 0.75, 9.6
for k, f in enumerate(files):
    row, col = divmod(k, 6)
    x = col * PITCH; z0 = ROWZ[row]
    camx = float(os.environ.get('CX', '-22')); yaw = -math.degrees(math.atan2(x - camx, float(os.environ.get('CD', '95')))) * 0.6 + random.uniform(-5, 5)
    bag(f, (x, 0, z0), yaw)
    clip(x, z0, yaw)
    # the wire ring over the rail
    bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.045, location=(x, 0, z0 + RAILZ - 0.15), rotation=(math.radians(90), 0, math.radians(90)))
    r = bpy.context.active_object; r.data.materials.append(STEEL)
    tube('hook', [Vector((x, 0, z0 + 7.4)), Vector((x, 0, z0 + 8.2)), Vector((x, 0, z0 + RAILZ - 1.1))], 0.045, STEEL)
for z0 in ROWZ:
    bpy.ops.mesh.primitive_cylinder_add(radius=RAILR, depth=120, location=(PITCH * 2.5, 0, z0 + RAILZ + RAILR - 0.2), rotation=(0, math.radians(90), 0), vertices=64)
    bpy.context.active_object.data.materials.append(RAIL); bpy.ops.object.shade_smooth()
bpy.ops.mesh.primitive_plane_add(size=600, location=(0, 40, 0), rotation=(math.radians(90), 0, 0)); bpy.context.active_object.data.materials.append(WALL)
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = srgb('#D4D3D0'); w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.7
def area(loc, size, power, sy=None):
    ld = bpy.data.lights.new('a', 'AREA'); ld.energy = power; ld.shape = 'RECTANGLE'; ld.size = size; ld.size_y = sy or size
    o = bpy.data.objects.new('a', ld); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector((PITCH * 2.5, 0, -6)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return o
area((-40, -80, 60), 70, 160000); area((110, -60, 10), 40, 50000); area((30, -30, 90), 60, 40000)
cam = bpy.data.cameras.new('c'); cam.lens = float(os.environ.get('LENS', '55')); co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co); sc.camera = co
co.location = Vector((float(os.environ.get('CX', '-22')), -float(os.environ.get('CD', '95')), float(os.environ.get('CZ', '6'))))
tgt = Vector((float(os.environ.get('TX', '22')), 0, float(os.environ.get('TZ', '-6')))); co.rotation_euler = (tgt - co.location).to_track_quat('-Z', 'Y').to_euler()
co.rotation_euler.y += math.radians(float(os.environ.get('ROLL', '-6')))
sc.render.filepath = OUT; bpy.ops.render.render(write_still=True); print('rendered', OUT)

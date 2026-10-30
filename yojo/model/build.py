# YOJO GHK-Cu vessel: parametric model + studio render (Blender 5.2, bpy module)
# usage: python build.py <shot> <out.png> <res_x> <res_y> <samples> [open_mm]
import sys, math, os
import numpy as np
import bpy
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SHOT = sys.argv[1] if len(sys.argv) > 1 else 'hero'
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'out.png')
RX, RY = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (800, 1000)
SAMPLES = int(sys.argv[5]) if len(sys.argv) > 5 else 64
OPEN = float(sys.argv[6]) if len(sys.argv) > 6 else 9.0   # head lift above locked, mm
MM = 0.001

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------- helpers ----------
def srgb_to_lin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)

def load_mask(path, blur):
    im = Image.open(path).convert('L')
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(im, dtype=np.float32) / 255.0

def bilinear(img, px, py):
    h, w = img.shape
    px = np.clip(px, 0, w - 1.001); py = np.clip(py, 0, h - 1.001)
    x0 = np.floor(px).astype(int); y0 = np.floor(py).astype(int)
    fx = px - x0; fy = py - y0
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy)
            + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)

def lathe(name, R, Z, C, bottom_center=None, top_center=None, mats=None, face_mat_rows=None):
    """R, Z: (rows, C) arrays. Rows go bottom->top along the surface. Builds quads between
    consecutive rings plus optional center fans. Returns object."""
    rows = R.shape[0]
    th = np.linspace(0, 2 * np.pi, C, endpoint=False)
    X = R * np.cos(th)[None, :]; Y = R * np.sin(th)[None, :]
    verts = np.stack([X, Y, Z], -1).reshape(-1, 3) * MM
    faces = []
    j = np.arange(C); jn = (j + 1) % C
    for r in range(rows - 1):
        a = r * C
        faces.append(np.stack([a + j, a + jn, a + C + jn, a + C + j], -1))
    quads = np.concatenate(faces).tolist()
    tris = []
    vlist = verts.tolist()
    if bottom_center is not None:
        ci = len(vlist); vlist.append([0, 0, bottom_center * MM])
        tris += [[ci, int(jj2), int(jj)] for jj, jj2 in zip(j, jn)]
    if top_center is not None:
        ci = len(vlist); vlist.append([0, 0, top_center * MM])
        a = (rows - 1) * C
        tris += [[a + int(jj), a + int(jj2), ci] for jj, jj2 in zip(j, jn)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(vlist, [], quads + tris)
    me.update()
    me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    if mats:
        for m in mats:
            me.materials.append(m)
    return ob, len(quads)

def catmull(points, n):
    P = np.array(points, dtype=float)
    P = np.vstack([P[0] * 2 - P[1], P, P[-1] * 2 - P[-2]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2])
    return np.array(out)

# ---------- materials ----------
def principled(name, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    for k, v in kw.items():
        if k in b.inputs:
            b.inputs[k].default_value = v
    return m, b

SKY = (tuple(map(float, os.environ['SKIN_LIN'].split(','))) + (1.0,)) if os.environ.get('SKIN_LIN') else srgb_to_lin(os.environ.get('SKIN', '#62B0E4'))
BG = os.environ.get('BG', 'black')
EXPO = float(os.environ.get('EXPO', '0'))
skin, skin_b = principled('skin_silicone', **{'Base Color': SKY, 'Roughness': 0.62,
                          'Sheen Weight': 0.55, 'Sheen Roughness': 0.35, 'Sheen Tint': (1.0, 1.0, 1.0, 1.0), 'Subsurface Weight': 0.06,
                          'Subsurface Scale': 0.002, 'Specular IOR Level': 0.35})
nt = skin.node_tree
nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 2500.0; nz.inputs['Detail'].default_value = 2.0
tc = nt.nodes.new('ShaderNodeTexCoord'); nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.06; bump.inputs['Distance'].default_value = 0.00005
nt.links.new(nz.outputs['Fac'], bump.inputs['Height']); nt.links.new(bump.outputs['Normal'], skin_b.inputs['Normal'])

chrome, _ = principled('chrome', **{'Base Color': (0.93, 0.94, 0.95, 1), 'Metallic': 1.0, 'Roughness': 0.07})
mirror, _ = principled('engrave_frost', **{'Base Color': (0.5, 0.52, 0.55, 1), 'Metallic': 1.0, 'Roughness': 0.5})
brushed, br_b = principled('brushed_satin', **{'Base Color': (0.9, 0.91, 0.92, 1), 'Metallic': 1.0, 'Roughness': 0.14,
                          'Anisotropic': 0.75})
tg = brushed.node_tree.nodes.new('ShaderNodeTangent'); tg.direction_type = 'RADIAL'; tg.axis = 'Z'
brushed.node_tree.links.new(tg.outputs['Tangent'], br_b.inputs['Tangent'])
slotm, _ = principled('slot', **{'Base Color': (0.01, 0.01, 0.012, 1), 'Roughness': 0.35})
floor_m, _ = principled('floor', **{'Base Color': (0.0, 0.0, 0.0, 1), 'Roughness': 0.06, 'Specular IOR Level': 0.5})

# ---------- egg skin ----------
prof = [(0.0, 0.3), (0.0, 10.0), (0.4, 14.0), (1.3, 16.8), (2.86, 18.9), (4.53, 21.3), (6.2, 23.3),
        (7.9, 25.1), (9.5, 26.6), (11.2, 27.9), (12.9, 29.1), (14.6, 29.9), (16.2, 30.8), (17.9, 31.4),
        (19.6, 32.1), (21.3, 32.6), (24.6, 33.5), (27.9, 34.0), (31.3, 34.0), (34.6, 34.0), (38.0, 33.7),
        (41.3, 33.2), (44.7, 32.3), (48.0, 31.5), (51.4, 30.6), (54.7, 29.6), (58.1, 28.4), (61.4, 26.9),
        (64.7, 25.4), (67.2, 24.0), (69.0, 22.4), (70.1, 20.2), (70.55, 17.6), (70.45, 15.9), (69.9, 15.1),
        (66.0, 14.95)]   # traced from the approved hero render, scaled to 68 mm wide
P = catmull([(r, z) for z, r in prof], 40)          # columns: r, z
seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = np.concatenate([[0], np.cumsum(seg)])
# resample evenly and smooth out tracing noise (sigma 1.2 mm along the surface)
su = np.arange(0, s[-1], 0.1); Pu = np.stack([np.interp(su, s, P[:, 0]), np.interp(su, s, P[:, 1])], 1)
k = np.exp(-0.5 * (np.arange(-40, 41) / 12.0) ** 2); k /= k.sum()
pad = np.pad(Pu, ((40, 40), (0, 0)), mode='edge')
Ps = np.stack([np.convolve(pad[:, i], k, mode='valid') for i in range(2)], 1)
Ps[:3] = Pu[:3]; Ps[-3:] = Pu[-3:]
P = Ps
seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = np.concatenate([[0], np.cumsum(seg)])
def density(z):  # rows per mm along the surface
    return np.where((z > 14) & (z < 40), 8.0, 2.2)
targets = [0.0]
while targets[-1] < s[-1]:
    zc = np.interp(targets[-1], s, P[:, 1])
    targets.append(targets[-1] + 1.0 / float(density(zc)))
targets = np.array(targets[:-1] + [s[-1]])
pr = np.interp(targets, s, P[:, 0]); pz = np.interp(targets, s, P[:, 1])
# outward normals in (r,z)
dr = np.gradient(pr); dz = np.gradient(pz); L = np.hypot(dr, dz) + 1e-12
nr, nzz = dz / L, -dr / L
C_EGG = 1600
th = np.linspace(0, 2 * np.pi, C_EGG, endpoint=False)
R = np.repeat(pr[:, None], C_EGG, 1); Z = np.repeat(pz[:, None], C_EGG, 1)
# deboss: front is -Y (theta = -pi/2). arc coordinate x_s = (theta - (-pi/2)) wrapped * r
egg_mask = load_mask(os.path.join(HERE, 'egg-mask.png'), 1.4)
dth = (th[None, :] + np.pi / 2 + np.pi) % (2 * np.pi) - np.pi      # 0 at the front, + toward +X
xs = dth * R    # camera sits at -Y, so +X reads to the right
px = (xs + 60) * 20; py = (92 - Z) * 20
m = np.where(np.abs(xs) < 59, bilinear(egg_mask, px, py), 0.0)
DEP = 0.5
R = R - DEP * m * nr[:, None]; Z = Z - DEP * m * nzz[:, None]
egg, _ = lathe('egg_skin', R, Z, C_EGG, bottom_center=0.0, mats=[skin])

# ---------- threaded sleeve ----------
import bmesh
LOCK_Z = 70.55          # head underside when locked
HEAD_Z0 = LOCK_Z + OPEN
pitch = 1.5; z_lo = 62.0; z_hi = HEAD_Z0 + 0.4
turns = (z_hi - z_lo) / pitch; steps_per = 96; steps = int(turns * steps_per)
bm = bmesh.new()
pts = [(13.3, -0.70), (15.0, -0.14), (15.0, 0.14), (13.3, 0.70)]
vs = [bm.verts.new((r * MM, 0, (z_lo + dzz) * MM)) for r, dzz in pts]
es = [bm.edges.new((vs[i], vs[i + 1])) for i in range(3)]
bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), dvec=(0, 0, pitch / steps_per * MM),
               angle=2 * math.pi * turns, steps=steps, use_duplicate=False)
me = bpy.data.meshes.new('sleeve'); bm.to_mesh(me); bm.free(); me.shade_smooth()
sleeve = bpy.data.objects.new('sleeve_thread', me); bpy.context.collection.objects.link(sleeve)
me.materials.append(chrome)
es_mod = sleeve.modifiers.new('es', 'EDGE_SPLIT'); es_mod.split_angle = math.radians(35)
# core
bpy.ops.mesh.primitive_cylinder_add(vertices=256, radius=13.36 * MM, depth=(z_hi - z_lo) * MM,
                                    location=(0, 0, (z_lo + z_hi) / 2 * MM))
core = bpy.context.active_object; core.name = 'sleeve_core'; core.data.materials.append(chrome)
core.data.shade_smooth()

# ---------- head (knurled disc, Y engraved on top) ----------
C_H = 760; HR = 18.0; HH = 9.0; z0 = HEAD_Z0; z1 = HEAD_Z0 + HH
thh = np.linspace(0, 2 * np.pi, C_H, endpoint=False)
rows_r, rows_z, rows_mat = [], [], []
def add_row(r, z, mat):
    rows_r.append(np.broadcast_to(np.asarray(r, float), (C_H,)).copy())
    rows_z.append(np.broadcast_to(np.asarray(z, float), (C_H,)).copy()); rows_mat.append(mat)
for rr in np.linspace(1.0, 13.0, 6):
    add_row(rr, z0, 0)
add_row(HR - 0.7, z0, 0); add_row(HR - 0.35, z0 + 0.12, 0)
NPITCH = 140; kp = 2 * np.pi * HR / NPITCH
def tri(x): return 1 - 2 * np.abs((x % 1.0) - 0.5)
kz = np.linspace(z0 + 0.6, z1 - 0.6, 64)
for zz in kz:
    u = thh * HR
    sA = (u + (zz - z0)) / kp; sB = (u - (zz - z0)) / kp
    h = np.minimum(tri(sA), tri(sB))
    add_row(HR - 0.38 + 0.38 * h, zz, 0)
add_row(HR - 0.35, z1 - 0.12, 0); add_row(HR - 0.7, z1, 1)
head_mask = load_mask(os.path.join(HERE, 'head-mask.png'), 1.2)
NR = 320
for rr in np.linspace(HR - 0.9, 0.06, NR):
    xx = rr * np.cos(thh); yy = rr * np.sin(thh)
    mk = bilinear(head_mask, (xx + 20) * 40, (20 - yy) * 40)
    add_row(rr, z1 - 0.15 * mk, 1)
    rows_mat[-1] = mk
Rh = np.array(rows_r); Zh = np.array(rows_z)
head, nq = lathe('head', Rh, Zh, C_H, bottom_center=z0, top_center=z1, mats=[chrome, brushed, mirror])
# material per quad row
mat_idx = []
for r in range(len(rows_mat) - 1):
    a, b = rows_mat[r], rows_mat[r + 1]
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        aa = a if isinstance(a, np.ndarray) else np.zeros(C_H); bb = b if isinstance(b, np.ndarray) else np.zeros(C_H)
        avg = (aa + np.roll(aa, -1) + bb + np.roll(bb, -1)) / 4
        mat_idx.append(np.where(avg > 0.45, 2, 1))
    else:
        mat_idx.append(np.full(C_H, max(a, b) if (a == 1 or b == 1) else 0))
mat_idx = np.concatenate(mat_idx)
allm = np.concatenate([mat_idx, np.zeros(C_H), np.where(np.asarray(rows_mat[-1]) > 0.45, 2, 1)])[:len(head.data.polygons)]
head.data.polygons.foreach_set('material_index', allm.astype(np.int32))
# dispensing slot at the front of the knurl
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.75 * MM, depth=4.2 * MM,
                                    location=(0, -(HR - 0.25) * MM, (z0 + HH * 0.42) * MM), rotation=(0, math.pi / 2, 0))
slot = bpy.context.active_object; slot.name = 'slot'; slot.scale = (1, 1, 1)
bev = slot.modifiers.new('b', 'BEVEL'); bev.width = 0.6 * MM; bev.segments = 6
slot.data.materials.append(slotm)

# ---------- studio: tone-on-tone cyclorama ----------
def studio_setup():
    bgc = (tuple(map(float, os.environ['BG_LIN'].split(','))) + (1.0,)) if os.environ.get('BG_LIN') else srgb_to_lin(BG)
    bgm, _ = principled('backdrop', **{'Base Color': bgc, 'Roughness': 0.95, 'Specular IOR Level': 0.2})
    # L-shaped sweep along X: floor (y<0.12), fillet r=0.18, wall at y=0.30
    prof = []
    for y in np.linspace(-1.2, 0.12, 30): prof.append((y, 0.0))
    for a_ in np.linspace(0, np.pi / 2, 40)[1:]: prof.append((0.12 + 0.18 * np.sin(a_), 0.18 - 0.18 * np.cos(a_)))
    for z in np.linspace(0.18, 1.2, 30)[1:]: prof.append((0.30, z))
    xs_ = np.linspace(-1.2, 1.2, 3)
    V = [(x, y, z) for (y, z) in prof for x in xs_]
    F = []
    n = len(xs_)
    for i in range(len(prof) - 1):
        for k in range(n - 1):
            F.append((i * n + k, i * n + k + 1, (i + 1) * n + k + 1, (i + 1) * n + k))
    me = bpy.data.meshes.new('sweep'); me.from_pydata(V, [], F); me.update(); me.shade_smooth()
    ob = bpy.data.objects.new('sweep', me); bpy.context.collection.objects.link(ob); me.materials.append(bgm)
    world = bpy.data.worlds.new('w'); scene.world = world; world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = bgc
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.05
    import mathutils
    def ar(name, loc, size, size_y, energy, target=(0, 0, 0.045), cam_vis=False):
        ld = bpy.data.lights.new(name, 'AREA'); ld.shape = 'RECTANGLE'; ld.size = size; ld.size_y = size_y; ld.energy = energy
        o = bpy.data.objects.new(name, ld); bpy.context.collection.objects.link(o); o.location = loc
        o.rotation_euler = mathutils.Vector(np.array(target) - np.array(loc)).to_track_quat('-Z', 'Y').to_euler()
        o.visible_camera = cam_vis
        return o
    ar('key', (-0.55, -0.45, 0.55), 0.9, 0.9, 6)
    ar('fill', (0.6, -0.5, 0.25), 0.9, 0.9, 1.4)
    ar('top', (0.0, 0.05, 0.7), 0.6, 0.6, 1.8)
    mc = bpy.data.collections.new('metal_only')
    for o in (head, sleeve, core, slot): mc.objects.link(o)
    for nm, loc, a_, b_, e_ in [('refl_panel', (0.0, 0.30, 0.33), 0.40, 0.16, 2.0), ('refl_side_L', (-0.22, -0.05, 0.10), 0.05, 0.25, 0.3)]:
        lo = ar(nm, loc, a_, b_, e_, target=(0, 0, 0.085)); lo.light_linking.receiver_collection = mc

if BG == 'black':
    # ---------- floor ----------
    bpy.ops.mesh.primitive_plane_add(size=3, location=(0, 0, 0)); fl = bpy.context.active_object; fl.data.materials.append(floor_m)

    # ---------- world + lights ----------
    world = bpy.data.worlds.new('w'); scene.world = world; world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 0, 0, 1)
    def area(name, loc, size, size_y, energy, color=(1, 1, 1), target=(0, 0, 0.06)):
        ld = bpy.data.lights.new(name, 'AREA'); ld.shape = 'RECTANGLE'; ld.size = size; ld.size_y = size_y
        ld.energy = energy; ld.color = color
        ob = bpy.data.objects.new(name, ld); bpy.context.collection.objects.link(ob); ob.location = loc
        d = np.array(target) - np.array(loc); ob.rotation_euler = (0, 0, 0)
        import mathutils
        ob.rotation_euler = mathutils.Vector(d).to_track_quat('-Z', 'Y').to_euler()
        ob.visible_camera = False
        return ob
    cool = (0.82, 0.9, 1.0)
    area('strip_top', (0, -0.05, 0.42), 0.34, 0.025, 4)
    area('rim_L', (-0.13, 0.30, 0.07), 0.04, 0.36, 13.0, (0.55, 0.75, 1.0))
    area('rim_R', (0.13, 0.30, 0.07), 0.04, 0.36, 13.0, (0.55, 0.75, 1.0))
    area('key_soft', (-0.32, -0.34, 0.2), 0.45, 0.45, 0.09)
    area('fill_low', (0.3, -0.3, 0.05), 0.3, 0.3, 0.05, cool)
    area('chrome_card', (0.0, -0.25, 0.30), 0.30, 0.06, 0.6)
    tb = area('top_back', (0.0, 0.26, 0.30), 0.30, 0.05, 3.0, (0.7, 0.85, 1.0))
    egg_coll = bpy.data.collections.new('egg_only'); egg_coll.objects.link(egg)
    tb.light_linking.receiver_collection = egg_coll
    metal_coll = bpy.data.collections.new('metal_only')
    for o in (head, sleeve, core, slot):
        metal_coll.objects.link(o)
    for nm, loc, a_, b_, e_ in [('refl_panel', (0.0, 0.30, 0.33), 0.40, 0.16, float(os.environ.get('PANEL', '0.18'))),
                                ('refl_side_L', (-0.22, -0.05, 0.10), 0.05, 0.25, 0.35),
                                ('refl_side_R', (0.24, 0.02, 0.12), 0.05, 0.25, 0.25)]:
        lo = area(nm, loc, a_, b_, e_, target=(0, 0, 0.085))
        lo.light_linking.receiver_collection = metal_coll

    prod_coll = bpy.data.collections.new('product_only')
    for o in (egg, head, sleeve, core, slot):
        prod_coll.objects.link(o)
    for o in bpy.data.objects:
        if o.type == 'LIGHT' and o.light_linking.receiver_collection is None:
            o.light_linking.receiver_collection = prod_coll

else:
    studio_setup()

# ---------- camera ----------
import mathutils
cam_d = bpy.data.cameras.new('cam'); cam_d.lens = 100; cam_d.sensor_fit = 'VERTICAL'; cam_d.sensor_height = 36
cam = bpy.data.objects.new('cam', cam_d); bpy.context.collection.objects.link(cam); scene.camera = cam
if SHOT == 'hero':
    tgt = mathutils.Vector((0, 0, 0.048)); elev = math.radians(21); dist = 0.45; cam_d.dof.use_dof = False
elif SHOT == 'top':
    tgt = mathutils.Vector((0, 0, 0.075)); elev = math.radians(42); dist = 0.24
else:
    tgt = mathutils.Vector((0, 0, 0.056)); elev = math.radians(6); dist = 0.50
cam.location = tgt + mathutils.Vector((0, -dist * math.cos(elev), dist * math.sin(elev)))
cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()

# ---------- render ----------
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'; scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
try: scene.cycles.denoiser = 'OPENIMAGEDENOISE'
except Exception: pass
scene.cycles.max_bounces = 8; scene.cycles.glossy_bounces = 6
scene.render.resolution_x = RX; scene.render.resolution_y = RY; scene.render.resolution_percentage = 100
try:
    scene.view_settings.view_transform = 'Standard'; scene.view_settings.look = 'None'; scene.view_settings.exposure = EXPO
except Exception as e:
    print('cm', e)
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
if '--glb' in sys.argv:
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and o.name.startswith('Plane'):
            bpy.data.objects.remove(o)
    bpy.ops.export_scene.gltf(filepath=os.path.join(HERE, 'yojo_vessel.glb'), export_format='GLB', export_apply=True,
                              export_cameras=False, export_lights=False)
if '--save' in sys.argv:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'yojo_vessel.blend'))
print('done', OUT)

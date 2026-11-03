# ---------- the bag: two sheets sealed at the edge, the air pulled out (cloth with negative pressure) ----------
import bmesh
PW, PH, SEALW = float(os.environ.get('PW', '7.0')), 10.5, 0.5
SP = float(os.environ.get('SPACING', '0.11'))
NX, NY = int(round(PW / SP)) + 1, int(round(PH / SP)) + 1
xs = np.linspace(-PW / 2, PW / 2, NX); ys = np.linspace(-PH / 2, PH / 2, NY)
DT = float(os.environ.get('TENT', '0.95')); SEED = float(os.environ.get('SEED', '0.12')); FREE = float(os.environ.get('FREE', '1.1'))
# true size: the vial as made (vial.py enlarges the 3 mL vial for its studio shots; undo that here)
root.scale = (1, 1, 1)
if NO.split('+')[0] in ('03', '08'):
    RAD, L = 1.2, 4.55 + 1.86
    prof = [(0.0, 1.08), (0.14, 1.2), (4.55, 1.2), (4.67, 1.19), (4.81, 1.14), (4.95, 1.03), (5.05, 0.9), (5.13, 0.86), (5.37, 0.86), (5.41, 0.98), (5.48, 1.055), (6.03, 1.11), (6.41, 1.0)]
else:
    RAD, L = 0.8, 3.5
    prof = [(0.0, 0.72), (0.1, 0.8), (2.35, 0.8), (2.42, 0.79), (2.52, 0.72), (2.61, 0.6), (2.65, 0.52), (2.77, 0.52), (2.82, 0.65), (3.15, 0.68), (3.42, 0.665), (3.5, 0.55)]
pa, pr = np.array([p[0] for p in prof]), np.array([p[1] for p in prof])
lift = 0.03                                   # the vial sits on the bottom sheet
root.location = (VX, -L / 2, RAD + lift)
bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UV'); dl = bm.verts.layers.deform.verify()
def edge_d(x, y): return min(x + PW / 2, PW / 2 - x, y + PH / 2, PH / 2 - y)
TOP, BOT = {}, {}
_r = np.random.default_rng(int(os.environ.get('RSEED', '4')))
_g = _r.normal(size=(NY + 8, NX + 8))
import numpy as _np
_k = _np.outer(_np.hanning(7), _np.hanning(7)); _k /= _k.sum()
SN = _np.zeros_like(_g)
for _a in range(7):
    for _b in range(7): SN += _k[_a, _b] * _np.roll(_np.roll(_g, _a - 3, 0), _b - 3, 1)
SN = SN / SN.std()
for j, y in enumerate(ys):
    for i, x in enumerate(xs):
        e = edge_d(x, y); border = i in (0, NX - 1) or j in (0, NY - 1)
        # start the top sheet already draped (tent off the vial), as the bag looks once sealed; only the film near the vial is free
        a_ = min(max(y + L / 2, 0), L); r_ = float(np.interp(a_, pa, pr)) + 0.06
        dx_ = max(abs(x - VX) - r_, 0); dy_ = max(-(y + L / 2), (y + L / 2) - L, 0); d_ = (dx_ ** 2 + dy_ ** 2) ** 0.5
        if d_ == 0: zt = RAD + lift + (max(r_ ** 2 - (x - VX) ** 2, 0)) ** 0.5
        else: zt = (RAD + lift) * max(1 - d_ / DT, 0) ** 2.4
        if 0 < d_ < FREE: zt += SEED * (1.0 if d_ < 1.4 else 0.35) * float(SN[int((y + PH / 2) / SP) % SN.shape[0], int((x + PW / 2) / SP) % SN.shape[1]]) * min(d_ / 0.3, 1) * max(1 - d_ / FREE, 0)
        vt = bm.verts.new((x, y, 0.02 + zt)); TOP[i, j] = vt
        w_ = min(max((d_ - FREE) / 0.5, 0), 1)
        if e < SEALW + 0.05: w_ = 1.0
        vt[dl][0] = w_
        if border:
            BOT[i, j] = vt
        else:
            vb = bm.verts.new((x, y, 0.0)); BOT[i, j] = vb
            vb[dl][0] = 1.0   # the back sheet lies on the table and stays put
for j in range(NY - 1):
    for i in range(NX - 1):
        f = bm.faces.new((TOP[i, j], TOP[i + 1, j], TOP[i + 1, j + 1], TOP[i, j + 1])); f.material_index = 0
        g = bm.faces.new((BOT[i, j], BOT[i, j + 1], BOT[i + 1, j + 1], BOT[i + 1, j])); g.material_index = 1
        for ff in (f, g):
            for lp in ff.loops:
                co = lp.vert.co; lp[uvl].uv = (co.x / PW + 0.5, co.y / PH + 0.5)
me = bpy.data.meshes.new('film'); bm.to_mesh(me); bm.free()
for p in me.polygons: p.use_smooth = True
film = bpy.data.objects.new('film', me); sc.collection.objects.link(film)
vg = film.vertex_groups.new(name='seal')
# bmesh deform layer index 0 maps to the first vertex group
cl = film.modifiers.new('cloth', 'CLOTH'); cs = cl.settings; cc = cl.collision_settings
cs.quality = 12; cs.mass = 0.04; cs.air_damping = 2.0
cs.tension_stiffness = 60; cs.compression_stiffness = 60; cs.shear_stiffness = 30
cs.bending_stiffness = float(os.environ.get('BEND', '0.08'))
cs.vertex_group_mass = 'seal'; cs.pin_stiffness = 2.0
cs.effector_weights.gravity = 0.0
cs.use_pressure = True; cs.use_pressure_volume = True
cs.target_volume = float(os.environ.get('TVOL', '6.0')); cs.pressure_factor = float(os.environ.get('PFAC', '6.0'))
cs.shrink_min = float(os.environ.get('SHRINK', '0.02'))
cc.collision_quality = 4; cc.distance_min = 0.012; cc.use_self_collision = True; cc.self_distance_min = 0.008; cc.self_friction = 5
FR = int(os.environ.get('FRAMES', '70'))
cl.point_cache.frame_start = 1; cl.point_cache.frame_end = FR
for o in vial:
    if o.name.startswith(('glass', 'crimp', 'cap')):
        m_ = o.modifiers.new('col', 'COLLISION'); o.collision.thickness_outer = 0.015; o.collision.cloth_friction = 8
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, -0.012)); gnd = bpy.context.active_object; gnd.name = 'ground'
gnd.modifiers.new('col', 'COLLISION'); gnd.collision.thickness_outer = 0.01; gnd.hide_render = True
sc.frame_start = 1; sc.frame_end = FR
import time; t0 = time.time()
for f in range(1, FR + 1):
    sc.frame_set(f)
print('cloth', FR, 'frames', round(time.time() - t0), 's', flush=True)
dg = bpy.context.evaluated_depsgraph_get()
nm = bpy.data.meshes.new_from_object(film.evaluated_get(dg))
film.modifiers.clear(); film.data = nm
sub = film.modifiers.new('sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 2
for p in film.data.polygons: p.use_smooth = True

# YOJO GHK-Cu vessel: working-mechanism model (Blender 5.2, bpy module)
# Every part is a real solid. A static quarter section (x<0, y<0 removed) shows the inside.
# env: OUT, RX, RY, SAMPLES, CLIP (1/0), STATE (locked|open|pressed|anim), FRAMES, CAM_TH, EXPO, SKIN_LIN
import os, sys, math
import numpy as np
import bpy, bmesh, mathutils
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
E = os.environ.get
OUT = E('OUT', os.path.join(HERE, 'mech.png'))
RX, RY = int(E('RX', '640')), int(E('RY', '800'))
SAMPLES = int(E('SAMPLES', '24'))
CLIP = float(E('CLIP', '1'))
STATE = E('STATE', 'open')
CAM_TH = math.radians(float(E('CAM_TH', '-125')))
TEXT_TH = math.radians(float(E('TEXT_TH', '-62')))
SLOT_TH = math.radians(float(E('SLOT_TH', '-62')))
MM = 0.001

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------------- helpers ----------------
def srgb_to_lin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)

def load_mask(path, blur):
    im = Image.open(path).convert('L')
    if blur: im = im.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(im, dtype=np.float32) / 255.0

def bilinear(img, px, py):
    h, w = img.shape
    px = np.clip(px, 0, w - 1.001); py = np.clip(py, 0, h - 1.001)
    x0 = np.floor(px).astype(int); y0 = np.floor(py).astype(int); fx = px - x0; fy = py - y0
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy)
            + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)

def lathe(name, R, Z, C, bottom_center=None, top_center=None, closed=False, mats=None):
    rows = R.shape[0]
    th = np.linspace(0, 2 * np.pi, C, endpoint=False)
    verts = np.stack([R * np.cos(th)[None, :], R * np.sin(th)[None, :], Z], -1).reshape(-1, 3) * MM
    j = np.arange(C); jn = (j + 1) % C
    quads = [np.stack([r * C + j, r * C + jn, (r + 1) * C + jn, (r + 1) * C + j], -1) for r in range(rows - 1)]
    if closed:
        a = (rows - 1) * C
        quads.append(np.stack([a + j, a + jn, jn, j], -1))
    faces = np.concatenate(quads).tolist(); vl = verts.tolist()
    if bottom_center is not None:
        ci = len(vl); vl.append([0, 0, bottom_center * MM]); faces += [[ci, int(b), int(a)] for a, b in zip(j, jn)]
    if top_center is not None:
        ci = len(vl); vl.append([0, 0, top_center * MM]); a = (rows - 1) * C
        faces += [[a + int(x), a + int(y), ci] for x, y in zip(j, jn)]
    me = bpy.data.meshes.new(name); me.from_pydata(vl, [], faces); me.update(); me.shade_smooth()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    for m in (mats or []): me.materials.append(m)
    return ob

def resample(pts, ds):
    P = np.array(pts, float); seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)]); su = np.linspace(0, s[-1], max(2, int(s[-1] / ds) + 1))
    # keep the original corners
    su = np.unique(np.concatenate([su, s]))
    return np.stack([np.interp(su, s, P[:, 0]), np.interp(su, s, P[:, 1])], 1)

def solid(name, pts, C, mats, closed=False, ds=0.25, split=40):
    P = resample(pts, ds); bc = tc = None
    if not closed and P[0, 0] < 0.02: bc = P[0, 1]; P = P[1:]
    if not closed and P[-1, 0] < 0.02: tc = P[-1, 1]; P = P[:-1]
    R = np.repeat(P[:, 0:1], C, 1); Z = np.repeat(P[:, 1:2], C, 1)
    ob = lathe(name, R, Z, C, bc, tc, closed, mats)
    if split:
        m = ob.modifiers.new('es', 'EDGE_SPLIT'); m.split_angle = math.radians(split)
    return ob

def catmull(points, n):
    P = np.array(points, float); P = np.vstack([P[0] * 2 - P[1], P, P[-1] * 2 - P[-2]]); out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2]); return np.array(out)

# ---------------- materials (with static quarter-section clip) ----------------
def principled(name, clip=True, cap=None, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes['Principled BSDF']; out = nt.nodes['Material Output']
    for k, v in kw.items():
        if k in b.inputs: b.inputs[k].default_value = v
    if clip and CLIP > 0:
        geo = nt.nodes.new('ShaderNodeNewGeometry'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(geo.outputs['Position'], sep.inputs['Vector'])
        lx = nt.nodes.new('ShaderNodeMath'); lx.operation = 'LESS_THAN'; lx.inputs[1].default_value = 0.0
        ly = nt.nodes.new('ShaderNodeMath'); ly.operation = 'LESS_THAN'; ly.inputs[1].default_value = 0.0
        nt.links.new(sep.outputs['X'], lx.inputs[0]); nt.links.new(sep.outputs['Y'], ly.inputs[0])
        mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
        nt.links.new(lx.outputs[0], mul.inputs[0]); nt.links.new(ly.outputs[0], mul.inputs[1])
        capb = nt.nodes.new('ShaderNodeBsdfPrincipled')
        capc = cap or kw.get('Base Color', (0.8, 0.8, 0.8, 1))
        if kw.get('Metallic', 0) > 0.5: capc = (0.42, 0.44, 0.47, 1)      # cut steel reads as matte grey
        capb.inputs['Base Color'].default_value = capc; capb.inputs['Roughness'].default_value = 0.6
        # a little self-light so the section reads; the cut faces still pick up the real lights
        capb.inputs['Emission Color'].default_value = capc; capb.inputs['Emission Strength'].default_value = float(E('CAP_GLOW', '0.12'))
        mixc = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(geo.outputs['Backfacing'], mixc.inputs['Fac'])
        nt.links.new(b.outputs['BSDF'], mixc.inputs[1]); nt.links.new(capb.outputs['BSDF'], mixc.inputs[2])
        tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mixt = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(mul.outputs[0], mixt.inputs['Fac'])
        nt.links.new(mixc.outputs[0], mixt.inputs[1]); nt.links.new(tr.outputs['BSDF'], mixt.inputs[2])
        nt.links.new(mixt.outputs[0], out.inputs['Surface'])
    return m, b

SKY = (tuple(map(float, E('SKIN_LIN').split(','))) + (1.0,)) if E('SKIN_LIN') else srgb_to_lin('#62B0E4')
skin, skin_b = principled('skin', **{'Base Color': SKY, 'Roughness': 0.62, 'Sheen Weight': 0.55, 'Sheen Roughness': 0.35,
                          'Sheen Tint': (1, 1, 1, 1), 'Subsurface Weight': 0.06, 'Subsurface Scale': 0.002, 'Specular IOR Level': 0.35})
nt = skin.node_tree
nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 2500.0; nz.inputs['Detail'].default_value = 2.0
tcn = nt.nodes.new('ShaderNodeTexCoord'); nt.links.new(tcn.outputs['Object'], nz.inputs['Vector'])
bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.06; bump.inputs['Distance'].default_value = 0.00005
nt.links.new(nz.outputs['Fac'], bump.inputs['Height']); nt.links.new(bump.outputs['Normal'], skin_b.inputs['Normal'])
shell_m, _ = principled('shell_pp', **{'Base Color': (0.82, 0.83, 0.84, 1), 'Roughness': 0.45})
weight_m, _ = principled('steel_weight', **{'Base Color': (0.55, 0.56, 0.58, 1), 'Metallic': 1.0, 'Roughness': 0.3})
chrome_in, _ = principled('chrome_in', **{'Base Color': (0.93, 0.94, 0.95, 1), 'Metallic': 1.0, 'Roughness': 0.07})
cup_m, _ = principled('cup_pp', **{'Base Color': (0.95, 0.96, 0.97, 1), 'Roughness': 0.3, 'Transmission Weight': 0.85, 'IOR': 1.49})
cream_m, _ = principled('cream', **{'Base Color': srgb_to_lin('#9CCFF0'), 'Roughness': 0.28, 'Subsurface Weight': 0.4,
                        'Subsurface Scale': 0.003, 'Coat Weight': 0.3})
piston_m, _ = principled('piston_pe', **{'Base Color': (0.9, 0.9, 0.9, 1), 'Roughness': 0.5})
pump_m, _ = principled('pump_pp', **{'Base Color': (0.88, 0.9, 0.92, 1), 'Roughness': 0.35, 'Transmission Weight': 0.5})
spring_m, _ = principled('spring_pom', **{'Base Color': (0.93, 0.93, 0.9, 1), 'Roughness': 0.35})   # metal-free plastic spring: it sits in the cream path
# the head stays whole so the twist reads
chrome_h, _ = principled('chrome_head', clip=False, **{'Base Color': (0.93, 0.94, 0.95, 1), 'Metallic': 1.0, 'Roughness': 0.07})
brushed, br_b = principled('brushed', clip=False, **{'Base Color': (0.9, 0.91, 0.92, 1), 'Metallic': 1.0, 'Roughness': 0.14, 'Anisotropic': 0.75})
tg = brushed.node_tree.nodes.new('ShaderNodeTangent'); tg.direction_type = 'RADIAL'; tg.axis = 'Z'
brushed.node_tree.links.new(tg.outputs['Tangent'], br_b.inputs['Tangent'])
engrave, _ = principled('engrave', clip=False, **{'Base Color': (0.5, 0.52, 0.55, 1), 'Metallic': 1.0, 'Roughness': 0.5})
slot_m, _ = principled('slot', clip=False, **{'Base Color': (0.01, 0.01, 0.012, 1), 'Roughness': 0.35})
ribbon_m, _ = principled('cream_ribbon', clip=False, **{'Base Color': srgb_to_lin('#9CCFF0'), 'Roughness': 0.25,
                         'Subsurface Weight': 0.4, 'Subsurface Scale': 0.003, 'Coat Weight': 0.35})
floor_m, _ = principled('floor', clip=False, **{'Base Color': (0, 0, 0, 1), 'Roughness': 0.06, 'Specular IOR Level': 0.5})

# ---------------- skin (thick silicone, debossed) ----------------
prof = [(0.0, 0.3), (0.0, 10.0), (0.4, 14.0), (1.3, 16.8), (2.86, 18.9), (4.53, 21.3), (6.2, 23.3), (7.9, 25.1), (9.5, 26.6),
        (11.2, 27.9), (12.9, 29.1), (14.6, 29.9), (16.2, 30.8), (17.9, 31.4), (19.6, 32.1), (21.3, 32.6), (24.6, 33.5), (27.9, 34.0),
        (31.3, 34.0), (34.6, 34.0), (38.0, 33.7), (41.3, 33.2), (44.7, 32.3), (48.0, 31.5), (51.4, 30.6), (54.7, 29.6), (58.1, 28.4),
        (61.4, 26.9), (64.7, 25.4), (67.2, 24.0), (69.0, 22.4), (70.1, 20.2), (70.55, 17.6), (70.45, 15.9)]
P = catmull([(r, z) for z, r in prof], 40)
seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = np.concatenate([[0], np.cumsum(seg)])
su = np.arange(0, s[-1], 0.1); Pu = np.stack([np.interp(su, s, P[:, 0]), np.interp(su, s, P[:, 1])], 1)
k = np.exp(-0.5 * (np.arange(-40, 41) / 12.0) ** 2); k /= k.sum()
pad = np.pad(Pu, ((40, 40), (0, 0)), mode='edge')
P = np.stack([np.convolve(pad[:, i], k, mode='valid') for i in range(2)], 1); P[:3] = Pu[:3]; P[-3:] = Pu[-3:]
seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = np.concatenate([[0], np.cumsum(seg)])
tg_ = [0.0]
while tg_[-1] < s[-1]:
    zc = np.interp(tg_[-1], s, P[:, 1]); tg_.append(tg_[-1] + (1 / 8.0 if 14 < zc < 40 else 1 / 2.2))
tg_ = np.array(tg_[:-1] + [s[-1]])
pr = np.interp(tg_, s, P[:, 0]); pz = np.interp(tg_, s, P[:, 1])
dr = np.gradient(pr); dzz = np.gradient(pz); L = np.hypot(dr, dzz) + 1e-12; nr, nzn = dzz / L, -dr / L
C_EGG = int(E('C_EGG', '1400'))
th = np.linspace(0, 2 * np.pi, C_EGG, endpoint=False)
Ro = np.repeat(pr[:, None], C_EGG, 1); Zo = np.repeat(pz[:, None], C_EGG, 1)
emask = load_mask(os.path.join(HERE, 'egg-mask.png'), 1.4)
dth = (th[None, :] - TEXT_TH + np.pi) % (2 * np.pi) - np.pi
xs = dth * Ro; mk = np.where(np.abs(xs) < 59, bilinear(emask, (xs + 60) * 20, (92 - Zo) * 20), 0.0)
Ro = Ro - 0.5 * mk * nr[:, None]; Zo = Zo - 0.5 * mk * nzn[:, None]
WALL = 3.5
# inner surface: offset of the outer, below the shoulder, then the lip that wraps into the opening
inn = np.stack([pr - WALL * nr, pz - WALL * nzn], 1)
inn = inn[(pz < 61.5) & (inn[:, 0] > 0.3)]
lip = np.array([[15.65, 69.7], [15.65, 66.6], [18.8, 66.4], [21.0, 65.2]])
inner_path = np.vstack([lip, inn[::-1]])
inner_path = resample(inner_path, 0.4)
if inner_path[-1, 0] > 0.35: inner_path = np.vstack([inner_path, [[0.3, inner_path[-1, 1]]]])
Ri = np.repeat(inner_path[:, 0:1], C_EGG, 1); Zi = np.repeat(inner_path[:, 1:2], C_EGG, 1)
egg = lathe('skin', np.vstack([Ro, Ri]), np.vstack([Zo, Zi]), C_EGG, bottom_center=0.0, top_center=inner_path[-1, 1], mats=[skin])

# ---------------- inner shell (rigid PP) ----------------
so = np.stack([pr - (WALL + 0.06) * nr, pz - (WALL + 0.06) * nzn], 1); si = np.stack([pr - (WALL + 1.7) * nr, pz - (WALL + 1.7) * nzn], 1)
so = so[(pz < 60.5) & (so[:, 0] > 0.3)]; si = si[(pz < 58.5) & (si[:, 0] > 0.3)]
shell_path = np.vstack([[[0.0, so[0, 1]]], so, [[19.6, 64.6], [18.7, 66.3], [17.35, 66.3], [17.35, 61.0]], si[::-1], [[0.0, si[0, 1]]]])
shell = solid('shell', shell_path, 360, [shell_m], ds=0.5, split=0)

# ---------------- fixed collar (internal thread rides the sleeve) ----------------
collar = solid('collar', [(15.05, 60.5), (17.3, 60.5), (17.3, 66.3), (15.05, 66.3)], 360, [chrome_in], closed=True)

# ---------------- moving cartridge: threaded sleeve + pump + refill cup ----------------
HB0 = 70.55                      # head underside when locked (sits on the rigid stop)
S0, S1 = 52.0, HB0 + 1.0         # sleeve bottom/top when locked
cart = bpy.data.objects.new('cartridge', None); bpy.context.collection.objects.link(cart)
def link(ob, parent):
    ob.parent = parent; return ob
pitch, lead = 1.5, 9.0           # 3-start thread with a 9 mm lead: one full turn opens it
bm = bmesh.new()
for start in range(3):
    turns = (S1 - S0 - 1.0) / lead; spp = 140; steps = int(turns * spp)
    ang0 = start * 2 * math.pi / 3
    pts = [(13.3, -1.25), (15.0, -0.22), (15.0, 0.22), (13.3, 1.25)]
    vs = [bm.verts.new(((r * math.cos(ang0)) * MM, (r * math.sin(ang0)) * MM, (S0 + 0.8 + dz_) * MM)) for r, dz_ in pts]
    es = [bm.edges.new((vs[i], vs[i + 1])) for i in range(3)]
    bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), dvec=(0, 0, lead / spp * MM),
                   angle=2 * math.pi * turns, steps=steps, use_duplicate=False)
me = bpy.data.meshes.new('thread'); bm.to_mesh(me); bm.free(); me.shade_smooth(); me.materials.append(chrome_in)
thread = bpy.data.objects.new('thread', me); bpy.context.collection.objects.link(thread)
thread.modifiers.new('es', 'EDGE_SPLIT').split_angle = math.radians(35); link(thread, cart)
link(solid('sleeve_core', [(12.3, S0), (13.36, S0), (13.36, S1), (12.3, S1)], 360, [chrome_in], closed=True), cart)
P0, P1 = S1 - 12.5, S1 - 2.5
link(solid('pump_body', [(0, P0), (7.0, P0), (7.0, P1 - 1.0), (5.0, P1), (0, P1)], 240, [pump_m]), cart)
# spring inside the pump
bm = bmesh.new()
sv = bmesh.ops.create_circle(bm, cap_ends=False, radius=0.42 * MM, segments=12)['verts']
bmesh.ops.rotate(bm, verts=sv, cent=(0, 0, 0), matrix=mathutils.Matrix.Rotation(math.pi / 2, 3, 'X'))
bmesh.ops.translate(bm, verts=sv, vec=(4.0 * MM, 0, 0))
geom = sv + list({e for v in sv for e in v.link_edges})
bmesh.ops.spin(bm, geom=geom, cent=(0, 0, 0), axis=(0, 0, 1), dvec=(0, 0, 1.25 / 48 * MM), angle=2 * math.pi * 6, steps=288)
me = bpy.data.meshes.new('spring'); bm.to_mesh(me); bm.free(); me.shade_smooth(); me.materials.append(spring_m)
spring = bpy.data.objects.new('spring', me); bpy.context.collection.objects.link(spring); link(spring, cart)
spring.location = (0, 0, (P0 + 1.0) * MM)
# 30 ml refill cup: Ø37 x 37. Its top stays below the fixed collar even when the cartridge is up 9 mm.
C0, C1, CR, CW = 14.0, 51.0, 18.5, 0.8
link(solid('cup', [(0, C0), (CR, C0), (CR, C1 - 1.2), (13.4, C1), (13.4, S0 + 0.4), (12.6, S0 + 0.4), (12.6, C1 - 0.7),
                   (CR - CW, C1 - 1.6), (CR - CW, C0 + CW), (0, C0 + CW)], 240, [cup_m]), cart)
PIS0, PIS1 = C0 + CW, C0 + CW + 3.0
link(solid('piston', [(0, PIS0), (CR - CW - 0.05, PIS0), (CR - CW - 0.05, PIS1), (0, PIS1)], 240, [piston_m]), cart)
link(solid('cream', [(0, PIS1), (CR - CW - 0.05, PIS1), (CR - CW - 0.05, C1 - 1.7), (12.55, C1 - 0.8), (12.55, S0 + 0.3),
                     (3.0, S0 + 0.3), (3.0, P0), (0, P0)], 240, [cream_m], split=0), cart)
VOL = math.pi * (CR - CW) ** 2 * (C1 - 1.6 - PIS1) / 1000.0
print('cup fill volume ml', round(VOL, 1))
# steel slug shaped to the bottom of the shell (~60 g): keeps the centre of mass low so the egg rights itself
si_full = np.stack([pr - (WALL + 1.75) * nr, pz - (WALL + 1.75) * nzn], 1)
si_full = si_full[si_full[:, 0] > 0.3]
WTOP = 13.2
bowl = si_full[si_full[:, 1] < WTOP]
wpath = np.vstack([[[0.0, bowl[0, 1]]], bowl, [[bowl[-1, 0], WTOP]], [[0.0, WTOP]]])
weight = solid('weight', wpath, 240, [weight_m], ds=0.4, split=30)

# ---------------- head (knurled, Y engraved, bore underneath, side slot) ----------------
C_H = 760; HR = 18.0; HH = 9.0; BORE_R, BORE_D = 15.4, 5.5
z0 = HB0; z1 = HB0 + HH
thh = np.linspace(0, 2 * np.pi, C_H, endpoint=False)
rr_, zz_, mm_ = [], [], []
def row(r, z, m):
    rr_.append(np.broadcast_to(np.asarray(r, float), (C_H,)).copy()); zz_.append(np.broadcast_to(np.asarray(z, float), (C_H,)).copy()); mm_.append(m)
for r in np.linspace(1.0, BORE_R, 5): row(r, z0 + BORE_D, 0)          # bore ceiling
for z in np.linspace(z0 + BORE_D, z0, 4)[1:]: row(BORE_R, z, 0)        # bore wall
row(HR - 0.7, z0, 0); row(HR - 0.35, z0 + 0.12, 0)
NP = 140; kp = 2 * np.pi * HR / NP
def tri(x): return 1 - 2 * np.abs((x % 1.0) - 0.5)
for z in np.linspace(z0 + 0.6, z1 - 0.6, 64):
    u = thh * HR; h = np.minimum(tri((u + (z - z0)) / kp), tri((u - (z - z0)) / kp)); row(HR - 0.38 + 0.38 * h, z, 0)
row(HR - 0.35, z1 - 0.12, 0); row(HR - 0.7, z1, 1)
hmask = load_mask(os.path.join(HERE, 'head-mask.png'), 1.2)
for r in np.linspace(HR - 0.9, 0.06, 300):
    xx = r * np.cos(thh); yy = r * np.sin(thh)
    # Y reads upright from the front (-Y)
    mk2 = bilinear(hmask, (xx + 20) * 40, (20 - yy) * 40); row(r, z1 - 0.15 * mk2, mk2)
head = lathe('head', np.array(rr_), np.array(zz_), C_H, bottom_center=z0 + BORE_D, top_center=z1, mats=[chrome_h, brushed, engrave])
mi = []
for a, b in zip(mm_[:-1], mm_[1:]):
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        aa = a if isinstance(a, np.ndarray) else np.zeros(C_H); bb = b if isinstance(b, np.ndarray) else np.zeros(C_H)
        mi.append(np.where((aa + np.roll(aa, -1) + bb + np.roll(bb, -1)) / 4 > 0.45, 2, 1))
    else:
        mi.append(np.full(C_H, 1 if (a == 1 or b == 1) else 0))
mi = np.concatenate(mi)
allm = np.concatenate([mi, np.zeros(C_H), np.where(np.asarray(mm_[-1]) > 0.45, 2, 1)])[:len(head.data.polygons)]
head.data.polygons.foreach_set('material_index', allm.astype(np.int32))
# slot
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.75 * MM, depth=4.2 * MM,
    location=((HR - 0.25) * math.cos(SLOT_TH) * MM, (HR - 0.25) * math.sin(SLOT_TH) * MM, (z0 + HH * 0.42) * MM),
    rotation=(0, math.pi / 2, SLOT_TH + math.pi / 2))
slot = bpy.context.active_object; slot.name = 'slot'; slot.data.materials.append(slot_m)
bv = slot.modifiers.new('b', 'BEVEL'); bv.width = 0.6 * MM; bv.segments = 6
# stem from pump to head, moves with the head
stem = solid('stem', [(0, P1 - 0.5), (2.0, P1 - 0.5), (2.0, z0 + BORE_D), (0, z0 + BORE_D)], 64, [pump_m])
# pivot all head parts on the axis
headrig = bpy.data.objects.new('headrig', None); bpy.context.collection.objects.link(headrig)
for o in (head, slot, stem): o.parent = headrig
# cream ribbon out of the slot
cu = bpy.data.curves.new('ribbon', 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 1.35 * MM; cu.bevel_resolution = 6
cu.use_fill_caps = True; cu.resolution_u = 24
spl = cu.splines.new('BEZIER'); pts = [(18.4, 0.0), (23.5, -1.2), (28.0, -4.6), (30.0, -9.5)]
spl.bezier_points.add(len(pts) - 1)
zc = z0 + HH * 0.42
for bp, (r, dz_) in zip(spl.bezier_points, pts):
    bp.co = (r * math.cos(SLOT_TH) * MM, r * math.sin(SLOT_TH) * MM, (zc + dz_) * MM); bp.handle_left_type = bp.handle_right_type = 'AUTO'
ribbon = bpy.data.objects.new('ribbon', cu); bpy.context.collection.objects.link(ribbon); cu.materials.append(ribbon_m)
ribbon.parent = headrig
cu.bevel_factor_mapping_end = 'SPLINE'; cu.bevel_factor_end = 0.0

# ---------------- states / animation ----------------
OPEN_MM, PRESS_MM = 9.0, 4.0
def set_state(lift, turn_deg, press, cream, frame=None):
    cart.location = (0, 0, lift * MM); cart.rotation_euler = (0, 0, math.radians(turn_deg))
    headrig.location = (0, 0, (lift - press) * MM); headrig.rotation_euler = (0, 0, math.radians(turn_deg))
    spring.scale = (1, 1, 1 - 0.35 * press / PRESS_MM)
    cu.bevel_factor_end = cream
    if frame is not None:
        for o, p in ((cart, 'location'), (cart, 'rotation_euler'), (headrig, 'location'), (headrig, 'rotation_euler'), (spring, 'scale')):
            o.keyframe_insert(p, frame=frame)
        cu.keyframe_insert('bevel_factor_end', frame=frame)
# twisting up turns the head counter-clockwise seen from above; the slot ends where it started
if STATE == 'locked': set_state(0, 0, 0, 0)
elif STATE == 'open': set_state(OPEN_MM, 360, 0, 0)
elif STATE == 'pressed': set_state(OPEN_MM, 360, PRESS_MM, 0.85)
else:
    seg_ = E('SEG', 'open')   # 'open': locked -> twist up -> press -> cream ; 'lock': open -> twist down
    if seg_ == 'open':
        keys = [(1, 0, 0, 0, 0), (12, 0, 0, 0, 0), (52, OPEN_MM, 360, 0, 0), (60, OPEN_MM, 360, 0, 0),
                (68, OPEN_MM, 360, PRESS_MM, 0.0), (92, OPEN_MM, 360, PRESS_MM, 1.0), (98, OPEN_MM, 360, PRESS_MM, 1.0)]
    else:
        keys = [(1, OPEN_MM, 360, 0, 0), (8, OPEN_MM, 360, 0, 0), (44, 0, 0, 0, 0), (56, 0, 0, 0, 0)]
    for f, l, t, p, c in keys: set_state(l, t, p, c, frame=f)
    scene.frame_start, scene.frame_end = 1, keys[-1][0]
    if E('FRAME_START'): scene.frame_start = int(E('FRAME_START'))
    if E('FRAME_END'): scene.frame_end = int(E('FRAME_END'))

# ---------------- floor, lights, camera ----------------
bpy.ops.mesh.primitive_plane_add(size=3); fl = bpy.context.active_object; fl.data.materials.append(floor_m)
world = bpy.data.worlds.new('w'); scene.world = world; world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 0, 0, 1)
parts = [o for o in bpy.data.objects if o.type in ('MESH', 'CURVE') and o is not fl]
prod = bpy.data.collections.new('product'); [prod.objects.link(o) for o in parts]
metal = bpy.data.collections.new('metal'); [metal.objects.link(o) for o in (head, slot, thread, collar)]
eggc = bpy.data.collections.new('eggonly'); eggc.objects.link(egg)
def area(name, loc, a, b, e, col=(1, 1, 1), tgt=(0, 0, 0.06), recv=None):
    ld = bpy.data.lights.new(name, 'AREA'); ld.shape = 'RECTANGLE'; ld.size = a; ld.size_y = b; ld.energy = e; ld.color = col
    ob = bpy.data.objects.new(name, ld); bpy.context.collection.objects.link(ob); ob.location = loc
    ob.rotation_euler = mathutils.Vector(np.array(tgt) - np.array(loc)).to_track_quat('-Z', 'Y').to_euler()
    ob.visible_camera = False; ob.light_linking.receiver_collection = recv or prod
    return ob
cool = (0.82, 0.9, 1.0)
# rig rotated so it faces the camera
rot = mathutils.Matrix.Rotation(CAM_TH + math.pi / 2, 3, 'Z')
def R_(v): return tuple(rot @ mathutils.Vector(v))
area('strip_top', R_((0, -0.05, 0.42)), 0.34, 0.025, 4)
area('rim_L', R_((-0.13, 0.30, 0.07)), 0.04, 0.36, 13.0, (0.55, 0.75, 1.0))
area('rim_R', R_((0.13, 0.30, 0.07)), 0.04, 0.36, 13.0, (0.55, 0.75, 1.0))
area('key_soft', R_((-0.32, -0.34, 0.2)), 0.45, 0.45, 0.09)
area('fill_low', R_((0.3, -0.3, 0.05)), 0.3, 0.3, 0.05, cool)
area('chrome_card', R_((0.0, -0.25, 0.30)), 0.30, 0.06, 0.6)
area('top_back', R_((0.0, 0.26, 0.30)), 0.30, 0.05, 3.0, (0.7, 0.85, 1.0), recv=eggc)
if CLIP > 0: area('inside_fill', R_((-0.05, -0.30, 0.10)), 0.25, 0.25, 0.35, tgt=(0, 0, 0.045))   # lights the section
for nm, loc, a, b, e in [('refl_panel', (0.0, 0.30, 0.33), 0.40, 0.16, float(E('PANEL', '0.6'))), ('refl_side_L', (-0.22, -0.05, 0.10), 0.05, 0.25, 0.35)]:
    area(nm, R_(loc), a, b, e, tgt=(0, 0, 0.085), recv=metal)
cam_d = bpy.data.cameras.new('cam'); cam_d.lens = 100; cam_d.sensor_fit = 'VERTICAL'; cam_d.sensor_height = 36
cam = bpy.data.objects.new('cam', cam_d); bpy.context.collection.objects.link(cam); scene.camera = cam
tgt = mathutils.Vector((0, 0, float(E('CAM_Z', '0.054')))); elev = math.radians(float(E('CAM_EL', '15'))); dist = float(E('CAM_D', '0.46'))
def place_cam(th):
    cam.location = tgt + mathutils.Vector((dist * math.cos(elev) * math.cos(th), dist * math.cos(elev) * math.sin(th), dist * math.sin(elev)))
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
place_cam(CAM_TH)
if STATE == 'anim':
    drift = math.radians(float(E('DRIFT', '7')))
    for f, th_ in ((scene.frame_start, CAM_TH - drift / 2), (scene.frame_end, CAM_TH + drift / 2)):
        place_cam(th_); cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)

# ---------------- render ----------------
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
try: scene.cycles.denoiser = 'OPENIMAGEDENOISE'
except Exception: pass
scene.cycles.max_bounces = int(E('BOUNCES', '7')); scene.cycles.glossy_bounces = 4; scene.cycles.transparent_max_bounces = int(E('TBOUNCES', '14'))
scene.cycles.diffuse_bounces = 3
scene.cycles.use_adaptive_sampling = True; scene.cycles.adaptive_threshold = float(E('ADAPT', '0.03'))
scene.cycles.transmission_bounces = 8
scene.render.use_persistent_data = True
scene.render.resolution_x = RX; scene.render.resolution_y = RY; scene.render.resolution_percentage = 100
scene.view_settings.view_transform = 'Standard'; scene.view_settings.look = 'None'; scene.view_settings.exposure = float(E('EXPO', '-1.063'))
if STATE == 'anim':
    scene.render.image_settings.file_format = 'PNG'; scene.render.filepath = OUT  # frame sequence prefix
    scene.render.fps = 24
    scene.render.use_overwrite = False   # resume: keep frames already on disk
    bpy.ops.render.render(animation=True)
else:
    scene.render.image_settings.file_format = 'PNG'; scene.render.filepath = OUT
    bpy.ops.render.render(write_still=True)
if E('SAVE'): bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'yojo_mechanism.blend'))
print('done', OUT)

# ZUMA vacuum pouch: one vial vacuum-sealed in a 75 x 105 mm pouch, shot from above (Cycles via bpy).
#   bpyenv/bin/python vac.py NO ART MASK FILM OUT [W H SAMPLES]
# ART  = 1500 x 2100 RGBA, the ink (20 px/mm), top of the art = cap end.
# MASK = 1500 x 2100 RGB: R = base layer (1 = frosted / foil / white underlay, 0 = clear film), G = seal ribs, B = pouch shape.
# FILM = clear | frosted | silver | oxfoil | white
import sys, os, math, json
import numpy as np
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
NO, ART, MASK, FILM, OUT, GROUND = args[:6]
W, H, SAMPLES = (int(args[6]), int(args[7]), int(args[8])) if len(args) > 8 else (900, 1200, 96)

# reuse the site's vial (geometry, glass, label, crimp, cap, cake) from zuma/render/vial.py
VP = '/home/user/zuma/render/vial.py'
src = open(VP).read()
src = src[:src.index("if SHOT == 'lineup'")].replace("'..', 'site3', 'src', 'data'", "'..', 'source', 'src', 'data'")
sys.argv = ['vial.py', 'float', NO, OUT]
g = {'__file__': VP, '__name__': 'vialmod'}
exec(compile(src, VP, 'exec'), g)
bpy, lin, mat, make_vial, sc, TEX = g['bpy'], g['lin'], g['mat'], g['make_vial'], g['sc'], g['TEX']
from mathutils import Vector

# ---------- the vial, lying on its back, cap toward +Y ----------
VX = -0.5                     # vial axis sits 5 mm left of the pouch centre (room for the tall wordmark)
root, vial = make_vial(NO)
L = 4.55 + 1.47
root.rotation_euler = (math.radians(-90), 0, math.radians(0)); root.location = (VX, -L / 2, 1.2)
# turn the label so its front panel faces up (it faces -Y before the tip; after -90 about X that is +Z)

# ---------- the film: a height field over the pouch ----------
PW, PH = 7.5, 10.5            # pouch, cm
NX, NY = 375, 525
xs = np.linspace(-PW / 2, PW / 2, NX); ys = np.linspace(-PH / 2, PH / 2, NY)
X, Y = np.meshgrid(xs, ys)
# vial radius along its axis (axial coordinate a from the base, 0 .. L)
prof = [(0.0, 1.08), (0.14, 1.2), (4.55, 1.2), (4.67, 1.19), (4.81, 1.14), (4.95, 1.03), (5.05, 0.9), (5.13, 0.86), (5.37, 0.86), (5.41, 0.98), (5.48, 1.055), (5.97, 1.055), (6.02, 0.95)]
pa, pr = np.array([p[0] for p in prof]), np.array([p[1] for p in prof])
A = Y + L / 2
Ac = np.clip(A, 0, L)
Rr = np.interp(Ac, pa, pr) + 0.03
dx = np.maximum(np.abs(X - VX) - Rr, 0); dy = np.maximum(np.maximum(-A, A - L), 0)
dist = np.sqrt(dx ** 2 + dy ** 2)
inside = (dist == 0)
top = 1.2 + np.sqrt(np.maximum(Rr ** 2 - (X - VX) ** 2, 0))
D = 1.25
t = np.clip(dist / D, 0, 1)
tent = 1.2 * (1 - t) ** 2.6
Z = np.where(inside, top, tent)

# value noise
rng = np.random.default_rng(7)
def vnoise(u, v, seed):
    r = np.random.default_rng(seed); G = r.random((64, 64))
    u0 = np.floor(u).astype(int); v0 = np.floor(v).astype(int); fu = u - u0; fv = v - v0
    fu = fu * fu * (3 - 2 * fu); fv = fv * fv * (3 - 2 * fv)
    g = lambda i, j: G[(v0 + j) % 64, (u0 + i) % 64]
    return (g(0, 0) * (1 - fu) + g(1, 0) * fu) * (1 - fv) + (g(0, 1) * (1 - fu) + g(1, 1) * fu) * fv
# creases run outward from the vial: fast across the edge direction, slow along the distance
along = np.where(dy > 0, X - VX, Y)             # coordinate that runs along the vial's outline
cre = sum((vnoise(along * f * 1.25 + 9 * k, dist * f * 0.55 + 3 * k, 11 + k) - 0.5) / f for k, f in enumerate((1, 2.2)))
ridge = 1 - np.abs(np.sin(cre * 3.2))           # sharp-ish creases
band = np.exp(-((t - 0.38) / 0.33) ** 2) * (~inside)
Z += band * (0.16 * ridge ** 2 + 0.06 * cre)
# loose air in the flat of the bag, small puckers
puck = vnoise(X * 2.2 + 40, Y * 2.2, 5) + 0.5 * vnoise(X * 6 + 7, Y * 6, 6)
flat = np.clip((t - 0.7) / 0.3, 0, 1) * (~inside)
Z += flat * 0.035 * puck
# the seal: 6 mm round the edge, pressed flat
e = np.minimum(np.minimum(X + PW / 2, PW / 2 - X), np.minimum(Y + PH / 2, PH / 2 - Y))
seal = np.clip((e - 0.6) / 0.35, 0, 1)
Z = Z * seal + 0.01
# a slight film thickness above the vial so it never cuts in
Z = np.maximum(Z, 0.012)

import bmesh
bm = bmesh.new()
verts = [[bm.verts.new((X[j, i], Y[j, i], Z[j, i])) for i in range(NX)] for j in range(NY)]
uvl = bm.loops.layers.uv.new('UV')
for j in range(NY - 1):
    for i in range(NX - 1):
        f = bm.faces.new((verts[j][i], verts[j][i + 1], verts[j + 1][i + 1], verts[j + 1][i]))
        for lp in f.loops:
            co = lp.vert.co; lp[uvl].uv = (co.x / PW + 0.5, co.y / PH + 0.5)
me = bpy.data.meshes.new('film'); bm.to_mesh(me); bm.free()
for p in me.polygons: p.use_smooth = True
film = bpy.data.objects.new('film', me); sc.collection.objects.link(film)

# ---------- film material ----------
m = bpy.data.materials.new('film'); m.use_nodes = True; nt = m.node_tree; N = nt.nodes; Lk = nt.links
for n in list(N):
    if n.type != 'OUTPUT_MATERIAL': N.remove(n)
out = N['Material Output']
def node(t, **kw):
    n = N.new(t)
    for k, v in kw.items(): n.inputs[k].default_value = v
    return n
def tex(path, cs='sRGB'):
    n = N.new('ShaderNodeTexImage'); n.image = bpy.data.images.load(path); n.image.colorspace_settings.name = cs; n.interpolation = 'Cubic'; n.extension = 'CLIP'; return n
ink = tex(ART); msk = tex(MASK, 'Non-Color'); sep = N.new('ShaderNodeSeparateColor'); Lk.new(msk.outputs['Color'], sep.inputs['Color'])
# clear film: transparent with a fresnel gloss
fr = node('ShaderNodeLayerWeight', Blend=0.42)
clear = N.new('ShaderNodeMixShader'); Lk.new(fr.outputs['Fresnel'], clear.inputs['Fac'])
Lk.new(node('ShaderNodeBsdfTransparent', Color=(1, 1, 1, 1)).outputs[0], clear.inputs[1]); Lk.new(node('ShaderNodeBsdfGlossy', Roughness=0.015).outputs[0], clear.inputs[2])
clear2 = N.new('ShaderNodeMixShader'); clear2.inputs['Fac'].default_value = 0.04   # a touch of haze
Lk.new(clear.outputs[0], clear2.inputs[1]); Lk.new(node('ShaderNodeBsdfDiffuse', Color=(1, 1, 1, 1)).outputs[0], clear2.inputs[2])
# base layer
if FILM == 'frosted':
    ref = node('ShaderNodeBsdfRefraction', IOR=1.0, Roughness=0.42, Color=(0.96, 0.97, 0.98, 1))
    b1 = N.new('ShaderNodeMixShader'); b1.inputs['Fac'].default_value = 0.22
    Lk.new(ref.outputs[0], b1.inputs[1]); Lk.new(node('ShaderNodeBsdfDiffuse', Color=(0.93, 0.94, 0.95, 1)).outputs[0], b1.inputs[2])
    base = N.new('ShaderNodeMixShader'); Lk.new(fr.outputs['Fresnel'], base.inputs['Fac']); Lk.new(b1.outputs[0], base.inputs[1]); Lk.new(node('ShaderNodeBsdfGlossy', Roughness=0.22).outputs[0], base.inputs[2])
elif FILM in ('silver', 'oxfoil'):
    col = (0.80, 0.82, 0.85, 1) if FILM == 'silver' else lin('#8E2A3C')
    base = node('ShaderNodeBsdfPrincipled', **{'Base Color': col, 'Metallic': 1.0, 'Roughness': 0.16 if FILM == 'silver' else 0.22})
else:  # white underlay (opaque print)
    base = node('ShaderNodeBsdfPrincipled', **{'Base Color': (0.92, 0.92, 0.9, 1), 'Roughness': 0.3})
layer = N.new('ShaderNodeMixShader'); Lk.new(sep.outputs['Red'], layer.inputs['Fac']); Lk.new(clear2.outputs[0], layer.inputs[1]); Lk.new(base.outputs[0], layer.inputs[2])
# ink: printed on the film (reverse printed, so it sits under a glossy skin)
inkb = node('ShaderNodeBsdfPrincipled', Roughness=0.4, **{'Coat Weight': 0.3, 'Coat Roughness': 0.14})
gam = node('ShaderNodeGamma', Gamma=1.7); Lk.new(ink.outputs['Color'], gam.inputs['Color']); Lk.new(gam.outputs['Color'], inkb.inputs['Base Color'])
inked = N.new('ShaderNodeMixShader'); Lk.new(ink.outputs['Alpha'], inked.inputs['Fac']); Lk.new(layer.outputs[0], inked.inputs[1]); Lk.new(inkb.outputs[0], inked.inputs[2])
# pouch shape (rounded corners): outside it the film is gone
shape = N.new('ShaderNodeMixShader'); Lk.new(sep.outputs['Blue'], shape.inputs['Fac'])
Lk.new(node('ShaderNodeBsdfTransparent').outputs[0], shape.inputs[1]); Lk.new(inked.outputs[0], shape.inputs[2])
Lk.new(shape.outputs[0], out.inputs['Surface'])
# seal ribs and fine film grain as bump
uvn = N.new('ShaderNodeUVMap'); wave = N.new('ShaderNodeTexWave'); wave.wave_type = 'BANDS'; wave.bands_direction = 'DIAGONAL'
wave.inputs['Scale'].default_value = 90; wave.inputs['Distortion'].default_value = 0.0; Lk.new(uvn.outputs['UV'], wave.inputs['Vector'])
rib = N.new('ShaderNodeMath'); rib.operation = 'MULTIPLY'; Lk.new(wave.outputs['Fac'], rib.inputs[0]); Lk.new(sep.outputs['Green'], rib.inputs[1])
grain = node('ShaderNodeTexNoise', Scale=60.0, Detail=6.0)
gsum = N.new('ShaderNodeMath'); gsum.operation = 'MULTIPLY_ADD'; Lk.new(grain.outputs['Fac'], gsum.inputs[0]); gsum.inputs[1].default_value = 0.015; Lk.new(rib.outputs[0], gsum.inputs[2])
bump = node('ShaderNodeBump', Strength=0.5, Distance=0.02); Lk.new(gsum.outputs[0], bump.inputs['Height'])
for s in (inkb, base) if FILM != 'clear' else (inkb,):
    if 'Normal' in s.inputs: Lk.new(bump.outputs['Normal'], s.inputs['Normal'])
gl = [n for n in N if n.type == 'BSDF_GLOSSY']
for n in gl: Lk.new(bump.outputs['Normal'], n.inputs['Normal'])
film.data.materials.append(m)

# ---------- set: a matte sweep, soft box, strip, studio HDRI ----------
world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True; wn = world.node_tree
env = wn.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(os.path.join(TEX, 'studio.hdr'))
bg = wn.nodes['Background']; bg.inputs['Strength'].default_value = 0.55; wn.links.new(env.outputs['Color'], bg.inputs['Color'])
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, -0.002)); gnd = bpy.context.active_object
gm, gb = mat('ground', **{'Base Color': lin(GROUND), 'Roughness': 0.85}); gnd.data.materials.append(gm)
def area(name, size, loc, power, sy=None):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = power; ld.shape = 'RECTANGLE'; ld.size = size; ld.size_y = sy or size
    o = bpy.data.objects.new(name, ld); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
area('key', 30, (-22, 14, 34), 26000)
area('strip', 5, (18, -4, 20), 5000, 40)
area('top', 50, (0, 0, 60), 7000)
area('streak', 2, (-6, -16, 30), 4000, 30)
area('streak2', 1.5, (12, 10, 26), 2500, 24)

# ---------- camera: straight down ----------
cam = bpy.data.cameras.new('cam'); co = bpy.data.objects.new('cam', cam); sc.collection.objects.link(co); sc.camera = co
cam.sensor_width = 36; cam.lens = 92; co.location = (0, 0, 46); co.rotation_euler = (0, 0, 0)
r = sc.render; r.engine = 'CYCLES'; r.resolution_x, r.resolution_y = W, H; r.resolution_percentage = 100
cam.sensor_fit = 'VERTICAL'; cam.sensor_height = 36 * 0.75
sc.cycles.device = 'CPU'; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 16; sc.cycles.transmission_bounces = 16; sc.cycles.glossy_bounces = 8; sc.cycles.transparent_max_bounces = 32
sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
sc.view_settings.view_transform = 'AgX'
try: sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception: pass
r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGB'; r.filepath = OUT
bpy.ops.render.render(write_still=True)
print('rendered', OUT)

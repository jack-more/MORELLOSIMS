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
VX = float(os.environ.get('VX', '-0.5'))   # vial axis offset from the pouch centre, cm
root, vial = make_vial(NO)
L = 4.55 + 1.47
root.rotation_euler = (math.radians(-90), 0, math.radians(0)); root.location = (VX, -L / 2, 1.2)
# turn the label so its front panel faces up (it faces -Y before the tip; after -90 about X that is +Z)

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
VY = float(os.environ.get('VY', '0'))   # vial moved toward the bottom of the bag, cm
root.location = (VX, -L / 2 - VY, RAD + lift)
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
        a_ = min(max(y + L / 2 + VY, 0), L); r_ = float(np.interp(a_, pa, pr)) + 0.06
        dx_ = max(abs(x - VX) - r_, 0); dy_ = max(-(y + L / 2 + VY), (y + L / 2 + VY) - L, 0); d_ = (dx_ ** 2 + dy_ ** 2) ** 0.5
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
inkb = node('ShaderNodeBsdfPrincipled', Roughness=0.5, **{'Coat Weight': float(os.environ.get('COAT', '0.3')), 'Coat Roughness': 0.2})
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
ART, MASK, FILM = os.path.join(os.path.dirname(ART), 'blank-art.png'), os.path.join(os.path.dirname(MASK), 'blank-mask.png'), 'clear'
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
inkb = node('ShaderNodeBsdfPrincipled', Roughness=0.5, **{'Coat Weight': float(os.environ.get('COAT', '0.3')), 'Coat Roughness': 0.2})
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
# the back sheet is never seen from above; where the sheets touch it would show through the print, so it renders as nothing
_bm = film.data.materials[1]; _bm.use_nodes = True
for _n in list(_bm.node_tree.nodes):
    if _n.type != 'OUTPUT_MATERIAL': _bm.node_tree.nodes.remove(_n)
_tr = _bm.node_tree.nodes.new('ShaderNodeBsdfTransparent'); _bm.node_tree.links.new(_tr.outputs[0], _bm.node_tree.nodes['Material Output'].inputs['Surface'])
# ---------- set: a matte sweep, soft box, strip, studio HDRI ----------
world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True; wn = world.node_tree
env = wn.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(os.path.join(TEX, 'studio.hdr'))
bg = wn.nodes['Background']; bg.inputs['Strength'].default_value = 0.55; wn.links.new(env.outputs['Color'], bg.inputs['Color'])
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, -0.25)); gnd = bpy.context.active_object
gm, gb = mat('ground', **{'Base Color': lin(GROUND), 'Roughness': 0.85}); gnd.data.materials.append(gm)
def area(name, size, loc, power, sy=None):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = power; ld.shape = 'RECTANGLE'; ld.size = size; ld.size_y = sy or size
    o = bpy.data.objects.new(name, ld); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
area('key', 30, (-22, 14, 34), 26000)
area('strip', 5, (18, -4, 20), 5000, 40)
area('top', 50, (0, 0, 60), 7000)
area('streak', 1.2, (-6, -16, 30), 3000, 34)
area('streak2', 0.8, (12, 10, 26), 1800, 30)
for _n in ('key', 'top', 'strip'):
    bpy.data.objects[_n].visible_glossy = False

# ---------- camera: straight down ----------
cam = bpy.data.cameras.new('cam'); co = bpy.data.objects.new('cam', cam); sc.collection.objects.link(co); sc.camera = co
cam.sensor_width = 36; cam.lens = 92; co.location = (0, -float(os.environ.get('CAMY', '13')), 44); co.rotation_euler = (Vector((0, 0.2, 0)) - co.location).to_track_quat('-Z', 'Y').to_euler()
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

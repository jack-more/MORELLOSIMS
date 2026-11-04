# Six-egg carton tin: brushed aluminium tray + open lid with the wordmark pressed in, six YOJO eggs from the production model.
import os, sys, math, json
import numpy as np
import bpy, mathutils
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__)); E = os.environ.get
OUT = E('OUT', os.path.join(HERE, 'carton.png')); RX, RY = int(E('RX', '800')), int(E('RY', '1000')); SAMPLES = int(E('SAMPLES', '32'))
MM = 0.001
bpy.ops.wm.read_factory_settings(use_empty=True); scene = bpy.context.scene

def s2l(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)
def mat(name, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    for k, v in kw.items():
        if k in b.inputs: b.inputs[k].default_value = v
    return m, b
def skinmat(name, lin):
    m, b = mat(name, **{'Base Color': lin, 'Roughness': 0.62, 'Sheen Weight': 0.55, 'Sheen Roughness': 0.35, 'Sheen Tint': (1, 1, 1, 1),
                       'Subsurface Weight': 0.06, 'Subsurface Scale': 0.002, 'Specular IOR Level': 0.35})
    nt = m.node_tree; nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 2500.0
    tc = nt.nodes.new('ShaderNodeTexCoord'); nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.06; bp.inputs['Distance'].default_value = 0.00005
    nt.links.new(nz.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m
lin = lambda n: tuple(map(float, json.load(open(os.path.join(HERE, f'cm_{n}.json')))['SKIN_LIN'].split(','))) + (1.0,)
SK = {'sky': lin('sky'), 'rose': lin('rose'), 'sage': lin('sage'), 'cloud': lin('cloud'), 'cobalt': s2l('#1A5FD6')}
chrome, _ = mat('chrome', **{'Base Color': (0.93, 0.94, 0.95, 1), 'Metallic': 1.0, 'Roughness': 0.07})
brushed, bb = mat('brushed', **{'Base Color': (0.9, 0.91, 0.92, 1), 'Metallic': 1.0, 'Roughness': 0.16, 'Anisotropic': 0.75})
tg = brushed.node_tree.nodes.new('ShaderNodeTangent'); tg.direction_type = 'RADIAL'; tg.axis = 'Z'; brushed.node_tree.links.new(tg.outputs['Tangent'], bb.inputs['Tangent'])
engrave, _ = mat('engrave', **{'Base Color': (0.5, 0.52, 0.55, 1), 'Metallic': 1.0, 'Roughness': 0.5})
alu, ab = mat('alu', **{'Base Color': (0.86, 0.87, 0.88, 1), 'Metallic': 1.0, 'Roughness': 0.28, 'Anisotropic': 0.6})
tga = alu.node_tree.nodes.new('ShaderNodeTangent'); tga.direction_type = 'UV_MAP' if False else 'RADIAL'; tga.axis = 'X'
alu.node_tree.links.new(tga.outputs['Tangent'], ab.inputs['Tangent'])
blackm, _ = mat('slot', **{'Base Color': (0.01, 0.01, 0.01, 1), 'Roughness': 0.4})

# ---------- tray and lid as height fields over a rounded rectangle ----------
TW, TD, TH, RAD = 252.0, 170.0, 30.0, 16.0
PITCH, CUP_R, CUP_D = 80.0, 30.0, 20.0
cups = [((i - 1) * PITCH, (j - 0.5) * PITCH) for j in range(2) for i in range(3)]
def rrect_sdf(x, y, w, d, r):
    qx = np.abs(x) - (w / 2 - r); qy = np.abs(y) - (d / 2 - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
def heightfield(name, w, d, top, wall_soft, cupfn=None, mask=None, maskdepth=0.0, N=(520, 360)):
    xs = np.linspace(-w / 2 - 6, w / 2 + 6, N[0]); ys = np.linspace(-d / 2 - 6, d / 2 + 6, N[1]); X, Y = np.meshgrid(xs, ys)
    sd = rrect_sdf(X, Y, w, d, RAD)
    z = top * np.clip(-sd / wall_soft, 0, 1) ** 0.35          # rounded shoulder down to the table
    z = np.where(sd > 0, 0.0, z)
    if cupfn is not None: z = z - cupfn(X, Y)
    if mask is not None:
        h, wd = mask.shape; px = (X + w / 2) / w * (wd - 1); py = (d / 2 - Y) / d * (h - 1)
        inside = (px >= 0) & (px <= wd - 1) & (py >= 0) & (py <= h - 1)
        m = np.zeros_like(X); m[inside] = mask[py[inside].astype(int), px[inside].astype(int)]
        z = z - maskdepth * m
    V = np.stack([X, Y, z], -1).reshape(-1, 3) * MM; nx, ny = N
    idx = np.arange(nx * ny).reshape(ny, nx)
    F = np.stack([idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]], -1).reshape(-1, 4)
    keep = (sd.reshape(-1) <= 0.8)[F].all(1); F = F[keep]
    me = bpy.data.meshes.new(name); me.from_pydata(V.tolist(), [], F.tolist()); me.update(); me.shade_smooth()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    so = ob.modifiers.new('thick', 'SOLIDIFY'); so.thickness = 1.0 * MM; so.offset = -1
    return ob
def cupfn(X, Y):
    out = np.zeros_like(X)
    for cx, cy in cups:
        r = np.hypot(X - cx, Y - cy); t = np.clip(r / CUP_R, 0, 1)
        out = np.maximum(out, CUP_D * (1 - t ** 2) ** 0.8)
    return out
tray = heightfield('tray', TW, TD, TH, 7.0, cupfn); tray.data.materials.append(alu)
lm = np.asarray(Image.open(os.path.join(HERE, 'lid-mask.png')).convert('L').filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255
lid = heightfield('lid', TW, TD, 16.0, 6.0, None, lm, 1.6); lid.data.materials.append(alu)
# lid hinged at the back edge, open past vertical, standing behind the tray
lid.rotation_euler = (math.radians(180 - 72), 0, 0); lid.location = (0, (TD / 2 + 2) * MM, 0)
lid.rotation_mode = 'XYZ'
# rotate about its own back edge: move its origin to the hinge line
bpy.context.view_layer.update()
lid.location = (0, (TD / 2 + 1) * MM + math.cos(math.radians(72)) * (TD / 2) * MM, math.sin(math.radians(72)) * (TD / 2) * MM)

# ---------- six eggs ----------
order = ['sky', 'rose', 'cobalt', 'sage', 'cloud', 'sky']
spin = [8, -14, 20, -6, 12, -18]                 # each egg turned a little differently, like a real carton
def assign(o, skinm):
    if o.type != 'MESH': return
    n = o.name.split('.')[0]
    o.data.materials.clear()
    if n.startswith('skin'): o.data.materials.append(skinm)
    elif n.startswith('head'): [o.data.materials.append(m) for m in (chrome, brushed, engrave)]
    elif n.startswith('thread') or n.startswith('sleeve'): o.data.materials.append(chrome)
    else: o.data.materials.append(blackm)
SEAT = TH - CUP_D + 7.5          # the egg settles into the cup
for k, (cx, cy) in enumerate(cups):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(HERE, 'mk', 'egg_hi.glb'))
    new_objs = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new(f'egg_{k}', None); bpy.context.collection.objects.link(root)
    for o in new_objs:
        if o.parent is None: o.parent = root
    root.location = (cx * MM, cy * MM, SEAT * MM); root.rotation_euler = (0, 0, math.radians(spin[k]))
    sm = skinmat(f'skin_{k}', SK[order[k]])
    for o in new_objs: assign(o, sm)

# ---------- studio: tone-on-tone sky sweep, soft daylight ----------
BG = s2l(E('BG', '#BFE3FA'))
bgm, _ = mat('backdrop', **{'Base Color': BG, 'Roughness': 0.95, 'Specular IOR Level': 0.2})
bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 0, 0)); fl = bpy.context.active_object; fl.data.materials.append(bgm)
world = bpy.data.worlds.new('w'); scene.world = world; world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = BG; world.node_tree.nodes['Background'].inputs['Strength'].default_value = float(E('WORLD', '0.6'))
def area(name, loc, a, b, e, tgt=(0, 0, 0.02)):
    ld = bpy.data.lights.new(name, 'AREA'); ld.shape = 'RECTANGLE'; ld.size = a; ld.size_y = b; ld.energy = e
    ob = bpy.data.objects.new(name, ld); bpy.context.collection.objects.link(ob); ob.location = loc
    ob.rotation_euler = mathutils.Vector(np.array(tgt) - np.array(loc)).to_track_quat('-Z', 'Y').to_euler(); ob.visible_camera = False
area('key', (-0.6, -0.5, 0.9), 1.2, 1.2, float(E('KEY', '120')))
area('fill', (0.7, -0.4, 0.5), 1.0, 1.0, float(E('FILL', '25')))
area('top', (0.0, 0.1, 1.1), 0.8, 0.8, float(E('TOP', '40')))
cam_d = bpy.data.cameras.new('cam'); cam_d.lens = float(E('LENS', '70')); cam_d.sensor_fit = 'VERTICAL'; cam_d.sensor_height = 24
cam = bpy.data.objects.new('cam', cam_d); bpy.context.collection.objects.link(cam); scene.camera = cam
tgt = mathutils.Vector((0, 0.01, 0.045)); el = math.radians(float(E('EL', '42'))); th = math.radians(float(E('TH', '-104'))); d = float(E('D', '0.75'))
cam.location = tgt + mathutils.Vector((d * math.cos(el) * math.cos(th), d * math.cos(el) * math.sin(th), d * math.sin(el)))
cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = SAMPLES; scene.cycles.use_denoising = True
scene.cycles.use_adaptive_sampling = True
scene.render.resolution_x = RX; scene.render.resolution_y = RY
scene.view_settings.view_transform = 'Standard'; scene.view_settings.look = 'None'; scene.view_settings.exposure = float(E('EXPO', '-0.8'))
scene.render.filepath = OUT; bpy.ops.render.render(write_still=True); print('done', OUT)

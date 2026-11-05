# Grove pilot, beat 4: the chrome nail spins down into a blank pod; a blue burst; YOJO presses into the skin.
import os, math, json
import numpy as np
import bpy, mathutils
HERE = os.path.dirname(os.path.abspath(__file__)); E = os.environ.get; G = lambda k, d: float(E(k, d))
OUT = E('OUT', os.path.join(HERE, 'grove', 'nail_')); RX, RY = int(E('RX', '1280')), int(E('RY', '720')); SAMPLES = int(E('SAMPLES', '24'))
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
SKY = tuple(map(float, json.load(open(os.path.join(HERE, 'cm_sky.json')))['SKIN_LIN'].split(','))) + (1.0,)
skin, _ = mat('skin', **{'Base Color': SKY, 'Roughness': 0.62, 'Sheen Weight': 0.55, 'Sheen Roughness': 0.35, 'Sheen Tint': (1, 1, 1, 1),
                        'Subsurface Weight': 0.06, 'Subsurface Scale': 0.002, 'Specular IOR Level': 0.35})
def carved(name):
    m, b = mat(name, **{'Base Color': (0.96, 0.92, 0.86, 1), 'Metallic': 1.0, 'Roughness': 0.1})
    t = m.node_tree; at = t.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'carve'
    cr = t.nodes.new('ShaderNodeMapRange'); t.links.new(at.outputs['Fac'], cr.inputs['Value']); cr.inputs['From Min'].default_value = 0.25; cr.inputs['From Max'].default_value = 0.6
    mc = t.nodes.new('ShaderNodeMix'); mc.data_type = 'RGBA'; t.links.new(cr.outputs['Result'], mc.inputs['Factor'])
    mc.inputs[6].default_value = (0.96, 0.92, 0.86, 1); mc.inputs[7].default_value = (0.018, 0.018, 0.02, 1); t.links.new(mc.outputs[2], b.inputs['Base Color'])
    mr = t.nodes.new('ShaderNodeMapRange'); t.links.new(cr.outputs['Result'], mr.inputs['Value']); mr.inputs['To Min'].default_value = 0.1; mr.inputs['To Max'].default_value = 0.62
    t.links.new(mr.outputs['Result'], b.inputs['Roughness'])
    return m
head_m = carved('head'); black, _ = mat('slot', **{'Base Color': (0.01, 0.01, 0.01, 1), 'Roughness': 0.4})
def load(fn, names):
    with bpy.data.libraries.load(os.path.join(HERE, 'mk', fn)) as (src, dst):
        want = [n for n in src.objects if n in names]; dst.objects = list(want)
    out = {}
    for n, o in zip(want, dst.objects):
        bpy.context.collection.objects.link(o); out[n] = o
    return out
branded = load('egg_c.blend', ('skin',))
nailp = load('egg_open.blend', ('head', 'slot', 'thread', 'sleeve_core'))
branded.update(nailp)
blank = load('pod_blank.blend', ('skin',))
for o in (branded['skin'], blank['skin']):
    o.data.materials.clear(); o.data.materials.append(skin)
branded['head'].data.materials.clear(); [branded['head'].data.materials.append(head_m) for _ in range(3)]
branded['slot'].data.materials.clear(); branded['slot'].data.materials.append(black)
threadm, _ = mat('thread', **{'Base Color': (0.80, 0.78, 0.75, 1), 'Metallic': 1.0, 'Roughness': 0.32})
for n_ in ('thread', 'sleeve_core'): branded[n_].data.materials.clear(); branded[n_].data.materials.append(threadm)
# the nail: head + slot move together on an empty at the axis
nail = bpy.data.objects.new('nail', None); bpy.context.collection.objects.link(nail)
for o in (branded['head'], branded['slot'], branded['thread'], branded['sleeve_core']): o.parent = nail
F0, FC, F1 = 1, 34, 84            # start, contact, end
def key(f, z, turns):
    nail.location = (0, 0, z * MM); nail.rotation_euler = (0, 0, -2 * math.pi * turns); nail.keyframe_insert('location', frame=f); nail.keyframe_insert('rotation_euler', frame=f)
key(F0, G('Z0', '95'), 3.0); key(FC - 10, 6, 0.6); key(FC, -9, 0.0); key(F1, -9, 0.0)
for fc in nail.animation_data.action.fcurves if hasattr(nail.animation_data.action, 'fcurves') else []:
    for kp in fc.keyframe_points: kp.interpolation = 'BEZIER'
# blank -> branded swap under the flash
SW = FC + 3
for o, vis in ((blank['skin'], (False, True)), (branded['skin'], (True, False))):
    for f, h in ((SW - 1, vis[0]), (SW, vis[1])):
        o.hide_render = h; o.keyframe_insert('hide_render', frame=f)
# blue burst: a point light in the neck plus an emissive ring that expands and fades
burst = bpy.data.lights.new('burst', 'POINT'); burst.color = (0.35, 0.65, 1.0); burst.shadow_soft_size = 0.01
bo = bpy.data.objects.new('burst', burst); bpy.context.collection.objects.link(bo); bo.location = (0, -0.012, 0.092)
for f, e in ((FC - 1, 0), (FC, G('BURST', '3')), (FC + 4, G('BURST', '3') * 0.5), (FC + 16, 0)): burst.energy = e; burst.keyframe_insert('energy', frame=f)
bpy.ops.mesh.primitive_torus_add(major_radius=0.02, minor_radius=0.0012, location=(0, 0, 0.0785)); ring = bpy.context.active_object
rm = bpy.data.materials.new('ring'); rm.use_nodes = True; rn = rm.node_tree; [rn.nodes.remove(n) for n in list(rn.nodes) if n.type != 'OUTPUT_MATERIAL']
em = rn.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (0.12, 0.45, 1.0, 1)
tr = rn.nodes.new('ShaderNodeBsdfTransparent'); mx = rn.nodes.new('ShaderNodeMixShader')
rn.links.new(tr.outputs[0], mx.inputs[1]); rn.links.new(em.outputs[0], mx.inputs[2]); rn.links.new(mx.outputs[0], [n for n in rn.nodes if n.type == 'OUTPUT_MATERIAL'][0].inputs['Surface'])
ring.data.materials.append(rm)
for f, s, fac, st in ((FC - 1, 0.8, 0.0, 0), (FC, 1.0, 1.0, G('RING', '8')), (FC + 14, 4.5, 0.0, 0)):
    ring.scale = (s, s, 1); mx.inputs['Fac'].default_value = fac; em.inputs['Strength'].default_value = st
    ring.keyframe_insert('scale', frame=f); mx.inputs['Fac'].keyframe_insert('default_value', frame=f); em.inputs['Strength'].keyframe_insert('default_value', frame=f)
# golden-hour sky world, warm sun, cool fill, rim
world = bpy.data.worlds.new('w'); scene.world = world; world.use_nodes = True; wn = world.node_tree.nodes; wl = world.node_tree.links
tc = wn.new('ShaderNodeTexCoord'); sp = wn.new('ShaderNodeSeparateXYZ'); wl.new(tc.outputs['Window'], sp.inputs['Vector'])
rp = wn.new('ShaderNodeValToRGB'); wl.new(sp.outputs['Y'], rp.inputs['Fac'])
rp.color_ramp.elements[0].color = s2l('#FFD9A8'); rp.color_ramp.elements[1].color = s2l('#5FA8E8'); rp.color_ramp.elements[1].position = 0.85
lp = wn.new('ShaderNodeLightPath'); bc = wn.new('ShaderNodeBackground'); wl.new(rp.outputs['Color'], bc.inputs['Color'])
bl = wn.new('ShaderNodeBackground'); bl.inputs['Color'].default_value = s2l('#9CC9F0'); bl.inputs['Strength'].default_value = 0.35
ms = wn.new('ShaderNodeMixShader'); wl.new(lp.outputs['Is Camera Ray'], ms.inputs['Fac']); wl.new(bl.outputs[0], ms.inputs[1]); wl.new(bc.outputs[0], ms.inputs[2])
wl.new(ms.outputs[0], wn['World Output'].inputs['Surface'])
sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 3.0; sun.color = (1.0, 0.82, 0.62); sun.angle = math.radians(3)
so = bpy.data.objects.new('sun', sun); bpy.context.collection.objects.link(so); so.rotation_euler = (math.radians(62), 0, math.radians(-35))
def area(n, loc, s, e, col, tgt=(0, 0, 0.06)):
    ld = bpy.data.lights.new(n, 'AREA'); ld.size = s; ld.energy = e; ld.color = col
    ob = bpy.data.objects.new(n, ld); bpy.context.collection.objects.link(ob); ob.location = loc; ob.visible_camera = False
    ob.rotation_euler = mathutils.Vector(np.array(tgt) - np.array(loc)).to_track_quat('-Z', 'Y').to_euler()
area('fill', (-0.3, -0.35, 0.15), 0.6, 1.2, (0.7, 0.85, 1.0)); area('rim', (0.18, 0.3, 0.2), 0.08, 6.0, (1.0, 0.85, 0.7))
area('top', (0, -0.05, 0.4), 0.3, 1.5, (1, 1, 1), tgt=(0, 0, 0.09))
# low hero angle, slow push in
cd = bpy.data.cameras.new('cam'); cd.lens = G('LENS', '60'); cd.sensor_fit = 'HORIZONTAL'; cd.sensor_width = 36
cam = bpy.data.objects.new('cam', cd); bpy.context.collection.objects.link(cam); scene.camera = cam
for f, d, tz in ((F0, G('D0', '0.62'), 0.100), (F1, G('D1', '0.40'), 0.058)):
    th = math.radians(-100); el = math.radians(6); tg = mathutils.Vector((0, 0, tz))
    cam.location = tg + mathutils.Vector((d * math.cos(el) * math.cos(th), d * math.cos(el) * math.sin(th), d * math.sin(el)))
    cam.rotation_euler = (tg - cam.location).to_track_quat('-Z', 'Y').to_euler(); cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
scene.frame_start, scene.frame_end = int(E('FS', str(F0))), int(E('FE', str(F1))); scene.render.fps = 24
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = SAMPLES; scene.cycles.use_denoising = True
scene.cycles.use_adaptive_sampling = True; scene.render.resolution_x = RX; scene.render.resolution_y = RY
scene.view_settings.view_transform = 'Standard'; scene.view_settings.exposure = G('EXPO', '0')
scene.render.film_transparent = False; scene.render.image_settings.file_format = 'PNG'; scene.render.filepath = OUT
scene.render.use_overwrite = False
if E('STILL'):
    scene.frame_set(int(E('STILL'))); scene.render.filepath = OUT; bpy.ops.render.render(write_still=True)
else:
    bpy.ops.render.render(animation=True)
print('done')

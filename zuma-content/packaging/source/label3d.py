# Label options on the real 3 mL vial (16 mm x 35 mm, 13 mm crimp), rendered physically (Blender Cycles via bpy).
#   bpyenv/bin/python cyc/label3d.py OPTION OUT W H SAMPLES
#   OPTION: A frosted film, Oxblood print, area band | B area-colour field label | C Snow paper label, area band
# The label is 52 x 20 mm, a full wrap on the straight body. Three vials on stucco, low sun through palm fronds.
import bpy, math, os, sys
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__)); TEX = os.path.join(HERE, 'tex'); LB = os.path.join(HERE, 'lab3')
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
LARGS = list(args); OPT, OUT = LARGS[0], LARGS[1]
NOS = os.environ.get('ZNOS', '05,01,09').split(',')
src = open(os.path.join(HERE, 'vial.py')).read()
sys.argv = ['vial.py', 'front', NOS[0], OUT]
exec(compile(src[:src.index("if SHOT == 'lineup':")], 'vial.py', 'exec'))
W, H, SAMPLES = int(LARGS[2]), int(LARGS[3]), int(LARGS[4])

R = 0.8                                   # 16 mm body
def vial3(no):
    area = AREA_OF[no]; parts = []
    # real 3 mL proportions: straight body to 23.5 mm, shoulder, short neck, rolled lip; crimp skirt and a tall flip-off cap make 35 mm
    outer = [(0.0, 0.02), (0.62, 0.0), (0.76, 0.03), (0.8, 0.14), (R, 2.35), (0.785, 2.45), (0.72, 2.54), (0.6, 2.6), (0.54, 2.66),
             (0.54, 2.74), (0.6, 2.77), (0.65, 2.82), (0.65, 2.95), (0.5, 2.97)]
    inner = [(0.43, 2.97), (0.47, 2.93), (0.47, 2.64), (0.53, 2.585), (0.645, 2.515), (0.715, 2.43), (0.73, 2.34), (0.73, 0.2), (0.6, 0.12), (0.0, 0.14)]   # an even 0.7 mm wall through the shoulder, no thick lens of glass
    glass = lathe('glass', outer + inner, seg=160)
    tint = {'metabolic': '#9DB9F2', 'dermal': '#F4AE97', 'tissue': '#8ED3AE', 'endocrine': '#EBC27C', 'neuro': '#BCA6EE', 'supplies': '#C9D2DC'}
    gcol = lin(tint[area]) if os.environ.get('ZTINT') else (1, 1, 1, 1)   # ZTINT=1: glass tinted in the area colour
    gm, gb = mat('glass', **{'Base Color': gcol, 'Roughness': 0.0, 'IOR': 1.51, 'Transmission Weight': 1.0}); gb.inputs['Specular IOR Level'].default_value = 0.5
    gnt = gm.node_tree; out = gnt.nodes['Material Output']; lp = gnt.nodes.new('ShaderNodeLightPath'); mx = gnt.nodes.new('ShaderNodeMixShader'); tr = gnt.nodes.new('ShaderNodeBsdfTransparent')
    orr = gnt.nodes.new('ShaderNodeMath'); orr.operation = 'MAXIMUM'; gnt.links.new(lp.outputs['Is Shadow Ray'], orr.inputs[0]); gnt.links.new(lp.outputs['Is Diffuse Ray'], orr.inputs[1])
    gnt.links.new(orr.outputs['Value'], mx.inputs['Fac']); gnt.links.new(gb.outputs['BSDF'], mx.inputs[1]); gnt.links.new(tr.outputs['BSDF'], mx.inputs[2]); gnt.links.new(mx.outputs['Shader'], out.inputs['Surface'])
    if os.environ.get('ZTINT') == 'vol':
        # coloured glass: white surface, the colour absorbed inside the wall, so thin faces read light and the edges run deep
        gb.inputs['Base Color'].default_value = (1, 1, 1, 1)
        ab = gnt.nodes.new('ShaderNodeVolumeAbsorption'); ac = lin(TONES[area][1]); am = max(ac[:3]); ab.inputs['Color'].default_value = tuple((ac[i] / am) ** 0.5 for i in range(3)) + (1,); ab.inputs['Density'].default_value = float(os.environ.get('ZDENS', '6'))
        gnt.links.new(ab.outputs['Volume'], out.inputs['Volume'])
    glass.data.materials.append(gm); parts.append(glass)
    # grey rubber stopper: the plug sits down in the neck and shows through the glass under the crimp
    stp = lathe('stopper', [(0.0, 2.55), (0.4, 2.55), (0.44, 2.58), (0.445, 2.97), (0.6, 2.98), (0.6, 3.03), (0.0, 3.03)], seg=96)   # the plug shows as a thin grey ring through the neck, under the crimp
    sm, sb = mat('rubber', **{'Base Color': lin('#8E9196'), 'Roughness': 0.6}); stp.data.materials.append(sm); parts.append(stp)
    # aluminium crimp: a tall satin skirt rolled under the lip
    crimp = lathe('crimp', [(0.0, 3.06), (0.45, 3.06), (0.66, 3.05), (0.675, 3.02), (0.675, 2.74), (0.665, 2.71), (0.6, 2.7), (0.57, 2.73)], seg=128)
    cm, cb = mat('alu', **{'Base Color': lin('#CDD1D5'), 'Metallic': 1.0, 'Roughness': 0.3, 'Anisotropic': 0.5}); crimp.data.materials.append(cm); parts.append(crimp)
    # flip-off cap: moulded plastic sitting proud on the crimp, slightly wider, soft rounded top edge
    cap = lathe('cap', [(0.0, 3.06), (0.69, 3.06), (0.705, 3.09), (0.71, 3.3), (0.705, 3.44), (0.68, 3.49), (0.62, 3.5), (0.0, 3.5)], seg=128)
    pm, pb = mat('cap', **{'Base Color': lin({'ox': '#6E1C2A', 'snow': '#EEEAE3'}.get(os.environ.get('ZCAP'), TONES[area][2 if os.environ.get('ZCAP') == 'deep' else 1])), 'Roughness': 0.38, 'Coat Weight': 0.3, 'Coat Roughness': 0.2}); cap.data.materials.append(pm); parts.append(cap)
    cake = lathe('cake', [(0.0, 0.15), (0.71, 0.15), (0.72, 0.2), (0.72, 0.62), (0.69, 0.66), (0.4, 0.64), (0.0, 0.62)], seg=96)
    km, kb = mat('cake', **{'Base Color': lin('#F2EFE8'), 'Roughness': 0.95}); cake.data.materials.append(km); parts.append(cake)
    # the label: 20 mm tall on the straight body, 3 mm above the base, full wrap
    LR, LZ0, LH = R + 0.006, 0.26, 2.0
    lab = lathe('label', [(LR, LZ0), (LR, LZ0 + LH)], seg=256)
    me = lab.data; uv = me.uv_layers.new(name='UV')
    for poly in me.polygons:
        for li in poly.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co; a = math.atan2(v.y, v.x)
            uv.data[li].uv = (((a + math.pi / 2) / (2 * math.pi) + 0.5) % 1.0, (v.z - LZ0) / LH)
    for poly in me.polygons:
        us = [uv.data[li].uv[0] for li in poly.loop_indices]
        if max(us) - min(us) > 0.5:
            for li in poly.loop_indices:
                if uv.data[li].uv[0] < 0.5: uv.data[li].uv = (uv.data[li].uv[0] + 1, uv.data[li].uv[1])
    lm = bpy.data.materials.new('label'); lm.use_nodes = True; nt = lm.node_tree; nt.nodes.clear()
    o = nt.nodes.new('ShaderNodeOutputMaterial'); img = nt.nodes.new('ShaderNodeTexImage'); img.interpolation = 'Cubic'; img.extension = 'CLIP'
    img.image = bpy.data.images.load(os.path.join(TEX, 'label-%s.png' % no) if OPT == 'OG' else os.path.join(LB, 'l%s-%s.png' % (OPT, no)))   # OG: the original tricolour label art
    ink = nt.nodes.new('ShaderNodeBsdfPrincipled'); ink.inputs['Roughness'].default_value = 0.45
    nt.links.new(img.outputs['Color'], ink.inputs['Base Color'])
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 900; bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.04
    nt.links.new(nz.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], ink.inputs['Normal'])
    if OPT in ('T', 'S') or OPT.startswith('P'):
        # printed straight on the glass: ink where the art has ink, clear everywhere else
        clear = nt.nodes.new('ShaderNodeBsdfTransparent'); m2 = nt.nodes.new('ShaderNodeMixShader'); nt.links.new(img.outputs['Alpha'], m2.inputs['Fac'])
        nt.links.new(clear.outputs['BSDF'], m2.inputs[1]); nt.links.new(ink.outputs['BSDF'], m2.inputs[2]); nt.links.new(m2.outputs['Shader'], o.inputs['Surface'])
    elif OPT == 'A':
        # frosted film: a rough translucent sheet, with the print laid on it where the art has ink
        frost = nt.nodes.new('ShaderNodeBsdfPrincipled'); frost.inputs['Base Color'].default_value = (0.95, 0.95, 0.95, 1)
        frost.inputs['Transmission Weight'].default_value = 1.0; frost.inputs['Roughness'].default_value = 0.42; frost.inputs['IOR'].default_value = 1.45
        frost.inputs['Base Color'].default_value = (1, 1, 1, 1); frost.inputs['Roughness'].default_value = 0.5
        haze = nt.nodes.new('ShaderNodeBsdfDiffuse'); haze.inputs['Color'].default_value = (0.93, 0.92, 0.9, 1)
        hm = nt.nodes.new('ShaderNodeMixShader'); hm.inputs['Fac'].default_value = 0.3
        nt.links.new(frost.outputs['BSDF'], hm.inputs[1]); nt.links.new(haze.outputs['BSDF'], hm.inputs[2])
        m2 = nt.nodes.new('ShaderNodeMixShader'); nt.links.new(img.outputs['Alpha'], m2.inputs['Fac'])
        nt.links.new(hm.outputs['Shader'], m2.inputs[1]); nt.links.new(ink.outputs['BSDF'], m2.inputs[2]); nt.links.new(m2.outputs['Shader'], o.inputs['Surface'])
    else:
        ink.inputs['Coat Weight'].default_value = 0.3 if OPT in ('B', 'OG', 'D') else 0.0
        nt.links.new(ink.outputs['BSDF'], o.inputs['Surface'])
    lab.data.materials.append(lm); parts.append(lab)
    root = bpy.data.objects.new('vial-' + no, None); sc.collection.objects.link(root)
    for p_ in parts: p_.parent = root
    return root

def stucco(name, hexc):
    m, b = mat(name, **{'Base Color': lin(hexc), 'Roughness': 0.92}); nt = m.node_tree
    n1 = nt.nodes.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = 0.5; n1.inputs['Detail'].default_value = 5
    n2 = nt.nodes.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 16; n2.inputs['Detail'].default_value = 8
    mx = nt.nodes.new('ShaderNodeMath'); mx.operation = 'MULTIPLY_ADD'; mx.inputs[1].default_value = 0.35
    nt.links.new(n2.outputs['Fac'], mx.inputs[0]); nt.links.new(n1.outputs['Fac'], mx.inputs[2])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.18
    nt.links.new(mx.outputs['Value'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal']); return m
def slab(name, size, loc, m):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.active_object; o.name = name
    o.scale = size; bpy.ops.object.transform_apply(scale=True); o.data.materials.append(m); return o
slab('floor', (120, 80, 1), (0, 20, -0.5), stucco('floor', '#E7DAC6'))
slab('wall', (120, 1, 80), (0, 5, 30), stucco('wall', '#EFE4D2'))
for no, x, y, rot in zip(NOS, (-2.0, 0.0, 2.0), (0.4, -0.3, 0.5), [float(x) for x in os.environ.get('ZROT', '-3,0,3').split(',')]):
    v = vial3(no); v.location = (x, y, 0); v.rotation_euler = (0, 0, math.radians(rot))

world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True; wn = world.node_tree
env = wn.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(os.path.join(TEX, 'studio.hdr'))
bg = wn.nodes['Background']; bg.inputs['Strength'].default_value = 0.35; wn.links.new(env.outputs['Color'], bg.inputs['Color'])
def area(name, size, loc, power, look=(0, 0, 1.6), sx=None):
    l = bpy.data.lights.new(name, 'AREA'); l.shape = 'RECTANGLE'; l.size = size; l.size_y = sx or size; l.energy = power
    o = bpy.data.objects.new(name, l); sc.collection.objects.link(o); o.location = loc
    d = Vector(look) - Vector(loc); o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); return o
area('fill', 40, (16, -60, 24), 5200)
area('front', 8, (-3, -16, 5), 240)
area('kiss', 2.5, (-11, -4, 9), 380, sx=11)
area('rim', 3, (9, 5, 8), 300, look=(0, 0, 2.0), sx=9)
sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 6.0; sun.angle = math.radians(0.8); sun.color = (1.0, 0.87, 0.70)
so = bpy.data.objects.new('sun', sun); sc.collection.objects.link(so); so.rotation_euler = (math.radians(55), 0, math.radians(-38))
bpy.ops.mesh.primitive_plane_add(size=30, location=(-22, -12, 30)); g = bpy.context.active_object
g.rotation_euler = so.rotation_euler; g.rotation_euler.rotate_axis('Z', math.radians(20))
fm, fb = mat('fronds', **{'Base Color': (0, 0, 0, 1), 'Roughness': 1.0}); fnt = fm.node_tree
fi = fnt.nodes.new('ShaderNodeTexImage'); fi.image = bpy.data.images.load(os.path.join(TEX, 'fronds.png')); fnt.links.new(fi.outputs['Alpha'], fb.inputs['Alpha'])
g.data.materials.append(fm); g.visible_camera = False; g.visible_glossy = False; g.visible_transmission = False; g.visible_diffuse = False

cam = bpy.data.cameras.new('cam'); co = bpy.data.objects.new('cam', cam); sc.collection.objects.link(co); sc.camera = co
cam.sensor_width = 36; cam.lens = 90; co.location = (0, -18, 2.6); look = Vector((0, 0.2, 1.6))
d = look - co.location; co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
cam.dof.use_dof = True; cam.dof.focus_distance = d.length; cam.dof.aperture_fstop = 7.1

r = sc.render; r.engine = 'CYCLES'; r.resolution_x, r.resolution_y = W, H; r.resolution_percentage = 100
sc.cycles.device = 'CPU'; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 16; sc.cycles.transmission_bounces = 16; sc.cycles.glossy_bounces = 8; sc.cycles.transparent_max_bounces = 24
sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
sc.view_settings.view_transform = 'AgX'
try: sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception: pass
r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGB'; r.filepath = OUT
bpy.ops.render.render(write_still=True)
print('rendered', OUT)

# Styled looks for the closed vessel. Exec'd from mech.py (shares its globals). LOOK = studio | fortnite | invert
LOOK = E('LOOK'); MET = E('METAL', 'brushed')
def nm(name, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    for k, v in kw.items():
        if k in b.inputs: b.inputs[k].default_value = v
    return m, b
def set_mats(ob, mats):
    ob.data.materials.clear(); [ob.data.materials.append(m) for m in mats]
def sweep(col, curve_r=0.30, rough=0.92):
    bm_ = bmesh.new(); prof_ = [(-1.2, 0.0)] + [(curve_r - curve_r * math.cos(a), curve_r - curve_r * math.sin(a)) for a in np.linspace(math.pi / 2, 0, 24)] + [(curve_r, 1.6)]
    # profile in (y, z): floor toward camera (-y), curving up into a back wall at +y
    prof_ = [(-1.2, 0.0)] + [(0.25 + curve_r * math.sin(a), curve_r - curve_r * math.cos(a)) for a in np.linspace(0, math.pi / 2, 24)] + [(0.25 + curve_r, 1.6)]
    rows_ = []
    for x in (-1.5, 1.5): rows_.append([bm_.verts.new((x, y, z)) for y, z in prof_])
    for i in range(len(prof_) - 1): bm_.faces.new((rows_[0][i], rows_[0][i + 1], rows_[1][i + 1], rows_[1][i]))
    me_ = bpy.data.meshes.new('sweep'); bm_.to_mesh(me_); bm_.free(); me_.shade_smooth()
    ob_ = bpy.data.objects.new('sweep', me_); bpy.context.collection.objects.link(ob_)
    m_, _ = nm('sweep', **{'Base Color': col, 'Roughness': rough, 'Specular IOR Level': 0.2}); me_.materials.append(m_)
    # rotate so the wall sits behind the egg as seen from the camera
    ob_.rotation_euler = (0, 0, CAM_TH + math.pi / 2)
    return ob_
def area(name, loc, a, b, e, col=(1, 1, 1), tgt=(0, 0, 0.05), shape='RECTANGLE', cam_vis=False):
    ld = bpy.data.lights.new(name, 'AREA'); ld.shape = shape; ld.size = a; ld.size_y = b; ld.energy = e; ld.color = col
    ob = bpy.data.objects.new(name, ld); bpy.context.collection.objects.link(ob)
    v = rot @ mathutils.Vector(loc); ob.location = v
    ob.rotation_euler = mathutils.Vector(np.array(tgt) - np.array(v)).to_track_quat('-Z', 'Y').to_euler(); ob.visible_camera = cam_vis
    return ob
def flag(loc, w, h):
    # black card the chrome can mirror; hidden from camera
    bpy.ops.mesh.primitive_plane_add(size=1); f = bpy.context.active_object; f.scale = (w, h, 1)
    v = rot @ mathutils.Vector(loc); f.location = v
    f.rotation_euler = (mathutils.Vector((0, 0, 0.07)) - v).to_track_quat('Z', 'Y').to_euler()
    fm, _ = nm('flag', **{'Base Color': (0.005, 0.005, 0.006, 1), 'Roughness': 0.95}); f.data.materials.append(fm); f.visible_camera = False
    return f
rot = mathutils.Matrix.Rotation(CAM_TH + math.pi / 2, 3, 'Z')    # rig space: camera looks along +y from -y
world = bpy.data.worlds.new('w'); scene.world = world; world.use_nodes = True; wn = world.node_tree.nodes; wl = world.node_tree.links
bg = wn['Background']
G = lambda k, d: float(E(k, d))

def sterling(name, base=tuple(map(float, E('SILVER', '0.93,0.93,0.94').split(','))) + (1,), ox=(0.018, 0.018, 0.02, 1), oxr=0.62):
    # polished silver; anything cut (attribute 'carve') goes blackened and duller, like oxidised sterling
    m, b = nm(name, **{'Base Color': base, 'Metallic': 1.0, 'Roughness': 0.1})
    t = m.node_tree; at = t.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'carve'
    cr = t.nodes.new('ShaderNodeMapRange'); t.links.new(at.outputs['Fac'], cr.inputs['Value']); cr.inputs['From Min'].default_value = 0.25; cr.inputs['From Max'].default_value = 0.6
    mc = t.nodes.new('ShaderNodeMix'); mc.data_type = 'RGBA'; t.links.new(cr.outputs['Result'], mc.inputs['Factor'])
    mc.inputs[6].default_value = base; mc.inputs[7].default_value = ox; t.links.new(mc.outputs[2], b.inputs['Base Color'])
    mr = t.nodes.new('ShaderNodeMapRange'); t.links.new(cr.outputs['Result'], mr.inputs['Value']); mr.inputs['To Min'].default_value = 0.1; mr.inputs['To Max'].default_value = oxr
    t.links.new(mr.outputs['Result'], b.inputs['Roughness'])
    return m
TIER = E('TIER', '')
if TIER in ('epic', 'legendary'):
    st = sterling('sterling_head'); set_mats(head, [st, st, st])
if TIER == 'legendary':
    set_mats(egg, [sterling('sterling_body', ox=(0.32, 0.32, 0.34, 1), oxr=0.4)])   # lettering: smoky satin, still a deboss
if LOOK == 'studio':
    BGC = srgb_to_lin(E('BG', '#A9D6F2'))
    sweep(BGC)
    bg.inputs['Color'].default_value = BGC; bg.inputs['Strength'].default_value = G('WORLD', '0.35')
    area('key', (-0.45, -0.40, 0.55), 0.9, 0.9, G('KEY', '30'))
    area('fill', (0.55, -0.35, 0.25), 0.9, 0.9, G('FILL', '9'))
    area('top', (0.0, 0.0, 0.75), 0.6, 0.6, G('TOP', '12'))
    area('back', (0.0, 0.45, 0.35), 0.5, 0.3, G('BACK', '6'))
    flag((0.0, 0.32, 0.30), 0.7, 0.35)
    area('strip_head', (0.0, 0.30, 0.26), 0.40, 0.02, G('STRIP', '1.2'), tgt=(0, 0, 0.08))

elif LOOK == 'fortnite':
    # stylised game-item finish: cel bands from a fixed key direction, hard spec, rim, ink outline, cartoon sky
    Ldir = (rot @ mathutils.Vector((-0.45, -0.55, 0.75))).normalized()
    def toon(name, dark, mid, light, spec='#FFFFFF', rim='#E8FCFF', bands=(0.05, 0.55), spec_t=0.985, rim_t=0.62, rim_mix=0.8):
        m = bpy.data.materials.new(name); m.use_nodes = True; t = m.node_tree; N_ = t.nodes; L_ = t.links
        for n in list(N_):
            if n.type != 'OUTPUT_MATERIAL': N_.remove(n)
        out = [n for n in N_][0]
        geo = N_.new('ShaderNodeNewGeometry')
        ld = N_.new('ShaderNodeCombineXYZ'); ld.inputs[0].default_value, ld.inputs[1].default_value, ld.inputs[2].default_value = Ldir
        dot = N_.new('ShaderNodeVectorMath'); dot.operation = 'DOT_PRODUCT'; L_.new(geo.outputs['Normal'], dot.inputs[0]); L_.new(ld.outputs[0], dot.inputs[1])
        r = N_.new('ShaderNodeValToRGB'); L_.new(dot.outputs['Value'], r.inputs['Fac']); cr = r.color_ramp; cr.interpolation = 'EASE'
        cr.elements[0].position = bands[0] - 0.04; cr.elements[0].color = srgb_to_lin(dark)
        cr.elements[1].position = bands[0] + 0.04; cr.elements[1].color = srgb_to_lin(mid)
        e = cr.elements.new(bands[1] - 0.03); e.color = srgb_to_lin(mid)
        e = cr.elements.new(bands[1] + 0.03); e.color = srgb_to_lin(light)
        # spec: N.H
        h = N_.new('ShaderNodeVectorMath'); h.operation = 'ADD'; L_.new(ld.outputs[0], h.inputs[0]); L_.new(geo.outputs['Incoming'], h.inputs[1])
        hn = N_.new('ShaderNodeVectorMath'); hn.operation = 'NORMALIZE'; L_.new(h.outputs[0], hn.inputs[0])
        d2 = N_.new('ShaderNodeVectorMath'); d2.operation = 'DOT_PRODUCT'; L_.new(geo.outputs['Normal'], d2.inputs[0]); L_.new(hn.outputs[0], d2.inputs[1])
        sp = N_.new('ShaderNodeMapRange'); L_.new(d2.outputs['Value'], sp.inputs['Value']); sp.inputs['From Min'].default_value = spec_t - 0.004; sp.inputs['From Max'].default_value = spec_t + 0.004
        m1 = N_.new('ShaderNodeMix'); m1.data_type = 'RGBA'; L_.new(sp.outputs['Result'], m1.inputs['Factor']); L_.new(r.outputs['Color'], m1.inputs[6]); m1.inputs[7].default_value = srgb_to_lin(spec)
        # rim on the shadow side edge
        lw = N_.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.5
        rr = N_.new('ShaderNodeMapRange'); L_.new(lw.outputs['Facing'], rr.inputs['Value']); rr.inputs['From Min'].default_value = rim_t; rr.inputs['From Max'].default_value = rim_t + 0.04
        rk = N_.new('ShaderNodeMath'); rk.operation = 'MULTIPLY'; rk.inputs[1].default_value = rim_mix; L_.new(rr.outputs['Result'], rk.inputs[0])
        m2 = N_.new('ShaderNodeMix'); m2.data_type = 'RGBA'; L_.new(rk.outputs[0], m2.inputs['Factor']); L_.new(m1.outputs[2], m2.inputs[6]); m2.inputs[7].default_value = srgb_to_lin(rim)
        em = N_.new('ShaderNodeEmission'); L_.new(m2.outputs[2], em.inputs['Color']); L_.new(em.outputs[0], out.inputs['Surface'])
        return m
    P_ = {'sky': ('#1F6FD1', '#3FA6FF', '#8FD6FF'), 'rose': ('#C2416A', '#F27497', '#FFB3C7'), 'sage': ('#4E8F3A', '#7CC45E', '#BDEB9E'),
          'cobalt': ('#0E2F9E', '#1A5FD6', '#5C9BFF'), 'cloud': ('#B7A992', '#E8E0D2', '#FFFFFF')}[E('TOON', 'sky')]
    set_mats(egg, [toon('egg_toon', *P_, rim_t=0.66)])
    hc = toon('head_toon', '#3E4C60', '#8A9AAE', '#D9E3EE', rim='#FFFFFF', bands=(0.15, 0.62), spec_t=0.97)
    hd = toon('head_brush', '#56667C', '#9FB0C4', '#E6EEF6', rim='#FFFFFF', bands=(0.2, 0.8), spec_t=0.995)
    hy = toon('head_y', '#FFFFFF', '#FFFFFF', '#FFFFFF', rim='#FFFFFF', bands=(0.0, 0.5), spec_t=0.999)
    set_mats(head, [hc, hd, hy])
    # ink outline: inverted hull
    INK = srgb_to_lin(E('INK', '#0B2A5C'))
    def ink(ob, thick):
        me0 = ob.data; n = len(me0.vertices)
        co = np.empty(n * 3, np.float32); me0.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
        nv = np.empty(n * 3, np.float32); me0.vertices.foreach_get('normal', nv); nv = nv.reshape(-1, 3)
        me1 = me0.copy(); me1.vertices.foreach_set('co', (co + nv * thick * MM).ravel()); me1.flip_normals(); me1.update()
        me1.materials.clear()
        im = bpy.data.materials.new('ink'); im.use_nodes = True; it = im.node_tree; [it.nodes.remove(x) for x in list(it.nodes) if x.type != 'OUTPUT_MATERIAL']
        g = it.nodes.new('ShaderNodeNewGeometry'); emn = it.nodes.new('ShaderNodeEmission'); emn.inputs['Color'].default_value = INK
        tr2 = it.nodes.new('ShaderNodeBsdfTransparent'); mx_ = it.nodes.new('ShaderNodeMixShader')
        it.links.new(g.outputs['Backfacing'], mx_.inputs['Fac']); it.links.new(emn.outputs[0], mx_.inputs[1]); it.links.new(tr2.outputs[0], mx_.inputs[2])
        it.links.new(mx_.outputs[0], [x for x in it.nodes if x.type == 'OUTPUT_MATERIAL'][0].inputs['Surface'])
        me1.materials.append(im); me1.polygons.foreach_set('material_index', np.zeros(len(me1.polygons), np.int32))
        cp = bpy.data.objects.new(ob.name + '_ink', me1); bpy.context.collection.objects.link(cp); cp.parent = ob.parent; cp.matrix_local = ob.matrix_local.copy()
        cp.visible_shadow = False
        return cp
    if not E('NOINK'): ink(egg, G('INKW', '0.9')); ink(head, G('INKW', '0.9') * 0.7)
    set_mats(slot, [toon('slot_t', '#0A1A33', '#0F2547', '#1A3A66', rim='#1A3A66')])
    # sky in screen space: gradient, a halo behind the item, flat cartoon clouds low in frame
    tc = wn.new('ShaderNodeTexCoord'); sep = wn.new('ShaderNodeSeparateXYZ'); wl.new(tc.outputs['Window'], sep.inputs['Vector'])
    ramp = wn.new('ShaderNodeValToRGB'); wl.new(sep.outputs['Y'], ramp.inputs['Fac'])
    ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = srgb_to_lin(E('SKYLO', '#9FE3FF'))
    ramp.color_ramp.elements[1].position = 1.0; ramp.color_ramp.elements[1].color = srgb_to_lin(E('SKYHI', '#1B7FE8'))
    # halo
    cx = wn.new('ShaderNodeVectorMath'); cx.operation = 'SUBTRACT'; wl.new(tc.outputs['Window'], cx.inputs[0]); cx.inputs[1].default_value = (0.5, 0.52, 0)
    sc = wn.new('ShaderNodeVectorMath'); sc.operation = 'MULTIPLY'; wl.new(cx.outputs[0], sc.inputs[0]); sc.inputs[1].default_value = (RX / RY, 1, 0)
    ln = wn.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; wl.new(sc.outputs[0], ln.inputs[0])
    hr = wn.new('ShaderNodeMapRange'); wl.new(ln.outputs['Value'], hr.inputs['Value']); hr.inputs['From Min'].default_value = 0.42; hr.inputs['From Max'].default_value = 0.08
    hp = wn.new('ShaderNodeMath'); hp.operation = 'POWER'; hp.inputs[1].default_value = 1.6; wl.new(hr.outputs['Result'], hp.inputs[0])
    hk = wn.new('ShaderNodeMath'); hk.operation = 'MULTIPLY'; hk.inputs[1].default_value = G('HALO', '0.7'); wl.new(hp.outputs[0], hk.inputs[0])
    mh = wn.new('ShaderNodeMix'); mh.data_type = 'RGBA'; wl.new(hk.outputs[0], mh.inputs['Factor']); wl.new(ramp.outputs['Color'], mh.inputs[6]); mh.inputs[7].default_value = srgb_to_lin('#E9FBFF')
    # clouds: overlapping round puffs (voronoi), flat white with a pale-blue belly, kept to the bottom of frame
    def puffs(scale, sx, off, rad):
        mp = wn.new('ShaderNodeMapping'); wl.new(tc.outputs['Window'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (sx * RX / RY, 1, 1)
        mp.inputs['Location'].default_value = (off, 0, 0)
        vo = wn.new('ShaderNodeTexVoronoi'); vo.inputs['Scale'].default_value = scale; vo.inputs['Randomness'].default_value = 0.8; wl.new(mp.outputs[0], vo.inputs['Vector'])
        yk = wn.new('ShaderNodeMath'); yk.operation = 'MULTIPLY'; yk.inputs[1].default_value = G('CLK', '2.2'); wl.new(sep.outputs['Y'], yk.inputs[0])
        dd = wn.new('ShaderNodeMath'); dd.operation = 'ADD'; wl.new(vo.outputs['Distance'], dd.inputs[0]); wl.new(yk.outputs[0], dd.inputs[1])
        mr = wn.new('ShaderNodeMapRange'); wl.new(dd.outputs[0], mr.inputs['Value']); mr.inputs['From Min'].default_value = rad; mr.inputs['From Max'].default_value = rad - 0.02
        return mr
    p1 = puffs(3.2, 1.0, float(E('CLX', '0.3')), G('PR', '0.40')); p2 = puffs(5.5, 1.0, float(E('CLX', '0.3')) + 0.17, G('PR', '0.40') - 0.02)
    mxp = wn.new('ShaderNodeMath'); mxp.operation = 'MAXIMUM'; wl.new(p1.outputs['Result'], mxp.inputs[0]); wl.new(p2.outputs['Result'], mxp.inputs[1])
    yb = wn.new('ShaderNodeMapRange'); wl.new(sep.outputs['Y'], yb.inputs['Value']); yb.inputs['From Min'].default_value = 1.0; yb.inputs['From Max'].default_value = 0.99
    cm = wn.new('ShaderNodeMath'); cm.operation = 'MULTIPLY'; wl.new(mxp.outputs[0], cm.inputs[0]); wl.new(yb.outputs['Result'], cm.inputs[1])
    base = wn.new('ShaderNodeMapRange'); wl.new(sep.outputs['Y'], base.inputs['Value']); base.inputs['From Min'].default_value = float(E('CLB', '0.1')); base.inputs['From Max'].default_value = float(E('CLB', '0.1')) - 0.005
    cmb = wn.new('ShaderNodeMath'); cmb.operation = 'MAXIMUM'; wl.new(cm.outputs[0], cmb.inputs[0]); wl.new(base.outputs['Result'], cmb.inputs[1]); cm = cmb
    cmr = wn.new('ShaderNodeMath'); cmr.operation = 'MINIMUM'; cmr.inputs[1].default_value = 1.0; wl.new(cm.outputs[0], cmr.inputs[0])
    bel = wn.new('ShaderNodeMapRange'); wl.new(sep.outputs['Y'], bel.inputs['Value']); bel.inputs['From Min'].default_value = 0.0; bel.inputs['From Max'].default_value = 0.12
    cc = wn.new('ShaderNodeMix'); cc.data_type = 'RGBA'; wl.new(bel.outputs['Result'], cc.inputs['Factor']); cc.inputs[6].default_value = srgb_to_lin('#C4ECFF'); cc.inputs[7].default_value = (1, 1, 1, 1)
    mc = wn.new('ShaderNodeMix'); mc.data_type = 'RGBA'; wl.new(cmr.outputs[0], mc.inputs['Factor']); wl.new(mh.outputs[2], mc.inputs[6]); wl.new(cc.outputs[2], mc.inputs[7])
    bg.inputs['Strength'].default_value = 1.0; wl.new(mc.outputs[2], bg.inputs['Color'])
elif LOOK == 'invert':
    # metal body, soft silicone head
    sil = (tuple(map(float, E('SKIN_LIN').split(','))) + (1.0,)) if E('SKIN_LIN') else srgb_to_lin('#62B0E4')
    hm, hb = nm('head_sil', **{'Base Color': sil, 'Roughness': 0.62, 'Sheen Weight': 0.55, 'Sheen Roughness': 0.35, 'Sheen Tint': (1, 1, 1, 1),
                                'Subsurface Weight': 0.06, 'Subsurface Scale': 0.002, 'Specular IOR Level': 0.35})
    sil_d = tuple(c * 0.7 for c in sil[:3]) + (1.0,)
    hy, _ = nm('head_y', **{'Base Color': tuple(c * 0.45 for c in sil[:3]) + (1.0,), 'Roughness': 0.7, 'Specular IOR Level': 0.3})
    set_mats(head, [hm, hm, hy])
    if MET == 'brushed':
        mm, mb = nm('body', **{'Base Color': (0.86, 0.87, 0.88, 1), 'Metallic': 1.0, 'Roughness': 0.22, 'Anisotropic': 0.9})
        t_ = mm.node_tree.nodes.new('ShaderNodeTangent'); t_.direction_type = 'RADIAL'; t_.axis = 'Z'
        mm.node_tree.links.new(t_.outputs['Tangent'], mb.inputs['Tangent'])
    elif MET == 'mirror':
        mm, mb = nm('body', **{'Base Color': (0.95, 0.96, 0.97, 1), 'Metallic': 1.0, 'Roughness': 0.02})
    elif MET == 'bead':
        mm, mb = nm('body', **{'Base Color': (0.72, 0.71, 0.69, 1), 'Metallic': 1.0, 'Roughness': 0.38})
    elif MET == 'pvd':
        mm, mb = nm('body', **{'Base Color': (0.16, 0.165, 0.18, 1), 'Metallic': 1.0, 'Roughness': 0.12, 'Anisotropic': 0.6})
        t_ = mm.node_tree.nodes.new('ShaderNodeTangent'); t_.direction_type = 'RADIAL'; t_.axis = 'Z'
        mm.node_tree.links.new(t_.outputs['Tangent'], mb.inputs['Tangent'])
    elif MET == 'anodized':
        # titanium heat-tint: thin film over grey ti, blue-violet at the shoulders
        mm, mb = nm('body', **{'Base Color': (0.62, 0.62, 0.64, 1), 'Metallic': 1.0, 'Roughness': 0.12,
                               'Thin Film Thickness': G('FILM', '420'), 'Thin Film IOR': 2.2})
    set_mats(egg, [mm])
    BGC = srgb_to_lin(E('BG', '#A9D6F2')); sweep(BGC)
    bg.inputs['Color'].default_value = BGC; bg.inputs['Strength'].default_value = G('WORLD', '0.6')
    # big soft boxes the metal can mirror: tall strips read as clean highlights on a curved body
    area('strip_L', (-0.30, -0.18, 0.18), 0.10, 0.70, G('STRIPL', '18'), tgt=(0, 0, 0.04))
    area('strip_R', (0.32, -0.10, 0.16), 0.06, 0.70, G('STRIPR', '10'), tgt=(0, 0, 0.04))
    area('top', (0.0, -0.05, 0.6), 0.5, 0.5, G('TOP', '14'))
    area('key', (-0.4, -0.45, 0.4), 0.8, 0.8, G('KEY', '8'))
    # a large dim card in front so the near side of the metal is not black
    area('front', (0.0, -0.6, 0.12), 1.2, 0.5, G('FRONT', '4'), tgt=(0, 0, 0.05))

cam_d = bpy.data.cameras.new('cam'); cam_d.lens = G('LENS', '100'); cam_d.sensor_fit = 'VERTICAL'; cam_d.sensor_height = 36
cam = bpy.data.objects.new('cam', cam_d); bpy.context.collection.objects.link(cam); scene.camera = cam
tgt = mathutils.Vector((0, 0, G('CAM_Z', '0.046'))); elev = math.radians(G('CAM_EL', '14')); dist = G('CAM_D', '0.46')
cam.location = tgt + mathutils.Vector((dist * math.cos(elev) * math.cos(CAM_TH), dist * math.cos(elev) * math.sin(CAM_TH), dist * math.sin(elev)))
cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = SAMPLES; scene.cycles.use_denoising = True
scene.cycles.use_adaptive_sampling = True; scene.cycles.adaptive_threshold = 0.01
scene.cycles.max_bounces = 8; scene.cycles.glossy_bounces = 6
scene.render.resolution_x = RX; scene.render.resolution_y = RY; scene.render.filter_size = 1.2
scene.view_settings.view_transform = E('VT', 'Standard'); scene.view_settings.look = E('VLOOK', 'None'); scene.view_settings.exposure = G('EXPO', '0')
scene.render.image_settings.file_format = 'PNG'; scene.render.filepath = OUT
bpy.ops.render.render(write_still=True); print('done', OUT)

# Studio cutout of the egg on a transparent background, for the area-style hero. SKIN = sky | rose | sage | cloud
import os, math
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_helpers.py')).read())
SKIN = E('SKIN', 'sky'); OUT = E('OUT', os.path.join(HERE, 'cut_' + SKIN + '.png'))
bgn.inputs['Color'].default_value = (1, 1, 1, 1); bgn.inputs['Strength'].default_value = 0.12
egg = load_egg(lin(SKIN)); egg.rotation_euler = (0, 0, math.radians(-10))
area('key', (-0.32, -0.22, 0.26), 0.25, 7, tgt=(0, 0, 0.04)); area('rim', (0.28, 0.24, 0.2), 0.12, 6, tgt=(0, 0, 0.05))
area('top', (0.02, 0.0, 0.4), 0.2, 3, tgt=(0, 0, 0.08)); area('fill', (0.35, -0.3, 0.03), 0.4, 0.8, tgt=(0, 0, 0.04))
camera((0, -0.5, 0.12), (0, 0, 0.044), 130)
scene.render.film_transparent = True
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = SAMPLES; scene.cycles.use_denoising = True
scene.render.resolution_x = RX; scene.render.resolution_y = RY; scene.render.image_settings.color_mode = 'RGBA'
scene.view_settings.view_transform = 'AgX'; scene.view_settings.look = 'AgX - Medium High Contrast'
scene.render.filepath = OUT; bpy.ops.render.render(write_still=True); print('done', OUT)

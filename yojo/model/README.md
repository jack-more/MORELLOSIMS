# YOJO vessel 3D model

This is the source of truth for the vessel. Every spec render and mechanism video comes from `mech.py`.

- `mech.py`: the working model (skin, shell, weight, collar, threaded sleeve, pump, 30 ml cup, head). It renders locked, open, pressed or the animation, with an optional static quarter section.
- `build.py`: the earlier hero and studio renderer. It uses the same egg outline.
- `calc.py`: computes the weight mass and volumes from the profile.
- `calib.py`: color calibration. It renders, measures and corrects until the colors hit the target hex values.
- `masks.py` + `shotm.js`: rasterize the YOJO / GHK-CU deboss and the Y engraving from the wordmark trace.
- `run.sh` / `finish.sh`: animation batch and encode.

Requires Blender as a Python module: `python -m venv bl && bl/bin/pip install bpy==5.2.3 pillow`. Run these from a folder that holds `bl/` one level up. The paths are relative.

Example: `STATE=open CLIP=1 CAM_TH=-118 TEXT_TH=-28 OUT=$PWD/open.png ../bl/bin/python mech.py`

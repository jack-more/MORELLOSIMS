# The plain box (carton v3 B): approved reference

The founders' favourite packaging images. Every box render and box decision is measured against these.

- `renders/bb-plain-closed.webp`: RT-3, closed (hero)
- `renders/bb-plain-open.webp`: RT-3, open from above, the inside flooded in the area colour
- `renders/set-pack.webp`, `renders/set-pack-card.webp`: the four-box set (RT-3, BPC+TB, GHK-Cu, Selank)
- `renders/carton-NN.webp`: one per product, as shown on the product pages
- `source/v3/`: the face artwork (`gen.py` over `base.py`)
- `source/v3-pack-src/`: the factory pack builder (`pack.py`), face export (`faces.py`) and the Blender scenes (`scene_plainB.py`, `scene_site.py`)

Missing: `scene_w6.py`, the window-box Blender scene that `scene_plainB.py` builds on. It was lost with a scratch-space wipe. Rebuild it (geometry: `zuma-content/packaging/window/final-RevF/geomF.json`) before making new box renders.

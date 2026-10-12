# ZUMA (staging)

Static site for ZUMA research peptides, plus the source and render setup that produce it.

- `site/`: the built site Netlify serves (index.html, shop.html, one page per compound, assets/).
- `source/`: the site source. `python3 source/build.py` rebuilds into `source/dist/`; copy that into `site/`.
- `render/`: the Blender (Cycles) scene for every vial, set, box and turn-frame image (`render/vial.py`) and its textures.
  `render/tex/studio.hdr` is "Studio Small 09" from Poly Haven (CC0).

Netlify: Import from Git → this repo → branch `claude/nice-planck-sn9yd9` → base directory `zuma`. No build command; publish directory `site` (set in `netlify.toml`).

For laboratory research use only. Not for human or veterinary use.

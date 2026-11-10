# ZUMA Lightbox, live 3D (10 Nov 2026)

The site's own Lightbox (ombre.js, the same settings as the site's canvases) with live motion on top, after the founders' three.js reference.
v1 (procedural glass, wire mesh, code-drawn leaves) looked worse than the site and was dropped. v2 keeps the real Lightbox untouched
and adds a pixel-scale glass shimmer, a slow drift, and a soft pool of light that follows the pointer or finger. One research colour at a time
(Tissue, Metabolic, Dermal, Endocrine, Neuro, ZUMA grey), never blended.

- `index.html` + `ombre.js` (a copy of the site's): plain WebGL, no other libraries. `?area=metabolic` picks the colour; `?t=3` freezes a frame for stills.
- `lightbox-live.mp4`: 8 seconds of it moving. `lightbox-3d-tissue-metabolic.jpg`: stills.
- Not on the live site; it deploys only when a founder says "deploy".

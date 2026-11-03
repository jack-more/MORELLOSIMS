# ZUMA: project memory

Read this before any ZUMA design, packaging, site or writing work.

## Packaging decision (3 Nov 2026): ONE bag, ONE box, ONE colour

- The founders want no colour SKUs in packaging. There is one vacuum bag and one box for every vial, both in the ZUMA grey.
- **ZUMA grey is the ZUMA shop / family colour:** the grey Lightbox, light #E3E8ED, mid #9AA8B6, deep #3D4956, panel #4E6077. It was "Lab supplies · Stone"; there is no Lab supplies research area any more.
- **Research colours are five:** Metabolic, Dermal, Endocrine, Tissue, Neuro. They live on the vial labels and the site, not on the packaging.
- **The compound name goes on a sticker** (Snow, name in Oxblood) on the box front and on the bag. The box carries no compound name and no area line. Box: `zuma-content/packaging/one-box/`.
- **The bag is "Lane" in grey:** clear vacuum film, the grey Lightbox as a solid strip down the left under the tall wordmark, and the crest, bar and type in Oxblood printed on clear film. Concepts: `zuma-content/packaging/vacuum-bag/clear-concepts/`.

## Approved and loved (do not drift from these)

- **The plain box (carton v3 B).** The founders call these renders beautiful. They are the reference for every box image and every packaging decision.
  - Renders: `zuma-content/brand/approved/plain-box/renders/`. `bb-plain-closed.webp` is the RT-3 hero, `set-pack.webp` the four-box set (RT-3, BPC+TB, GHK-Cu, Selank), and `carton-NN.webp` one per product.
  - The look: white board, the Lightbox panels in tones of the area colour, a tall area-colour panel on the front with the crest reversed out in Snow, the area-colour top with the crest knocked out, and an Oxblood band round the base with the ZUMA wordmark in Snow.
  - Artwork source: `zuma-content/brand/approved/plain-box/source/` (`v3/base.py` + `gen.py` for the faces, `v3-pack-src/pack.py` for the factory pack). The factory pack is `zuma-content/packaging/plain-box/v3B-factory/`.
  - Gap: the Blender scene behind these renders (`scene_w6.py`, which `scene_plainB.py` and `scene_site.py` build on) was lost when a session's scratch space was wiped. The finished renders are kept here. Rebuild the scene before making new box renders.
- **Vacuum bag: style 10.** A full-bleed area Lightbox, the tall ZUMA wordmark up the left side, the crest top right, and Oxblood bars placed by hand that run in from the right edge and stop clear of the type. Set: `zuma-content/packaging/pouch/pouch-style10-set.png`. Supplier pack: `zuma-content/packaging/vacuum-bag/`.
- **Vial labels: Rev 4 (no QR code; the ZUMA star on the left panel).** `zuma-content/packaging/print-pack-vial-labels/`.
  - Every product is on the 3 mL vial (Ø 16 mm, 35 mm tall with the cap) with the 13 mm Oxblood flip-off cap, except BAC water (03) and NAD+ (08), which are on the 10 mL vial (Ø 24 mm) with the 65 × 30.2 mm label centred on the wall.
  - Contents: white lyophilized powder, except GHK-Cu (blue powder) and BAC water (clear liquid).
  - Site renderer: `zuma/render/vial.py`, which uses `render/tex/rev2/`.
- **Stickers:** `zuma-content/stickers/`. No borders.

## Rules the founders have set

- Ask before doing design or writing work. If a direction might be off, stop and ask; do not ship defaults.
- No tracked-out monospace caps with dots between words, on any product surface. Use the brand sans in sentence case.
- Never let a shadow, bar or texture clash with a labelled asset. Keep the Lightbox clean where type sits on it.
- Each Lightbox field is one research area, never blended. Oxblood is its own lane.
- Do not change an approved design when putting it into production. Scale it; do not redesign it. Raise any print problem as a question.
- Keep packaging specs physically true: real vial sizes, real bag sizes, and real clear and solid layers. Check the supplier's listing photos before writing a spec.
- Never write "it's not X, it's Y".
- No dosing advice or human-use claims anywhere. Keep "For laboratory research use only. Not for human or veterinary use." on every product surface.
- No dose on the boxes.
- The live site only deploys when a founder says the word "deploy".
- Keep personal contact details and supplier prices out of the repo.
- Commit and push work to the session's branch; scratch space can be wiped.

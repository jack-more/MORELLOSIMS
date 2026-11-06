# ZUMA: project memory

Read this before any ZUMA design, packaging, site or writing work.

## Packaging decision (3 Nov 2026): ONE bag, ONE box, ONE colour

- The founders want no colour SKUs in packaging. There is one vacuum bag and one box for every vial, both in the ZUMA grey.
- **ZUMA grey is the ZUMA shop / family colour:** the grey Lightbox, light #E3E8ED, mid #9AA8B6, deep #3D4956, panel #4E6077. It was "Lab supplies · Stone"; there is no Lab supplies research area any more.
- **Research colours are five:** Metabolic, Dermal, Endocrine, Tissue, Neuro. They live on the vial labels and the site, not on the packaging.
- **The box (decided 4 Nov 2026): ONE box for every product, the plain carton v3 B in ZUMA blue #1E74A8** (panels, top flap, inside flood), Oxblood band and wordmark unchanged. No compound name, no area line. Factory pack: `zuma-content/packaging/one-box/factory-blue/`.
- **The compound is named by a round sticker** (16 mm, no border: the compound's research-area Lightbox, the crest in the middle, the name round the top edge, zumatides.com round the bottom, all Oxblood). It replaces the rectangular name stickers. Files: `zuma-content/stickers/round-compound/`. The bag carries no sticker.
- **Full production set** (every piece as .ai, with each supplier's message): `zuma-content/production/ZUMA-full-set.zip`.
- **The bag: APPROVED 4 Nov 2026 ("this is perfect"). The tinted bag, big ZUMA, split layers, 100 x 150 mm, holds two vials, in three tints: red, blue and grey.** This replaces the colour-free one-bag rule above for the bag; the box rule is unchanged. Reference render: `zuma-content/packaging/vacuum-bag/tinted/split-red-blue-grey-two-vials.jpg`.
  - Size: 100 x 150 mm outside, 5 mm seals (the supplier, Alibaba listing 1600480585221, makes custom sizes). The same 2:3 shape as the old 70 x 105 bag, so the art scales without a redesign. It holds two 3 mL vials, or a 3 mL and a 10 mL, or two 10 mL (tight: the 10 mL pair touches the copy).
  - Front sheet: clear film printed with that tint's own Lightbox as see-through ink (the tiles and the darker pools sit on the front; red = the Oxblood field, blue = Metabolic, grey = ZUMA grey). Printed solid in Snow on a white underlay: the tall ZUMA up the left, the crest and zumatides.com top right, "Research peptides, tested by lot", the leaflet copy on its side down the right edge, the research-use line, Lot and Packed lines, "ZUMA vacuum pack, 100 x 150 mm". No compound sticker on the bag.
  - Back sheet: the palm shadow only, on light neutral, the same for every tint.
  - Plates in `tinted/source/`: `front-tint-red|blue|grey.png` (the Lightbox ink), `back-sheet-shadow.png`, the Snow art from `art_big.py`. Renders: `bag4.py` (several vials, no cloth sim, crisp film), `hang.py` (rail scene).
  - Clear option still open: fully clear with Oxblood print looked strongest (`tinted/clear-three-versions.jpg`). Supplier print plates are not built yet.

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
- **Bubble mailer B (approved 4 Nov 2026, "I fucking love it"):** white film, one spot ink (ZUMA Oxblood). Back (side A): the tall ZUMA, crest, "Tested by lot", palm shadow, all below the 44 mm flap line. Front (side B): ZUMA, crest, 4 x 6 in label outline, bamboo down both edges. Shadows are the same ink as a tint (max 28%), 2 mm clear of type. The mailer never says "peptides". Pack: `zuma-content/packaging/mailer-factory-B/` (replaces `mailer-factory/`).
- **Vector files:** labels, bag and mailer all have `.ai` files (PDF-based, type as outlines, exact page and TrimBox) written by `pdfw.py`; see each pack's `vector/` and `source/`.

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

## Tools and stack

- **Generative media (images and video):** Krea and Fal, accessed through Nous Portal, on a custom generative-media plugin in Hermes Desktop. (Noted 6 Nov 2026.)

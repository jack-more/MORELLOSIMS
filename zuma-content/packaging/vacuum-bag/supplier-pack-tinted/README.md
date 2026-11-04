# ZUMA tinted vacuum bag: supplier pack (approved 4 Nov 2026)

Send `ZUMA-vacuum-bag-tinted-supplier-pack.zip` (5 MB: the .ai files, the spec, the die line and the proofs) with the text in `MESSAGE-TO-SUPPLIER.txt` (fill in the target price in the chat, not in this repo). The 600 dpi raster plates in `print/` are the backup set.
Supplier: Alibaba listing 1600480585221 (QD XTD Plastic Products). This replaces the older fully printed pack in `../` and `../clear-concepts/`: do not send those.

- 100 x 150 mm flat vacuum pouch, 3-side seal, open top, 5 mm seals, tear notches 18 mm from the top.
- Front: plate 1 transparent colour ink (red / blue / grey), plate 2 opaque white on the type only (shared).
- Back: white flood + palm shadow in grey K (shared).
- Files are 106 x 156 mm (3 mm bleed), 600 dpi. `source/build.py` rebuilds them from the art in the session scratch (`vac/`).
- Open question for the supplier: the smallest white type is about 4.5 pt.

## Vector / Illustrator files (`vector/`)

- `ZUMA-bag-front-red|blue|grey.ai` (+ the same as `.pdf`): the colour ink as a 600 dpi image, with the white artwork as vector paths on top and the die line.
- `ZUMA-bag-front-white-ink-plate.ai`: the white plate only (black = white ink), all vector.
- `ZUMA-bag-back.ai`: the white flood plus the shadow as a 600 dpi image.
- Every letter is converted to outlines (no fonts in the files). The .ai files are PDF-based: Illustrator opens them directly, and the parts come in as groups (Dieline, White ink, Colour) rather than named layers.
- Rebuild: `source/extract.cjs` (reads the glyph positions from the artwork in Chrome), `source/build_ai.py` (outlines with the Outfit font), `source/topdf.cjs`.

# ZUMA vial labels: print pack (Option C)

Plain clear 3 mL vial, Oxblood flip-off cap, tricolour wrap label. Twelve SKUs: ten on the 3 mL vial, plus BAC water (03) and NAD+ (08) on a standard 10 mL vial (Rev 4: no QR code, the ZUMA star in its place).

**Send to the printer:** `ZUMA-vial-label-print-spec-Rev4.pdf` plus everything in `print/`.

- `print/zuma-label-NN-print.pdf`: one per SKU. Page 46 × 23 mm = 43 × 20 mm trim + 1.5 mm bleed. No crop marks.
- `art/zuma-label-NN-art.png`: the same art as PNG, 3080 × 1540 px (1702 dpi), for printers that want images.
- `proofs/`: each label with the trim (blue) and safe-area (pink) lines, and `all-labels-proof.jpg`.
- `source/`: the print version of the label (`label-print.js`) and the scripts that make the pack.

To confirm before ordering: who codes the lot number in the LOT box (inkjet or thermal transfer), quantities, and rolls or sheets. BAC water (03) and NAD+ (08) are 65.0 × 30.2 mm trim (page 69.5 × 34.8 mm) for a standard 10 mL vial, Ø 24 mm: confirm against the real vial.

## Vector / Illustrator files (`vector/`), Rev 4

- `vector/zuma-label-NN-vector.ai` (and the same file as `.pdf`): every label as vector. The bands and lot box are shapes, the logo and stars are their paths, and every letter is converted to outlines (no fonts in the files).
- Page exactly 46 x 23 mm (43 x 20 trim + 1.5 mm bleed); 03 and 08 are 69.53 x 34.77 mm (65.0 x 30.2 trim). Each file has a TrimBox at the cut.
- Checked against the raster art: under 0.15% of pixels differ, all antialiasing on edges.
- The .ai files are PDF-based: Illustrator opens them directly.
- Rebuild: `source/record.cjs` records the label's drawing calls from `label-print.js`; `source/build_pdf.py` writes the PDFs with `source/pdfw.py` (needs the Outfit and IBM Plex Mono TTFs).

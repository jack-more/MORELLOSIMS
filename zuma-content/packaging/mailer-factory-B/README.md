# ZUMA bubble mailer B: factory pack (4 Nov 2026)

The founders' pick ("I fucking love it"): white film, one spot ink (ZUMA Oxblood #6E1C2A). Replaces `../mailer-factory/` (the Oxblood tile-grid mailer). The mailer does not say "peptides".

- Side A (back): the tall ZUMA (190 mm), the crest, zumatides.com, "Tested by lot", the research-use line, the palm shadow. Everything sits below the 44 mm flap line, because the flap closes over the top of this side.
- Side B (front): ZUMA and the crest, the 4 x 6 in label area as a 0.3 mm outline, the research-use line, zumatides.com, and a bamboo stalk with leaves down each edge, outside the label area.
- Shadows: the same ink as a tint, up to 28%. They are kept 2 mm clear of all type and logos. The printer screens them (expected about 65 lpi flexo); judge on the printed proof and drop them if grainy.
- Files: `vector/*.ai` (+ `.pdf`): spot colour ZUMA_Oxblood, type as outlines, 158.4 x 260 mm pages (3 mm bleed) with a TrimBox at 152.4 x 254. `vector/ZUMA-mailer-dieline-layout.ai` shows the flap and fold. `mailer-proof.jpg` simulates the screened print.
- Send `ZUMA-mailer-B-factory-pack.zip` with `QUOTE-REQUEST-Mailer.txt`.
- Rebuild: `source/mailerB.html` (the artwork), `source/extract.cjs` (glyph positions), `source/pack.py` (shadows + spot-colour PDFs), `source/dieline.py`.

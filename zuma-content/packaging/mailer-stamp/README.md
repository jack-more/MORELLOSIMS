# ZUMA mailer stamp (18 Nov 2026): three directions, not chosen yet

For the brown kraft bubble mailers. One ink: ZUMA Oxblood #6E1C2A. 2 in (50.8 mm). It never says "peptides" (same rule as mailer B).

- `stamps-on-kraft.jpg`: all three inked on kraft at the same scale.
- `vector/zuma-stamp-A-round-seal.svg`: 50.8 mm round. The crest and the ZUMA wordmark, zumatides.com round the bottom, a 1.1 mm ring and a 0.45 mm inner ring.
- `vector/zuma-stamp-B-block.svg`: 50.8 x 26 mm. The crest beside the wordmark, zumatides.com under it, a rounded 0.9 mm frame.
- `vector/zuma-stamp-C-crest.svg`: the crest alone, 50.8 mm wide.

The SVGs are the stamp art at 1:1 in mm. Ink is drawn in black and all type is outlines, so the maker needs no fonts. Send them as drawn: the stamp maker mirrors the rubber.
Rubber holds lines down to about 0.3 mm. The crest's petal lines are about 0.29 mm in A and 0.24 mm in B, so ask the maker to proof B's crest, or make it slightly bolder.
Rebuild: `python source/build.py vector source/Outfit-600.ttf`, render the SVGs at 40 px/mm, then `python source/mock.py <renders> stamps-on-kraft.jpg`.

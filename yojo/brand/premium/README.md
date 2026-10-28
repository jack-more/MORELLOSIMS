# Premium pass

Renders from 2026-10-28, based on what you picked from the four direction boards (the debossed tone-on-tone skins, your wordmark, and the chrome head macro) and the references you sent (Laneige, Gezeiten, Pure Honey, Outside-In, salted, goodal, and the molded type on the green tube).

## The renders

| File | What it shows |
|---|---|
| `01-sky.jpg` | Chalk sky, tone on tone |
| `02-rose.jpg` | Chalk rose, tone on tone |
| `03-sage.jpg` | Chalk sage, tone on tone |
| `04-cobalt.jpg` | Deep cobalt, tone on tone |
| `05-hero-black.jpg` | Hero shot on black, with the chrome head as the jewel |
| `06-spec-plate.jpg` | Molded spec plate on the back: GHK-CU / COPPER TRIPEPTIDE-1 / 30 ML |
| `07a-head-hallmark.jpg` | Head-top option A: YO/JO hallmark in raised chrome |
| `07b-head-engraved.jpg` | Head-top option B: small laser-engraved YOJO |
| `08-two-tone.jpg` | Two-tone drop: sky over cobalt |
| `09-frost-rare.jpg` | Rare tier: frosted translucent skin with a chrome token inside |
| `10-lineup.jpg` | Season lineup, each unit on its own color block |
| `11-head-side-stamped.jpg` | YOJO stamped into a smooth band on the side of the head, so it reads from the front |
| `12-head-side-metal-on-metal.jpg` | Side band, metal on metal: mirror YOJO on brushed satin, no fill |
| `13-head-top-metal-on-metal.jpg` | Head top, metal on metal: large mirror YOJO on brushed satin |
| `14-all-metal-grail.jpg` | All-metal top tier: satin metal body, mirror head, YOJO/GHK-CU pressed in |
| `15-head-level-front.jpg` | Fix for 12: head sits level with an even reveal; side band YOJO, metal on metal |
| `16-head-level-above.jpg` | Same, from slightly above |
| `17-head-top-y.jpg` | Y on the head top, mirror on satin, no ring around it |
| `18-head-y-plus-side-band.jpg` | Full head: Y on top plus YOJO on the side band |

The head always seats level: it stops on a rigid shoulder and is keyed to the thread. Render 12 shows it tilted, which is an AI error.

The Y in renders 17 and 18 is a generic sans-serif Y. Production uses the Y from the YOJO wordmark: see `../logo/y-mark/`.

## Palette (screen targets sampled from the renders)

| Name | Skin, lit side | Backdrop | Role |
|---|---|---|---|
| Chalk Sky | #A1D6F6 | #BFE3FA | YOJO Cream core |
| Chalk Rose | #E4AAB9 | #D6A4AF | YOJO JELLY |
| Chalk Sage | #AAC694 | #A5B691 | YOJO POP |
| Cobalt | #1E77F3 | #1E6DDF | Accent and drops |
| Black | #000000 | | Hero shots only |
| Satin chrome | | | The head. Always the only shiny thing in the frame. |

The pastels are chalky: slightly gray, powdery, velvety matte. Cobalt is the one saturated color. Match physical parts to Pantone chips before tooling; these hex values are screen targets only.

## Finish and print rules

1. **No ink on the skin.** All text is molded into the silicone in the same color as the skin. Light and shadow make it readable.
2. **Front:** YOJO above GHK-CU, debossed (pressed in), 0.3–0.5 mm deep.
3. **Back:** spec plate, a rounded rectangle with three lines (GHK-CU / COPPER TRIPEPTIDE-1 / 30 ML).
4. **Head top:** either the YO/JO hallmark (A) or the small engraved YOJO (B). Pick one.
5. **One shiny thing.** The chrome head is the only gloss in any shot. No glossy props or floors, except the black hero.
6. **Tone on tone.** Shoot each skin on a backdrop and plinth in its own color.
7. **Drops are color blocked.** Two tones split on a horizontal line, and the YOJO/GHK-CU stays on the upper color.
8. **Rare tier is a material.** Frosted translucent silicone with an object encased in the wall. The formula is never rarity-gated.

## Notes for production

- The spec plate in the render is a debossed panel with raised letters. Either way works in LSR. Raised letters at 0.3 mm or more hold up better against wear.
- **Frosted rare skin:** encasing a token means two-shot or insert molding. Ask SIMTEC and Rilong (see `SOURCES.md`) about insert-molded LSR.
- **Head A:** the raised chrome hallmark needs either a die-cast or zinc head with PVD, or a metallized plastic head with the letters cut into the mold.
- **Head B:** a laser mark, which is the cheapest option.

## Higgsfield job IDs

| File | Job ID |
|---|---|
| 01-sky | 9598655b-6fe1-49b7-a74e-12ac9be0ae33 |
| 02-rose | 15c57f29-e97b-4fb6-b7aa-63bc83c7c1cf |
| 03-sage | 805a7597-6fb7-416d-b002-148d627b3b3c |
| 04-cobalt | a3b2d958-dc5d-4761-a71a-cb5c6eb87ff4 |
| 05-hero-black | b7ef283e-7e36-4290-8c0d-7d74e14ab880 |
| 06-spec-plate | 54eab0f6-e5e2-498b-9b7c-356f0b962567 |
| 07a-head-hallmark | 94f6ab6b-8707-4bb2-9afb-458ea9a688c9 |
| 07b-head-engraved | e349cd86-3dfc-48f4-8d30-ac4fc53fb999 |
| 08-two-tone | fb103072-a8f4-4723-b085-5c1bca611112 |
| 09-frost-rare | d19afb0f-8197-4279-9216-fb98a6d6430a |
| 10-lineup | fb10c98a-70fc-4cb1-acc9-4698cad39957 |
| 11-head-side-stamped | 385acefb-2a7d-4ae4-ae39-6d798e68c131 |
| 12-head-side-metal-on-metal | 786a7a92-d4d7-41c5-a8de-7e9b3465a76c |
| 13-head-top-metal-on-metal | f3647ddc-66fc-480e-916f-7463062eae03 |
| 14-all-metal-grail | dd3ba176-763d-408b-b402-e7517e035d74 |
| 15-head-level-front | 732d41ff-01ac-427c-96b6-21b1a9037b87 |
| 16-head-level-above | ccb51504-f775-4c04-957c-76d9358e81bd |
| 17-head-top-y | 62fc45d1-dace-4a71-8355-07199db9763c |
| 18-head-y-plus-side-band | 030f7550-41aa-4ed3-9c40-e29872450c4e |

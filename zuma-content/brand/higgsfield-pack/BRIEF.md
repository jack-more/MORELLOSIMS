# ZUMA Higgsfield pack (13 Nov 2026)

For whichever session runs Higgsfield on the Scale plan. Everything here was tested in the ZUMA lab work; follow it and the bag,
vial and words come out right the first time.

## Rules (from the founders)

- **No Higgsfield credits without a founder's explicit go-ahead for that specific generation.** Run `higgsfield generate cost ...` first, tell them the number, wait for yes.
- No crosses or religious symbols (the mood images have them; copy the light, not the symbols).
- No dosing or human-use claims. No people handling vials. Keep any visible research-use line intact.
- Spell every word on the product exactly as given below. Never let the model invent words.

## The references (`refs/`), and how to name them in the prompt

Pass them in this order and refer to them by number in the prompt ("image 3 is ...").

| # | File | What it is | Say in the prompt |
|---|------|------------|-------------------|
| 1 | `mood-1-pale-arch-lab.png` | Founders' mood: pale mission-arch lab, coloured window light | mood only; copy no objects or symbols |
| 2 | `mood-2-90s-lab.jpg` | Founders' mood: 90s researchers, CRTs, glowing arches | mood only; copy no objects or symbols |
| 3 | `bag-1-seethru-over-lab.png` | **The bag, see-through, over a lab: the master bag reference** | the exact bag: see-through sky-blue film, blue Lightbox tiles on the front, palm fronds on the back, background showing through |
| 4 | `bag-2-over-white.png` | The bag over white (its blue at full strength) | the bag's colour |
| 5 | `bag-3-over-stripes.png` | The bag over stripes and a red disc | proof it is see-through: what is behind shows through, tinted blue |
| 6 | `bag-4-over-provence.png` | The bag over a terrace | proof it is see-through |
| 7 | `bag-5-front-print-flat.png` | The flat front print, high resolution | exact layout: tall white ZUMA up the left, "Research peptides, tested by lot", fine copy down the right, Lot / Packed lines |
| 8 | `bag-6-crest-and-address.png` | Crest + address close-up | the address reads exactly "zumatides.com" |
| 9 | `vial-rt3.png` | The 3 mL vial render | clear glass, dark-red flip-off cap, silver crimp |
| 10 | `label-rt3-rev4.png` (or `label-NN-rev4.png`) | The Rev 4 label for that product | spell out its words (below) |

Label words (Rev 4): 01 RT-3 · 10 MG · RETATRUTIDE · METABOLIC RESEARCH. 02 TZ-2. 04 TESAMORELIN. 05 GHK-Cu · 50 MG. 06 MOTS-c.
08 NAD+ · 500 MG (10 mL vial). 09 BPC+TB. 11 SELANK. Check the label file for each; copy its words exactly.

## Settings that worked

- Stills: `gpt_image_2_6`, `--quality high --resolution 2k --aspect_ratio 9:16` (2.75 credits each on our tests).
- Video: make and approve the still first, then `seedance_2_5` with that still as `--start-image`, 1080p, 12 s (about 192 credits). AI video drifts on print and hands; keep hands out or very simple.

## Prompt structure that fixed the errors

Start with a REFERENCE KEY that names every image and what to copy from it, spell the exact words, call the bag SEE-THROUGH and
point at images 3, 5 and 6 as proof, then describe the SCENE. `prompts/` has the full text of the best still (bags backlit on a
line, vials on a bench), the 90s lab version, and an overhead version.

## Check every result before showing it (the five checks)

1. The blue Lightbox reads on the front of the bag (tiles, darker pools).
2. The background shows through the bag.
3. The dark palm fronds read through the front.
4. The white print is crisp and spelled right ("zumatides.com", "Research peptides, tested by lot").
5. The vial label reads with the right words.

Known weak spots: tiny fine print on the bag and the vial's bottom band can come out as texture or slightly garbled.
Fix those in the approved still before it becomes a video frame.

`examples/` shows the best still so far, a close-up with the text right, and the palm check.

ZUMA sells peptides for performance and longevity research: six research peptides in small lots with a published report for every lot. The identity is **Tricolor**: each research area owns three tones of one colour, and every vial, card and page block carries them as three horizontal bands. The brand should feel cool, rich and strong without trying: bold colour on cream, heavy type, nothing fussy. A first-time visitor should know what everything is and where to click. Someone who knows the field should find every number checkable. Everything ZUMA sells is for laboratory research use only, and every product surface says so.

## The four ideas

1. **One colour per research area, with the area named on it.** Blue is metabolic, green is tissue, red-orange is dermal, amber is endocrine. The area's name is printed on its bright band, so nobody has to be told what a colour means. A colour never means anything else: not a section, not a status, not the brand, not a button.
2. **The bands tell you what you're looking at.** Light band: who (ZUMA). Bright band: what (the research area, then the compound). Deep band: the rules (research use, lot, storage). Always in that order, top to bottom.
3. **Pills press. Squares inform.** Anything you can click is round-ended. Anything you only read is square. A visitor learns this in one screen and can trust it everywhere.
4. **The ground changes when the subject changes.** Sections are full-width blocks of paper, sand or ink, with generous space. Nothing on a page is divided by a thin line.

## Voice

Write like a calm expert who doesn't need to sell: short, plain, exact. US English, sentence case, no exclamation marks, no emoji, no slang, no urgency.

- Lead with the compound and the evidence: "BPC-157 · 10 mg. Lot BPC-2610A, report published."
- Name products by compound only (RT-3, BPC-157). No catalogue numbers, no N°, No. or #.
- The positioning line is always "performance and longevity research", in full, naming a field of study. Never shorten it and never present it as something a compound gives.
- Headings say what the section is ("Lot reports", "Save with a set"). No slogans, no rhyming pairs of short sentences.
- Headlines are a few words: "Small lots. True colors." "The collection." "Fresh lots. Every report published."
- Name methods and units exactly: "HPLC · MS", "−20 °C", "10 mg". Use the `·` separator and a true minus sign.
- Say each legal line once per surface, where it applies. Don't repeat disclaimers in every block.
- Button labels are verbs: "Shop the collection", "View", "Add to cart · $54", "Add set". Never "Click here", "Learn more" or "Buy now".

Claims follow one rule: if there is no document to point at, the claim doesn't run.

- **Every product surface carries:** "For laboratory research use only. Not for human or veterinary use."
- **Describe compounds by mechanism only**, then "Studied in … research models." Never describe an effect in people or animals.
- **Never write:** dose or dosing, cycle, stack, results, gains, recovery, benefits, heal, treat, safe, clinically proven, pharmaceutical grade, for human use, before and after, performance, weight loss, muscle.
- **$ZUMA and referrals** are always called a utility, a membership or a loyalty program. Never an investment, never a return, never a price prediction.

## Colour

ZUMA's colour works in two layers. Keep them apart and the whole system reads at a glance.

### Identity: the four research areas

Each area has three tones. Use them only on things that belong to that area: its vials, labels, cards, the hero when it features that area, and the area's swatch.

| Area | Light band | Bright band | Deep band | Compounds |
|---|---|---|---|---|
| Metabolic | `metabolic-light` #A3CEFF | `metabolic-bright` #1F4FD8 | `metabolic-deep` #0B1F5C | RT-3, MOTS-c |
| Tissue | `tissue-light` #ABE9C3 | `tissue-bright` #0E9A5B | `tissue-deep` #0A3B26 | BPC-157, TB-500 |
| Dermal | `dermal-light` #FFB7C5 | `dermal-bright` #FF5A1F | `dermal-deep` #9E1717 | GHK-Cu |
| Endocrine | `endocrine-light` #FFE97A | `endocrine-bright` #F5A300 | `endocrine-deep` #5E3C00 | IPAMORELIN |

- Text on a light band is that area's deep tone. Text on a deep band is white, with the light tone for secondary lines.
- The area's name goes on its bright band, in `.z-area` (20px, weight 800, capitals), above the compound. Never write a line that explains the colours; naming the area on its colour does that.
- Text on a bright band uses the area's `on-…-bright` token and must be display size: 24px and up, or 19px at weight 800. Smaller text on a bright band (tags, chip labels, the lot line) takes the band's action colour instead: `ink`, or `paper` on metabolic.
- Never use an area colour for a section ground, a button, a link, a status or a chart that isn't about that area.
- The area swatch (three bars, light over bright over deep) stands for an area wherever the full bands won't fit: chips, cart lines, tables.

### House: ink, paper, sand, white

Everything that isn't an area is house colour. This is also the colour of every control.

- `paper` is the page. `sand` is the second light ground. `white` is for tiles, panels and fields. `ink` is text, the main button and the dark ground.
- Set text in `ink` on light grounds, with `ink-soft` for secondary text. On `ink`, set text in `paper` with `paper-soft` for secondary text.
- `ink-raised` is a tile on an ink ground.
- `line` is a hairline inside a component (table rows, list dividers). Never use a line to separate sections.
- The token and referral programs are house, not an area: they use ink, paper, sand and white only.

### Contrast

Every text pair named in a token's usage note meets 4.5:1, except the bright bands of tissue (3.6:1) and dermal (3.1:1), which carry display-size text only. Control edges and focus rings meet 3:1 on the ground they sit on.

## The bands

The tricolor block is ZUMA's signature. It's three bands of one area, one above the next, with a `band-gap` (4px) between them so the ground shows through.

| Band | Carries | On a vial | On a product card | In the hero |
|---|---|---|---|---|
| Light | Who | ZUMA | The vial picture | The headline and the main button |
| Bright | What | The area, then the short name, full name and fill | The area, the short name, full name and fills | The area switch, the featured compound's area and name, and its button |
| Deep | The rules | Research use only, lot, fill date, storage | Lot, price and the View button | Research use only |

- Keep the order: light on top, bright in the middle, deep at the bottom.
- Use `band-gap` only inside a tricolor block. Tiles and cards are spaced with `space-4` or `space-6`.
- Put tricolor blocks on `paper`, `sand` or `white`. Never on `ink`: the deep band disappears into it. For the same reason, the section after the hero is always a light ground.
- A band is never a button. If a band holds an action, the action is a pill inside it.

## Interaction: how a visitor knows where to click

### Pills press, squares inform

| Looks like | Means | Examples |
|---|---|---|
| Filled pill | The main action here | Shop the collection, View, Add to cart, Add set, Cart |
| Outlined pill | A second action | Read the label, Menu, Close, Copy, Pay with crypto |
| Pill with a swatch, in a labelled row | A filter or switch | Metabolic · Tissue · Dermal · Endocrine |
| Rounded box (`radius-option`) | A choice you select | 10 mg / 20 mg, One time / Subscribe, the checkout confirmation |
| Underlined text, often with → | A link that goes somewhere | How to read a label →, Report ↗ |
| Square tag | Information only | Report published, In testing, Flagship |
| Dashed square | Not live yet | Example data, Placeholder, Proposal |
| Square tile, band or card | Content | Steps, rules, lot records, the label figure |

- One filled pill per block. If two actions compete, the second one is outlined.
- Every clickable card shows a pill. Never rely on hover to reveal that something is clickable.
- Clickable things are at least `hit-min` (44px) tall.
- Arrows mean movement: → goes to another place on the page or opens a panel, ↗ opens a document or another site.

### Actions on each ground

The filled pill is always whichever of `ink` or `paper` contrasts most with the ground, and outlined pills and chips use the same colour for their edge and label. The ground classes set this for you.

| Ground | Filled pill | Outlined pill and chips (edge and label) | Focus ring |
|---|---|---|---|
| `paper`, `sand`, `white` | `ink`, `paper` label | `ink` | `ink` |
| `ink`, `ink-raised` | `paper`, `ink` label | `paper` | `paper` |
| Any light band | `ink`, `paper` label | `ink` | The area's deep tone |
| Metabolic bright | `paper`, `ink` label | `paper` | White |
| Tissue, dermal bright | `ink`, `paper` label | `ink` | White |
| Endocrine bright | `ink`, `paper` label | `ink` | `endocrine-deep` |
| Any deep band | `paper`, `ink` label | `paper` | White |

### States

- **Hover:** pills rise 2px and take `shadow-pill`; outlined pills fill in; their arrow moves 4px. Clickable cards rise 6px and take `shadow-lift`, and their pill shows its hover state too. Text links thicken their underline from 2px to 4px. Header links draw a 3px underline.
- **Pressed:** pills settle back and shrink to 98%.
- **Focus (keyboard):** a 3px solid ring, 3px outside the element, in the ground's text colour. A clickable card shows the ring around the whole card.
- **Selected:** chips and options fill with the ground's text colour and invert their label.
- **Disabled:** the pill drops to 38% opacity and the cursor says not-allowed. Say why nearby ("Confirm research use to continue").
- **Current section:** the header link for the section in view keeps its underline.

## Layout

### Sections

A page is a run of full-width sections. Each one has a single ground, `space-32` (128px) of padding top and bottom (`space-20` on phones), and opens with a section header.

- **Section header:** a solid square tag naming the section (`tag`, in capitals), the title in `display-l` (h2), and one aside in `ink-soft` to the right on desktop, underneath on phones. Then `space-16` before the content.
- **Grounds alternate.** Two neighbouring sections never share a ground. The home page runs: hero (bands) → paper → sand → paper → sand → paper → sand → ink → sand → paper → photograph → ink footer.
- **White tiles sit on sand.** On paper, use tricolor cards, a table with an ink header, or space alone.
- Inside a section, separate blocks with `space-16` and a sub-header (`display-m` with an aside). Never with a rule.

### Grid and spacing

- Content runs up to `content-max` (1320px) with gutters of `space-4` on phones and `space-10` on desktop.
- Cards sit in a grid: four across for area cards, three for products and sets, two on tablets (`bp-tablet`), one on phones (`bp-phone`). Gaps are `space-6` on desktop and `space-4` on phones.
- Padding inside a band is `space-6` (`space-4` on phones). Running text stops at `measure` (62 characters).
- Spacing comes from the scale only: 4, 8, 12, 16, 24, 32, 40, 48, 64, 80, 128.

### The header

- A thin `ink` bar on top carries the research-use line. Under it, on `paper`: the logo, the section links in `button` type, and the Cart pill with its count.
- At `bp-nav` (1100px) and below, the links fold into an outlined Menu pill; the menu opens under the header as large links with arrows.
- The header sticks to the top and takes `shadow-header` once the page scrolls.

### Panels

- The product drawer and the cart slide in from the right on `paper`, with `shadow-panel` and the `scrim` behind. Each opens with a bar holding the logo, a title and an outlined Close pill.
- The product drawer is a tricolor block of the compound's area: the vial on the light band, the name on the bright band, the options on paper, the research-use line and lot record on the deep band.
- The cart is house colours only: items on paper, the total on sand, checkout on ink.

## Type

Two families, both on Google Fonts. Load Schibsted Grotesk at 500 to 900 and IBM Plex Mono at 500 and 600.

- **Schibsted Grotesk** (`display`) carries everything people read: `giant` and `display-xl` once per page in the hero, `display-l` for section titles, `display-m` for compound and set names, `title` for tiles and steps, `lead` under headlines, `body` for text, `small` for notes, `kicker` for eyebrows, `button` for pills and header links, `chip` for chips.
- **IBM Plex Mono** (`mono`) is the record: `data` for prices, lots, dates and balances; `tag` for square tags.
- Nothing is lighter than 500. Text under 16px is 600 or heavier. Headlines are 900 with tight tracking.
- Capitals are for `kicker`, `button` and `tag` only. Everything else is sentence case. Keep the lowercase that carries meaning in compound names (GHK-Cu, MOTS-c).
- Type sizes step down on phones as each style's usage note says.

## Logo

The final logo is still being chosen in the ZUMA Logo Lab. Until then the site uses a placeholder: ZUMA in Schibsted Grotesk 800 with a square dot (see `Logos`).

- The logo lives in one place, the logo slot (`<symbol id="zuma-logo">`), and every page and label draws from it, so changing it once changes it everywhere.
- On light grounds it's `ink`; on `ink` and deep bands it's `paper`. The dot takes the bright tone of the area in view (in the header, the area the hero is featuring).
- Give it clear space equal to its own height on every side. Never stretch, outline, add effects to it or set it in live type.

## The vial and label

- A clear 10 ml serum vial, a white freeze-dried cake, a silver crimp and a cap in the area's deep tone.
- The label wraps all the way around as three bands. Front: ZUMA (light); the research area, then the short name, full name and fill (bright); "Research use only · Not for human or veterinary use" (deep). Left side: the lot record and a code that opens the lot report.
- Lot and fill date are printed at fill. Everything else is fixed per compound.
- See `Vial` for the renders and `Label` for the label anatomy.

## Packaging

- The Collection: a white board box, a fitted tray holding all six vials, and a lid printed with the four areas in their three bands and "For laboratory research use only".
- Single vials ship in a white sleeve printed with the vial's own bands.

## Imagery and 3D

- Product imagery is the 3D render of the real vial only (see `Product` and `Photography`). Never use a generated vial with an invented label.
- Vials sit on their own area's light tone, or on `sand` or `paper` when several areas share a picture. Never on another area's colour.
- On the site the vials are live 3D where WebGL runs: drag to spin, hover a card to turn it to the lot side. The still renders are the posters and the fallback.
- Never show people, faces, hands, bodies, syringes, pills or capsules, medical crosses, or before-and-after images. No beach clichés: no palms, waves, suns, surfboards or lifeguard towers in artwork.

## Motion

- Hover and press: 180ms ease. Cards: 220ms. Panels: 380ms ease-out. The hero's change of area: 500ms.
- Nothing moves on its own. The vial turns when it's dragged or its card is hovered, and settles back.
- With reduced motion on, nothing slides or rises: states change instantly.

## $ZUMA and referrals

Both are proposals until legal review, and the design says so.

- The token section sits on `ink` and uses house colours only. Its header carries a dashed "Proposal" tag.
- Anything not live yet is dashed: the buyback step, example dashboard data, placeholder prices and lots.
- Referral levels are drawn to scale in `ink` on `white` (see `Ladder`). Rewards are "a loyalty program for referral rewards", never income.
- Every referral surface repeats the sharing rule: posts must keep "For laboratory research use only. Not for human or veterinary use." and never suggest use in people. Paid referrers disclose the relationship.

## Compliance checklist

Run this on every page, post and package before it ships.

- [ ] "For laboratory research use only. Not for human or veterinary use." is on every product surface: the header bar, the collection, the product drawer, the cart, the label, the box and the footer.
- [ ] Checkout asks the buyer to confirm research use and that they are 21 or older before it continues.
- [ ] No never-words (see Voice). The site build fails if one appears.
- [ ] Compound descriptions are mechanism-only and end "Studied in … research models."
- [ ] No people, bodies, syringes, pills, capsules, medical crosses or before-and-after imagery.
- [ ] Research areas are called fields of study, never uses.
- [ ] Token and referral copy says utility or loyalty program, never investment, and carries "subject to legal review".
- [ ] Placeholders (prices, lots, reports, example data) are marked with a dashed tag.

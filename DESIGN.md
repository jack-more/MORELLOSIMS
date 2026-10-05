# DESIGN.md — Morello Sims

The one design system for everything public: the site, pick cards, posts.
Read this before building or changing any screen. If a choice isn't covered
here, match the homepage (`index.html`), never invent a new look.

Brand guide (visual): https://claude.ai/artifact/2QWoeSCAuJzkSGTBkP6g7b
Owner references: `~/Desktop/sport-info-DESIGN/reference/brand-guide-2026-10/`
(guidance only — never published).

## The idea

**Research that leads somewhere.** The research is the path; the payoff is the
view. Every image looks *through* something (trees, leaves, stone) *out to*
something big and calm (sea, mountains, sky). The work is precise; the feeling
is a clear day by the water.

## Voice

Calm, certain, specific. Short sentences, real numbers from the ledger, no hype.

- Say: "The sim found 29.6 units last season." Not: "🔥 MAX LOCK 🔥".
- Post losses plainly: "Last night: 4–6, −1.9u. A bad one. It's on the ledger."
- Abundance is a quiet line, never a promise: "Good things are on the board tonight."
- Never: guarantees, "locks", emoji, model-room jargon (MOJO, C10, $PP) on public surfaces.
- Every number comes from `ledger/nba/<season>.json`. 1u = 25 $PP (owner decision).

## Color

| Token | Hex | Use |
|---|---|---|
| paper | `#F4F1EC` | page ground |
| paper-2 | `#FBF9F6` | alternate section ground, cards |
| ink | `#0F1D26` | text, primary buttons, dark bands |
| ink-2 | `#4A5864` | secondary text (4.5:1 on paper) |
| rule | `#DCD5CB` | hairlines, card borders |
| green | `#17734F` | wins, accents, numerals, links on hover |
| loss | `#E9A08F` | losing nights (lighter than green — never hue alone) |
| sky | `#4994E6` / hero top `#5C9FDF→#6DAAE3` | hero ground (ink text on it) |
| deep water | `#1D3854` | research cards, favicon |

No black, no neon, no grey grounds, no gradient washes (the only gradient is
the hero's sky, which matches the photo).

## Type

- **Display — Instrument Serif** (400 only): headlines, big numbers, the wordmark.
  `h1` clamp(52px, 7.6vw, 112px), `h2` clamp(40px, 4.4vw, 64px), line-height ≈1, letter-spacing −1px.
- **Text — Geist** 400/500/600: everything you read. Body 16–20px, line-height 1.5–1.6.
- **Data — Geist Mono**: eyebrows, step numbers, lines and times. 12–14px, uppercase, tracked.
- Never Inter, Roboto, Arial for brand surfaces. Never bold the serif.

## Logo

**Wordmark only: "Morello Sims" in Instrument Serif.** No icon until a real one is
commissioned (Higgsfield or a designer). Do not draw logos, icons or illustrations
in SVG by hand. Favicon = serif "M" on deep water.

## Imagery

Our own art only (Higgsfield), commissioned from the references:
- Always: a framed view out to water or mountains, high midday sun, sunlit greens
  and deep blue together, calm, no one in frame.
- Never: night, neon, crowds, cash, champagne, grey cities, stock-photo bettors.
- **Stadium art**: every arena drawn true to the real building (from a licensed
  reference photo logged in `reference/SOURCES.md`), set in the brand landscape —
  reached by a path through green, water and sky beyond.
- Plans = three stones (rough → emerald → diamond), used as art, not labels.

## Layout

- Container 1200px, 24px side padding; sections 110–120px vertical padding.
- Grids collapse with `repeat(auto-fit, minmax(min(Npx, 100%), 1fr))`; every page
  works at 375px with no sideways scroll.
- Hairlines (`1px solid rule`) separate items; no left-border cards, no drop-shadow stacks.
- Radius: buttons 999px, cards 18–22px, small chips 3–4px.

## Components

- **Primary button**: ink pill, paper text, ≥44px tall; hover → green. One primary
  action per section; the page repeats the same one ("Get tonight's picks").
- **Plan card**: paper-2, 1px rule, 22px radius, stone art, name, serif price,
  one line, one button. The featured plan is inverted (ink ground).
- **Proof strip**: ink band, four serif numbers with small labels.
- **Research cards** (pick card, game report): read in one pass — pick → why →
  game → receipt. Team color lives inside; the frame is always the brand.
- **FAQ**: `<details>` rows with hairlines, "+/–" marker.

## Sales rules

- First screen: the offer in one sentence, one button, proof one scroll away.
- Prices and what each includes are always visible on the page, never only in a modal.
- Answer the doubts on the page: wins every night? (no), what's a unit, how picks
  arrive, does it renew (no — one-time), not a guarantee, 21+, 1-800-GAMBLER.
- Never claim a feature that isn't live (e.g. Telegram alerts before the channel exists).

## Before you ship

1. `python3 scripts/check_site_js.py` passes (also runs on every push).
2. Load the page at 375px and 1440px: no overlap, no sideways scroll, no console errors.
3. Every number on the page traces to the ledger JSON.

# YOJO Wobble: custom packaging development brief

Send this, with the images in `brief-img/`, to packaging developers. Get an NDA signed before sending.

---

## The product

YOJO is a US skincare brand. The first product is a GHK-Cu copper peptide cream, 30 ml, sold mainly on TikTok Shop. We need a partner to engineer, prototype, tool and manufacture a custom package.

**First order:** 3,000 units. **Scale:** 10,000+ per year, plus refill cups.

## What it is

A weighted egg-shaped bottle, about Ø68 × 110 mm, that wobbles and rights itself. It has a satin-silver knurled press head that screws down flush to lock.

| Image | Shows |
|---|---|
| `brief-img/01-locked-vs-open.jpg` | Locked (head flush on the egg) and open (head raised on its thread) |
| `brief-img/02-twist-macro.jpg` | Twisting the knurled head up to unlock |
| `brief-img/03-press-side-slot.jpg` | Pressing the head; cream leaves a slot on the side of the head |
| `brief-img/04-locked-lineup.jpg` | Color range, all locked |
| `brief-img/05-carton-locked.jpg` | Six-pack gift carton |

These are concept renders, not engineering drawings. A cross-section and part list are in `build-spec/index.html`.

## Parts

| Part | Requirement |
|---|---|
| Press head | Ø about 36 mm flat disc, deep diamond knurl on the rim, dispensing slot on the side. ABS or PP, satin-silver PVD with UV hardcoat. |
| Lock sleeve and collar | The mechanism below. Satin-silver PVD visible surfaces. |
| Airless pump | 0.2 ml dose. **Metal-free fluid path**, spring included. Pump stays in the bottle. |
| Refill cup | 30 ml PP cup with PE follower piston and foil seal. The customer replaces only the cup. |
| Inner shell | Rigid PP or ABS egg with a threaded neck and a pocket for the weight. |
| Weight | Steel or zinc, about 50–80 g, tuned so the egg rights itself. Bottom curve radius ≥ 40 mm. |
| Silicone skin | Platinum-cure LSR, Shore 30–40A, soft-touch, logo debossed in the tool, removable for washing. 4–5 colors. |

## The lock mechanism (custom)

1. The whole pump rides on a threaded sleeve inside the collar.
2. The press head is keyed to the sleeve with vertical splines, so turning the head turns the sleeve, but the head can still slide down to pump.
3. **Twist clockwise about one turn:** head, pump and refill cup screw down together. Nothing moves relative to the pump, so **no cream is dispensed when locking**. The head lands flush on top of the egg.
4. **Locked:** the head rests on a **rigid** stop with zero gap, so it can't be pressed. The side slot sits inside the collar, sealed from lint and drips.
5. **Twist counter-clockwise:** the head rises about 6 mm and clicks into the open position, ready to pump.
6. Click detents at both ends. Pressing the head to pump must never back-drive the thread.
7. The twist should feel smooth and satisfying. The knurl is the grip.

## Hard rules

- Nothing metal in contact with the cream. GHK-Cu reacts with aluminum and steel.
- Airless: no air back into the cup after dispensing.
- Compatible with a cream of pH about 5–7 containing GHK-Cu. We will run a 12-week stability test at 40 °C in every wet part.
- YOJO owns all molds and tooling, in writing.

## What we're asking you for

1. Feedback on whether the mechanism can be made and how you'd simplify it
2. CAD and a development plan
3. Prototypes: appearance models and working mechanism samples
4. Tooling cost per part, and who owns the tools
5. Unit price for the full assembly at 3,000 and 10,000, and for refill cups alone at 10,000 and 50,000
6. Lead times: development, tooling, first production
7. MOQ per color for the silicone skin
8. Your experience with custom airless or dispensing mechanisms, with examples
9. Your factory address, business license and ISO certificates

## Before sending

- Get an NDA signed.
- Talk to a patent attorney about a US design patent, and possibly a utility patent for the lock, **before** showing this widely. Public disclosure can start a filing clock.

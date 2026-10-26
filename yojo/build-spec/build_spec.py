import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

# ---------- shared geometry (local coords, 4 px = 1 mm, x=0 is the centre line) ----------
SKIN = "M -60 80 C -112 108 -140 220 -136 320 C -132 400 -80 448 0 448 C 80 448 132 400 136 320 C 140 220 112 108 60 80 Z"
SHELL = "M -48 96 C -96 122 -122 222 -120 320 C -116 390 -70 432 0 432 C 70 432 116 390 120 320 C 122 222 96 122 48 96 Z"
CAVITY = "M -42 104 C -88 130 -114 224 -112 320 C -108 384 -64 424 0 424 C 64 424 108 384 112 320 C 114 224 88 130 42 104 Z"
WEIGHT = "M -88 386 L 88 386 C 80 406 50 424 0 424 C -50 424 -80 406 -88 386 Z"


def teeth(x_base, x_tip, y0, y1, step=4):
    pts = []
    y = y0
    flip = False
    while y <= y1:
        pts.append(f"{x_tip if flip else x_base},{y}")
        flip = not flip
        y += step / 2
    return " ".join(pts)


def body(full=True):
    """Skin, shell, cavity, refill cup, piston, weight. full=False skips parts below the head detail."""
    s = []
    s.append(f'<path d="{SKIN}" fill="var(--skin)" stroke="var(--ink)" stroke-width="1.2"/>')
    s.append(f'<path d="{SHELL}" fill="var(--shell)" stroke="var(--ink)" stroke-width="0.8"/>')
    s.append(f'<path d="{CAVITY}" fill="var(--void)" stroke="var(--ink)" stroke-width="0.6"/>')
    if full:
        s.append(f'<path d="{WEIGHT}" fill="var(--steel)" stroke="var(--ink)" stroke-width="1"/>')
    # refill cup
    s.append('<rect x="-52" y="124" width="104" height="252" fill="var(--pp)" stroke="var(--ink)" stroke-width="1"/>')
    s.append('<rect x="-48" y="128" width="96" height="224" fill="var(--cream)"/>')
    if full:
        s.append('<rect x="-48" y="352" width="96" height="14" fill="var(--piston)" stroke="var(--ink)" stroke-width="0.8"/>')
        s.append('<rect x="-48" y="366" width="96" height="6" fill="var(--void)"/>')
        s.append('<rect x="-5" y="371" width="10" height="6" fill="var(--void)"/>')
    return "\n".join(s)


def head(dy, spring_top):
    """Collar (fixed) + pump (fixed) + moving head/stem shifted down by dy."""
    s = []
    # collar walls with outer lock thread
    s.append('<rect x="-58" y="56" width="10" height="48" fill="var(--alu)" stroke="var(--ink)" stroke-width="0.8"/>')
    s.append('<rect x="48" y="56" width="10" height="48" fill="var(--alu)" stroke="var(--ink)" stroke-width="0.8"/>')
    s.append('<rect x="-48" y="56" width="30" height="8" fill="var(--alu)" stroke="var(--ink)" stroke-width="0.8"/>')
    s.append('<rect x="18" y="56" width="30" height="8" fill="var(--alu)" stroke="var(--ink)" stroke-width="0.8"/>')
    # pump engine
    s.append('<rect x="-24" y="100" width="48" height="30" rx="3" fill="var(--pp)" stroke="var(--ink)" stroke-width="1"/>')
    s.append('<circle cx="0" cy="124" r="4" fill="var(--ink)"/>')
    # spring
    pts = []
    y = spring_top
    i = 0
    n = 8
    step = (100 - spring_top) / n
    while i <= n:
        pts.append(f"{-16 if i % 2 == 0 else 16},{spring_top + i * step:.1f}")
        i += 1
    s.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="var(--ink)" stroke-width="1.2"/>')
    # moving part: stem + disc + skirt
    g = [f'<g transform="translate(0 {dy})">']
    g.append('<rect x="-6" y="30" width="12" height="74" fill="var(--pp)" stroke="var(--ink)" stroke-width="0.8"/>')
    g.append('<rect x="-2" y="20" width="4" height="80" fill="var(--cream)"/>')
    g.append('<rect x="-74" y="10" width="148" height="22" rx="2" fill="var(--alu)" stroke="var(--ink)" stroke-width="1.2"/>')
    g.append('<rect x="0" y="18" width="74" height="5" fill="var(--cream)"/>')
    # knurl hatching on disc rim
    for x in (-73, -70, -67, 67, 70, 73):
        g.append(f'<line x1="{x}" y1="11" x2="{x}" y2="31" stroke="var(--ink)" stroke-width="0.6"/>')
    g.append('<rect x="-74" y="32" width="10" height="16" fill="var(--alu)" stroke="var(--ink)" stroke-width="0.8"/>')
    g.append('<rect x="64" y="32" width="10" height="16" fill="var(--alu)" stroke="var(--ink)" stroke-width="0.8"/>')
    g.append('<rect x="-64" y="42" width="12" height="6" fill="var(--alu)" stroke="var(--ink)" stroke-width="0.8"/>')
    g.append('<rect x="52" y="42" width="12" height="6" fill="var(--alu)" stroke="var(--ink)" stroke-width="0.8"/>')
    g.append('</g>')
    s.extend(g)
    return "\n".join(s)


def label(x, y, text, px, py, anchor):
    lx = x + 6 if anchor == "end" else x - 6
    return (f'<line x1="{lx}" y1="{y - 4}" x2="{px}" y2="{py}" stroke="var(--ink)" stroke-width="0.7"/>'
            f'<circle cx="{px}" cy="{py}" r="2.2" fill="var(--ink)"/>'
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" class="lbl">{text}</text>')


# ---------- figure 1: full section, unlocked ----------
OX, OY = 380, 24
def g(x, y):
    return OX + x, OY + y

f1 = [f'<svg viewBox="0 0 760 520" role="img" aria-label="Cross-section of the YOJO Wobble in the unlocked position, showing the press head, twist-lock lugs, airless pump, refill cup, follower piston, rigid inner shell, silicone skin and weight." class="dwg">']
f1.append(f'<g transform="translate({OX} {OY})">')
f1.append(body(True))
f1.append(head(0, 68))
# cream leaving the side slot
f1.append('<path d="M 74 19 C 84 17 92 20 96 26 C 99 31 94 35 89 33 C 85 31 86 25 80 23 Z" fill="var(--cream)" stroke="var(--ink)" stroke-width="0.8"/>')
f1.append('</g>')
left = [
    ("Press head", 36, -74, 20),
    ("Lock lug", 82, -58, 46),
    ("Airless pump", 134, -24, 114),
    ("Refill cup · 30 ml", 238, -52, 220),
    ("Follower piston", 378, -48, 359),
    ("Steel weight", 420, -60, 402),
]
for t, y, px, py in left:
    gx, gy = g(px, py)
    f1.append(label(226, y, t, gx, gy, "end"))
right = [
    ("Side outlet slot", 40, 92, 26),
    ("Return spring", 100, 16, 84),
    ("GHK-Cu cream", 200, 30, 190),
    ("Rigid inner shell", 286, 117, 262),
    ("Silicone skin", 358, 128, 342),
]
for t, y, px, py in right:
    gx, gy = g(px, py)
    f1.append(label(534, y, t, gx, gy, "start"))
# dimensions
y_dim = OY + 470
f1.append(f'<line x1="{OX-136}" y1="{y_dim}" x2="{OX+136}" y2="{y_dim}" class="dim"/>')
f1.append(f'<line x1="{OX-136}" y1="{y_dim-6}" x2="{OX-136}" y2="{y_dim+6}" class="dim"/>')
f1.append(f'<line x1="{OX+136}" y1="{y_dim-6}" x2="{OX+136}" y2="{y_dim+6}" class="dim"/>')
f1.append(f'<text x="{OX}" y="{y_dim+18}" text-anchor="middle" class="dimt">Ø 68</text>')
x_dim = 720
f1.append(f'<line x1="{x_dim}" y1="{OY+10}" x2="{x_dim}" y2="{OY+448}" class="dim"/>')
f1.append(f'<line x1="{x_dim-6}" y1="{OY+10}" x2="{x_dim+6}" y2="{OY+10}" class="dim"/>')
f1.append(f'<line x1="{x_dim-6}" y1="{OY+448}" x2="{x_dim+6}" y2="{OY+448}" class="dim"/>')
f1.append(f'<text x="{x_dim-8}" y="{OY+229}" text-anchor="end" class="dimt">110</text>')
f1.append('</svg>')
FIG1 = "\n".join(f1)

# ---------- figure 2: twist lock, collar rim unrolled ----------
f2 = ['<svg viewBox="0 0 840 300" role="img" aria-label="Collar rim unrolled flat. Unlocked: the two lugs under the head sit over the two notches in the rim, so the head can press down 4 mm. Locked: after a quarter turn the lugs rest on the solid rim past a click detent, so the head cannot go down." class="dwg">']
f2.append('<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="var(--signal)"/></marker></defs>')
NOTCH = (45, 225)
for ox, locked, title in ((30, False, "UNLOCKED"), (450, True, "LOCKED")):
    f2.append(f'<text x="{ox+180}" y="24" text-anchor="middle" class="ttl">{title}</text>')
    # head skirt band
    f2.append(f'<rect x="{ox}" y="60" width="360" height="34" fill="var(--alu)" stroke="var(--ink)" stroke-width="1.2"/>')
    f2.append(f'<text x="{ox+8}" y="82" class="lbl">head</text>')
    lugs = (135, 315) if locked else NOTCH
    for d in lugs:
        f2.append(f'<rect x="{ox+d-10}" y="94" width="20" height="16" fill="var(--alu)" stroke="var(--ink)" stroke-width="1.2"/>')
    # collar rim with two notches and two click bumps
    pts = [f"{ox},190", f"{ox},140"]
    for d in NOTCH:
        pts += [f"{ox+d-14},140", f"{ox+d-14},174", f"{ox+d+14},174", f"{ox+d+14},140"]
        bx = ox + d + 72
        pts += [f"{bx-6},140", f"{bx},134", f"{bx+6},140"]
    pts += [f"{ox+360},140", f"{ox+360},190"]
    f2.append(f'<polygon points="{" ".join(pts)}" fill="var(--alu)" stroke="var(--ink)" stroke-width="1.2"/>')
    f2.append(f'<text x="{ox+8}" y="184" class="lbl">collar</text>')
    for d in (0, 90, 180, 270, 360):
        f2.append(f'<line x1="{ox+d}" y1="190" x2="{ox+d}" y2="196" stroke="var(--mute)" stroke-width="1"/>')
        f2.append(f'<text x="{ox+d}" y="210" text-anchor="middle" class="dimt">{d}°</text>')
    if locked:
        f2.append(f'<path d="M {ox+45} 46 L {ox+128} 46" fill="none" stroke="var(--signal)" stroke-width="2" marker-end="url(#ah)"/>')
        f2.append(f'<text x="{ox+140}" y="50" class="ann">¼ turn, click</text>')
        for d in lugs:
            cx, cy = ox + d, 125
            f2.append(f'<line x1="{cx-7}" y1="{cy-7}" x2="{cx+7}" y2="{cy+7}" stroke="var(--signal)" stroke-width="2.4"/>')
            f2.append(f'<line x1="{cx-7}" y1="{cy+7}" x2="{cx+7}" y2="{cy-7}" stroke="var(--signal)" stroke-width="2.4"/>')
        f2.append(f'<text x="{ox+180}" y="240" text-anchor="middle" class="ann">Lugs rest on the solid rim.</text>')
        f2.append(f'<text x="{ox+180}" y="258" text-anchor="middle" class="ann">The head cannot go down.</text>')
    else:
        for d in lugs:
            f2.append(f'<line x1="{ox+d}" y1="114" x2="{ox+d}" y2="166" stroke="var(--signal)" stroke-width="2" marker-end="url(#ah)"/>')
        f2.append(f'<text x="{ox+90}" y="128" class="lbl">notch</text>')
        f2.append(f'<text x="{ox+180}" y="240" text-anchor="middle" class="ann">Lugs line up with the notches.</text>')
        f2.append(f'<text x="{ox+180}" y="258" text-anchor="middle" class="ann">Press: the head travels 4 mm.</text>')
f2.append('<text x="420" y="290" text-anchor="middle" class="dimt">collar rim unrolled flat · not to scale</text>')
f2.append('</svg>')
FIG2 = "\n".join(f2)

# ---------- figure 3: why it rocks back up ----------
f3 = ['<svg viewBox="0 0 640 240" role="img" aria-label="Self-righting rule: the balance point G must sit below the centre C of the curved bottom. When tipped, the weight swings back under C and the egg rocks upright." class="dwg">']
f3.append('<line x1="20" y1="214" x2="620" y2="214" stroke="var(--ink)" stroke-width="1"/>')
# upright egg bottom arc
for cx, tilt, cap in ((170, 0, "Upright"), (470, 18, "Tipped")):
    f3.append(f'<g transform="rotate({tilt} {cx} 94)">')
    f3.append(f'<path d="M {cx-110} 60 C {cx-120} 150 {cx-80} 214 {cx} 214 C {cx+80} 214 {cx+120} 150 {cx+110} 60" fill="var(--skin)" stroke="var(--ink)" stroke-width="1.2"/>')
    f3.append(f'<path d="M {cx-60} 196 Q {cx} 222 {cx+60} 196 L {cx+56} 182 Q {cx} 204 {cx-56} 182 Z" fill="var(--steel)" stroke="var(--ink)" stroke-width="0.8"/>')
    f3.append(f'<line x1="{cx}" y1="60" x2="{cx}" y2="214" stroke="var(--ink)" stroke-width="0.6" stroke-dasharray="4 4"/>')
    f3.append(f'<circle cx="{cx}" cy="94" r="5" fill="var(--void)" stroke="var(--ink)" stroke-width="1.2"/>')
    f3.append(f'<text x="{cx+10}" y="98" class="lbl">C</text>')
    f3.append(f'<circle cx="{cx}" cy="168" r="6" fill="var(--signal)"/>')
    f3.append(f'<text x="{cx+12}" y="172" class="lbl">G</text>')
    f3.append('</g>')
    if tilt:
        f3.append(f'<line x1="{cx}" y1="94" x2="{cx}" y2="214" stroke="var(--mute)" stroke-width="1" stroke-dasharray="2 4"/>')
    f3.append(f'<text x="{cx}" y="236" text-anchor="middle" class="ann">{cap}</text>')
# restoring arrow on tipped egg
f3.append('<path d="M 540 196 Q 560 160 520 132" fill="none" stroke="var(--signal)" stroke-width="2" marker-end="url(#ah3)"/>')
f3.insert(1, '<defs><marker id="ah3" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="var(--signal)"/></marker></defs>')
f3.append('<text x="566" y="150" class="ann">rocks back</text>')
f3.append('</svg>')
FIG3 = "\n".join(f3)

HTML = f"""<title>YOJO Wobble Build Spec</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@125,700;125,800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: an engineering drawing sheet. Title block, then figures with captions, then tables a factory can quote from. */
:root {{
  --paper: #eef5fb;
  --sheet: #f8fbfe;
  --ink: #14263b;
  --mute: #52657a;
  --rule: #c9d9e8;
  --skin: #8cc3ec;
  --shell: #dfe8f1;
  --void: #f8fbfe;
  --pp: #f2f4f6;
  --alu: #c3cbd3;
  --steel: #9aa6b2;
  --piston: #6e7f90;
  --cream: #bfe0f6;
  --signal: #d9407a;
  --display: "Archivo", "Arial Black", system-ui, sans-serif;
  --body: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --paper: #0d1824; --sheet: #122130; --ink: #e2edf7; --mute: #9db1c4; --rule: #2a3f54;
    --skin: #3d7cb3; --shell: #2a3c4f; --void: #122130; --pp: #31465a; --alu: #7f8c99;
    --steel: #6b7886; --piston: #a3b2c1; --cream: #5a93bf; --signal: #f06d9c; color-scheme: dark;
  }}
}}
:root[data-theme="dark"] {{
  --paper: #0d1824; --sheet: #122130; --ink: #e2edf7; --mute: #9db1c4; --rule: #2a3f54;
  --skin: #3d7cb3; --shell: #2a3c4f; --void: #122130; --pp: #31465a; --alu: #7f8c99;
  --steel: #6b7886; --piston: #a3b2c1; --cream: #5a93bf; --signal: #f06d9c; color-scheme: dark;
}}
* {{ box-sizing: border-box; }}
img {{ display: block; max-width: 100%; height: auto; }}
body {{ background: var(--paper); color: var(--ink); font: 400 16px/1.6 var(--body); }}
.wrap {{ max-width: 980px; margin: 0 auto; padding-block: 32px 72px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 40px; }}
h1 {{ font: 800 clamp(34px, 6vw, 56px)/1 var(--display); letter-spacing: -0.01em; margin: 0; text-wrap: balance; }}
h2 {{ font: 700 22px/1.2 var(--display); margin: 0; text-wrap: balance; }}
p {{ margin: 0; max-width: 65ch; }}
.mono, .eyebrow, th, .tb dt {{ font-family: var(--mono); }}
.eyebrow {{ font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--mute); }}
header {{ display: grid; gap: 16px; }}
.lede {{ font-size: 18px; color: var(--mute); }}
.tb {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); border: 1.5px solid var(--ink); background: var(--sheet); margin: 0; }}
.tb div {{ padding: 10px 12px; border-right: 1px solid var(--rule); border-bottom: 1px solid var(--rule); min-width: 0; }}
.tb dt {{ font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--mute); }}
.tb dd {{ margin: 2px 0 0; font-weight: 600; }}
section {{ display: grid; gap: 16px; }}
figure {{ margin: 0; background: var(--sheet); border: 1px solid var(--rule); padding: 16px; display: grid; gap: 12px; }}
.scroll {{ overflow-x: auto; }}
.dwg {{ display: block; width: 100%; min-width: 560px; height: auto; }}
.dwg .lbl {{ font: 500 13px var(--mono); fill: var(--ink); }}
.dwg .ann {{ font: 500 13px var(--mono); fill: var(--signal); }}
.dwg .ttl {{ font: 700 14px var(--mono); letter-spacing: 0.14em; fill: var(--ink); }}
.dwg .dim {{ stroke: var(--mute); stroke-width: 1; }}
.dwg .dimt {{ font: 500 12px var(--mono); fill: var(--mute); }}
figcaption {{ font-size: 14px; color: var(--mute); max-width: 75ch; }}
figcaption b {{ color: var(--ink); font-weight: 600; }}
.photos {{ display: grid; grid-template-columns: 1.6fr 1fr; gap: 16px; }}
.photos figure {{ padding: 0; overflow: hidden; }}
.photos img {{ display: block; width: 100%; height: 100%; object-fit: cover; }}
.photos figcaption {{ padding: 0 14px 14px; }}
.steps {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 16px; }}
.step {{ border-top: 2px solid var(--ink); padding-top: 10px; display: grid; gap: 6px; min-width: 0; }}
.step h3 {{ font: 600 16px/1.3 var(--body); margin: 0; }}
.step p {{ font-size: 15px; color: var(--mute); }}
ol.seq {{ margin: 0; padding-left: 1.4em; display: grid; gap: 6px; max-width: 70ch; }}
.tablewrap {{ overflow-x: auto; border: 1px solid var(--rule); background: var(--sheet); }}
table {{ border-collapse: collapse; width: 100%; min-width: 640px; font-size: 14px; }}
th {{ text-align: left; font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--mute); font-weight: 500; padding: 10px 12px; border-bottom: 1.5px solid var(--ink); }}
td {{ padding: 10px 12px; border-bottom: 1px solid var(--rule); vertical-align: top; }}
td.num, td .num {{ font-family: var(--mono); font-variant-numeric: tabular-nums; }}
.tag {{ display: inline-block; font: 500 11px var(--mono); letter-spacing: 0.06em; padding: 2px 7px; border: 1px solid var(--ink); white-space: nowrap; }}
.tag.custom {{ background: var(--ink); color: var(--sheet); }}
.tag.wet {{ border-color: var(--signal); color: var(--signal); }}
.note {{ border-left: 3px solid var(--signal); padding: 4px 0 4px 14px; max-width: 70ch; }}
.note p + p {{ margin-top: 8px; }}
@media (max-width: 640px) {{ .photos {{ grid-template-columns: 1fr; }} }}
</style>

<div class="wrap">
  <header>
    <span class="eyebrow">YOJO · GHK-Cu copper peptide cream</span>
    <h1>Wobble build spec</h1>
    <p class="lede">How the egg bottle goes together: a weighted silicone egg with a knurled silver press head that screws down to lock and an airless refill cup inside.</p>
    <dl class="tb">
      <div><dt>Part</dt><dd>YOJO Wobble 30 ml</dd></div>
      <div><dt>Rev</dt><dd class="mono">A · concept</dd></div>
      <div><dt>Units</dt><dd class="mono">mm · g · ml</dd></div>
      <div><dt>Status</dt><dd>For first samples</dd></div>
    </dl>
  </header>

  <div class="photos">
    <figure><img src="img/carton.jpg" alt="Six YOJO egg bottles in two pinks, two sky blues, cobalt and green standing in an open brushed-aluminum egg-carton tin.">
      <figcaption><b>Six-pack carton.</b> The look we are building toward.</figcaption></figure>
    <figure><img src="img/press.jpg" alt="A finger presses the knurled silver head of a YOJO egg and a ribbon of pale blue cream comes out of the slot on the side of the head onto a fingertip.">
      <figcaption><b>Press to dispense.</b> Cream leaves through the slot on the side of the head.</figcaption></figure>
  </div>

  <section>
    <span class="eyebrow">Fig. 1 · section, unlocked · 4 px = 1 mm</span>
    <h2>What's inside</h2>
    <figure><div class="scroll">{FIG1}</div>
      <figcaption><b>Everything that touches cream is plastic.</b> The refill cup, piston, pump and the channel through the head are PP or PE. The silver disc and collar are metallized plastic and sit outside the fluid path. Copper peptide reacts with bare aluminum and steel, so every wet part stays PP or PE. This is a hard rule for the factory.</figcaption>
    </figure>
  </section>

  <section>
    <span class="eyebrow">Fig. 2 · head detail</span>
    <h2>How the twist lock works</h2>
    <figure><div class="scroll">{FIG2}</div>
      <figcaption><b>You never press down to lock.</b> Two small lugs hang from the underside of the head. The collar rim has two notches. Unlocked, the lugs sit over the notches, so a press lets the head travel 4 mm and dispense. Turn the head a quarter turn clockwise and the lugs ride past a small bump onto the solid rim with a click. Now the head can't move down at all, so nothing comes out in a bag and no cream is wasted. Turn it back a quarter turn to unlock.</figcaption>
    </figure>
    <figure style="padding:0;overflow:hidden"><img src="img/lock-steps.jpg" alt="Step 1: fingers turn the knurled head a quarter turn clockwise on a sky-blue egg. Step 2: the head at the same height, turned to the locked mark, with a padlock icon.">
      <figcaption style="padding:0 14px 14px"><b>For the product page.</b> Step 1 turn a quarter turn, step 2 locked. The head stays at the same height.</figcaption></figure>
    <div class="note">
      <p><b>This is a stock mechanism.</b> Many airless and lotion pumps already lock this way. Ask for it with a click detent so customers feel it lock, and a small engraved dot on the disc that points to a lock mark on the collar.</p>
      <p>Optional upgrade: the same quarter turn swings the side slot behind a small lip on the collar, so the outlet can't drip or pick up lint.</p>
    </div>
  </section>

  <section>
    <span class="eyebrow">Use</span>
    <h2>Four things a customer does</h2>
    <div class="steps">
      <div class="step"><h3>Press</h3><p>Press the silver disc. About 0.2 ml leaves the side slot. A 30 ml cup gives roughly 150 presses.</p></div>
      <div class="step"><h3>Lock</h3><p>Turn the head a quarter turn clockwise until it clicks. It stays up and can't be pressed. Safe for a bag.</p></div>
      <div class="step"><h3>Unlock</h3><p>Turn it a quarter turn back. It's ready to press.</p></div>
      <div class="step"><h3>Refill</h3><p>Grip the collar band and unscrew the pump. Lift out the empty cup, peel the foil on a new one, drop it in and screw the pump back. Press 3 to 5 times to prime.</p></div>
    </div>
  </section>

  <section>
    <span class="eyebrow">Bill of materials</span>
    <h2>Parts, top to bottom</h2>
    <div class="tablewrap"><table>
      <thead><tr><th>Part</th><th>Material</th><th>How it's made</th><th>Source</th><th>Touches cream</th></tr></thead>
      <tbody>
        <tr><td>Press disc</td><td>ABS, satin silver PVD, UV hardcoat</td><td>Injection molded with the knurl and side slot in the tool, then vacuum metallized and topcoated</td><td><span class="tag custom">Custom</span></td><td>No</td></tr>
        <tr><td>Actuator insert</td><td>PP</td><td>Injection molded. Carries the outlet channel to the slot and the two lock lugs. The disc snaps over it.</td><td><span class="tag">Modified stock</span></td><td><span class="tag wet">Yes</span></td></tr>
        <tr><td>Collar</td><td>PP, satin silver PVD, UV hardcoat</td><td>Two lock notches and a click bump on the rim. Screws onto the shell neck below.</td><td><span class="tag">Modified stock</span></td><td>No</td></tr>
        <tr><td>Airless pump</td><td>PP/PE, metal-free fluid path</td><td>Stock airless pump with a quarter-turn up-lock, 0.2 ml dose, return spring</td><td><span class="tag">Stock</span></td><td><span class="tag wet">Yes</span></td></tr>
        <tr><td>Refill cup</td><td>PP cup, PE follower piston, foil seal</td><td>Stock refillable airless cup, 30 ml. This is the repeat purchase.</td><td><span class="tag">Stock</span></td><td><span class="tag wet">Yes</span></td></tr>
        <tr><td>Inner shell</td><td>PP or ABS, 1.5 mm wall</td><td>Injection molded egg with threaded neck and a weight pocket</td><td><span class="tag custom">Custom</span></td><td>No</td></tr>
        <tr><td>Weight</td><td>Steel or zinc alloy, 50–80 g</td><td>Turned or die-cast, pressed into the shell pocket. Tune the mass on prototypes.</td><td><span class="tag custom">Custom</span></td><td>No</td></tr>
        <tr><td>Silicone skin</td><td>Platinum-cure LSR, Shore 30–40A, soft-touch</td><td>LSR injection molded, YOJO and GHK-CU debossed in the tool. Stretches over the shell and comes off to wash.</td><td><span class="tag custom">Custom</span></td><td>No</td></tr>
      </tbody>
    </table></div>
    <div class="note">
      <p><b>Why plated plastic instead of real metal.</b> Almost every silver cap in a beauty store is molded plastic with a thin metal coating. It costs a fraction of machined aluminum, the knurl is molded in for free, and it is lighter, so the steel weight keeps the balance point low. The egg still feels heavy and solid because of that weight.</p>
      <p>The trade-off is the knurled edge, where fingers rub. A UV hardcoat stops the silver from wearing through, and a satin finish hides wear better than mirror chrome. If samples wear too fast, upgrade to electroplated ABS, which has a thicker, tougher layer. Keep the weight real steel or zinc: that's the one place metal earns its cost.</p>
    </div>
  </section>

  <section>
    <span class="eyebrow">Targets for prototype 1</span>
    <h2>Key dimensions</h2>
    <div class="tablewrap"><table>
      <thead><tr><th>Item</th><th>Target</th><th>Why</th></tr></thead>
      <tbody>
        <tr><td>Overall size</td><td class="num">Ø 68 × 110</td><td>Fits a hand and the carton cups</td></tr>
        <tr><td>Press disc</td><td class="num">Ø 36 × 5.5</td><td>Wide enough to grip the knurl when turning</td></tr>
        <tr><td>Pump stroke</td><td class="num">4</td><td>Head travel when unlocked</td></tr>
        <tr><td>Lock turn</td><td class="num">¼ turn, click detent</td><td>One motion, and you feel it lock</td></tr>
        <tr><td>Skin wall</td><td class="num">3.5</td><td>Soft feel without losing the egg shape</td></tr>
        <tr><td>Bottom curve radius</td><td class="num">≥ 40</td><td>A flatter bottom makes self-righting much easier (Fig. 3)</td></tr>
        <tr><td>Weight</td><td class="num">50–80 g</td><td>Most of the mass, as low as possible</td></tr>
        <tr><td>Fill · dose</td><td class="num">30 ml · 0.2 ml</td><td>About 150 presses per cup</td></tr>
        <tr><td>Total mass</td><td class="num">≈ 200–240 g</td><td>Feels solid and premium in the hand</td></tr>
      </tbody>
    </table></div>
  </section>

  <section>
    <span class="eyebrow">Fig. 3 · self-righting</span>
    <h2>Why it wobbles and stands back up</h2>
    <figure><div class="scroll">{FIG3}</div>
      <figcaption><b>The balance point G has to sit below C, the center of the curved bottom.</b> When the egg tips, G swings out to the side and gravity pulls it back under C, so it rocks upright. The skin and refill sit high and pull G up. The steel weight pulls it down. A flatter bottom moves C higher, which gives you more room. Tune this with a 3D-printed shell and a few steel slugs before cutting molds.</figcaption>
    </figure>
  </section>

  <section>
    <span class="eyebrow">Build order</span>
    <h2>Assembly</h2>
    <ol class="seq">
      <li>Press the weight into the pocket at the bottom of the inner shell.</li>
      <li>Stretch the silicone skin over the shell until the lip seats on the neck.</li>
      <li>Fill and foil-seal the refill cup, then drop it into the shell.</li>
      <li>Screw the collar and pump onto the shell neck. The pump seals the cup.</li>
      <li>Snap the silver disc onto the actuator so its slot lines up with the outlet channel.</li>
      <li>Prime with a few presses, then lock the head for shipping.</li>
    </ol>
  </section>

  <section>
    <span class="eyebrow">For the RFQ</span>
    <h2>Questions to send the factory</h2>
    <ol class="seq">
      <li>Do you have an airless pump with a quarter-turn up-lock and a click detent? Which dose sizes?</li>
      <li>Can the actuator outlet run to a slot on the side of a snap-on metallized overcap?</li>
      <li>Do you offer a refillable airless system where the pump stays and only a 30 ml cup with piston is replaced?</li>
      <li>Is the whole fluid path metal-free, spring included? Please confirm in writing.</li>
      <li>Run a 12-week stability test at 40 °C with our GHK-Cu cream in every wet part and report any color change.</li>
      <li>LSR skin: tooling cost, MOQ per color, soft-touch coating options and deboss depth.</li>
      <li>Quote the inner shell, the weight, and the PVD disc and collar at 3,000 and 10,000 units. Add electroplated ABS as an option.</li>
    </ol>
  </section>
</div>
"""

with open(OUT, "w") as f:
    f.write(HTML)
print("wrote", OUT, len(HTML))

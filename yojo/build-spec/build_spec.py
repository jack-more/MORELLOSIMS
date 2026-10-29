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

HTML = f"""<title>YOJO Vessel Build Spec</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
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
  --display: "IBM Plex Sans", system-ui, sans-serif;
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
.photos {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.states {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
.states figure {{ padding: 0; overflow: hidden; background: #000; }}
.states figcaption {{ padding: 0 12px 12px; color: #c9d6e2; }}
.states figcaption b {{ color: #fff; }}
video {{ display: block; width: 100%; height: auto; background: #000; }}
.vids {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
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
@media (max-width: 640px) {{ .photos, .vids {{ grid-template-columns: 1fr; }} .states {{ grid-template-columns: 1fr; }} }}
</style>

<div class="wrap">
  <header>
    <span class="eyebrow">YOJO · GHK-Cu copper peptide cream · 30 ml</span>
    <h1>Vessel build spec</h1>
    <p class="lede">A weighted silicone egg with a knurled head that twists up to open and twists down to lock flush. Inside, a threaded cartridge carries an airless pump and a 30 ml refill cup. Every image here is rendered from one 3D model, built to the numbers below.</p>
    <dl class="tb">
      <div><dt>Part</dt><dd>YOJO GHK-Cu vessel</dd></div>
      <div><dt>Rev</dt><dd class="mono">B · twist-down lock</dd></div>
      <div><dt>Units</dt><dd class="mono">mm · g · ml</dd></div>
      <div><dt>Status</dt><dd>For first samples</dd></div>
    </dl>
  </header>

  <div class="photos">
    <figure><img src="img/ext-locked.jpg" alt="The YOJO vessel locked: sky-blue silicone egg with the knurled chrome head sitting flush on top, YOJO over GHK-CU debossed on the front.">
      <figcaption><b>Locked.</b> The head sits flush on the egg. Pressing does nothing.</figcaption></figure>
    <figure><img src="img/ext-open.jpg" alt="The YOJO vessel open: the knurled head raised 9 mm on chrome threads, ready to press.">
      <figcaption><b>Open.</b> One full turn raises the head 9 mm on the threads. Now it presses.</figcaption></figure>
  </div>

  <section>
    <span class="eyebrow">Mechanism · quarter section</span>
    <h2>How it works</h2>
    <div class="states">
      <figure><img src="img/cut-locked.jpg" alt="Quarter-section of the vessel, locked: head flush on the egg, cartridge down.">
        <figcaption><b>1 · Locked.</b> The head's underside sits on the rigid stop, the top face of the fixed collar under the skin lip. There is no gap for the head to move into, so it can't be pressed. Safe in a bag.</figcaption></figure>
      <figure><img src="img/cut-open.jpg" alt="Quarter-section, open: head and the whole cartridge raised 9 mm.">
        <figcaption><b>2 · Twist up.</b> One full turn counter-clockwise. The head is keyed to the threaded sleeve by splines, so turning the head turns the sleeve. A 3-start thread with a 9 mm lead lifts the sleeve, pump and refill cup 9 mm in one turn.</figcaption></figure>
      <figure><img src="img/cut-pressed.jpg" alt="Quarter-section, pressed: head pushed 4 mm down onto the pump, cream leaving the side slot.">
        <figcaption><b>3 · Press.</b> The head slides 4 mm down the splines and works the airless pump. About 0.2 ml leaves the side slot. The pump spring pushes the head back up.</figcaption></figure>
    </div>
    <div class="vids">
      <figure style="padding:0;overflow:hidden;background:#000"><video src="video/mechanism.mp4" controls muted loop playsinline preload="metadata" poster="img/cut-open.jpg"></video>
        <figcaption style="padding:0 14px 14px;color:#c9d6e2"><b style="color:#fff">Mechanism, sectioned.</b> Twist up, press, twist down.</figcaption></figure>
      <figure style="padding:0;overflow:hidden;background:#000"><video src="video/exterior.mp4" controls muted loop playsinline preload="metadata" poster="img/ext-open.jpg"></video>
        <figcaption style="padding:0 14px 14px;color:#c9d6e2"><b style="color:#fff">Same motion, outside.</b> What the customer sees.</figcaption></figure>
    </div>
    <div class="note">
      <p><b>Locking is twisting down, nothing else.</b> No push-and-turn, no lugs. One turn clockwise until the head seats flush with a click. One turn counter-clockwise to open, with a light detent at the open height.</p>
      <p><b>Everything that touches cream is plastic.</b> The refill cup, piston, pump, its spring and the outlet channel in the head are PP, PE or POM. Copper peptide reacts with bare aluminium and steel, so the pump spring must be metal-free. The silver parts are metallized plastic and sit outside the fluid path. This is a hard rule for the factory.</p>
    </div>
  </section>

  <section>
    <span class="eyebrow">Use</span>
    <h2>Four things a customer does</h2>
    <div class="steps">
      <div class="step"><h3>Open</h3><p>Twist the head one turn counter-clockwise. It rises 9 mm on the threads.</p></div>
      <div class="step"><h3>Press</h3><p>Press the head. About 0.2 ml leaves the side slot. A 30 ml cup gives roughly 150 presses.</p></div>
      <div class="step"><h3>Lock</h3><p>Twist one turn clockwise until it clicks flush. It can't be pressed. Safe for a bag.</p></div>
      <div class="step"><h3>Refill</h3><p>From open, keep turning past the detent until the cartridge unthreads. Lift it out, pull the empty cup off the pump, push on a new one, drop it back and twist down. Press 3 to 5 times to prime.</p></div>
    </div>
  </section>

  <section>
    <span class="eyebrow">Bill of materials</span>
    <h2>Parts, top to bottom</h2>
    <div class="tablewrap"><table>
      <thead><tr><th>Part</th><th>Material</th><th>How it's made</th><th>Source</th><th>Touches cream</th></tr></thead>
      <tbody>
        <tr><td>Head</td><td>ABS, satin silver PVD, UV hardcoat</td><td>Ø36 × 9. Diamond knurl (140 around) and the side slot molded in. Y from the wordmark engraved 0.15 mm on top with a frosted floor. A 5.5 mm deep bore underneath slides on the sleeve.</td><td><span class="tag custom">Custom</span></td><td>No</td></tr>
        <tr><td>Actuator insert</td><td>PP</td><td>Sits inside the head. Carries the outlet channel from the pump stem to the slot, and the splines that key the head to the sleeve.</td><td><span class="tag custom">Custom</span></td><td><span class="tag wet">Yes</span></td></tr>
        <tr><td>Threaded sleeve</td><td>ABS, silver PVD on the visible band only</td><td>3-start thread, 9 mm lead, 3 mm pitch, OD 30. Holds the pump. Rises 9 mm when opened.</td><td><span class="tag custom">Custom</span></td><td>No</td></tr>
        <tr><td>Fixed collar</td><td>POM or PBT</td><td>Internal 3-start thread for the sleeve. Its top face is the rigid stop the head locks against. Click detents at locked and open. Snaps into the shell neck.</td><td><span class="tag custom">Custom</span></td><td>No</td></tr>
        <tr><td>Airless pump</td><td>PP/PE, plastic spring</td><td>0.2 ml dose, 4 mm stroke. Fully metal-free fluid path.</td><td><span class="tag">Stock, modified</span></td><td><span class="tag wet">Yes</span></td></tr>
        <tr><td>Refill cup</td><td>PP cup, PE follower piston, foil seal</td><td>Ø37 × 37, 31 ml fill for 30 ml nominal. Pushes onto the pump. This is the repeat purchase.</td><td><span class="tag">Stock or custom size</span></td><td><span class="tag wet">Yes</span></td></tr>
        <tr><td>Inner shell</td><td>PP, about 1.6 mm wall</td><td>Injection molded egg. The neck holds the collar. The cavity clears the cup through its 9 mm of travel.</td><td><span class="tag custom">Custom</span></td><td>No</td></tr>
        <tr><td>Weight</td><td>Steel, or zinc alloy</td><td>Slug shaped to the shell floor, Ø45 × 8. 68 g in steel, 57 g in zinc alloy. Keeps the centre of mass low.</td><td><span class="tag custom">Custom</span></td><td>No</td></tr>
        <tr><td>Silicone skin</td><td>Platinum-cure LSR, Shore 30–40A, soft-touch</td><td>3.5 mm wall, about 60 g. YOJO and GHK-CU debossed 0.5 mm in the tool. The lip wraps into the opening over the collar. Comes off to wash and to swap colours.</td><td><span class="tag custom">Custom</span></td><td>No</td></tr>
      </tbody>
    </table></div>
    <div class="note">
      <p><b>Plated plastic, real steel weight.</b> The silver parts are molded plastic with a thin metal coating: a fraction of the cost of machined metal, and lighter, so the steel weight keeps the balance low. The egg still feels heavy and solid.</p>
      <p><b>Don't plate the threads.</b> Threads rub every time the head turns, and plating there will wear through. Mold the sleeve in silver-pigmented ABS or POM so the threads look metal without a coating, and plate only the visible band if needed. Make the collar from POM so the thread runs smooth and quiet.</p>
    </div>
  </section>

  <section>
    <span class="eyebrow">Targets for prototype 1</span>
    <h2>Key dimensions</h2>
    <div class="tablewrap"><table>
      <thead><tr><th>Item</th><th>Target</th><th>Why</th></tr></thead>
      <tbody>
        <tr><td>Body</td><td class="num">Ø 68 × 70.5</td><td>Traced from the approved hero render</td></tr>
        <tr><td>Overall height</td><td class="num">79.5 locked · 88.5 open</td><td>Head 9 mm tall, lifts 9 mm</td></tr>
        <tr><td>Head</td><td class="num">Ø 36 × 9</td><td>Wide enough to grip and twist</td></tr>
        <tr><td>Thread</td><td class="num">3-start, lead 9, pitch 3, OD 30</td><td>One full turn opens or locks</td></tr>
        <tr><td>Pump stroke · dose</td><td class="num">4 · 0.2 ml</td><td>About 150 presses per cup</td></tr>
        <tr><td>Refill cup</td><td class="num">Ø 37 × 37 · 31 ml</td><td>30 ml nominal with headroom</td></tr>
        <tr><td>Skin wall</td><td class="num">3.5</td><td>Soft feel without losing the egg shape</td></tr>
        <tr><td>Weight</td><td class="num">68 g steel</td><td>Most of the mass, as low as possible</td></tr>
        <tr><td>Total mass</td><td class="num">≈ 220 g</td><td>Feels solid and premium in the hand</td></tr>
      </tbody>
    </table></div>
  </section>

  <section>
    <span class="eyebrow">Fig. · self-righting</span>
    <h2>Why it stands back up</h2>
    <figure><div class="scroll">{FIG3}</div>
      <figcaption><b>The balance point G has to sit below C, the centre of the curved bottom.</b> When the egg tips, G swings out to the side and gravity pulls it back under C. The steel weight pulls G down; the skin and the raised cartridge pull it up. The approved shape has a small flat land at the base, so it stands steady and rocks back gently. Check this on a 3D-printed shell with steel slugs before cutting molds.</figcaption>
    </figure>
  </section>

  <section>
    <span class="eyebrow">Build order</span>
    <h2>Assembly</h2>
    <ol class="seq">
      <li>Press the steel weight onto the floor of the inner shell.</li>
      <li>Snap the collar into the shell neck.</li>
      <li>Stretch the silicone skin over the shell until its lip wraps into the opening over the collar.</li>
      <li>Fill and foil-seal the refill cup and push it onto the pump in the sleeve.</li>
      <li>Thread the sleeve into the collar.</li>
      <li>Press the head onto the sleeve splines and the pump stem, with the slot lined up with the outlet.</li>
      <li>Prime with a few presses, then twist down to lock for shipping.</li>
    </ol>
  </section>

  <section>
    <span class="eyebrow">For the RFQ</span>
    <h2>Questions to send the factory</h2>
    <ol class="seq">
      <li>Can you mold a 3-start, 9 mm lead thread on an OD 30 sleeve in silver-pigmented ABS or POM, running in a POM collar, with click detents at locked and open?</li>
      <li>Can the head slide 4 mm on splines with no wobble, returned by the pump spring?</li>
      <li>Do you have an airless pump with a plastic spring, 0.2 ml dose and 4 mm stroke, where the pump stays and only a 30 ml cup with piston is replaced?</li>
      <li>Is the whole fluid path metal-free, spring included? Please confirm in writing.</li>
      <li>Run a 12-week stability test at 40 °C with our GHK-Cu cream in every wet part and report any colour change.</li>
      <li>LSR skin: tooling cost, MOQ per colour, soft-touch coating options and deboss depth.</li>
      <li>Quote the inner shell, weight, collar, sleeve and PVD head at 3,000 and 10,000 units.</li>
    </ol>
  </section>
</div>
"""

with open(OUT, "w") as f:
    f.write(HTML)
print("wrote", OUT, len(HTML))

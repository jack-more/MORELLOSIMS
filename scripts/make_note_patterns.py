#!/usr/bin/env python3
"""Code-built guilloche for the pick note (the homepage pick card).

Writes three single-colour SVGs to assets/brand/v2/. The card uses them as CSS
masks, so one file takes any ink: the team colour, the brand green, white.

  note-lattice.svg   interlaced sine waves, tiles horizontally (the team band)
  note-rosette.svg   an epitrochoid rosette (the stake's denomination)
  note-frame.svg     a 1080x1350 frame of crossing waves (the card's border)

  python3 scripts/make_note_patterns.py
"""

import math
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "assets", "brand", "v2")


def path(points):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points)


def svg(w, h, body, stroke=1.2):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            f'<g fill="none" stroke="#000" stroke-width="{stroke}" stroke-linecap="round">{body}</g></svg>\n')


def wave(x0, x1, y, amp, length, phase, step=4):
    return [(x, y + amp * math.sin(2 * math.pi * (x / length) + phase))
            for x in [x0 + i * step for i in range(int((x1 - x0) / step) + 1)]]


def lattice():
    """Rows of crossing sine waves; the width is a whole number of wavelengths so it tiles."""
    w, h, length = 480, 240, 120
    body = []
    for row in range(6):
        yc = 20 + row * 40
        for k in range(6):
            body.append(f'<path d="{path(wave(0, w, yc, 16, length, k * math.pi / 3))}"/>')
    return svg(w, h, "".join(body), 0.9)


def rosette():
    """Twelve offset epitrochoids around one centre."""
    size, c = 600, 300
    R, r, d = 150.0, 30.0, 95.0
    body = []
    for k in range(12):
        rot = k * math.pi / 36
        pts = []
        for i in range(721):
            t = 2 * math.pi * i / 720
            x = (R + r) * math.cos(t) - d * math.cos((R + r) / r * t)
            y = (R + r) * math.sin(t) - d * math.sin((R + r) / r * t)
            pts.append((c + x * math.cos(rot) - y * math.sin(rot), c + x * math.sin(rot) + y * math.cos(rot)))
        body.append(f'<path d="{path(pts)}Z"/>')
    for rad in (282, 290):
        body.append(f'<circle cx="{c}" cy="{c}" r="{rad}"/>')
    return svg(size, size, "".join(body), 1.4)


def frame():
    """Two bands of crossing waves around a 1080x1350 card, 34px in from the edge."""
    W, H, inset, band = 1080, 1350, 34, 26
    body = []
    for k in range(4):
        ph = k * math.pi / 2
        for y in (inset + band / 2, H - inset - band / 2):
            body.append(f'<path d="{path(wave(inset, W - inset, y, band / 2 - 2, 54, ph))}"/>')
        for x in (inset + band / 2, W - inset - band / 2):
            pts = [(px, py) for py, px in wave(inset, H - inset, x, band / 2 - 2, 54, ph)]
            body.append(f'<path d="{path(pts)}"/>')
    for off in (inset - 4, inset + band + 4):
        body.append(f'<rect x="{off}" y="{off}" width="{W - 2 * off}" height="{H - 2 * off}" rx="{max(6, 30 - off / 3):.0f}"/>')
    return svg(W, H, "".join(body), 1.1)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, make in (("note-lattice.svg", lattice), ("note-rosette.svg", rosette), ("note-frame.svg", frame)):
        with open(os.path.join(OUT, name), "w") as f:
            f.write(make())
        print("wrote", os.path.join("assets", "brand", "v2", name))

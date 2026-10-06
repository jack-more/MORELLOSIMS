#!/usr/bin/env python3
"""Arena plate: a Higgsfield engraving (black ink on off-white paper) ->
transparent line art that can sit on any ground.

Paper isn't flat (vignettes, shading), so the paper level is estimated
locally; only pixels clearly darker than their paper become ink. Grey haze
(dense hatching smeared by compression, paper shading) is dropped instead of
turning into a wash, and anything that isn't paper (a dark page around a
screenshot) is masked out.

  python3 scripts/make_arena_plate.py RAW.png OUT.png [--width 1600]
Output: alpha = ink, RGB = black. Tint at use time (white on blue, ink on paper).
"""

import argparse

import numpy as np
from PIL import Image, ImageFilter, ImageOps


def plate(raw, width=None):
    g = ImageOps.grayscale(raw).filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=2))
    bg = g.filter(ImageFilter.MaxFilter(21)).filter(ImageFilter.GaussianBlur(31))
    gv, bv = np.asarray(g, float), np.asarray(bg, float)
    dark = bv - gv
    a = np.clip((dark - 26) / 60, 0, 1)            # only clear ink; haze below 26 levels is paper
    a[a < 0.28] = 0
    a[bv < 150] = 0                                # not paper: page chrome around a screenshot
    img = Image.fromarray((a * 255).astype("uint8"))
    box = img.point(lambda v: 255 if v > 90 else 0).getbbox()
    img = img.crop(box)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.putalpha(img)
    if width:
        out = out.resize((width, round(width * out.height / out.width)), Image.LANCZOS)
    return out


def tinted(p, rgb):
    t = Image.new("RGBA", p.size, rgb + (0,))
    t.putalpha(p.getchannel("A"))
    return t


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("raw"); ap.add_argument("out")
    ap.add_argument("--width", type=int)
    a = ap.parse_args()
    plate(Image.open(a.raw), a.width).save(a.out)
    print(a.out)

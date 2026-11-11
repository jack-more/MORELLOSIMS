# Grade the blue bag film in a render to the print plate's blue (#81CFF2 family): only blue, saturated-enough pixels move.
import sys, numpy as np
from PIL import Image, ImageFilter
src, dst = sys.argv[1], sys.argv[2]; SAT = float(sys.argv[3]) if len(sys.argv) > 3 else 1.6; LIFT = float(sys.argv[4]) if len(sys.argv) > 4 else 0.04
im = Image.open(src).convert('RGB'); a = np.asarray(im).astype(float) / 255
mx, mn = a.max(-1), a.min(-1); l = (mx + mn) / 2; d = mx - mn
s = np.where(d == 0, 0, d / (1 - np.abs(2 * l - 1) + 1e-6))
r, g, b = a[..., 0], a[..., 1], a[..., 2]
h = np.where(mx == r, ((g - b) / (d + 1e-9)) % 6, np.where(mx == g, (b - r) / (d + 1e-9) + 2, (r - g) / (d + 1e-9) + 4)) * 60
m = ((h > 182) & (h < 222) & (s > 0.10) & (l > 0.12) & (l < 0.92)).astype(float)
m = np.asarray(Image.fromarray((m * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(1.5))).astype(float) / 255
h2 = h * (1 - m * 0.6) + 199 * m * 0.6                      # pull the hue to the plate's 199
s2 = np.clip(s * (1 + (SAT - 1) * m), 0, 1); l2 = np.clip(l + LIFT * m, 0, 1)
c = (1 - np.abs(2 * l2 - 1)) * s2; x = c * (1 - np.abs((h2 / 60) % 2 - 1)); mm = l2 - c / 2
k = (h2 // 60).astype(int) % 6
rgb = np.zeros_like(a)
for i, (R, G, B) in enumerate([(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)]):
    sel = k == i
    for ch, v in enumerate((R, G, B)): rgb[..., ch][sel] = (v if np.ndim(v) else np.full_like(c, v))[sel]
rgb += mm[..., None]
Image.fromarray((np.clip(rgb, 0, 1) * 255).astype('uint8')).save(dst)

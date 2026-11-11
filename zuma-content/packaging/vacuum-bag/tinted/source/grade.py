# Recolour the blue film to the print plate's blue, keeping each pixel's brightness relative to the film's median:
# darker = the palm shadow seen through the ink (stays dark), lighter = glints (go toward white). The white ink is left alone.
import sys, numpy as np
from PIL import Image, ImageFilter
src, dst = sys.argv[1], sys.argv[2]; T = np.array([0x6A, 0xBA, 0xE0], float)
a = np.asarray(Image.open(src).convert('RGB')).astype(float)
r, g, b = a[..., 0], a[..., 1], a[..., 2]; mx, mn = a.max(-1), a.min(-1); d = mx - mn
h = np.where(mx == r, ((g - b) / (d + 1e-9)) % 6, np.where(mx == g, (b - r) / (d + 1e-9) + 2, (r - g) / (d + 1e-9) + 4)) * 60
s = d / (mx + 1e-9); lum = a @ [0.2126, 0.7152, 0.0722]
m = ((h > 180) & (h < 225) & (s > 0.12) & (mx > 25)).astype(float)
m = np.asarray(Image.fromarray((m * 255).astype('uint8')).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.0))).astype(float) / 255
m *= np.clip((240 - mx) / 30, 0, 1)                          # the white ink stays white
med = np.median(lum[m > 0.9]); ratio = lum / med; Tl = T @ [0.2126, 0.7152, 0.0722]
dark = T[None, None, :] * np.minimum(ratio, 1)[..., None]
lightf = np.clip((ratio - 1) / ((255 / Tl) - 1), 0, 1)[..., None]
light = T[None, None, :] + (255 - T[None, None, :]) * lightf
new = np.where((ratio <= 1)[..., None], dark, light)
out = a * (1 - m[..., None]) + new * m[..., None]
Image.fromarray(np.clip(out, 0, 255).astype('uint8')).save(dst)

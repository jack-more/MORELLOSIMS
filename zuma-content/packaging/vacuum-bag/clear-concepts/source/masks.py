# combine: R = base layer (from the mask render, white = base), G = seal ribs, B = pouch shape (rounded corners)
import sys, numpy as np
from PIL import Image
base_png, out = sys.argv[1], sys.argv[2]
from PIL import Image as _I
W, H = (_I.open(base_png).size if base_png != '-' else (1400, 2100)); SEAL, RAD = 100, 140
y, x = np.mgrid[0:H, 0:W].astype(float)
e = np.minimum(np.minimum(x, W - 1 - x), np.minimum(y, H - 1 - y))
cx = np.clip(x, RAD, W - 1 - RAD); cy = np.clip(y, RAD, H - 1 - RAD)
shape = (np.hypot(x - cx, y - cy) <= RAD).astype(float)
seal = ((e < SEAL) & (e > 12)).astype(float)
R = np.asarray(Image.open(base_png).convert('L')).astype(float) / 255 if base_png != '-' else np.zeros((H, W))
img = np.dstack([R, seal, shape]) * 255
Image.fromarray(img.astype(np.uint8)).save(out)

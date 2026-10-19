# Higgsfield dancer clips -> keyed silhouette frames for ad.html.
# python3 key.py clip.mp4 outdir : decodes at 30 fps, keys the dancer off the flat background by colour distance from the
# frame's own border colour, crops every frame to the dancer's bounding box over the whole clip, writes outdir/NNNN.webp
# (near-black with alpha) and outdir/meta.json {n, fps, w, h} where w, h are the crop size in source pixels.
import json, os, subprocess, sys
import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, binary_fill_holes, binary_opening, label

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', src], capture_output=True, text=True).stdout.strip().split(',')
w, h = int(probe[0]), int(probe[1])
proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', src, '-vf', 'fps=30', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
alphas = []                                           # one frame at a time: a whole clip as float would need ~4 GB
while True:
    buf = proc.stdout.read(w * h * 3)
    if len(buf) < w * h * 3: break
    f = np.frombuffer(buf, np.uint8).reshape(h, w, 3).astype(np.float32)
    border = np.concatenate([f[:12].reshape(-1, 3), f[-12:].reshape(-1, 3), f[:, :12].reshape(-1, 3), f[:, -12:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    d = np.linalg.norm(f - bg, axis=2) / (np.linalg.norm(bg) + 1e-3)      # 0 on the background, ~1 on black
    a = np.clip((d - .38) / .3, 0, 1)
    # keep the dancer: the biggest connected blob plus anything big touching it (hair, fingers); drop specks
    m = binary_opening(a > .5, iterations=2); lab, n = label(m)
    if n:
        sizes = np.bincount(lab.ravel()); sizes[0] = 0; keep = (sizes > sizes.max() * .04)[lab]
        a = a * binary_dilation(keep, iterations=3)          # the soft edge pixels next to the kept blobs stay
        a = np.maximum(a, binary_fill_holes(keep).astype(np.float32))   # light shirts and faces inside the body go solid too
    else: a = a * 0
    alphas.append((a * 255).astype(np.uint8))
proc.wait()
A = np.stack(alphas)
ys, xs = np.where(A.max(0) > 127)
pad = 12
y0, y1 = max(0, ys.min() - pad), min(h, ys.max() + pad); x0, x1 = max(0, xs.min() - pad), min(w, xs.max() + pad)
for i, a in enumerate(A):
    rgba = np.zeros((y1 - y0, x1 - x0, 4), np.uint8); rgba[..., :3] = (10, 10, 13); rgba[..., 3] = a[y0:y1, x0:x1]
    Image.fromarray(rgba, 'RGBA').save(f'{out}/{i:04d}.webp', quality=90, method=4)
hard = A > 127
energy = [0.0] + [float((hard[i] ^ hard[i - 1]).sum()) for i in range(1, len(A))]   # pixels that changed: how much the dancer moves
json.dump({'energy': [round(e) for e in energy], 'n': len(A), 'fps': 30, 'w': int(x1 - x0), 'h': int(y1 - y0), 'src': [w, h], 'box': [int(x0), int(y0), int(x1), int(y1)]}, open(f'{out}/meta.json', 'w'))
print(src, len(A), 'frames, crop', x1 - x0, 'x', y1 - y0)

# Calibrate skin (and backdrop) so the rendered lit side hits target hex values.
import subprocess, sys, os, json, math
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); PY = os.path.join(HERE, '..', 'bl', 'bin', 'python')
def s2l(c): c = c / 255.0; return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def hexl(h): return s2l(np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], float))
def patch(img, fx, fy, f=0.035):
    a = np.asarray(img.convert('RGB'), float); H, W, _ = a.shape
    x0, y0 = int(W * (fx - f)), int(H * (fy - f)); x1, y1 = int(W * (fx + f)), int(H * (fy + f))
    return s2l(a[y0:y1, x0:x1].reshape(-1, 3).mean(0))
def run(env, out):
    e = dict(os.environ); e.update(env)
    subprocess.run([PY, os.path.join(HERE, 'build.py'), 'hero', out, '320', '400', '24'], env=e, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return Image.open(out)
def calibrate(skin_target, bg, bg_target=None, iters=4, skin_pt=(0.40, 0.45), bg_pt=(0.12, 0.12)):
    tS = hexl(skin_target); skin = tS.copy() * 0.8; expo = -2.0
    tB = hexl(bg_target) if bg_target else None; bgl = tB.copy() * 0.8 if bg_target else None
    for it in range(iters):
        env = {'SKIN_LIN': ','.join(f'{v:.5f}' for v in skin), 'EXPO': f'{expo:.3f}', 'BG': bg}
        if bgl is not None: env['BG_LIN'] = ','.join(f'{v:.5f}' for v in bgl)
        img = run(env, os.path.join(HERE, f'cal_{it}.png'))
        mS = patch(img, *skin_pt)
        prop = skin * (tS / np.maximum(mS, 1e-5))
        m = prop.max(); skin = np.clip(prop * (0.8 / m), 0.002, 0.9); expo += math.log2(m / 0.8)
        msg = {'it': it, 'skin_meas': '#%02X%02X%02X' % tuple(int(round(v)) for v in (np.where(mS <= 0.0031308, mS * 12.92, 1.055 * mS ** (1 / 2.4) - 0.055) * 255).clip(0, 255)), 'expo': round(expo, 3)}
        if bgl is not None:
            mB = patch(img, *bg_pt); bgl = np.clip(bgl * tB / np.maximum(mB, 1e-5), 0.002, 0.95)
            msg['bg_meas'] = '#%02X%02X%02X' % tuple(int(round(v)) for v in (np.where(mB <= 0.0031308, mB * 12.92, 1.055 * mB ** (1 / 2.4) - 0.055) * 255).clip(0, 255))
        print(json.dumps(msg), flush=True)
    return {'SKIN_LIN': ','.join(f'{v:.5f}' for v in skin), 'EXPO': f'{expo:.3f}', 'BG': bg,
            **({'BG_LIN': ','.join(f'{v:.5f}' for v in bgl)} if bgl is not None else {})}
if __name__ == '__main__':
    name, skin_t, bg = sys.argv[1], sys.argv[2], sys.argv[3]
    bg_t = sys.argv[4] if len(sys.argv) > 4 else None
    res = calibrate(skin_t, bg, bg_t)
    json.dump(res, open(os.path.join(HERE, f'calib_{name}.json'), 'w'))
    print('final', res)

# Converts the site renders (cyc/siteimg/*.png) and the option C labels (cyc/tex2) into the site's image files (site3/src/img).
import os, glob
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
SI = os.path.join(ROOT, 'cyc', 'siteimg'); TEX = os.path.join(ROOT, 'cyc', 'tex2'); IMG = os.path.join(ROOT, 'site3', 'src', 'img')
def save(im, path, q=86): im.save(path, 'WEBP', quality=q, method=6); print('  ', os.path.relpath(path, ROOT))
for f in sorted(glob.glob(os.path.join(TEX, 'label-*.png'))):           # flat labels: the printed span, 1800 x 838
    no = os.path.basename(f)[6:8]; im = Image.open(f).convert('RGB').crop((160, 0, 3040, 1340)).resize((1800, 838), Image.LANCZOS)
    save(im, os.path.join(IMG, 'label-%s.webp' % no))
    if os.path.exists(os.path.join(IMG, 'label-%s-s.webp' % no)): save(im.resize((900, 419), Image.LANCZOS), os.path.join(IMG, 'label-%s-s.webp' % no))
for f in sorted(glob.glob(os.path.join(SI, 'vial-*.png'))):            # product page photos, 720 x 960
    save(Image.open(f).convert('RGB'), os.path.join(IMG, os.path.basename(f)[:-4] + '.webp'))
for f in sorted(glob.glob(os.path.join(SI, 'spin-*.png'))):            # product page turn frames, 540 x 720
    no, k = os.path.basename(f)[5:-4].split('-'); save(Image.open(f).convert('RGB'), os.path.join(IMG, 'spin', '%s-%s.webp' % (no, k)), 80)
for f in sorted(glob.glob(os.path.join(SI, 'hspin-*.png'))):           # home hero turn frames, 760 x 950, transparent
    no, k = os.path.basename(f)[6:-4].split('-'); save(Image.open(f), os.path.join(IMG, 'hspin', '%s-%s.webp' % (no, k)), 82)
for f in sorted(glob.glob(os.path.join(SI, 'hero-vial-*.png'))):       # tilted cutouts: 1000 x 1250, a 560 x 814 close crop, a 240 x 300 thumb
    no = os.path.basename(f)[10:12]; im = Image.open(f).convert('RGBA')
    save(im, os.path.join(IMG, 'hero-vial-%s.webp' % no)); save(im.resize((240, 300), Image.LANCZOS), os.path.join(IMG, 'hero-vial-%s-s.webp' % no))
    bb = im.getbbox(); cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2; ch = min(1250, (bb[3] - bb[1]) * 1.04); cw = ch * 560 / 814
    save(im.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))).resize((560, 814), Image.LANCZOS), os.path.join(IMG, 'hero-vial-%s-c.webp' % no))

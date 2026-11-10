# ZUMA launch cut: AI footage (no text) + our own captions, typed a word at a time in white pills, + end card.
# usage: python edit.py footage.mp4 out.mp4 workdir
import subprocess, sys, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SRC, OUT, WD = sys.argv[1], sys.argv[2], sys.argv[3]
FONT = '/tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad/font/Outfit-600.ttf'
W, H = 1080, 1920
INK, PILL = (22, 24, 28, 255), (255, 255, 255, 240)
os.makedirs(WD, exist_ok=True)

# (start s, end s, full line, word count shown): a line types on, word by word
LINES = [   # timed to the footage's cuts (1 s apart); y = pill centre as a fraction of the height
    (0.15, 2.90, 'Research is changing.', 0.50),
    (3.05, 4.90, 'Tested by lot.', 0.50),
    (5.05, 8.90, 'Every vial. Every report.', 0.50),
    (9.05, 11.90, "It's a new era of research,", 0.20),
    (12.05, 14.90, 'here now.', 0.20),
]
STEP = 0.22   # seconds between words while typing

def pill(text, yf=0.5, size=58):
    f = ImageFont.truetype(FONT, size); d0 = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    tw = d0.textlength(text, font=f); a, dsc = f.getmetrics()
    px, py = 34, 22; w, h = int(tw + 2 * px), int(a + dsc + 2 * py - 8)
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    x0, y0 = (W - w) // 2, int(H * yf) - h // 2
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle([x0, y0 + 6, x0 + w, y0 + h + 6], 22, fill=(0, 0, 0, 70))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(im); d.rounded_rectangle([x0, y0, x0 + w, y0 + h], 22, fill=PILL)
    d.text((x0 + px, y0 + py - 6), text, font=f, fill=INK)
    return im

overlays = []   # (png, start, end)
for i, (t0, t1, line, yf) in enumerate(LINES):
    words = line.split(' ')
    for k in range(1, len(words) + 1):
        a = t0 + (k - 1) * STEP; b = t0 + k * STEP if k < len(words) else t1
        p = f'{WD}/cap-{i}-{k}.png'; pill(' '.join(words[:k]), yf).save(p); overlays.append((p, a, b))

inputs = ['-i', SRC]
for p, _, _ in overlays: inputs += ['-i', p]
fc = ['[0:v]scale=1080:1920:flags=lanczos,fps=30,setsar=1,format=yuv420p[v0]']
last = 'v0'
for j, (_, a, b) in enumerate(overlays, 1):
    fc.append(f"[{last}][{j}:v]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'[v{j}]"); last = f'v{j}'
subprocess.run(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', ';'.join(fc), '-map', f'[{last}]', '-map', '0:a?',
                '-c:v', 'libx264', '-crf', '17', '-preset', 'slow', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', f'{WD}/body.mp4'], check=True)

# end card: the crest, ZUMA and zumatides.com on ZUMA blue, research-use line on the Oxblood band
import io, re, cairosvg
snow, ox = '#FCFBF8', '#6E1C2A'
def svgimg(path, width):
    s = open(path).read(); s = re.sub(r'<svg[^>]*?viewBox', '<svg xmlns="http://www.w3.org/2000/svg" viewBox', s, count=1).replace('currentColor', snow)
    s = re.sub(r'fill="#[0-9A-Fa-f]{3,6}"', f'fill="{snow}"', s)
    return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=s.encode(), output_width=width))).convert('RGBA')
card = Image.new('RGBA', (W, H), '#1E74A8'); d = ImageDraw.Draw(card)
crest = svgimg('/home/user/MORELLOSIMS/zuma-content/packaging/capsule-case/zuma-crest-stamp.svg', 260)
wm = svgimg('/home/user/zuma/source/src/partials/wordmark.svg', 600)
card.alpha_composite(crest, ((W - crest.width) // 2, 560)); card.alpha_composite(wm, ((W - wm.width) // 2, 900))
f2 = ImageFont.truetype(FONT, 46); t = 'zumatides.com'; d.text(((W - d.textlength(t, font=f2)) / 2, 1110), t, font=f2, fill=snow)
d.rectangle([0, H - 200, W, H], fill=ox); f3 = ImageFont.truetype(FONT.replace('600', '500'), 30)
for i, t in enumerate(['For laboratory research use only.', 'Not for human or veterinary use.']):
    d.text(((W - d.textlength(t, font=f3)) / 2, H - 150 + i * 44), t, font=f3, fill=snow)
card.convert('RGB').save(f'{WD}/endcard.png')

dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f'{WD}/body.mp4'], capture_output=True, text=True).stdout)
off = dur - 0.4
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f'{WD}/body.mp4', '-loop', '1', '-t', '3', '-i', f'{WD}/endcard.png', '-filter_complex',
                f'[0:v]fps=30,settb=1/30,format=yuv420p,setsar=1[b];[1:v]scale=1080:1920,fps=30,settb=1/30,format=yuv420p,setsar=1[c];[b][c]xfade=transition=fade:duration=0.4:offset={off:.2f}[v];'
                f'[0:a]apad=pad_dur=2.7,afade=t=out:st={dur:.2f}:d=2.4[a]', '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-crf', '17',
                '-preset', 'slow', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', OUT], check=True)
print('done', OUT)

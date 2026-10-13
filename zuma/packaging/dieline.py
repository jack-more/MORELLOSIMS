# flat reverse-tuck carton from the 4080x3300 atlas: [glue][front][right][back][left], top flap on the front, bottom flap on the back
import sys; from PIL import Image, ImageDraw
src, out = sys.argv[1], sys.argv[2]; A = Image.open(src).convert('RGB'); s = 0.25
P = 1020; H = 2280; G = 160; T = 1020; TK = 260   # panel, height, glue flap, flap depth, tuck
W = G + 4 * P; HH = TK + T + H + T + TK
im = Image.new('RGBA', (W + 80, HH + 80), (0, 0, 0, 0)); ox, oy = 40, 40; d = ImageDraw.Draw(im)
order = [0, 1, 2, 3]
for i, k in enumerate(order): im.paste(A.crop((k * P, 0, k * P + P, H)), (ox + G + i * P, oy + TK + T))
top = A.crop((0, 2280, 1020, 3300)); bot = A.crop((1020, 2280, 2040, 3300))
im.paste(top, (ox + G, oy + TK)); im.paste(bot.rotate(180), (ox + G + 2 * P, oy + TK + T + H))
fill = A.getpixel((1030, 1200)); edge = A.getpixel((10, 2270))
d.polygon([(ox, oy + TK + T + 120), (ox + G, oy + TK + T), (ox + G, oy + TK + T + H), (ox, oy + TK + T + H - 120)], fill=fill)
d.rounded_rectangle([ox + G + 40, oy, ox + G + P - 40, oy + TK + 20], radius=120, fill=A.getpixel((500, 2400)))
d.rounded_rectangle([ox + G + 2 * P + 40, oy + TK + T + H + T - 20, ox + G + 3 * P - 40, oy + HH], radius=120, fill=fill)
for i in (1, 3):  # dust flaps
    x0 = ox + G + i * P; d.polygon([(x0 + 30, oy + TK + T), (x0 + 120, oy + TK + T - 520), (x0 + P - 120, oy + TK + T - 520), (x0 + P - 30, oy + TK + T)], fill=fill)
    d.polygon([(x0 + 30, oy + TK + T + H), (x0 + 120, oy + TK + T + H + 520), (x0 + P - 120, oy + TK + T + H + 520), (x0 + P - 30, oy + TK + T + H)], fill=fill)
def dash(a, b, c=(17, 19, 25, 255)):
    (x1, y1), (x2, y2) = a, b; n = int(max(abs(x2 - x1), abs(y2 - y1)) / 28)
    for j in range(0, n, 2): d.line([(x1 + (x2 - x1) * j / n, y1 + (y2 - y1) * j / n), (x1 + (x2 - x1) * (j + 1) / n, y1 + (y2 - y1) * (j + 1) / n)], fill=c, width=6)
y0, y1 = oy + TK + T, oy + TK + T + H
for i in range(5): dash((ox + G + i * P, y0), (ox + G + i * P, y1))
dash((ox + G, y0), (ox + G + 4 * P, y0)); dash((ox + G, y1), (ox + G + 4 * P, y1)); dash((ox + G, oy + TK), (ox + G + P, oy + TK)); dash((ox + G + 2 * P, y1 + T), (ox + G + 3 * P, y1 + T))
im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS); im.save(out, quality=88)

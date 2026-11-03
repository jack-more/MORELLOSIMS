# Text to outlines: shape with HarfBuzz, draw glyphs with fontTools, emit one SVG <path> in mm.
# Factory art carries no live type, so nothing reflows or substitutes at the printer.
import os, math
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
FILES = {('Outfit', 700): 'outfit-700.ttf', ('Figtree', 500): 'figtree-500.ttf', ('Figtree', 600): 'figtree-600.ttf',
         ('IBM Plex Mono', 500): 'plexmono-500.ttf', ('IBM Plex Mono', 600): 'plexmono-600.ttf'}
_cache = {}

def _font(fam, w):
    k = (fam, w)
    if k not in _cache:
        p = os.path.join(FD, FILES[k]); data = open(p, 'rb').read()
        hbf = hb.Font(hb.Face(data)); tt = TTFont(p)
        _cache[k] = (hbf, tt, tt.getGlyphSet(), tt['head'].unitsPerEm)
    return _cache[k]

def shape(txt, fam, w):
    hbf, tt, gs, upem = _font(fam, w)
    buf = hb.Buffer(); buf.add_str(txt); buf.guess_segment_properties()
    hb.shape(hbf, buf, {'kern': True, 'liga': True})
    order = tt.getGlyphOrder()
    return [(order[i.codepoint], p.x_advance, p.x_offset, p.y_offset) for i, p in zip(buf.glyph_infos, buf.glyph_positions)], upem

def width(txt, size, fam='Figtree', w=500, ls=0):
    gl, upem = shape(txt, fam, w)
    return sum(a for _, a, _, _ in gl) * size / upem + ls * len(gl)

def text_path(x, y, size, txt, fam='Figtree', w=500, fill='#000', anchor='start', ls=0, rot=None, opacity=None):
    gl, upem = shape(txt, fam, w); _, tt, gs, _ = _font(fam, w)
    k = size / upem; tw = width(txt, size, fam, w, ls)
    x0 = x - (tw / 2 if anchor == 'middle' else tw if anchor == 'end' else 0)
    c, s = (1, 0) if rot is None else (math.cos(math.radians(rot)), math.sin(math.radians(rot)))
    pen = SVGPathPen(gs, ntos=lambda v: ('%.3f' % v).rstrip('0').rstrip('.'))
    cx = x0
    for name, adv, xo, yo in gl:
        gx, gy = cx + xo * k, y - yo * k  # glyph origin before rotation
        # rotate about (x, y) like SVG rotate(rot x y); font y is up, SVG y is down
        ox = x + (gx - x) * c - (gy - y) * s; oy = y + (gx - x) * s + (gy - y) * c
        gs[name].draw(TransformPen(pen, (k * c, k * s, k * s, -k * c, ox, oy)))
        cx += adv * k + ls
    op = f' opacity="{opacity}"' if opacity is not None else ''
    return f'<path d="{pen.getCommands()}" fill="{fill}"{op}/>'

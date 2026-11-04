# A minimal vector PDF writer: exact page size (MediaBox + TrimBox), fills and strokes in RGB, paths from SVG path data and font glyphs.
import zlib
from fontTools.pens.basePen import BasePen
from fontTools.svgLib.path import parse_path
class PDFPen(BasePen):
    def __init__(self, gs=None): super().__init__(gs); self.o = []
    def _moveTo(self, p): self.o.append(f'{p[0]:.4f} {p[1]:.4f} m')
    def _lineTo(self, p): self.o.append(f'{p[0]:.4f} {p[1]:.4f} l')
    def _curveToOne(self, a, b, c): self.o.append(f'{a[0]:.4f} {a[1]:.4f} {b[0]:.4f} {b[1]:.4f} {c[0]:.4f} {c[1]:.4f} c')
    def _qCurveToOne(self, a, b):
        p0 = self._getCurrentPoint(); c1 = (p0[0] + 2 / 3 * (a[0] - p0[0]), p0[1] + 2 / 3 * (a[1] - p0[1])); c2 = (b[0] + 2 / 3 * (a[0] - b[0]), b[1] + 2 / 3 * (a[1] - b[1]))
        self._curveToOne(c1, c2, b)
    def _closePath(self): self.o.append('h')
    def _endPath(self): pass
def svgpath(d): p = PDFPen(); parse_path(d, p); return ' '.join(p.o)
def rgb(h):
    h = h.strip()
    if h.startswith('#') and len(h) == 7: return ' '.join(f'{int(h[i:i + 2], 16) / 255:.4f}' for i in (1, 3, 5))
    raise ValueError('colour ' + h)
def mm(v): return v * 72 / 25.4
def write(path, w_mm, h_mm, bleed_mm, content, images=None):
    """content: PDF operators drawn in points with the origin at the bottom-left. images: {name: (jpeg_bytes, px_w, px_h, 'DeviceRGB'|'DeviceGray')}."""
    W, H, B = mm(w_mm), mm(h_mm), mm(bleed_mm); images = images or {}
    objs = []; add = lambda b: objs.append(b) or len(objs)
    stream = zlib.compress(content.encode('latin-1'))
    c_id = add(b'<< /Length %d /Filter /FlateDecode >>\nstream\n' % len(stream) + stream + b'\nendstream')
    xo = {}
    for n, (data, iw, ih, cs) in images.items():
        xo[n] = add(b'<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /%s /BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n' % (iw, ih, cs.encode(), len(data)) + data + b'\nendstream')
    res = '<< /XObject << ' + ' '.join(f'/{n} {i} 0 R' for n, i in xo.items()) + ' >> >>' if xo else '<< >>'
    pages_id = len(objs) + 2
    pg = add(f'<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {W:.3f} {H:.3f}] /TrimBox [{B:.3f} {B:.3f} {W - B:.3f} {H - B:.3f}] /Resources {res} /Contents {c_id} 0 R >>'.encode())
    add(f'<< /Type /Pages /Kids [{pg} 0 R] /Count 1 >>'.encode()); cat = add(f'<< /Type /Catalog /Pages {pages_id} 0 R >>'.encode())
    out = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'; offs = []
    for i, o in enumerate(objs, 1): offs.append(len(out)); out += b'%d 0 obj\n' % i + o + b'\nendobj\n'
    x = len(out); out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1) + b''.join(b'%010d 00000 n \n' % o for o in offs)
    out += b'trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, cat, x)
    open(path, 'wb').write(out)

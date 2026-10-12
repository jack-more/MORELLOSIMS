/* ZUMA Tricolor label.
   A port of the "field-bands" direction (lux7/dirs-r3.js, "Color Field · Three Bands") with no other dependencies.
   One wrap-around label, 3200 x 1340 px. Printed span x 160..3040 (the gap is the seam at the back); the front panel is centred on x 1600.
   Light band: the brand. Saturated band: the research area, named on its own colour, and the compound. Deep band: the research-use line and the lot line.
   The left side panel carries the QR code and the lot record; the right side panel repeats the research-use sentence.
   Needs qrcodejs 1.0.0 (window.QRCode) and Schibsted Grotesk 700/800/900 loaded before drawing.
   Used by the live 3D vials (js/vials3d.js) and by the still renders (tools/build.sh concatenates this file). */
(function (root) {
  const SG = "'Schibsted Grotesk', 'Helvetica Neue', Arial, sans-serif";
  const W = 3200, H = 1340, X0 = 160, X1 = 3040, FC = 1600;
  const PAPER = '#F7F4EE', WHITE = '#FFFFFF';
  // Tricolor: three tones of one color per research area (light, saturated, deep)
  const TONES = {
    metabolic: ['#A3CEFF', '#1F4FD8', '#0B1F5C'],
    tissue: ['#ABE9C3', '#0E9A5B', '#0A3B26'],
    dermal: ['#FFB7C5', '#FF5A1F', '#9E1717'],
    endocrine: ['#FFE97A', '#F5A300', '#5E3C00']
  };
  const AREA_NAME = { metabolic: 'Metabolic research', tissue: 'Tissue research', dermal: 'Dermal research', endocrine: 'Endocrine research' };
  // ink on the saturated band: white, except on endocrine amber where white would not read
  const onMid = a => a === 'endocrine' ? TONES.endocrine[2] : WHITE;
  const RUO1 = 'RESEARCH USE ONLY', RUO2 = 'NOT FOR HUMAN OR VETERINARY USE', RUOF = 'For laboratory research use only. Not for human or veterinary use.';
  const YS = [[0, 400], [418, 850], [868, 1340]];

  // text with tracking, alignment and a max width that shrinks the size (same maths as the lux6 kit)
  function T(x, s, X, Y, o = {}) {
    const { size = 40, weight = 400, family = SG, fill = '#000', ls = 0, align = 'left', maxW = 0 } = o;
    let fs = size; const set = () => { x.font = `${weight} ${fs}px ${family}`; x.letterSpacing = (ls * fs / size) + 'px'; };
    set(); let w = x.measureText(s).width - ls * fs / size;
    while (maxW && w > maxW && fs > 6) { fs -= Math.max(1, fs * 0.04); set(); w = x.measureText(s).width - ls * fs / size; }
    x.textBaseline = 'alphabetic'; x.textAlign = 'left'; const sx = align === 'center' ? X - w / 2 : align === 'right' ? X - w : X;
    x.fillStyle = fill; x.fillText(s, sx, Y); x.letterSpacing = '0px'; return { w, fs, x0: sx };
  }
  function wrap(x, s, maxW) { const out = []; let cur = ''; for (const w of s.split(' ')) { const t = cur ? cur + ' ' + w : w; if (x.measureText(t).width > maxW && cur) { out.push(cur); cur = w; } else cur = t; } if (cur) out.push(cur); return out; }
  function para(x, s, X, Y, o) { const { size, weight, fill, maxW, lh = 1.32 } = o; x.font = `${weight} ${size}px ${SG}`; x.letterSpacing = '0px';
    wrap(x, s, maxW).forEach((l, i) => T(x, l, X, Y + i * size * lh, { size, weight, fill })); }
  function rows(x, X, Y, list) { let y = Y; list.forEach(([t, weight, size, fill]) => { T(x, t, X, y, { size, weight, fill, maxW: 940 }); y += size * 1.36; }); }
  function qr(x, url, X, Y, S, dark) {
    try { const d = document.createElement('div'); const q = new QRCode(d, { text: url, width: 64, height: 64, correctLevel: QRCode.CorrectLevel.M }); const m = q._oQRCode, n = m.getModuleCount(), c = S / (n + 2);
      x.fillStyle = dark; for (let r = 0; r < n; r++) for (let k = 0; k < n; k++) if (m.isDark(r, k)) x.fillRect(X + c * (k + 1), Y + c * (r + 1), c + 0.6, c + 0.6);
    } catch (e) { x.fillStyle = dark; x.fillRect(X, Y, S, S); }
  }

  // ---------- LOGO: the one place the label gets its logo ----------
  // It redraws whatever <symbol id="zuma-logo"> on the page holds (text, rect, path, circle, polygon), so swapping the
  // page's logo slot also swaps the logo printed on every vial. Without a symbol it falls back to the Tricolor mark.
  // h is the height of the symbol's viewBox in canvas px; returns the drawn width.
  let SPEC;
  function readSymbol() {
    if (SPEC !== undefined) return SPEC; SPEC = null;
    const sym = typeof document !== 'undefined' && document.getElementById('zuma-logo'); if (!sym) return SPEC;
    const vb = (sym.getAttribute('viewBox') || '0 0 448 100').trim().split(/[\s,]+/).map(Number);
    const num = (el, a, d = 0) => { const v = parseFloat(el.getAttribute(a)); return isNaN(v) ? d : v; };
    const paint = el => { const role = el.getAttribute('data-role'); if (role === 'dot') return 'dot';
      const f = (el.style && el.style.fill) || el.getAttribute('fill') || 'currentColor'; if (f === 'none') return null; if (f === 'currentColor') return 'ink';
      const m = /var\([^,]+,\s*([^)]+)\)/.exec(f); return m ? m[1].trim() : f; };
    const els = [...sym.querySelectorAll('text,rect,path,circle,polygon')].map(el => {
      const k = el.tagName.toLowerCase(), o = { k, paint: paint(el) };
      if (k === 'text') Object.assign(o, { s: el.textContent.trim(), x: num(el, 'x'), y: num(el, 'y'), size: num(el, 'font-size', 100), weight: el.getAttribute('font-weight') || '800',
        family: el.getAttribute('font-family') || SG, ls: num(el, 'letter-spacing'), anchor: el.getAttribute('text-anchor') || 'start' });
      if (k === 'rect') Object.assign(o, { x: num(el, 'x'), y: num(el, 'y'), w: num(el, 'width'), h: num(el, 'height'), r: num(el, 'rx') });
      if (k === 'circle') Object.assign(o, { x: num(el, 'cx'), y: num(el, 'cy'), r: num(el, 'r') });
      if (k === 'path') { o.p = new Path2D(el.getAttribute('d')); o.rule = el.getAttribute('fill-rule') === 'evenodd' ? 'evenodd' : 'nonzero'; }
      if (k === 'polygon') o.p = new Path2D('M' + el.getAttribute('points').trim() + 'Z');
      return o; });
    SPEC = { vb, els }; return SPEC;
  }
  function logo(x, X, Y, h, ink, dot) {
    const sp = readSymbol();
    if (!sp) { const r = T(x, 'ZUMA', X, Y + h * 0.9, { size: h * 1.15, weight: 800, fill: ink, ls: h * 0.02 }); x.fillStyle = dot; x.fillRect(X + r.w + h * 0.22, Y + h * 0.3, h * 0.6, h * 0.6); return r.w + h * 0.9; }
    const [vx, vy, vw, vh] = sp.vb, s = h / vh; x.save(); x.translate(X, Y); x.scale(s, s); x.translate(-vx, -vy);
    for (const e of sp.els) { if (!e.paint) continue; x.fillStyle = e.paint === 'ink' ? ink : e.paint === 'dot' ? dot : e.paint;
      if (e.k === 'text') { x.font = `${e.weight} ${e.size}px ${e.family}`; x.letterSpacing = e.ls + 'px'; x.textBaseline = 'alphabetic';
        const w = x.measureText(e.s).width; x.textAlign = 'left'; x.fillText(e.s, e.anchor === 'middle' ? e.x - w / 2 : e.anchor === 'end' ? e.x - w : e.x, e.y); x.letterSpacing = '0px'; }
      else if (e.k === 'rect') { x.beginPath(); x.roundRect ? x.roundRect(e.x, e.y, e.w, e.h, e.r) : x.rect(e.x, e.y, e.w, e.h); x.fill(); }
      else if (e.k === 'circle') { x.beginPath(); x.arc(e.x, e.y, e.r, 0, Math.PI * 2); x.fill(); }
      else x.fill(e.p, e.rule || 'nonzero'); }
    x.restore(); return vw * s;
  }

  // p: { name, full, area, mg, lot, filled, url }
  function draw(x, p) {
    const A = p.area, [lt, md, dp] = TONES[A], mi = onMid(A), areaName = (p.areaName || AREA_NAME[A]).toUpperCase();
    x.fillStyle = PAPER; x.fillRect(X0, 0, X1 - X0, H);
    YS.forEach(([t, b], i) => { x.fillStyle = TONES[A][i]; x.fillRect(X0, t, X1 - X0, b - t); });
    // front panel
    // the brand alone on the light band, centred on the front panel
    { const m = document.createElement('canvas').getContext('2d'), lw = logo(m, 0, 0, 236, dp, md); logo(x, FC - lw / 2, 82, 236, dp, md); }
    // the research area sits on the solid colour it owns, above the compound
    T(x, areaName, FC, 474, { size: 40, weight: 800, fill: mi, align: 'center', ls: 6, maxW: 900 });
    T(x, p.name, FC, 738, { size: 300, weight: 900, fill: mi, align: 'center', maxW: 1010, ls: -8 });
    T(x, String(p.mg).toUpperCase(), FC, 834, { size: 92, weight: 900, fill: mi, align: 'center', ls: 2, maxW: 900 });
    T(x, (p.full + ' · lyophilized powder').toUpperCase(), FC, 948, { size: 38, weight: 800, fill: lt, align: 'center', ls: 3, maxW: 960 });
    T(x, RUO1, FC, 1062, { size: 84, weight: 900, fill: WHITE, align: 'center', ls: 3, maxW: 960 });
    T(x, RUO2, FC, 1124, { size: 40, weight: 700, fill: WHITE, align: 'center', ls: 3, maxW: 960 });
    T(x, 'LOT ' + p.lot + '  ·  FILLED ' + p.filled + '  ·  STORE −20 °C', FC, 1222, { size: 32, weight: 700, fill: lt, align: 'center', ls: 2, maxW: 960 });
    // left side panel: the code to this lot's report and the lot record
    qr(x, p.url, 640, 45, 320, dp);
    rows(x, 640, 560, [['Lot ' + p.lot, 800, 42, mi], ['Filled ' + p.filled, 700, 38, mi], ['Store at −20 °C, dark', 700, 38, mi]]);
    // right side panel
    para(x, RUOF, 2240, 120, { size: 34, weight: 700, fill: dp, maxW: 580 });
    logo(x, 2240, 700 - 170 * 0.9, 170, mi, mi === WHITE ? lt : dp);
    T(x, 'EST. 2026', 2246, 790, { size: 36, weight: 700, fill: mi, ls: 6 });
  }
  // a canvas with the label drawn at scale k (1 = 3200 x 1340)
  function canvas(p, k = 1) { const c = document.createElement('canvas'); c.width = Math.round(W * k); c.height = Math.round(H * k); const x = c.getContext('2d'); x.scale(k, k); draw(x, p); return c; }
  // which way to turn the vial: 0 shows the front panel, LOT_SIDE shows the code and lot record
  const LOT_SIDE = Math.PI / 2;
  root.ZUMA_LABEL = { W, H, X0, X1, FC, TONES, AREA_NAME, PAPER, onMid, draw, canvas, logo, LOT_SIDE, FONTS: ["700 40px 'Schibsted Grotesk'", "800 40px 'Schibsted Grotesk'", "900 40px 'Schibsted Grotesk'"] };
})(typeof window !== 'undefined' ? window : globalThis);

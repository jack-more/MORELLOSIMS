/* ZUMA Tricolor label, PRINT version: the same label re-set for a 43 x 20 mm wrap label (67 px/mm, 1702 dpi).
   Every line is at least 2.7 pt, the QR code is 9.6 mm so a phone reads it, the lot number is left to an inkjet box, and the bands run 1.5 mm (100 px) into bleed.
   Draw it on a 3080 x 1540 canvas translated by (-60, 100): trim is x 160..3040, y 0..1340.
   Made from label2.js; keep the two in step when the design changes.

   A port of the "field-bands" direction (lux7/dirs-r3.js, "Color Field · Three Bands") with no other dependencies.
   One wrap-around label, 3200 x 1340 px. Printed span x 160..3040 (the gap is the seam at the back); the front panel is centred on x 1600.
   Light band: the brand. Saturated band: the research area, named on its own colour, and the compound. Deep band: the research-use line and the lot line.
   The left side panel carries the QR code and the lot record; the right side panel repeats the research-use sentence.
   Needs qrcodejs 1.0.0 (window.QRCode) and Outfit 700/800/900 loaded before drawing.
   Used by the live 3D vials (js/vials3d.js) and by the still renders (tools/build.sh concatenates this file). */
(function (root) {
  const SG = "'Outfit', 'Helvetica Neue', Arial, sans-serif";
  const W = 3200, H = 1340, X0 = 60, X1 = 3140, FC = 1600, BL = 100;
  const PAPER = '#F7F4EE', WHITE = '#FFFFFF', OX = '#6E1C2A', SNOW = '#FCFBF8';
  // refined palette: light, bright, deep per research area
  const TONES = {
    metabolic: ['#BFE8FB', '#36B3E8', '#0E5A8C'], tissue: ['#D5F3BC', '#6CC93A', '#2F6E14'], dermal: ['#FFC9BE', '#FF6A55', '#A8281F'],
    endocrine: ['#FBF1A6', '#F4D63A', '#9A7A06'], neuro: ['#E4D8FF', '#A57BF0', '#4B2A9A'], supplies: ['#E3E8ED', '#9AA8B6', '#3D4956']
  };
  const AREA_NAME = { metabolic: 'Metabolic research', tissue: 'Tissue research', dermal: 'Dermal research', endocrine: 'Endocrine research', neuro: 'Neuro research', supplies: 'Laboratory supplies' };
  const onMid = a => OX;   // Oxblood type on every colour band
  const RUOF = 'For laboratory research use only. Not for human or veterinary use.';
  // light band (brand), bright band (the compound, most of the label), a slim Oxblood band (research-use and lot lines)
  const YS = [[-BL, 330], [342, 1128], [1128, 1340 + BL]];

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
  const SPECS = {};
  function readSymbol(id = 'zuma-logo') {
    if (SPECS[id] !== undefined) return SPECS[id]; let SPEC = SPECS[id] = null;
    const sym = typeof document !== 'undefined' && document.getElementById(id); if (!sym) return SPEC;
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
    SPEC = SPECS[id] = { vb, els }; return SPEC;
  }
  function logo(x, X, Y, h, ink, dot, id) {
    const sp = readSymbol(id);
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

  // p: { name, full, area, mg, lot, filled, url, form?, store? }
  function draw(x, p) {
    const A = p.area, [lt, md, dp] = TONES[A], areaName = (p.areaName || AREA_NAME[A]).toUpperCase();
    x.fillStyle = OX; x.fillRect(X0, -BL, X1 - X0, H + 2 * BL);                    // Oxblood shows in the line between the bands
    x.fillStyle = lt; x.fillRect(X0, YS[0][0], X1 - X0, YS[0][1] - YS[0][0]); x.fillStyle = md; x.fillRect(X0, YS[1][0], X1 - X0, YS[1][1] - YS[1][0]);
    // front panel: a big Oxblood logo on the light band
    { const m = document.createElement('canvas').getContext('2d'), w0 = logo(m, 0, 0, 250, OX, OX), h = Math.min(228, 250 * 940 / w0);
      logo(x, FC - w0 * h / 250 / 2, 74 + (228 - h) / 2, h, OX, OX); }
    T(x, areaName, FC, 452, { size: 70, weight: 800, fill: OX, align: 'center', ls: 8, maxW: 1060 });
    // a long name shrinks to fit; the name and fill move up together so the band never shows a gap above them
    const fs = T(document.createElement('canvas').getContext('2d'), p.name, 0, 0, { size: 400, weight: 900, maxW: 1060, ls: -10 }).fs, lift = (400 - fs) * 0.42;
    T(x, p.name, FC, 812 - lift, { size: 400, weight: 900, fill: OX, align: 'center', maxW: 1060, ls: -10 });
    T(x, String(p.mg).toUpperCase(), FC, 948 - lift - (400 - fs) * 0.15, { size: 112, weight: 900, fill: OX, align: 'center', ls: 2, maxW: 900 });
    T(x, p.full.toUpperCase(), FC, 1078, { size: 66, weight: 800, fill: OX, align: 'center', ls: 3, maxW: 1100 });
    // the Oxblood band: the research-use sentence once, whole, centred on the front and clear of the cut at both ends
    T(x, 'FOR LABORATORY RESEARCH USE ONLY  \u00b7  NOT FOR HUMAN OR VETERINARY USE', FC, 1257,
      { size: 62, weight: 600, family: "'IBM Plex Mono', ui-monospace, monospace", fill: SNOW, align: 'center', ls: 5, maxW: 2640 });
    // left side panel: a box left clear for the filler's inkjet (the lot number), and the code to the product's lot reports
    x.fillStyle = SNOW; x.fillRect(290, 78, 760, 228); x.strokeStyle = OX; x.lineWidth = 5; x.strokeRect(290, 78, 760, 228);
    T(x, 'LOT', 318, 214, { size: 64, weight: 800, fill: OX, ls: 4 });
    qr(x, p.url, 300, 404, 640, OX);
    // right side panel: the crest, the founding year, the form and how to keep it
    { const m = document.createElement('canvas').getContext('2d'), h = 430, w = logo(m, 0, 0, h, OX, OX, 'zuma-mark');
      logo(x, 2560 - w / 2, 380, h, OX, OX, 'zuma-mark'); }
    T(x, 'EST. 2026', 2560, 906, { size: 70, weight: 800, fill: OX, align: 'center', ls: 10 });
    T(x, (p.form || 'Lyophilized powder').toUpperCase(), 2560, 996, { size: 64, weight: 800, fill: OX, align: 'center', ls: 3, maxW: 760 });
    T(x, ('Store ' + (p.store || '−20 °C, dark')).toUpperCase(), 2560, 1082, { size: 64, weight: 800, fill: OX, align: 'center', ls: 3, maxW: 760 });
  }
  // a canvas with the label drawn at scale k (1 = 3200 x 1340)
  function canvas(p, k = 1) { const c = document.createElement('canvas'); c.width = Math.round(W * k); c.height = Math.round(H * k); const x = c.getContext('2d'); x.scale(k, k); draw(x, p); return c; }
  // which way to turn the vial: 0 shows the front panel, LOT_SIDE shows the code and lot record
  const LOT_SIDE = Math.PI / 2;
  root.ZUMA_LABEL_PRINT = { W, H, X0, X1, FC, TONES, AREA_NAME, PAPER, onMid, draw, canvas, logo, LOT_SIDE, FONTS: ["700 40px 'Outfit'", "800 40px 'Outfit'", "900 40px 'Outfit'"] };
})(typeof window !== 'undefined' ? window : globalThis);

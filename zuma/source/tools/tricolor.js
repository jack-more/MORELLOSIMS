// Tricolor for the lux7 render harness: the vial label comes from the site's own port (src/js/label.js, ZUMA_LABEL),
// so the stills and the live 3D vials print the same label. Also the box lid art (ported from field-bands lid()).
(() => {
  const CODE = { '01': 'RT3', '02': 'BPC', '03': 'TB5', '04': 'GHK', '05': 'IPA', '06': 'MOT' };
  const lotted = p => { const lot = (CODE[p.no] || 'ZM') + '-2610A'; return { ...p, lot, url: 'https://zuma.example/lot/' + lot }; };
  const ZL = window.ZUMA_LABEL, B = ZL.TONES, SG = "'Schibsted Grotesk', 'Helvetica Neue', sans-serif", WHITE = '#FFFFFF';
  const AREAS = ['metabolic', 'tissue', 'dermal', 'endocrine'], WORD = { metabolic: 'Metabolic', tissue: 'Tissue', dermal: 'Dermal', endocrine: 'Endocrine' };
  const bands = (x, X, W, a, ys) => ys.forEach(([t, b], i) => { x.fillStyle = B[a][i]; x.fillRect(X, t, W, b - t); });
  DIRS.push({ id: 'tricolor', name: 'Tricolor', parent: 'field', type: ['Schibsted Grotesk', 'Schibsted Grotesk'], logo: (x, X, Y, h, fill) => ZL.logo(x, X, Y, h, fill, B.metabolic[1]),
    mode: { type: 'paper', cap: p => B[p.area][2] }, stage: { sweep: '#ECE7DE', key: '#FFFFFF', tint: '#E8EEF6', gobo: 'fern' },
    label(x, p) { ZL.draw(x, lotted(p)); },
    lid(x, w, h) { x.fillStyle = ZL.PAPER; x.fillRect(0, 0, w, h);
      AREAS.forEach((a, i) => { const X = 50 + i * 578; bands(x, X, 556, a, [[50, 260], [276, 560], [576, 760]]);
        L2.T(x, WORD[a].toUpperCase(), X + 278, 690, { size: 46, weight: 900, family: SG, fill: WHITE, align: 'center', ls: 6 }); });
      ZL.logo(x, 60, 830, 80, B.metabolic[2], B.metabolic[1]);
      L2.T(x, 'THE COLLECTION · FOR LABORATORY RESEARCH USE ONLY', w - 60, 905, { size: 36, weight: 800, family: SG, fill: B.metabolic[2], align: 'right', ls: 2 }); },
    hero: { bg: B.metabolic[2], fg: WHITE, headFont: SG, textFont: SG, lines: ['Three bands.', 'One area.'], cta: B.metabolic[1], ctaInk: WHITE } });
  // the printed span of a label, flat, scaled to width w (for the "How to read" plate and the brand sheet)
  window.LABEL_FLAT = async (no, w = 1600, type = 'image/webp', q = 0.92) => { await FONTS_READY; const full = ZL.canvas(lotted(L2.P(no)), 1), sw = ZL.X1 - ZL.X0, k = w / sw;
    const c = L2.cv(w, Math.round(ZL.H * k)), x = c.getContext('2d'); x.drawImage(full, ZL.X0, 0, sw, ZL.H, 0, 0, w, c.height); return c.toDataURL(type, q); };
})();

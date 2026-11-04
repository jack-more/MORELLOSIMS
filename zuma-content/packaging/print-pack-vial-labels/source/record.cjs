// Record every drawing call the Rev 4 vial label makes on its print canvas, so it can be rebuilt as vector.
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const SRC = process.argv[2], OUT = process.argv[3];
const P = [['01','metabolic','RT-3','Retatrutide','10 mg'],['02','metabolic','TZ-2','Tirzepatide','15 mg'],['04','endocrine','TESAMORELIN','Tesamorelin','10 mg'],
 ['05','dermal','GHK-Cu','Copper peptide GHK-Cu','50 mg'],['06','metabolic','MOTS-c','MOTS-c','10 mg'],['07','endocrine','CJC+IPA','CJC-1295 + Ipamorelin','10 mg'],
 ['08','metabolic','NAD+','NAD+','500 mg'],['09','tissue','BPC+TB','BPC-157 + TB-500','10 mg'],['10','dermal','KLOW','GHK-Cu + BPC + TB + KPV','80 mg'],
 ['11','neuro','SELANK','Selank','10 mg'],['12','neuro','SEMAX','Semax','10 mg']];
(async () => {
  const b = await chromium.launch(); const p = await b.newPage(); await p.goto('file://' + path.join(SRC, 'print.html'));
  await p.waitForFunction(() => window.ZUMA_LABEL_PRINT);
  await p.evaluate(() => {
    const O = window.Path2D; window.Path2D = class extends O { constructor(d) { super(d); this._d = typeof d === 'string' ? d : (d && d._d) || null; } };
    const C = CanvasRenderingContext2D.prototype, rec = (x, o) => { if (x.canvas === window.__main) { const m = x.getTransform(); o.m = [m.a, m.b, m.c, m.d, m.e, m.f]; window.__ops.push(o); } };
    const fr = C.fillRect; C.fillRect = function (a, b2, w, h) { rec(this, { k: 'rect', x: a, y: b2, w, h, fill: this.fillStyle }); return fr.apply(this, arguments); };
    const sr = C.strokeRect; C.strokeRect = function (a, b2, w, h) { rec(this, { k: 'srect', x: a, y: b2, w, h, stroke: this.strokeStyle, lw: this.lineWidth }); return sr.apply(this, arguments); };
    const ft = C.fillText; C.fillText = function (s, X, Y) {
      if (this.canvas === window.__main) { const adv = []; for (let i = 0; i < s.length; i++) adv.push(this.measureText(s.slice(0, i + 1)).width - this.measureText(s[i]).width);   // includes the kern with the letter before
        rec(this, { k: 'text', s, x: X, y: Y, font: this.font, ls: this.letterSpacing, fill: this.fillStyle, adv, align: this.textAlign, base: this.textBaseline }); }
      return ft.apply(this, arguments); };
    const fl = C.fill; C.fill = function (a, r) { if (a instanceof Path2D) rec(this, { k: 'path', d: a._d, rule: r || 'nonzero', fill: this.fillStyle }); else rec(this, { k: 'fillcur', fill: this.fillStyle }); return fl.apply(this, arguments); };
    window.go2 = async q => { for (const f of ["900 40px Outfit", "800 40px Outfit", "700 40px Outfit", "600 40px 'IBM Plex Mono'"]) await document.fonts.load(f);
      const c = document.createElement('canvas'); c.width = 3080; c.height = 1540; const x = c.getContext('2d'); window.__main = c; window.__ops = []; x.translate(-60, 100);
      ZUMA_LABEL_PRINT.draw(x, q); return { ops: window.__ops, png: c.toDataURL('image/png') }; };
  });
  const all = {};
  for (const [no, a, n, full, mg] of P) all[no] = await p.evaluate(q => go2(q), { name: n, full, area: a, mg, url: '' });
  all['03'] = await p.evaluate(q => go2(q), { name: 'BAC WATER', full: 'Bacteriostatic water · 0.9% benzyl alcohol', area: 'supplies', mg: '10 mL', form: 'Sterile solution', store: '20–25 °C', url: '' });
  for (const no in all) { fs.writeFileSync(path.join(OUT, `ref-${no}.png`), Buffer.from(all[no].png.split(',')[1], 'base64')); all[no] = all[no].ops; }
  fs.writeFileSync(path.join(OUT, 'ops.json'), JSON.stringify(all)); console.log(Object.keys(all).map(k => k + ':' + all[k].length).join(' ')); await b.close();
})();

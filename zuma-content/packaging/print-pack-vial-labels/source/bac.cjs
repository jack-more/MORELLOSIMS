// BAC water label for the standard 10 mL vial (about Ø 24 mm, straight wall about 35 mm): the same wrap label scaled by 65/43,
// so trim is 65.0 x 30.2 mm and the bleed scales to 2.27 mm (page 69.5 x 34.8 mm). node bac.cjs
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const K = 65 / 43, PW = (46 * K).toFixed(2) + 'mm', PH = (23 * K).toFixed(2) + 'mm';
(async () => {
  const b = await chromium.launch(); const p = await b.newPage(); await p.goto('file://' + path.join(__dirname, 'print.html'));
  await p.waitForFunction(() => window.ZUMA_LABEL_PRINT && window.QRCode);
  const d = await p.evaluate(q => go(q), { name: 'BAC WATER', full: 'Bacteriostatic water · 0.9% benzyl alcohol', area: 'supplies', mg: '10 mL',
    form: 'Sterile solution', store: '20–25 °C', url: 'https://zumatides.com/lots#BAC-' });
  const art = path.join(__dirname, '..', 'art', 'zuma-label-03-art.png'); fs.writeFileSync(art, Buffer.from(d.split(',')[1], 'base64'));
  const pdf = await b.newPage();
  await pdf.setContent(`<html><head><style>@page{size:${PW} ${PH};margin:0}html,body{margin:0;padding:0}img{display:block;width:${PW};height:${PH}}</style></head><body><img src="${d}"></body></html>`);
  await pdf.pdf({ path: path.join(__dirname, '..', 'print', 'zuma-label-03-print.pdf'), width: PW, height: PH, printBackground: true, pageRanges: '1' });
  console.log('done 03', PW, PH); await b.close();
})();

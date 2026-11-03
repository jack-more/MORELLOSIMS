// The 10 mL vial labels (03 BAC water, 08 NAD+): the same art, printed at 65/43 scale, trim 65.0 x 30.2 mm, page 69.5 x 34.8 mm.
// Makes print/zuma-label-08-print.pdf from art/zuma-label-08-art.png (03 is made by bac.cjs).   node big.cjs
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const K = 65 / 43, PW = (46 * K).toFixed(2) + 'mm', PH = (23 * K).toFixed(2) + 'mm';
(async () => {
  const b = await chromium.launch(); const pdf = await b.newPage();
  for (const no of ['08']) {
    const d = fs.readFileSync(path.join(__dirname, '..', 'art', `zuma-label-${no}-art.png`)).toString('base64');
    await pdf.setContent(`<html><head><style>@page{size:${PW} ${PH};margin:0}html,body{margin:0;padding:0}img{display:block;width:${PW};height:${PH}}</style></head><body><img src="data:image/png;base64,${d}"></body></html>`);
    await pdf.pdf({ path: path.join(__dirname, '..', 'print', `zuma-label-${no}-print.pdf`), width: PW, height: PH, printBackground: true, pageRanges: '1' });
    console.log('done', no, PW, PH);
  }
  await b.close();
})();

// Print pack for the Option C wrap label: per SKU, the art with bleed (PNG, 1702 dpi), a true-size PDF (46 x 23 mm page = 43 x 20 trim + 1.5 bleed),
// and a proof with the cut and safe lines.   node print.cjs [NO ...]
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const OUT = path.join(__dirname, '..', 'printpack');
const P = [['01','metabolic','RT-3','Retatrutide','10 mg','RT3'],['02','metabolic','TZ-2','Tirzepatide','15 mg','TZ2'],['04','endocrine','TESAMORELIN','Tesamorelin','10 mg','TES'],
 ['05','dermal','GHK-Cu','Copper peptide GHK-Cu','50 mg','GHK'],['06','metabolic','MOTS-c','MOTS-c','10 mg','MOT'],['07','endocrine','CJC+IPA','CJC-1295 + Ipamorelin','10 mg','CJI'],
 ['08','metabolic','NAD+','NAD+','500 mg','NAD'],['09','tissue','BPC+TB','BPC-157 + TB-500','10 mg','BPT'],['10','dermal','GHK+BT','GHK-Cu + BPC + TB','70 mg','GBT'],
 ['11','neuro','SELANK','Selank','10 mg','SEL'],['12','neuro','SEMAX','Semax','10 mg','SMX']];
const only = process.argv.slice(2);
(async () => {
  const b = await chromium.launch(); const p = await b.newPage(); await p.goto('file://' + path.join(__dirname, 'print.html'));
  await p.waitForFunction(() => window.ZUMA_LABEL_PRINT && window.QRCode);
  const pdf = await b.newPage();
  for (const [no, a, n, full, mg, c] of P) {
    if (only.length && !only.includes(no)) continue;
    const d = await p.evaluate(q => go(q), { name: n, full, area: a, mg, url: 'https://zumatides.com/lots#' + c + '-' });
    const png = path.join(OUT, `zuma-label-${no}-art.png`); fs.writeFileSync(png, Buffer.from(d.split(',')[1], 'base64'));
    await pdf.setContent(`<html><head><style>@page{size:46mm 23mm;margin:0}html,body{margin:0;padding:0}img{display:block;width:46mm;height:23mm}</style></head><body><img src="data:image/png;base64,${d.split(',')[1]}"></body></html>`);
    await pdf.pdf({ path: path.join(OUT, `zuma-label-${no}-print.pdf`), width: '46mm', height: '23mm', printBackground: true, pageRanges: '1' });
    console.log('done', no);
  }
  await b.close();
})();

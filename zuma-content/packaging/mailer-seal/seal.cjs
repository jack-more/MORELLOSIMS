const { chromium } = require('playwright'); const path = require('path');
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 800, height: 800 }, deviceScaleFactor: 4 });
  for (const n of ['oxblood', 'snow']) { await p.goto('file://' + path.join(__dirname, `seal-${n}.html`)); await p.waitForTimeout(1500);
    await p.pdf({ path: path.join(__dirname, `zuma-seal-2in-${n}.pdf`), width: '54.8mm', height: '54.8mm', printBackground: true, pageRanges: '1' });
    await (await p.$('svg:last-of-type')).screenshot({ path: path.join(__dirname, `zuma-seal-2in-${n}.png`) }); }
  await b.close(); })();

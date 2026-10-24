const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1123, height: 794 }, deviceScaleFactor: 1.5 });
  await p.goto('file://' + process.argv[2]); await p.waitForTimeout(2000);
  await p.pdf({ path: process.argv[3], format: 'A4', landscape: true, printBackground: true, preferCSSPageSize: true });
  await p.screenshot({ path: process.argv[4], fullPage: true }); await b.close(); })();

const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1500, height: 500 }, deviceScaleFactor: 2 });
  await p.goto('file://' + process.argv[2]); await p.waitForTimeout(2500); await (await p.$('#h')).screenshot({ path: process.argv[3] }); await b.close(); })();

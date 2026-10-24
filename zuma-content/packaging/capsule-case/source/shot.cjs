const { chromium } = require('playwright'); const [, , html, png, w, h] = process.argv;
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: +w, height: +h } });
  await p.goto('file://' + html); await p.screenshot({ path: png }); await b.close(); })();

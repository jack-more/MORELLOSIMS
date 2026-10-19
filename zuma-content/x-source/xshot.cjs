// node xshot.cjs : screenshots xbanner.html at 3000x1000 -> cyc/xk/x-banner.png
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 3000, height: 1000 } });
  await p.goto('http://127.0.0.1:8772/xbanner.html'); await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(300);
  await (await p.$('.b')).screenshot({ path: 'cyc/xk/x-banner.png' }); await b.close(); console.log('ok');
})();

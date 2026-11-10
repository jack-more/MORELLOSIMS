const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1600, height: 2100 } });
  await p.goto('file://' + process.cwd() + '/tex.html'); await p.waitForTimeout(300);
  for (const id of ['sign', 'tag', 'strap']) await p.locator('#' + id).screenshot({ path: id + '-mask.png' });
  await b.close();
})();

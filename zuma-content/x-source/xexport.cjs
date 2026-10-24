const { chromium } = require('playwright'); const D = process.argv[2], OUT = process.argv[3];
(async () => { const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1700, height: 1200 }, deviceScaleFactor: 2 });
  await p.goto('file://' + D + '/brandbook.html'); await p.waitForTimeout(1500);
  await p.addStyleTag({ content: `.bb-xh{width:1500px!important;max-width:none!important}.bb-story{width:540px!important;max-width:none!important}` });
  await p.evaluate(() => window.dispatchEvent(new Event('resize'))); await p.waitForTimeout(1500);
  await (await p.$('.bb-xh')).screenshot({ path: OUT + '/x-header-refined-3000.png' });
  await (await p.$('.bb-story')).screenshot({ path: OUT + '/end-card-9x16.png' });
  await b.close(); })();

const { chromium } = require('playwright'); const D = process.argv[2], OUT = process.argv[3];
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 2100, height: 1400 }, deviceScaleFactor: 1 });
  await p.goto('file://' + D + '/brandbook.html'); await p.waitForTimeout(1200);
  await p.addStyleTag({ content: `.bb-story{width:1920px!important;max-width:none!important;aspect-ratio:16/9!important;gap:3.2cqi!important}.bb-story svg{width:34cqi!important}.bb-story p{font-size:5.4cqi!important}.bb-story span{bottom:4cqi!important;font-size:1.8cqi!important}` });
  await p.evaluate(() => window.dispatchEvent(new Event('resize'))); await p.waitForTimeout(1500);
  await (await p.$('.bb-story')).screenshot({ path: OUT }); await b.close(); })();

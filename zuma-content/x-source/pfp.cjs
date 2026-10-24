const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 800, height: 800 } });
  for (const k of ['A','B','C']) { await p.goto('file://' + process.argv[2] + '/pfp-' + k + '.html'); await p.waitForTimeout(1500); await (await p.$('.p')).screenshot({ path: process.argv[2] + '/xout/x-pfp-' + k + '.png' }); }
  await b.close(); })();

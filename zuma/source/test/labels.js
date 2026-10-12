// node labels.js outdir : full-wrap label artwork (3200 x 1340 PNG) for every product, printed by js/label.js on the built site
const { chromium } = require('playwright'); const fs = require('fs');
(async () => { const b = await chromium.launch({ args: ['--proxy-server=' + process.env.HTTPS_PROXY, '--proxy-bypass-list=127.0.0.1;localhost', '--ignore-certificate-errors'] });
  const p = await b.newPage(); await p.goto('http://127.0.0.1:8772/site3/dist/shop.html', { waitUntil: 'networkidle' });
  await p.evaluate(() => Promise.all(window.ZUMA_LABEL.FONTS.map(f => document.fonts.load(f)))); await p.waitForTimeout(1500);
  const urls = await p.evaluate(() => window.ZUMA.P.map(pr => window.ZUMA_LABEL.canvas(window.ZUMA.labelData(pr), 1).toDataURL('image/png')));
  urls.forEach((u, i) => { const f = `${process.argv[2]}/label-${String(i + 1).padStart(2, '0')}.png`; fs.writeFileSync(f, Buffer.from(u.split(',')[1], 'base64')); console.log(f); });
  await b.close(); })();

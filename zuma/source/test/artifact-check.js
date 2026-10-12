const { chromium } = require('playwright');
(async () => { const b = await chromium.launch({ args: ['--proxy-server=' + process.env.HTTPS_PROXY, '--proxy-bypass-list=127.0.0.1;localhost', '--ignore-certificate-errors', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 860 } }); const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); }); p.on('requestfailed', r => errs.push('failed ' + r.url()));
  await p.goto('http://127.0.0.1:8782/index.html', { waitUntil: 'networkidle' }); const live = await p.waitForSelector('#grid.live', { timeout: 60000 }).then(() => true, () => false);
  await p.waitForTimeout(2000); await p.screenshot({ path: __dirname + '/shots/artifact-top.png' });
  const info = await p.evaluate(() => ({ mode: document.compatMode, title: document.title, logo: !!document.getElementById('zuma-logo'), imgs: [...document.images].filter(i => i.complete && i.naturalWidth === 0 && i.loading !== 'lazy').map(i => i.src) }));
  console.log(JSON.stringify({ live, errs, ...info })); await b.close(); })();

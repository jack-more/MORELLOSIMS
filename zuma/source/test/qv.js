const { chromium } = require('playwright');
(async () => { const b = await chromium.launch({ args: ['--proxy-server=' + process.env.HTTPS_PROXY, '--proxy-bypass-list=127.0.0.1;localhost', '--ignore-certificate-errors', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('http://127.0.0.1:8772/site3/dist/shop.html', { waitUntil: 'networkidle' }); await p.waitForTimeout(5000);
  await p.hover('#grid .z-pcard[data-no="04"] .z-pic', { force: true }); await p.waitForTimeout(400);
  const t0 = Date.now(); await p.click('#grid .z-pcard[data-no="04"] [data-quick]');
  await p.waitForSelector('#drawer.on', { timeout: 20000 }); console.log('drawer on after', Date.now() - t0, 'ms');
  await p.waitForTimeout(2500); await p.screenshot({ path: 'shots/flow-3-quickview.png' }); console.log('errors', errs.join('|') || 'none'); await b.close(); })();

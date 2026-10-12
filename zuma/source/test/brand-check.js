const { chromium } = require('playwright');
(async () => { const b = await chromium.launch({ args: ['--proxy-server=' + process.env.HTTPS_PROXY, '--proxy-bypass-list=127.0.0.1;localhost', '--ignore-certificate-errors'] });
  for (const [tag, w, h] of [['d', 1440, 900], ['m', 390, 844]]) { const p = await b.newPage({ viewport: { width: w, height: h } }); const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    await p.goto('http://127.0.0.1:8781/brand.html', { waitUntil: 'networkidle' });
    for (const [n, s] of [['logo', '#logo'], ['label', '#label'], ['images', '#images'], ['end', '.foot']]) { await p.evaluate(s => { const el = document.querySelector(s); window.scrollTo({ top: el.getBoundingClientRect().top + scrollY - 10, behavior: 'instant' }); }, s); await p.waitForTimeout(700); await p.screenshot({ path: `${__dirname}/shots/${tag}-brand-${n}.png` }); }
    const o = await p.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]); console.log(tag, JSON.stringify({ errs, overflow: o[0] > o[1] })); await p.close(); }
  await b.close(); })();

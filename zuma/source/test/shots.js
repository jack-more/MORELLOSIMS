// node shots.js [page] : full-page screenshots of dist/<page> at 1440 and 390, cut into viewport-height slices, plus errors
const { chromium } = require('playwright'); const fs = require('fs');
const page = process.argv[2] || 'index.html', out = __dirname + '/shots';
(async () => { const b = await chromium.launch({ args: ['--proxy-server=' + process.env.HTTPS_PROXY, '--proxy-bypass-list=127.0.0.1;localhost', '--ignore-certificate-errors', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  for (const [tag, w, h, mobile] of [['d', 1440, 900, false], ['m', 390, 844, true]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, isMobile: mobile, hasTouch: mobile });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    await p.goto('http://127.0.0.1:8772/site3/dist/' + page, { waitUntil: 'networkidle', timeout: 120000 }); await p.waitForTimeout(6000);
    const H = await p.evaluate(() => document.documentElement.scrollHeight); const sw = await p.evaluate(() => document.documentElement.scrollWidth);
    for (let y = 0, k = 0; y < H; y += h, k++) { await p.evaluate(y => scrollTo(0, y), y); await p.waitForTimeout(700); await p.screenshot({ path: `${out}/${page.split('.')[0]}-${tag}-${String(k).padStart(2, '0')}.png` }); }
    console.log(tag, 'height', H, 'scrollWidth', sw, 'errors:', errs.join(' | ') || 'none'); await ctx.close(); }
  await b.close(); })();

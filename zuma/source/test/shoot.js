// usage: node test/shoot.js [base-url] [outdir] -> screenshots of the shop and brand sheet at 1440 and 390, console errors, overflow
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const BASE = process.argv[2] || 'http://127.0.0.1:8781/', OUT = process.argv[3] || path.join(__dirname, 'shots'); fs.mkdirSync(OUT, { recursive: true });
const only = (process.env.ONLY || '').split(',').filter(Boolean);
(async () => {
  const b = await chromium.launch({ args: ['--proxy-server=' + process.env.HTTPS_PROXY, '--proxy-bypass-list=127.0.0.1;localhost', '--ignore-certificate-errors', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const report = [];
  for (const [tag, w, h, mobile] of [['d', 1440, 900, false], ['m', 390, 844, true]]) {
    if (only.length && !only.includes(tag)) continue;
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: mobile ? 2 : 1, isMobile: mobile, hasTouch: mobile });
    const p = await ctx.newPage(); const errs = [];
    p.on('pageerror', e => errs.push('pageerror: ' + e.message)); p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
    p.on('requestfailed', r => errs.push('requestfailed: ' + r.url() + ' ' + (r.failure() || {}).errorText));
    await p.goto(BASE + 'index.html', { waitUntil: 'networkidle', timeout: 120000 });
    const live = await p.waitForSelector('#grid.live', { timeout: 60000 }).then(() => true, () => false);
    await p.waitForTimeout(2500);
    const shot = async name => { await p.screenshot({ path: `${OUT}/${tag}-${name}.png` }); };
    const at = async sel => { await p.evaluate(s => { const el = document.querySelector(s); window.scrollTo(0, el.getBoundingClientRect().top + scrollY - 112); }, sel); await p.waitForTimeout(900); };
    await shot('top');
    const over = async where => { const o = await p.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, bw: document.body.scrollWidth })); if (o.sw > o.cw || o.bw > o.cw) errs.push(`overflow at ${where}: ${JSON.stringify(o)}`); };
    await over('load');
    for (const [n, s] of [['rule', '.arearule'], ['collection', '#series'], ['collection2', '#grid .cell:nth-child(4)'], ['sets', '#sets'], ['read', '#read'], ['lots', '#lots'], ['box', '#set'], ['token', '#token'], ['token2', '.tblocks'], ['ref', '#referrals'], ['ladder', '.ladder'], ['dash', '.dash'], ['rules', '.rules'], ['about', '#about'], ['foot', '.foot']]) { await at(s); await shot(n); }
    // hover a cell (desktop) to turn it to the lot side
    if (!mobile) { await at('#series'); await p.hover('#grid .cell:nth-child(2) .c1'); await p.waitForTimeout(1500); await shot('hover'); }
    // hero area switch
    await p.evaluate(() => window.scrollTo(0, 0)); await p.click('[data-hero="3"]'); await p.waitForTimeout(1600); await shot('hero-dermal'); await p.click('[data-hero="4"]'); await p.waitForTimeout(1600); await shot('hero-endo'); await p.click('[data-hero="0"]');
    // drawer
    await at('#series'); await p.click('#grid .cell:nth-child(1) .choose'); await p.waitForTimeout(1800); await shot('drawer');
    await p.click('#t-back'); await p.waitForTimeout(1500); await shot('drawer-lot');
    await p.evaluate(() => document.querySelector('#drawer .pbody').scrollTo(0, 9999)); await p.waitForTimeout(400); await shot('drawer-end');
    await p.click('#d-add'); await p.waitForTimeout(300); await p.click('#drawer [data-close]'); await p.waitForTimeout(500);
    // cart
    await p.click('#cartbtn'); await p.waitForTimeout(700); await shot('cart');
    await p.check('#c-ok'); await p.click('#c-go'); await p.waitForTimeout(300); await shot('cart-ok');
    await p.click('#c-crypto'); await p.waitForTimeout(400); await shot('launch'); await p.click('#l-close'); await p.click('#cart [data-close]'); await p.waitForTimeout(500);
    // token buttons
    await at('.tactions'); await p.click('[data-launch="wallet"]'); await p.waitForTimeout(300); await shot('launch-wallet'); await p.click('#l-close');
    if (mobile) { await p.evaluate(() => window.scrollTo(0, 0)); await p.click('#menubtn'); await p.waitForTimeout(300); await shot('menu'); await p.click('#menubtn'); }
    await over('end');
    // brand sheet
    await p.goto(BASE + 'brand.html', { waitUntil: 'networkidle', timeout: 120000 }); await p.waitForTimeout(800); await over('brand');
    await p.screenshot({ path: `${OUT}/${tag}-brand-full.png`, fullPage: true });
    report.push({ tag, live, errs }); await ctx.close();
  }
  console.log(JSON.stringify(report, null, 1)); await b.close();
})();

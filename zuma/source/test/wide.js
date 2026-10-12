// node wide.js page : list elements wider than the phone viewport
const { chromium } = require('playwright');
(async () => { const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }); const p = await ctx.newPage();
  await p.goto('http://127.0.0.1:8772/site3/dist/' + process.argv[2], { waitUntil: 'networkidle' }); await p.waitForTimeout(3000);
  console.log(await p.evaluate(() => [...document.querySelectorAll('body *')].filter(e => { const r = e.getBoundingClientRect(); return r.right > 392 && r.width > 0 && !e.closest('.scroll'); })
    .slice(0, 12).map(e => e.tagName + '.' + [...e.classList].join('.') + '#' + e.id + ' right=' + Math.round(e.getBoundingClientRect().right) + ' hidden-parent=' + !!e.closest('[hidden]')).join('\n')));
  await b.close(); })();

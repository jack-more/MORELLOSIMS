const { chromium } = require('playwright');
(async () => { const b = await chromium.launch({ args: ['--proxy-server=' + process.env.HTTPS_PROXY, '--proxy-bypass-list=127.0.0.1;localhost', '--ignore-certificate-errors', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }); const p = await ctx.newPage();
  await p.goto('http://127.0.0.1:8772/site3/dist/' + process.argv[2], { waitUntil: 'networkidle' }); await p.waitForTimeout(7000);
  console.log(await p.evaluate(() => { const out = [document.documentElement.scrollWidth, document.body.scrollWidth, innerWidth].join(' ');
    const all = [...document.querySelectorAll('*')].map(e => [e, e.getBoundingClientRect().right]).filter(([e]) => !e.closest('.carousel,.scroll')).sort((a, b) => b[1] - a[1]).slice(0, 8);
    return out + '\n' + all.map(([e, r]) => e.tagName + '.' + [...e.classList].join('.') + '#' + e.id + ' ' + Math.round(r) + ' ' + getComputedStyle(e).position).join('\n'); }));
  await b.close(); })();

const { chromium } = require('playwright');
(async () => { const b = await chromium.launch({ args: ['--proxy-server=' + process.env.HTTPS_PROXY, '--proxy-bypass-list=127.0.0.1;localhost', '--ignore-certificate-errors', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true }); const p = await ctx.newPage();
  await p.goto('http://127.0.0.1:8772/site3/dist/' + process.argv[2], { waitUntil: 'networkidle', timeout: 120000 });
  for (const t of [0, 2000, 4000, 6000]) { await p.waitForTimeout(t ? 2000 : 0);
    console.log(t, await p.evaluate(() => { const sw = document.documentElement.scrollWidth; if (sw <= 391) return sw;
      const all = [...document.querySelectorAll('*')].filter(e => !e.closest('.carousel,.scroll')).map(e => [e, e.getBoundingClientRect().right]).sort((a, b) => b[1] - a[1]).slice(0, 5);
      return sw + ' ' + all.map(([e, r]) => e.tagName + '.' + [...e.classList].join('.') + '#' + e.id + ' ' + Math.round(r) + ' ' + getComputedStyle(e).position).join(' | '); })); }
  await b.close(); })();

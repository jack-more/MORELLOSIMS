const { chromium } = require('playwright');
(async () => { const b = await chromium.launch();
  for (const [w,h,n] of [[1440,900,'d'],[390,844,'m']]) {
    const p = await (await b.newContext({ viewport:{width:w,height:h}, isMobile:n==='m' })).newPage();
    await p.goto('http://127.0.0.1:8772/site3/dist/index.html', { waitUntil:'networkidle' }); await p.waitForTimeout(1500);
    await p.screenshot({ path: process.argv[2]+'/hero-'+n+'.png' }); }
  await b.close(); })();

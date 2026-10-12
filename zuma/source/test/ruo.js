const { chromium } = require('playwright');
(async () => { const b = await chromium.launch();
  for (const [w,n] of [[1280,'d'],[390,'m']]) { const p = await (await b.newContext({ viewport:{width:w,height:900} })).newPage();
    await p.goto('file://'+process.argv[2]); await p.waitForTimeout(1500);
    console.log(n, await p.evaluate(()=>document.documentElement.scrollWidth));
    await p.screenshot({ path: process.argv[3]+'/ruo-'+n+'.png', fullPage:true }); }
  await b.close(); })();

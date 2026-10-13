const { chromium } = require('playwright');
(async () => { const b = await chromium.launch();
  for (const [w,n,dark] of [[1280,'d',false],[390,'m',true]]) { const p = await (await b.newContext({ viewport:{width:w,height:900}, colorScheme: dark?'dark':'light' })).newPage();
    await p.goto('file://'+process.argv[2]); await p.waitForTimeout(1200);
    console.log(n, 'scrollW', await p.evaluate(()=>document.documentElement.scrollWidth));
    await p.screenshot({ path: process.argv[3]+'/pp-'+n+'.png', fullPage:true }); }
  await b.close(); })();

const { chromium } = require('playwright');
(async () => { const b = await chromium.launch({ args: ['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'] });
  const p = await (await b.newContext({ viewport:{width:1440,height:900} })).newPage();
  await p.goto('file://'+process.argv[2], { waitUntil:'load', timeout:20000 }).catch(e=>console.log('goto',e.message)); await p.waitForTimeout(4000);
  const H = await p.evaluate(()=>document.documentElement.scrollHeight); console.log('H',H);
  for (let i=0, y=0; y<H && i<8; i++, y+=900) { await p.evaluate(y=>window.scrollTo(0,y), y); await p.waitForTimeout(800);
    await p.screenshot({ path: process.argv[3]+'/valt-'+i+'.png', timeout:60000, animations:'disabled' }).catch(e=>console.log('shot',i,e.message.slice(0,80))); }
  await b.close(); })();

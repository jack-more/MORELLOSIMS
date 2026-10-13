const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await (await b.newContext({ viewport:{width:4080,height:3300} })).newPage();
  for (const no of process.argv.slice(3)) { await p.goto('file://'+process.argv[2]+'/html/carton-'+no+'.html'); await p.waitForSelector('body[data-ready]'); await p.waitForTimeout(300);
    await p.screenshot({ path: process.argv[2]+'/png/carton-'+no+'.png' }); console.log(no); }
  await b.close(); })();

const { chromium } = require('playwright');
const U = 'http://127.0.0.1:8772/site3/dist/', O = process.argv[2];
(async () => { const b = await chromium.launch();
  const ctx = await b.newContext({ viewport:{width:1440,height:900} }); const p = await ctx.newPage(); const errs=[]; p.on('pageerror',e=>errs.push(e.message));
  await p.goto(U+'index.html',{waitUntil:'networkidle'}); await p.waitForTimeout(800); await p.screenshot({path:O+'/v3-home.png'});
  await p.evaluate(()=>scrollTo(0,1400)); await p.waitForTimeout(500); await p.screenshot({path:O+'/v3-home-scrolled.png'});
  await p.goto(U+'build.html',{waitUntil:'networkidle'}); await p.waitForTimeout(600);
  for (const no of ['02','04','06']) await p.click(`[data-pick="${no}"]`);
  await p.click('.bcard[data-no="02"] [data-bq="1"]'); await p.click('#bp-rep'); await p.waitForTimeout(300);
  await p.screenshot({path:O+'/v3-build.png'});
  console.log('total', await p.textContent('#bp-total'), '|', await p.textContent('#bp-save-l'), '|', await p.textContent('#bld-count'));
  await p.click('#bp-add'); await p.waitForTimeout(300); console.log('cart', await p.textContent('#cartn'));
  await p.click('#cartbtn'); await p.waitForTimeout(600); await p.screenshot({path:O+'/v3-cart.png'});
  await p.goto(U+'lots.html',{waitUntil:'networkidle'}); await p.fill('#lib-q','2609'); await p.waitForTimeout(300); console.log('lots', await p.textContent('#lib-count'));
  await p.screenshot({path:O+'/v3-lots.png'}); await p.click('#lib-rows [data-coa]'); await p.waitForTimeout(400); console.log('coa lot', await p.evaluate(()=>document.querySelector('#coa-card').innerText.match(/([A-Z0-9]+-\d{4}A)/)[1]));
  await p.goto(U+'bpc-157.html',{waitUntil:'networkidle'}); await p.waitForTimeout(600); await p.screenshot({path:O+'/v3-pdp.png'});
  const m = await (await b.newContext({ viewport:{width:390,height:844}, isMobile:true, hasTouch:true })).newPage(); m.on('pageerror',e=>errs.push(e.message));
  for (const [f,n] of [['index.html','home'],['build.html','build'],['lots.html','lots']]) { await m.goto(U+f,{waitUntil:'networkidle'}); await m.waitForTimeout(600);
    if (n==='build') { await m.tap('[data-pick="02"]'); await m.tap('[data-pick="05"]'); await m.waitForTimeout(300); }
    console.log(n,'scrollW',await m.evaluate(()=>document.documentElement.scrollWidth)); await m.screenshot({path:O+'/v3-m-'+n+'.png'}); }
  console.log('errors', errs.length, errs.slice(0,3)); await b.close(); })();

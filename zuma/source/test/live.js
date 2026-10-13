const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const U='https://kaleidoscopic-lollipop-7a87dd.netlify.app';
  for (const [w,h,n,m] of [[1440,900,'d',false],[390,844,'m',true]]) { const p = await (await b.newContext({ viewport:{width:w,height:h}, isMobile:m })).newPage();
    const errs=[]; p.on('pageerror',e=>errs.push(e.message)); p.on('response',r=>{ if(r.status()>=400) errs.push(r.status()+' '+r.url()); });
    for (const path of ['/','/shop.html','/rt-3.html']) { await p.goto(U+path,{waitUntil:'networkidle'}); await p.waitForTimeout(800); }
    await p.goto(U+'/',{waitUntil:'networkidle'}); await p.waitForTimeout(1200); await p.screenshot({path:process.argv[2]+'/live-'+n+'.png'});
    console.log(n,'errors:',errs.length, errs.slice(0,3).join(' | ')); }
  await b.close(); })();

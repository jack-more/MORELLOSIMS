const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await (await b.newContext({ viewport:{width:1440,height:900} })).newPage();
  const errs=[]; p.on('pageerror',e=>errs.push(e.message));
  await p.goto('http://127.0.0.1:8772/site3/dist/index.html', { waitUntil:'networkidle' }); await p.waitForTimeout(1000);
  const a = await p.$('.hero-anchor'); const r = await a.boundingBox(); const x=r.x+r.width/2, y=r.y+r.height/2;
  await p.mouse.move(x,y); await p.mouse.down(); for (let i=1;i<=10;i++) await p.mouse.move(x+i*14,y); await p.waitForTimeout(600);
  console.log('src', await p.evaluate(()=>{const i=document.querySelector('.hero-anchor img'); return i&&i.currentSrc}));
  await p.screenshot({ path: process.argv[2]+'/hero-drag.png' }); await p.mouse.up(); console.log('errors', errs.length, errs[0]||'');
  await b.close(); })();

const { chromium } = require('playwright');
const P=[['01','metabolic','RT-3','10 mg','RT3-2610A'],['05','dermal','GHK-Cu','50 mg','GHK-2610A'],['09','tissue','BPC+TB','10 mg','BPT-2610A']];
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:2513,height:1000}});
for(const [no,a,n,f,l] of P){
 await p.goto('file://'+process.cwd()+`/label9.html?a=${a}&n=${encodeURIComponent(n)}&f=${encodeURIComponent(f)}&l=${l}`);
 await p.waitForFunction(()=>document.body.dataset.ready,null,{timeout:20000});await p.waitForTimeout(200);
 await (await p.$('#L')).screenshot({path:`lP-${no}.png`,omitBackground:true});}
await b.close();console.log('ok');})();

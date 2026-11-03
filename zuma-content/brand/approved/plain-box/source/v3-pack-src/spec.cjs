const {chromium}=require('playwright');const path=require('path');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1123,height:794},deviceScaleFactor:2});
await p.goto('file://'+path.resolve('spec.html'));await p.waitForTimeout(800);
await p.pdf({path:'ZUMA-Plain-Carton-v3B-Production-Spec.pdf',width:'297mm',height:'210mm',printBackground:true,preferCSSPageSize:true});
const pgs=await p.$$('.pg');for(let i=0;i<pgs.length;i++){await pgs[i].screenshot({path:`preview/spec-page-${i+1}.png`});}
await b.close();})();

// production print files: one-colour vector PDF at true size (50.27 x 20 mm wrap) plus a 50 px/mm PNG proof, per SKU
const { chromium } = require('playwright');
const P=[['01','metabolic','RT-3','10 mg'],['02','metabolic','TZ-2','15 mg'],['04','endocrine','Tesamorelin','10 mg'],['05','dermal','GHK-Cu','50 mg'],
 ['06','metabolic','MOTS-c','10 mg'],['07','endocrine','CJC+IPA','10 mg'],['08','metabolic','NAD+','500 mg'],['09','tissue','BPC+TB','10 mg'],
 ['10','dermal','GHK+BT','70 mg'],['11','neuro','Selank','10 mg'],['12','neuro','Semax','10 mg']];
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:2513,height:1000}});
for(const [no,a,n,f] of P){
 await p.goto('file://'+process.cwd()+`/label10.html?v=2&a=${a}&n=${encodeURIComponent(n)}&f=${encodeURIComponent(f)}&l=&ink=%236E1C2A`);
 await p.waitForFunction(()=>document.body.dataset.ready,null,{timeout:20000});await p.waitForTimeout(150);
 await (await p.$('#L')).screenshot({path:`prod/print-${no}.png`,omitBackground:true});
 await p.addStyleTag({content:'@page{size:50.27mm 20mm;margin:0}html,body{width:50.27mm;height:20mm;overflow:hidden}#L{transform:scale('+(50.27*96/25.4/2513)+');transform-origin:0 0}'});
 await p.pdf({path:`prod/print-${no}.pdf`,width:'50.27mm',height:'20mm',printBackground:false,pageRanges:'1'});
 const slug=n.replace(/[^A-Za-z0-9]+/g,'-');console.log(no,slug);}
await b.close();})();

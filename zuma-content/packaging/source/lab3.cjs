const { chromium } = require('playwright');
const T={metabolic:['#A3CEFF','#1F4FD8','#0B1F5C'],tissue:['#ABE9C3','#0E9A5B','#0A3B26'],dermal:['#FFB7C5','#FF5A1F','#9E1717'],endocrine:['#FFE97A','#D08000','#5E3C00'],neuro:['#D9C8FF','#6E3FD8','#2A1263']};
const P=[['01','metabolic','RT-3','10 mg','RT3-2610A'],['05','dermal','GHK-Cu','50 mg','GHK-2610A'],['09','tissue','BPC+TB','10 mg','BPT-2610A'],['04','endocrine','Tesamorelin','10 mg','TES-2610A'],['11','neuro','Selank','10 mg','SEL-2610A']];
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:2513,height:1000}});
for(const o of ['A','B','C']) for(const [no,a,n,f,l] of P){const [lt,br,dp]=T[a];
 await p.goto('file://'+process.cwd()+`/label3.html?o=${o}&a=${a}&n=${encodeURIComponent(n)}&f=${encodeURIComponent(f)}&l=${l}&lt=${encodeURIComponent(lt)}&br=${encodeURIComponent(br)}&dp=${encodeURIComponent(dp)}`);
 await p.waitForFunction(()=>document.body.dataset.ready,null,{timeout:20000});await p.waitForTimeout(200);
 await (await p.$('#L')).screenshot({path:`l${o}-${no}.png`,omitBackground:o==='A'});}
await b.close();console.log('ok');})();

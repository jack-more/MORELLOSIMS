const { chromium } = require('playwright'); const fs=require('fs');
const P=[['01','metabolic','RT-3','Retatrutide','10 mg','RT3'],['02','metabolic','TZ-2','Tirzepatide','15 mg','TZ2'],['04','endocrine','TESAMORELIN','Tesamorelin','10 mg','TES'],
 ['05','dermal','GHK-Cu','Copper peptide GHK-Cu','50 mg','GHK'],['06','metabolic','MOTS-c','MOTS-c','10 mg','MOT'],['07','endocrine','CJC+IPA','CJC-1295 + Ipamorelin','10 mg','CJI'],
 ['08','metabolic','NAD+','NAD+','500 mg','NAD'],['09','tissue','BPC+TB','BPC-157 + TB-500','10 mg','BPT'],['10','dermal','GHK+BT','GHK-Cu + BPC + TB','70 mg','GBT'],
 ['03','supplies','BAC WATER','Bacteriostatic water','10 mL','BAC'],['11','neuro','SELANK','Selank','10 mg','SEL'],['12','neuro','SEMAX','Semax','10 mg','SMX']];
(async()=>{const b=await chromium.launch();const p=await b.newPage();await p.goto('file://'+process.cwd()+'/og2.html');await p.waitForFunction(()=>window.ZUMA_LABEL&&window.QRCode);
for(const [no,a,n,full,mg,c] of P){const d=await p.evaluate(q=>go(q),{name:n,full,area:a,mg,form:no==='03'?'0.9% benzyl alcohol':undefined,store:no==='03'?'20–25 °C':undefined,lot:c+'-2610A',filled:'10.10.2026',url:'https://zumatides.com/lots#'+c+'-2610A'});
 fs.writeFileSync(`../tex2/label-${no}.png`,Buffer.from(d.split(',')[1],'base64'));}
await b.close();console.log('ok')})();

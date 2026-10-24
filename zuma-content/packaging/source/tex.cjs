const { chromium } = require('playwright');
const J=[['dermal','11','palm','4'],['metabolic','8','bamboo','7'],['tissue','14','palm','6'],['endocrine','5','bamboo','5'],['neuro','21','palm','8']];
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1800,height:1800},deviceScaleFactor:1});
for(const [a,s,bh,bs] of J){await p.goto('file://'+process.cwd()+`/tex.html?a=${a}&s=${s}&b=${bh}&bs=${bs}`);
 await p.waitForSelector('canvas[data-painted]');await (await p.$('#c')).screenshot({path:`lb-${a}.png`});}
await b.close();console.log('ok')})();

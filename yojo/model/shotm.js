const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();
for (const [n,w,h] of [['egg',2400,1840],['head',1600,1600]]){const p=await b.newPage({viewport:{width:w,height:h}});await p.goto('file://'+process.cwd()+'/'+n+'.html');await p.evaluate(()=>document.fonts.ready);await p.waitForTimeout(300);
const tw=await p.evaluate(()=>{const t=document.getElementById('t');return t?t.getBBox().width/20:null});console.log(n,'text width mm',tw);
await p.screenshot({path:n+'-mask.png'});}
await b.close()})()

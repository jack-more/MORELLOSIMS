const {chromium}=require('playwright');const path=require('path');const fs=require('fs');
(async()=>{const b=await chromium.launch();const p=await b.newPage({deviceScaleFactor:1});
for(const [f,w,h] of [['look-B.html',3000,2000],['flat-B.html',3300,1400]]){await p.setViewportSize({width:w,height:h});await p.goto('file://'+path.resolve(f));await p.waitForTimeout(1500);await p.screenshot({path:'preview/'+f.replace('.html','.png')});}
await p.setViewportSize({width:1605,height:1560});
for(const f of fs.readdirSync('svg')){await p.setContent(`<body style="margin:0;background:#fff"><img src="file://${path.resolve('svg/'+f)}" style="width:1605px">`);await p.waitForTimeout(150);await p.screenshot({path:'preview/'+f.replace('.svg','.png')});}
await b.close();})();

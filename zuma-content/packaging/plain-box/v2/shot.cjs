const {chromium}=require('playwright');const D=process.argv[2];const names=process.argv.slice(3);
(async()=>{const b=await chromium.launch();for(const n of names){const html=require('fs').readFileSync(`${D}/${n}.html`,'utf8');
const m=html.match(/width:(\d+)px;height:(\d+)px;overflow/);const p=await b.newPage({viewport:{width:+m[1],height:+m[2]}});
await p.setContent(html,{waitUntil:'networkidle'});await p.evaluate(()=>document.fonts.ready);await p.waitForTimeout(400);
await p.screenshot({path:`${D}/${n}.png`});await p.close();console.log('ok',n)}await b.close()})();

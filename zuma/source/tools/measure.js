// measures the ZUMA wordmark in Schibsted Grotesk 800 (used to size the logo slot's viewBox)
const { chromium } = require('playwright');
(async () => { const b = await chromium.launch({ args: ['--proxy-server=' + process.env.HTTPS_PROXY, '--proxy-bypass-list=127.0.0.1;localhost', '--ignore-certificate-errors'] });
  const p = await b.newPage();
  await p.setContent(`<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@500..900&display=block"><p style="font-family:'Schibsted Grotesk'">x</p>`, { waitUntil: 'networkidle' });
  const r = await p.evaluate(async () => { await document.fonts.load("800 115px 'Schibsted Grotesk'"); const c = document.createElement('canvas').getContext('2d');
    c.font = "800 115px 'Schibsted Grotesk'"; c.letterSpacing = '2px'; const m = c.measureText('ZUMA'); return { w: m.width, asc: m.actualBoundingBoxAscent, desc: m.actualBoundingBoxDescent, left: m.actualBoundingBoxLeft, right: m.actualBoundingBoxRight, ok: document.fonts.check("800 115px 'Schibsted Grotesk'") }; });
  console.log(JSON.stringify(r)); await b.close(); })();

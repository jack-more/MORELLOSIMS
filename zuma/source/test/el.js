const { chromium } = require('playwright');
const [page, sel, w, out] = process.argv.slice(2);
(async () => { const b = await chromium.launch({ args: ['--proxy-server=' + process.env.HTTPS_PROXY, '--proxy-bypass-list=127.0.0.1;localhost', '--ignore-certificate-errors'] });
  const p = await b.newPage({ viewport: { width: +w, height: 900 } }); await p.goto('http://127.0.0.1:8772/site3/dist/' + page, { waitUntil: 'networkidle' }); await p.waitForTimeout(1500);
  const el = await p.$(sel); await el.scrollIntoViewIfNeeded(); await p.waitForTimeout(500); await el.screenshot({ path: out }); await b.close(); })();

// One transparent PNG per sticker at 600 dpi, with the white die-cut border and no shadow. node export.cjs
const { chromium } = require('playwright'); const path = require('path');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1600, height: 1200 }, deviceScaleFactor: 600 / 96 });
  await p.goto('file://' + path.resolve('stickers.html'), { waitUntil: 'load' }); await p.waitForTimeout(2500);
  await p.addStyleTag({ content: '.grid{zoom:1!important} body{background:transparent!important}' });
  await p.evaluate(() => document.querySelectorAll('feFlood.shadow').forEach(f => f.setAttribute('flood-opacity', '0')));
  for (const el of await p.$$('svg.st')) {
    const k = await el.getAttribute('data-key');
    await el.screenshot({ path: `print/zuma-sticker-${k}.png`, omitBackground: true }); console.log(k);
  }
  await b.close();
})();

const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1440, height: 900 } }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('http://127.0.0.1:8772/site3/dist/bpc-157.html', { waitUntil: 'networkidle' }); const st = await p.$('#pdp-stage'); const bx = await st.boundingBox();
  await p.mouse.move(bx.x + bx.width * 0.7, bx.y + bx.height / 2); await p.mouse.down(); await p.mouse.move(bx.x + bx.width * 0.3, bx.y + bx.height / 2, { steps: 12 }); await p.mouse.up(); await p.waitForTimeout(800);
  console.log('poster after drag:', await p.$eval('#d-poster', e => e.src.split('/').pop()), '| lot pressed:', await p.$eval('#t-back', e => e.getAttribute('aria-pressed')), '| errors:', errs.join('|') || 'none');
  await p.screenshot({ path: 'shots/spin-test.png', clip: bx }); await b.close(); })();

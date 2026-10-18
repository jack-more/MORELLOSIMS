// node shoot.cjs [fps] [from] [to] : steps render(t) and writes frames/NNNNN.png (or only the listed seconds with "stills")
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const [fpsArg, fromArg, toArg] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  p.on('pageerror', e => console.error('ERR', e.message));
  await p.goto('http://127.0.0.1:8772/ad/ad.html'); await p.waitForFunction('window.READY === true', null, { timeout: 120000 });
  const dir = path.join(__dirname, 'frames'); fs.mkdirSync(dir, { recursive: true });
  if (fpsArg === 'stills') {
    for (const t of (fromArg || '0.6,2,3.2,5.2,6.8,9.2,11.8,13.5,15.1,16.8,18.5').split(',').map(Number)) {
      await p.evaluate(t => window.render(t), t); await (await p.$('#c')).screenshot({ path: path.join(__dirname, `still-${t}.png`) });
    }
  } else {
    const fps = Number(fpsArg || 30), t0 = Number(fromArg || 0), t1 = Number(toArg || 20);
    for (let f = Math.round(t0 * fps); f < Math.round(t1 * fps); f++) {
      const url = await p.evaluate(t => { window.render(t); return document.getElementById('c').toDataURL('image/jpeg', .93); }, f / fps);
      fs.writeFileSync(path.join(dir, String(f).padStart(5, '0') + '.jpg'), Buffer.from(url.split(',')[1], 'base64'));
    }
  }
  await b.close(); console.log('done');
})();

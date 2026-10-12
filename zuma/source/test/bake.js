// node bake.js [preview|all] : bakes the vial stills from the live renderer (js/vials3d.js) into src/img (or test/shots/bake-* for preview)
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const mode = process.argv[2] || 'preview', IMG = path.join(__dirname, '..', 'src', 'img'), SH = path.join(__dirname, 'shots');
const save = (f, url) => { fs.writeFileSync(f, Buffer.from(url.split(',')[1], 'base64')); console.log('  wrote', path.basename(f), Math.round(fs.statSync(f).size / 1024), 'KB'); };
(async () => { const b = await chromium.launch({ args: ['--proxy-server=' + process.env.HTTPS_PROXY, '--proxy-bypass-list=127.0.0.1;localhost', '--ignore-certificate-errors', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const errs = [];
  const open = async page => { const p = await b.newPage({ viewport: { width: 1440, height: 900 } }); p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    await p.addInitScript(() => { window.ZUMA_BAKE = true; }); await p.goto('http://127.0.0.1:8772/site3/dist/' + page, { waitUntil: 'networkidle', timeout: 120000 });
    await p.waitForFunction('window.ZUMA3D_READY === true', null, { timeout: 180000 }); return p; };
  const p = await open('shop.html');
  if (mode === 'preview') { for (const [i, side] of [[0, 0], [1, 0], [3, 1]]) save(`${SH}/bake-${i}-${side}.webp`, await p.evaluate(([i, s]) => ZUMA3D.bakeCell(i, s), [i, side])); }
  else for (let i = 0; i < 6; i++) { const no = String(i + 1).padStart(2, '0'); save(`${IMG}/vial-${no}.webp`, await p.evaluate(i => ZUMA3D.bakeCell(i, 0), i)); save(`${IMG}/vial-${no}-back.webp`, await p.evaluate(i => ZUMA3D.bakeCell(i, 1), i)); }
  if (mode !== 'preview') { save(`${IMG}/lineup-2400.webp`, await p.evaluate(() => ZUMA3D.bakeLineup(2400, 1100))); save(`${IMG}/lineup-1200.webp`, await p.evaluate(() => ZUMA3D.bakeLineup(1200, 550))); }
  else save(`${SH}/bake-lineup.webp`, await p.evaluate(() => ZUMA3D.bakeLineup(1200, 550)));
  const h = await open('index.html');
  if (mode === 'preview') save(`${SH}/bake-hero.webp`, await h.evaluate(() => ZUMA3D.bakeHero(0)));
  else for (const i of [0, 1, 3, 4]) save(`${IMG}/hero-vial-${String(i + 1).padStart(2, '0')}.webp`, await h.evaluate(i => ZUMA3D.bakeHero(i), i));
  console.log('errors:', errs.join(' | ') || 'none'); await b.close(); })();

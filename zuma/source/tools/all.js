// Renders through tools/render.html (build it first with ./build.sh; the scratchpad server must run on port 8772).
//   node all.js site [only...]   -> every still the site needs, written to ../src/img (only: singles cutouts four lineup box detail flats)
//   node all.js test WxH ids...  -> the original lux7 trio renders (e.g. tricolor, field-bands) into out/test
//   node all.js compare          -> field-bands label (lux7) next to the ported Tricolor label, plus a pixel diff, into out/
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const [mode, ...rest] = process.argv.slice(2);
const IMG = path.join(__dirname, '..', 'src', 'img'), OUT = path.join(__dirname, 'out');
fs.mkdirSync(IMG, { recursive: true }); fs.mkdirSync(OUT, { recursive: true });
const save = (file, url) => { fs.writeFileSync(file, Buffer.from(url.split(',')[1], 'base64')); console.log('  wrote', path.relative(path.join(__dirname, '..'), file), Math.round(fs.statSync(file).size / 1024) + ' KB'); };
(async () => { const px = process.env.HTTPS_PROXY; const b = await chromium.launch({ args: ['--proxy-server=' + px, '--proxy-bypass-list=127.0.0.1;localhost', '--ignore-certificate-errors', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto('http://127.0.0.1:8772/site3/tools/render.html', { waitUntil: 'networkidle', timeout: 180000 }); await p.waitForFunction('window.SCENE_READY===true', null, { timeout: 180000 });
  const run = (fn, ...args) => p.evaluate(([fn, args]) => SHOTS[fn](...args), [fn, args]);
  if (mode === 'test') { const [size, ...ids] = rest, [w, h] = size.split('x').map(Number); for (const id of ids) save(`${OUT}/r-${id}.jpg`, await p.evaluate(([w, h, id]) => SHOTS.trio(w, h, id), [w, h, id])); }
  else if (mode === 'compare') { save(`${OUT}/cmp-field-bands.png`, await p.evaluate(() => FLAT('field-bands', 'label', '01', 'image/png')));
    save(`${OUT}/cmp-tricolor.png`, await p.evaluate(() => FLAT('tricolor', 'label', '01', 'image/png'))); }
  else if (mode === 'site') { const only = new Set(rest), want = k => !only.size || only.has(k), NOS = ['01', '02', '03', '04', '05', '06'];
    if (want('singles')) for (const no of NOS) { save(`${IMG}/vial-${no}.webp`, await run('single', 720, 960, no, 0)); save(`${IMG}/vial-${no}-back.webp`, await run('single', 720, 960, no, 1)); }
    if (want('cutouts')) for (const no of ['01', '02', '04', '05']) save(`${IMG}/hero-vial-${no}.webp`, await run('cutout', 880, 1100, no));
    if (want('four')) { save(`${IMG}/hero-2400.webp`, await run('four', 2400, 1350)); save(`${IMG}/hero-1200.webp`, await run('four', 1200, 675));
      const og = await run('four', 1200, 630); save(`${IMG}/og.webp`, og); }
    if (want('lineup')) { save(`${IMG}/lineup-2400.webp`, await run('lineup', 2400, 1100)); save(`${IMG}/lineup-1200.webp`, await run('lineup', 1200, 550)); }
    if (want('box')) { save(`${IMG}/box-2000.webp`, await run('box', 2000, 1375)); save(`${IMG}/box-1000.webp`, await run('box', 1000, 688)); }
    if (want('detail')) { save(`${IMG}/detail-1400.webp`, await run('detail', 1400, 1100)); save(`${IMG}/detail-800.webp`, await run('detail', 800, 629)); }
    if (want('flats')) { save(`${IMG}/label-01.webp`, await run('flat', '01', 1800)); save(`${IMG}/label-01-s.webp`, await run('flat', '01', 900));
      for (const no of NOS.slice(1)) save(`${IMG}/label-${no}.webp`, await run('flat', no, 900));
      save(`${IMG}/lid.webp`, await p.evaluate(async () => (await ART('tricolor', 'lid')).toDataURL('image/webp', 0.9))); } }
  console.log('errors:', errs.join(' | ') || 'none'); await b.close(); })();

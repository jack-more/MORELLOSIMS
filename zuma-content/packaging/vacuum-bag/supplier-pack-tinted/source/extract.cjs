// Read the Snow artwork's layout from the browser: every glyph's position, every logo path, every rule. Rotations are undone and recorded.
const { chromium } = require('playwright'); const fs = require('fs');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1400, height: 2100 } });
  await p.goto('file://' + process.argv[2]); await p.waitForTimeout(1500); await p.evaluate(() => document.fonts.ready);
  const out = await p.evaluate(() => {
    const rots = [];
    for (const el of document.querySelectorAll('[style*="rotate"]')) {
      const m = el.style.transform.match(/rotate\((-?[\d.]+)deg\)/); el.style.transform = el.style.transform.replace(/rotate\([^)]*\)/, '').trim() || 'none';
      const r = el.getBoundingClientRect(); el.dataset.rot = rots.length; rots.push({ a: +m[1], cx: r.left + r.width / 2, cy: r.top + r.height / 2 });
    }
    const rotOf = n => { const e = (n.nodeType === 1 ? n : n.parentElement).closest('[data-rot]'); return e ? +e.dataset.rot : -1; };
    const glyphs = [], svgs = [], rects = [];
    const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let t; (t = tw.nextNode());) {
      const cs = getComputedStyle(t.parentElement); if (t.parentElement.closest('svg,style,script')) continue;
      for (let i = 0; i < t.length; i++) { const ch = t.data[i]; if (/\s/.test(ch)) continue;
        const rg = document.createRange(); rg.setStart(t, i); rg.setEnd(t, i + 1); const r = rg.getClientRects()[0]; if (!r) continue;
        glyphs.push({ ch, x: r.left, top: r.top, h: r.height, size: parseFloat(cs.fontSize), w: +cs.fontWeight, rot: rotOf(t) }); }
    }
    for (const s of document.querySelectorAll('svg')) { const r = s.getBoundingClientRect(), vb = s.getAttribute('viewBox').split(/\s+/).map(Number);
      for (const pth of s.querySelectorAll('path')) svgs.push({ x: r.left, y: r.top, w: r.width, h: r.height, vb, d: pth.getAttribute('d'), rule: pth.getAttribute('fill-rule') || 'nonzero', rot: rotOf(s) }); }
    for (const d of document.querySelectorAll('div')) { const cs = getComputedStyle(d); if (d.children.length || d.textContent.trim() || cs.backgroundColor === 'rgba(0, 0, 0, 0)') continue;
      const r = d.getBoundingClientRect(); rects.push({ x: r.left, y: r.top, w: r.width, h: r.height, rot: rotOf(d) }); }
    return { rots, glyphs, svgs, rects };
  });
  fs.writeFileSync(process.argv[3], JSON.stringify(out)); console.log('glyphs', out.glyphs.length, 'svgs', out.svgs.length, 'rects', out.rects.length, 'rots', JSON.stringify(out.rots)); await b.close();
})();

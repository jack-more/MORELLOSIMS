/* ZUMA shop: every page's behaviour. Data comes from window.ZUMA_CATALOG (src/data/catalog.json, embedded by build.py).
   Pages: data-page="home" | "shop" | "pdp" on .z-base. Markup follows the brand guide (src/design): pills press, squares inform.
   Vial pictures are rendered in Blender (../cyc/vial.py); window.ZUMA3D hooks are optional.
   PLACEHOLDERS: prices, stock and shipping lines, lots, report links, the sample lot report and referral figures. Hooks to wire are marked "WIRE:". */
(() => {
  const C = window.ZUMA_CATALOG, A = window.ZUMA_ASSET || '';
  const img = f => A + 'img/' + f;
  const AREAS = C.areas;
  const P = C.products.map(p => ({ ...p, lot: p.code + '-2610A', filled: C.lot.filled, href: p.slug + '.html' }));
  const byNo = n => P.find(p => p.no === n), std = p => p.sizes[p.def];
  const SETS = C.sets.map(s => ({ ...s, list: s.items.reduce((a, n) => a + std(byNo(n))[1], 0) }));
  const FREE = C.freeShipping, tierOf = q => q >= 3 ? 0.85 : q === 2 ? 0.9 : 1;
  // launch pricing: the cart price is the launch price; the struck list price is what it becomes after launch (PLACEHOLDER)
  const listOf = v => Math.round(v * 100 / (100 - C.launch.off)), lp = v => `<span class="lchip">Launch</span><s>$${listOf(v)}</s>$${v}`;
  const base = document.querySelector('.z-base'), PAGE = base ? base.dataset.page : 'home';
  // what the label prints (label.js); url is the lot report the QR opens. WIRE: point at the real report URLs.
  const labelData = (p, mg) => ({ no: p.no, name: p.name, full: p.full, area: p.area, mg: mg || std(p)[0], lot: p.lot, filled: p.filled, url: 'https://zuma.example/lot/' + p.lot });
  const STATUS = { ok: ['Report published', 'z-tag z-tag-solid z-tag-dot'], pending: ['In testing', 'z-tag z-tag-ring'] };
  // WIRE: stock and dispatch come from inventory at launch
  const STOCK = { ok: 'In stock · ships in 1 business day', pending: 'Next lot in testing · ships when its report is out' };
  const addWord = p => p.status === 'pending' ? 'Pre-order' : 'Add to cart';
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const sw = '<span class="z-swatch" aria-hidden="true"><i></i><i></i><i></i></span>', arr = '<span class="z-arr" aria-hidden="true">→</span>';
  const on = (sel, ev, fn) => { const el = typeof sel === 'string' ? $(sel) : sel; if (el) el.addEventListener(ev, fn); };
  window.ZUMA = { P, AREAS, labelData, img };

  // ---------- product card (home and shop): size chips, quick view, quick add, and the whole card opens its page ----------
  const SPIN = 24;   // rendered turn frames per vial
  const pick = {};   // chosen size per product
  const sizeOf = p => pick[p.no] ?? p.def;
  function card(p, i, eager) {
    const k = sizeOf(p), z = p.sizes[k];
    return `<article class="z-card z-pcard" data-i="${i}" data-no="${p.no}" data-area="${p.area}">
  <div class="z-light z-pic"><img src="${img('vial-' + p.no + '.webp')}" width="720" height="960" loading="${eager ? 'eager' : 'lazy'}" alt="ZUMA ${esc(p.name)}: a clear vial with a three-band ${AREAS[p.area].short.toLowerCase()} label">
    <div class="z-pic-top"><span></span>${p.badge ? `<span class="z-tag z-tag-solid">${esc(p.badge)}</span>` : ''}</div>
    <div class="z-pic-actions"><button class="z-btn z-btn-sm" type="button" data-quick="${i}">Quick view</button></div></div>
  <div class="z-bright z-pad"><span class="z-area">${AREAS[p.area].label}</span><h3>${esc(p.name)}</h3><p class="z-full">${esc(p.full.toUpperCase() !== p.name.toUpperCase() ? p.full : 'Lyophilized')}</p></div>
  <div class="z-deep z-pad"><p class="z-lotline"><span>${STOCK[p.status].split(' · ')[0]}</span><span>Lot ${p.lot}</span></p>
    <div class="csizes" role="group" aria-label="Amount of ${esc(p.name)}">${p.sizes.map((s, j) => `<button class="z-chip" type="button" data-csize="${j}" aria-pressed="${j === k}">${s[0]}</button>`).join('')}</div>
    <div class="z-row cbuy"><span class="z-price" data-cp>${lp(z[1])}</span><span class="cbtns"><button class="z-btn z-btn-sm" type="button" data-qadd="${i}">${addWord(p)}</button><a class="z-btn z-btn-line z-btn-sm z-stretch" href="${p.href}?size=${k}" aria-label="View ${esc(p.name)}"><span class="cview">View</span> ${arr}</a></span></div></div>
</article>`;
  }
  document.addEventListener('click', e => {
    const c = e.target.closest('[data-csize]');
    if (c) { const el = c.closest('.z-pcard'), p = byNo(el.dataset.no), k = +c.dataset.csize; pick[p.no] = k;
      el.querySelectorAll('[data-csize]').forEach(b => b.setAttribute('aria-pressed', String(b === c)));
      el.querySelectorAll('[data-cp]').forEach(s => s.innerHTML = lp(p.sizes[k][1])); el.querySelector('.z-stretch').href = p.href + '?size=' + k; return; }
    const q = e.target.closest('[data-quick]'); if (q) { openProduct(+q.dataset.quick); return; }
    const a = e.target.closest('[data-qadd]'); if (a) { const p = P[+a.dataset.qadd], z = p.sizes[sizeOf(p)]; addItem(p.no + '-' + z[0], `${p.name} · ${z[0]}`, z[1], 1, p.area, p.no);
      a.textContent = 'Added ✓'; setTimeout(() => a.textContent = addWord(p), 1400); }
  });

  // ---------- grid with filter (and sort on the shop page) ----------
  let filt = 'all', sort = 'no';
  function renderGrid() {
    const g = $('#grid'); if (!g || !g.dataset.products) return;
    let list = P.map((p, i) => [p, i]).filter(([p]) => filt === 'all' || p.area === filt);
    const area = Object.keys(AREAS);
    if (sort === 'low') list.sort((a, b) => a[0].sizes[0][1] - b[0].sizes[0][1]); else if (sort === 'high') list.sort((a, b) => b[0].sizes[0][1] - a[0].sizes[0][1]);
    else if (sort === 'area') list.sort((a, b) => area.indexOf(a[0].area) - area.indexOf(b[0].area) || a[1] - b[1]);
    if (!g.children.length) g.innerHTML = P.map((p, i) => card(p, i, i < 3)).join('');
    const els = [...g.querySelectorAll('.z-pcard')], shown = new Set(list.map(([, i]) => i));
    list.forEach(([, i]) => g.appendChild(els.find(el => +el.dataset.i === i)));
    els.forEach(el => el.hidden = !shown.has(+el.dataset.i));
    $$('#filters .z-chip').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.f === filt)));
    const n = list.length; if ($('#plp-count')) $('#plp-count').textContent = `${n} ${n === 1 ? 'compound' : 'compounds'}${filt === 'all' ? '' : ' · ' + AREAS[filt].label}`;
    window.ZUMA3D && ZUMA3D.relayout && ZUMA3D.relayout();
  }
  if ($('#grid') && PAGE !== 'pdp') {
    $('#grid').dataset.products = '1';
    const q = new URLSearchParams(location.search).get('area'); if (q && AREAS[q]) filt = q;
    if ($('#filters')) $('#filters').innerHTML = `<button class="z-chip" type="button" data-f="all" aria-pressed="true">All six</button>` + Object.entries(AREAS).map(([k, a]) => `<button class="z-chip" type="button" data-f="${k}" data-area="${k}" aria-pressed="false">${sw}${a.short}</button>`).join('');
    on('#filters', 'click', e => { const b = e.target.closest('.z-chip'); if (b) { filt = b.dataset.f; renderGrid(); } });
    on('#sort', 'change', e => { sort = e.target.value; renderGrid(); });
    renderGrid();
  }
  window.ZUMA.filter = f => { filt = f; renderGrid(); };

  // ---------- research-area cards (home) ----------
  if ($('#areacards')) $('#areacards').innerHTML = Object.entries(AREAS).map(([k, a]) => { const ps = P.filter(p => p.area === k);
    return `<a class="z-card z-areacard" href="shop.html?area=${k}" data-area="${k}">
  <div class="z-light z-pad"><span class="z-kicker">Research area</span><span class="z-data">${ps.length} ${ps.length === 1 ? 'compound' : 'compounds'}</span></div>
  <div class="z-bright z-pad"><span class="z-area-name">${a.short}</span><span class="z-cmp">${ps.map(p => esc(p.name)).join(' · ')}</span></div>
  <div class="z-deep z-pad"><span class="z-btn z-btn-sm">Shop ${a.short.toLowerCase()} ${arr}</span></div>
</a>`; }).join('');

  // ---------- sets ----------
  if ($('#setcards')) $('#setcards').innerHTML = SETS.map(s => { const pair = !!s.area;
    return `<article class="z-setcard" data-area="${s.area || 'metabolic'}">
  <div class="z-light set-pic"><img src="${img('set-' + (s.area || 'collection') + '.webp')}" width="1280" height="800" loading="lazy" alt="${pair ? s.items.map(n => 'ZUMA ' + esc(byNo(n).name)).join(' and ') + ' vials together' : 'The ZUMA Collection box: six vials standing in a fitted insert, the printed lid behind'}"></div>
  <div class="${pair ? 'z-bright' : 'z-ink'} z-pad"><span class="${pair ? 'z-area' : 'z-kicker'}">${pair ? AREAS[s.area].label : 'All four research areas'}</span><h3>${s.name}</h3><p>${pair ? s.items.map(n => esc(byNo(n).name)).join(' + ') : 'All six, one of each'}</p></div>
  <div class="${pair ? 'z-deep' : 'z-ink'} z-pad z-row"><span class="z-price"><s>$${s.list}</s>$${s.price}</span><button class="z-btn z-btn-sm" type="button" data-set="${s.key}">Add set · save $${s.list - s.price}</button></div>
</article>`; }).join('');
  document.addEventListener('click', e => { const b = e.target.closest('[data-set]'); if (!b) return; addSet(b.dataset.set); const t = b.innerHTML; b.textContent = 'Added to cart'; setTimeout(() => b.innerHTML = t, 1400); });
  function addSet(key) { const s = SETS.find(x => x.key === key); addItem('set-' + key, `${s.name} · ${s.items.map(n => byNo(n).name).join(' + ')}`, s.price, 1, s.area || 'metabolic', s.area ? s.items[0] : 'box'); }

  // ---------- lots table (home) ----------
  if ($('#lotrows')) $('#lotrows').innerHTML = P.map(p => `<tr><td class="z-tnm"><a class="z-link" href="${p.href}">${esc(p.name)}</a></td><td class="areacell" data-k="Area"><span class="area" data-area="${p.area}">${sw}${AREAS[p.area].label}</span></td><td data-k="Lot">${p.lot}</td><td data-k="Filled">${p.filled}</td><td data-k="Tested">HPLC · MS</td><td><span class="${STATUS[p.status][1]}">${STATUS[p.status][0]}</span></td><td>${p.status === 'ok' ? `<button class="z-link" type="button" data-coa="${p.no}">Report ↗</button>` : '<span class="z-soft">Due</span>'}</td></tr>`).join('');
  const ls = $('#labelscroll'); if (ls) addEventListener('load', () => { if (ls.scrollWidth > ls.clientWidth) ls.scrollLeft = (ls.scrollWidth - ls.clientWidth) * 0.42; });

  // ---------- cart ----------
  let cart = [];
  try { cart = JSON.parse(localStorage.getItem('zuma-cart') || '[]'); if (!Array.isArray(cart)) cart = []; } catch (e) { cart = []; }
  function saveCart() { try { localStorage.setItem('zuma-cart', JSON.stringify(cart)); } catch (e) {} renderCart(); }
  function addItem(key, label, price, qty, area, no) { const f = cart.find(c => c.key === key); if (f) f.qty += qty; else cart.push({ key, label, price, qty, area, no }); saveCart();
    toast('Added to cart · ' + label.split(' · ').slice(0, 2).join(' · '), true); }
  const thumbOf = c => c.no === 'box' ? img('box-1000.webp') : c.no === 'set' ? img('set-pack-800.webp') : img('vial-' + (c.no || c.key.split('-')[0]) + '.webp');
  function renderCart() {
    if (!$('#cart')) return;
    const n = cart.reduce((a, c) => a + c.qty, 0), t = cart.reduce((a, c) => a + c.qty * c.price, 0);
    $('#cartn').textContent = n; $('#c-total').textContent = '$' + t; $('#c-empty').hidden = n > 0;
    $('#c-items').innerHTML = cart.map((c, k) => `<li data-area="${c.area || 'metabolic'}"><span class="${c.no === 'box' || c.no === 'set' ? 'z-sand' : 'z-light'} cthumb"><img src="${thumbOf(c)}" alt=""></span>
      <span class="cbody"><span class="t">${esc(c.label)}</span><span class="cqty"><span class="z-stepper z-stepper-sm" role="group" aria-label="Quantity"><button type="button" data-cq="${k}" data-d="-1" aria-label="One fewer">−</button><output>${c.qty}</output><button type="button" data-cq="${k}" data-d="1" aria-label="One more">+</button></span><button class="z-link" type="button" data-rm="${k}">Remove</button></span></span>
      <span class="z-price">$${c.qty * c.price}</span></li>`).join('');
    const ok = n > 0 && $('#c-ok').checked; $('#c-go').disabled = !ok; $('#c-crypto').disabled = !ok;
    $('#c-status').textContent = n > 0 && !$('#c-ok').checked ? 'Confirm research use above to continue.' : '';
    const left = Math.max(0, FREE - t);
    $('#c-shipt').textContent = n === 0 ? `Free cold-chain shipping on orders over $${FREE}.` : left > 0 ? `$${left} away from free cold-chain shipping.` : 'Free cold-chain shipping unlocked.';
    $('#c-shipb').style.width = Math.min(100, t / FREE * 100) + '%';
    const inCart = new Set(cart.map(c => c.key.split('-')[0])), want = [];
    cart.forEach(c => { const s = SETS.find(x => x.items.length === 2 && x.items.includes(c.key.split('-')[0])); if (s) s.items.forEach(m => { if (!inCart.has(m) && !want.includes(m)) want.push(m); }); });
    ['01', '02'].forEach(m => { if (!inCart.has(m) && !want.includes(m)) want.push(m); });
    $('#c-sugg').innerHTML = n === 0 ? '' : `<span class="z-legend">Often added</span>` + want.slice(0, 2).map(m => { const p = byNo(m), z = std(p);
      return `<button type="button" data-sugg="${m}"><span class="z-light" data-area="${p.area}"><img src="${img('vial-' + m + '.webp')}" alt=""></span><span>${esc(p.name)}<small>${AREAS[p.area].label} · ${z[0]}</small></span><span class="z-price">+$${z[1]}</span></button>`; }).join('');
  }
  on('#c-sugg', 'click', e => { const b = e.target.closest('[data-sugg]'); if (!b) return; const p = byNo(b.dataset.sugg), z = std(p); addItem(p.no + '-' + z[0], `${p.name} · ${z[0]}`, z[1], 1, p.area, p.no); });
  on('#c-items', 'click', e => { const r = e.target.closest('[data-rm]'); if (r) { cart.splice(+r.dataset.rm, 1); saveCart(); return; }
    const q = e.target.closest('[data-cq]'); if (q) { const c = cart[+q.dataset.cq]; c.qty += +q.dataset.d; if (c.qty < 1) cart.splice(+q.dataset.cq, 1); saveCart(); } });
  on('#c-ok', 'change', renderCart);
  // WIRE: checkout. Replace this handler with a redirect to the real checkout, passing `cart`, the 21+ research-use confirmation and the referral code.
  on('#c-go', 'click', () => { $('#c-status').textContent = 'Checkout opens at launch. Your cart is saved on this device.'; });
  renderCart();

  // ---------- panels ----------
  let openPanel = null, lastFocus = null;
  function show(el) { if (openPanel) hide(true); lastFocus = document.activeElement; el.hidden = false; requestAnimationFrame(() => { el.classList.add('on'); $('#scrim').classList.add('on'); }); openPanel = el; document.body.style.overflow = 'hidden'; setTimeout(() => el.querySelector('[data-close]').focus(), 30); }
  function hide(quick, noFocus) { const el = openPanel; if (!el) return; el.classList.remove('on'); $('#scrim').classList.remove('on'); openPanel = null; document.body.style.overflow = '';
    const done = () => { if (!el.classList.contains('on')) el.hidden = true; }; quick ? done() : setTimeout(done, 400); if (!quick && !noFocus && lastFocus && lastFocus.focus) lastFocus.focus();
    if (el.id === 'drawer' && window.ZUMA3D) ZUMA3D.drawerClosed(); }
  $$('[data-close]').forEach(b => b.addEventListener('click', () => hide()));
  on('#scrim', 'click', () => hide());
  const trap = (root, e) => { const f = [...root.querySelectorAll('button:not([disabled]),a[href],input:not([disabled]),[tabindex]:not([tabindex="-1"])')].filter(x => x.offsetParent !== null); if (!f.length) return;
    const a = f[0], z = f[f.length - 1]; if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); } else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); } };
  document.addEventListener('keydown', e => {
    const dlg = $$('.z-dialog').find(d => !d.hidden); if (dlg) { if (e.key === 'Escape') closeDialog(dlg); else if (e.key === 'Tab') trap(dlg, e); return; }
    if (!openPanel) { if (e.key === 'Escape') { toggleMenu(false); toggleMega(false); } return; }
    if (e.key === 'Escape') { hide(); return; } if (e.key === 'Tab') trap(openPanel, e);
  });
  on('#cartbtn', 'click', () => { renderCart(); show($('#cart')); });

  // ---------- buying one compound: the quick-view drawer (home, shop) or the product page's buy box share this ----------
  const D = { i: 0, size: 0, qty: 1, freq: 'once' };
  const unitFor = () => P[D.i].sizes[D.size][1] * tierOf(D.qty) * (D.freq === 'standing' ? 0.9 : 1);
  const priceNow = () => Math.round(unitFor()) * D.qty;
  function refresh() { const p = P[D.i], full = p.sizes[D.size][1] * D.qty; $('#q-n').textContent = D.qty;
    $('#d-add').textContent = priceNow() < full ? `${addWord(p)} · $${priceNow()} (was $${full})` : `${addWord(p)} · $${priceNow()}`; if ($('#bb-add')) $('#bb-add').textContent = addWord(p);
    $('#d-tiers').textContent = D.qty >= 3 ? '15% off for 3 or more vials' : D.qty === 2 ? '10% off for 2 vials · add one more for 15%' : '2 vials save 10% · 3 or more save 15%';
    if ($('#pdp-list')) $('#pdp-list').textContent = '$' + listOf(p.sizes[D.size][1]);
    if ($('#pdp-price')) { $('#pdp-price').textContent = '$' + Math.round(unitFor()); $('#pdp-per').textContent = D.freq === 'standing' ? 'per vial, subscribed' : 'per vial'; }
    if ($('#bb-price')) { $('#bb-price').textContent = '$' + priceNow(); $('#bb-size').textContent = `${p.sizes[D.size][0]} × ${D.qty}${D.freq === 'standing' ? ' · every 30 days' : ''}`; }
    window.ZUMA3D && ZUMA3D.reprint(D.i, p.sizes[D.size][0]); }
  function addCurrent(btn) { const p = P[D.i], s = p.sizes[D.size], st = D.freq === 'standing';
    addItem(p.no + '-' + s[0] + (st ? '-standing' : ''), `${p.name} · ${s[0]}${st ? ' · Subscription' : ''}`, Math.round(unitFor()), D.qty, p.area, p.no);
    if (btn) { btn.textContent = 'Added to cart'; setTimeout(refresh, 1400); } }
  function wireBuy() {
    on('#d-sizes', 'change', e => { D.size = +e.target.value; refresh(); });
    $$('input[name="freq"]').forEach(r => r.addEventListener('change', () => { D.freq = r.value; refresh(); }));
    on('#q-minus', 'click', () => { if (D.qty > 1) { D.qty--; refresh(); } });
    on('#q-plus', 'click', () => { if (D.qty < 20) { D.qty++; refresh(); } });
    on('#d-add', 'click', e => addCurrent(e.currentTarget));
    on('#t-front', 'click', () => setTurn(false));
    on('#t-back', 'click', () => setTurn(true));
  }
  function setTurn(back, silent) { $('#t-front').setAttribute('aria-pressed', String(!back)); $('#t-back').setAttribute('aria-pressed', String(back));
    $$('.pdp-thumb[data-view="label"], .pdp-thumb[data-view="box"]').forEach(t => t.setAttribute('aria-pressed', 'false'));
    const st = $('#pdp-stage'); if (st) st.classList.remove('still');
    $('#d-poster').src = img('vial-' + P[D.i].no + (back ? '-back' : '') + '.webp'); SP.forEach(s => s.set(back ? 6 : 0)); }
  window.ZUMA.setTurnUI = back => { if (!$('#t-front')) return; $('#t-front').setAttribute('aria-pressed', String(!back)); $('#t-back').setAttribute('aria-pressed', String(back)); };

  // ---------- drag to turn: 24 rendered frames per vial (img/spin/NN-KK.webp, frame 6 is the lot side) ----------
  function spinner(stage) {
    const poster = stage.querySelector('#d-poster'); let frames = null, no = null, f = 0, drag = null;
    const load = () => { no = P[D.i].no; frames = Array.from({ length: SPIN }, (_, k) => { const im = new Image(); im.decoding = 'async'; im.src = img(`spin/${no}-${String(k).padStart(2, '0')}.webp`); return im; }); };
    const show = k => { f = ((k % SPIN) + SPIN) % SPIN; if (!frames || no !== P[D.i].no) load(); const im = frames[f], want = f;
      if (im.complete && im.naturalWidth) poster.src = im.src; else im.onload = () => { if (f === want) poster.src = im.src; };
      if ($('#t-front')) { $('#t-front').setAttribute('aria-pressed', String(f === 0)); $('#t-back').setAttribute('aria-pressed', String(f === 6)); } };
    stage.addEventListener('pointerdown', e => { if (stage.classList.contains('still')) return; drag = { x: e.clientX, f }; if (!frames || no !== P[D.i].no) load(); stage.setPointerCapture(e.pointerId); });
    stage.addEventListener('pointermove', e => { if (drag) show(drag.f + Math.round((e.clientX - drag.x) / 22)); });
    const end = () => { drag = null; }; stage.addEventListener('pointerup', end); stage.addEventListener('pointercancel', end);
    return { set(k) { f = k; frames = frames && no === P[D.i].no ? frames : null; } };
  }
  const SP = ['#pdp-stage', '#d-stage'].map(s => $(s)).filter(Boolean).map(spinner);

  function openProduct(i) {
    const dr = $('#drawer'); if (!dr) { location.href = P[i].href; return; }
    const p = P[i]; D.i = i; D.size = sizeOf(p); D.qty = 1; D.freq = 'once'; $('#o-once').checked = true; dr.dataset.area = p.area;
    const pr = SETS.find(s => s.items.length === 2 && s.items.includes(p.no));
    $('#d-pair').innerHTML = pr ? (() => { const o = byNo(pr.items.find(n => n !== p.no)); return `<div class="pairc" data-area="${o.area}"><span class="z-light pair-img"><img src="${img('vial-' + o.no + '.webp')}" alt=""></span><div><span class="z-legend">Complete the pair</span><b>${pr.name}</b><span>${esc(byNo(pr.items[0]).name)} + ${esc(byNo(pr.items[1]).name)} · <s>$${pr.list}</s> $${pr.price}</span><div class="pair-btns"><button class="z-btn z-btn-line z-btn-sm" type="button" data-set="${pr.key}">Add the pair · save $${pr.list - pr.price}</button></div></div></div>`; })() : '';
    $('#d-area').textContent = AREAS[p.area].label; $('#d-name').textContent = p.name; $('#d-full').textContent = p.full + ' · lyophilized'; $('#d-lab').textContent = p.name;
    $('#d-about').textContent = p.about; $('#d-pdp').href = p.href;
    $('#d-poster').src = img('vial-' + p.no + '.webp'); $('#d-poster').alt = `ZUMA ${p.name} vial`;
    $('#d-sizes').innerHTML = p.sizes.map((s, k) => `<label class="z-option"><input type="radio" name="fill" value="${k}" ${k === D.size ? 'checked' : ''}><span>${s[0]}<small>$${s[1]}</small></span></label>`).join('');
    $('#d-lot').innerHTML = [['LOT', p.lot], ['FILLED', p.filled], ['TESTED', 'HPLC · MS'], ['STORE', '−20 °C, DARK'], ['ON-CHAIN', 'at launch']].map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('');
    const c = $('#d-chip'); c.className = STATUS[p.status][1]; c.textContent = STATUS[p.status][0];
    $('#d-lotlink').innerHTML = (p.status === 'ok' ? 'View the lot report ' : 'Ships when its report is out ') + arr; $('#d-lotlink').dataset.coa = p.status === 'ok' ? p.no : '';
    setTurn(false, true); refresh(); show(dr); window.ZUMA3D && ZUMA3D.drawerOpened(i);
  }
  window.ZUMA.openProduct = openProduct;
  if ($('#drawer')) { wireBuy(); on('#d-lotlink', 'click', e => { e.preventDefault(); const no = e.currentTarget.dataset.coa; if (no) openCoa(no, e.currentTarget); else hide(false, true); }); }

  // ---------- product page ----------
  const pdp = $('[data-pdp]');
  if (pdp) {
    D.i = +pdp.dataset.pdp; const p = P[D.i];
    const qs = new URLSearchParams(location.search).get('size'), q = qs === null ? NaN : +qs; D.size = Number.isInteger(q) && p.sizes[q] ? q : p.def;
    const r = $(`#d-sizes input[value="${D.size}"]`); if (r) r.checked = true;
    wireBuy(); refresh();
    $$('.pdp-thumb[data-view="label"], .pdp-thumb[data-view="box"]').forEach(t => t.addEventListener('click', () => {
      $$('.pdp-thumb').forEach(x => x.setAttribute('aria-pressed', String(x === t))); $('#pdp-stage').classList.add('still');
      $('#d-poster').src = t.dataset.view === 'label' ? img('label-' + p.no + '.webp') : img('pack-' + p.no + '.webp'); }));
    // the add-to-cart bar appears once the buy box's button scrolls out of view
    const bb = $('#buybar'), btn = $('#d-add');
    if (bb && btn && 'IntersectionObserver' in window) new IntersectionObserver(([en]) => { const showBar = !en.isIntersecting && en.boundingClientRect.top < 0;
      bb.classList.toggle('on', showBar); bb.setAttribute('aria-hidden', String(!showBar)); $('#bb-add').tabIndex = showBar ? 0 : -1; }).observe(btn);
    on('#bb-add', 'click', e => addCurrent(e.currentTarget));
    const stock = document.createElement('p'); stock.className = 'stock' + (p.status === 'ok' ? ' instock' : ''); stock.textContent = STOCK[p.status]; $('.pdp-buy .addrow').before(stock);
    if (p.status !== 'ok') { const n = document.createElement('button'); n.className = 'z-btn z-btn-line z-btn-block'; n.type = 'button'; n.dataset.launch = 'notify'; n.textContent = 'Notify me when the next lot is published'; $('.pdp-buy .addrow').after(n); }
  }
  // related products carousel
  $$('[data-scroll]').forEach(b => b.addEventListener('click', () => { const t = $('#related'); t.scrollBy({ left: +b.dataset.scroll * t.clientWidth * 0.8, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); }));

  // ---------- hero (home): switch the featured area; the header logo's dot follows it ----------
  const hero = $('#hero'), giant = $('#h-name');
  if (hero && giant) {
    const fitGiant = () => { const avail = giant.parentElement.clientWidth, max = innerWidth < 761 ? 96 : 140; giant.style.fontSize = max + 'px'; const w = giant.scrollWidth; if (w > avail) giant.style.fontSize = Math.max(44, Math.floor(max * avail / w)) + 'px'; };
    const heroShow = (i, user) => { const p = P[i]; hero.dataset.area = p.area; if ($('#top')) $('#top').dataset.area = p.area;
      $('#h-area').textContent = AREAS[p.area].label; giant.textContent = p.name; $('#h-full').textContent = `${p.full} · ${std(p)[0]} · from $${p.sizes[0][1]}`;
      $('#h-open').innerHTML = `Shop ${p.name} ${arr}`; $('#h-open').href = p.href; $('#h-open').dataset.i = i;
      $$('[data-hero]').forEach(b => b.setAttribute('aria-pressed', String(+b.dataset.hero === i)));
      const po = $('#hero-poster'); po.src = img('hero-vial-' + p.no + '.webp'); po.alt = `ZUMA ${p.name}: a clear vial whose label is three bands of ${AREAS[p.area].short.toLowerCase()}`;
      fitGiant(); if (user && window.ZUMA3D) ZUMA3D.heroShow(i); };
    $$('[data-hero]').forEach(b => b.addEventListener('click', () => heroShow(+b.dataset.hero, true)));
    window.ZUMA.heroIndex = () => +($('#h-open').dataset.i || 0);
    addEventListener('resize', fitGiant); document.fonts && document.fonts.ready.then(fitGiant); heroShow(0, false);
    // drag the floating vial to turn it: 24 rendered frames per featured vial (img/hspin/NN-KK.webp)
    const anc = $('#hero-anchor'), po = $('#hero-poster'); let hf = null, hno = null, hk = 0, hd = null;
    const hload = () => { hno = P[window.ZUMA.heroIndex()].no; hf = Array.from({ length: SPIN }, (_, k) => { const im = new Image(); im.src = img(`hspin/${hno}-${String(k).padStart(2, '0')}.webp`); return im; }); };
    const hshow = k => { hk = ((k % SPIN) + SPIN) % SPIN; if (!hf || hno !== P[window.ZUMA.heroIndex()].no) hload(); const im = hf[hk], want = hk; if (im.complete && im.naturalWidth) po.src = im.src; else im.onload = () => { if (hk === want) po.src = im.src; }; };
    if (anc && po) { anc.classList.add('turnable');
      anc.addEventListener('pointerdown', e => { hd = { x: e.clientX, k: hk, moved: 0 }; if (!hf || hno !== P[window.ZUMA.heroIndex()].no) hload(); anc.setPointerCapture(e.pointerId); anc.classList.add('dragging'); });
      anc.addEventListener('pointermove', e => { if (!hd) return; hd.moved = Math.abs(e.clientX - hd.x); hshow(hd.k + Math.round((e.clientX - hd.x) / 22)); });
      const hend = () => { if (!hd) return; const tap = hd.moved < 6; hd = null; anc.classList.remove('dragging'); if (tap) location.href = P[window.ZUMA.heroIndex()].href; };
      anc.addEventListener('pointerup', hend); anc.addEventListener('pointercancel', () => { hd = null; anc.classList.remove('dragging'); });
      $$('[data-hero]').forEach(b => b.addEventListener('click', () => { hk = 0; hf = null; })); }
  }

  // ---------- header: offers, the Shop menu, the phone menu, shadow once scrolled, current section ----------
  const msgs = $$('.promo-msg'); let pi = 0, pt = 0;
  const promo = d => { if (!msgs.length) return; msgs[pi].hidden = true; pi = (pi + d + msgs.length) % msgs.length; msgs[pi].hidden = false; };
  $$('[data-promo]').forEach(b => b.addEventListener('click', () => { promo(+b.dataset.promo); clearInterval(pt); }));
  if (msgs.length > 1 && !matchMedia('(prefers-reduced-motion: reduce)').matches) { pt = setInterval(() => promo(1), 6000); on('#promo', 'mouseenter', () => clearInterval(pt)); }
  function toggleMega(open) { const m = $('#mega'); if (!m) return; m.hidden = !open; $('#megabtn').setAttribute('aria-expanded', String(open)); }
  on('#megabtn', 'click', () => toggleMega($('#mega').hidden));
  document.addEventListener('click', e => { if ($('#mega') && !$('#mega').hidden && !e.target.closest('#mega, #megabtn')) toggleMega(false); });
  function toggleMenu(open) { const m = $('#menu'); if (!m) return; m.hidden = !open; $('#menubtn').setAttribute('aria-expanded', String(open)); $('#menubtn').textContent = open ? 'Close' : 'Menu'; }
  on('#menubtn', 'click', () => toggleMenu($('#menu').hidden));
  on('#menu', 'click', e => { if (e.target.closest('a')) toggleMenu(false); });
  const top = $('#top'), onScroll = () => top && top.classList.toggle('scrolled', scrollY > 8); addEventListener('scroll', onScroll, { passive: true }); onScroll();
  if (PAGE === 'home') { const links = $$('#nav a'), byId = id => links.find(a => a.getAttribute('href') === '#' + id);
    const spy = new IntersectionObserver(es => es.forEach(e => { if (!e.isIntersecting) return; links.forEach(a => a.removeAttribute('aria-current'));
      const l = byId(e.target.id === 'box' ? 'lots' : e.target.id === 'label' ? 'sets' : e.target.id); if (l) l.setAttribute('aria-current', 'true'); }), { rootMargin: '-45% 0px -50% 0px' });
    $$('main > section[id]').forEach(s => spy.observe(s)); }

  // ---------- dialogs: "Coming at launch" (wallet, crypto, notify, newsletter) and the sample lot report ----------
  // WIRE: wallet: POST /api/wallets/challenge -> sign -> POST /api/wallets/verify (../zuma-referrals). Crypto checkout: payment processor. Newsletter and notify: email provider.
  const LAUNCH = { wallet: ['Wallet', 'Wallet connection and crypto checkout (USDC, SOL and $ZUMA) open at launch. Nothing on this preview connects to a chain or asks a wallet to sign.'],
    crypto: ['Pay with crypto · USDC, SOL, $ZUMA', 'Crypto checkout opens at launch, beside card checkout. Nothing on this preview connects to a chain or asks a wallet to sign.'],
    link: ['Referrals · link a wallet', 'Linking a wallet opens at launch. Nothing on this preview connects to a chain or asks a wallet to sign.'],
    payout: ['Referrals · payouts', 'Payouts open at launch, in USDC or store credit.'],
    notify: ['Notify me', 'Lot alerts open at launch: one email when the next lot of this compound is published, and nothing else.'],
    news: ['Newsletter', 'Sign-up opens at launch. Nothing you type here is stored or sent.'] };
  let dlgFrom = null;
  function openDialog(d, from) { dlgFrom = from; d.hidden = false; setTimeout(() => (d.querySelector('[data-dclose]') || d.querySelector('button')).focus(), 20); }
  function closeDialog(d) { d.hidden = true; if (dlgFrom && dlgFrom.focus) dlgFrom.focus(); }
  function openLaunch(kind, from) { const L = LAUNCH[kind] || ['At launch', '']; $('#l-ctx').textContent = L[0]; $('#l-p').textContent = L[1]; openDialog($('#launch'), from); }
  document.addEventListener('click', e => { const b = e.target.closest('[data-launch]'); if (b && !b.disabled) { openLaunch(b.dataset.launch, b); return; }
    const c = e.target.closest('[data-coa]'); if (c && c.dataset.coa && c.id !== 'd-lotlink') { e.preventDefault(); openCoa(c.dataset.coa, c, c.dataset.lot); } });
  on('#l-close', 'click', () => closeDialog($('#launch')));
  on('#launch', 'click', e => { if (e.target === $('#launch')) closeDialog($('#launch')); });
  on('#news', 'submit', e => { e.preventDefault(); openLaunch('news', $('#news button')); });

  // The lot report viewer. Every figure is a SAMPLE for the preview and is marked as such. WIRE: replace with each lot's published report (PDF).
  function chroma(seed) { // a sample HPLC trace for layout: one main peak, two small ones
    const W = 520, H = 150, pts = []; for (let x = 0; x <= W; x += 2) { const t = x / W, g = (c, w, h) => h * Math.exp(-((t - c) ** 2) / (2 * w * w));
      const y = 4 + g(0.18, 0.006, 6) + g(0.52 + seed * 0.01, 0.012, 128) + g(0.71, 0.007, 9) + 1.2 * Math.sin(x * 0.7 + seed); pts.push(`${x},${(H - y).toFixed(1)}`); }
    return `<svg viewBox="0 0 520 160" role="img" aria-label="Sample HPLC trace: one main peak"><path d="M0 150H520" stroke="currentColor" stroke-opacity=".35"/><polyline fill="none" stroke="currentColor" stroke-width="2" points="${pts.join(' ')}"/><text x="2" y="160" font-size="10" fill="currentColor" opacity=".7">0 min</text><text x="484" y="160" font-size="10" fill="currentColor" opacity=".7">30 min</text></svg>`; }
  function openCoa(no, from, lotNo) {
    const p0 = byNo(no); if (!p0) return; const p = lotNo ? { ...p0, lot: lotNo, filled: (LOTS.find(l => l.lot === lotNo) || p0).filled } : p0; let d = $('#coa');
    if (!d) { d = document.createElement('div'); d.className = 'z-dialog'; d.id = 'coa'; d.setAttribute('role', 'dialog'); d.setAttribute('aria-modal', 'true'); d.setAttribute('aria-labelledby', 'coa-h'); d.hidden = true;
      d.innerHTML = '<div class="z-dialog-card z-white coa" id="coa-card"></div>'; (base || document.body).appendChild(d);
      d.addEventListener('click', e => { if (e.target === d || e.target.closest('[data-dclose]')) closeDialog(d); }); }
    const spec = Object.entries(p.spec).map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join('');
    $('#coa-card').innerHTML = `<div class="coa-mark" aria-hidden="true">SAMPLE</div>
      <div class="coa-head" data-area="${p.area}"><span class="z-swatch z-swatch-lg" aria-hidden="true"><i></i><i></i><i></i></span><div><p class="z-kicker z-soft">Lot report · sample layout</p><h2 class="display-m" id="coa-h">${esc(p.name)}</h2></div><button class="z-btn z-btn-line z-btn-sm" type="button" data-dclose>Close ✕</button></div>
      <p class="coa-warn"><span class="z-tag z-tag-dash">Sample</span> This is how each lot report will read. It is not a real report, and none of its figures describe a real lot.</p>
      <dl class="speclist"><div><dt>Lot</dt><dd>${p.lot}</dd></div><div><dt>Compound</dt><dd>${esc(p.full)}</dd></div>${spec}<div><dt>Filled</dt><dd>${p.filled}</dd></div><div><dt>Identity (MS)</dt><dd>Sample: matches reference mass</dd></div><div><dt>Purity (HPLC)</dt><dd>Sample: stated on the published report</dd></div><div><dt>Appearance</dt><dd>White lyophilized powder</dd></div></dl>
      <figure class="coa-chart" data-area="${p.area}">${chroma(+p.no)}<figcaption>Sample HPLC trace, for layout only.</figcaption></figure>
      <p class="z-soft small">At launch each report is published as a PDF, linked from the code on the vial, and its fingerprint (SHA-256) is recorded on-chain. For laboratory research use only. Not for human or veterinary use.</p>`;
    openDialog(d, from);
  }
  window.ZUMA.openCoa = openCoa;

  // ---------- help links: open the answer a link points at (#faq-shipping ...) ----------
  const openHash = () => { const d = location.hash && document.getElementById(location.hash.slice(1)); if (d && d.tagName === 'DETAILS') d.open = true; };
  addEventListener('hashchange', openHash); openHash();

  // ---------- copy buttons (referral link and code) ----------
  $$('[data-copy]').forEach(b => b.addEventListener('click', () => { const inp = document.getElementById(b.dataset.copy), v = inp.value;
    const done = () => { b.textContent = 'Copied'; setTimeout(() => b.textContent = 'Copy', 1400); };
    const fallback = () => { inp.focus(); inp.select(); try { document.execCommand('copy') ? done() : toast('Selected · press Ctrl+C or ⌘C to copy'); } catch (e) { toast('Selected · press Ctrl+C or ⌘C to copy'); } };
    try { navigator.clipboard.writeText(v).then(done, fallback); } catch (e) { fallback(); } }));

  let tt = 0; function toast(t, withCart) { const el = $('#toast'); if (!el) return; el.innerHTML = esc(t) + (withCart ? ' <button class="z-link" type="button" data-opencart>View cart</button>' : ''); el.classList.add('on'); clearTimeout(tt); tt = setTimeout(() => el.classList.remove('on'), 2600); }
  document.addEventListener('click', e => { if (e.target.closest('[data-opencart]')) { $('#toast').classList.remove('on'); renderCart(); show($('#cart')); } });

  // ---------- every lot (lot library page): current lot plus earlier ones, newest first ----------
  const LOTS = P.flatMap(p => [{ p, lot: p.lot, filled: p.filled, status: p.status }].concat(C.lot.previous.map(([pre, d]) => ({ p, lot: `${p.code}-${pre}A`, filled: d, status: 'ok' }))));
  if ($('#lib-rows')) {
    let la = 'all', ls = 'all', lq = '';
    $('#lib-areas').innerHTML = `<button class="z-chip" type="button" data-a="all" aria-pressed="true">All areas</button>` + Object.entries(AREAS).map(([k, a]) => `<button class="z-chip" type="button" data-a="${k}" data-area="${k}" aria-pressed="false">${sw}${a.short}</button>`).join('');
    const draw = () => {
      const q = lq.trim().toUpperCase().replace(/\s+/g, '');
      const rows = LOTS.filter(l => (la === 'all' || l.p.area === la) && (ls === 'all' || l.status === ls) && (!q || l.lot.toUpperCase().includes(q) || l.p.name.toUpperCase().replace(/\s+/g, '').includes(q) || l.p.full.toUpperCase().includes(q)));
      $('#lib-rows').innerHTML = rows.map(l => `<tr><td class="z-tnm"><a class="z-link" href="${l.p.href}">${esc(l.p.name)}</a></td><td class="areacell" data-k="Area"><span class="area" data-area="${l.p.area}">${sw}${AREAS[l.p.area].label}</span></td><td data-k="Lot">${l.lot}</td><td data-k="Fills">${l.p.sizes.map(z => z[0]).join(' · ')}</td><td data-k="Filled">${l.filled}</td><td data-k="Tested">HPLC · MS</td><td><span class="${STATUS[l.status][1]}">${STATUS[l.status][0]}</span></td><td>${l.status === 'ok' ? `<button class="z-link" type="button" data-coa="${l.p.no}" data-lot="${l.lot}">Report ↗</button>` : '<span class="z-soft">Due</span>'}</td></tr>`).join('');
      $('#lib-count').textContent = `${rows.length} ${rows.length === 1 ? 'lot' : 'lots'}`; $('#lib-none').hidden = rows.length > 0; $('#lib').hidden = !rows.length;
      $$('#lib-areas .z-chip').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.a === la))); $$('#lib-status .z-chip').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.s === ls))); };
    on('#lib-areas', 'click', e => { const b = e.target.closest('[data-a]'); if (b) { la = b.dataset.a; draw(); } });
    on('#lib-status', 'click', e => { const b = e.target.closest('[data-s]'); if (b) { ls = b.dataset.s; draw(); } });
    on('#lib-q', 'input', e => { lq = e.target.value; draw(); });
    const pre = new URLSearchParams(location.search).get('lot'); if (pre) { lq = pre; $('#lib-q').value = pre; }
    draw();
  }

  // ---------- build a set: the number of different compounds sets the saving; a set can repeat every 30 days ----------
  if ($('#bld-grid')) {
    const TIERS = C.builder.tiers, REP = C.builder.repeatOff;
    const tierFor = n => TIERS.reduce((t, x) => n >= x[0] ? x : t, TIERS[0]);
    const B = {}; let rep = false;   // B[no] = { size, qty }
    const plus = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 4v12M4 10h12" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>';
    const tick = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5l3.6 3.6 7.4-8" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    $('#bld-grid').innerHTML = P.map(p => `<article class="bcard" data-no="${p.no}" data-area="${p.area}">
  <div class="bcard-pic"><img src="${img('pack-' + p.no + '.webp')}" width="720" height="900" loading="lazy" alt="ZUMA ${esc(p.name)}: the vial in front of its ${AREAS[p.area].short.toLowerCase()} carton">
    <span class="bcard-area">${sw}${AREAS[p.area].short}</span>
    <button class="bcard-pick" type="button" data-pick="${p.no}" aria-pressed="false" aria-label="Add ${esc(p.name)} to your set">${plus}</button></div>
  <div class="bcard-body"><div class="bcard-row"><h3>${esc(p.name)}</h3><span class="z-price" data-bp>${lp(std(p)[1])}</span></div>
    <p class="bcard-sub">${esc(p.full.toUpperCase() !== p.name.toUpperCase() ? p.full : 'Lyophilized')} · Lot ${p.lot}${p.status === 'pending' ? ' · in testing' : ''}</p>
    <div class="bcard-opts"><div class="z-chips" role="group" aria-label="Amount of ${esc(p.name)}">${p.sizes.map((s, j) => `<button class="z-chip" type="button" data-bsize="${j}" aria-pressed="${j === p.def}">${s[0]}</button>`).join('')}</div>
      <div class="z-stepper z-stepper-sm bcard-qty" role="group" aria-label="Vials of ${esc(p.name)}" hidden><button type="button" data-bq="-1" aria-label="One fewer vial">−</button><output>1</output><button type="button" data-bq="1" aria-label="One more vial">+</button></div></div>
    <a class="z-link bcard-more" href="${p.href}">Compound details ${arr}</a></div>
</article>`).join('');
    const sizeIdx = {}; P.forEach(p => sizeIdx[p.no] = p.def);
    const d = new Date(); d.setDate(d.getDate() + 3); $('#bp-date').value = d.toISOString().slice(0, 10); $('#bp-date').min = new Date().toISOString().slice(0, 10);
    function bdraw() {
      const nos = Object.keys(B), n = nos.length, t = tierFor(n), vials = nos.reduce((a, k) => a + B[k].qty, 0);
      const sub = nos.reduce((a, k) => a + byNo(k).sizes[B[k].size][1] * B[k].qty, 0), off = t[1] + (rep && n ? REP : 0), save = Math.round(sub * off / 100), total = sub - save;
      $$('.bcard').forEach(c => { const no = c.dataset.no, on = !!B[no], b = c.querySelector('[data-pick]'); c.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on)); b.innerHTML = on ? tick : plus;
        b.setAttribute('aria-label', (on ? 'Remove ' : 'Add ') + byNo(no).name + (on ? ' from' : ' to') + ' your set'); const q = c.querySelector('.bcard-qty'); q.hidden = !on; if (on) q.querySelector('output').textContent = B[no].qty;
        c.querySelectorAll('[data-bsize]').forEach(s => s.setAttribute('aria-pressed', String(+s.dataset.bsize === sizeIdx[no]))); c.querySelector('[data-bp]').innerHTML = lp(byNo(no).sizes[sizeIdx[no]][1]); });
      $('#bp-tiers').innerHTML = TIERS.map((x, i) => { const hi = (TIERS[i + 1] || [7])[0] - 1, lab = hi >= 6 ? `${x[0]}+` : x[0] === hi ? `${x[0]}` : `${x[0]}–${hi}`;
        return `<span role="listitem" class="bp-tier${x === t && n ? ' on' : ''}"><b>${lab}</b><small>${x[1] ? x[1] + '% off' : 'List'}</small></span>`; }).join('');
      $('#bp-items').innerHTML = nos.map(k => { const p = byNo(k), z = p.sizes[B[k].size];
        return `<li data-area="${p.area}"><span class="bp-sw">${sw}</span><span class="bp-nm"><b>${esc(p.name)}</b><small>${z[0]} · ${B[k].qty} ${B[k].qty === 1 ? 'vial' : 'vials'}</small></span><span class="bp-pr">$${z[1] * B[k].qty}</span><button type="button" class="bp-x" data-unpick="${k}" aria-label="Remove ${esc(p.name)}">×</button></li>`; }).join('');
      $('#bp-empty').hidden = n > 0; $('#bp-sum').hidden = n === 0;
      $('#bp-vials').textContent = vials; $('#bp-sub').textContent = '$' + sub; $('#bp-save').textContent = save ? '−$' + save : '$0';
      $('#bp-save-l').textContent = n === 0 ? 'Set saving' : off ? `Set saving · ${t[1]}%${rep ? ` + ${REP}% repeat` : ''}` : n < TIERS[1][0] ? `Add ${TIERS[1][0] - n} more ${TIERS[1][0] - n === 1 ? 'compound' : 'compounds'} to save ${TIERS[1][1]}%` : 'Set saving';
      $('#bp-total').textContent = '$' + total; $('#bp-state').textContent = n ? (rep ? 'Repeats monthly' : 'Ready') : 'Draft';
      const left = Math.max(0, FREE - total); $('#bp-ship').textContent = !n ? `Free cold-chain shipping on orders over $${FREE}.` : left ? `$${left} away from free cold-chain shipping.` : 'Free cold-chain shipping unlocked.';
      const nextT = TIERS.find(x => x[0] > n);
      $('#bp-add').disabled = !n; $('#bp-add').textContent = n ? `Add set to cart · $${total}` : 'Pick at least one compound';
      $('#bld-count').textContent = n ? `${n} picked · ${vials} ${vials === 1 ? 'vial' : 'vials'}${nextT ? ` · ${nextT[0] - n} more for ${nextT[1]}% off` : ' · top saving'}` : '0 picked';
      $('#bm-t').textContent = n ? `${n} picked · $${total}` : '0 picked'; $('#bld-mbar').classList.toggle('on', n > 0); $('#bld-mbar').setAttribute('aria-hidden', String(!n)); $('#bld-mbar a').tabIndex = n ? 0 : -1;
      $('#bp-datebox').hidden = !rep;
      return { nos, total, rep };
    }
    on('#bld-grid', 'click', e => {
      const pk = e.target.closest('[data-pick]'); if (pk) { const no = pk.dataset.pick; if (B[no]) delete B[no]; else B[no] = { size: sizeIdx[no], qty: 1 }; bdraw(); return; }
      const sz = e.target.closest('[data-bsize]'); if (sz) { const no = sz.closest('.bcard').dataset.no; sizeIdx[no] = +sz.dataset.bsize; if (B[no]) B[no].size = sizeIdx[no]; bdraw(); return; }
      const q = e.target.closest('[data-bq]'); if (q) { const no = q.closest('.bcard').dataset.no; B[no].qty = Math.min(20, B[no].qty + +q.dataset.bq); if (B[no].qty < 1) delete B[no]; bdraw(); } });
    on('#bp-items', 'click', e => { const x = e.target.closest('[data-unpick]'); if (x) { delete B[x.dataset.unpick]; bdraw(); } });
    on('#bp-rep', 'change', e => { rep = e.target.checked; bdraw(); });
    on('#bp-add', 'click', e => { const s = bdraw(); if (!s.nos.length) return;
      const parts = s.nos.map(k => `${byNo(k).name} ${byNo(k).sizes[B[k].size][0]}${B[k].qty > 1 ? ' ×' + B[k].qty : ''}`);
      const key = 'build-' + s.nos.map(k => `${k}.${B[k].size}.${B[k].qty}`).join('_') + (s.rep ? '-r' + $('#bp-date').value : '');
      addItem(key, `Your set · ${parts.join(' + ')}${s.rep ? ' · every 30 days from ' + $('#bp-date').value : ''}`, s.total, 1, 'metabolic', 'set');
      const b = e.currentTarget; b.textContent = 'Added to cart ✓'; setTimeout(bdraw, 1400); });
    const pre = new URLSearchParams(location.search).get('add'); if (pre && byNo(pre)) B[pre] = { size: sizeIdx[pre], qty: 1 };
    bdraw();
  }

  // ---------- preview badge: on every page until launch ----------
  if (base && !$('.pv-badge')) { const pv = document.createElement('div'); pv.className = 'pv-badge'; pv.setAttribute('role', 'note'); pv.innerHTML = '<i aria-hidden="true"></i>Preview shop · no purchases'; base.appendChild(pv); }
})();

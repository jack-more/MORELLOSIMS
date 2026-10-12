// ZUMA live vials (three r169). One renderer draws the collection cells and the drawer / product-page stage; the hero has its own.
// The same code bakes every vial still the site uses (ZUMA3D.bakeCell / bakeHero, driven by test/bake.js), so a still and the
// live vial it turns into are the same picture. Every label is printed by js/label.js (ZUMA_LABEL).
// The set: a seamless sweep in the area's light tone, warm sun through palm fronds (a cut-out that only casts shadows),
// a studio environment with soft boxes and black flags (the flags give the glass its dark edges), real transmission glass.
import * as THREE from 'three';

const Z = window.ZUMA, ZL = window.ZUMA_LABEL;
const CELL = { fov: 16.5, pos: [0, 2.7, 21], look: [0, 2.15, 0], rest: -0.12, aspect: 0.75 };      // stills: 720 x 960
const HERO = { fov: 20, dist: 15.5, tilt: [0.16, -0.22, -0.38], centre: 2.08, aspect: 0.8 };       // hero cut-outs: 880 x 1100
const LOT = ZL.LOT_SIDE, TAU = Math.PI * 2;
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const BAKE = !!window.ZUMA_BAKE;
const small = !BAKE && innerWidth < 700, dpr = () => BAKE ? 1 : Math.min(2, devicePixelRatio || 1);
function fovFor(base, imgAspect, aspect, mode) { const t = Math.tan(THREE.MathUtils.degToRad(base / 2)), wide = aspect >= imgAspect;
  return (mode === 'cover') === wide ? THREE.MathUtils.radToDeg(2 * Math.atan(t * imgAspect / aspect)) : base; }
const rand = s => () => { s |= 0; s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };

// ---------- light: a photo studio. Grey surround, two tall soft boxes, a top box, black flags left and right of camera ----------
function studioEnv(R) {
  const s = new THREE.Scene(), g = new THREE.SphereGeometry(30, 48, 24), p = g.attributes.position, col = [];
  for (let i = 0; i < p.count; i++) { const y = p.getY(i) / 30, k = y > 0 ? 0.42 + 0.25 * y : 0.42 + 0.18 * y; col.push(k, k * 0.99, k * 0.97); }
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3)); s.add(new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide })));
  const box = (w, h, pos, k, warm = 1) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(k, k * 0.98 * warm, k * 0.95 * warm), side: THREE.DoubleSide })); m.position.set(...pos); m.lookAt(0, 2, 0); s.add(m); };
  box(3.2, 16, [-10, 5, 5], 9);            // key soft box, camera left: the long highlight down the glass
  box(1.1, 16, [9.5, 5, 3], 6);            // strip, camera right: the thin second highlight
  box(14, 4, [0, 16, 0], 3.2);             // overhead
  box(10, 10, [0, 2, -18], 1.4, 1.02);     // warm bounce behind
  box(4.5, 18, [-4.2, 4, 12], 0.004); box(4.5, 18, [4.2, 4, 12], 0.004);   // black flags: dark edges on the glass
  const pm = new THREE.PMREMGenerator(R), t = pm.fromScene(s, 0.015).texture; pm.dispose(); return t; }

// ---------- the vial: 10 mL clear vial, 20 mm crimp, flip-off cap, freeze-dried cake ----------
const V2 = a => a.map(([r, y]) => new THREE.Vector2(r, y)), LZ = [0.6, 2.84];
const G = { top: new THREE.LatheGeometry(V2([[0.845, LZ[1]], [0.845, 2.92], [0.835, 3.02], [0.80, 3.10], [0.72, 3.18], [0.64, 3.24], [0.615, 3.30], [0.615, 3.4]]), 128),
  topIn: new THREE.LatheGeometry(V2([[0.79, LZ[1]], [0.79, 2.92], [0.78, 3.0], [0.745, 3.08], [0.67, 3.15], [0.585, 3.22], [0.56, 3.28], [0.56, 3.36]]), 96),
  bot: new THREE.LatheGeometry(V2([[0.001, 0.14], [0.6, 0.11], [0.76, 0.05], [0.83, 0.0], [0.845, 0.08], [0.845, LZ[0]]]), 128),
  mid: new THREE.CylinderGeometry(0.845, 0.845, LZ[1] - LZ[0], 128, 1, true).translate(0, (LZ[0] + LZ[1]) / 2, 0),
  inner: new THREE.CylinderGeometry(0.79, 0.79, LZ[1] - 0.2, 96, 1, true).translate(0, (LZ[1] + 0.2) / 2, 0),
  label: new THREE.CylinderGeometry(0.852, 0.852, LZ[1] - LZ[0] - 0.02, 192, 1, true, -Math.PI, TAU).translate(0, (LZ[0] + LZ[1]) / 2, 0),
  base: new THREE.CylinderGeometry(0.79, 0.81, 0.16, 64).translate(0, 0.08, 0), stopper: new THREE.CylinderGeometry(0.56, 0.56, 0.16, 40).translate(0, 3.33, 0),
  crimp: new THREE.LatheGeometry(V2([[0.60, 3.33], [0.655, 3.335], [0.676, 3.37], [0.676, 3.72], [0.665, 3.76], [0.60, 3.78], [0.52, 3.78]]), 96),
  cap: new THREE.LatheGeometry(V2([[0.001, 4.09], [0.56, 4.09], [0.60, 4.085], [0.635, 4.07], [0.655, 4.045], [0.665, 4.0], [0.665, 3.80], [0.64, 3.78], [0.001, 3.78]]), 96),
  capDish: new THREE.CylinderGeometry(0.5, 0.5, 0.012, 64).translate(0, 4.084, 0),
  cake: new THREE.CylinderGeometry(0.775, 0.775, 0.3, 72, 4).translate(0, 0.31, 0) };
// the cake: a slightly domed, cracked top and a shrink gap at the wall, the way a freeze-dried plug sits in a vial
{ const p = G.cake.attributes.position, r1 = rand(7); for (let i = 0; i < p.count; i++) { const y = p.getY(i), x = p.getX(i), z = p.getZ(i), r = Math.hypot(x, z), a = Math.atan2(z, x);
    if (y > 0.45) p.setY(i, y + 0.025 * (1 - (r / 0.775) ** 2) + 0.012 * Math.sin(a * 5 + r * 13) + 0.006 * (r1() - 0.5));
    if (r > 0.7) { const k = 0.745 / r; p.setX(i, x * k); p.setZ(i, z * k); } } G.cake.computeVertexNormals(); }
function noiseTex(n, seed, lo, hi) { const c = document.createElement('canvas'); c.width = c.height = n; const x = c.getContext('2d'), d = x.createImageData(n, n), r = rand(seed);
  for (let i = 0; i < n * n; i++) { const v = (lo + (hi - lo) * r()) * 255; d.data[i * 4] = d.data[i * 4 + 1] = d.data[i * 4 + 2] = v; d.data[i * 4 + 3] = 255; } x.putImageData(d, 0, 0);
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; return t; }
const PAPER_BUMP = noiseTex(256, 3, 0.35, 0.65); PAPER_BUMP.repeat.set(10, 3);
const CAKE_BUMP = noiseTex(128, 9, 0, 1); CAKE_BUMP.repeat.set(3, 3);
const M = { glass: new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0.02, transmission: 1, thickness: 0.09, ior: 1.52, specularIntensity: 1, attenuationColor: new THREE.Color('#dcebe6'), attenuationDistance: 2.4, envMapIntensity: 1.25, side: THREE.DoubleSide }),
  glassIn: new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0.03, transmission: 1, thickness: 0.05, ior: 1.52, envMapIntensity: 0.7, side: THREE.BackSide }),
  base: new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0.02, transmission: 1, thickness: 0.6, ior: 1.52, attenuationColor: new THREE.Color('#cfe6df'), attenuationDistance: 0.7 }),
  alu: new THREE.MeshPhysicalMaterial({ color: 0xd9dcdf, metalness: 1, roughness: 0.18, anisotropy: 0.85, anisotropyRotation: Math.PI / 2, envMapIntensity: 1.3 }),
  rubber: new THREE.MeshStandardMaterial({ color: 0x5d6166, roughness: 0.75 }),
  cake: new THREE.MeshStandardMaterial({ color: 0xf6f3ec, roughness: 0.96, bumpMap: CAKE_BUMP, bumpScale: 1.6, envMapIntensity: 0.5 }) };
// clear glass for transparent cut-outs (transmission needs something behind it, so baked cut-outs use a thin reflective shell)
const SHELL = { glass: new THREE.MeshPhysicalMaterial({ color: 0xf4f8fb, roughness: 0.03, transparent: true, opacity: 0.16, envMapIntensity: 2.4, clearcoat: 1, clearcoatRoughness: 0.03, depthWrite: false, side: THREE.DoubleSide }),
  base: new THREE.MeshPhysicalMaterial({ color: 0xeef5f3, roughness: 0.05, transparent: true, opacity: 0.35, envMapIntensity: 1.8, depthWrite: false }) };
const LK = small ? 0.5 : 0.75, labels = [];
function labelTex(i, mg) { const p = Z.P[i], d = Z.labelData(p, mg);
  if (!labels[i]) { const c = ZL.canvas(d, LK), t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; labels[i] = { c, t, mg: d.mg }; return labels[i].t; }
  const L = labels[i]; if (mg && mg !== L.mg) { const x = L.c.getContext('2d'); x.setTransform(1, 0, 0, 1, 0, 0); x.clearRect(0, 0, L.c.width, L.c.height); x.scale(LK, LK); ZL.draw(x, d); L.t.needsUpdate = true; L.mg = d.mg; }
  return L.t; }
function vial(i) { const p = Z.P[i], g = new THREE.Group(), add = (geo, mat, tag) => { const m = new THREE.Mesh(geo, mat); m.castShadow = m.receiveShadow = true; if (tag) m.userData.glass = tag; g.add(m); return m; };
  add(G.cake, M.cake);
  // printed label: paper with a light satin varnish, so the soft box draws a soft sheen across it
  add(G.label, new THREE.MeshPhysicalMaterial({ map: labelTex(i), alphaTest: 0.5, roughness: 0.42, bumpMap: PAPER_BUMP, bumpScale: 0.25, clearcoat: 0.45, clearcoatRoughness: 0.22, envMapIntensity: 0.8 }));
  add(G.stopper, M.rubber); add(G.crimp, M.alu);
  add(G.top, M.glass, 'glass'); add(G.bot, M.glass, 'glass'); add(G.mid, M.glass, 'glass'); add(G.base, M.base, 'base'); add(G.inner, M.glassIn, 'in'); add(G.topIn, M.glassIn, 'in');
  // flip-off cap: moulded polypropylene, satin with a crisp edge highlight
  const capM = new THREE.MeshPhysicalMaterial({ color: new THREE.Color(ZL.TONES[p.area][2]), roughness: 0.38, clearcoat: 0.6, clearcoatRoughness: 0.18, sheen: 0.2, envMapIntensity: 1 });
  add(G.cap, capM); add(G.capDish, new THREE.MeshPhysicalMaterial({ color: new THREE.Color(ZL.TONES[p.area][2]).multiplyScalar(0.82), roughness: 0.55 }));
  return g; }
function shellify(g, on) { g.children.forEach(m => { const k = m.userData.glass; if (!k) return; if (k === 'in') m.visible = !on;
  else m.material = on ? (k === 'base' ? SHELL.base : SHELL.glass) : (k === 'base' ? M.base : M.glass); if (k !== 'in') m.renderOrder = on ? 2 : 0; }); }

// ---------- the set: sweep, sun through palm fronds, a soft contact shadow ----------
function sweepGeo() { const geo = new THREE.PlaneGeometry(60, 66, 1, 220), p = geo.attributes.position, F = 36, Rr = 4.5, z0 = 34;
  for (let i = 0; i < p.count; i++) { const s = p.getY(i) + 33, x = p.getX(i); let y, z;
    if (s < F) { z = z0 - s; y = 0; } else if (s < F + Math.PI / 2 * Rr) { const a = (s - F) / Rr; z = z0 - F - Rr * Math.sin(a); y = Rr * (1 - Math.cos(a)); } else { z = z0 - F - Rr; y = Rr + (s - F - Math.PI / 2 * Rr); }
    p.setXYZ(i, x, y, z); }
  geo.computeVertexNormals(); return geo; }
// palm fronds, drawn white on clear: only the white parts block the sun
function frondCanvas() { const n = 1024, c = document.createElement('canvas'); c.width = c.height = n; const x = c.getContext('2d'); x.fillStyle = '#fff'; x.strokeStyle = '#fff'; x.lineCap = 'round';
  const frond = (ox, oy, ang, len, curl, seed, leaf = 0.42) => { const r = rand(seed), N = 54, pts = []; let px = ox, py = oy;
    for (let i = 0; i <= N; i++) { const t = i / N, a = ang + curl * t * t; pts.push([px, py, a, t]); px += Math.cos(a) * len / N; py += Math.sin(a) * len / N; }
    pts.forEach(([px, py, a, t], i) => { if (i < 2 || i === N) return; x.lineWidth = 9 * (1 - t) + 2; if (i) { const q = pts[i - 1]; x.beginPath(); x.moveTo(q[0], q[1]); x.lineTo(px, py); x.stroke(); }
      for (const side of [-1, 1]) { if (r() < 0.08) continue; const L = len * leaf * Math.pow(Math.sin(Math.PI * Math.min(1, t * 1.08)), 0.75) * (0.82 + 0.36 * r()), la = a + side * (0.62 + 0.3 * t + 0.1 * (r() - 0.5)), w = 22 * (1 - 0.5 * t) + 5;
        const ex = px + Math.cos(la) * L, ey = py + Math.sin(la) * L, droop = 0.18 * side, mx = px + Math.cos(la - droop) * L * 0.55, my = py + Math.sin(la - droop) * L * 0.55, nx = -Math.sin(la) * w / 2, ny = Math.cos(la) * w / 2;
        x.beginPath(); x.moveTo(px + nx, py + ny); x.quadraticCurveTo(mx + nx, my + ny, ex, ey); x.quadraticCurveTo(mx - nx, my - ny, px - nx, py - ny); x.fill(); } }); };
  frond(-80, 180, 0.28, 900, 0.5, 11, 0.36); frond(-60, 640, -0.22, 820, 0.55, 23, 0.34); frond(1100, 60, 2.6, 760, -0.45, 37, 0.34);
  const t = new THREE.CanvasTexture(c); return t; }
function contactTex() { const c = document.createElement('canvas'); c.width = c.height = 256; const x = c.getContext('2d'), g = x.createRadialGradient(128, 128, 0, 128, 128, 128);
  g.addColorStop(0, 'rgba(0,0,0,0.55)'); g.addColorStop(0.42, 'rgba(0,0,0,0.25)'); g.addColorStop(1, 'rgba(0,0,0,0)'); x.fillStyle = g; x.fillRect(0, 0, 256, 256); return new THREE.CanvasTexture(c); }
function makeSet(R, env, opts = {}) {
  const s = new THREE.Scene(); s.environment = env; s.environmentIntensity = 1;
  const sw = new THREE.Mesh(sweepGeo(), new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.95, envMapIntensity: 0.55 })); sw.receiveShadow = true; s.add(sw);
  const hemi = new THREE.HemisphereLight(0xffffff, 0xffffff, 0.55); s.add(hemi);
  // the sun: a warm, hard-ish spot from high camera-left, its pool falls off toward the corners of the frame
  const sun = new THREE.SpotLight(0xfff1dc, 9, 0, 0.42, 0.85, 0); sun.position.set(-9, 15, 11); sun.target.position.set(0.6, 1.2, -1.5); s.add(sun, sun.target);
  sun.castShadow = true; sun.shadow.mapSize.set(small ? 1024 : 2048, small ? 1024 : 2048); sun.shadow.radius = 2; sun.shadow.blurSamples = 10; sun.shadow.bias = -0.0003; sun.shadow.normalBias = 0.02; sun.shadow.camera.near = 4; sun.shadow.camera.far = 60; sun.shadow.intensity = 0.8;
  const fill = new THREE.DirectionalLight(0xe8f0ff, 0.7); fill.position.set(8, 5, 8); s.add(fill);
  // the fronds: between the sun and the set, out of the camera's view
  const gobo = new THREE.Mesh(new THREE.PlaneGeometry(9, 9), new THREE.MeshBasicMaterial({ map: frondCanvas(), alphaTest: 0.5, side: THREE.DoubleSide, colorWrite: false, depthWrite: false }));
  gobo.position.copy(sun.position).lerp(sun.target.position, 0.36); gobo.lookAt(sun.position); gobo.rotateZ(0.9); gobo.castShadow = true; s.add(gobo);
  const contact = new THREE.Mesh(new THREE.PlaneGeometry(2.9, 2.9).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ map: contactTex(), transparent: true, depthWrite: false })); contact.position.set(0.12, 0.004, -0.05); s.add(contact);
  const tint = c => { const col = new THREE.Color(c); sw.material.color.copy(col); hemi.color.set(0xffffff); hemi.groundColor.copy(col); s.background = col; };
  return { s, tint, sun, gobo, contact };
}
const newRenderer = o => { const R = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: BAKE, ...o }); R.setPixelRatio(1); R.outputColorSpace = THREE.SRGBColorSpace; R.toneMapping = THREE.NeutralToneMapping; R.toneMappingExposure = 1.0; return R; };

async function main() {
  const probe = document.createElement('canvas'); if (!(probe.getContext('webgl2') || probe.getContext('webgl'))) return;
  try { await Promise.race([Promise.all([...ZL.FONTS, "800 115px 'Schibsted Grotesk'"].map(f => document.fonts.load(f))), new Promise(r => setTimeout(r, 4000))]); } catch (e) {}
  if (!window.QRCode) await new Promise(r => { let n = 0; const t = setInterval(() => { if (window.QRCode || ++n > 40) { clearInterval(t); r(); } }, 100); });
  cells(); if (document.getElementById('hero-anchor')) hero();
  window.ZUMA3D_READY = true;
}

// ---------- collection cells + drawer / product stage: one renderer, drawn into each canvas ----------
function cells() {
  const R = newRenderer(); R.shadowMap.enabled = true; R.shadowMap.type = THREE.PCFShadowMap;
  const env = studioEnv(R), set = makeSet(R, env), s = set.s;
  const V = Z.P.map((p, i) => { const g = vial(i); g.visible = false; s.add(g); return g; });
  const cam = new THREE.PerspectiveCamera(CELL.fov, CELL.aspect, 0.1, 400);
  const cellEls = [...document.querySelectorAll('#grid .z-pcard')], cvs = cellEls.map(c => c.querySelector('canvas')), pi = cellEls.map(c => +c.dataset.i);   // pi: product index of each card
  const st = cellEls.map(() => ({ cur: CELL.rest, target: CELL.rest, dirty: true }));
  const dc = document.getElementById('d-canvas') || document.createElement('canvas'), ds = { on: false, i: 0, cur: CELL.rest, target: CELL.rest, vel: 0, dirty: false };
  let size = [0, 0]; const fit = (w, h) => { if (size[0] !== w || size[1] !== h) { R.setSize(w, h, false); size = [w, h]; } };
  function render(k, rot, w, h, mode) { fit(w, h);
    cam.aspect = w / h; cam.fov = fovFor(CELL.fov, CELL.aspect, cam.aspect, mode); cam.position.set(...CELL.pos); cam.lookAt(...CELL.look); cam.updateProjectionMatrix();
    set.tint(ZL.TONES[Z.P[k].area][0]); V.forEach((g, j) => g.visible = j === k); V[k].rotation.y = rot; R.render(s, cam); }
  function draw(k, rot, cv, mode) { const w = cv.width, h = cv.height; if (!w || !h) return; render(k, rot, w, h, mode); cv.getContext('2d').drawImage(R.domElement, 0, 0); }
  const sizeCells = () => { const vis = cvs.find(c => c.getBoundingClientRect().width > 0); if (!vis) return; const r = vis.getBoundingClientRect(), w = Math.round(r.width * dpr()), h = Math.round(r.height * dpr());
    cvs.forEach(c => { if (c.width !== w || c.height !== h) { c.width = w; c.height = h; } }); st.forEach(x => x.dirty = true); };
  const sizeDrawer = () => { const r = dc.getBoundingClientRect(), w = Math.round(r.width * dpr()), h = Math.round(r.height * dpr()); if (w && h && (dc.width !== w || dc.height !== h)) { dc.width = w; dc.height = h; } ds.dirty = true; };
  const ease = x => { const d = x.target - x.cur; if (d === 0) return; x.cur = reduce || Math.abs(d) < 1e-3 ? x.target : x.cur + d * 0.14; x.dirty = true; };
  const seen = new Set(); const io = new IntersectionObserver(es => { es.forEach(e => { const k = cellEls.indexOf(e.target); if (e.isIntersecting) { seen.add(k); st[k].dirty = true; } else seen.delete(k); }); go(); }, { rootMargin: '200px' });
  cellEls.forEach(c => io.observe(c));
  let raf = 0; const go = () => { if (!raf && !BAKE) raf = requestAnimationFrame(tick); };
  function tick() { raf = 0; let more = false;
    if (ds.on) { if (drag === null && Math.abs(ds.vel) > 0.0005) { ds.cur += ds.vel; ds.target = ds.cur; ds.vel *= 0.94; ds.dirty = true; more = true; } else ease(ds);
      if (ds.dirty) { draw(ds.i, ds.cur, dc, 'contain'); ds.dirty = false; dc.classList.add('on'); } if (ds.cur !== ds.target) more = true; }
    else st.forEach((x, k) => { if (!seen.has(k) || cellEls[k].hidden) return; ease(x); if (x.dirty) { draw(pi[k], x.cur, cvs[k], 'cover'); x.dirty = false; } if (x.cur !== x.target) more = true; });
    if (more) go(); }
  cellEls.forEach((c, k) => {
    c.addEventListener('pointerenter', e => { if (e.pointerType === 'mouse') { st[k].target = CELL.rest + LOT; go(); } });
    c.addEventListener('pointerleave', () => { st[k].target = CELL.rest; go(); });
    c.addEventListener('focusin', () => { st[k].target = CELL.rest + LOT; go(); }); c.addEventListener('focusout', () => { st[k].target = CELL.rest; go(); });
  });
  let drag = null;
  const sideOf = a => { const r = ((a - CELL.rest) % TAU + TAU) % TAU, near = t => Math.min(Math.abs(r - t), TAU - Math.abs(r - t)) < Math.PI / 4; return near(0) ? 'front' : near(LOT) ? 'lot' : null; };
  const syncUI = () => { const sd = sideOf(ds.target); if (sd) Z.setTurnUI(sd === 'lot'); };
  dc.addEventListener('pointerdown', e => { drag = { x: e.clientX, t: e.timeStamp }; ds.vel = 0; dc.setPointerCapture(e.pointerId); });
  dc.addEventListener('pointermove', e => { if (!drag) return; const d = (e.clientX - drag.x) * 0.012, dt = Math.max(8, e.timeStamp - drag.t); ds.cur = ds.target = ds.cur + d; ds.vel = reduce ? 0 : d * (16 / dt); drag.x = e.clientX; drag.t = e.timeStamp; ds.dirty = true; go(); });
  const end = () => { if (!drag) return; drag = null; setTimeout(syncUI, 600); go(); };
  dc.addEventListener('pointerup', end); dc.addEventListener('pointercancel', end);
  addEventListener('resize', () => { sizeCells(); if (ds.on) sizeDrawer(); go(); });
  window.ZUMA3D = Object.assign(window.ZUMA3D || {}, {
    drawerOpened(i) { ds.on = true; ds.i = i; ds.cur = ds.target = CELL.rest; ds.vel = 0; dc.classList.remove('on'); requestAnimationFrame(() => { sizeDrawer(); go(); }); },
    drawerClosed() { ds.on = false; st.forEach(x => x.dirty = true); dc.classList.remove('on'); go(); },
    relayout() { sizeCells(); go(); },
    turnDrawer(back) { ds.vel = 0; const base = Math.round((ds.cur - CELL.rest) / TAU) * TAU; ds.target = CELL.rest + base + (back ? LOT : 0); go(); },
    reprint(i, mg) { labelTex(i, mg); st.forEach((x, k) => { if (pi[k] === i) x.dirty = true; }); ds.dirty = true; go(); },
    // a product still: same set, lens and pose as the live cell (side 1 = the lot side)
    bakeCell(i, side = 0, w = 720, h = 960, q = 0.9) { render(i, CELL.rest + (side ? LOT : 0), w, h, 'cover'); return R.domElement.toDataURL('image/webp', q); },
    // all six in a row on sand, for the shop page header and the about plate
    bakeLineup(w = 2400, h = 1100, q = 0.9) { fit(w, h); set.tint('#E9E2D3'); const xs = V.map((g, j) => (j - 2.5) * 2.15), extra = [];
      V.forEach((g, j) => { g.visible = true; g.position.x = xs[j]; g.rotation.y = -0.18 + j * 0.05; const c = set.contact.clone(); c.position.x = xs[j] + 0.1; s.add(c); extra.push(c); }); set.contact.visible = false;
      const sp = set.sun.position.clone(), gp = set.gobo.position.clone(); set.sun.position.x -= 2; set.sun.angle = 0.6;
      cam.aspect = w / h; cam.fov = 17; cam.position.set(0, 3.4, 33); cam.lookAt(0, 1.9, 0); cam.updateProjectionMatrix(); R.render(s, cam); const url = R.domElement.toDataURL('image/webp', q);
      V.forEach(g => { g.visible = false; g.position.x = 0; }); extra.forEach(c => s.remove(c)); set.contact.visible = true; set.sun.position.copy(sp); set.gobo.position.copy(gp); set.sun.angle = 0.42; return url; }
  });
  if (BAKE) return;
  sizeCells(); tick(); const grid = document.getElementById('grid'); if (grid && cellEls.length) grid.classList.add('live');
  const d = document.getElementById('drawer'); if (d && !d.hidden) ZUMA3D.drawerOpened(Math.max(0, Z.P.findIndex(p => p.name === document.getElementById('d-lab').textContent)));
  const pdp = document.querySelector('[data-pdp]'); if (pdp && document.getElementById('d-canvas')) { ZUMA3D.drawerOpened(+pdp.dataset.pdp); const h = document.querySelector('.pdp-hint'); if (h) h.classList.add('on'); }
}

// ---------- hero: the featured vial floats across its bands. The canvas paints the bands behind itself, so the glass refracts the real page ----------
function hero() {
  const anchor = document.getElementById('hero-anchor'), cv = document.getElementById('hero-c'), hint = document.getElementById('hero-hint');
  const R = newRenderer({ canvas: cv, alpha: true }); R.setClearColor(0x000000, 0);
  const env = studioEnv(R), s = new THREE.Scene(); s.environment = env; s.environmentIntensity = 1.05;
  s.add(new THREE.HemisphereLight(0xffffff, 0xdfe6ee, 0.6)); const key = new THREE.DirectionalLight(0xfff3e2, 2.6); key.position.set(-7, 12, 9); s.add(key); const rim = new THREE.DirectionalLight(0xffffff, 1.1); rim.position.set(8, 6, -8); s.add(rim);
  const cam = new THREE.PerspectiveCamera(HERO.fov, HERO.aspect, 0.1, 400); cam.position.set(0, 0, HERO.dist); cam.lookAt(0, 0, 0);
  const piv = new THREE.Group(); piv.rotation.set(...HERO.tilt); s.add(piv);
  const cache = {}; let idx = -1, v = null;
  function use(i) { if (i === idx) return; if (v) piv.remove(v); v = cache[i] || (cache[i] = vial(i)); v.position.y = -HERO.centre; piv.add(v); idx = i; }
  // backdrop: the page behind the canvas, painted into a texture the size of the canvas
  const bc = document.createElement('canvas'), bt = new THREE.CanvasTexture(bc); bt.colorSpace = THREE.SRGBColorSpace;
  function paintBack() { const r = cv.getBoundingClientRect(); if (!r.width) return; const k = bc.width / r.width, x = bc.getContext('2d');
    const heroEl = document.getElementById('hero'); x.fillStyle = getComputedStyle(heroEl).backgroundColor || '#F7F4EE'; x.fillRect(0, 0, bc.width, bc.height);
    heroEl.querySelectorAll('.hb').forEach(b => { const q = b.getBoundingClientRect(); x.fillStyle = getComputedStyle(b).backgroundColor; x.fillRect((q.left - r.left) * k, (q.top - r.top) * k, q.width * k, q.height * k); });
    bt.needsUpdate = true; }
  let ang = 0, vel = 0, drag = null, moved = 0, raf = 0, intro = null, visible = true, paintUntil = 0;
  const go = () => { if (!raf && visible) raf = requestAnimationFrame(frame); };
  function size() { const r = anchor.getBoundingClientRect(); if (!r.width || !r.height) return; const w = Math.min(1400, Math.round(r.width * dpr())), h = Math.round(w * r.height / r.width);
    R.setSize(w, h, false); bc.width = w; bc.height = h; cam.aspect = w / h; cam.fov = fovFor(HERO.fov, HERO.aspect, cam.aspect, 'contain'); cam.updateProjectionMatrix(); paintBack(); }
  function frame(t) { raf = 0; let more = false;
    if (Date.now() < paintUntil) { paintBack(); more = true; }
    if (intro) { if (intro.t0 == null) intro.t0 = t; const p = Math.min(1, (t - intro.t0) / intro.ms), e = 1 - Math.pow(1 - p, 3); ang = intro.from * (1 - e); if (p < 1) more = true; else intro = null; }
    else if (!drag && Math.abs(vel) > 0.0004) { ang += vel; vel *= 0.955; more = true; }
    if (v) v.rotation.y = ang; R.render(s, cam); if (more) go(); }
  cv.addEventListener('pointerdown', e => { drag = { x: e.clientX, y: e.clientY, t: e.timeStamp }; moved = 0; vel = 0; intro = null; cv.setPointerCapture(e.pointerId); });
  cv.addEventListener('pointermove', e => { if (!drag) return; const dx = e.clientX - drag.x, dt = Math.max(8, e.timeStamp - drag.t); moved += Math.abs(dx) + Math.abs(e.clientY - drag.y);
    const d = dx * 0.011; ang += d; vel = reduce ? 0 : d * (16 / dt); drag.x = e.clientX; drag.y = e.clientY; drag.t = e.timeStamp; go(); });
  const end = () => { if (!drag) return; drag = null; if (moved < 6) { vel = 0; Z.openProduct(idx); return; } go(); };
  cv.addEventListener('pointerup', end); cv.addEventListener('pointercancel', () => { drag = null; go(); });
  new IntersectionObserver(es => { visible = es[0].isIntersecting; if (visible) go(); }).observe(anchor);
  addEventListener('resize', () => { size(); go(); });
  window.ZUMA3D = Object.assign(window.ZUMA3D || {}, {
    heroShow(i) { use(i); paintUntil = Date.now() + 800; intro = reduce ? null : { t0: null, from: -TAU * 0.75, ms: 900 }; if (reduce) ang = 0; go(); },
    // the hero poster: a transparent cut-out at the resting pose (shell glass, since there is nothing behind it to refract)
    bakeHero(i, w = 880, h = 1100, q = 0.88) { use(i); v.rotation.y = 0; shellify(v, true); s.background = null; R.setSize(w, h, false); cam.aspect = w / h; cam.fov = HERO.fov; cam.updateProjectionMatrix();
      R.render(s, cam); const url = R.domElement.toDataURL('image/webp', q); shellify(v, false); s.background = bt; size(); return url; }
  });
  s.background = bt;
  use(Z.heroIndex ? Z.heroIndex() : 0); size();
  if (BAKE) return;
  if (!reduce) intro = { t0: null, from: -TAU, ms: 1800 };
  requestAnimationFrame(t => { frame(t); cv.classList.add('on'); anchor.classList.add('live'); hint.classList.add('on'); });
}
main();

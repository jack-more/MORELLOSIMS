import * as THREE from 'three';
import { SVGLoader } from 'three/addons/loaders/SVGLoader.js';
await window.FONTS_READY;
const R = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true }); R.setPixelRatio(1); document.body.appendChild(R.domElement);
R.outputColorSpace = THREE.SRGBColorSpace; R.toneMapping = THREE.NeutralToneMapping; R.shadowMap.enabled = true; R.shadowMap.type = THREE.PCFSoftShadowMap;
const pm = new THREE.PMREMGenerator(R);
function studioEnv(top = '#DDE3EA', mid = '#F4F2EE', bot = '#8D8A84', k = 1, gen = pm) { const s = new THREE.Scene(), g = new THREE.SphereGeometry(30, 48, 24), p = g.attributes.position, col = [], A = new THREE.Color(top), B = new THREE.Color(mid), C = new THREE.Color(bot);
  for (let i = 0; i < p.count; i++) { const y = p.getY(i) / 30, c = y > 0 ? B.clone().lerp(A, Math.min(1, y * 1.5)) : B.clone().lerp(C, Math.min(1, -y * 2.5)); c.multiplyScalar(0.85 * k); col.push(c.r, c.g, c.b); }
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3)); s.add(new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide })));
  const strip = (w, h, pos, kk) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(kk, kk, kk), side: THREE.DoubleSide })); m.position.set(...pos); m.lookAt(0, 1.5, 0); s.add(m); };
  strip(2.2, 14, [-9, 4, 6], 8 * k); strip(1.4, 14, [9, 4, 4], 5 * k); strip(14, 2.4, [0, 14, 2], 3.5 * k); strip(3, 14, [-5, 4, 9], 0.01); strip(3, 14, [5, 4, 9], 0.01);
  return gen.fromScene(s, 0.02).texture; }
const ENV_L = studioEnv(), ENV_D = studioEnv('#2A3138', '#4B5560', '#0B0D10', 0.9), ENV_C = studioEnv('#06080B', '#3A4654', '#020304', 1.7);
// ---------- vial ----------
const V2 = a => a.map(([r, y]) => new THREE.Vector2(r, y)), LZ = [0.6, 2.84];
const G = { top: new THREE.LatheGeometry(V2([[0.845, LZ[1]], [0.845, 2.92], [0.835, 3.02], [0.80, 3.10], [0.72, 3.18], [0.64, 3.24], [0.615, 3.30], [0.615, 3.4]]), 128),
  bot: new THREE.LatheGeometry(V2([[0.001, 0.14], [0.6, 0.11], [0.76, 0.05], [0.83, 0.0], [0.845, 0.08], [0.845, LZ[0]]]), 128),
  mid: new THREE.CylinderGeometry(0.845, 0.845, LZ[1] - LZ[0], 128, 1, true).translate(0, (LZ[0] + LZ[1]) / 2, 0),
  label: new THREE.CylinderGeometry(0.852, 0.852, LZ[1] - LZ[0] - 0.02, 220, 1, true, -Math.PI, Math.PI * 2).translate(0, (LZ[0] + LZ[1]) / 2, 0),
  foil: new THREE.CylinderGeometry(0.8535, 0.8535, LZ[1] - LZ[0] - 0.02, 220, 1, true, -Math.PI, Math.PI * 2).translate(0, (LZ[0] + LZ[1]) / 2, 0),
  base: new THREE.CylinderGeometry(0.80, 0.82, 0.13, 64).translate(0, 0.065, 0), stopper: new THREE.CylinderGeometry(0.56, 0.56, 0.16, 40).translate(0, 3.33, 0),
  crimp: new THREE.LatheGeometry(V2([[0.60, 3.33], [0.655, 3.335], [0.676, 3.37], [0.676, 3.72], [0.665, 3.76], [0.60, 3.78], [0.52, 3.78]]), 96),
  cap: new THREE.CylinderGeometry(0.655, 0.665, 0.30, 72).translate(0, 3.93, 0), capTop: new THREE.CylinderGeometry(0.58, 0.58, 0.02, 72).translate(0, 4.085, 0),
  capRing: new THREE.TorusGeometry(0.62, 0.032, 12, 72).rotateX(Math.PI / 2).translate(0, 4.075, 0), cake: new THREE.CylinderGeometry(0.77, 0.77, 0.46, 72, 6).translate(0, 0.37, 0) };
{ const p = G.cake.attributes.position; for (let i = 0; i < p.count; i++) { const y = p.getY(i); if (y > 0.59) { const a = Math.atan2(p.getZ(i), p.getX(i)), r = Math.hypot(p.getX(i), p.getZ(i)); p.setY(i, y - 0.04 * (r / 0.77) ** 2 + 0.015 * Math.sin(a * 6 + r * 11)); } } G.cake.computeVertexNormals(); }
const M = { glass: new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0, transmission: 1, thickness: 0.12, ior: 1.5, attenuationColor: new THREE.Color('#e8f1ee'), attenuationDistance: 5, envMapIntensity: 1.5, side: THREE.DoubleSide }),
  base: new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0.03, transmission: 1, thickness: 0.5, ior: 1.52, attenuationColor: new THREE.Color('#d6ebe5'), attenuationDistance: 0.9 }),
  alu: new THREE.MeshPhysicalMaterial({ color: 0xd6d9dc, metalness: 1, roughness: 0.22, anisotropy: 0.8, anisotropyRotation: Math.PI / 2 }), rubber: new THREE.MeshStandardMaterial({ color: 0x6d7176, roughness: 0.8 }),
  cake: new THREE.MeshStandardMaterial({ color: 0xfbfaf6, roughness: 0.9, envMapIntensity: 0.6 }) };
const tex = c => { const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 16; return t; };
async function vial(d, no) { const p = L2.P(no), g = new THREE.Group(), add = (geo, mat) => { const m = new THREE.Mesh(geo, mat); m.castShadow = m.receiveShadow = true; g.add(m); return m; };
  const lc = await ART(d.id, 'label', no), mode = d.mode;
  let lm; if (mode.type === 'holo') lm = new THREE.MeshPhysicalMaterial({ map: tex(lc), alphaTest: 0.5, metalness: 0.85, roughness: 0.2, iridescence: 1, iridescenceIOR: 1.7, iridescenceThicknessRange: [180, 820], envMapIntensity: 1.3 });
  else lm = new THREE.MeshPhysicalMaterial({ map: tex(lc), alphaTest: 0.5, roughness: 0.5, clearcoat: 0.35, clearcoatRoughness: 0.3, envMapIntensity: 0.7 });
  if (mode.emissive) { lm.emissiveMap = lm.map; lm.emissive = new THREE.Color('#ffffff'); lm.emissiveIntensity = mode.emissive; }
  if (mode.bump) { const bc = L2.cv(L2.LW, L2.LH), bx = bc.getContext('2d'); bx.fillStyle = '#000'; bx.fillRect(0, 0, bc.width, bc.height); bx.filter = 'blur(3px)'; mode.bump(bx, p); const bt = new THREE.CanvasTexture(bc); bt.anisotropy = 16; lm.bumpMap = bt; lm.bumpScale = 6; lm.roughness = 0.62; lm.clearcoat = 0.1; }
  add(G.cake, M.cake); add(G.label, lm);
  if (mode.foil) { const fc = L2.cv(L2.LW, L2.LH), fx = fc.getContext('2d'); fx.fillStyle = '#000'; fx.fillRect(0, 0, fc.width, fc.height); mode.foil(fx, p); const ft = new THREE.CanvasTexture(fc); ft.anisotropy = 16;
    add(G.foil, new THREE.MeshPhysicalMaterial({ color: new THREE.Color(mode.foilColor || '#C9A24A'), metalness: 1, roughness: 0.28, alphaMap: ft, alphaTest: 0.5, envMapIntensity: 1.6 })); }
  add(G.stopper, M.rubber); add(G.top, M.glass); add(G.bot, M.glass); add(G.mid, M.glass); add(G.base, M.base); add(G.crimp, M.alu);
  const capM = new THREE.MeshPhysicalMaterial({ color: new THREE.Color(mode.cap(p)), roughness: 0.45, clearcoat: 0.25, clearcoatRoughness: 0.35 }); add(G.cap, capM); add(G.capTop, capM); add(G.capRing, capM); return g; }
// ---------- studio ----------
function sweep(color, zf = 16) { const L = 90 + zf - 16, F = 30 + zf - 16, Rr = 7, geo = new THREE.PlaneGeometry(90, L, 1, 240), p = geo.attributes.position;
  for (let i = 0; i < p.count; i++) { const s = (p.getY(i) + L / 2), x = p.getX(i); let y, z; const zf = 16;
    if (s < F) { z = zf - s; y = 0; } else if (s < F + Math.PI / 2 * Rr) { const a = (s - F) / Rr; z = zf - F - Rr * Math.sin(a); y = Rr * (1 - Math.cos(a)); } else { z = zf - F - Rr; y = Rr + (s - F - Math.PI / 2 * Rr); }
    p.setXYZ(i, x, y, z); }
  geo.computeVertexNormals(); const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: new THREE.Color(color), roughness: 0.92, side: THREE.DoubleSide })); m.receiveShadow = true; return m; }
function slats() { const c = L2.cv(1024, 1024), x = c.getContext('2d'); x.fillStyle = '#fff'; for (let i = 0; i < 9; i++) x.fillRect(0, 40 + i * 110, 1024, 60); x.fillRect(0, 0, 60, 1024); x.fillRect(964, 0, 60, 1024); x.fillRect(482, 0, 60, 1024); return new THREE.CanvasTexture(c); }
function frondTex(k) { const c = L2.cv(2048, 2048), x = c.getContext('2d'); x.fillStyle = '#fff'; L2.frond(x, k, 150, 1850, -48, 4.6, 0); L2.frond(x, k, 1900, 1950, -132, 3.6, 1); return new THREE.CanvasTexture(c); }
async function chromeLogo() { const loader = new SVGLoader(), sc = 11 / UNB.w; const data = loader.parse(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -800 ${UNB.w} 820"><path d="${UNB.d}"/></svg>`);
  const grp = new THREE.Group(), mat = new THREE.MeshPhysicalMaterial({ color: '#F4F7FA', metalness: 1, roughness: 0.05, envMap: ENV_C, envMapIntensity: 2.6, clearcoat: 1, clearcoatRoughness: 0.05 });
  data.paths.forEach(path => SVGLoader.createShapes(path).forEach(sh => { const geo = new THREE.ExtrudeGeometry(sh, { depth: 260, bevelEnabled: true, bevelThickness: 30, bevelSize: 18, bevelSegments: 5, curveSegments: 16 }); const m = new THREE.Mesh(geo, mat); m.castShadow = true; m.receiveShadow = true; grp.add(m); }));
  grp.scale.set(sc, -sc, sc); grp.position.set(-UNB.w * sc / 2, 3.75, -6.5); return grp; }
async function stage(d) { const st = d.stage, dark = !!st.dark; const s = new THREE.Scene(); s.environment = dark ? ENV_D : ENV_L; s.environmentIntensity = dark ? 0.8 : 0.95; s.background = new THREE.Color(st.sweep);
  s.add(sweep(st.sweep, st.front || 16)); s.add(new THREE.HemisphereLight(new THREE.Color(st.tint || '#ffffff'), new THREE.Color(st.sweep), dark ? 0.35 : 0.85));
  const key = new THREE.DirectionalLight(new THREE.Color(st.key || '#ffffff'), dark ? 2.2 : st.hard ? 3.2 : 2.5); key.position.set(-7, 12, 9); key.target.position.set(0, 1.5, 0); s.add(key, key.target);
  key.castShadow = true; key.shadow.mapSize.set(4096, 4096); key.shadow.radius = st.hard ? 2 : 7; key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02; Object.assign(key.shadow.camera, { left: -12, right: 12, top: 12, bottom: -12, near: 1, far: 50 }); key.shadow.intensity = 0.75;
  const rim = new THREE.DirectionalLight(new THREE.Color(st.rim ? st.rim[0] : dark ? '#9FD8FF' : '#ffffff'), st.rim ? st.rim[1] : dark ? 2.4 : 0.9); rim.position.set(8, 6, -8); s.add(rim);
  if (st.rim2) { const r2 = new THREE.DirectionalLight(new THREE.Color(st.rim2[0]), st.rim2[1]); r2.position.set(-9, 4, -6); s.add(r2); }
  if (st.gobo || st.slats) { const t = st.slats ? slats() : frondTex(st.gobo); const g = new THREE.Mesh(new THREE.PlaneGeometry(st.slats ? 9 : 13, st.slats ? 9 : 13), new THREE.MeshBasicMaterial({ map: t, alphaTest: 0.5, side: THREE.DoubleSide, colorWrite: false, depthWrite: false }));
    g.position.set(-3.6, 7.2, 4.2); g.lookAt(key.position); g.rotateZ(st.slats ? 0.35 : 1.1); g.castShadow = true; s.add(g); }
  if (st.chromeLogo) s.add(await chromeLogo());
  R.toneMappingExposure = dark ? 1.05 : 1.0; return s; }
function finish(w, h, { vig = 0.14, grain = 0.04 } = {}) { const c = L2.cv(w, h), x = c.getContext('2d'); x.drawImage(R.domElement, 0, 0);
  const g = x.createRadialGradient(w / 2, h * 0.46, Math.min(w, h) * 0.35, w / 2, h / 2, Math.hypot(w, h) * 0.62); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, `rgba(0,0,0,${vig})`); x.fillStyle = g; x.fillRect(0, 0, w, h);
  L2.grain(x, w, h, grain, 9); return c; }
window.SHOTS = {
  async trio(w, h, id) { const d = DIRS.find(v => v.id === id), s = await stage(d);
    const place = [['02', [-2.35, 0, -1.3], -0.55], ['04', [2.45, 0, -1.4], 0.25], ['01', [0.15, 0, 0.7], -0.14]];
    for (const [no, pos, ry] of place) { const v = await vial(d, no); v.position.set(...pos); v.rotation.y = ry; s.add(v); }
    const cam = new THREE.PerspectiveCamera(22, w / h, 0.1, 400); cam.position.set(0, 3.1, 17.5); cam.lookAt(0, 1.95, -0.3); R.setSize(w, h, false); R.render(s, cam);
    const c = finish(w, h); window.LAST = c; return c.toDataURL('image/jpeg', 0.92); },
  async hero(w, h, id) { if (!window.LAST) return null; window.HERO_SRC = window.HERO_SRC || {}; window.HERO_SRC[id] = window.LAST.toDataURL('image/jpeg', 0.9); return FLAT(id, 'hero', '01', 'image/jpeg', 0.9); }
};

// ---------- finishes: cap, crimp and label-stock options on one vial ----------
const FIN = [
  ['white-silver', 'Gloss white cap, silver crimp', { cap: '#F6F6F3', capR: 0.18 }],
  ['black-silver', 'Matte black cap, silver crimp', { cap: '#15171A', capR: 0.7, cc: 0 }],
  ['blackout', 'Matte black cap, black crimp', { cap: '#141518', capR: 0.7, cc: 0, crimp: '#1C1D20', crimpR: 0.35 }],
  ['navy-gold', 'Navy cap, gold crimp', { cap: '#13213F', capR: 0.4, crimp: '#D3A84F' }],
  ['black-gold', 'Gloss black cap, gold crimp', { cap: '#0E0F11', capR: 0.12, crimp: '#D3A84F' }],
  ['area-silver', 'Area-colour cap, silver crimp', { cap: '#1F45E0', capR: 0.35 }],
  ['matched', 'Colour-matched cap and crimp', { cap: '#1F45E0', capR: 0.35, crimp: '#2A4FE6', crimpR: 0.28 }],
  ['rose', 'Blush cap, rose-gold crimp', { cap: '#E9BFB3', capR: 0.4, crimp: '#D79C86' }],
  ['copper', 'Forest cap, copper crimp', { cap: '#173A2B', capR: 0.45, crimp: '#C27A4C' }],
  ['frost', 'Frosted clear cap', { frost: true }],
  ['chrome', 'Mirror chrome cap', { cap: '#E8ECEF', capMetal: 1, capR: 0.06 }],
  ['red', 'Lifeguard red cap', { cap: '#D7262B', capR: 0.3 }],
  ['printed', 'Printed cap top', { cap: '#13213F', capR: 0.35, print: true }],
  ['wax-red', 'Red wax dip', { wax: '#B3161C' }],
  ['wax-black', 'Black wax dip', { wax: '#121214' }],
  ['wax-cream', 'Cream wax dip', { wax: '#EEE6D3' }],
  ['stock-gloss', 'Label stock: high gloss', { stock: 'gloss' }],
  ['stock-clear', 'Label stock: clear film', { stock: 'clear' }],
  ['stock-silver', 'Label stock: brushed silver', { stock: 'silver' }],
  ['stock-kraft', 'Label stock: uncoated kraft', { stock: 'kraft' }],
  ['stock-holo', 'Label stock: holographic', { stock: 'holo' }],
];
window.FIN = FIN.map(([id, name]) => ({ id, name }));
const glassR = y => { const P = [[2.84, 0.845], [2.92, 0.845], [3.02, 0.835], [3.10, 0.80], [3.18, 0.72], [3.24, 0.64], [3.30, 0.615], [3.5, 0.615]]; if (y <= P[0][0]) return 0.845; for (let i = 1; i < P.length; i++) if (y <= P[i][0]) { const [y0, r0] = P[i - 1], [y1, r1] = P[i], t = (y - y0) / (y1 - y0); return r0 + (r1 - r0) * t; } return 0.615; };
function waxGeo(seed) { const rows = [[0.700, 3.30], [0.702, 3.34], [0.705, 3.40], [0.706, 3.48], [0.706, 3.60], [0.705, 3.80], [0.704, 3.98], [0.698, 4.07], [0.672, 4.125], [0.6, 4.152], [0.4, 4.165], [0.001, 4.17]];
  const geo = new THREE.LatheGeometry(V2(rows), 320), p = geo.attributes.position, r = L2.rng(seed), drips = [];
  for (let k = 0; k < 11; k++) drips.push([r() * Math.PI * 2, 0.07 + r() * 0.1, k < 4 ? 0.22 + r() * 0.3 : 0.05 + r() * 0.16]);
  for (let i = 0; i < p.count; i++) { const x = p.getX(i), y = p.getY(i), z = p.getZ(i), a = Math.atan2(z, x), w = Math.max(0, 1 - (y - 3.30) / 0.3); if (w <= 0) continue;
    let d = 0.03 + 0.02 * Math.sin(a * 7 + 1.3) + 0.015 * Math.sin(a * 13); for (const [c, s, A] of drips) { let da = Math.abs(a - c); da = Math.min(da, Math.PI * 2 - da); d += A * Math.exp(-((da / s) ** 2)); }
    const ny = y - d * w * w, rr = Math.hypot(x, z), need = glassR(ny) + 0.035 * (0.6 + 0.4 * w), nr = Math.max(rr, need); p.setXYZ(i, x / rr * nr, ny, z / rr * nr); }
  geo.computeVertexNormals(); return geo; }
function capPrint() { const c = L2.cv(512, 512), x = c.getContext('2d'); x.fillStyle = '#13213F'; x.fillRect(0, 0, 512, 512); x.strokeStyle = '#E9E3D3'; x.lineWidth = 6; x.beginPath(); x.arc(256, 256, 214, 0, 7); x.stroke();
  L2.arcText(x, 'ZUMA · MALIBU · RESEARCH USE ONLY · ZUMA · MALIBU ·', 256, 256, 178, 0, { size: 30, weight: 800, family: "'Hanken Grotesk'", fill: '#E9E3D3', ls: 6 });
  L2.T(x, 'Z', 256, 300, { size: 150, family: "'Gilda Display'", fill: '#E9E3D3', align: 'center' }); return c; }
function stockCanvas(lc, kind) { const c = L2.cv(lc.width, lc.height), x = c.getContext('2d'); x.drawImage(lc, 0, 0);
  if (kind === 'clear' || kind === 'silver') { const id = x.getImageData(0, 0, c.width, c.height), d = id.data; for (let i = 0; i < d.length; i += 4) { if (d[i + 3] < 10) continue; const m = Math.min(d[i], d[i + 1], d[i + 2]); if (m > 225) { if (kind === 'clear') d[i + 3] = 0; else { d[i] = d[i + 1] = d[i + 2] = 200; } } } x.putImageData(id, 0, 0); }
  if (kind === 'kraft') { x.globalCompositeOperation = 'multiply'; x.fillStyle = '#C9A57A'; x.fillRect(0, 0, c.width, c.height); x.globalCompositeOperation = 'source-over'; L2.grain(x, c.width, c.height, 0.09, 4); x.globalCompositeOperation = 'destination-in'; x.drawImage(lc, 0, 0); x.globalCompositeOperation = 'source-over'; }
  return c; }
async function finishVial(f) { const d = DIRS.find(v => v.id === 'wide'), g = await vial(d, '01'), parts = {}; g.children.forEach(m => { for (const k of ['cap', 'capTop', 'capRing', 'crimp', 'label']) if (m.geometry === G[k]) parts[k] = m; });
  if (f.cap || f.frost) { const cm = f.frost ? new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0.42, transmission: 1, thickness: 0.6, ior: 1.45, attenuationColor: new THREE.Color('#dfe9ec'), attenuationDistance: 1.2 })
      : new THREE.MeshPhysicalMaterial({ color: new THREE.Color(f.cap), roughness: f.capR ?? 0.45, metalness: f.capMetal || 0, clearcoat: f.cc ?? 0.35, clearcoatRoughness: 0.25, envMapIntensity: f.capMetal ? 1.6 : 1 });
    parts.cap.material = parts.capRing.material = cm; parts.capTop.material = cm;
    if (f.print) { const pm2 = cm.clone(); pm2.map = tex(capPrint()); pm2.map.center.set(0.5, 0.5); pm2.map.rotation = -Math.PI / 2; pm2.color = new THREE.Color('#ffffff'); parts.capTop.material = pm2; } }
  if (f.crimp) parts.crimp.material = new THREE.MeshPhysicalMaterial({ color: new THREE.Color(f.crimp), metalness: 1, roughness: f.crimpR ?? 0.24, anisotropy: 0.8, anisotropyRotation: Math.PI / 2 });
  if (f.wax) { [parts.cap, parts.capTop, parts.capRing, parts.crimp].forEach(m => m.visible = false); const wm = new THREE.Mesh(waxGeo(7 + f.wax.length), new THREE.MeshPhysicalMaterial({ color: new THREE.Color(f.wax), roughness: 0.32, clearcoat: 0.8, clearcoatRoughness: 0.2, sheen: 0.3, sheenColor: new THREE.Color('#ffffff') })); wm.castShadow = wm.receiveShadow = true; g.add(wm); }
  if (f.stock) { const lc = await ART('wide', 'label', '01'), lm = parts.label.material;
    if (f.stock === 'gloss') { lm.roughness = 0.08; lm.clearcoat = 1; lm.clearcoatRoughness = 0.02; lm.envMapIntensity = 1.2; }
    if (f.stock === 'clear') { lm.map = tex(stockCanvas(lc, 'clear')); lm.roughness = 0.15; lm.clearcoat = 0.6; lm.transparent = true; lm.depthWrite = true; }
    if (f.stock === 'silver') { lm.map = tex(stockCanvas(lc, 'silver')); lm.metalness = 0.9; lm.roughness = 0.32; lm.envMapIntensity = 1.5; lm.clearcoat = 0.2; }
    if (f.stock === 'kraft') { lm.map = tex(stockCanvas(lc, 'kraft')); lm.roughness = 0.85; lm.clearcoat = 0; }
    if (f.stock === 'holo') { lm.metalness = 0.75; lm.roughness = 0.22; lm.iridescence = 1; lm.iridescenceIOR = 1.7; lm.iridescenceThicknessRange = [180, 820]; lm.envMapIntensity = 1.3; } }
  if (f.noGlass) g.children.forEach(m => { if (m.geometry === G.mid || m.geometry === G.top || m.geometry === G.bot) m.visible = false; });
  return g; }
window.SHOTS.finish = async function (w, h, fid) { const f = FIN.find(v => v[0] === fid)[2], s = await stage({ stage: { sweep: '#E7E4DE', gobo: 'palm' } });
  const v = await finishVial(f); v.position.set(0.1, 0, 0); v.rotation.y = -0.1; s.add(v);
  const cam = new THREE.PerspectiveCamera(23, w / h, 0.1, 400); cam.position.set(0, 8.4, 13.4); cam.lookAt(0.05, 2.05, 0); R.setSize(w, h, false); R.render(s, cam); return finish(w, h, { vig: 0.12 }).toDataURL('image/jpeg', 0.92); };
// ================= site3: Tricolor site stills =================
// Framing and lights here are mirrored in src/js/vials3d.js so the stills and the live vials line up when one replaces the other.
const ZL = window.ZUMA_LABEL, TRI = () => DIRS.find(v => v.id === 'tricolor');
const CELL = { fov: 16.5, pos: [0, 2.7, 21], look: [0, 2.4, 0], rest: -0.12 };
const HERO = { fov: 20, dist: 15.5, tilt: [0.16, -0.22, -0.38], centre: 2.08 };
let RA = null, ENV_A = null; // a second renderer with an alpha channel, for cut-outs (with its own environment map: PMREM textures belong to one GL context)
const alphaR = () => { if (!RA) { RA = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true, premultipliedAlpha: false }); RA.setPixelRatio(1); RA.outputColorSpace = THREE.SRGBColorSpace; RA.toneMapping = THREE.NeutralToneMapping; RA.setClearColor(0x000000, 0); ENV_A = studioEnv(undefined, undefined, undefined, 1, new THREE.PMREMGenerator(RA)); } return RA; };
// flat studio: a seamless single-colour sweep (the background is the clear colour, so it prints the exact hex), a soft key and a contact shadow
function flatStudio(bg, floor = true) { const s = new THREE.Scene(); s.environment = ENV_L; s.environmentIntensity = 0.95; if (bg) s.background = new THREE.Color(bg);
  s.add(new THREE.HemisphereLight(0xffffff, new THREE.Color(bg || '#dfe6ee'), 0.85));
  const key = new THREE.DirectionalLight(0xffffff, 2.5); key.position.set(-7, 12, 9); key.target.position.set(0, 1.5, 0); s.add(key, key.target);
  key.castShadow = true; key.shadow.mapSize.set(2048, 2048); key.shadow.radius = 9; key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02; Object.assign(key.shadow.camera, { left: -6, right: 6, top: 6, bottom: -6, near: 1, far: 50 });
  const rim = new THREE.DirectionalLight(0xffffff, 0.9); rim.position.set(8, 6, -8); s.add(rim);
  if (floor) { const fl = new THREE.Mesh(new THREE.PlaneGeometry(60, 60).rotateX(-Math.PI / 2), new THREE.ShadowMaterial({ opacity: 0.2 })); fl.receiveShadow = true; s.add(fl); }
  return s; }
// clear glass for cut-outs on a transparent background (transmission needs an opaque backdrop, so the glass becomes a thin reflective shell)
const shell = new THREE.MeshPhysicalMaterial({ color: 0xf4f8fb, roughness: 0.04, transparent: true, opacity: 0.2, envMapIntensity: 2.2, clearcoat: 1, clearcoatRoughness: 0.04, depthWrite: false, side: THREE.DoubleSide });
const shellBase = new THREE.MeshPhysicalMaterial({ color: 0xeef5f3, roughness: 0.06, transparent: true, opacity: 0.4, envMapIntensity: 1.6, depthWrite: false });
function toShell(g) { g.children.forEach(m => { if (m.material === M.glass) { m.material = shell; m.renderOrder = 2; } else if (m.material === M.base) { m.material = shellBase; m.renderOrder = 2; } }); return g; }
const webp = (r, q = 0.9) => r.domElement.toDataURL('image/webp', q);
Object.assign(window.SHOTS, {
  // one vial, front (side 0) or lot side (side 1), on its area's light tone; same camera as the collection cells
  async single(w, h, no, side = 0) { const p = L2.P(no), s = flatStudio(ZL.TONES[p.area][0]); const v = await vial(TRI(), no); v.rotation.y = CELL.rest + (side ? ZL.LOT_SIDE : 0); s.add(v);
    const cam = new THREE.PerspectiveCamera(CELL.fov, w / h, 0.1, 400); cam.position.set(...CELL.pos); cam.lookAt(...CELL.look); R.toneMappingExposure = 1; R.setSize(w, h, false); R.render(s, cam); return webp(R); },
  // the hero vial as a transparent cut-out at its resting pose; the live hero uses the same pose and lens
  async cutout(w, h, no) { const r = alphaR(), s = flatStudio(null, false); s.environment = ENV_A; const v = toShell(await vial(TRI(), no)), piv = new THREE.Group(); v.position.y = -HERO.centre; piv.add(v); piv.rotation.set(...HERO.tilt); s.add(piv);
    const cam = new THREE.PerspectiveCamera(HERO.fov, w / h, 0.1, 400); cam.position.set(0, 0, HERO.dist); cam.lookAt(0, 0, 0); r.setSize(w, h, false); r.render(s, cam); return webp(r, 0.88); },
  // four areas on a light sweep (og image, about plate)
  async four(w, h, sweepCol = '#E9E2D3') { const s = await stage({ stage: { sweep: sweepCol, key: '#FFFFFF', tint: '#EEF4FB', gobo: 'fern' } });
    const place = [['02', [-3.3, 0, -1.2], -0.5], ['01', [-1.05, 0, 0.6], -0.18], ['04', [1.25, 0, 0.1], 0.12], ['05', [3.45, 0, -1.3], 0.42]];
    for (const [no, pos, ry] of place) { const v = await vial(TRI(), no); v.position.set(...pos); v.rotation.y = ry; s.add(v); }
    const cam = new THREE.PerspectiveCamera(20, w / h, 0.1, 400); cam.position.set(0, 3.2, 19.5); cam.lookAt(0, 2.25, -0.3); R.setSize(w, h, false); R.render(s, cam); return finish(w, h, { vig: 0.1, grain: 0.03 }).toDataURL('image/webp', 0.9); },
  // all six in a row
  async lineup(w, h, sweepCol = '#F2EEE6') { const s = await stage({ stage: { sweep: sweepCol, key: '#FFFFFF', tint: '#EEF2F8', gobo: 'fern', front: 60 } });
    for (let i = 0; i < 6; i++) { const no = '0' + (i + 1), v = await vial(TRI(), no); v.position.set((i - 2.5) * 2.2, 0, 0); v.rotation.y = -0.12; s.add(v); }
    const cam = new THREE.PerspectiveCamera(9.6, w / h, 0.1, 400); cam.position.set(0, 4.2, 44); cam.lookAt(0, 2.0, 0); R.setSize(w, h, false); R.render(s, cam); return finish(w, h, { vig: 0.1, grain: 0.03 }).toDataURL('image/webp', 0.9); },
  // the Collection box: six vials in a fitted tray, the Tricolor lid beside it
  async box(w, h, sweepCol = '#E9E2D3') { const s = await stage({ stage: { sweep: sweepCol, key: '#FFFFFF', tint: '#EEF4FB', gobo: 'fern' } });
    const Bx = new THREE.Group(), white = new THREE.MeshStandardMaterial({ color: '#F7F4EE', roughness: 0.85 });
    const bx = (sz, p, m = white) => { const b = new THREE.Mesh(new THREE.BoxGeometry(...sz), m); b.position.set(...p); b.castShadow = b.receiveShadow = true; Bx.add(b); return b; };
    const W = 13.4, D = 5.6, H = 2.0, t = 0.09; bx([W, t, D], [0, t / 2, 0]); bx([W, H, t], [0, H / 2, -D / 2 + t / 2]); bx([W, H, t], [0, H / 2, D / 2 - t / 2]); bx([t, H, D], [-W / 2 + t / 2, H / 2, 0]); bx([t, H, D], [W / 2 - t / 2, H / 2, 0]);
    bx([W - 2 * t, 1.3, D - 2 * t], [0, 0.65, 0], new THREE.MeshStandardMaterial({ color: '#EFEBE3', roughness: 0.95 }));
    for (let i = 0; i < 6; i++) { const v = await vial(TRI(), '0' + (i + 1)); v.rotation.x = -Math.PI / 2; v.position.set((i - 2.5) * 2.08, 1.3 + 0.845 * 0.3, 2.05); Bx.add(v); }
    const lc = await ART('tricolor', 'lid'), lidTop = new THREE.MeshStandardMaterial({ map: tex(lc), roughness: 0.8 });
    const lid = new THREE.Mesh(new THREE.BoxGeometry(W + 0.12, 0.7, D + 0.12), [white, white, lidTop, white, white, white]); lid.castShadow = lid.receiveShadow = true; lid.position.set(-1.0, 0.35, -7.0); lid.rotation.y = 0.06; s.add(lid);
    Bx.rotation.y = -0.08; Bx.position.set(0.6, 0, 0.4); s.add(Bx);
    const cam = new THREE.PerspectiveCamera(26, w / h, 0.1, 400); cam.position.set(0, 30, 16); cam.lookAt(0, 0, -2.4); R.setSize(w, h, false); R.render(s, cam); return finish(w, h, { vig: 0.1, grain: 0.03 }).toDataURL('image/webp', 0.9); },
  // close-up of the lot side: code and lot record
  async detail(w, h, no = '01') { const p = L2.P(no), s = flatStudio(ZL.TONES[p.area][0]); const v = await vial(TRI(), no); v.rotation.y = ZL.LOT_SIDE - 0.1; s.add(v);
    const cam = new THREE.PerspectiveCamera(17, w / h, 0.1, 400); cam.position.set(0.2, 3.0, 12.5); cam.lookAt(0, 2.2, 0); R.setSize(w, h, false); R.render(s, cam); return webp(R); },
  async flat(no, w) { return LABEL_FLAT(no, w); }
});
window.SCENE_READY = true;

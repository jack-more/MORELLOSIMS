// YOJO vessel: the real production model, twisted by hand.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { Reflector } from 'three/addons/objects/Reflector.js';

const LIFT = 0.009;          // one turn lifts the head 9 mm
const PRESS = 0.004;         // press stroke 4 mm
const TURN = Math.PI * 2;    // 3-start thread, 9 mm lead: one full turn

const SKINS = [
  { name: 'Chalk Sky', hex: '#5aaee6', swatch: '#a1d6f6' },
  { name: 'Chalk Rose', hex: '#d98a9f', swatch: '#e4aab9' },
  { name: 'Chalk Sage', hex: '#8fb56d', swatch: '#aac694' },
  { name: 'Chalk Cloud', hex: '#dcd6cc', swatch: '#ece8e1' },
  { name: 'Cobalt', hex: '#1e6fe6', swatch: '#1e77f3' },
];

const canvas = document.getElementById('stage');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x000000);
// studio for reflections: a black room with a few softboxes, so chrome reads like the hero shot
const pmrem = new THREE.PMREMGenerator(renderer);
function studio() {
  const s = new THREE.Scene(); s.background = new THREE.Color(0x020202);
  const box = (w, h, x, y, z, k, col = 0xffffff) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(col).multiplyScalar(k), side: THREE.DoubleSide }));
    m.position.set(x, y, z); m.lookAt(0, 0.05, 0); s.add(m);
  };
  box(3.0, 0.25, 0, 2.4, 0.3, 6);                 // long strip overhead
  box(0.25, 2.2, -2.2, 0.6, -1.4, 4, 0x9fc6ff);   // cool rims behind
  box(0.25, 2.2, 2.2, 0.6, -1.4, 4, 0x9fc6ff);
  box(1.6, 1.0, -1.8, 0.9, 1.8, 1.4);             // soft key, front left
  box(2.6, 0.45, 0, 0.55, -2.6, 3.0);              // low panel behind: the brushed top and the Y catch it
  box(0.18, 0.9, -1.2, 0.15, 2.0, 3.5);             // eye-level strips: the thread and knurl catch them
  box(0.18, 0.9, 1.3, 0.15, 1.8, 2.5);
  return pmrem.fromScene(s, 0.02).texture;
}
scene.environment = studio();

const camera = new THREE.PerspectiveCamera(20, 1, 0.01, 10);
const target = new THREE.Vector3(0, 0.047, 0);

// light: a narrow strip from above, cool rims behind, a soft key in front
const top = new THREE.DirectionalLight(0xffffff, 1.4); top.position.set(0.02, 0.6, 0.12); top.target.position.copy(target);
const rimL = new THREE.DirectionalLight(0x8cbcff, 3.2); rimL.position.set(-0.3, 0.15, -0.35);
const rimR = new THREE.DirectionalLight(0x8cbcff, 3.2); rimR.position.set(0.3, 0.15, -0.35);
const key = new THREE.DirectionalLight(0xffffff, 0.35); key.position.set(-0.35, 0.25, 0.45);
scene.add(top, top.target, rimL, rimR, key, new THREE.AmbientLight(0xffffff, 0.02));

// glossy black floor with a fading reflection
const floor = new Reflector(new THREE.CircleGeometry(0.6, 64), {
  textureWidth: 512, textureHeight: 512, color: 0x151515, clipBias: 0.0005,
});
floor.rotation.x = -Math.PI / 2; scene.add(floor);
const fadeTex = (() => {
  const c = document.createElement('canvas'); c.width = c.height = 256; const g = c.getContext('2d');
  const r = g.createRadialGradient(128, 128, 8, 128, 128, 128);
  r.addColorStop(0, 'rgba(0,0,0,0.5)'); r.addColorStop(0.3, 'rgba(0,0,0,0.82)'); r.addColorStop(1, 'rgba(0,0,0,1)');
  g.fillStyle = r; g.fillRect(0, 0, 256, 256); return new THREE.CanvasTexture(c);
})();
const fade = new THREE.Mesh(new THREE.CircleGeometry(0.6, 64), new THREE.MeshBasicMaterial({ map: fadeTex, transparent: true, depthWrite: false }));
fade.rotation.x = -Math.PI / 2; fade.position.y = 0.0002; scene.add(fade);

// materials
const skin = new THREE.MeshPhysicalMaterial({ color: SKINS[0].hex, roughness: 0.66, sheen: 0.55, sheenRoughness: 0.5,
  sheenColor: new THREE.Color(0xd8ecff), envMapIntensity: 0.18 });
const chrome = new THREE.MeshPhysicalMaterial({ color: 0xf2f4f6, metalness: 1, roughness: 0.12, envMapIntensity: 1.7 });
const brushed = new THREE.MeshPhysicalMaterial({ color: 0xe6e9ec, metalness: 1, roughness: 0.32, envMapIntensity: 1.8 });
const engrave = new THREE.MeshPhysicalMaterial({ color: 0x8c9198, metalness: 1, roughness: 0.55, envMapIntensity: 0.9 });
const slotM = new THREE.MeshStandardMaterial({ color: 0x050505, roughness: 0.4 });

// load the production model
const loading = document.getElementById('loading'); const bar = document.getElementById('loadbar');
const loader = new GLTFLoader(); loader.setMeshoptDecoder(MeshoptDecoder);
let headrig, cartridge, vessel;
loader.load(canvas.dataset.model || 'assets/model/yojo.glb', (gltf) => {
  vessel = gltf.scene;
  vessel.traverse((o) => {
    if (!o.isMesh) return;
    const n = o.name;
    if (n.startsWith('skin')) o.material = skin;
    else if (n.startsWith('head')) {
      // three primitives in slot order: knurled side, brushed top, engraved Y
      const i = n === 'head' ? 0 : parseInt(n.split('_')[1] || '0', 10);
      o.material = [chrome, brushed, engrave][i] || chrome;
    } else if (n.startsWith('thread') || n.startsWith('sleeve')) o.material = chrome;
    else o.material = slotM;
  });
  headrig = vessel.getObjectByName('headrig'); cartridge = vessel.getObjectByName('cartridge');
  scene.add(vessel);
  loading.classList.add('done');
}, (e) => { if (e.total) bar.style.setProperty('--p', (e.loaded / e.total).toFixed(3)); },
(err) => { loading.querySelector('span').textContent = 'Could not load the model'; console.error(err); });

// twist state
let angle = 0, angleTarget = 0, press = 0, pressT = 0, dragging = false, lastX = 0, moved = 0, sway = 0;
const stateLabel = document.getElementById('stateLabel'); const toggle = document.getElementById('toggle');
const dial = document.getElementById('dialFill'); const hint = document.getElementById('hint');
let lastNotch = 0;
function setTarget(a) {
  angleTarget = Math.min(TURN, Math.max(0, a));
}
canvas.addEventListener('pointerdown', (e) => {
  dragging = true; lastX = e.clientX; moved = 0; canvas.classList.add('drag'); canvas.setPointerCapture(e.pointerId);
});
canvas.addEventListener('pointermove', (e) => {
  if (!dragging) return;
  const dx = e.clientX - lastX; lastX = e.clientX; moved += Math.abs(dx);
  // dragging right turns the head counter-clockwise (opening), like turning it with your thumb
  setTarget(angleTarget + dx * 0.012);
  hint.style.opacity = 0;
});
function release() {
  if (!dragging) return; dragging = false; canvas.classList.remove('drag');
  if (moved < 4 && angle > TURN * 0.98) { pressT = 1; return; }            // tap when open: press
  setTarget(angleTarget > TURN * 0.5 ? TURN : 0);                           // settle open or locked
}
canvas.addEventListener('pointerup', release); canvas.addEventListener('pointercancel', release);
toggle.addEventListener('click', () => setTarget(angleTarget > TURN * 0.5 ? 0 : TURN));

// skins
const chips = document.getElementById('chips'); const skinName = document.getElementById('skinName');
const skinTo = new THREE.Color(SKINS[0].hex);
SKINS.forEach((s, i) => {
  const b = document.createElement('button'); b.className = 'chip'; b.style.background = s.swatch;
  b.setAttribute('aria-label', s.name); b.setAttribute('aria-pressed', i === 0 ? 'true' : 'false');
  b.addEventListener('click', () => {
    skinTo.set(s.hex); skinName.textContent = s.name;
    chips.querySelectorAll('.chip').forEach((c) => c.setAttribute('aria-pressed', c === b ? 'true' : 'false'));
  });
  chips.appendChild(b);
});

// layout
function resize() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  renderer.setSize(w, h, false); camera.aspect = w / h;
  const narrow = w / h < 0.8;
  camera.fov = narrow ? 30 : 20; camera.updateProjectionMatrix();
}
addEventListener('resize', resize); resize();

// loop
const clock = new THREE.Clock();
const camDist = () => (camera.aspect < 0.8 ? 0.5 : 0.56);
function frame() {
  const dt = Math.min(clock.getDelta(), 0.05); const t = clock.elapsedTime;
  angle += (angleTarget - angle) * (1 - Math.exp(-dt * 9));
  // press: quick down, spring back
  if (pressT > 0) { pressT = Math.max(0, pressT - dt * 3.2); }
  press = Math.sin(Math.min(1, (1 - pressT)) * Math.PI) * (pressT > 0 ? 1 : 0);
  const lift = (angle / TURN) * LIFT;
  if (headrig && cartridge) {
    cartridge.position.y = lift; cartridge.rotation.y = angle;
    headrig.position.y = lift - press * PRESS; headrig.rotation.y = angle;
  }
  // a click you can feel at every third of a turn (the thread starts)
  const notch = Math.floor((angle / TURN) * 3 + 0.001);
  if (notch !== lastNotch) { if (navigator.vibrate) navigator.vibrate(6); lastNotch = notch; }
  const open = angle / TURN;
  dial.style.transform = `scaleX(${open.toFixed(3)})`;
  stateLabel.textContent = open > 0.98 ? 'Open' : open < 0.02 ? 'Locked' : 'Turning';
  toggle.setAttribute('aria-pressed', open > 0.5 ? 'true' : 'false');
  skin.color.lerp(skinTo, 1 - Math.exp(-dt * 6));
  // slow living sway of the camera so it reads as an object, not a picture
  sway = Math.sin(t * 0.35) * 0.22;
  const el = 0.2 + Math.sin(t * 0.21) * 0.02;
  const d = camDist();
  camera.position.set(Math.sin(sway) * d * Math.cos(el), target.y + Math.sin(el) * d, Math.cos(sway) * d * Math.cos(el));
  camera.lookAt(target);
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

// waitlist: no backend wired yet
const form = document.getElementById('form'); const msg = document.getElementById('formMsg');
const FORM_ENDPOINT = '';   // set to the waitlist endpoint (Shopify, Klaviyo or Formspree) before launch
form.addEventListener('submit', async (e) => {
  e.preventDefault(); const email = document.getElementById('email').value.trim();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { msg.textContent = 'Check the email address'; return; }
  if (!FORM_ENDPOINT) { msg.textContent = 'Waitlist opens soon'; return; }
  try {
    const r = await fetch(FORM_ENDPOINT, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ email }) });
    msg.textContent = r.ok ? 'You are on the list' : 'Something went wrong. Try again.';
    if (r.ok) form.reset();
  } catch { msg.textContent = 'Something went wrong. Try again.'; }
});

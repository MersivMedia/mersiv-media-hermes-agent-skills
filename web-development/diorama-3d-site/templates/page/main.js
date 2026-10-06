// examples/__SLUG__/main.js — a minimal diorama world on the Dioramas engine (src/core, MIT).
// Boot sequence (from docs/ENGINE.md): loader -> load + normalize -> compile -> start -> intro.
// Scroll drives the camera through one state per section; press-and-hold is the signature interaction;
// the cursor moves the key light. Copy this, then make it YOUR world (see docs/briefs/__SLUG__.md).
import { Engine, THREE, normalize, prepModel, damp, smooth, lerp, studioEnvironment } from '../../src/core/engine.js';
import { Assets, firstMesh } from '../../src/core/assets.js';
import { Pointer } from '../../src/core/input.js';
import { smoothScroll, gsap, reveal } from '../../src/core/scroll.js';
import { preloader, cursor, magnetic, worldNav } from '../../src/core/ui.js';

const Q = new URLSearchParams(location.search);
const MODEL = Q.get('m') || 'models/__SLUG__/hero.glb';           // ?m= lets the smoke test swap in a sample model
const touch = matchMedia('(pointer: coarse)').matches;
// ?lite: QA mode for GPU-less boxes (software WebGL). Same scene, cheaper post. Never ship it as the default.
const LITE = Q.has('lite');

const engine = new Engine({
  canvas: document.getElementById('gl'), fov: 32, near: 0.05, far: 80, dpr: LITE ? 0.75 : 1.75, background: 0x08080a,
  post: {
    ao: LITE ? false : { aoRadius: 0.5, intensity: 2.2, distanceFalloff: 0.8 },
    bloom: { intensity: 0.7, luminanceThreshold: 0.8, radius: 0.6 },
    tone: 'agx', vignette: { offset: 0.25, darkness: 0.75 }, noise: LITE ? false : 0.05, smaa: !LITE,
  },
});
const { scene, camera, renderer } = engine;
scene.environment = studioEnvironment(renderer, { top: 0x15151a, bottom: 0x040405 });
scene.environmentIntensity = 0.9;                      // r186: use scene.environmentIntensity, not material.envMapIntensity
scene.fog = new THREE.FogExp2(0x08080a, 0.06);

// floor: a dark matte disc that catches shadow + AO contact
const floor = new THREE.Mesh(new THREE.CircleGeometry(8, 96), new THREE.MeshStandardMaterial({ color: 0x0d0d10, roughness: 0.9 }));
floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; scene.add(floor);

// key (follows the cursor), rim, fill
const key = new THREE.SpotLight(0xfff1dc, 60, 20, 0.5, 0.6, 1.6);
key.position.set(2.5, 4.5, 3); key.castShadow = true; key.shadow.mapSize.set(LITE ? 512 : 2048, LITE ? 512 : 2048); key.shadow.bias = -0.0002;
scene.add(key, key.target);
const rim = new THREE.DirectionalLight(0xbcd4ff, 2.2); rim.position.set(-4, 3, -4); scene.add(rim);
const fill = new THREE.HemisphereLight(0x1a1c22, 0x050505, 0.6); scene.add(fill);

const assets = new Assets();
const pointer = new Pointer({ lambda: 6 });
const loaderEl = document.getElementById('loader');
const pre = preloader({ assets, el: loaderEl, onValue: v => { loaderEl.firstElementChild.textContent = Math.round(v * 100); } });

const gltf = await assets.gltf(MODEL);
const hero = gltf.scene;
normalize(hero, 1.6, { ground: true });
prepModel(hero, renderer, { cast: true, receive: true });
const pivot = new THREE.Group(); pivot.add(hero); scene.add(pivot);
key.target.position.set(0, 0.6, 0);

// camera states, one per [data-cam] section: position, look-at, object turn, and screen-space shift (`side`) that
// slides the object AWAY from the copy column (left copy -> object right). Verified need: with side 0 the hero
// object sat on top of the headline at 1280x800 (smoke test 2026-10-03).
const CAM = {
  hero:   { pos: [0, 1.2, 4.6],  look: [0, 0.75, 0], turn: 0, side: 0.5 },
  detail: { pos: [1.2, 1.1, 2.9], look: [0.1, 0.8, 0], turn: -0.6, side: -0.5 },
  orbit:  { pos: [-2.8, 1.8, 2.6], look: [0, 0.7, 0], turn: 1.4, side: 0.5 },
  final:  { pos: [0, 2.6, 8.2],  look: [0, 0.6, 0], turn: Math.PI * 2, side: 0, lift: 0.5 },
};
const secs = [...document.querySelectorAll('[data-cam]')];
const tmp = { p: new THREE.Vector3(), l: new THREE.Vector3() };
function camAt(progress) {           // progress 0..1 over the whole page -> blended state between sections
  const f = progress * (secs.length - 1), i = Math.min(secs.length - 2, Math.floor(f)), t = smooth(0, 1, f - i);
  const a = CAM[secs[i].dataset.cam], b = CAM[secs[i + 1].dataset.cam];
  tmp.p.set(lerp(a.pos[0], b.pos[0], t), lerp(a.pos[1], b.pos[1], t), lerp(a.pos[2], b.pos[2], t));
  tmp.l.set(lerp(a.look[0], b.look[0], t), lerp(a.look[1], b.look[1], t), lerp(a.look[2], b.look[2], t));
  return { turn: lerp(a.turn, b.turn, t), side: lerp(a.side ?? 0, b.side ?? 0, t), lift: lerp(a.lift ?? 0, b.lift ?? 0, t) };
}

// signature interaction: press and hold -> the object lifts, spins up and the key light flares
let hold = 0, holding = false;
pointer.on('down', () => { holding = true; });
pointer.on('up', () => { holding = false; });

const lenis = smoothScroll();
let scrollP = 0;
lenis.on('scroll', ({ progress }) => { scrollP = progress || 0; });
const look = new THREE.Vector3(0, 0.75, 0);
let turn = 0, side = 0, lift = 0;
const narrow = () => innerWidth < 720;          // phones: copy sits under the object, so no sideways shift
engine.onTick((dt, t) => {
  pointer.update(dt);
  const s = camAt(scrollP);
  // shift the projection, not the scene: the object moves sideways on screen while lighting/framing stay put
  side = damp(side, narrow() ? 0 : s.side, 4, dt); lift = damp(lift, narrow() ? 0.3 : s.lift, 4, dt);
  // view-offset window moves opposite to the content: -x window => object right; +y window => object HIGHER.
  camera.setViewOffset(innerWidth, innerHeight, -side * innerWidth * 0.5, lift * innerHeight * 0.5, innerWidth, innerHeight);
  camera.position.x = damp(camera.position.x, tmp.p.x + pointer.sx * 0.15, 4, dt);
  camera.position.y = damp(camera.position.y, tmp.p.y + pointer.sy * 0.08, 4, dt);
  camera.position.z = damp(camera.position.z, tmp.p.z, 4, dt);
  look.lerp(tmp.l, 1 - Math.exp(-4 * dt)); camera.lookAt(look);
  hold = damp(hold, holding ? 1 : 0, holding ? 2.2 : 3.5, dt);
  turn = damp(turn, s.turn, 3, dt) + hold * dt * 2.4;
  pivot.rotation.y = turn + Math.sin(t * 0.4) * 0.03;
  pivot.position.y = hold * 0.25 + Math.sin(t * 1.3) * 0.01 * (1 + hold * 4);
  key.position.x = damp(key.position.x, 2.5 + pointer.sx * 2.2, 3, dt);
  key.position.z = damp(key.position.z, 3 - pointer.sy * 1.5, 3, dt);
  key.intensity = 60 + hold * 90;
  engine.post.bloom.intensity = 0.7 + hold * 0.8;
});

engine.onResize(() => {});
renderer.compile(scene, camera);       // avoid first-frame shader hitches
camAt(0); camera.position.copy(tmp.p); camera.lookAt(tmp.l);
engine.start();
await pre.finish();
cursor({ color: '#f1eee9' });
magnetic('[data-magnetic]');
// worldNav() is the Dioramas gallery's prev/next switcher; it only makes sense INSIDE the gallery (slug must be in
// src/core/worlds.js). A standalone client site skips it. Set ?gallery or add the slug to worlds.js to show it.
if (Q.has('gallery')) worldNav('__SLUG__', { theme: 'dark', corner: 'bl' });
reveal('.h1, .h2', { type: 'lines' });
gsap.from(pivot.scale, { x: 0.85, y: 0.85, z: 0.85, duration: 1.6, ease: 'expo.out' });
if (touch) document.querySelector('.hint').textContent = 'Touch and hold anywhere';
window.__ready = true;                 // QA hook

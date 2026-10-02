import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const canvas = document.getElementById("stage");
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
renderer.setClearColor(0x0a0a0b, 1);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0a0b);
const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 40);
camera.position.set(0, 0.15, 7.4);

const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.add(new THREE.AmbientLight(0xfff6ea, 0.55));
const key = new THREE.DirectionalLight(0xfff3d2, 2.4);
key.position.set(2.2, 4.2, 3.2);
scene.add(key);
const blush = new THREE.DirectionalLight(0xd8c4f2, 0.85);
blush.position.set(-3.2, 0.4, 2);
scene.add(blush);

const butter = new THREE.MeshPhysicalMaterial({
  color: 0xf3e27a,
  roughness: 0.32,
  metalness: 0.02,
  clearcoat: 0.45,
  clearcoatRoughness: 0.25,
});
const lilac = new THREE.MeshPhysicalMaterial({
  color: 0xc9b6e6,
  roughness: 0.28,
  metalness: 0.04,
  clearcoat: 0.3,
});

function makeTube() {
  const group = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.22, 1.45, 28), butter);
  const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.24, 0.32, 28), lilac);
  cap.position.y = 0.86;
  const crimp = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.06, 0.12), butter);
  crimp.position.y = -0.74;
  group.add(body, cap, crimp);
  return group;
}

const cluster = new THREE.Group();
scene.add(cluster);
const tubes = [];
for (let i = 0; i < 5; i += 1) {
  const tube = makeTube();
  const angle = (i / 5) * Math.PI * 2;
  tube.userData.angle = angle;
  tube.userData.radius = 1.15 + (i % 2) * 0.18;
  tube.rotation.z = -0.65 + i * 0.26;
  tube.rotation.x = 0.12 * (i - 2);
  cluster.add(tube);
  tubes.push(tube);
}

const dollop = new THREE.Mesh(
  new THREE.SphereGeometry(0.16, 24, 24),
  new THREE.MeshPhysicalMaterial({ color: 0xf7e7ea, roughness: 0.2, clearcoat: 0.6 })
);
dollop.scale.set(1.4, 0.55, 1);
dollop.position.set(0.2, -1.35, 0.6);
scene.add(dollop);

let dragging = false;
let lastX = 0;
let spin = 0.2;

function resize() {
  const frame = canvas.parentElement;
  const width = frame.clientWidth || window.innerWidth;
  const height = frame.clientHeight || window.innerHeight;
  camera.aspect = width / Math.max(height, 1);
  camera.updateProjectionMatrix();
  renderer.setSize(width, height, false);
  canvas.style.width = "100%";
  canvas.style.height = "100%";
}

canvas.addEventListener("pointerdown", (event) => {
  dragging = true;
  lastX = event.clientX;
  canvas.setPointerCapture(event.pointerId);
});
canvas.addEventListener("pointerup", () => { dragging = false; });
canvas.addEventListener("pointercancel", () => { dragging = false; });
canvas.addEventListener("pointermove", (event) => {
  if (!dragging) return;
  spin += (event.clientX - lastX) * 0.005;
  lastX = event.clientX;
});

function frame(time) {
  const progress = window.COSMIX_SCROLL?.hero ?? 0;
  if (!dragging) spin = reduced ? 0.4 : 0.2 + progress * Math.PI * 2.4;
  cluster.rotation.y = spin;
  const wide = window.innerWidth > 860;
  cluster.position.x = wide ? 0.85 : 0;
  cluster.position.y = wide ? 0.15 : 0.35;
  cluster.scale.setScalar(wide ? 1.2 : 0.72);
  camera.position.z = 7.5 - progress * 1.5;
  tubes.forEach((tube, index) => {
    const bob = reduced ? 0 : Math.sin(time * 0.001 + index) * 0.06;
    const angle = tube.userData.angle + progress * 0.35;
    tube.position.set(
      Math.cos(angle) * tube.userData.radius,
      Math.sin(angle) * 0.62 + bob,
      Math.sin(angle) * 0.4
    );
  });
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

window.addEventListener("resize", resize);
resize();
requestAnimationFrame(frame);

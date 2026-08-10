import * as THREE from "https://unpkg.com/three@0.166.1/build/three.module.js";

const canvas = document.querySelector("#game-canvas");
const stage = document.querySelector(".game-stage");
const message = document.querySelector("#message");
const playButton = document.querySelector("#play");
const restartButton = document.querySelector("#restart");
const coinCount = document.querySelector("#coin-count");
const lifeCount = document.querySelector("#life-count");

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
scene.fog = new THREE.Fog(0x8cd8fa, 20, 62);

const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 100);
camera.position.set(7, 6.4, 12);

const ambient = new THREE.HemisphereLight(0xdff7ff, 0x38512f, 2.3);
scene.add(ambient);
const sun = new THREE.DirectionalLight(0xfff0bb, 2.4);
sun.position.set(8, 13, 8);
sun.castShadow = true;
sun.shadow.mapSize.set(1024, 1024);
scene.add(sun);

const world = new THREE.Group();
scene.add(world);

const materials = {
  grass: new THREE.MeshStandardMaterial({ color: 0x35b96f, roughness: 0.82 }),
  dirt: new THREE.MeshStandardMaterial({ color: 0xa65b36, roughness: 0.92 }),
  brick: new THREE.MeshStandardMaterial({ color: 0xdd5e47, roughness: 0.74 }),
  brickDark: new THREE.MeshStandardMaterial({ color: 0xa84035, roughness: 0.75 }),
  gold: new THREE.MeshStandardMaterial({ color: 0xffd34e, emissive: 0x6e4300, emissiveIntensity: 0.38, metalness: 0.22, roughness: 0.38 }),
  enemy: new THREE.MeshStandardMaterial({ color: 0x7b3f31, roughness: 0.85 }),
  enemyFace: new THREE.MeshStandardMaterial({ color: 0xffd7c2, roughness: 0.8 }),
  flag: new THREE.MeshStandardMaterial({ color: 0xff5b4f, roughness: 0.6 }),
  pole: new THREE.MeshStandardMaterial({ color: 0xe7edf5, metalness: 0.55, roughness: 0.3 }),
};

const platforms = [];
const coins = [];
const enemies = [];
let goal;
let running = false;
let finished = false;
let collected = 0;
let lives = 3;
let lastTime = performance.now();
let playerVelocity = new THREE.Vector3();
const input = { left: false, right: false, jump: false, jumpPressed: false };

function meshBox(width, height, depth, material, position) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material);
  mesh.position.copy(position);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  world.add(mesh);
  return mesh;
}

function addPlatform(x, y, width, height = 1, depth = 3) {
  const dirt = meshBox(width, height, depth, materials.dirt, new THREE.Vector3(x, y - height / 2, 0));
  const grass = meshBox(width + 0.08, 0.18, depth + 0.08, materials.grass, new THREE.Vector3(x, y + 0.08, 0));
  platforms.push({ x: x - width / 2, right: x + width / 2, y, height, depth, visual: [dirt, grass] });
}

function addBrick(x, y) {
  const brick = meshBox(1, 0.8, 1.2, materials.brick, new THREE.Vector3(x, y, 0));
  const inset = meshBox(0.78, 0.06, 1.23, materials.brickDark, new THREE.Vector3(x, y - 0.08, -0.61));
  platforms.push({ x: x - 0.5, right: x + 0.5, y: y + 0.4, height: 0.8, depth: 1.2, visual: [brick, inset] });
}

function addCoin(x, y) {
  const coin = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.25, 0.1, 24), materials.gold);
  coin.rotation.x = Math.PI / 2;
  coin.position.set(x, y, 0);
  coin.castShadow = true;
  world.add(coin);
  coins.push({ mesh: coin, baseY: y, collected: false });
}

function addEnemy(x, y, left, right) {
  const group = new THREE.Group();
  const body = new THREE.Mesh(new THREE.SphereGeometry(0.42, 18, 12), materials.enemy);
  body.scale.set(1.05, 0.75, 0.85);
  body.castShadow = true;
  const face = new THREE.Mesh(new THREE.SphereGeometry(0.25, 14, 10), materials.enemyFace);
  face.scale.set(1.2, 0.66, 0.2);
  face.position.set(0, 0.02, 0.34);
  const leftEye = new THREE.Mesh(new THREE.SphereGeometry(0.035, 8, 8), new THREE.MeshBasicMaterial({ color: 0x1d2d50 }));
  const rightEye = leftEye.clone();
  leftEye.position.set(-0.09, 0.08, 0.39);
  rightEye.position.set(0.09, 0.08, 0.39);
  group.add(body, face, leftEye, rightEye);
  group.position.set(x, y + 0.4, 0);
  world.add(group);
  enemies.push({ group, left, right, direction: 1, alive: true });
}

function addGoal(x, y) {
  const group = new THREE.Group();
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 4.2, 10), materials.pole);
  pole.position.y = 2.1;
  pole.castShadow = true;
  const ball = new THREE.Mesh(new THREE.SphereGeometry(0.18, 12, 10), materials.gold);
  ball.position.y = 4.24;
  const flag = new THREE.Mesh(new THREE.PlaneGeometry(1.3, 0.85), materials.flag);
  flag.position.set(0.68, 3.55, 0.02);
  group.add(pole, ball, flag);
  group.position.set(x, y, 0);
  world.add(group);
  goal = { group, x, y };
}

function addCloud(x, y, scale) {
  const cloud = new THREE.Group();
  const cloudMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.82 });
  [-0.58, -0.12, 0.36].forEach((offset, index) => {
    const puff = new THREE.Mesh(new THREE.SphereGeometry(0.42 + index * 0.1, 12, 10), cloudMaterial);
    puff.position.set(offset, index === 1 ? 0.15 : 0, -2.8);
    cloud.add(puff);
  });
  cloud.position.set(x, y, 0);
  cloud.scale.setScalar(scale);
  scene.add(cloud);
}

function addPlayer() {
  const group = new THREE.Group();
  const shirt = new THREE.MeshStandardMaterial({ color: 0xe94f44, roughness: 0.7 });
  const overalls = new THREE.MeshStandardMaterial({ color: 0x285fc8, roughness: 0.72 });
  const skin = new THREE.MeshStandardMaterial({ color: 0xffc99c, roughness: 0.7 });
  const cap = new THREE.MeshStandardMaterial({ color: 0xff5c4c, roughness: 0.68 });
  const body = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.78, 0.5), overalls);
  body.position.y = 0.72;
  const torso = new THREE.Mesh(new THREE.BoxGeometry(0.72, 0.38, 0.52), shirt);
  torso.position.y = 1.06;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.36, 18, 14), skin);
  head.position.y = 1.45;
  const hat = new THREE.Mesh(new THREE.SphereGeometry(0.39, 18, 14, 0, Math.PI * 2, 0, Math.PI / 2), cap);
  hat.position.y = 1.6;
  const brim = new THREE.Mesh(new THREE.BoxGeometry(0.36, 0.09, 0.24), cap);
  brim.position.set(0.18, 1.55, 0.12);
  const foot = new THREE.MeshStandardMaterial({ color: 0x4b2d25, roughness: 0.9 });
  [-0.22, 0.22].forEach((offset) => {
    const shoe = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.18, 0.48), foot);
    shoe.position.set(offset, 0.12, 0.06);
    group.add(shoe);
  });
  group.add(body, torso, head, hat, brim);
  group.position.set(-7.5, 1, 0);
  group.traverse((item) => { if (item.isMesh) item.castShadow = true; });
  world.add(group);
  return group;
}

const player = addPlayer();

function buildLevel() {
  addPlatform(-3, 0, 13, 1.2);
  addPlatform(8, 0, 8, 1.2);
  addPlatform(17, 0, 9, 1.2);
  addPlatform(29, 0, 12, 1.2);
  addPlatform(41, 0, 7, 1.2);
  addPlatform(50, 0, 12, 1.2);
  addPlatform(11, 2.6, 3.2, 0.65, 2.2);
  addPlatform(23, 3.8, 3.2, 0.65, 2.2);
  addPlatform(34, 2.6, 3, 0.65, 2.2);
  addBrick(2.2, 3.1);
  addBrick(3.35, 3.1);
  addBrick(4.5, 3.1);
  [-5.5, -3.9, -2.3, 1.2, 2.2, 3.35, 4.5, 10.2, 11.4, 12.6, 21.8, 23, 24.2, 33.2, 34.4, 35.6, 43, 45, 49.2].forEach((x, index) => addCoin(x, index % 3 === 0 ? 2.3 : 1.9));
  addCoin(11, 4.2);
  addCoin(23, 5.35);
  addCoin(34, 4.2);
  addEnemy(5.6, 0.6, 4.8, 7.1);
  addEnemy(18.7, 0.6, 16, 20.4);
  addEnemy(38, 0.6, 35.8, 40);
  addGoal(55, 0.6);
  addCloud(-3, 7, 1.2);
  addCloud(15, 8, 0.85);
  addCloud(35, 7.5, 1.15);
}

buildLevel();

function resize() {
  const { width, height } = stage.getBoundingClientRect();
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function resetLevel() {
  player.position.set(-7.5, 1.05, 0);
  playerVelocity.set(0, 0, 0);
  collected = 0;
  lives = 3;
  finished = false;
  coins.forEach((coin) => { coin.collected = false; coin.mesh.visible = true; });
  enemies.forEach((enemy) => { enemy.alive = true; enemy.group.visible = true; enemy.group.scale.setScalar(1); });
  coinCount.textContent = "0";
  lifeCount.textContent = "3";
}

function showMessage(title, description, buttonLabel = "Play again") {
  message.innerHTML = `<span class="message-kicker">Brick Leap</span><strong>${title}</strong><small>${description}</small><button id="play" type="button">${buttonLabel}</button>`;
  message.classList.add("is-visible");
  document.querySelector("#play").addEventListener("click", () => { resetLevel(); running = true; message.classList.remove("is-visible"); });
}

function setDirection(action, active) { input[action] = active; }
function requestJump() { input.jumpPressed = true; }

window.addEventListener("keydown", (event) => {
  if (["ArrowLeft", "ArrowRight", "ArrowUp", " ", "a", "d", "A", "D", "w", "W"].includes(event.key)) event.preventDefault();
  if (event.key === "ArrowLeft" || event.key === "a" || event.key === "A") setDirection("left", true);
  if (event.key === "ArrowRight" || event.key === "d" || event.key === "D") setDirection("right", true);
  if (event.key === "ArrowUp" || event.key === "w" || event.key === "W" || event.key === " ") requestJump();
});
window.addEventListener("keyup", (event) => {
  if (event.key === "ArrowLeft" || event.key === "a" || event.key === "A") setDirection("left", false);
  if (event.key === "ArrowRight" || event.key === "d" || event.key === "D") setDirection("right", false);
});

function bindTouch(buttonId, action, isJump = false) {
  const button = document.querySelector(buttonId);
  const onStart = (event) => { event.preventDefault(); isJump ? requestJump() : setDirection(action, true); };
  const onEnd = (event) => { event.preventDefault(); if (!isJump) setDirection(action, false); };
  button.addEventListener("pointerdown", onStart);
  button.addEventListener("pointerup", onEnd);
  button.addEventListener("pointerleave", onEnd);
  button.addEventListener("pointercancel", onEnd);
}

bindTouch("#move-left", "left");
bindTouch("#move-right", "right");
bindTouch("#jump", "jump", true);
playButton.addEventListener("click", () => { resetLevel(); running = true; message.classList.remove("is-visible"); });
restartButton.addEventListener("click", () => { resetLevel(); running = true; message.classList.remove("is-visible"); });

function playerOnPlatform(nextY) {
  const feet = nextY;
  return platforms.find((platform) => player.position.x + 0.27 > platform.x && player.position.x - 0.27 < platform.right && feet >= platform.y - 0.18 && feet <= platform.y + 0.22);
}

function respawn() {
  lives -= 1;
  lifeCount.textContent = String(lives);
  if (lives <= 0) {
    running = false;
    showMessage("Out of lives!", `You collected ${collected} coin${collected === 1 ? "" : "s"}. Try a cleaner run.");
    return;
  }
  player.position.set(Math.max(-7.5, player.position.x - 3), 2.8, 0);
  playerVelocity.set(0, 0, 0);
}

function updatePlayer(delta) {
  const speed = 7.3;
  const move = (input.right ? 1 : 0) - (input.left ? 1 : 0);
  playerVelocity.x = THREE.MathUtils.damp(playerVelocity.x, move * speed, 14, delta);
  if (move !== 0) player.rotation.y = move > 0 ? 0 : Math.PI;

  const grounded = playerOnPlatform(player.position.y - 0.98);
  if (input.jumpPressed && grounded) playerVelocity.y = 8.3;
  input.jumpPressed = false;
  playerVelocity.y -= 22 * delta;

  player.position.x = THREE.MathUtils.clamp(player.position.x + playerVelocity.x * delta, -8.8, 55.8);
  const nextFeet = player.position.y - 0.98 + playerVelocity.y * delta;
  const landing = playerOnPlatform(nextFeet);
  if (playerVelocity.y <= 0 && landing) {
    player.position.y = landing.y + 0.98;
    playerVelocity.y = 0;
  } else {
    player.position.y += playerVelocity.y * delta;
  }

  player.rotation.z = THREE.MathUtils.damp(player.rotation.z, -playerVelocity.x * 0.035, 10, delta);
  if (player.position.y < -4) respawn();
}

function updateCoins(time) {
  coins.forEach((coin, index) => {
    if (coin.collected) return;
    coin.mesh.rotation.y += 0.07;
    coin.mesh.position.y = coin.baseY + Math.sin(time * 0.003 + index) * 0.16;
    if (coin.mesh.position.distanceTo(player.position.clone().add(new THREE.Vector3(0, 0.45, 0))) < 0.62) {
      coin.collected = true;
      coin.mesh.visible = false;
      collected += 1;
      coinCount.textContent = String(collected);
    }
  });
}

function updateEnemies(delta) {
  enemies.forEach((enemy) => {
    if (!enemy.alive) return;
    enemy.group.position.x += enemy.direction * 1.3 * delta;
    if (enemy.group.position.x < enemy.left || enemy.group.position.x > enemy.right) enemy.direction *= -1;
    enemy.group.rotation.y = enemy.direction > 0 ? 0 : Math.PI;
    const distanceX = Math.abs(player.position.x - enemy.group.position.x);
    const distanceY = player.position.y - enemy.group.position.y;
    if (distanceX < 0.56 && Math.abs(distanceY) < 0.72) {
      if (playerVelocity.y < -1 && distanceY > 0.2) {
        enemy.alive = false;
        enemy.group.scale.y = 0.25;
        playerVelocity.y = 5.2;
      } else {
        respawn();
      }
    }
  });
}

function updateGoal() {
  if (!goal || finished) return;
  if (Math.abs(player.position.x - goal.x) < 0.72) {
    finished = true;
    running = false;
    showMessage("Level complete!", `You grabbed ${collected}/${coins.length} coins and made it to the flag.`, "Play again");
  }
}

function updateCamera(delta) {
  const targetX = THREE.MathUtils.clamp(player.position.x + 4.5, 4, 47);
  camera.position.x = THREE.MathUtils.damp(camera.position.x, targetX, 3.6, delta);
  camera.position.y = THREE.MathUtils.damp(camera.position.y, 6.4, 3.6, delta);
  camera.lookAt(camera.position.x - 2.6, 2.1, 0);
}

function animate(time) {
  const delta = Math.min((time - lastTime) / 1000, 0.05);
  lastTime = time;
  if (running) {
    updatePlayer(delta);
    updateCoins(time);
    updateEnemies(delta);
    updateGoal();
  }
  updateCamera(delta);
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}

window.addEventListener("resize", resize);
resize();
requestAnimationFrame(animate);

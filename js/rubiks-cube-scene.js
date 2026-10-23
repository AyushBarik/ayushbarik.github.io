// A Rubik's Cube you can spin and solve, modeled on the spinning teapot at davidheineman.com.
// It turns slowly on its own and stops while hovered. Swipe across it to push it spinning (left
// and right, or up and down to tumble it), click it for a big spin, drag a sticker to turn that
// layer, drag the space around it to look around, or type U D L R F B (Shift for counter-clockwise).
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

// Spin feel copied from the teapot.
const AUTO_ROTATE_SPEED = 0.5;    // rad/s while idle
const PUSH_SENSITIVITY = 0.3;     // rad/s of spin added per pixel of swipe
const SPIN_FRICTION = 2;          // how fast pushed spin decays (per second)
const CLICK_PUSH_IMPULSE = 14;    // rad/s added by a click
// Only swipes faster than this push the cube, so moving the mouse onto a sticker doesn't fling it.
const SWIPE_SPEED = 600;          // px/s

const TURN_TIME = 0.15;           // seconds per quarter turn (keyboard)
const SCRAMBLE_TURN_TIME = 0.08;
const SCRAMBLE_MOVES = 25;
const QUARTER = Math.PI / 2;
// Render at twice the screen's pixel density and let the browser scale it down, which smooths
// edges and highlights beyond what the GPU's antialiasing does. The canvas is small, so it's cheap.
const SUPERSAMPLE = 2;

// Sticker color for each outward direction of the solved cube: white up, green front, red right.
const FACES = [
  { dir: [1, 0, 0], color: 0xb71234 },   // red
  { dir: [-1, 0, 0], color: 0xff5800 },  // orange
  { dir: [0, 1, 0], color: 0xffffff },   // white
  { dir: [0, -1, 0], color: 0xffd500 },  // yellow
  { dir: [0, 0, 1], color: 0x009b48 },   // green
  { dir: [0, 0, -1], color: 0x0046ad },  // blue
];

export function mount(widget) {
  const canvas = widget.querySelector('canvas');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;   // soft studio reflections

  const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 100);
  camera.position.set(0, 5.4, 11.5);
  camera.lookAt(0, -0.45, 0);

  const keyLight = new THREE.DirectionalLight(0xffffff, 1.6);
  keyLight.position.set(4, 10, 5);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(2048, 2048);
  Object.assign(keyLight.shadow.camera, { left: -4, right: 4, top: 4, bottom: -4, near: 1, far: 25 });
  keyLight.shadow.normalBias = 0.03;
  const fillLight = new THREE.DirectionalLight(0xffffff, 0.9);   // lifts the faces turned away from the key light
  fillLight.position.set(-6, 3, 6);
  scene.add(keyLight, fillLight);

  const ground = new THREE.Mesh(new THREE.PlaneGeometry(30, 30), new THREE.ShadowMaterial({ opacity: 0.12 }));
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -2.75;       // just below the cube even when it's balanced on a corner
  ground.receiveShadow = true;
  scene.add(ground);

  // --- The cube: 26 cubies, each a rounded black block with a sticker on every outward face.
  const cube = new THREE.Group();   // the whole puzzle; spins and tumbles
  const pivot = new THREE.Group();  // temporarily holds the layer that is turning
  cube.add(pivot);
  cube.rotation.y = -0.6;
  scene.add(cube);

  const bodyGeo = new RoundedBoxGeometry(0.96, 0.96, 0.96, 8, 0.1);
  const bodyMat = new THREE.MeshPhysicalMaterial({ color: 0x0b0b0d, roughness: 0.4, clearcoat: 0.6, clearcoatRoughness: 0.3 });
  const stickerGeo = new THREE.ExtrudeGeometry(roundedSquare(0.8, 0.12), {
    depth: 0.01, bevelEnabled: true, bevelThickness: 0.006, bevelSize: 0.006, bevelSegments: 4, curveSegments: 16,
  });
  const faces = FACES.map(({ dir, color }) => ({
    dir: new THREE.Vector3(...dir),
    // Dim reflections so the studio lights don't wash the colors out to pastel.
    material: new THREE.MeshPhysicalMaterial({
      color, roughness: 0.32, clearcoat: 0.5, clearcoatRoughness: 0.15, envMapIntensity: 0.35,
    }),
  }));

  const cubies = [];
  const zAxis = new THREE.Vector3(0, 0, 1);
  for (let x = -1; x <= 1; x++) {
    for (let y = -1; y <= 1; y++) {
      for (let z = -1; z <= 1; z++) {
        if (!x && !y && !z) continue;
        const cubie = new THREE.Group();
        cubie.position.set(x, y, z);
        cubie.userData.home = cubie.position.clone();
        const body = new THREE.Mesh(bodyGeo, bodyMat);
        body.castShadow = true;
        body.userData.cubie = cubie;
        cubie.add(body);
        for (const face of faces) {
          if (face.dir.dot(cubie.position) < 1) continue;   // only outward faces get stickers
          const sticker = new THREE.Mesh(stickerGeo, face.material);
          sticker.quaternion.setFromUnitVectors(zAxis, face.dir);
          sticker.position.copy(face.dir).multiplyScalar(0.474);
          sticker.userData = { cubie, normal: face.dir, face };
          cubie.add(sticker);
        }
        cube.add(cubie);
        cubies.push(cubie);
      }
    }
  }

  // --- Layer turns. `axis` is a unit vector along x, y or z in the cube's own frame (it may point
  // either way); `layer` is -1, 0 or 1 along that axis.
  const queue = [];      // turns waiting to animate: { axis, layer, angle, duration, byHand, scramble }
  let turn = null;       // the turn being animated: { from, to, t, duration, byHand, scramble }

  function grabLayer(axis, layer) {
    const i = axisIndex(axis);
    for (const c of cubies) {
      if (Math.round(c.position.getComponent(i)) === layer) pivot.attach(c);
    }
    pivot.userData.axis = axis;
  }

  function setLayerAngle(angle) {
    pivot.quaternion.setFromAxisAngle(pivot.userData.axis, angle);
  }

  function releaseLayer() {
    for (const c of [...pivot.children]) {
      cube.attach(c);
      c.position.round();
      snapRotation(c.quaternion);
    }
    pivot.quaternion.identity();
  }

  function animateTurn(from, to, duration, byHand, scramble = false) {
    turn = { from, to, t: 0, duration, byHand, scramble };
  }

  function stepTurns(dt) {
    if (!turn && queue.length && !drag?.turning) {
      const next = queue.shift();
      grabLayer(next.axis, next.layer);
      animateTurn(0, next.angle, next.duration, next.byHand, next.scramble);
    }
    if (!turn) return;
    turn.t = Math.min(1, turn.t + dt / turn.duration);
    const eased = 1 - (1 - turn.t) ** 3;
    setLayerAngle(turn.from + (turn.to - turn.from) * eased);
    if (turn.t < 1) return;
    const done = turn;
    turn = null;
    releaseLayer();
    if (done.byHand && solving && isSolved()) {
      solving = false;
      yawVelocity += CLICK_PUSH_IMPULSE * 1.5;   // victory spin
    }
    if (done.scramble && !queue.some((m) => m.scramble)) solving = true;
  }

  let solving = false;   // scrambled and not yet solved

  function isSolved() {
    const colorFacing = {};
    const n = new THREE.Vector3();
    for (const c of cubies) {
      for (const s of c.children) {
        if (!s.userData.face) continue;
        const key = axisKey(n.copy(s.userData.normal).applyQuaternion(c.quaternion));
        colorFacing[key] ??= s.userData.face;
        if (colorFacing[key] !== s.userData.face) return false;
      }
    }
    return true;
  }

  function scramble() {
    let lastAxis = -1;
    for (let i = 0; i < SCRAMBLE_MOVES; i++) {
      let a;
      do a = Math.floor(Math.random() * 3); while (a === lastAxis);
      lastAxis = a;
      const axis = new THREE.Vector3().setComponent(a, 1);
      const layer = [-1, 1][Math.floor(Math.random() * 2)];
      const angle = [-1, 1, 2][Math.floor(Math.random() * 3)] * QUARTER;
      queue.push({ axis, layer, angle, duration: SCRAMBLE_TURN_TIME * (Math.abs(angle) > QUARTER ? 1.5 : 1), byHand: false, scramble: true });
    }
  }

  // --- Pointer input.
  const raycaster = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let hovering = false;
  let drag = null;          // the press in progress
  let lastMove = null;      // previous pointer sample for swipe speed: { x, y, time }
  let yawVelocity = 0;      // extra spin from pushes, rad/s (around the vertical)
  let pitchVelocity = 0;    // tumble from up/down pushes, rad/s (around the horizontal)
  let autoSpeed = reduceMotion ? 0 : AUTO_ROTATE_SPEED;
  let touchResume = 0;

  function pick(e) {
    const rect = canvas.getBoundingClientRect();
    ndc.set(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
    const hit = raycaster.intersectObjects(cubies, true)[0];
    if (!hit) return null;
    const cubie = hit.object.userData.cubie;
    // The face that was hit, as an outward direction in the cube's frame.
    const normal = hit.face.normal.clone().transformDirection(hit.object.matrixWorld)
      .applyQuaternion(cube.quaternion.clone().invert());
    const axis = snapAxis(normal);
    if (cubie.parent !== cube || Math.round(axis.dot(cubie.position)) !== 1) return { point: hit.point };
    return { cubie, normal: axis, point: hit.point };
  }

  canvas.addEventListener('pointerenter', (e) => { if (e.pointerType === 'mouse') hovering = true; });
  canvas.addEventListener('pointerleave', (e) => {
    if (e.pointerType === 'mouse') hovering = false;
    lastMove = null;
  });

  canvas.addEventListener('pointerdown', (e) => {
    if (e.button !== 0 || drag) return;
    canvas.setPointerCapture(e.pointerId);
    const hit = pick(e);
    if (e.pointerType !== 'mouse') {
      hovering = true;
      clearTimeout(touchResume);
    }
    // Grabbing the cube catches it.
    if (hit) yawVelocity = pitchVelocity = 0;
    drag = { id: e.pointerId, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, time: e.timeStamp,
      hit, moved: false, turning: false, canTurn: !!hit?.cubie && !turn && !queue.length };
  });

  canvas.addEventListener('pointermove', (e) => {
    if (drag && e.pointerId === drag.id) {
      const dx = e.clientX - drag.x0;
      const dy = e.clientY - drag.y0;
      if (!drag.moved && Math.hypot(dx, dy) > 6) {
        drag.moved = true;
        if (drag.canTurn) startLayerDrag(dx, dy);
      }
      if (drag.turning) {
        setLayerAngle(layerDragAngle(dx, dy));
      } else if (drag.moved) {
        // Dragging the space around the cube (or a cube that's mid-turn) rolls the whole cube.
        const dt = Math.max(1, e.timeStamp - drag.time) / 1000;
        rotateCube((e.clientX - drag.x) * 0.012, (e.clientY - drag.y) * 0.012);
        drag.vx = (e.clientX - drag.x) * 0.012 / dt;
        drag.vy = (e.clientY - drag.y) * 0.012 / dt;
      }
      drag.x = e.clientX;
      drag.y = e.clientY;
      drag.time = e.timeStamp;
      return;
    }
    // Swiping across the cube pushes it, like the teapot.
    if (lastMove && e.pointerType === 'mouse') {
      const dx = e.clientX - lastMove.x;
      const dy = e.clientY - lastMove.y;
      const speed = Math.hypot(dx, dy) / (Math.max(1, e.timeStamp - lastMove.time) / 1000);
      if (speed > SWIPE_SPEED && pick(e)) {
        yawVelocity += dx * PUSH_SENSITIVITY;
        pitchVelocity += dy * PUSH_SENSITIVITY;
      }
    }
    lastMove = { x: e.clientX, y: e.clientY, time: e.timeStamp };
  });

  function endPress(e) {
    if (!drag || e.pointerId !== drag.id) return;
    if (drag.turning) {
      // Snap to the nearest quarter turn, leaning toward the direction it was dragged.
      const angle = layerDragAngle(e.clientX - drag.x0, e.clientY - drag.y0);
      let quarters = Math.round(angle / QUARTER);
      if (quarters === 0 && Math.abs(angle) > 0.35) quarters = Math.sign(angle);
      animateTurn(angle, quarters * QUARTER, 0.12, quarters % 4 !== 0);
    } else if (drag.moved) {
      yawVelocity = drag.vx || 0;      // let go mid-roll and it keeps rolling
      pitchVelocity = drag.vy || 0;
    } else if (drag.hit && e.type === 'pointerup') {
      yawVelocity += CLICK_PUSH_IMPULSE;   // a click spins it, like the teapot
    }
    drag = null;
    if (e.pointerType !== 'mouse') {
      clearTimeout(touchResume);
      touchResume = setTimeout(() => { hovering = false; }, 4000);
    }
  }
  canvas.addEventListener('pointerup', endPress);
  canvas.addEventListener('pointercancel', endPress);

  // Dragging a sticker: the drag picks one of the two directions along that face, and the layer
  // that moves the sticker that way follows the pointer until it's let go.
  function startLayerDrag(dx, dy) {
    const { cubie, normal, point } = drag.hit;
    const along = new THREE.Vector2(dx, dy).normalize();
    let best = null;
    for (let i = 0; i < 3; i++) {
      if (normal.getComponent(i) !== 0) continue;
      const t = new THREE.Vector3().setComponent(i, 1);
      const screen = screenDelta(point, t.clone().applyQuaternion(cube.quaternion).multiplyScalar(0.5));
      const fit = Math.abs(along.dot(screen.clone().normalize()));
      if (!best || fit > best.fit) best = { t, screen, fit };
    }
    // Turning about n × t by a positive angle carries the sticker toward +t.
    const axis = new THREE.Vector3().crossVectors(normal, best.t);
    grabLayer(axis, Math.round(cubie.position.getComponent(axisIndex(axis))));
    drag.screenDir = best.screen.clone().normalize();
    drag.pxPerRadian = (best.screen.length() / 0.5) * 1.5;   // stickers sit ~1.5 from the turning axis
    drag.turning = true;
  }

  function layerDragAngle(dx, dy) {
    return (dx * drag.screenDir.x + dy * drag.screenDir.y) / drag.pxPerRadian;
  }

  // Pixel offset on the canvas for moving `delta` (world units) away from world point `point`.
  function screenDelta(point, delta) {
    const rect = canvas.getBoundingClientRect();
    const a = point.clone().project(camera);
    const b = point.clone().add(delta).project(camera);
    return new THREE.Vector2((b.x - a.x) * rect.width / 2, -(b.y - a.y) * rect.height / 2);
  }

  const worldUp = new THREE.Vector3(0, 1, 0);
  const worldRight = new THREE.Vector3(1, 0, 0);
  const spinStep = new THREE.Quaternion();
  function rotateCube(yaw, pitch) {
    cube.quaternion.premultiply(spinStep.setFromAxisAngle(worldUp, yaw));
    cube.quaternion.premultiply(spinStep.setFromAxisAngle(worldRight, pitch));
  }

  // --- Keyboard: faces are named by where they are on screen right now.
  const FACE_KEYS = { KeyU: [0, 1, 0], KeyD: [0, -1, 0], KeyR: [1, 0, 0], KeyL: [-1, 0, 0], KeyF: [0, 0, 1], KeyB: [0, 0, -1] };
  canvas.tabIndex = 0;
  function onKey(e) {
    const view = FACE_KEYS[e.code];
    if (!view || e.metaKey || e.ctrlKey || e.altKey) return;
    if (!hovering && document.activeElement !== canvas) return;
    if (e.target.closest?.('input, textarea, [contenteditable]')) return;
    e.preventDefault();
    // Screen directions (camera right / up / toward the viewer) as an outward face of the cube.
    camera.updateMatrixWorld();
    const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
    const up = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
    const toward = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 2);
    const world = right.multiplyScalar(view[0]).add(up.multiplyScalar(view[1])).add(toward.multiplyScalar(view[2]));
    const normal = snapAxis(world.applyQuaternion(cube.quaternion.clone().invert()));
    // Clockwise as seen from outside that face is a negative turn about its outward normal.
    queue.push({ axis: normal, layer: axisSign(normal), angle: (e.shiftKey ? 1 : -1) * QUARTER, duration: TURN_TIME, byHand: true });
  }
  window.addEventListener('keydown', onKey);

  // --- Render loop, paused while the cube is off screen.
  function resize() {
    const { clientWidth: w, clientHeight: h } = canvas;
    if (!w || !h) return;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 3) * SUPERSAMPLE);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(canvas);
  resize();

  let last = performance.now();
  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    const targetSpeed = hovering || reduceMotion ? 0 : AUTO_ROTATE_SPEED;
    autoSpeed += (targetSpeed - autoSpeed) * (1 - Math.exp(-dt / 0.25));
    if (!drag?.moved || drag.turning) rotateCube((autoSpeed + yawVelocity) * dt, pitchVelocity * dt);
    const friction = Math.max(0, 1 - SPIN_FRICTION * dt);
    yawVelocity *= friction;
    pitchVelocity *= friction;
    stepTurns(dt);
    renderer.render(scene, camera);
  }
  new IntersectionObserver(([entry]) => {
    if (entry.isIntersecting) {
      last = performance.now();
      renderer.setAnimationLoop(frame);
    } else {
      renderer.setAnimationLoop(null);
    }
  }).observe(canvas);

  widget.classList.add('ready');
  // Show it's a real puzzle: it sits solved until it's actually on screen, then (after a beat, so
  // you see it solved first) scrambles itself once. Scrolling away before then cancels the wait.
  let scrambleTimer = 0;
  const scrambleWatcher = new IntersectionObserver(([entry]) => {
    clearTimeout(scrambleTimer);
    if (!entry.isIntersecting) return;
    scrambleTimer = setTimeout(() => {
      scrambleWatcher.disconnect();
      if (!turn && !queue.length && !drag) scramble();
    }, 700);
  }, { threshold: 0.6 });
  scrambleWatcher.observe(canvas);
}

function roundedSquare(size, r) {
  const h = size / 2;
  const s = new THREE.Shape();
  s.moveTo(-h + r, -h);
  s.lineTo(h - r, -h);
  s.quadraticCurveTo(h, -h, h, -h + r);
  s.lineTo(h, h - r);
  s.quadraticCurveTo(h, h, h - r, h);
  s.lineTo(-h + r, h);
  s.quadraticCurveTo(-h, h, -h, h - r);
  s.lineTo(-h, -h + r);
  s.quadraticCurveTo(-h, -h, -h + r, -h);
  return s;
}

function axisIndex(v) {
  const a = [Math.abs(v.x), Math.abs(v.y), Math.abs(v.z)];
  return a.indexOf(Math.max(...a));
}

function axisSign(v) {
  return v.getComponent(axisIndex(v));
}

// The nearest of the six axis directions.
function snapAxis(v) {
  const i = axisIndex(v);
  return new THREE.Vector3().setComponent(i, Math.sign(v.getComponent(i)));
}

function axisKey(v) {
  const i = axisIndex(v);
  return (v.getComponent(i) > 0 ? '+' : '-') + 'xyz'[i];
}

// Rounds a rotation that should be a multiple of 90° about each axis, so float error never builds up.
function snapRotation(q) {
  const m = new THREE.Matrix4().makeRotationFromQuaternion(q);
  const e = m.elements;
  for (const i of [0, 1, 2, 4, 5, 6, 8, 9, 10]) e[i] = Math.round(e[i]);
  q.setFromRotationMatrix(m);
}

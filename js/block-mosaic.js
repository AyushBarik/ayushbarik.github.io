// Profile picture made of Minecraft blocks (built by scripts/build_mosaic.py). Hovering zooms in
// around the cursor until each block shows at 2x its 16px texture, and names the block under it.
// The mosaic is drawn from a small atlas into a canvas rather than shipped as one big image, so
// it loads fast and stays pixel-sharp at any zoom.
(function () {
  const data = window.BLOCK_MOSAIC;
  const frame = document.getElementById('profileMosaic');
  if (!data || !frame) return;

  const BLOCK_CSS_PX = 32;   // on-screen size of one block when fully zoomed in
  const ZOOM_TIME = 0.12;    // seconds; time constants for easing toward the target view
  const PAN_TIME = 0.06;

  const fallback = frame.querySelector('img');
  const label = frame.querySelector('.mosaic-label');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const { cols, rows, tile, atlasCols, names } = data;

  const raw = atob(data.cells);
  const cells = new Uint16Array(cols * rows);
  for (let i = 0; i < cells.length; i++) {
    cells[i] = data.bytesPerCell === 2
      ? raw.charCodeAt(2 * i) | (raw.charCodeAt(2 * i + 1) << 8)
      : raw.charCodeAt(i);
  }

  const atlas = new Image();
  atlas.onload = init;
  atlas.src = frame.dataset.atlas;

  function init() {
    // levels[0] holds every block at full 16px; each later level halves the one before, so
    // drawing zoomed out samples a pre-averaged image instead of skipping most texels.
    const base = document.createElement('canvas');
    base.width = cols * tile;
    base.height = rows * tile;
    const baseCtx = base.getContext('2d');
    for (let i = 0; i < cells.length; i++) {
      const b = cells[i];
      baseCtx.drawImage(atlas, (b % atlasCols) * tile, Math.floor(b / atlasCols) * tile, tile, tile,
        (i % cols) * tile, Math.floor(i / cols) * tile, tile, tile);
    }
    const levels = [base];
    while (levels[levels.length - 1].width > cols * 2) {
      const prev = levels[levels.length - 1];
      const next = document.createElement('canvas');
      next.width = Math.ceil(prev.width / 2);
      next.height = Math.ceil(prev.height / 2);
      const ctx = next.getContext('2d');
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(prev, 0, 0, next.width, next.height);
      levels.push(next);
    }

    const canvas = document.createElement('canvas');
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', fallback.alt);
    const ctx = canvas.getContext('2d');
    frame.insertBefore(canvas, fallback);
    fallback.remove();

    let width = 0;       // canvas size in device pixels
    let height = 0;
    let maxZoom = 1;
    // View: zoom factor, and the image point (0-1) that stays fixed under the cursor while zooming.
    const view = { zoom: 1, x: 0.5, y: 0.5 };
    const target = { zoom: 1, x: 0.5, y: 0.5 };
    let frameId = 0;
    let lastTime = 0;

    function resize() {
      const css = frame.clientWidth;
      if (!css) return;
      width = Math.round(css * (window.devicePixelRatio || 1));
      height = Math.round(width * rows / cols);
      canvas.width = width;
      canvas.height = height;
      maxZoom = Math.max(1, BLOCK_CSS_PX * cols / css);
      if (target.zoom > 1) target.zoom = maxZoom;
      draw();
    }

    function draw() {
      const z = view.zoom;
      const w = 1 / z;                  // visible fraction of the image
      const x0 = view.x * (1 - w);
      const y0 = view.y * (1 - w);
      const blockPx = width * z / cols;  // device pixels per block at this zoom

      // Smallest level that still has at least one texel per device pixel.
      let level = 0;
      while (level + 1 < levels.length && tile / 2 ** (level + 1) >= blockPx) level++;
      const src = levels[level];
      // Downscaling needs smoothing to average texels; upscaling stays nearest-neighbor so the
      // blocks keep their hard pixel edges.
      ctx.imageSmoothingEnabled = tile / 2 ** level > blockPx;
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(src, x0 * src.width, y0 * src.height, w * src.width, w * src.height, 0, 0, width, height);

      const zoomedIn = z > 0.6 * maxZoom && target.zoom > 1;
      if (zoomedIn) {
        const col = Math.min(cols - 1, Math.floor(view.x * cols));
        const row = Math.min(rows - 1, Math.floor(view.y * rows));
        label.textContent = blockName(names[cells[row * cols + col]]);
      }
      label.classList.toggle('visible', zoomedIn);
    }

    function step(time) {
      const dt = lastTime ? Math.min(0.1, (time - lastTime) / 1000) : 1 / 60;
      lastTime = time;
      const zoomK = reduceMotion ? 1 : 1 - Math.exp(-dt / ZOOM_TIME);
      const panK = reduceMotion ? 1 : 1 - Math.exp(-dt / PAN_TIME);
      // Ease zoom in log space so zooming in and out feel equally fast.
      view.zoom = Math.exp(Math.log(view.zoom) + (Math.log(target.zoom) - Math.log(view.zoom)) * zoomK);
      view.x += (target.x - view.x) * panK;
      view.y += (target.y - view.y) * panK;

      const settled = Math.abs(Math.log(view.zoom / target.zoom)) < 1e-3 &&
        Math.abs(view.x - target.x) < 1e-4 && Math.abs(view.y - target.y) < 1e-4;
      if (settled) Object.assign(view, target);
      draw();
      frameId = settled ? 0 : requestAnimationFrame(step);
    }

    function animate() {
      if (!frameId) {
        lastTime = 0;
        frameId = requestAnimationFrame(step);
      }
    }

    function pointAt(e) {
      const rect = canvas.getBoundingClientRect();
      target.x = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
      target.y = Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height));
    }

    function zoomIn(e) {
      // Starting from rest, jump the anchor to the cursor so the zoom heads straight there.
      pointAt(e);
      if (view.zoom < 1.01) Object.assign(view, { x: target.x, y: target.y });
      target.zoom = maxZoom;
      animate();
    }

    function zoomOut() {
      target.zoom = 1;
      animate();
    }

    // Mouse and pen zoom on hover; touch zooms while a finger is held on the picture.
    canvas.addEventListener('pointerenter', (e) => { if (e.pointerType !== 'touch') zoomIn(e); });
    canvas.addEventListener('pointerleave', (e) => { if (e.pointerType !== 'touch') zoomOut(); });
    canvas.addEventListener('pointerdown', (e) => {
      if (e.pointerType !== 'touch') return;
      canvas.setPointerCapture(e.pointerId);
      zoomIn(e);
    });
    canvas.addEventListener('pointermove', (e) => {
      if (target.zoom === 1) {
        // The cursor can already be over the picture when it loads, with no pointerenter.
        if (e.pointerType !== 'touch') zoomIn(e);
        return;
      }
      pointAt(e);
      animate();
    });
    canvas.addEventListener('pointerup', (e) => { if (e.pointerType === 'touch') zoomOut(); });
    canvas.addEventListener('pointercancel', zoomOut);

    new ResizeObserver(resize).observe(frame);
    // Moving the window to a screen with a different pixel density doesn't resize the frame.
    // The query only describes the current density, so set up a new one after each change.
    (function watchDensity() {
      window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`)
        .addEventListener('change', () => { resize(); watchDensity(); }, { once: true });
    })();
  }

  // "oak_log_top" -> "Oak Log"
  function blockName(id) {
    return id
      .replace(/_(top|bottom|side|front|back|end|particle)\d*$/, '')
      .split('_')
      .map((w) => w[0].toUpperCase() + w.slice(1))
      .join(' ');
  }
})();

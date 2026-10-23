// Loads the Rubik's Cube (js/rubiks-cube-scene.js and three.js) once the Teaching & Service
// section is about to scroll into view, so the rest of the page never waits on it.
const widget = document.getElementById('cubeWidget');

if (widget) {
  const observer = new IntersectionObserver((entries) => {
    if (!entries.some((e) => e.isIntersecting)) return;
    observer.disconnect();
    import('./rubiks-cube-scene.js')
      .then((scene) => scene.mount(widget))
      .catch(() => { widget.hidden = true; });   // no WebGL, or the CDN is unreachable
  }, { rootMargin: '400px' });
  observer.observe(widget);
}

'use strict';

// Zeitbalken wie in Audio- und Videoprogrammen: Überblick über den gesamten erfassten Zeitraum mit einem Fenster
// für die aktuelle Ansicht. Das Fenster lässt sich ziehen (verschieben), an den Rändern ziehen (Zoom),
// per Mausrad zoomen, ein neuer Bereich lässt sich aufziehen, und per Tastatur bedienen. Alles ändert nur das Zeitfenster
// (setView in app.js); die Daten werden danach gebündelt neu geladen.

const TIMELINE = {height: 60, bars: 36, pad: 8, grab: 9};
let timelineLoadedAt = 0, timelineDrag = null, timelineWidth = 760;

async function updateTimeline(force = false) {
  if (force || !timelineData || Date.now() - timelineLoadedAt > 60000) {
    try { timelineData = await api('/api/timeline'); timelineLoadedAt = Date.now(); } catch { return; }
  }
  renderTimeline();
}

function timelineGeometry() {
  if (!timelineData?.start) return null;
  const first = timelineData.start, last = Math.max(first + 1, nowSeconds());
  const width = Math.max(280, timelineWidth), inner = width - 2 * TIMELINE.pad;
  return {first, last, width, inner, scale: inner / (last - first),
    x: ts => TIMELINE.pad + (ts - first) * inner / (last - first),
    ts: x => first + (x - TIMELINE.pad) * (last - first) / inner};
}

function timelineAxisLabel(ts, span) {
  const days = span / 86400;
  if (days > 700) return localTime(ts, {year: 'numeric'});
  if (days > 60) return localTime(ts, {month: 'short', year: '2-digit'});
  if (days > 3) return localTime(ts, {day: '2-digit', month: '2-digit'});
  return localTime(ts, {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'});
}

// Fenster in Pixeln; ein sehr schmales Fenster bleibt greifbar breit.
function timelineBox(g, win) {
  let left = g.x(win.from), right = g.x(win.to);
  if (right - left < 12) { const centre = (left + right) / 2; left = centre - 6; right = centre + 6; }
  return {left: Math.max(TIMELINE.pad - 4, left), right: Math.min(g.width - TIMELINE.pad + 4, right)};
}

// Greifzone der Ränder; bei einem schmalen Fenster bleibt die Mitte zum Verschieben frei.
const timelineGrab = (left, right) => Math.min(TIMELINE.grab, (right - left) / 3);

function renderTimeline() {
  const box = document.getElementById('timeline'), svg = document.getElementById('timeline-svg');
  if (!box || !svg) return;
  const g = timelineGeometry(), win = currentWindow();
  box.hidden = !g || !win || document.getElementById('range-bar').hidden;
  if (box.hidden) return;
  const measured = svg.getBoundingClientRect().width;
  if (measured >= 280) timelineWidth = measured;
  const geo = timelineGeometry(), {bars, height, pad} = TIMELINE;
  svg.setAttribute('viewBox', `0 0 ${geo.width} ${height}`);
  const max = Math.max(1e-9, ...timelineData.bins.map(bin => bin.kwh));
  const barWidth = Math.max(1, timelineData.bin_seconds * geo.scale - .5);
  const columns = timelineData.bins.map(bin => {
    const h = Math.max(2, bin.kwh / max * (bars - 2));
    return `<rect class="tl-bar${bin.covered < .5 ? ' low' : ''}" x="${geo.x(bin.ts).toFixed(1)}" y="${(bars - h).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${h.toFixed(1)}"/>`;
  }).join('');
  let ticks = '';
  for (let i = 0; i <= 4; i++) {
    const ts = geo.first + (geo.last - geo.first) * i / 4;
    ticks += `<text x="${geo.x(ts).toFixed(1)}" y="${height - 4}" text-anchor="${i === 0 ? 'start' : i === 4 ? 'end' : 'middle'}">${esc(timelineAxisLabel(ts, geo.last - geo.first))}</text>`;
  }
  const {left, right} = timelineBox(geo, win);
  svg.innerHTML = `<rect class="tl-track" x="${pad}" y="0" width="${geo.inner}" height="${bars}" rx="4"/>${columns}`
    + `<rect class="tl-dim" x="${pad}" y="0" width="${Math.max(0, left - pad)}" height="${bars}"/><rect class="tl-dim" x="${right}" y="0" width="${Math.max(0, geo.width - pad - right)}" height="${bars}"/>`
    + `<rect class="tl-window" x="${left}" y="0" width="${right - left}" height="${bars}" rx="3"/>`
    + `<rect class="tl-handle" x="${left - 3}" y="${bars / 2 - 9}" width="6" height="18" rx="3"/><rect class="tl-handle" x="${right - 3}" y="${bars / 2 - 9}" width="6" height="18" rx="3"/>${ticks}`;
  const text = windowText(win);
  document.getElementById('timeline-label').textContent = text;
  svg.setAttribute('aria-valuetext', text);
}

function timelinePointer(event) {
  const svg = document.getElementById('timeline-svg'), rect = svg.getBoundingClientRect();
  return (event.clientX - rect.left) * (timelineGeometry().width / (rect.width || timelineWidth));
}

function timelineBind() {
  const svg = document.getElementById('timeline-svg');
  if (!svg) return;
  svg.addEventListener('pointerdown', event => {
    const g = timelineGeometry(), win = currentWindow();
    if (!g || !win || event.button) return;
    event.preventDefault();
    svg.focus();
    const x = timelinePointer(event), {left, right} = timelineBox(g, win), grab = timelineGrab(left, right);
    const mode = Math.abs(x - left) <= grab ? 'left' : Math.abs(x - right) <= grab ? 'right' : x > left && x < right ? 'move' : 'select';
    timelineDrag = {mode, x, ts: g.ts(x), win, moved: false};
    svg.setPointerCapture?.(event.pointerId);
  });
  svg.addEventListener('pointermove', event => {
    const g = timelineGeometry(), win = currentWindow();
    if (!g || !win) return;
    const x = timelinePointer(event);
    if (!timelineDrag) {
      const {left, right} = timelineBox(g, win), grab = timelineGrab(left, right);
      svg.style.cursor = Math.abs(x - left) <= grab || Math.abs(x - right) <= grab ? 'ew-resize' : x > left && x < right ? 'grab' : 'crosshair';
      return;
    }
    const drag = timelineDrag, ts = g.ts(x), shift = (x - drag.x) / g.scale;
    if (!drag.moved && Math.abs(x - drag.x) < 3) return;
    drag.moved = true;
    if (drag.mode === 'move') setView(drag.win.from + shift, drag.win.to + shift);
    else if (drag.mode === 'left') setView(Math.min(ts, drag.win.to - MIN_SPAN), drag.win.to);
    else if (drag.mode === 'right') setView(drag.win.from, Math.max(ts, drag.win.from + MIN_SPAN));
    else setView(Math.min(drag.ts, ts), Math.max(drag.ts, ts));
  });
  const finish = event => {
    const drag = timelineDrag;
    timelineDrag = null;
    if (!drag || event.type === 'pointercancel') return;
    // Ein Klick neben das Fenster setzt es dorthin, mit unveränderter Länge.
    if (drag.mode === 'select' && !drag.moved) {
      const half = (drag.win.to - drag.win.from) / 2;
      setView(drag.ts - half, drag.ts + half);
    }
  };
  svg.addEventListener('pointerup', finish);
  svg.addEventListener('pointercancel', finish);
  svg.addEventListener('wheel', event => {
    const g = timelineGeometry();
    if (!g) return;
    event.preventDefault();
    viewZoomTs(g.ts(timelinePointer(event)), Math.exp(event.deltaY * .0025));
  }, {passive: false});
  svg.addEventListener('keydown', event => {
    const handled = event.key === 'ArrowLeft' ? (viewPan(event.shiftKey ? -.5 : -.1), true)
      : event.key === 'ArrowRight' ? (viewPan(event.shiftKey ? .5 : .1), true)
      : event.key === '+' || event.key === '=' ? (viewZoomAt(.5, .5), true)
      : event.key === '-' || event.key === '_' ? (viewZoomAt(.5, 2), true)
      : event.key.toLowerCase() === 'home' ? (showWholeHistory(), true) : false;
    if (handled) event.preventDefault();
  });
  document.getElementById('timeline-in').addEventListener('click', () => viewZoomAt(.5, .5));
  document.getElementById('timeline-out').addEventListener('click', () => viewZoomAt(.5, 2));
  document.getElementById('timeline-all').addEventListener('click', showWholeHistory);
  if (typeof ResizeObserver === 'function') new ResizeObserver(() => { if (!document.getElementById('timeline').hidden) renderTimeline(); }).observe(svg);
}

function showWholeHistory() {
  const g = timelineGeometry();
  if (g) setView(g.first, g.last);
}

timelineBind();

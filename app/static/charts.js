'use strict';

// Interaktion mit Diagrammen: Fadenkreuz mit Marker und Tooltip (Maus, Touch, Tastatur) sowie Zoomen und
// Verschieben der Zeitachse (Strg+Mausrad, Ziehen, Zwei-Finger-Geste). Die Diagramme melden ihre Daten
// über registerChart(); mountCharts() verbindet sie nach dem Zeichnen mit dem Dokument.
// Tooltips enthalten nur Text (textContent); sie ergänzen die Werte, sind aber nie die einzige Quelle.

const chartModels = new Map();
let chartCounter = 0;

function registerChart(model) {
  if (chartModels.size > 200) chartModels.clear();
  const id = 'chart' + (++chartCounter);
  chartModels.set(id, model);
  return id;
}

function nearestIndex(values, x) {
  let low = 0, high = values.length - 1;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (values[middle] < x) low = middle + 1; else high = middle;
  }
  return low > 0 && Math.abs(values[low - 1] - x) <= Math.abs(values[low] - x) ? low - 1 : low;
}

// Liniendiagramm: o = {data, field, xField, X, Y, x0, x1, w, h, left, right, top, bottom, gapLimit, label, overlays, seconds, zoomable}
function lineModel(o) {
  const xs = o.data.map(item => item[o.xField]), ys = o.data.map(item => item[o.field]);
  const tolerance = Number.isFinite(o.gapLimit) ? o.gapLimit / 2 : Infinity;
  const timed = o.xField === 'ts';
  const format = x => timed ? localTime(x, {day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', ...(o.seconds ? {second: '2-digit'} : {})}) : unit(x, 'h');
  const extras = (o.overlays || []).filter(overlay => overlay.type === 'line' || overlay.type === 'band');
  const near = (points, x) => {
    if (!points.length) return null;
    const point = points[nearestIndex(points.map(p => p.x), x)];
    return Math.abs(point.x - x) <= tolerance ? point : null;
  };
  const at = index => {
    const rows = [{v: unit(ys[index], o.label), cls: 'main'}];
    for (const overlay of extras) {
      const point = near(overlay.points, xs[index]);
      if (!point) continue;
      if (overlay.type === 'line') rows.push({v: unit(point.y, o.label), k: overlay.name, cls: overlay.cls});
      else rows.push({v: `${number(point.low, 0)} – ${unit(point.high, o.label)}`, k: overlay.name, cls: 'overlay-band'});
    }
    return {index, x: o.X(xs[index]), y: o.Y(ys[index]), head: format(xs[index]), rows};
  };
  return {type: 'line', count: xs.length, w: o.w, h: o.h, left: o.left, right: o.right, top: o.top, bottom: o.bottom, zoomable: !!o.zoomable, at,
    pick(svgX) {
      const x = o.x0 + (svgX - o.left) / (o.w - o.left - o.right) * (o.x1 - o.x0);
      const index = nearestIndex(xs, x);
      if (Math.abs(xs[index] - x) > tolerance) return {index: null, x: svgX, y: null, head: format(x), rows: [{v: t('keine Daten')}]};
      return at(index);
    }};
}

// Balkendiagramm: o = {w, h, left, right, top, bottom, width, items:[{head, rows, y}], zoomable}
function barModel(o) {
  const at = index => ({index, x: o.left + (index + .5) * o.width, y: o.items[index].y, head: o.items[index].head, rows: o.items[index].rows});
  return {type: 'bar', count: o.items.length, w: o.w, h: o.h, left: o.left, right: o.right, top: o.top, bottom: o.bottom, zoomable: !!o.zoomable, at,
    pick(svgX) {
      const index = Math.floor((svgX - o.left) / o.width);
      return index < 0 || index >= o.items.length ? null : at(index);
    }};
}

// Das Diagramm, dessen Tooltip gerade offen ist, und die laufende Zoom-/Verschiebegeste (unabhängig vom Element,
// weil das Diagramm beim Nachladen neu gezeichnet wird).
let activeChart = null;
let gesture = null;
const touches = new Map();

function hideActive() {
  if (activeChart) { activeChart.hide(); activeChart = null; }
}

document.addEventListener('pointerdown', event => {
  if (activeChart && !activeChart.chart.contains(event.target)) hideActive();
});

window.addEventListener('pointermove', event => {
  if (touches.has(event.pointerId)) touches.set(event.pointerId, {x: event.clientX, y: event.clientY});
  if (!gesture) return;
  if (gesture.kind === 'drag' && event.pointerId === gesture.id) {
    const dx = event.clientX - gesture.x;
    if (!gesture.moved && Math.abs(dx) < 4) return;
    if (!gesture.moved) { gesture.moved = true; hideActive(); document.body.classList.add('panning'); }
    const shift = -dx / gesture.pixels * gesture.span;
    if (typeof setView === 'function') setView(gesture.from + shift, gesture.to + shift);
  } else if (gesture.kind === 'pinch' && touches.size >= 2) {
    const [a, b] = [...touches.values()];
    const distance = Math.max(10, Math.hypot(a.x - b.x, a.y - b.y));
    const fraction = ((a.x + b.x) / 2 - gesture.plotLeft) / gesture.pixels;
    const span = gesture.span * gesture.distance / distance;
    const from = gesture.anchor - fraction * span;
    if (typeof setView === 'function') setView(from, from + span);
  }
});

function endPointer(event) {
  touches.delete(event.pointerId);
  if (gesture && ((gesture.kind === 'drag' && event.pointerId === gesture.id) || (gesture.kind === 'pinch' && touches.size < 2))) {
    gesture = null;
    document.body.classList.remove('panning');
  }
}
window.addEventListener('pointerup', endPointer);
window.addEventListener('pointercancel', endPointer);

const SVG_NS = 'http://www.w3.org/2000/svg';

function mountChart(chart, model) {
  const svg = chart.querySelector('svg');
  if (!svg) return;
  let cursor = null, line = null, dot = null, mark = null;
  if (model.type === 'line') {
    cursor = document.createElementNS(SVG_NS, 'g');
    cursor.setAttribute('class', 'chart-cursor');
    cursor.setAttribute('hidden', '');
    line = document.createElementNS(SVG_NS, 'line');
    line.setAttribute('y1', model.top);
    line.setAttribute('y2', model.h - model.bottom);
    dot = document.createElementNS(SVG_NS, 'circle');
    dot.setAttribute('r', 5);
    cursor.append(line, dot);
    svg.append(cursor);
  }
  const tip = document.createElement('div');
  tip.className = 'chart-tip';
  tip.hidden = true;
  chart.append(tip);
  let keyboardIndex = null, byPointer = false;

  const geometry = () => {
    const rect = svg.getBoundingClientRect();
    return {rect, scale: (rect.width || model.w) / model.w};
  };
  const plotPixels = () => (geometry().rect.width || model.w) * (model.w - model.left - model.right) / model.w;
  const svgX = event => { const {rect, scale} = geometry(); return (event.clientX - rect.left) / scale; };
  const fraction = event => Math.min(1, Math.max(0, (svgX(event) - model.left) / (model.w - model.left - model.right)));

  function hide() {
    tip.hidden = true;
    tip.removeAttribute('role');
    if (cursor) cursor.setAttribute('hidden', '');
    if (mark) { mark.classList.remove('hover'); mark = null; }
  }

  function show(info, announce) {
    if (!info) { hide(); return; }
    activeChart = {chart, hide};
    if (cursor) {
      line.setAttribute('x1', info.x);
      line.setAttribute('x2', info.x);
      if (info.y == null) dot.setAttribute('hidden', ''); else { dot.removeAttribute('hidden'); dot.setAttribute('cx', info.x); dot.setAttribute('cy', info.y); }
      cursor.removeAttribute('hidden');
    } else {
      if (mark) mark.classList.remove('hover');
      mark = svg.querySelector(`rect[data-i="${info.index}"]`);
      if (mark) mark.classList.add('hover');
    }
    const head = document.createElement('div');
    head.className = 'tip-head';
    head.textContent = info.head;
    tip.replaceChildren(head);
    for (const row of info.rows) {
      const item = document.createElement('div');
      item.className = 'tip-row';
      if (row.cls) { const key = document.createElement('i'); key.className = 'tip-key ' + row.cls; item.append(key); }
      const value = document.createElement('strong');
      value.textContent = row.v;
      item.append(value);
      if (row.k) { const name = document.createElement('span'); name.textContent = row.k; item.append(name); }
      tip.append(item);
    }
    if (announce) tip.setAttribute('role', 'status'); else tip.removeAttribute('role');
    tip.hidden = false;
    const {rect, scale} = geometry(), box = chart.getBoundingClientRect();
    const x = rect.left - box.left + info.x * scale, y = info.y == null ? 12 : rect.top - box.top + info.y * scale;
    const width = tip.offsetWidth, height = tip.offsetHeight, room = box.width || model.w;
    let left = x + 14;
    if (left + width > room) left = x - width - 14;
    tip.style.left = Math.max(0, left) + 'px';
    tip.style.top = Math.max(0, Math.min(Math.max(0, (box.height || model.h) - height), y - height / 2)) + 'px';
  }

  chart.addEventListener('pointermove', event => {
    if (gesture || (event.pointerType === 'touch' && touches.size > 1)) return;
    keyboardIndex = null;
    show(model.pick(svgX(event)), false);
  });
  chart.addEventListener('pointerleave', event => { if (event.pointerType !== 'touch' && !gesture) hide(); });
  chart.addEventListener('pointerdown', event => {
    byPointer = true;
    const {rect} = geometry();
    const base = {pixels: plotPixels(), plotLeft: rect.left + model.left * (rect.width || model.w) / model.w};
    const window_ = typeof currentWindow === 'function' ? currentWindow() : null;
    if (event.pointerType === 'touch') {
      touches.set(event.pointerId, {x: event.clientX, y: event.clientY});
      if (touches.size === 2 && model.zoomable && window_) {
        const [a, b] = [...touches.values()];
        const span = window_.to - window_.from;
        gesture = {kind: 'pinch', ...base, span, distance: Math.max(10, Math.hypot(a.x - b.x, a.y - b.y)),
          anchor: window_.from + span * Math.min(1, Math.max(0, ((a.x + b.x) / 2 - base.plotLeft) / base.pixels))};
        hide();
      } else if (touches.size === 1) show(model.pick(svgX(event)), false);
    } else if (event.button === 0 && model.zoomable && window_) {
      gesture = {kind: 'drag', id: event.pointerId, x: event.clientX, moved: false, ...base, from: window_.from, to: window_.to, span: window_.to - window_.from};
    }
  });
  chart.addEventListener('wheel', event => {
    if (!model.zoomable || typeof setView !== 'function') return;
    const horizontal = Math.abs(event.deltaX) > Math.abs(event.deltaY);
    if (event.ctrlKey || event.metaKey) {
      event.preventDefault();
      viewZoomAt(fraction(event), Math.exp(event.deltaY * .0025));
    } else if (event.shiftKey || horizontal) {
      event.preventDefault();
      viewPan((horizontal ? event.deltaX : event.deltaY) / plotPixels());
    }
  }, {passive: false});
  chart.addEventListener('dblclick', event => {
    if (model.zoomable && typeof setView === 'function') viewZoomAt(fraction(event), event.shiftKey ? 2 : .5);
  });

  const move = (index, announce = true) => {
    keyboardIndex = Math.min(model.count - 1, Math.max(0, index));
    show(model.at(keyboardIndex), announce);
  };
  chart.addEventListener('focus', () => {
    if (!byPointer && model.count) move(keyboardIndex ?? model.count - 1, false);
    byPointer = false;
  });
  chart.addEventListener('blur', () => { hide(); keyboardIndex = null; });
  chart.addEventListener('keydown', event => {
    if (!model.count) return;
    const current = keyboardIndex ?? model.count - 1, page = Math.max(1, Math.round(model.count / 10));
    const zoomable = model.zoomable && typeof setView === 'function';
    if (event.shiftKey && zoomable && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) viewPan(event.key === 'ArrowLeft' ? -.25 : .25);
    else if (event.key === 'ArrowLeft') move(current - 1);
    else if (event.key === 'ArrowRight') move(current + 1);
    else if (event.key === 'PageUp') move(current - page);
    else if (event.key === 'PageDown') move(current + page);
    else if (event.key.toLowerCase() === 'home') move(0);
    else if (event.key.toLowerCase() === 'end') move(model.count - 1);
    else if (event.key.toLowerCase() === 'escape') { hide(); keyboardIndex = null; }
    else if (zoomable && (event.key === '+' || event.key === '=')) viewZoomAt(.5, .5);
    else if (zoomable && (event.key === '-' || event.key === '_')) viewZoomAt(.5, 2);
    else return;
    event.preventDefault();
  });
}

function mountCharts(root = document) {
  for (const chart of root.querySelectorAll('.chart[data-chart]:not([data-mounted])')) {
    chart.dataset.mounted = '1';
    const model = chartModels.get(chart.dataset.chart);
    chartModels.delete(chart.dataset.chart);
    if (model) mountChart(chart, model);
  }
}

new MutationObserver(() => mountCharts()).observe(document.body, {childList: true, subtree: true});

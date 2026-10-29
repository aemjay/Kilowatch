'use strict';

// Einblendbare Vergleichs- und Referenzlinien für Diagramme. Die Auswahl je Diagramm liegt im Browser.
// Gleitende Werte laufen über ein zurückliegendes Zeitfenster (oder eine Anzahl Punkte) und brechen an
// Messlücken ab. Referenzlinien verändern die Achse nie: Liegt eine Grenze über dem Diagramm, steht nur ihr Name
// am oberen Rand.
const OVERLAYS = {
  mean: tk('Ø Zeitraum'),
  moving: tk('Gleitender Ø'),
  previous: tk('Vorperiode'),
};
// Diagramme, deren Vorperioden-Vergleich die Serie der Vorperiode vom Server braucht.
const COMPARED_CHARTS = ['power', 'energy-day', 'energy-month'];

function overlayChoice(chart) {
  try { return JSON.parse(localStorage.getItem('kilowatch-overlays-' + chart) || '[]'); } catch { return []; }
}

function setOverlayChoice(chart, list) {
  try { localStorage.setItem('kilowatch-overlays-' + chart, JSON.stringify(list)); } catch { /* nur Sitzung */ }
}

// Ob eine Übersichtsabfrage die Serie der Vorperiode mitladen soll.
function comparisonWanted() {
  return COMPARED_CHARTS.some(chart => overlayChoice(chart).includes('previous'));
}

// Gleitender Mittelwert: window in Sekunden bei Zeitachsen, sonst Anzahl Punkte. Null-Werte zählen nicht.
function rolling(data, field, xField, window, byCount = false, gapLimit = Infinity) {
  const result = [];
  let start = 0;
  data.forEach((item, index) => {
    if (index && data[index][xField] - data[index - 1][xField] > gapLimit) start = index;
    while (byCount ? index - start >= window : item[xField] - data[start][xField] >= window) start++;
    const values = data.slice(start, index + 1).map(row => row[field]).filter(value => value != null && Number.isFinite(value));
    result.push({x: item[xField], mean: item[field] == null || !values.length ? null : values.reduce((a, b) => a + b, 0) / values.length});
  });
  return result;
}

function average(data, field) {
  const values = data.map(row => row[field]).filter(value => value != null && Number.isFinite(value));
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
}

// Baut Overlays für ein Diagramm aus der gespeicherten Auswahl.
// spec: {chart, data, field, xField, window, byCount, windowLabel, gapLimit, trends,
//        previous: {label, kind: 'line'|'bars', points: [{x, y}]}, references: [{key, label, value}]}
function buildOverlays(spec) {
  const chosen = new Set(overlayChoice(spec.chart));
  if (spec.trends === false) for (const key of ['mean', 'moving']) chosen.delete(key);
  const overlays = [];
  if (chosen.has('previous') && spec.previous?.points?.length) {
    overlays.push({type: spec.previous.kind === 'bars' ? 'bars' : 'line', cls: 'overlay-previous', name: spec.previous.label, points: spec.previous.points, gap: spec.gapLimit});
  }
  if (chosen.has('moving')) {
    const series = rolling(spec.data, spec.field, spec.xField, spec.window, spec.byCount, spec.gapLimit);
    overlays.push({type: 'line', cls: 'overlay-moving', name: [t(OVERLAYS.moving), spec.windowLabel].filter(Boolean).join(' '), points: series.filter(p => p.mean != null).map(p => ({x: p.x, y: p.mean})), gap: spec.gapLimit});
  }
  if (chosen.has('mean')) {
    const value = average(spec.data, spec.field);
    if (value != null) overlays.push({type: 'hline', cls: 'overlay-mean', y: value, label: t('Ø {value}', {value: number(value, value < 10 ? 2 : 0)})});
  }
  for (const reference of spec.references || []) {
    if (chosen.has(reference.key) && reference.value != null) overlays.push({type: 'hline', cls: 'overlay-reference', y: reference.value, label: reference.label});
  }
  return overlays;
}

// Schalter über dem Diagramm. Änderungen zeichnen die Seite neu (onChange).
function overlayToggles(spec) {
  const chosen = new Set(overlayChoice(spec.chart));
  const trends = spec.trends === false ? [] : [['mean', t(OVERLAYS.mean)], ['moving', `${t(OVERLAYS.moving)} ${spec.windowLabel}`]];
  const items = [...trends,
    ...(spec.previous ? [['previous', spec.previous.label]] : []),
    ...(spec.references || []).filter(reference => reference.value != null).map(reference => [reference.key, reference.label])];
  return `<div class="overlay-toggles" data-overlay-chart="${esc(spec.chart)}">${items.map(([key, label]) => `<label class="overlay-toggle overlay-${esc(key)}"><input type="checkbox" value="${esc(key)}"${chosen.has(key) ? ' checked' : ''}><span>${esc(label)}</span></label>`).join('')}</div>`;
}

function mountOverlayToggles(root, onChange) {
  // Nur noch nicht verbundene Schalter, falls ein Seitenteil später nachgeladen wird.
  for (const box of root.querySelectorAll('[data-overlay-chart]:not([data-mounted])')) {
    box.dataset.mounted = '1';
    box.addEventListener('change', () => {
      setOverlayChoice(box.dataset.overlayChart, [...box.querySelectorAll('input:checked')].map(input => input.value));
      onChange();
    });
  }
}

// Fensterlänge passend zur Auflösung der Leistungskurve.
function powerWindow(resolution) {
  return resolution === 0 ? {window: 300, windowLabel: t('5 min')} : resolution === 60 ? {window: 900, windowLabel: t('15 min')} : {window: 7200, windowLabel: t('2 h')};
}

// Linienpunkte an Lücken trennen, damit keine Linie über fehlende Daten läuft.
function splitAtGaps(points, gap) {
  const segments = [];
  let segment = [];
  points.forEach((point, index) => {
    if (index && point.x - points[index - 1].x > gap) { if (segment.length) segments.push(segment); segment = []; }
    segment.push(point);
  });
  if (segment.length) segments.push(segment);
  return segments;
}

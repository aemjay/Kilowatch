'use strict';

// Einblendbare Trend- und Referenzlinien für Diagramme. Gleitende Werte laufen über ein
// zurückliegendes Zeitfenster (oder eine Anzahl Punkte) und brechen an Messlücken ab.
const OVERLAYS = {
  mean: tk('Ø Zeitraum'),
  moving: tk('Gleitender Ø'),
  range: tk('Gleitendes Min/Max'),
};

function overlayChoice(chart) {
  try { return JSON.parse(localStorage.getItem('kilowatch-overlays-' + chart) || '[]'); } catch { return []; }
}

function setOverlayChoice(chart, list) {
  try { localStorage.setItem('kilowatch-overlays-' + chart, JSON.stringify(list)); } catch { /* nur Sitzung */ }
}

// Gleitende Werte: window in Sekunden bei Zeitachsen, sonst Anzahl Punkte. Null-Werte zählen nicht.
function rolling(data, field, xField, window, byCount = false, gapLimit = Infinity) {
  const result = [];
  let start = 0;
  data.forEach((item, index) => {
    if (index && data[index][xField] - data[index - 1][xField] > gapLimit) start = index;
    while (byCount ? index - start >= window : item[xField] - data[start][xField] >= window) start++;
    const values = data.slice(start, index + 1).map(row => row[field]).filter(value => value != null && Number.isFinite(value));
    if (item[field] == null || !values.length) { result.push({x: item[xField], mean: null, low: null, high: null}); return; }
    result.push({x: item[xField], mean: values.reduce((a, b) => a + b, 0) / values.length, low: Math.min(...values), high: Math.max(...values)});
  });
  return result;
}

function average(data, field) {
  const values = data.map(row => row[field]).filter(value => value != null && Number.isFinite(value));
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
}

// Baut Overlays für ein Diagramm aus der gespeicherten Auswahl.
// spec: {chart, data, field, xField, window, byCount, windowLabel, gapLimit, references:[{key,label,value}]}
function buildOverlays(spec) {
  const chosen = new Set(overlayChoice(spec.chart));
  if (spec.trends === false) for (const key of Object.keys(OVERLAYS)) chosen.delete(key);
  const overlays = [];
  const series = (chosen.has('moving') || chosen.has('range')) ? rolling(spec.data, spec.field, spec.xField, spec.window, spec.byCount, spec.gapLimit) : [];
  if (chosen.has('range')) overlays.push({type: 'band', points: series.filter(p => p.low != null).map(p => ({x: p.x, low: p.low, high: p.high}))});
  if (chosen.has('moving')) overlays.push({type: 'line', cls: 'overlay-moving', points: series.filter(p => p.mean != null).map(p => ({x: p.x, y: p.mean}))});
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
  const trends = spec.trends === false ? [] : [['mean', t(OVERLAYS.mean)], ['moving', `${t(OVERLAYS.moving)} ${spec.windowLabel}`], ['range', `${t(OVERLAYS.range)} ${spec.windowLabel}`]];
  const items = [...trends,
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

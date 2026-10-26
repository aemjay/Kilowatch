'use strict';

// Übersicht: Kostenrate der laufenden Viertelstunde und Preisampel für dynamische Tarife.
// Zeiten in der Zeitzone aus den Einstellungen; alle Werte laufen über esc/number/unit.

const zoneTime = (ts, options = {}) => new Date(ts * 1000).toLocaleString(LOCALE, {timeZone: settings.timezone || 'Europe/Berlin', ...options});
const zoneClock = ts => zoneTime(ts, {hour: '2-digit', minute: '2-digit'});
const ctPrice = (eur, decimals = 2) => unit(eur * 100, 'ct/kWh', decimals);
// Stunde und Minute in der eingestellten Zeitzone, unabhängig vom Zahlenformat der Sprache.
function zoneParts(ts) {
  const parts = new Intl.DateTimeFormat('en-GB', {timeZone: settings.timezone || 'Europe/Berlin', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'}).formatToParts(new Date(ts * 1000));
  return {hour: Number(parts.find(p => p.type === 'hour').value), minute: Number(parts.find(p => p.type === 'minute').value)};
}

// Karte „Kostet gerade“: Netzleistung × Arbeitspreis bzw. Einspeisevergütung, Werte aus /api/live.
function liveCostParts() {
  const cost = live.cost || {}, valid = live.reading && !live.stale;
  if (!cost.tariff) return {label: t('Kostet gerade'), value: '—', note: t('Tarif unter Kosten & Tarife anlegen')};
  if (valid && cost.direction === 'export') {
    return {label: t('Erlös gerade'), value: number(cost.eur_per_hour, 2),
      note: cost.feedin_eur_kwh ? t('Einspeisevergütung {price}', {price: ctPrice(cost.feedin_eur_kwh)}) : t('Keine Einspeisevergütung hinterlegt')};
  }
  const note = cost.rate_eur_kwh == null ? t('Kein Preis für diese Viertelstunde') : t('Arbeitspreis {price}', {price: ctPrice(cost.rate_eur_kwh)});
  return {label: t('Kostet gerade'), value: number(valid ? cost.eur_per_hour : null, 2), note: valid ? note : `${note} · ${t('keine aktuelle Messung')}`};
}

function liveCostCard() {
  const p = liveCostParts();
  return `<div class="card metric-card"><div class="metric-label"><span id="live-cost-label">${esc(p.label)}</span><span class="metric-icon">€</span></div><div class="metric-value"><span id="live-cost">${esc(p.value)}</span><small>${esc(localCurrency('€/h'))}</small></div><div class="metric-note" id="live-cost-note">${esc(p.note)}</div></div>`;
}

function updateLiveCost() {
  const node = $('#live-cost');
  if (!node) return;
  const p = liveCostParts();
  node.textContent = p.value; $('#live-cost-label').textContent = p.label; $('#live-cost-note').textContent = p.note;
}

// Preisampel: drei Stufen relativ zu Minimum und Maximum des angezeigten Zeitraums.
const PRICE_LEVELS = [tk('günstig'), tk('mittel'), tk('teuer')];
const PRICE_CLASSES = ['price-low', 'price-mid', 'price-high'];
const PRICE_WINDOWS = [2, 3, 4];
let priceWindowHours = (() => { try { return PRICE_WINDOWS.includes(Number(localStorage.getItem('kilowatch-price-window'))) ? Number(localStorage.getItem('kilowatch-price-window')) : 2; } catch { return 2; } })();
let priceOutlookCache = null;

function priceLevel(value, low, high) {
  if (high - low < 1e-9) return 0;
  const share = (value - low)/(high - low);
  return share < 1/3 ? 0 : share < 2/3 ? 1 : 2;
}

function priceChart(data) {
  const start = data.start, end = data.tomorrow_available ? data.end : data.tomorrow_start;
  const slots = Math.round((end - start)/900), byStart = new Map(data.intervals.map(item => [item.start, item]));
  const w = 760, h = 210, left = 42, right = 9, top = 18, bottom = 34, width = (w - left - right)/slots;
  const values = data.intervals.filter(item => item.start < end).map(item => item.eur_kwh * 100);
  const low = Math.min(0, ...values), high = Math.max(.1, ...values) * 1.12;
  const Y = value => top + (high - value)/(high - low) * (h - top - bottom);
  const X = ts => left + (ts - start)/900 * width;
  let grid = '';
  for (let i = 0; i <= 4; i++) { const value = low + (high - low) * i/4, y = Y(value); grid += `<line class="grid-line" x1="${left}" x2="${w - right}" y1="${y}" y2="${y}"/><text x="${left - 8}" y="${y + 3}" text-anchor="end">${number(value, 0)}</text>`; }
  let marks = '', bars = '';
  const items = [];
  for (let index = 0; index < slots; index++) {
    const ts = start + index * 900, item = byStart.get(ts), local = zoneParts(ts);
    const head = `${zoneTime(ts, {weekday: 'short', hour: '2-digit', minute: '2-digit'})}–${zoneClock(ts + 900)}`;
    if (!local.minute && local.hour % 6 === 0) {
      const x = X(ts), midnight = !local.hour;
      marks += `${midnight && index ? `<line class="price-day" x1="${x}" x2="${x}" y1="${top}" y2="${h - bottom}"/>` : ''}<text x="${x}" y="${h - 9}" text-anchor="${index ? 'middle' : 'start'}">${esc(midnight ? zoneTime(ts, {weekday: 'short'}) : zoneClock(ts))}</text>`;
    }
    if (!item) { items.push({head, rows: [{v: t('keine Daten')}], y: Y(0)}); continue; }
    const ct = item.eur_kwh * 100, level = priceLevel(item.eur_kwh, data.low_eur_kwh, data.high_eur_kwh), y = Math.min(Y(ct), Y(0));
    const current = ts === data.current_start;
    items.push({head, rows: [{v: unit(ct, 'ct/kWh', 2), cls: 'main'}, {v: t(PRICE_LEVELS[level]) + (current ? ' · ' + t('jetzt') : '')}], y: Y(ct)});
    bars += `<rect class="bar ${PRICE_CLASSES[level]}${current ? ' price-current' : ''}" data-i="${index}" x="${X(ts) + width * .1}" y="${y}" width="${Math.max(1, width * .8)}" height="${Math.max(.5, Math.abs(Y(0) - Y(ct)))}"/>`;
  }
  const best = data.cheapest && data.cheapest.start < end ? `<rect class="price-best" x="${X(data.cheapest.start)}" y="${top}" width="${(Math.min(end, data.cheapest.end) - data.cheapest.start)/900 * width}" height="${h - top - bottom}"/>` : '';
  const now = data.current_start >= start && data.current_start < end ? `<line class="price-now" x1="${X(data.current_start) + width/2}" x2="${X(data.current_start) + width/2}" y1="${top - 6}" y2="${h - bottom}"/><text class="price-now-label" x="${X(data.current_start) + width/2}" y="${top - 8}" text-anchor="middle">${esc(t('jetzt'))}</text>` : '';
  const id = registerChart(barModel({w, h, left, right, top, bottom, width, items}));
  return `<div class="chart" data-chart="${id}" tabindex="0"><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(t('Strompreis je Viertelstunde in ct/kWh'))}">${best}${grid}${marks}${bars}${now}<text x="${left}" y="8">${esc(localCurrency('ct/kWh'))}</text></svg></div>`;
}

function priceOutlookPanel(data) {
  if (!data?.dynamic || !data.intervals?.length) return '';
  const toggle = `<div class="segments price-window-toggle" role="group" aria-label="${esc(t('Fensterlänge'))}">${PRICE_WINDOWS.map(hours => `<button type="button" data-price-window="${hours}" aria-pressed="${hours === data.window_hours}"${hours === data.window_hours ? ' class="selected"' : ''}>${hours} h</button>`).join('')}</div>`;
  const best = data.cheapest;
  const window = best ? t('{day} {from}–{to}, Ø {price}', {day: best.start >= data.tomorrow_start ? t('Morgen') : t('Heute'), from: zoneClock(best.start), to: zoneClock(best.end), price: ctPrice(best.average_eur_kwh, 1)})
    : t('Kein vollständiges Fenster mit Preisen ab jetzt.');
  const legend = `<div class="legend price-legend">${PRICE_LEVELS.map((label, index) => `<span><i class="${PRICE_CLASSES[index]}"></i>${esc(t(label))}</span>`).join('')}</div>`;
  const tomorrow = data.tomorrow_available ? '' : `<div class="notice info">${esc(t('Preise für morgen erscheinen am frühen Nachmittag.'))}</div>`;
  const note = `<p class="copy-footnote">${esc(t('Bruttopreise deines dynamischen Tarifs. Farben relativ zum günstigsten ({low}) und teuersten Preis ({high}) im Diagramm. Das Fenster beginnt frühestens mit der laufenden Viertelstunde; Zeiten in {zone}.', {low: ctPrice(data.low_eur_kwh), high: ctPrice(data.high_eur_kwh), zone: data.timezone}))}</p>`;
  return panel(t('Preisampel'), data.tomorrow_available ? t('Heute und morgen je Viertelstunde') : t('Heute je Viertelstunde'),
    `<div class="price-window"><span>${esc(t('Günstigstes Fenster'))}</span>${toggle}<strong id="price-window-text">${esc(window)}</strong></div>${tomorrow}${priceChart(data)}${note}`, legend);
}

function showPriceOutlook(slot, data) {
  slot.innerHTML = priceOutlookPanel(data);
  for (const button of $$('[data-price-window]', slot)) button.addEventListener('click', safely(async () => {
    priceWindowHours = Number(button.dataset.priceWindow);
    try { localStorage.setItem('kilowatch-price-window', String(priceWindowHours)); } catch { /* nur für diese Sitzung */ }
    await mountPriceOutlook();
    $(`[data-price-window="${priceWindowHours}"]`)?.focus();
  }));
}

async function mountPriceOutlook() {
  const slot = $('#price-outlook-slot');
  if (!slot) return;
  // Letzten Stand sofort zeigen, damit das Neuzeichnen der Übersicht nicht flackert.
  if (priceOutlookCache?.window_hours === priceWindowHours) showPriceOutlook(slot, priceOutlookCache);
  const data = await api('/api/prices/outlook?window_hours=' + priceWindowHours).catch(() => null);
  if (!data || !slot.isConnected || page !== 'dashboard') return;
  priceOutlookCache = data;
  showPriceOutlook(slot, data);
}

// Einrichtungsliste „Noch einzurichten“: offene Punkte mit Link zur passenden Seite, einzeln ausblendbar.
let checklistCache = null;

function checklistPanel(data) {
  if (!data?.items?.length) return '';
  const items = data.items.map(item => `<li><div><strong>${esc(t(item.title))}</strong><p>${esc(t(item.text, item.params || {}))}</p></div><div class="button-row"><a class="secondary" href="#${esc(item.page)}">${esc(t(pageText[item.page] || item.page))}</a><button type="button" class="subtle" data-checklist-mute="${esc(item.key)}" aria-label="${esc(t('„{title}“ ausblenden', {title: t(item.title)}))}">${esc(t('Ausblenden'))}</button></div></li>`).join('');
  return panel(t('Noch einzurichten'), t('Erledigte Punkte verschwinden von selbst.'), `<ul class="checklist">${items}</ul>`);
}

function showChecklist(slot, data) {
  slot.innerHTML = checklistPanel(data);
  for (const button of $$('[data-checklist-mute]', slot)) button.addEventListener('click', safely(async () => {
    const muted = [...new Set([...(data.muted || []), button.dataset.checklistMute])];
    checklistCache = await api('/api/checklist', 'PUT', {muted});
    if (slot.isConnected) showChecklist(slot, checklistCache);
    toast(t('Ausgeblendet. Unter Einstellungen wieder einblenden.'));
  }));
}

async function mountChecklist() {
  const slot = $('#checklist-slot');
  if (!slot) return;
  if (checklistCache) showChecklist(slot, checklistCache);
  const data = await api('/api/checklist').catch(() => null);
  if (!data || !slot.isConnected || page !== 'dashboard') return;
  checklistCache = data;
  showChecklist(slot, data);
}

'use strict';

// Übersetzungen nach gettext-Art: Der deutsche Quelltext ist der Schlüssel, Kataloge unter
// /i18n/<sprache>.json liefern die Übersetzung. Fehlt ein Eintrag, gilt Englisch, dann Deutsch.
// Platzhalter: {name}. Mehrzahl: Katalogwert als Objekt nach Intl.PluralRules ({one, other}),
// gewählt über den Parameter count.
const LANGUAGES = {
  de: {name: 'Deutsch', locale: 'de-DE'},
  en: {name: 'English', locale: 'en-GB'},
  nb: {name: 'Norsk bokmål', locale: 'nb-NO'},
  sv: {name: 'Svenska', locale: 'sv-SE'},
  nl: {name: 'Nederlands', locale: 'nl-NL'},
};
const CURRENCIES = {
  EUR: {symbol: '€', sub: 'ct', factor: 100},
  NOK: {symbol: 'kr', sub: 'øre', factor: 100},
  SEK: {symbol: 'kr', sub: 'öre', factor: 100},
};
let LANGUAGE = 'de', LOCALE = 'de-DE', CATALOG = {}, FALLBACK = {}, CURRENCY = CURRENCIES.EUR;

function storedLanguage() {
  try { return localStorage.getItem('kilowatch-language') || ''; } catch { return ''; }
}

function languageOptions(selected) {
  return Object.entries(LANGUAGES).map(([code, item]) => `<option value="${code}"${code === selected ? ' selected' : ''}>${item.name}</option>`).join('');
}

function pickLanguage(preferred) {
  const candidates = [preferred];
  candidates.push(storedLanguage());
  for (const value of navigator.languages || [navigator.language]) candidates.push(value);
  for (const value of candidates) {
    const code = String(value || '').toLowerCase().split('-')[0].replace(/^(no|nn)$/, 'nb');
    if (LANGUAGES[code]) return code;
  }
  return 'de';
}

async function loadCatalog(code) {
  if (code === 'de') return {};
  try {
    const response = await fetch(`/i18n/${code}.json`, {credentials: 'same-origin'});
    return response.ok ? await response.json() : {};
  } catch { return {}; }
}

async function setLanguage(code, remember = true) {
  code = LANGUAGES[code] ? code : 'de';
  const [catalog, fallback] = await Promise.all([loadCatalog(code), code === 'en' || code === 'de' ? {} : loadCatalog('en')]);
  LANGUAGE = code; LOCALE = LANGUAGES[code].locale; CATALOG = catalog; FALLBACK = fallback;
  if (remember) { try { localStorage.setItem('kilowatch-language', code); } catch { /* nur Sitzung */ } }
  document.documentElement.lang = code;
  const select = document.getElementById('login-language');
  if (select) select.innerHTML = languageOptions(code);
  translateStatic(document);
  window.kilowatchTheme?.refresh();
}

// Zahlen in Parametern vom Server im Format der Sprache.
function numberParams(params = {}) {
  return Object.fromEntries(Object.entries(params || {}).map(([key, value]) => [key, typeof value === 'number' ? value.toLocaleString(LOCALE) : value]));
}

// Markiert Quelltexte für die Extraktion, ohne sie sofort zu übersetzen.
const tk = text => text;
// Vorgegebene Namen des Zuhauses (Standard und Demo) erscheinen übersetzt; eigene Namen bleiben unverändert.
tk('Mein Zuhause'); tk('Beispielhaushalt');

let CURRENCY_CODE = 'EUR';
function setCurrency(code) { CURRENCY_CODE = CURRENCIES[code] ? code : 'EUR'; CURRENCY = CURRENCIES[CURRENCY_CODE]; }

// Geldbeträge: Quelltexte nennen € und ct; bei NOK/SEK werden Zeichen und Untereinheit ersetzt.
function localCurrency(text) {
  if (CURRENCY === CURRENCIES.EUR) return text;
  return String(text).replace(/€/g, CURRENCY.symbol).replace(/\bct\b/g, CURRENCY.sub);
}

function t(text, params = {}) {
  let value = CATALOG[text] ?? FALLBACK[text] ?? DE_PLURALS[text] ?? text;
  if (typeof params.count === 'number') {
    // Mehrzahl nach der Zahl selbst wählen, angezeigt wird sie im Format der Sprache.
    const count = params.count;
    params = {...params, count: count.toLocaleString(LOCALE)};
    if (value && typeof value === 'object') value = value[new Intl.PluralRules(LOCALE).select(count)] ?? value.other ?? text;
  }
  if (value && typeof value === 'object') {
    const category = new Intl.PluralRules(LOCALE).select(Number(params.count ?? 0));
    value = value[category] ?? value.other ?? text;
  }
  return localCurrency(String(value).replace(/\{(\w+)\}/g, (match, name) => name in params ? String(params[name]) : match));
}

// Deutsche Mehrzahlformen für Quelltexte, deren Zahl variiert.
const DE_PLURALS = {
  '{count} Lücke(n)': {one: '{count} Lücke', other: '{count} Lücken'},
  'Letzte {count} Std.': {one: 'Letzte Stunde', other: 'Letzte {count} Std.'},
  '{count} Person(en) im Haus': {one: '{count} Person im Haus', other: '{count} Personen im Haus'},
  '{count} Person(en) in einer Wohnung': {one: '{count} Person in einer Wohnung', other: '{count} Personen in einer Wohnung'},
  '{count} Hinweis(e) ausgeblendet.': {one: '{count} Hinweis ausgeblendet.', other: '{count} Hinweise ausgeblendet.'},
};

// Statische Texte in index.html: data-i18n (Text), data-i18n-placeholder, data-i18n-aria-label, data-i18n-title.
function translateStatic(root) {
  for (const node of root.querySelectorAll('[data-i18n]')) {
    node.dataset.i18nSource ??= node.textContent;
    node.textContent = t(node.dataset.i18nSource);
  }
  for (const attribute of ['placeholder', 'aria-label', 'title']) {
    for (const node of root.querySelectorAll(`[data-i18n-${attribute}]`)) {
      const key = `i18nSource${attribute.replace(/(^|-)(\w)/g, (m, d, c) => c.toUpperCase())}`;
      node.dataset[key] ??= node.getAttribute(`data-i18n-${attribute}`);
      node.setAttribute(attribute, t(node.dataset[key]));
    }
  }
  document.title = t('Kilowatch · Energie zu Hause');
}

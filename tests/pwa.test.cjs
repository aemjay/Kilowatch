'use strict';
// Update-Verhalten der installierten App mit gespielten Browser-Ereignissen (kein Browser nötig).
const assert = require('node:assert/strict');
const {test} = require('node:test');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {JSDOM} = require('jsdom');

const source = readFileSync(join(__dirname, '..', 'app', 'static', 'pwa.js'), 'utf8');

function start({controller = true, secure = true} = {}) {
  const dom = new JSDOM('<body><input id="field"></body>', {url: 'https://kilowatch.test/', runScripts: 'outside-only'});
  const w = dom.window;
  const listeners = {}, registrations = [];
  let reloads = 0, updates = 0;
  Object.defineProperty(w, 'isSecureContext', {value: secure});
  w.t = text => text;
  w.setInterval = () => 0;
  Object.defineProperty(w.navigator, 'serviceWorker', {value: {
    controller: controller ? {} : null,
    addEventListener: (name, handler) => { listeners[name] = handler; },
    register: async (url, options) => { registrations.push({url, options}); return {update: async () => { updates++; }}; },
  }});
  // jsdom kann location.reload nicht ersetzen: den Aufruf im Testexemplar umleiten.
  w.reloadPage = () => { reloads++; };
  w.eval(source.replace('location.reload()', 'window.reloadPage()'));
  return {w, listeners, registrations, reloads: () => reloads, updates: () => updates};
}

test('registers the worker without letting the browser cache it', async () => {
  const {registrations} = start();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(JSON.stringify(registrations), JSON.stringify([{url: '/sw.js', options: {updateViaCache: 'none'}}]));
});

test('does nothing without a secure context', () => {
  const {registrations} = start({secure: false});
  assert.equal(registrations.length, 0);
});

test('an update reloads the page automatically while nobody is typing', () => {
  const app = start();
  app.listeners.controllerchange();
  assert.equal(app.reloads(), 1);
});

test('the first installation does not reload the page', () => {
  const app = start({controller: false});
  app.listeners.controllerchange();
  assert.equal(app.reloads(), 0);
});

test('an update waits while a form field is focused and applies when the app goes to the background', () => {
  const app = start();
  app.w.document.getElementById('field').focus();
  app.listeners.controllerchange();
  assert.equal(app.reloads(), 0);
  const banner = app.w.document.querySelector('.pwa-bar');
  assert.ok(banner && banner.textContent.includes('aktualisiert'));
  banner.querySelector('.pwa-action').click();
  assert.equal(app.reloads(), 1);
});

test('offers the installation once and can be dismissed for good', () => {
  const app = start();
  const event = new app.w.Event('beforeinstallprompt', {cancelable: true});
  let prompted = 0;
  event.prompt = () => { prompted++; };
  app.w.dispatchEvent(event);
  const bar = app.w.document.querySelector('.pwa-bar');
  assert.ok(bar && event.defaultPrevented);
  bar.querySelector('.pwa-action').click();
  assert.equal(prompted, 1);
  assert.equal(app.w.document.querySelector('.pwa-bar'), null);

  const again = start();
  again.w.localStorage.setItem('kilowatch-install-dismissed', '1');
  again.w.dispatchEvent(new again.w.Event('beforeinstallprompt', {cancelable: true}));
  assert.equal(again.w.document.querySelector('.pwa-bar'), null);
});

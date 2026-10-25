'use strict';
// Service Worker von Kilowatch. Der Server liefert ihn mit der App-Version aus; sobald sich die Version
// ändert, erkennt der Browser einen neuen Worker und die Seite wird aktualisiert (pwa.js).
// Zwischengespeichert wird nur die App-Oberfläche. Anfragen an /api/ gehen immer ans Netz, damit nie Messdaten
// oder Anmeldedaten im Cache landen.
const VERSION = '__VERSION__';
const CACHE = 'kilowatch-' + VERSION;
const SHELL = ['/', '/style.css', '/theme.js', '/i18n.js', '/overlays.js', '/configure.js', '/extras.js', '/insights.js',
  '/app.js', '/pwa.js', '/icon.svg', '/icon-192.png', '/manifest.webmanifest'];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE)
    .then(cache => cache.addAll(SHELL.map(url => new Request(url, {cache: 'reload'}))))
    .then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(key => key.startsWith('kilowatch-') && key !== CACHE).map(key => caches.delete(key))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin
      || url.pathname.startsWith('/api/') || url.pathname === '/healthz' || url.pathname === '/sw.js') return;
  // Netz zuerst, damit nach einem Update nie alte Dateien erscheinen; ohne Netz gilt der Zwischenspeicher.
  event.respondWith((async () => {
    try {
      const response = await fetch(request);
      if (response.ok && response.type === 'basic') {
        const cache = await caches.open(CACHE);
        cache.put(request, response.clone());
      }
      return response;
    } catch (error) {
      const cached = await caches.match(request);
      if (cached) return cached;
      if (request.mode === 'navigate') {
        const home = await caches.match('/');
        if (home) return home;
      }
      throw error;
    }
  })());
});

// Installierbare App (PWA): Service Worker anmelden, Updates erkennen und einspielen, Installation anbieten.
(function () {
  if (!('serviceWorker' in navigator) || !window.isSecureContext) return;
  const bar = text => {
    const box = document.createElement('div');
    box.className = 'toast pwa-bar';
    box.setAttribute('role', 'status');
    const label = document.createElement('span');
    label.textContent = text;
    box.append(label);
    document.body.append(box);
    return {box, add(caption, onClick, secondary) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = secondary ? 'pwa-later' : 'pwa-action';
      button.textContent = caption;
      button.addEventListener('click', onClick);
      box.append(button);
    }};
  };
  const typing = () => ['input', 'textarea', 'select'].includes(document.activeElement && document.activeElement.localName);

  // Update: Der neue Worker übernimmt sofort (skipWaiting). Die Seite lädt dann selbst neu, sobald niemand
  // gerade ein Formular bearbeitet; sonst erscheint ein Hinweis, und beim Wechsel in den Hintergrund wird neu geladen.
  const hadController = !!navigator.serviceWorker.controller;
  let pending = false, reloading = false, banner = null;
  const reload = () => { if (!reloading) { reloading = true; location.reload(); } };
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (!hadController) return;
    if (!typing()) return reload();
    pending = true;
    if (!banner) {
      banner = bar(t('Kilowatch wurde aktualisiert.'));
      banner.add(t('Neu laden'), reload);
    }
  });
  document.addEventListener('visibilitychange', () => { if (pending && document.hidden && !typing()) reload(); });

  navigator.serviceWorker.register('/sw.js', {updateViaCache: 'none'}).then(registration => {
    const check = () => registration.update().catch(() => {});
    document.addEventListener('visibilitychange', () => { if (!document.hidden) check(); });
    window.addEventListener('online', check);
    setInterval(check, 60 * 60 * 1000);
  }).catch(() => {});

  // Installation anbieten, wenn der Browser sie erlaubt (Chrome, Edge, Android). Safari: Teilen → Zum Home-Bildschirm.
  let offered = false;
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();
    let dismissed = false;
    try { dismissed = localStorage.getItem('kilowatch-install-dismissed') === '1'; } catch (error) { /* ohne Speicher erneut fragen */ }
    if (offered || dismissed) return;
    offered = true;
    const offer = bar(t('Kilowatch als App installieren?'));
    offer.add(t('Installieren'), () => { offer.box.remove(); event.prompt(); });
    offer.add(t('Später'), () => {
      offer.box.remove();
      try { localStorage.setItem('kilowatch-install-dismissed', '1'); } catch (error) { /* ignorieren */ }
    }, true);
  });
})();

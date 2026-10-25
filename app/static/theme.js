'use strict';
// Läuft vor dem ersten Zeichnen: gespeichertes Farbschema setzen, damit nichts aufblitzt.
// Ohne Eintrag folgt die Oberfläche der Systemeinstellung (prefers-color-scheme).
(function () {
  const order = ['auto', 'light', 'dark'];
  const labels = {auto: 'Farbschema: automatisch', light: 'Farbschema: hell', dark: 'Farbschema: dunkel'};
  const icons = {auto: 'Auto', light: 'Hell', dark: 'Dunkel'};
  function stored() { try { return localStorage.getItem('kilowatch-theme') || 'auto'; } catch { return 'auto'; } }
  function apply(mode) {
    if (mode === 'auto') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', mode);
    const button = document.getElementById('theme-toggle');
    if (button) { button.textContent = icons[mode]; button.title = labels[mode]; button.setAttribute('aria-label', labels[mode]); }
  }
  apply(stored());
  window.kilowatchTheme = {
    current: stored,
    // Diagramme lesen das tatsächlich aktive Schema (auch bei „automatisch“).
    isDark: () => getComputedStyle(document.documentElement).getPropertyValue('--is-dark').trim() === '1',
    cycle() {
      const next = order[(order.indexOf(stored()) + 1) % order.length];
      try { if (next === 'auto') localStorage.removeItem('kilowatch-theme'); else localStorage.setItem('kilowatch-theme', next); } catch { /* nur für diese Sitzung */ }
      apply(next);
      return next;
    },
    refresh: () => apply(stored()),
  };
})();

# Übersetzungen

Die Oberfläche gibt es auf Deutsch, Englisch, Norwegisch (Bokmål), Schwedisch und Niederländisch, also in den Sprachen der Märkte, in denen Tibber aktiv ist. Die Sprache lässt sich auf der Anmeldeseite und unter **Einstellungen → Sprache und Währung** wählen. Ohne Auswahl gilt die Browsersprache, sonst Deutsch.

## Wie es funktioniert

- Der deutsche Text ist der Schlüssel. Die Kataloge liegen unter `app/static/i18n/<sprache>.json` und ordnen jedem deutschen Text die Übersetzung zu.
- Fehlt eine Übersetzung, gilt Englisch, dann Deutsch.
- `{name}` ist ein Platzhalter und muss unverändert bleiben.
- Hängt ein Text von einer Anzahl ab, kann der Wert ein Objekt mit Mehrzahlformen sein, zum Beispiel `{"one": "{count} gap", "other": "{count} gaps"}`.
- Beträge stehen in den Texten immer als `€` und `ct`. Bei der Währung NOK oder SEK ersetzt Kilowatch nur diese Zeichen durch `kr` und `øre` bzw. `öre`. Es wird nichts umgerechnet: Eigene Tarife trägst du direkt in deiner Währung ein.
- Fehlermeldungen und Benachrichtigungen übersetzt der Server mit denselben Katalogen. Benachrichtigungen verwenden die zuletzt in der Oberfläche gewählte Sprache.

## Einschränkungen

- Englisch, Norwegisch, Schwedisch und Niederländisch sind maschinell vorübersetzt und noch nicht von Muttersprachlern geprüft. Korrekturen sind willkommen.
- HT/NT und der monatliche Abschlag sind Begriffe aus deutschen Stromverträgen; sie sind übersetzt, aber nicht an andere Tarifmodelle angepasst.
- Die optionalen Börsenpreise stammen von aWATTar DE (Preiszone DE-LU, Euro). Bei NOK oder SEK blendet Kilowatch sie deshalb aus.
- Die Dokumentation ist auf Deutsch.

## Texte ergänzen oder korrigieren

1. Neue Texte in JavaScript mit `t('…')` schreiben (Platzhalter als zweites Argument: `t('{count} Tage', {count})`). Python-Meldungen für die Oberfläche als `ValueError("…")`, mit Platzhaltern als `UserError("… {name} …", name=wert)`.
2. Fehlende und überzählige Schlüssel anzeigen:

   ```sh
   python tools/i18n_extract.py --missing
   ```

3. Übersetzungen in den JSON-Dateien ergänzen.
4. `python -m pytest tests/test_i18n.py` prüft Vollständigkeit, Platzhalter, Währungszeichen und meldet deutsche Texte, die nicht übersetzbar markiert sind (`python tools/i18n_extract.py --untranslated`).

Eine neue Sprache braucht einen Eintrag in `LANGUAGES` in `app/static/i18n.js` und `app/i18n.py`, einen Katalog und einen Eintrag in `tools/i18n_extract.py`.

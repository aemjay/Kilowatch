# Bedienung

Diagramme ablesen, Zeiträume zoomen, Sprache und Währung wählen.

## Werte ablesen

- **Maus:** Ein Fadenkreuz rastet auf den nächsten Messwert ein. Der Tooltip nennt Zeit und Wert und bei eingeblendeten Trendlinien auch deren Werte. Über Messlücken steht „keine Daten“.
- **Balken:** Der Balken unter dem Zeiger hebt sich ab; der Tooltip nennt Datum, Energie und erfasste Stunden.
- **Touch:** Antippen oder mit einem Finger streichen zeigt den Wert, senkrechtes Wischen scrollt die Seite.
- **Tastatur:** Diagramm mit Tab anspringen, dann `←` `→` (Punkt für Punkt), `Bild↑` `Bild↓`, `Pos1` `Ende`, `Esc`. Der Wert wird vorgelesen.

## Zeitraum zoomen und verschieben

Der **Zeitbalken** unter der Zeitraumleiste zeigt den gesamten erfassten Zeitraum (Energie je Abschnitt, blasse Balken = wenig erfasst). Das Fenster darin ist der Zeitraum, den du siehst.

| Aktion | Wirkung |
|---|---|
| Fenster ziehen | verschiebt den Zeitraum |
| Rand ziehen | ändert Beginn oder Ende |
| Mausrad auf dem Zeitbalken | zoomt um den Zeiger |
| Klick neben das Fenster / ziehen | setzt das Fenster dorthin / wählt neuen Bereich |
| `+` `−` **Alles** | hinein, heraus, ganzer Zeitraum |
| Pfeiltasten, `+` `−`, `Pos1` auf dem Zeitbalken | verschieben (mit `Umschalt` halbe Fensterbreite), zoomen, alles zeigen |

**Im Diagramm:** `Strg` + Mausrad (oder Pinch auf dem Trackpad) zoomt, Ziehen verschiebt, `Umschalt` + Mausrad verschiebt ebenfalls, Doppelklick zoomt hinein (`Umschalt` heraus). Auf dem Handy zoomen und verschieben zwei Finger.

Das Fenster misst 5 Minuten bis zum gesamten Zeitraum, höchstens zehn Jahre. Die Auflösung passt sich an: bis 30 Minuten einzelne Werte bzw. Minuten, bis drei Tage Viertelstunden, darüber Tage und Monate. Reicht das Fenster bis zur Gegenwart, aktualisiert es sich selbst. Eine Voreinstellung (Heute, 7 Tage …) hebt die freie Auswahl auf. Alle Seiten rechnen mit dem gewählten Zeitraum; der Export nutzt die Datumsfelder, die mitwandern.

## Sprache und Währung

Die Oberfläche gibt es auf Deutsch, Englisch, Norwegisch (Bokmål), Schwedisch und Niederländisch. Wähle sie auf der Anmeldeseite oder unter **Einstellungen → Sprache und Währung**; ohne Auswahl gilt die Browsersprache, sonst Deutsch. Benachrichtigungen nutzen die gespeicherte Sprache.

- Die Währung (€, NOK, SEK) ändert nur das Zeichen, es wird nichts umgerechnet. Eigene Tarife trägst du direkt in deiner Währung ein.
- Die Börsenpreis-Funktionen gibt es nur für Euro.
- Die Übersetzungen außer Deutsch sind maschinell vorübersetzt; Korrekturen sind willkommen. HT/NT und Abschlag sind Begriffe aus deutschen Verträgen.

<details><summary>Für Mitwirkende: Texte ergänzen</summary>

Der deutsche Text ist der Schlüssel; die Kataloge liegen in `app/static/i18n/<sprache>.json`. Neue Texte schreibst du in JavaScript als `t('…')` und in Python als `ValueError("…")` bzw. `UserError("… {name} …", name=wert)`. `python tools/i18n_extract.py --missing` zeigt fehlende Schlüssel, `python -m pytest tests/test_i18n.py` prüft Vollständigkeit und Platzhalter. Fehlt eine Übersetzung, gilt Englisch, dann Deutsch.
</details>

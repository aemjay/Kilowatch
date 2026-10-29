# Bedienung

Diagramme ablesen, Zeiträume zoomen, Sprache und Währung wählen.

## Werte ablesen

- **Maus:** Ein Fadenkreuz rastet auf den nächsten Messwert ein. Der Tooltip nennt Zeit und Wert und bei eingeblendeten Vergleichslinien auch deren Werte. Über Messlücken steht „keine Daten“.
- **Balken:** Der Balken unter dem Zeiger hebt sich ab; der Tooltip nennt Datum, Energie und erfasste Stunden.
- **Touch:** Antippen oder mit einem Finger streichen zeigt den Wert, senkrechtes Wischen scrollt die Seite.
- **Tastatur:** Diagramm mit Tab anspringen, dann `←` `→` (Punkt für Punkt), `Bild↑` `Bild↓`, `Pos1` `Ende`, `Esc`. Der Wert wird vorgelesen.

## Vergleichslinien

Über den Diagrammen der Übersicht, des Verlaufs und der Analyse lassen sich Linien einblenden. Die Auswahl merkt sich der Browser je Diagramm.

| Linie | Bedeutung |
|---|---|
| **Ø Zeitraum** | Mittelwert aller gezeichneten Werte |
| **Gleitender Ø** | Mittel über die letzten 5 oder 15 Minuten bzw. 2 Stunden (Leistung), 7 Tage oder 3 Monate (Energie); bricht an Messlücken ab |
| **Vorperiode** | der gleich lange Zeitraum davor: als gestrichelte Linie über der Leistungskurve, als graue Schatten hinter den Energiebalken. Die Serie wird erst geladen, wenn du sie einschaltest |
| **Nachtgrundlast**, **Grundlast kWh/Tag** | Nachtgrundlast der letzten sieben Tage, bei Tagesbalken als Energie pro Tag |
| **Grenze hohe Last**, **Tagesziel**, **Typischer Haushalt** | Schwelle aus den Einstellungen, Monatsziel als Tagesanteil, Stromspiegel-Referenz |

Referenzlinien verändern die Achse nicht: Liegt ein Wert über dem Diagramm, steht nur sein Name mit ▲ am oberen Rand. Der Prozentvergleich zur Vorperiode (Übersicht) erscheint erst, wenn beide Zeiträume zu mindestens 95 % erfasst sind; die Vorperiode selbst ist immer sichtbar.

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

## Noch einzurichten

Oben auf der Übersicht listet Kilowatch offene Einrichtungsschritte, jeweils mit Link zur passenden Seite. Erledigte Punkte verschwinden, ist nichts offen, fehlt die Karte.

| Punkt | Erscheint, wenn |
|---|---|
| Kein Tarif hinterlegt | es keinen Tarif gibt |
| Dynamischer Tarif ohne Preisquelle / Preisabruf gestört | ein dynamischer Tarif existiert und keine Preisquelle gewählt ist, oder seit mehr als 26 Stunden kein Abruf gelungen ist |
| E-Mail-Benachrichtigungen aus | Hauptschalter, E-Mail-Kanal, SMTP-Server oder Empfänger fehlen |
| Keine aktuelle Sicherung | im Sicherungsordner keine tägliche Sicherung jünger als acht Tage liegt |
| Update verfügbar | die eingeschaltete Update-Prüfung eine neue Version gefunden hat |

**Ausblenden** schaltet einen Punkt dauerhaft stumm, auch wenn er später wieder zutrifft; **Einstellungen → Hinweise auf der Übersicht → Alle wieder einblenden** hebt das auf. Wer Preise nur per CSV importiert, blendet den Preisquellen-Hinweis so aus. Ob die Bridge noch in die Tibber-Cloud sendet, prüft die Liste nicht: Kilowatch liest aus `/status.json` nur Firmware, MQTT-Status und Laufzeit, nicht das MQTT-Ziel. Im Demo-Modus zeigt der Update-Punkt ein Beispiel.

## Gerät messen

Unter **Ereignisse → Gerät messen** misst eine Stoppuhr den Mehrverbrauch des Hauses: **Messung starten** merkt Zeitpunkt und Bezugszählerstand, danach das Gerät einschalten; nach dem Gerätelauf **Messung beenden**. Das Ergebnis zeigt Mehrverbrauch, Dauer, mittlere Mehrleistung und Kosten mit dem über die Messdauer gemittelten Arbeitspreis (bei HT/NT und dynamischen Tarifen je Viertelstunde anteilig); mit einem Namen bleibt es in der Liste.

- Gemessen wird am Netzanschluss: Alles, was im Zeitraum zusätzlich lief (Kühlschrank, Licht, andere Geräte), zählt mit. Abgezogen wird nur die Nachtgrundlast der letzten sieben Tage. Für belastbare Werte in ruhigen Zeiten messen und mehrfach wiederholen. Bei PV-Einspeisung während der Messung ist das Ergebnis zu niedrig.
- Start und Ende brauchen einen frischen Zählerstand (höchstens 30 Sekunden alt). Die Genauigkeit hängt von der Auflösung des Zählerstands ab; liefert dein Zähler nur gerundete Werte, eignet sich die Messung nur für größere Verbräuche.
- Es läuft höchstens eine Messung. Sie liegt in der Datenbank und läuft bei Neustart oder in einem anderen Browser weiter. Nach 24 Stunden wird sie abgebrochen und als unvollständig gespeichert.

## Sprache und Währung

Die Oberfläche gibt es auf Deutsch, Englisch, Norwegisch (Bokmål), Schwedisch und Niederländisch. Wähle sie auf der Anmeldeseite oder unter **Einstellungen → Sprache und Währung**; ohne Auswahl gilt die Browsersprache, sonst Deutsch. Benachrichtigungen nutzen die gespeicherte Sprache.

- Die Währung (€, NOK, SEK) ändert nur das Zeichen, es wird nichts umgerechnet. Eigene Tarife trägst du direkt in deiner Währung ein.
- Die Börsenpreis-Funktionen gibt es nur für Euro.
- Die Übersetzungen außer Deutsch sind maschinell vorübersetzt; Korrekturen sind willkommen. HT/NT und Abschlag sind Begriffe aus deutschen Verträgen.

<details><summary>Für Mitwirkende: Texte ergänzen</summary>

Der deutsche Text ist der Schlüssel; die Kataloge liegen in `app/static/i18n/<sprache>.json`. Neue Texte schreibst du in JavaScript als `t('…')` und in Python als `ValueError("…")` bzw. `UserError("… {name} …", name=wert)`. `python tools/i18n_extract.py --missing` zeigt fehlende Schlüssel, `python -m pytest tests/test_i18n.py` prüft Vollständigkeit und Platzhalter. Fehlt eine Übersetzung, gilt Englisch, dann Deutsch.
</details>

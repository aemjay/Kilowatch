# Tests und Abnahme

Was die automatischen Tests abdecken und was du bei jeder Installation selbst prüfen solltest. Alle Testdaten sind künstlich; echte Telegramme und Zugangsdaten gehören nicht ins Repository.

## Automatische Tests

```sh
python -m pytest                               # Python 3.13
npm ci --ignore-scripts && npm test            # Oberfläche mit jsdom, Node 24
```

Der [GitHub-Workflow](../.github/workflows/nas-image.yml) führt beides aus, prüft die JavaScript-Syntax und alle Compose-Dateien, baut Images für amd64 und arm64 und testet sie als Container: Start ohne Zugangsdaten, Einrichtung über den Setup-Code, API, Sicherung, Dateirechte, Neustart und das Update von der letzten Version. Mosquitto prüft er getrennt.

| Bereich | Geprüft |
|---|---|
| Messung | SML und CRC, Skalierung, Vorzeichen, T1/T2 ohne Doppelzählung, Energiebilanz, Lücken ohne erfundene Werte, Zählerwechsel |
| Zeit und Kosten | 23-/25-Stunden-Tage, Tarifwechsel, HT/NT, negative und fehlende Preise, dynamische Preisquellen |
| Sicherheit | Anmeldung, Sitzungen, Sperre, Ursprungsprüfung, verschlüsselte Zugangsdaten, Passwort-Rücksetzung |
| Netzwerk | Gerätenamen mit wechselnden DNS-Antworten, Gerätesuche, Abweisen öffentlicher Ziele |
| Betrieb | Sicherung und Wiederherstellung, Migrationen mit Vorab-Sicherung, Installations- und Update-Skript inklusive Rollback |
| Benachrichtigungen | SMTP-Sicherheit, Regeln, Ruhezeiten, Wiederholungen, Test-Begrenzung (mit simulierter Gegenstelle) |
| Oberfläche | Einrichtung, Formulare, Tooltips, Zeitbalken und Zoom, Farbschema, Sprachen, App-Installation, Dokumentationslinks |

> [!NOTE]
> Echte E-Mail-Zustellung, Gerätesuche im echten Netz und Touch-Gesten auf echten Geräten deckt die Automatik nicht ab.

## Bei jeder Installation prüfen

- [ ] Setup abschließen und frische Messwerte sehen.
- [ ] Nach 24 Stunden den Tagesverbrauch mit dem Zählerstand vergleichen.
- [ ] Bridge- und Host-Neustart: Webserver, Namensauflösung, Wiederanlauf, gespeicherte Zugänge.
- [ ] Datenbank und Zugangsdaten getrennt sichern und die Wiederherstellung in einer Testinstanz ausprobieren.
- [ ] Mail-Test wirklich empfangen, dann Alarm und Entwarnung prüfen.
- [ ] HT/NT-Zeiten mit dem Vertrag abgleichen.
- [ ] Nur bei Cloud-Ausstieg: lokalen MQTT-Betrieb erst ohne, dann mit Internetsperre je mindestens 24 Stunden beobachten.

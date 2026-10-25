# Testabdeckung und Abnahme

Diese Seite beschreibt, was die automatisierten Tests abdecken, und welche Punkte jede Installation selbst abnehmen sollte. Sie enthält keine Daten einer konkreten Installation.

## Automatisierte Tests

- **Python-Tests** (`python -m pytest`, Python 3.13): Decoder, Berechnung, API, Sicherung/Restore, Schema-Migrationen, lokale Geheimnisspeicherung, Einrichtung, DNS, Gerätesuche, Tarife, Analysen, Börsenpreise, Update-Hinweis, Benachrichtigungen, Übersetzungen und Installer.
- **DOM-Tests** (`npm test`, Node 24/jsdom): Ersteinrichtung, Passwortbestätigung, FQDN-Verbindungstest, Speicherung/Testversand in der Oberfläche, Entfernen des Bridge-Passworts, Absendername und Erkennungswort im Betreff, Gerätesuche, HT/NT-Tarif, Börsenpreise, Tarifsimulation, Budget, Farbschema sowie Sprache und Währung. API-Antworten sind ausschließlich simuliert, es gibt kein Netzwerk und kein echtes Konto.
- JavaScript-Syntaxprüfung aller Oberflächenskripte.
- Alle Testdaten sind synthetisch. Echte Telegramme, Kennungen und Zugangsdaten gehören nicht ins Repository.

## Wesentliche Nachweise

| Bereich | Geprüftes Verhalten |
|---|---|
| SML/Register | CRC, Skalierung, Vorzeichen, T1/T2 ohne Doppelzählung, fehlende Register unbekannt |
| Energiebilanz | Zählerdifferenzen, Leistungsintegration beim Nulldurchgang, Grenzen von Minuten/Viertelstunden |
| Lücken/Plausibilität | keine erfundenen Nullwerte/Stundenwerte, persistente Basis, Zählerwechsel und Rücksprünge |
| Zeit/Tarife | 23-/25-Stunden-Tage, kalendertäglicher Grundpreis, Tarifwechsel, negative Preise und fehlende Preisintervalle |
| Einrichtung | keine persönliche Adresse/Benutzer/Passwort vorbelegt; einmaliger Setup-Code nicht per API lesbar |
| Anmeldung | Hash nach Neustart, Sitzungen, Drosselung, Ursprungsprüfung, Passwortänderung beendet alle Sitzungen |
| Geheimnisse | verschlüsselte lokale Speicherung getrennt vom Datenordner, keine Rückgabe, verlorener Schlüssel wird nicht ersetzt |
| Passwort-Wiederherstellung | Bestätigung gestoppter App erforderlich; nur App-Anmeldung zurücksetzen, Daten/Geheimnisse behalten |
| FQDN | simulierter Wechsel der DNS-Antwort beim nächsten Abruf, ursprünglicher Host-Header, DNS-Fehler, öffentliche/gemischte Ziele abweisen |
| SMTP | Zertifikatsprüfung, STARTTLS vor Anmeldung, kein unverschlüsselter Rückfall, Absendername, Erkennungswort im Betreff |
| Regeln | Ausfall einmal, Entwarnung nur nach zugestelltem Alarm, Beruhigung, Lastdauer nur mit kontinuierlichen frischen Daten |
| Zustellung | Ruhezeit auch in doppelter Winterzeitstunde, begrenzte Wiederholungen, Regelabschaltung verwirft ausstehende Alarme |
| Testversand | bewusste Aktion, 30 Sekunden Begrenzung, keine automatische Wiederholung |
| Backup/Restore | konsistenter Roundtrip, Schema/Integrität, ungültige Quelle ersetzt keine vorhandene Datenbank |
| Migrationen | geprüfte Sicherung vor jeder Schemaänderung, jede Stufe in eigener Transaktion, neuere Datenbank wird abgewiesen |
| Übersetzungen | alle Kataloge vollständig, Platzhalter und Mehrzahlformen erhalten, keine unmarkierten deutschen Texte, Fehlermeldungen und Benachrichtigungen in der gewählten Sprache |
| Paket | Quell-/Prebuilt-Konfiguration gleich, keine Zugangsdaten in Beispiel-Umgebung |

Ein Deprecation-Hinweis zum HTTPX-basierten Starlette-Testclient betrifft die Testumgebung und ist kein fehlgeschlagener Test.

## Linux-Container und Download

Der [GitHub-Workflow](../.github/workflows/nas-image.yml) führt Python- und DOM-Tests unter Linux aus, validiert alle Compose-Varianten und baut danach Images für amd64 und arm64 (arm64 per QEMU-Emulation); beide durchlaufen den Integrationstest. Der Integrationstest startet den Container ohne Zugangsdaten, liest den synthetischen Setup-Code aus dessen Protokoll, richtet ein Testpasswort ein und prüft API, Backup, Dateirechte sowie Persistenz nach Neustart. Mosquitto wird separat mit künstlichen Daten geprüft.

Eine externe E-Mail-Zustellung wird dadurch nicht bestätigt. Den konkreten Build-Status und das importierbare Artefakt immer im zugehörigen Actions-Lauf prüfen.

## Bei jeder Installation abzunehmen

- [ ] Projekt starten, Setup abschließen, frische echte Werte sehen.
- [ ] Bridge-FQDN vom Container auflösen; nach einem DHCP-Adresswechsel Empfang erneut prüfen.
- [ ] RAM/CPU und Datenwachstum auf dem NAS beobachten. Die Compose-Limits sind keine Messwerte.
- [ ] Tagesverbrauch nach mindestens 24 Stunden mit den Zählerständen vergleichen.
- [ ] Bridge- und NAS-Neustart prüfen: Webserver, DNS, Wiederanlauf und gespeicherte Zugangsdaten.
- [ ] Datenbank sowie Hash/Geheimnisse/Schlüssel getrennt sichern; Wiederherstellung in einer Testinstanz prüfen.
- [ ] Eigene E-Mail-Konfiguration: Test tatsächlich empfangen, dann Alarm und Entwarnung prüfen.
- [ ] HT/NT-Uhrzeiten mit dem eigenen Vertrag abgleichen.
- [ ] Falls vollständiger Cloud-Ausstieg gewünscht: lokalen MQTT-Betrieb mit NAS-FQDN erst ohne Internetsperre, danach mit Sperre und Neustart jeweils mindestens 24 Stunden prüfen.

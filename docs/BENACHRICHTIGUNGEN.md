# E-Mail-Benachrichtigungen einrichten

E-Mail ist der einzige Benachrichtigungskanal. Kanal und Hauptschalter sind zunächst ausgeschaltet. Alles wird nach der lokalen Anmeldung unter **Benachrichtigungen** eingerichtet und bleibt änderbar. Die Erfassung funktioniert auch ohne Benachrichtigungen.

## E-Mail

1. Eigenen SMTP-Server, Port und Verschlüsselung eintragen: meist **587/STARTTLS** oder **465/direktes TLS**. Die tatsächlichen Vorgaben des Mailanbieters verwenden.
2. Benutzer und SMTP-/App-Passwort eintragen. Manche Anbieter verlangen ein gesondertes App-Passwort. Absender muss zum Konto passen.
   Der **Absendername** (Standard „Kilowatch“) erscheint im Postfach vor der Adresse.
3. Bis zu fünf Empfänger ohne Anzeigenamen eingeben, je Zeile oder mit Komma getrennt.
4. **Speichern & E-Mail-Test senden** wählen. Der Test versendet eine erkennbare Testnachricht ohne Messwerte. Fehler erscheinen in der Oberfläche und im Zustellverlauf.
   Optional ein **Erkennungswort im Betreff** wählen, das nur du kennst, z. B. `Kuckuck-17`. Es steht in eckigen Klammern vor jedem Betreff (höchstens 40 Zeichen). Nachrichten, die angeblich von Kilowatch kommen, aber dieses Wort nicht tragen, sind gefälscht. Das Wort eignet sich auch für Mailfilter. Es ist kein Passwort und wird wie die übrigen Einstellungen lokal gespeichert.
5. Nach erfolgreichem Test **E-Mail als Kanal** sowie **Automatische Benachrichtigungen** aktivieren und speichern.

TLS-Zertifikate werden geprüft. Es gibt keinen Rückfall auf unverschlüsselten Versand. STARTTLS wird vor einer SMTP-Anmeldung ausgeführt. Ein erfolgreicher Versand bestätigt die Annahme durch den SMTP-Server, nicht den Eingang im Postfach; gegebenenfalls Spamordner prüfen. E-Mail ist nicht durch diese Anwendung Ende-zu-Ende-verschlüsselt.

Einstellungen früherer Versionen für den entfernten Messenger-Kanal werden ignoriert; wartende Nachrichten dieses Kanals werden verworfen und ein gespeicherter Gateway-Token beim Start gelöscht. Den Zusatzcontainer und sein Volume bei Bedarf selbst entfernen.

## Regeln und empfohlener Einstieg

| Regel | Vorgabe bei Aktivierung | Verhalten |
|---|---|---|
| Keine frischen Zählerdaten | 120 Sekunden | Meldet ausbleibende gültige Messungen; nach App-Start gilt die Wartezeit erneut |
| Hohe Dauerlast | zunächst aus; 3000 W für 10 Minuten | Nur frische, kontinuierliche Daten; Entwarnung unter 90 % der Schwelle |
| Tagesbudget Netzbezug | 0 = aus | Einmal pro lokalem Tag nach Erreichen der erfassten kWh; fehlende Daten können zusätzlichen Verbrauch enthalten |
| Batteriespannung | 2,7 V | Nur bei aktueller verfügbarer Diagnose; Entwarnung ab Schwelle + 0,15 V |
| Datenspeicher knapp | weniger als 512 MiB frei | Freier Speicher am Datenpfad; Entwarnung erst mit 10 % Reserve über der Schwelle |

Zunächst Messausfälle aktivieren und Dauerlast/Tagesbudget nach eigenen Erfahrungswerten ergänzen. Die Batterieschwelle ist ein veränderbarer Hinweis und keine garantierte Restlaufzeit. Die separate Analyse des Nachtmedians bleibt ein Hinweis in der Oberfläche.

## Ruhezeiten und Zustellung

- Ruhezeiten verwenden **Europe/Berlin**, auch bei Sommer-/Winterzeit. Vorgabefenster 22–07 Uhr, zunächst ausgeschaltet.
- Automatische Nachrichten warten während der Ruhezeit. Löst sich ein Problem vor dem Versand, werden zugehörige ausstehende Alarme verworfen.
- Standardmäßig ein Alarm je Zustandswechsel, mindestens 60 Minuten zwischen erneuten Alarmen derselben Regel. Kein Alarm pro Messpunkt.
- Entwarnungen gehen nur an Kanäle, die den zugehörigen Alarm bereits erfolgreich angenommen haben. Wiederholungen des Normalzustands werden vermieden.
- Die Warteschlange bleibt bei App-Neustarts bestehen. Bei Versandfehlern maximal fünf Versuche mit wachsenden Pausen; nach 24 Stunden veraltete automatische Nachrichten verwerfen. Der Zustellverlauf zeigt Fehler und Annahme durch den Versanddienst.
- Tests sind bewusste Einzelaktionen: Sie umgehen Hauptschalter/Ruhezeit, werden nicht automatisch wiederholt und sind auf einen Test in 30 Sekunden begrenzt.
- Bei pausierter oder noch nicht eingerichteter Erfassung entstehen keine neuen Messalarme; pausierte Erfassung pausiert auch automatischen Versand. Im Demo-Modus ist der Versand abgeschaltet.

Passwörter/Token werden verschlüsselt lokal gespeichert und nicht zurück an den Browser geliefert. Empfänger und Servernamen sind lokale Einstellungen. Sicherung und Schlüsselverwaltung: [BETRIEB.md](BETRIEB.md).

## Grenzen und Abnahme

Ein komplett ausgefallener Host oder ein ausgefallener Internetzugang kann aus diesem System heraus keine Nachricht zustellen. Für die Überwachung des Hosts selbst wäre ein zusätzlicher unabhängiger Monitor sinnvoll. Alarmmeldungen sind Hinweise zur privaten Verbrauchsauswertung.

Der Versand ist mit einer simulierten SMTP-Gegenstelle getestet. Die automatisierten Tests verwenden kein echtes Konto und versenden keine reale Nachricht. Nach der Einrichtung einen Test empfangen, anschließend eine passend gewählte Regel auslösen und Entwarnung sowie Ruhezeit prüfen. Messung und Zustellung getrennt beurteilen.

Primärquelle: [Python SMTP](https://docs.python.org/3/library/smtplib.html).

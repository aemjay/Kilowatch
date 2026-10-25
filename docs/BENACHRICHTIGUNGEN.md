# E-Mail und Signal einrichten

Beide Kanäle und der Hauptschalter sind zunächst ausgeschaltet. Alles wird nach der lokalen Anmeldung unter **Benachrichtigungen** eingerichtet und bleibt änderbar. Die Erfassung funktioniert auch ohne Nachrichtenkanäle.

## E-Mail

1. Eigenen SMTP-Server, Port und Verschlüsselung eintragen: meist **587/STARTTLS** oder **465/direktes TLS**. Die tatsächlichen Vorgaben des Mailanbieters verwenden.
2. Benutzer und SMTP-/App-Passwort eintragen. Manche Anbieter verlangen ein gesondertes App-Passwort. Absender muss zum Konto passen.
3. Bis zu fünf Empfänger ohne Anzeigenamen eingeben, je Zeile oder mit Komma getrennt.
4. **Speichern & E-Mail-Test senden** wählen. Der Test versendet eine erkennbare Testnachricht ohne Messwerte. Fehler erscheinen in der Oberfläche und im Zustellverlauf.
5. Nach erfolgreichem Test **E-Mail als Kanal** sowie **Automatische Benachrichtigungen** aktivieren und speichern.

TLS-Zertifikate werden geprüft. Es gibt keinen Rückfall auf unverschlüsselten Versand. STARTTLS wird vor einer SMTP-Anmeldung ausgeführt. Ein erfolgreicher Versand bestätigt die Annahme durch den SMTP-Server, nicht den Eingang im Postfach; gegebenenfalls Spamordner prüfen. E-Mail ist nicht durch diese Anwendung Ende-zu-Ende-verschlüsselt.

## Signal: optionaler Zusatzcontainer

Kilowatch verwendet [signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api) als Community-Anbindung. Das ist kein offizieller Signal-Bot-Dienst. Du benötigst ein bereits eingerichtetes Signal-Konto auf dem Handy. Die Anwendung registriert keine neue Telefonnummer und verschickt keine SMS zur Registrierung.

Im NAS-Projektordner:

```sh
docker compose -f compose.yaml -f compose.signal.yaml up -d
```

Mit importiertem App-Image:

```sh
docker compose -f compose.yaml -f compose.signal.yaml up -d
```

Im Container Manager muss die Projektkonfiguration beide Services enthalten. Dafür die YAML-Dateien zusammenführen oder den SSH-Befehl verwenden. `signal-api` muss im gleichen Compose-Netzwerk wie `kilowatch` laufen. Die Zusatzdatei allein ist keine vollständige App-Installation. Bei späteren Updates die Zusatzdatei mitführen.

Das Image ist auf `bbernhard/signal-cli-rest-api:0.101` festgelegt (Multi-Arch, amd64 und arm64), Modus `json-rpc`. Dieser nutzt Java und setzt daher keinen Native-Modus mit zusätzlichen CPU-Anforderungen voraus; auch ältere NAS-CPUs sind damit geeignet. RAM-Limit: 1024 MiB, zusätzlich zur App. Dauerbetrieb und tatsächlichen Bedarf auf dem NAS kontrollieren. Kein Gateway-Port wird ins LAN veröffentlicht.

Koppeln:

1. Unter **Benachrichtigungen → Signal** die Gateway-URL **`http://signal-api:8080`** eintragen. Signal-Kanal und Hauptschalter vorerst aus lassen.
2. **Speichern & Kopplungs-QR anzeigen** wählen. Nur angemeldete App-Nutzer können den lokalen QR abrufen.
3. Am Handy Signal → **Einstellungen → Gekoppelte Geräte → Neues Gerät koppeln** öffnen und QR scannen. Der QR ist zeitlich begrenzt; bei Ablauf neu anfordern.
4. Die zu diesem Konto gehörende Absendernummer und bis zu fünf Empfänger jeweils international mit `+` eintragen. Die Empfänger müssen Signal verwenden. Gruppen-IDs sind in dieser Version nicht unterstützt.
5. **Speichern & Signal-Test senden** wählen und Eingang am Empfänger prüfen. Dann Signal-Kanal, gewünschte Regeln und Hauptschalter einschalten und speichern.

Ein Gateway-Token ist nur für eine eigene vorgeschaltete Authentifizierung vorgesehen. Der mitgelieferte interne Container verlangt standardmäßig keinen Token. Die App akzeptiert lokale Gateway-Adressen per IP oder DNS und prüft die aufgelösten IPv4-Ziele vor der Verbindung. Der private Docker-Servicename funktioniert ohne feste IP.

Das Volume `kilowatch-signal` bewahrt die gekoppelte Geräteidentität. Nicht bei Updates löschen. Signal-/signal-cli-Änderungen können später ein kontrolliertes Update oder erneutes Koppeln erfordern. Unter **Gekoppelte Geräte** am Handy lässt sich der Zugang widerrufen. Nachrichtenempfang und benötigte Kontoverbindung laufen im JSON-RPC-Dienst. Der erste Start kann etwas dauern; bei Problemen `docker compose -f compose.yaml -f compose.signal.yaml logs --tail=100 signal-api` prüfen. Logs können Kontoinformationen enthalten und gehören nicht ins Repository.

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
- Tests sind bewusste Einzelaktionen: Sie umgehen Hauptschalter/Ruhezeit, werden nicht automatisch wiederholt und sind je Kanal auf einen Test in 30 Sekunden begrenzt.
- Bei pausierter oder noch nicht eingerichteter Erfassung entstehen keine neuen Messalarme; pausierte Erfassung pausiert auch automatischen Versand. Im Demo-Modus sind Versand und Signal-Kopplung abgeschaltet.

Passwörter/Token werden verschlüsselt lokal gespeichert und nicht zurück an den Browser geliefert. Empfänger und Servernamen sind lokale Einstellungen. Sicherung und Schlüsselverwaltung: [BETRIEB.md](BETRIEB.md).

## Grenzen und Abnahme

Ein komplett ausgefallenes NAS oder ein ausgefallener Internetzugang kann aus diesem System heraus keine Nachricht zustellen. Für die Überwachung des NAS selbst wäre ein zusätzlicher unabhängiger Monitor sinnvoll. Alarmmeldungen sind Hinweise zur privaten Verbrauchsauswertung.

Die Transportwege sind mit simulierten SMTP-/Signal-Gegenstellen getestet. Die automatisierten Tests koppeln kein echtes Konto und versenden keine reale Nachricht. Nach der Einrichtung je Kanal einen Test empfangen, anschließend eine passend gewählte Regel auslösen und Entwarnung sowie Ruhezeit prüfen. Messung und Zustellung getrennt beurteilen.

Primärquellen: [Gateway-Dokumentation](https://github.com/bbernhard/signal-cli-rest-api), [API](https://bbernhard.github.io/signal-cli-rest-api/), [Signal: Gekoppelte Geräte](https://support.signal.org/hc/en-us/articles/360007320551-Linked-Devices), [Python SMTP](https://docs.python.org/3/library/smtplib.html).

# Quellen und technische Grundlagen

Für die Ausarbeitung herangezogene Primärquellen (Stand Oktober 2026). Firmwareverhalten aus einem Community-Projekt ist von offiziell zugesicherten Geräteeigenschaften zu unterscheiden. Der verwendete Stand von `ha-tibber-pulse-local` wurde unter Commit `f23fdf9c04050ab39af0340aabba54ecc65b44c9` gelesen; spätere Änderungen können abweichen.

| Thema | Quelle | Bedeutung für das Projekt |
|---|---|---|
| Projekte in Container Manager | [Synology-Hilfe](https://kb.synology.com/de-de/DSM/help/ContainerManager/docker_project?version=7) | Compose-Projekt, Pfad, Erstellen/Bauen/Starten |
| Lokalen Bridge-Webserver aktivieren | [Community-Vorbereitung](https://github.com/marq24/ha-tibber-pulse-local/blob/f23fdf9c04050ab39af0340aabba54ecc65b44c9/preparation.md) | Basic Auth, Node-ID, Parameter 39 und Prüfungen |
| Betrieb ohne Tibber-Kunde | [Community-Dokumentation](https://github.com/marq24/ha-tibber-pulse-local/blob/f23fdf9c04050ab39af0340aabba54ecc65b44c9/TIBBER-PULSE-AS-NON-TIBBER-CUSTOMER.md) | Firmware kann funktionierendes MQTT-Ziel erwarten |
| Neuer/alter Datenpfad | [Bridge-Client im Community-Projekt](https://github.com/marq24/ha-tibber-pulse-local/blob/f23fdf9c04050ab39af0340aabba54ecc65b44c9/custom_components/tibber_local/tibber_client.py) | `/node_data.json` und Legacy `/data.json` |
| SML-Dekodierung | [SmlLib](https://github.com/spacemanspiff2007/SmlLib), [PyPI 1.7](https://pypi.org/project/smllib/1.7/) | Streamreader, CRC, OBIS und Skalierung |
| SQLite-WAL | [SQLite-Dokumentation](https://sqlite.org/wal.html) | Datenbank auf lokalem Dateisystem; WAL beachten |
| Konsistente Sicherung | [SQLite-Backup-API](https://sqlite.org/backup.html), [Python sqlite3](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup) | Sicherung während laufender Erfassung |
| MQTT-Konfiguration | [Mosquitto-Handbuch](https://mosquitto.org/man/mosquitto-conf-5.html) | Listener, anonyme Verbindung, Topic-ACL und Grenzen |
| Offizielles Brokerimage | [Docker Official Images](https://github.com/docker-library/official-images/blob/master/library/eclipse-mosquitto) | verfügbarer Tag 2.0.22, Multi-Arch (amd64/arm64) |
| Compose-Umgebung | [Docker Compose .env](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/) | lokale Konfiguration und Variablenersetzung |

## Sicherheit, Benachrichtigungen und Tests

| Thema | Primärquelle | Verwendung |
|---|---|---|
| Heimnetz-Gerätenamen | [FRITZ!Box: Gerätenamen](https://fritz.com/de-ch/apps/knowledge-base/FRITZ-Box-7360-SL/791_Netzwerkgerat-kann-nicht-umbenannt-werden) | DNS-Hostnamen statt fest eingetragener Geräte-IP; Router-DNS muss Namen tatsächlich pflegen |
| Lokale Verschlüsselung | [cryptography/Fernet](https://cryptography.io/en/latest/fernet/) | authentifizierte Verschlüsselung mit separat zu sicherndem lokalem Schlüssel |
| Passwort-Hash | [Python hashlib.scrypt](https://docs.python.org/3/library/hashlib.html#hashlib.scrypt) | gesalzener Hash für die App-Anmeldung |
| Mailversand | [Python smtplib](https://docs.python.org/3/library/smtplib.html), [TLS-Kontexte](https://docs.python.org/3/library/ssl.html#ssl.create_default_context) | STARTTLS/direktes TLS mit Zertifikatsprüfung |
| Signal-Gateway | [Upstream](https://github.com/bbernhard/signal-cli-rest-api), [Release 0.101](https://github.com/bbernhard/signal-cli-rest-api/releases/tag/0.101), [API](https://bbernhard.github.io/signal-cli-rest-api/) | JSON-RPC-Modus, QR-Kopplung, lokaler Versandaufruf |
| Signal-Kopplung | [Signal Support](https://support.signal.org/hc/en-us/articles/360007320551-Linked-Devices) | vom Nutzer am Handy bestätigte Verknüpfung eines Geräts |
| DOM-Tests | [jsdom](https://github.com/jsdom/jsdom) | isolierte Formularprüfungen ohne echten Browser und ohne Nachrichtenversand |

FQDN-Verhalten wird mit wechselnden simulierten DNS-Antworten getestet. Ob die eigene Bridge-Firmware für ihr optionales MQTT-Ziel DNS-Namen auflöst, ist vor Ort zu prüfen.

## Börsenpreise

[aWATTar/tado° DE API](https://energy.tado.com/services/api): veröffentlichte Börsenwerte mit Millisekunden-Zeitstempeln und Einheit EUR/MWh. Daraus werden keine vollständigen Vertragspreise abgeleitet.

## Strommix und CO₂

[Energy-Charts API](https://api.energy-charts.info/) des Fraunhofer ISE, Daten unter [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), Quellenangabe „Energy-Charts.info“ in der Oberfläche:

- `co2eq`: CO₂-Äquivalente in g/kWh je Viertelstunde für das gewählte Land. Veröffentlichte Werte erscheinen mit etwa 8 bis 12 Stunden Verzögerung. Die mitgelieferte Prognosereihe springt an der Übergangsstelle teils um ein Vielfaches (z. B. Niederlande 132 → 16 g/kWh) und wird deshalb nicht verwendet. Die Methodik beschreibt die Schnittstelle nicht. Ein Abgleich mit dem veröffentlichten Erzeugungsmix (`public_power`) passt zu Lebenszyklus-Faktoren (inklusive Vorketten), nicht zu reinen Verbrennungsemissionen; Kilowatch weist die Werte deshalb als Schätzung der Quelle aus.
- `public_power`: Reihe „Renewable share of load“ (Anteil erneuerbarer Erzeugung an der Last) je Viertelstunde.

Die Bilanz multipliziert den Netzbezug jeder Viertelstunde mit dem gemessenen Wert derselben Viertelstunde. Einspeisung wird nicht gegengerechnet, Bezug ohne veröffentlichten Wert wird getrennt ausgewiesen. Meldet die Schnittstelle `deprecated`, zeigt Kilowatch einen Hinweis.

## Vergleichswerte typischer Haushalte

[Stromspiegel für Deutschland (co2online), Stand 13.05.2025](https://www.stromspiegel.de/stromverbrauch-verstehen/stromverbrauch-im-haushalt/): durchschnittlicher Jahresverbrauch in kWh.

| Personen | Wohnung | Wohnung, Warmwasser elektrisch | Haus | Haus, Warmwasser elektrisch |
|---|---|---|---|---|
| 1 | 1.200 | 1.600 | 1.800 | 2.100 |
| 2 | 1.900 | 2.500 | 2.700 | 3.200 |
| 3 | 2.400 | 3.500 | 3.500 | 4.100 |
| 4 | 2.600 | 4.000 | 3.800 | 4.700 |
| 5 | 3.100 | 5.000 | 4.500 | 6.000 |

Elektrische Heizung, Wärmepumpe und E-Auto sind nicht enthalten. Die Werte beschreiben den gesamten Haushaltsstrom; mit eigener PV ist der gemessene Netzbezug niedriger. Für die Niederlande, Norwegen und Schweden fand sich keine vergleichbare, nach Haushaltsgröße aufgeschlüsselte Primärquelle; die Oberfläche weist darauf hin.

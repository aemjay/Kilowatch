# Quellen

Primärquellen, auf denen Kilowatch beruht (Stand Oktober 2026). Verhalten, das nur aus dem Community-Projekt `ha-tibber-pulse-local` stammt (gelesen unter Commit `f23fdf9c04050ab39af0340aabba54ecc65b44c9`), ist keine zugesicherte Geräteeigenschaft.

## Bridge und Betrieb

| Thema | Quelle |
|---|---|
| Lokalen Bridge-Webserver aktivieren | [Community-Vorbereitung](https://github.com/marq24/ha-tibber-pulse-local/blob/f23fdf9c04050ab39af0340aabba54ecc65b44c9/preparation.md) |
| Betrieb ohne Tibber-Kunde | [Community-Dokumentation](https://github.com/marq24/ha-tibber-pulse-local/blob/f23fdf9c04050ab39af0340aabba54ecc65b44c9/TIBBER-PULSE-AS-NON-TIBBER-CUSTOMER.md) |
| Datenpfade `/node_data.json` und `/data.json` | [Bridge-Client der Community](https://github.com/marq24/ha-tibber-pulse-local/blob/f23fdf9c04050ab39af0340aabba54ecc65b44c9/custom_components/tibber_local/tibber_client.py) |
| SML-Dekodierung | [SmlLib](https://github.com/spacemanspiff2007/SmlLib), [PyPI 1.7](https://pypi.org/project/smllib/1.7/) |
| Compose-Projekte in Synology Container Manager | [Synology-Hilfe](https://kb.synology.com/de-de/DSM/help/ContainerManager/docker_project?version=7) |
| SQLite WAL und konsistente Sicherung | [WAL](https://sqlite.org/wal.html), [Backup-API](https://sqlite.org/backup.html) |
| MQTT-Broker | [Mosquitto-Handbuch](https://mosquitto.org/man/mosquitto-conf-5.html), [Docker-Image](https://github.com/docker-library/official-images/blob/master/library/eclipse-mosquitto) (Tag 2.0.22, amd64/arm64) |
| Umgebungsvariablen in Compose | [Docker Compose](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/) |

## Sicherheit und Tests

| Thema | Quelle |
|---|---|
| Verschlüsselung der Zugangsdaten | [cryptography/Fernet](https://cryptography.io/en/latest/fernet/) |
| Passwort-Hash | [hashlib.scrypt](https://docs.python.org/3/library/hashlib.html#hashlib.scrypt) |
| Mailversand mit TLS | [smtplib](https://docs.python.org/3/library/smtplib.html), [ssl](https://docs.python.org/3/library/ssl.html#ssl.create_default_context) |
| Oberflächentests | [jsdom](https://github.com/jsdom/jsdom) |

## Preise, Strommix und Vergleichswerte

- **Tibber:** [GraphQL-API](https://developer.tibber.com/api/reference.md). Kilowatch nutzt `priceInfo(resolution: QUARTER_HOURLY)` für heute und morgen und `priceInfoRange` (höchstens 672 Viertelstunden je Abfrage) für den Rückblick. `total` enthält laut Referenz Energie und Abgaben samt MwSt (in Schweden auch Energiesteuer); alles darüber, etwa das Netzentgelt in Norwegen, trägst du als Aufschlag ein.
- **Börsenpreise:** [Energy-Charts](https://api.energy-charts.info/) (`price?bzn=…`, Day-Ahead in EUR/MWh; Fraunhofer ISE, Bundesnetzagentur | SMARD.de, CC BY 4.0). Es werden nur Euro-Gebotszonen angeboten. Für die Vorschau und die Tarifsimulation nutzt Kilowatch die [aWATTar/tado°-API](https://energy.tado.com/services/api) (Netto-Börsenwerte mit Millisekunden-Zeitstempeln). Daraus entstehen nie Vertragspreise.
- **Strommix und CO₂:** [Energy-Charts](https://api.energy-charts.info/), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), Quellenangabe „Energy-Charts.info“ in der Oberfläche. `co2eq` liefert g CO₂-Äquivalent je kWh und Viertelstunde mit etwa 8 bis 12 Stunden Verzögerung. Die mitgelieferte Prognosereihe wird nicht verwendet, weil sie am Übergang teils um ein Vielfaches springt. Die Werte passen zu Lebenszyklus-Faktoren (inklusive Vorketten), nicht zu reinen Verbrennungsemissionen, und gelten deshalb als Schätzung der Quelle. `public_power` liefert den Anteil erneuerbarer Erzeugung an der Last. Einspeisung wird nicht gegengerechnet.
- **Vergleichshaushalte:** [Stromspiegel für Deutschland (co2online), Stand 13.05.2025](https://www.stromspiegel.de/stromverbrauch-verstehen/stromverbrauch-im-haushalt/). Für NL, NO und SE fand sich keine vergleichbare Quelle nach Haushaltsgröße; die Oberfläche weist darauf hin.

<details><summary>Jahresverbrauch typischer Haushalte in kWh (Stromspiegel)</summary>

| Personen | Wohnung | Wohnung, Warmwasser elektrisch | Haus | Haus, Warmwasser elektrisch |
|---|---|---|---|---|
| 1 | 1.200 | 1.600 | 1.800 | 2.100 |
| 2 | 1.900 | 2.500 | 2.700 | 3.200 |
| 3 | 2.400 | 3.500 | 3.500 | 4.100 |
| 4 | 2.600 | 4.000 | 3.800 | 4.700 |
| 5 | 3.100 | 5.000 | 4.500 | 6.000 |

Elektrische Heizung, Wärmepumpe und E-Auto sind nicht enthalten. Mit eigener PV liegt der gemessene Netzbezug niedriger.
</details>

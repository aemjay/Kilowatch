# Kilowatch

**Lokale Stromanalyse auf einem Synology-NAS (oder jedem Docker-Host) – mit Tibber Pulse IR, ohne Tibber-Stromtarif.**

Kilowatch liest die vorhandene Bridge im Heimnetz aus und speichert Messwerte und Auswertungen auf dem NAS. Die Adresse kann eine **IPv4-Adresse oder ein FQDN** wie `tibber-bridge.fritz.box` sein. DHCP kann aktiviert bleiben: Der Name wird bei neuen HTTP-Abrufen erneut aufgelöst. Der Beispielname muss im eigenen Router tatsächlich existieren.

**Keine persönliche Adresse und keine Zugangsdaten sind vorbelegt.** Beim ersten Öffnen führt ein Assistent durch die Einrichtung. Bridge-Adresse, Benutzer, Passwort und Benachrichtigungen bleiben später in der Oberfläche änderbar. Passwörter und Gateway-Token werden lokal verschlüsselt gespeichert; das App-Passwort als gesalzener Hash. Nach einem Neustart ist keine erneute Eingabe der Bridge-Zugangsdaten nötig.

Für die laufende Messung braucht die Anwendung keine Tibber-API, kein Tibber-Konto und keine Internetverbindung. Installation, Updates und optionaler E-Mail-/Signal-Versand benötigen Internet. Lokales Auslesen beendet einen eventuell bestehenden Cloud-Upload der Bridge nicht automatisch.

Voraussetzungen: ein Synology-NAS mit **Container Manager** (DSM 7.2 oder neuer) oder ein anderer Docker-Host mit Docker Compose, eine Tibber Pulse IR mit Bridge im selben Heimnetz und ein Zähler, der SML oder lesbare OBIS-Werte über die optische Schnittstelle ausgibt. Unterstützt werden **linux/amd64** (Intel/AMD) und **linux/arm64**; die Plattform wird bei der Einrichtung gewählt oder automatisch vom Host übernommen. Für die App sind 512 MiB RAM als Obergrenze konfiguriert; der tatsächliche Bedarf hängt von Datenmenge und Ansichten ab. Das Zählermodell muss nicht ausgewählt werden; maßgeblich ist das tatsächlich gelieferte Telegramm.

## Funktionen

| Bereich | Enthalten |
|---|---|
| Einrichtung | Lokale Subnetzsuche, Assistent, eigenes App-Passwort, Bridge per FQDN oder IP, Zugangsdaten später ändern |
| Live | Netzleistung mit Vorzeichen, Bezug, Einspeisung, Aktualität und Empfangsdiagnose |
| Verlauf | Tag, Woche, Monat, Jahr, eigener Zeitraum, Vorperioden und Messlücken |
| Analyse | Stunden-Heatmap, Tagesprofile, Nachtgrundlast, Lastdauerlinie, Spitzen und Monatsprognose |
| Kosten | Einzeltarif oder HT/NT nach Uhrzeit, Tarifwechsel, Grundpreis, Einspeisevergütung, dynamische Bruttopreise per CSV, optionale Börsenpreisvorschau |
| Benachrichtigungen | E-Mail über eigenen SMTP-Server; optional Signal über lokal gekoppelten Zusatzcontainer |
| Alarmregeln | Fehlende Daten, anhaltend hohe Last, Tagesbudget, niedrige Batteriespannung und knapper Datenspeicher |
| Versand | Ruhezeiten, Entwarnungen, Mindestabstand, persistente Warteschlange, begrenzte Wiederholungen und Zustellverlauf |
| Berichte | Druckansicht, PDF über Browserdruck, CSV/JSON-Export und lokale HTTP-API |
| Betrieb | Wiederanlauf, Aufbewahrung, konsistente SQLite-Sicherungen, Restore und lokale Passwort-Wiederherstellung |

Die Oberfläche liefert JavaScript, SVG und Schriften lokal aus. Server: Python/FastAPI, Datenbank: SQLite mit WAL. Es gibt keinen Node-Build auf dem NAS. Mosquitto und Signal sind getrennte, optionale Container.

![Dashboard mit ausschließlich künstlichen Beispieldaten im Demo-Modus](docs/vorschau.png)

## Auf dem NAS starten

Ausführlich: **[Installation auf der Synology](docs/INSTALLATION-SYNOLOGY.md)**.

1. Vollständiges Projekt nach beispielsweise `/volume1/docker/kilowatch` kopieren.
2. Optional per SSH im Projektordner `python3 tools/setup.py` ausführen: fragt HTTP-Port und Plattform ab (`auto`, `amd64` oder `arm64`) und schreibt eine `.env`. Ohne `.env` gelten Port 8088 und die Plattform des NAS.
3. Container Manager → **Projekt → Erstellen**, Projektpfad auswählen, **`compose.yaml`** verwenden und bauen/starten.
4. Container-Protokoll öffnen und den einmaligen **Setup-Code** ablesen.
5. `http://<NAS-FQDN>:8088` öffnen, Setup-Code eingeben und eigenes App-Passwort festlegen.
6. Bridge-FQDN oder aktuelle IP sowie das Bridge-Passwort (Kennung vom Aufkleber, Format `ABCD-EFGH`) eingeben, **Verbindung prüfen**, dann **Bridge speichern und starten**. Node 1 ist der übliche Ausgangspunkt.
7. Unter **Kosten & Tarife** einen Preis oder zwei HT/NT-Preise mit Zeiten hinterlegen. Unter **Benachrichtigungen** gewünschte Kanäle einrichten und gezielt eine Testnachricht senden.

Mit SSH im Projektordner:

```sh
docker compose -f compose.yaml up -d --build
docker compose -f compose.yaml logs --tail=50 kilowatch
```

Die optionale `.env.example` enthält ausschließlich Betriebsoptionen wie HTTP-Port und Plattform. Adressen und persönliche Zugangsdaten werden in der Oberfläche eingegeben. Messdaten und tägliche Sicherungen liegen im Ordner **`data/`** des Projekts und werden so von Hyper Backup mitgesichert. Zugangsdaten liegen bewusst getrennt im Docker-Volume **`kilowatch-secrets`**, damit Schlüssel und verschlüsselte Passwörter nie gemeinsam in einer Sicherung landen ([Details](docs/BETRIEB.md#speicherorte)). `docker compose down -v` löscht dieses Volume und ist kein normaler Update-Schritt.

## Vorgebautes NAS-Image

Der [GitHub-Workflow](.github/workflows/nas-image.yml) prüft Tests und Compose-Konfigurationen und baut anschließend Images für amd64 und arm64. Er prüft den echten Containerstart ohne vorkonfigurierte Zugangsdaten, Einrichtung, Dateirechte, API, Sicherung, Persistenz nach Neustart und den optionalen MQTT-Broker.

Nach einem erfolgreichen Lauf stehen die Artefakte **`kilowatch-nas-amd64`** und **`kilowatch-nas-arm64`** mit **`kilowatch-1.0.0-<plattform>.tar.gz`** und SHA256-Prüfsumme 30 Tage bereit; das zur NAS-CPU passende wählen. Nach dem Import im Container Manager **`compose.prebuilt.yaml`** verwenden. Beide Varianten nutzen dasselbe Datenvolume und dürfen nicht gleichzeitig als zwei App-Instanzen laufen. Kein Registry-Login erforderlich.

## E-Mail und Signal

**[Einrichtung und Grenzen der Benachrichtigungen](docs/BENACHRICHTIGUNGEN.md)**.

E-Mail verwendet den eigenen SMTP-Server mit STARTTLS oder direktem TLS und Zertifikatsprüfung. Signal verwendet optional `signal-cli-rest-api` als Community-Anbindung. Der Gateway-Port wird nicht ins LAN veröffentlicht; die App zeigt den Kopplungs-QR nach Anmeldung an. Beide Kanäle sind zunächst ausgeschaltet. Erst die eigene Konfiguration und ein erfolgreicher Test bestätigen den Versand vor Ort.

Weitere sinnvolle Schutzfunktionen sind bereits enthalten: keine Nullwerte bei Messausfällen, Überwachung der Datenaktualität, Alarmberuhigung durch Ruhezeiten und Entwarnungen, Aufbewahrungsgrenzen und Wiederherstellung bei vergessenem App-Passwort. Ein komplett ausgeschaltetes NAS kann selbst keine Ausfallnachricht versenden; dafür wäre ein zusätzlicher unabhängiger Monitor nötig.

## Datenqualität und Unabhängigkeit

Zählerstandsdifferenzen haben Vorrang vor Wattintegration. Fehlende Messdaten sind kein Nullverbrauch. Während längerer Ausfälle bekannte Energie bleibt als Gesamtmenge erhalten und wird nicht auf erfundene Stundenwerte verteilt. Einzelne Geräte, PV-Eigenverbrauch und Autarkie lassen sich aus der Netzanschlussmessung allein nicht bestimmen. Prognosen sind offengelegte Schätzungen. Details: **[Datenmodell](docs/DATENMODELL.md)**.

| Daten | Standardaufbewahrung |
|---|---|
| Einzelmessungen | 90 Tage, einstellbar, 0 = unbegrenzt |
| Minutenwerte | 1095 Tage, einstellbar, 0 = unbegrenzt |
| Viertelstunden und Lücken | dauerhaft |
| Erfassungshinweise | 365 Tage |
| Nachrichtenverlauf | 90 Tage, Oberfläche zeigt letzte 100 Einträge |
| Automatische Datenbanksicherungen | letzte sieben Dateien, täglich UTC |

Die Historie beginnt mit der ersten Erfassung; ein Cloud-Historienimport ist nicht implementiert. Bridge-Firmware und Zähler unterscheiden sich; nach der Einrichtung den Tagesverbrauch einmal mit dem Zählerstand abgleichen. Ein vollständiger Cloud-Ausstieg ist optional und sollte schrittweise geprüft werden. **[Bridge und optionaler MQTT-Betrieb](docs/BRIDGE.md)** beschreibt die gesonderte Umstellung ohne Vorgabe einer festen IP.

## Dokumentation und Entwicklung

- [Betrieb, Zugangsdaten, Backup, Restore und Updates](docs/BETRIEB.md)
- [Eigener Strompreis, HT/NT und optionale Börsenpreise](docs/TARIFE.md)
- [Bridge im lokalen Subnetz suchen](docs/GERAETESUCHE.md)
- [API und Preis-CSV](docs/API.md)
- [Testabdeckung und Abnahme](docs/PRUEFPROTOKOLL.md)
- [Quellen](docs/QUELLEN.md)

```sh
python -m venv .venv
# Linux/macOS: . .venv/bin/activate
# Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest
# Optional auf dem Entwicklungsrechner: Formularabläufe (Node 24+)
npm ci --ignore-scripts
npm test
```

Zum lokalen Start `DATA_DIR` auf ein beschreibbares Verzeichnis setzen, optional `DEMO_MODE=true`, anschließend:

```sh
python -m uvicorn app.main:factory --factory --host 127.0.0.1 --port 8088
```

Auch im Demo-Modus ein eigenes App-Passwort über den Setup-Code einrichten. Demo-Daten liegen unter `DATA_DIR/demo`, echte Daten unter `DATA_DIR/live`. Der Demo-Modus kontaktiert weder Bridge noch Nachrichtenkanäle. Persönliche Daten, Telegramme, Kennungen und lokale Schlüssel gehören nicht ins Repository.

Lizenz: **GPL-3.0-or-later**, siehe [LICENSE](LICENSE) und [THIRD-PARTY.md](THIRD-PARTY.md). Eigenständiges Community-Projekt.

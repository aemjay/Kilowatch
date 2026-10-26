# ⚡ Kilowatch

> **English:** Kilowatch is a self-hosted energy monitor for the Tibber Pulse IR. It reads the Bridge in your home network and keeps all readings on your own server or NAS – no Tibber account or cloud needed for measuring. The interface comes in English, Norsk bokmål, Svenska, Nederlands and Deutsch, with light and dark themes. The documentation is in German.

**Lokale Stromanalyse mit der Tibber Pulse IR – auf jedem Docker-Host oder NAS, ohne Tibber-Stromtarif.**

Kilowatch liest die Bridge in deinem Heimnetz aus und speichert Messwerte und Auswertungen bei dir zu Hause. Für die Messung brauchst du weder Tibber-Konto noch Internet.

![Dashboard mit Beispieldaten im Demo-Modus](docs/vorschau.png)

## Das kann Kilowatch

- 📈 **Verlauf und Live-Werte:** Netzleistung, Bezug und Einspeisung von den letzten 5 Minuten bis zum Jahr. Zeitbalken zum Zoomen, Tooltips und Messlücken ([Bedienung](docs/BEDIENUNG.md)).
- 🔎 **Analyse:** Stundenmuster, Nachtgrundlast, Lastdauerlinie, Monatsprognose und Vergleich mit typischen Haushalten.
- 💶 **Kosten:** Fest-, HT/NT- und dynamische Tarife. Dynamische Preise holt Kilowatch automatisch von Tibber oder als Börsenpreis plus Aufschlag. Dazu Tarifsimulation, Monatsbudget und Abschlag ([Tarife](docs/TARIFE.md)).
- 🌱 **CO₂-Bilanz:** Optional für DE, NL, NO und SE aus dem Strommix des Netzes.
- 🔔 **E-Mail-Alarme:** Messausfall, hohe Dauerlast, Budget, Batterie, Speicher ([Benachrichtigungen](docs/BENACHRICHTIGUNGEN.md)).
- 📱 **Als App installierbar** (PWA, mit HTTPS), in fünf Sprachen, hell und dunkel.
- 🛡️ **Robust:** Sicherungen, Wiederherstellung, signierte Images und Updates mit automatischem Rollback.

## Voraussetzungen

- Docker mit Compose auf `linux/amd64` oder `linux/arm64` (Synology: Container Manager, DSM 7.2 oder neuer)
- Tibber Pulse IR mit Bridge im selben Heimnetz und ein Zähler mit SML oder lesbaren OBIS-Werten
- 512 MiB Arbeitsspeicher für die App

## Installieren

```sh
curl -fsSLO https://github.com/aemjay/Kilowatch/releases/latest/download/update.sh
sudo sh update.sh --user <benutzer> --dir /pfad/zu/kilowatch
```

Danach `http://<Host>:8088` öffnen, Setup-Code eingeben (das Skript zeigt ihn an) und die Bridge verbinden. Alle Schritte, Synology und HTTPS: **[Installation](docs/INSTALLATION.md)**.

## Aktualisieren

```sh
sudo sh <projektordner>/tools/update.sh
```

Dasselbe Skript prüft die Signatur, startet nur bei einer neuen Version neu und rollt automatisch zurück, wenn diese nicht gesund startet. Mehr: **[Updates](docs/UPDATES.md)**.

## Datenschutz und Grenzen

- Zugangsdaten gibst du nur im Browser ein. Sie liegen verschlüsselt in einem eigenen Docker-Volume, getrennt von den Messdaten ([Betrieb](docs/BETRIEB.md#speicherorte)).
- Ins Internet gehen nur optionale Abrufe: Preise (Tibber, Energy-Charts), Strommix, E-Mail und der Update-Hinweis. Messwerte verlassen dein Heimnetz nie.
- Ein bestehender Cloud-Upload der Bridge bleibt aktiv, bis du ihn selbst abschaltest ([Bridge](docs/BRIDGE.md)).
- Gemessen wird am Netzanschluss. Einzelne Geräte, PV-Eigenverbrauch und Autarkie lassen sich daraus nicht bestimmen, Prognosen sind Schätzungen ([Datenmodell](docs/DATENMODELL.md)).
- Sicherheitslücken bitte vertraulich melden: [SECURITY.md](SECURITY.md).

## Dokumentation

| Thema | Seite |
|---|---|
| Installieren, HTTPS, App-Installation, Synology | [Installation](docs/INSTALLATION.md) |
| Updates, Versionen, Rückweg | [Updates](docs/UPDATES.md) |
| Diagramme, Zoom, Sprache und Währung | [Bedienung](docs/BEDIENUNG.md) |
| Sicherung, Wiederherstellung, Passwort vergessen | [Betrieb](docs/BETRIEB.md) |
| Strompreis, HT/NT, dynamische Tarife | [Tarife](docs/TARIFE.md) |
| E-Mail-Alarme | [Benachrichtigungen](docs/BENACHRICHTIGUNGEN.md) |
| Bridge, Gerätesuche, MQTT, Cloud-Ausstieg | [Bridge](docs/BRIDGE.md) |
| Rechenregeln und Datenbank | [Datenmodell](docs/DATENMODELL.md) |
| HTTP-API und Preis-CSV | [API](docs/API.md) |
| Tests und Abnahme | [Prüfprotokoll](docs/PRUEFPROTOKOLL.md) |
| Quellen und Lizenzen | [Quellen](docs/QUELLEN.md), [Drittkomponenten](THIRD-PARTY.md) |

## Entwickeln

```sh
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest                                # Oberflächentests (Node 24+): npm ci --ignore-scripts && npm test
DATA_DIR=/tmp/kilowatch DEMO_MODE=true python -m uvicorn app.main:factory --factory --host 127.0.0.1 --port 8088
```

Der Demo-Modus nutzt künstliche Daten und kontaktiert weder Bridge noch Mail. Auch dort legst du über den Setup-Code ein eigenes Passwort fest. Persönliche Daten, Telegramme und Schlüssel gehören nicht ins Repository.

Lizenz: **GPL-3.0-or-later**, siehe [LICENSE](LICENSE). Unabhängiges Community-Projekt.

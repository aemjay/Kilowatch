# Kilowatch

> **English:** Kilowatch is a self-hosted energy monitor for the Tibber Pulse IR. It reads the Bridge in your home network and keeps all readings on your own server or NAS, with no Tibber account or cloud needed for measuring. The interface is available in English, Norsk bokmål, Svenska, Nederlands and Deutsch, with light and dark themes. The documentation is in German for now.

**Lokale Stromanalyse mit der Tibber Pulse IR – auf jedem Docker-Host oder Synology-NAS, ohne Tibber-Stromtarif.**

Kilowatch liest die vorhandene Bridge im Heimnetz aus und speichert Messwerte und Auswertungen lokal. Die Bridge-Adresse ist eine IPv4-Adresse oder ein Gerätename deines Routers; bei DHCP wird der Name bei neuen Abrufen erneut aufgelöst.

**Keine persönliche Adresse und keine Zugangsdaten sind vorbelegt.** Beim ersten Öffnen führt ein Assistent durch die Einrichtung. Passwörter und Token werden lokal verschlüsselt gespeichert, das App-Passwort als gesalzener Hash. Nach einem Neustart ist keine erneute Eingabe nötig.

Für die laufende Messung braucht die Anwendung keine Tibber-API, kein Tibber-Konto und keine Internetverbindung. Installation, Updates, E-Mail-Versand und die optionalen Abrufe von Strommix und dynamischen Preisen brauchen Internet. Dabei gehen nur Land, Zeitraum bzw. die Preisabfrage hinaus, keine Messwerte. Lokales Auslesen beendet einen eventuell bestehenden Cloud-Upload der Bridge nicht automatisch.

**Voraussetzungen:** ein Docker-Host mit Docker Compose (Synology: Container Manager, DSM 7.2 oder neuer) auf `linux/amd64` oder `linux/arm64`, eine Tibber Pulse IR mit Bridge im selben Heimnetz und ein Zähler mit SML oder lesbaren OBIS-Werten. Das Zählermodell muss nicht gewählt werden; maßgeblich ist das gelieferte Telegramm. Für die App sind 512 MiB RAM als Obergrenze konfiguriert.

## Funktionen

| Bereich | Enthalten |
|---|---|
| Einrichtung | Lokale Subnetzsuche, Assistent, eigenes App-Passwort, Bridge per Gerätename oder IP, Zugangsdaten später ändern |
| Live | Netzleistung mit Vorzeichen, Bezug, Einspeisung, Aktualität und Empfangsdiagnose |
| Verlauf | Letzte Stunde (Einzelwerte im Abfrageintervall), letzte 6 Stunden (Minutenwerte), Tag, Woche, Monat, Jahr, eigener Zeitraum, Vorperioden und Messlücken |
| Analyse | Stunden-Heatmap, Tagesprofile, Nachtgrundlast und deren Entwicklung samt Kosten pro Jahr, Lastdauerlinie, Spitzen, Einspeiseprofil und Monatsprognose |
| Kosten | Einzeltarif oder HT/NT nach Uhrzeit, Tarifwechsel, Grundpreis, Einspeisevergütung, dynamische Preise automatisch von Tibber oder als Börsenpreis + Aufschlag (oder per CSV), Tarifsimulation (Fest, HT/NT, Börsenpreis + Aufschlag), Monatsbudget und Abschlags-Hochrechnung, optionale Börsenpreise |
| Vergleichswerte | Optional: typischer Haushalt gleicher Größe (Personen, Wohnung oder Haus, Warmwasser) als Referenzlinie in Tages- und Monatsbalken, im Zeitraumvergleich, beim Monatsziel und in der Jahreshochrechnung (Stromspiegel für Deutschland) |
| Strommix und CO₂ | Optional für Deutschland, Niederlande, Norwegen und Schweden: CO₂-Bilanz des Netzbezugs aus gemessener Netzintensität je Viertelstunde, Ökostromanteil im Netz und aktueller Wert (Quelle: Energy-Charts.info, Fraunhofer ISE, CC BY 4.0) |
| Benachrichtigungen | E-Mail über eigenen SMTP-Server |
| Alarmregeln | Fehlende Daten, anhaltend hohe Last, Tagesbudget, Monatsbudget, niedrige Batteriespannung und knapper Datenspeicher |
| Versand | Ruhezeiten, Entwarnungen, Mindestabstand, persistente Warteschlange, begrenzte Wiederholungen und Zustellverlauf |
| Berichte | Druckansicht, PDF über Browserdruck, CSV/JSON-Export und lokale HTTP-API |
| Oberfläche | Deutsch, English, Norsk bokmål, Svenska, Nederlands; helles, dunkles oder automatisches Farbschema; Währungszeichen € (ct), NOK (øre) oder SEK (öre) |
| Betrieb | Wiederanlauf, Aufbewahrung, konsistente SQLite-Sicherungen, Restore, lokale Passwort-Wiederherstellung, optionaler Update-Hinweis und Datenbank-Migrationen mit automatischer Vorab-Sicherung |

Die Oberfläche liefert JavaScript, SVG und Schriften lokal aus. Server: Python/FastAPI, Datenbank: SQLite mit WAL. Es gibt keinen Node-Build im Image. Mosquitto ist ein getrennter, optionaler Container.

![Dashboard mit ausschließlich künstlichen Beispieldaten im Demo-Modus](docs/vorschau.png)

## Installation und Update

```sh
# 1. Skript holen
curl -fsSLO https://github.com/aemjay/Kilowatch/releases/latest/download/update.sh
# 2. Installieren (legt Ordner, Daten und Konfiguration an, prüft die Signatur, startet)
sudo sh update.sh --user <benutzer> --dir /pfad/zu/kilowatch
# 3. Im Browser http://<Host>:8088 öffnen, Setup-Code eingeben, Bridge verbinden
```

Das Skript gibt Adresse und Setup-Code aus. Alle Schritte, die Einrichtung im Browser, Synology (Aufgabenplaner, Container Manager) und HTTPS: **[Installation](docs/INSTALLATION.md)**.

**Update** – derselbe Befehl, immer:

```sh
sudo sh <projektordner>/tools/update.sh
```

Das Skript prüft die Image-Signatur, startet nur bei neuer Version neu und rollt automatisch zurück, wenn die neue Version nicht gesund startet. Kilowatch aktualisiert sich nie selbst und braucht keinen Docker-Zugriff; die App zeigt auf Wunsch nur einen Hinweis auf neue Versionen (standardmäßig aus). Automatisches Update per Aufgabenplaner oder cron, Offline-Weg und Rückweg: **[Updates](docs/UPDATES.md)**.

Releases erscheinen als signierte Multi-Arch-Images unter `ghcr.io/aemjay/kilowatch`; `compose.yaml` folgt standardmäßig der neuesten 1.x-Version. Messdaten und tägliche Sicherungen liegen im Ordner `data/` des Projekts. Zugangsdaten liegen bewusst getrennt im Docker-Volume `kilowatch-secrets`, damit Schlüssel und verschlüsselte Passwörter nie gemeinsam in einer Sicherung landen ([Details](docs/BETRIEB.md#speicherorte)). `docker compose down -v` löscht dieses Volume und ist kein Update-Schritt.

Empfohlen ist der Zugriff per HTTPS über einen Reverse-Proxy ([Anleitung](docs/INSTALLATION.md#https-über-einen-reverse-proxy)); mit HTTPS lässt sich Kilowatch auch als App installieren ([PWA](docs/INSTALLATION.md#als-app-installieren-pwa)). Sicherheitslücken bitte vertraulich melden ([SECURITY.md](SECURITY.md)).

## E-Mail-Benachrichtigungen

**[Einrichtung und Grenzen der Benachrichtigungen](docs/BENACHRICHTIGUNGEN.md)**.

E-Mail verwendet den eigenen SMTP-Server mit STARTTLS oder direktem TLS und Zertifikatsprüfung, einstellbarem Absendernamen und optionalem Erkennungswort im Betreff. Der Versand ist zunächst ausgeschaltet. Erst die eigene Konfiguration und ein erfolgreicher Test bestätigen den Versand vor Ort.

Weitere sinnvolle Schutzfunktionen sind bereits enthalten: keine Nullwerte bei Messausfällen, Überwachung der Datenaktualität, Alarmberuhigung durch Ruhezeiten und Entwarnungen, Aufbewahrungsgrenzen und Wiederherstellung bei vergessenem App-Passwort. Ein komplett ausgeschalteter Host kann selbst keine Ausfallnachricht versenden; dafür wäre ein zusätzlicher unabhängiger Monitor nötig.

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

- [Installation](docs/INSTALLATION.md) und [Updates](docs/UPDATES.md)
- [Betrieb, Zugangsdaten, Backup und Restore](docs/BETRIEB.md)
- [Eigener Strompreis, HT/NT und dynamische Preise](docs/TARIFE.md)
- [Bridge, Gerätesuche und optionaler MQTT-Betrieb](docs/BRIDGE.md)
- [API und Preis-CSV](docs/API.md)
- [Testabdeckung und Abnahme](docs/PRUEFPROTOKOLL.md)
- [Übersetzungen prüfen und ergänzen](docs/UEBERSETZUNG.md)
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

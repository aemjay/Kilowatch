# Installation

In etwa zehn Minuten von null zur laufenden Messung. Läuft auf jedem Docker-Host mit Docker Compose; Synology-Besonderheiten stehen im [eigenen Abschnitt](#synology-container-manager-und-dsm).

**Voraussetzungen**

- Docker mit Compose-Plugin (Synology: **Container Manager**, DSM 7.2 oder neuer) auf `linux/amd64` oder `linux/arm64`. 32-Bit-ARM wird nicht unterstützt.
- Eine Tibber Pulse IR mit Bridge im selben Heimnetz, ein Zähler mit SML oder lesbaren OBIS-Werten.
- Internet für die Installation (Image-Download, Signaturprüfung). Der laufende Betrieb braucht keins; [NAS ohne Internet](#ohne-internet).
- Ein Ordner auf einem lokalen Volume. Keine aktive Datenbank auf SMB/NFS.

**Keine Zugangsdaten in Dateien eintragen.** Bridge-, Mail- und App-Passwörter werden nur im Browser eingegeben.

## 1. Installieren

Ein Skript erledigt alles: `update.sh` dient zur Erstinstallation und zu jedem späteren Update.

```sh
curl -fsSLO https://github.com/aemjay/Kilowatch/releases/latest/download/update.sh
less update.sh        # optional: Skript ansehen
sudo sh update.sh --user <benutzer> --dir /pfad/zu/kilowatch
```

Das Skript

1. legt Projektordner und `data/` an und übergibt `data/` an `<benutzer>`, unter dem Kilowatch dann ohne Root-Rechte läuft,
2. lädt `compose.yaml` und `.env.example` aus dem Release und legt die `.env` an, falls es keine gibt,
3. prüft die Signatur des Images und lädt genau das geprüfte Image,
4. startet Kilowatch, wartet auf den Healthcheck und
5. gibt Adresse und Setup-Code aus.

Optionen: `--user NAME` (Eigentümer der Daten, kein root), `--dir PFAD` (Projektordner; Standard: der Ordner des Skripts, bei der Erstinstallation `/volume1/docker/kilowatch` auf Synology, sonst `/opt/kilowatch`), `--port 8088` (HTTP-Port), `--version 1.3.0` (feste Version statt neuester 1.x; `latest` hebt die Festlegung auf), `--no-start` (nur vorbereiten), `--source PFAD` (Release-Dateien aus einem lokalen Ordner, siehe [Ohne Internet](#ohne-internet)), `-h`. Der Ablauf bei bestehenden Installationen steht in [Updates](UPDATES.md).

Wer lieber ohne Skript arbeitet: `compose.yaml` vom Release laden, im Projektordner selbst den Ordner `data` anlegen und `docker compose up -d` ausführen. Der Setup-Code steht dann in `data/SETUP-CODE.txt`.

### Warum gehört `data` dem eigenen Benutzer?

Kilowatch läuft automatisch unter dem Eigentümer von `data/`. Legt der Container den Ordner selbst an, gehört er root, und Kilowatch weicht auf eine interne Benutzer-ID aus, die auf manchen Systemen (zum Beispiel mit Synology-ACL) nicht schreiben darf. Dann bricht der Start mit „Kilowatch kann nicht in /data schreiben …“ ab: Container stoppen, den leeren Ordner `data` löschen, selbst neu anlegen (oder das Skript mit `--user` erneut ausführen), starten. Ein bestimmter anderer Benutzer lässt sich über `PUID`/`PGID` in der `.env` festlegen.

## 2. Im Browser einrichten

1. `http://<Adresse-des-Hosts>:8088` öffnen. Setup-Code aus `data/SETUP-CODE.txt` (oder dem Container-Protokoll) eingeben und ein eigenes App-Passwort mit mindestens zwölf Zeichen festlegen. Es gibt kein Standardpasswort. Der Code verfällt nach der Einrichtung; bei einem Neustart davor wird ein neuer ausgegeben.

   ![Ersteinrichtung: Setup-Code und eigenes App-Passwort](bilder/installation-setup-code.png)

2. Bridge verbinden:

   | Feld | Eingabe |
   |---|---|
   | Bridge-Adresse | Gerätename aus dem Router oder IPv4-Adresse, ohne `http://`, Port und Pfad |
   | Bridge-Passwort | Kennung vom Bridge-Aufkleber, Format `ABCD-EFGH` |
   | Node-ID | meist 1; bei mehreren gekoppelten Pulse-Geräten die passende |

   Wer die Adresse nicht kennt, nutzt **Einstellungen → Bridge im Heimnetz suchen** ([Beschreibung](BRIDGE.md#bridge-im-heimnetz-suchen)).

   ![Bridge verbinden](bilder/installation-bridge.png)

3. **Verbindung prüfen** liest nur und zeigt die aufgelöste Adresse und das erkannte Protokoll. Erst **Bridge speichern und starten** übernimmt die Eingaben für die Erfassung.

Die Eingaben bleiben nach einem Neustart erhalten und lassen sich unter **Einstellungen** ändern. Ein leeres Passwortfeld behält ein gespeichertes Passwort. **Gespeichertes Bridge-Passwort entfernen** löscht es und pausiert die Erfassung; die Historie bleibt.

Danach unter **Kosten & Tarife** den eigenen Bruttopreis eintragen ([Tarife](TARIFE.md)) und unter **Benachrichtigungen** E-Mail einrichten ([Benachrichtigungen](BENACHRICHTIGUNGEN.md)). Die Historie beginnt mit der ersten erfolgreichen Erfassung. Ein Docker-Status `healthy` prüft Webserver und Datenbank, nicht den Empfang der Bridge.

## Gerätename statt fester IP

DHCP kann für Host und Bridge eingeschaltet bleiben. Im Router den tatsächlichen Gerätenamen der Bridge nachsehen oder einen eindeutigen Namen vergeben. Kilowatch legt keine DNS-Einträge an. Entscheidend ist, dass der DNS des Routers den Namen auf die aktuelle Adresse abbildet und der Container diesen DNS benutzen kann. Kilowatch löst den Namen bei neuen Abrufen erneut auf und hält keine alte Verbindung dauerhaft offen; wie schnell ein Adresswechsel ankommt, hängt von DNS-Caches und TTLs des Routers ab. Bei Auflösungsfehlern bleibt die Historie erhalten und die App versucht es erneut.

Schlägt die Auflösung nur im Container fehl, DNS von Host und Docker-Netzwerk prüfen. `.local`/mDNS funktioniert nicht in jeder Docker-Konfiguration; ein normaler Heimnetz-DNS-Name ist verlässlicher. Es werden lokale IPv4-Ziele unterstützt; öffentliche Ziele und gemischte öffentliche/private DNS-Antworten werden abgelehnt.

## Netzwerk und Ressourcen

- Oberfläche: TCP 8088 im Heimnetz (Firewall passend zur LAN-Quelle). Erfassung: Host → Bridge, TCP 80. Keine Portweiterleitung aus dem Internet; für den Zugriff von unterwegs ein VPN verwenden.
- Empfohlen ist HTTPS über einen Reverse-Proxy (nächster Abschnitt). Über direktes HTTP gehen App-Passwort und Sitzungscookie unverschlüsselt durchs Netz.
- Die Bridge spricht nur HTTP mit Basic Auth, das kann Kilowatch nicht ändern. Bridge und Host gehören in dasselbe vertrauenswürdige LAN oder in ein IoT-Segment, das nur der Host erreicht.
- Optionaler MQTT-Broker: die Bridge-Firmware braucht anonyme Verbindungen. Port 1883 **nur für die Bridge** freigeben ([Bridge](BRIDGE.md)).
- Limits: 512 MiB RAM für die App, optional 64 MiB für Mosquitto. Kein CPU-Limit, weil Synology-Kernel keine CFS-Quota unterstützen (`cpus` bricht dort den Start ab). Kein eigener Logtreiber, damit das Protokoll in der Verwaltungsoberfläche sichtbar bleibt.
- Mehrere GB Reserve vorsehen: sieben vollständige Datenbanksicherungen brauchen deutlich mehr Platz als die Datenbank allein. [Speicherorte und Sicherung](BETRIEB.md#speicherorte).

Aktuelle Bridge-Firmware liefert Daten unter `/node_data.json`, ältere unter `/data.json`; Kilowatch probiert beide. Es werden keine Bridge-Parameter verändert.

## HTTPS über einen Reverse-Proxy

Kilowatch spricht selbst nur HTTP. Mit beliebigem Reverse-Proxy (Caddy, nginx, Traefik, DSM):

1. Zertifikat für einen eigenen Namen besorgen, zum Beispiel `kilowatch.example.de`. Ohne Portfreigabe aus dem Internet geht das über DNS-01 (etwa mit [acme.sh](https://github.com/acmesh-official/acme.sh)).
2. Der Name muss im Heimnetz auf den Host zeigen (lokaler DNS-Eintrag im Router; manche Router blockieren das per DNS-Rebind-Schutz, dann dort eine Ausnahme für den Namen eintragen).
3. Proxy von `https://kilowatch.example.de` auf `http://localhost:8088` einrichten.
4. In der `.env` setzen und mit `docker compose up -d` neu starten:

   ```sh
   HTTP_BIND=127.0.0.1   # direkter HTTP-Port nur noch für den Proxy auf dem Host
   COOKIE_SECURE=true    # Sitzungscookie nur über HTTPS
   ```
5. Prüfen: `https://kilowatch.example.de` öffnet die Anmeldung, `http://<Host>:8088` ist aus dem LAN nicht mehr erreichbar. Erst danach HSTS aktivieren.

Hinter dem Proxy sieht Kilowatch alle Anfragen von derselben internen Adresse; die Anmeldebegrenzung gilt dann für alle Clients gemeinsam. Weitergeleitete Adress-Header werden bewusst nicht ausgewertet.

## Ohne Internet

An jedem Release hängen Importdateien `kilowatch-<version>-amd64.tar.gz` und `-arm64.tar.gz` mit Prüfsumme. Die passende zum Prozessor wählen (`uname -m`: `x86_64` = amd64, `aarch64` = arm64).

```sh
docker load -i kilowatch-<version>-<plattform>.tar.gz
docker compose -f compose.yaml up -d --pull never
```

Die Release-Dateien (`compose.yaml`, `update.sh`, `env.example`) lassen sich mit `sh update.sh --source <Ordner>` aus einem lokalen Ordner einspielen. Beide Wege verwenden den Ordner `data/` und das Volume `kilowatch-secrets`. Nur eine App-Instanz darauf betreiben, und nie `docker compose down -v` ausführen: das löscht die gespeicherten Zugangsdaten.

## Synology: Container Manager und DSM

Container Manager (DSM 7.2 oder neuer) und der Aufgabenplaner nehmen die Kommandozeile ab. Das Projekt gehört auf ein lokales Volume, zum Beispiel `/volume1/docker/kilowatch`.

**Ohne SSH – Aufgabenplaner:**

1. Systemsteuerung → **Aufgabenplaner** → Erstellen → Geplante Aufgabe → **Benutzerdefiniertes Skript**.
2. **Allgemein:** Aufgabe `Kilowatch installieren`, Benutzer **root**. **Zeitplan:** „An folgendem Datum ausführen“, ohne Wiederholung.
3. **Aufgabeneinstellungen** (`DEINNAME` durch den DSM-Benutzernamen ersetzen):

   ```sh
   cd /tmp && curl -fsSLO https://github.com/aemjay/Kilowatch/releases/latest/download/update.sh && sh update.sh --user DEINNAME --dir /volume1/docker/kilowatch
   ```

4. Speichern, markieren, **Ausführen**. Nach etwa einer Minute steht der Setup-Code in `docker/kilowatch/data/SETUP-CODE.txt`. Die Aufgabe danach löschen und mit Schritt 2 aus [Im Browser einrichten](#2-im-browser-einrichten) fortfahren.

**Klickweg ohne Skript:** `compose.yaml` vom Release in der File Station nach `docker/kilowatch` hochladen, dort **selbst** den Ordner `data` anlegen, dann Container Manager → **Projekt → Erstellen** (Name `kilowatch`, Pfad `/docker/kilowatch`, vorhandene `compose.yaml`). Der Setup-Code steht in `data/SETUP-CODE.txt`.

**Dateirechte:** Wer `data` in der File Station selbst anlegt, ist Eigentümer und hat laut Synology-ACL Zugriff. Das Skript setzt zusätzlich, soweit möglich, die ACL für `--user`.

**Weiteres:**

- Port 8088 in der DSM-Firewall für das Heimnetz freigeben; MQTT-Port 1883 nur für die Bridge.
- Reverse-Proxy: *Systemsteuerung → Anmeldeportal → Erweitert → Reverse Proxy*, Quelle HTTPS/443 mit dem Hostnamen, Ziel HTTP `localhost:8088`; Zertifikat unter *Sicherheit → Zertifikat → Einstellungen* zuordnen. Let's Encrypt in DSM verlangt Port 80 aus dem Internet, sonst ein per DNS-01 ausgestelltes Zertifikat importieren.
- Importdatei einspielen: Container Manager → **Image → Hinzufügen/Importieren → Aus Datei**; Prozessor unter **Systemsteuerung → Info-Center** nachsehen.
- Hyper Backup sichert `data/`, nicht das Volume mit den Zugangsdaten (Absicht, siehe [Betrieb](BETRIEB.md#speicherorte)).
- Legt der Container Manager die Konfiguration als `docker-compose.yml` ab, den Dateinamen in Befehlen anpassen. Ein vom Skript gestartetes Projekt erscheint unter **Container**.

## Selbst bauen

`compose.build.yaml` statt `compose.yaml` verwenden und im vollständigen Quellordner `docker compose -f compose.build.yaml up -d --build` ausführen. Updates bedeuten hier: neue Quellen holen und neu bauen. `update.sh` gilt nur für das fertige Image.

## Fehler eingrenzen

| Symptom | Prüfung |
|---|---|
| Start bricht ab: „kann nicht in /data schreiben“ | `data` gehört root. Siehe [Warum gehört `data` dem eigenen Benutzer?](#warum-gehört-data-dem-eigenen-benutzer) |
| Setup-Code abgelehnt | Aktuellsten Code seit dem letzten Start verwenden; keine `SETUP-CODE.txt` heißt: bereits eingerichtet. Passwort vergessen: [Betrieb](BETRIEB.md#app-passwort-vergessen). |
| Seite nicht erreichbar | Firewall für den Port prüfen; anderer Port über `HTTP_PORT` in der `.env`. |
| Gerätename nicht auflösbar | Name im Router, DNS des Containers prüfen; kein `http://` eingeben. |
| Keine Messwerte | Bridge-Passwort, Benutzer (`admin`, unter Erweitert), Node-ID, Webserver der Bridge und Funkverbindung prüfen. |
| Veraltete Daten | Lesekopf, Batterien, Empfangsdiagnose und letzte gültige Messung kontrollieren. |
| Nach Bridge-Neustart kein Webserver | [Bridge](BRIDGE.md) zur dauerhaften Freigabe. |
| Keine Benachrichtigung | Kanal, Hauptschalter, Ruhezeit und Zustellverlauf prüfen; gezielten Test senden. |

Nach der Einrichtung eine Datenbanksicherung herunterladen und die Zugangskonfiguration separat vertraulich sichern: [Betrieb](BETRIEB.md).

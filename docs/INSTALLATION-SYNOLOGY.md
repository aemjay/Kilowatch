# Installation auf einem Synology-NAS

Voraussetzung: ein Synology-NAS mit installiertem **Container Manager** (DSM 7.2 oder neuer). Unterstützt werden Modelle mit Intel/AMD-CPU (`linux/amd64`) und ARM64-Modelle (`linux/arm64`), sowohl beim Quellbuild als auch beim vorgebauten Image. Ohne weitere Angabe verwendet Docker die Plattform des NAS. Ältere 32-Bit-ARM-Modelle werden nicht unterstützt. Die Anleitung verändert DSM nicht. Auf anderen Docker-Hosts gelten dieselben Compose-Befehle.

## 1. Projektordner, Datenordner und Berechtigung

**Diese Reihenfolge einhalten.** Ohne vorab angelegten Ordner `data` mit passender Berechtigung scheitert der erste Start auf Synology: Der Container Manager legt fehlende Ordner nicht zuverlässig selbst an, und Synology-ACLs verweigern einer unbekannten Benutzer-ID den Zugriff, auch wenn der Container den Eigentümer setzt.

1. **Dateien kopieren.** Im GitHub-Repository **Code → Download ZIP** wählen, entpacken und den Inhalt nach beispielsweise `/volume1/docker/kilowatch` kopieren. Für das fertige Image genügen `compose.yaml`, `.env.example` und der Ordner `tools/`; zum Selbstbauen wird der vollständige Inhalt gebraucht.
2. **Benutzer wählen, dem die Daten gehören sollen.** Am einfachsten ein eigener DSM-Benutzer, z. B. `kilowatch` (Systemsteuerung → Benutzer und Gruppe → Erstellen; Anmeldung an DSM-Anwendungen darf verweigert werden). Alternativ das eigene Konto. Benutzer- und Gruppen-ID per SSH ermitteln: `id kilowatch` ergibt z. B. `uid=1030 gid=100`.
3. **Ordner `data` anlegen.** In der File Station unter `docker/kilowatch` den Ordner `data` erstellen.
4. **Berechtigung setzen.** File Station → `data` → Eigenschaften → Berechtigung → Erstellen: den Benutzer aus Schritt 2 mit **Lesen und Schreiben** eintragen und „Auf diesen Ordner, Unterordner und Dateien anwenden“ wählen.
5. **`.env` anlegen** mit `PUID` und `PGID` dieses Benutzers. Per SSH im Projektordner erledigt `python3 tools/setup.py` die Schritte 3 und 5 und fragt dabei Port, Plattform und IDs ab; nicht interaktiv: `python3 tools/setup.py --platform auto --puid 1030 --pgid 100`. Ohne SSH `.env.example` als `.env` kopieren (ohne `.txt`) und `PUID=`/`PGID=` ausfüllen.

**Keine Zugangsdaten in Dateien eintragen.** Bridge-, Mail- und App-Passwörter werden nur im Browser eingegeben.

Stimmt die Berechtigung nicht, bricht der Container beim Start mit einer Meldung im Protokoll ab („Kilowatch kann nicht in /data schreiben …“). Dann Schritt 4 und die IDs in der `.env` prüfen und das Projekt neu starten.

## 2. Projekt starten

**Empfohlen: fertiges Image.** Es wird automatisch aus der GitHub Container Registry geladen und lässt sich später einfach aktualisieren ([Updates](UPDATES.md)).

1. Container Manager → **Projekt → Erstellen**.
2. Name `kilowatch`, Projektpfad `/volume1/docker/kilowatch`.
3. Die vorhandene **`compose.yaml`** im Projektordner verwenden.
4. Erstellen und starten. Das Image für die NAS-Plattform (amd64 oder arm64) wird dabei geladen.

**Alternative: selbst bauen.** In Schritt 3 **`compose.build.yaml`** verwenden. Der Projektpfad muss dann der vollständige Quellordner bleiben, damit `build: .` funktioniert; der erste Build lädt Basisimage und Python-Pakete aus dem Internet. Updates bedeuten hier: neue Quellen kopieren und neu bauen; `tools/update.sh` gilt nur für das fertige Image.

Der Container Manager speichert die gewählte Datei im Projektordner immer als `compose.yaml`. Beim fertigen Image ist das dieselbe Datei wie im Repository. Wer `compose.build.yaml` wählt, bekommt deren Inhalt als `compose.yaml`; SSH-Befehle dann mit `-f compose.build.yaml` ausführen. Der Container heißt in beiden Fällen `kilowatch`.

Danach:

5. Container → Kilowatch → **Protokoll** öffnen. Dort steht beim ersten Start `Ersteinrichtung: Setup-Code …`. Den aktuellen Code lokal ablesen; nicht veröffentlichen.
6. Im Browser **`http://<NAS-FQDN>:8088`** öffnen. Auch die aktuelle NAS-IP ist möglich. Der NAS-Name muss vom eigenen Heimnetz auflösbar sein.

Falls Container Manager die Konfiguration als `docker-compose.yml` ablegt, den Dateinamen in SSH-Befehlen entsprechend anpassen. Ein Docker-Status `healthy` prüft Webserver und Datenbank, nicht den Empfang der Bridge.

## 3. Assistent abschließen

**Schritt 1:** Setup-Code aus dem Container-Protokoll und ein eigenes App-Passwort mit mindestens zwölf Zeichen eingeben. Es gibt kein Standardpasswort. Nach erfolgreicher Einrichtung ist der Code ungültig; bei einem Neustart vor Abschluss wird ein neuer Code ausgegeben.

**Schritt 2:** Folgende Werte eingeben:

| Feld | Eingabe |
|---|---|
| Bridge-Adresse | tatsächlicher FQDN, z. B. `tibber-bridge.fritz.box`, oder aktuelle IPv4-Adresse |
| Bridge-Passwort | Kennung vom Bridge-Aufkleber, Format `ABCD-EFGH` |
| Node-ID | meist 1; bei mehreren gekoppelten Pulse-Geräten die passende Node-ID der Bridge |

Optional unter **Bridge im Heimnetz suchen** das vorgeschlagene Subnetz prüfen und die Suche starten. Ein gefundener, überprüfter FQDN wird bevorzugt übernommen. Die Suche benötigt keine Zugangsdaten; danach den normalen Verbindungstest durchführen. [Details](GERAETESUCHE.md).

Die Adresse wird **ohne `http://`, Port und Pfad** eingegeben. **Verbindung prüfen** liest nur und zeigt die aufgelöste Adresse sowie das erkannte Protokoll. Danach **Bridge speichern und starten** wählen. Der Test allein übernimmt die Eingaben noch nicht für die Erfassung.

Die Bridge-Eingaben werden nach einem Neustart weiterverwendet. Unter **Einstellungen** lassen sich FQDN/IP, Benutzer und Passwort später ändern. Ein leeres Passwortfeld behält ein bereits gespeichertes Passwort bei. **Gespeichertes Bridge-Passwort entfernen** löscht es und pausiert die Erfassung; die Historie bleibt erhalten.

Anschließend unter **Kosten & Tarife** den eigenen vollständigen Bruttopreis eintragen: eine Tarifstufe oder zwei HT/NT-Preise mit Umschaltzeiten. [Tarifanleitung](TARIFE.md). Unter **Benachrichtigungen** E-Mail oder Signal einrichten; siehe [separate Anleitung](BENACHRICHTIGUNGEN.md). Die Historie beginnt mit der ersten erfolgreichen Erfassung.

## 4. DHCP und FQDN

DHCP kann für NAS und Bridge eingeschaltet bleiben. Im Router den tatsächlichen Gerätenamen nachsehen beziehungsweise einen eindeutigen Namen vergeben. Bei einer FRITZ!Box kann das beispielsweise `tibber-bridge.fritz.box` sein. Dieser Beispielname wird von Kilowatch nicht automatisch angelegt oder erkannt.

Entscheidend ist, dass der Router-DNS den Namen auf die jeweils aktuelle Adresse abbildet und der Container diesen DNS benutzen kann. Kilowatch löst den Bridge-Namen bei neuen HTTP-Abrufen erneut auf und hält keine alte HTTP-Verbindung dauerhaft offen. Die Geschwindigkeit eines Wechsels hängt zusätzlich von DNS-Caches und TTLs des Routers ab. Bei Auflösungsfehlern bleiben historische Daten erhalten und die App versucht es erneut.

Falls nur im Container die Auflösung fehlschlägt, die DNS-Konfiguration des NAS und des Docker-Netzwerks prüfen. `.local`/mDNS funktioniert nicht in jeder Docker-Konfiguration; für diesen Aufbau einen normalen Heimnetz-DNS-Namen verwenden. Es werden lokale IPv4-Ziele unterstützt; öffentliche Ziele und gemischte öffentliche/private DNS-Antworten werden abgelehnt.

Auch für den Browserzugriff auf das NAS kann dessen Router-DNS-Name verwendet werden. Eine DHCP-Reservierung oder statische IP wird nicht vorausgesetzt.

## 5. NAS ohne Internetzugang

An jedem Release (Releases-Seite des GitHub-Repositorys) hängen Importdateien `kilowatch-<version>-amd64.tar.gz` und `-arm64.tar.gz` mit Prüfsumme. Die zur NAS-CPU passende wählen (DSM: **Systemsteuerung → Info-Center**).

Container Manager → **Image → Hinzufügen/Importieren → Aus Datei**. Danach das Projekt wie oben mit **`compose.yaml`** erstellen; das importierte Image trägt bereits den passenden Namen.

Per SSH:

```sh
docker load -i kilowatch-<version>-<plattform>.tar.gz
docker compose -f compose.yaml up -d --pull never
docker compose -f compose.yaml logs --tail=50 kilowatch
```

Beide Varianten verwenden den Ordner `data/` im Projektordner und das Volume `kilowatch-secrets`. Nur eine App-Instanz darauf betreiben. Nicht `down -v` ausführen, sonst sind die gespeicherten Zugangsdaten weg.

## 6. Netzwerk und Ressourcen

- Oberfläche: TCP 8088 im eigenen Heimnetz; DSM-Firewall passend zur LAN-Quelle konfigurieren.
- Erfassung: NAS → aktuelle Bridge-Adresse, TCP 80. Keine Portweiterleitung aus dem Internet erforderlich.
- Die Bridge verwendet lokales HTTP mit Basic Auth. Für den Browserzugriff kann ein DSM-Reverse-Proxy mit gültigem HTTPS-Zertifikat eingerichtet werden. Dann `COOKIE_SECURE=true` setzen und den ursprünglichen Host-Header weiterreichen; bei direktem HTTP bleibt der Wert `false`.
- App-Limit: 512 MiB RAM; optional Mosquitto 64 MiB, optional Signal 1024 MiB. Kein CPU-Limit: Der DSM-Kernel unterstützt keine CFS-Quota (`cpus` bricht den Containerstart ab). Kein eigener Logtreiber, damit das Protokoll im Container Manager sichtbar bleibt.
- Mehrere GB freie Reserve vorsehen. Sieben vollständige Datenbanksicherungen können deutlich mehr Platz als die Datenbank allein benötigen. Freien Speicher und tatsächliches Wachstum überwachen.
- Der Projektordner muss auf einem lokalen NAS-Volume liegen (z. B. `/volume1/docker`). Keine aktive Datenbank auf SMB/NFS verlagern; Sicherungen dürfen dort liegen.
- `data/` vor dem ersten Start anlegen und dem Benutzer aus `PUID`/`PGID` Schreibrecht geben (Abschnitt 1). [Speicherorte und Sicherung](BETRIEB.md#speicherorte).

Die Anwendung nutzt vorhandene Geräte und verändert keine Bridge-Parameter. Aktuelle Firmware liefert Daten unter `/node_data.json`, ältere unter `/data.json`; Kilowatch probiert beide Pfade automatisch.

## Fehler eingrenzen

| Symptom | Prüfung |
|---|---|
| Setup-Code abgelehnt | aktuellstes Protokoll seit letztem Start verwenden; Code gilt nur bis zur abgeschlossenen Ersteinrichtung |
| App-Passwort vergessen | lokales Verfahren in [BETRIEB.md](BETRIEB.md) |
| Port belegt | `HTTP_PORT` in optionaler `.env` ändern und Projekt aktualisieren |
| Dockerfile fehlt | vollständiger Quellordner als Projektpfad |
| FQDN nicht auflösbar | Gerätename, Router-DNS und Container-DNS prüfen; kein `http://` eingeben |
| Keine Messwerte | Bridge-Passwort, Benutzer (`admin`, unter Erweitert), Node-ID, Webserver und Funkverbindung prüfen |
| Veraltete Daten | Lesekopf, Batterien, Empfangsdiagnose und letzte gültige Messung kontrollieren |
| Nach Bridge-Neustart kein Webserver | [BRIDGE.md](BRIDGE.md) zur dauerhaften Freigabe |
| Keine Benachrichtigung | Kanal, Hauptschalter, Ruhezeit und Zustellverlauf prüfen; gezielten Test senden |

Nach der Einrichtung eine Datenbanksicherung herunterladen und die Zugangskonfiguration separat vertraulich sichern: [BETRIEB.md](BETRIEB.md).

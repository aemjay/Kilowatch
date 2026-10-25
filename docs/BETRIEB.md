# Betrieb, Sicherung und Wiederherstellung

Alle Befehle im Projektordner des NAS ausführen. Wer selbst baut, verwendet `compose.build.yaml` statt `compose.yaml`. Bei optionalen Zusatzdiensten die zugehörigen `-f compose.signal.yaml` beziehungsweise `-f compose.mqtt.yaml` auch bei Updates mitführen.

## Alltag und Zugangsdaten

```sh
docker compose -f compose.yaml ps
docker compose -f compose.yaml logs --tail=100 kilowatch
docker compose -f compose.yaml restart kilowatch
```

`healthy` bestätigt Webserver und SQLite. Die Aktualität der Messung steht gesondert in der Oberfläche. Ein Healthcheck allein startet einen noch laufenden Container nicht neu; `unless-stopped` greift nach einem Prozessende beziehungsweise Docker-Neustart.

Unter **Einstellungen** lassen sich Bridge-FQDN/IP, Benutzer und Passwort sowie das App-Passwort ändern. Unter **Benachrichtigungen** bleiben Versandkanäle, Passwörter, Empfänger, Regeln und Ruhezeiten änderbar. Leere Passwortfelder behalten vorhandene Passwörter bei; eigene Schalter erlauben das Entfernen. Änderungen des App-Passworts beenden alle Sitzungen.

Es sind keine persönlichen Daten oder Passwörter im Image enthalten. Die Standardeinrichtung benötigt keine Zugangsdaten in `.env`.

## Abfrageintervall und Auflösung

Das **Abfrageintervall** (Einstellungen → Erweitert, 2 bis 60 Sekunden) bestimmt, wie oft Kilowatch die Bridge abfragt. Die Live-Anzeige aktualisiert sich im selben Takt. Neue Werte gibt es aber nur so oft, wie der Zähler über den Pulse Telegramme liefert; fragt Kilowatch öfter, kommt mehrfach derselbe Wert und die Anzeige meldet nach 30 Sekunden ein unverändertes Telegramm.

Gespeichert werden alle einzelnen Messwerte (Aufbewahrung „Einzelwerte“, Standard 90 Tage), Minutenwerte (Standard drei Jahre) und dauerhaft Viertelstundenwerte. Die Ansicht **1 Std.** zeigt die einzelnen Messwerte, **6 Std.** und einzelne Tage zeigen Minutenmittel, längere Zeiträume Viertelstunden, Tage oder Monate.

## Speicherorte

Messdaten und Zugangsdaten liegen bewusst an zwei Orten:

```text
<Projektordner>/data/            # Ordner, z. B. /volume1/docker/kilowatch/data
  live/
    kilowatch.sqlite3            # Datenbank (mit -wal/-shm)
    backups/                     # tägliche, geprüfte Sicherungen (letzte sieben)
  demo/                          # getrennte Daten im Demo-Modus

Docker-Volume kilowatch-secrets  # nicht im Projektordner
  live/
    app-auth.json                # gesalzener scrypt-Hash des App-Passworts
    secrets.enc                  # verschlüsselte Bridge-/SMTP-Passwörter und Gateway-Token
    secrets.key                  # lokaler Fernet-Schlüssel
```

**Warum getrennt?** Läge der Schlüssel neben den verschlüsselten Passwörtern im gesicherten Ordner, enthielte jede Sicherung beides zusammen, und die Verschlüsselung wäre wertlos. So landen in Hyper Backup nur Messdaten, Einstellungen und Sicherungen, aber keine Geheimnisse. Das Volume liegt unter `@docker` und wird von einer Sicherung des Ordners `docker` nicht erfasst.

Kilowatch läuft unter dem Eigentümer des Ordners `data` (wer ihn in der File Station angelegt hat) oder, falls gesetzt, unter `PUID`/`PGID` aus der `.env`. Beim Start passt der Container die Eigentümer an, prüft das Schreibrecht und läuft danach ohne Root-Rechte.

Passwörter und Token werden atomar mit Dateirechten 0600 geschrieben. Wer als NAS-Administrator auf das Volume zugreifen kann, kann die Geheimnisse entschlüsseln; für Schutz bei Datenträgerverlust zusätzlich NAS-Verschlüsselung verwenden. Die API liefert gespeicherte Passwörter und Schlüssel nicht zurück.

Adressen, Benutzernamen, Empfänger und Regeln sind Einstellungen in SQLite; ebenso der Nachrichtenverlauf einschließlich Nachrichtentext. Sicherungen von `data/` deshalb vertraulich behandeln.

## Sichern

- **Hyper Backup:** den Ordner `docker/kilowatch` (oder nur `data/`) aufnehmen. Für eine Wiederherstellung die geprüften Dateien aus `data/live/backups/` verwenden; die laufende `kilowatch.sqlite3` allein ist wegen WAL keine verlässliche Sicherung.
- **Sofort:** In **System & Datenqualität → Jetzt konsistent sichern** eine `.sqlite3`-Datei herunterladen. Die SQLite-Backup-API liefert auch im laufenden Betrieb einen konsistenten Stand; danach wird `integrity_check` geprüft.
- **Zugangsdaten:** werden absichtlich nicht mitgesichert. Nach einer Wiederherstellung auf einem neuen NAS über den Setup-Code ein neues App-Passwort setzen und Bridge-Passwort (Aufkleber) sowie SMTP-/Signal-Zugänge neu eingeben. Wer das vermeiden möchte, sichert das Volume separat auf verschlüsseltem Speicher – niemals zusammen mit `data/`.

Der optionale Signal-Container hat zusätzlich das Volume `kilowatch-signal` mit Geräteidentität und Schlüsseln. Es wird ebenfalls nicht mitgesichert; bei Verlust den Zusatzcontainer neu am Handy koppeln.

Eine Kopie auf einem anderen Datenträger ist nötig, um einen vollständigen NAS-Ausfall abzudecken.

## Datenbank wiederherstellen

1. Gewünschte Sicherung (z. B. aus `data/live/backups/`) nach `restore/kilowatch-sicherung.sqlite3` im Projektordner kopieren.
2. App stoppen. Keine zweite App-Instanz mit demselben Datenordner laufen lassen.
3. Geprüften Restore ausführen:

```sh
docker compose -f compose.yaml stop kilowatch
docker compose -f compose.yaml run --rm --no-deps -v "$PWD/restore:/restore:ro" kilowatch python -m app.cli restore /restore/kilowatch-sicherung.sqlite3 --confirm-stopped
docker compose -f compose.yaml up -d --no-build kilowatch
```

Das Werkzeug prüft Integrität und Schema, sichert eine vorhandene Datenbank als `backups/before-restore-…sqlite3` und ersetzt erst danach das Ziel. Solche Vorher-Sicherungen werden nicht von der normalen Sieben-Dateien-Rotation entfernt. `--confirm-stopped` bestätigt deine vorherige Handlung; es stoppt keinen anderen Container automatisch.

Zugangsdaten bleiben bei einem Datenbank-Restore unberührt. Fehlen sie (neues NAS), lässt sich die App über den Setup-Code neu einrichten und die Zugänge werden erneut eingegeben. Existiert `secrets.enc` ohne passenden Schlüssel, bricht der Start mit verständlichem Fehler ab, statt die vorhandenen Geheimnisse zu überschreiben. Nicht `down -v` als Restore-Schritt verwenden: das löscht das Zugangsdaten-Volume.

## App-Passwort vergessen

Mit lokalem Docker-Administrationszugriff lässt sich ausschließlich die App-Anmeldung zurücksetzen:

```sh
docker compose -f compose.yaml stop kilowatch
docker compose -f compose.yaml run --rm --no-deps kilowatch python -m app.cli reset-login --confirm-stopped
docker compose -f compose.yaml up -d --no-build kilowatch
docker compose -f compose.yaml logs --tail=50 kilowatch
```

Danach den neuen Setup-Code aus `data/SETUP-CODE.txt` oder dem Protokoll verwenden und ein neues App-Passwort setzen. Messdaten und verschlüsselte Bridge-/SMTP-Zugänge bleiben erhalten. Der alte Passwort-Hash wird lokal als `app-auth.before-reset-…json` gesichert. Eine versehentliche Rücksetzung kann bei gestoppter App durch Zurückkopieren dieser Datei nach `app-auth.json` rückgängig gemacht werden.

## Update

Siehe **[Updates](UPDATES.md)**: Update-Hinweis in der App, Update per Container Manager, SSH oder DSM-Aufgabenplaner, automatische Sicherung vor Datenbankänderungen und Rückweg.

## Nach Messausfällen

Die letzte Zählerbasis bleibt persistent. Eine spätere positive Differenz kann die Gesamtenergie während einer Unterbrechung liefern; der zeitliche Lastverlauf wird nicht erfunden. **Verlauf → Messlücken** und **System & Datenqualität** kontrollieren. Ruhezeiten und Wiederholungen für Nachrichten sind unter [Benachrichtigungen](BENACHRICHTIGUNGEN.md) beschrieben.

## Datenbankschema

Die Datenbank trägt eine Schemakennung (`PRAGMA user_version`). Ein älteres Schema wird beim Start ohne Verlust der Historie übernommen. Ältere App-Versionen lehnen ein neueres Schema ab; ein Downgrade benötigt daher die passende Sicherung von vor dem Update.

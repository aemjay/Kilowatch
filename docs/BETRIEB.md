# Betrieb, Sicherung und Wiederherstellung

Alle Befehle laufen im Projektordner. Wer selbst baut, nimmt `compose.build.yaml` statt `compose.yaml`; mit dem MQTT-Broker immer auch `-f compose.mqtt.yaml` mitführen.

## Alltag

```sh
docker compose -f compose.yaml ps                          # Status
docker compose -f compose.yaml logs --tail=100 kilowatch   # Protokoll
docker compose -f compose.yaml restart kilowatch           # Neustart
```

`healthy` bestätigt Webserver und Datenbank. Ob frische Messwerte ankommen, zeigt die Oberfläche. Bridge-Zugang, Mail-Zugang und App-Passwort änderst du unter **Einstellungen** und **Benachrichtigungen**; ein leeres Passwortfeld behält das gespeicherte. Ein neues App-Passwort beendet alle Sitzungen.

Das **Abfrageintervall** (Einstellungen → Erweitert, 2 bis 60 Sekunden, Standard 5) bestimmt, wie oft Kilowatch die Bridge fragt. Neue Werte gibt es nur, so oft der Zähler Telegramme liefert; öfter fragen bringt dieselben Werte mehrfach.

## Speicherorte

Messdaten und Zugangsdaten liegen bewusst getrennt:

```text
<Projektordner>/data/              Messdaten (in jede Dateisicherung aufnehmen)
  live/kilowatch.sqlite3           Datenbank (mit -wal/-shm)
  live/backups/                    tägliche, geprüfte Sicherungen (letzte sieben)
  demo/                            Daten des Demo-Modus
Docker-Volume kilowatch-secrets    Zugangsdaten (nicht im Projektordner)
  live/app-auth.json               Hash des App-Passworts
  live/secrets.enc, secrets.key    verschlüsselte Passwörter und ihr Schlüssel
```

Läge der Schlüssel neben den verschlüsselten Passwörtern, enthielte jede Sicherung beides, und die Verschlüsselung wäre wertlos. Wer Administrator des Hosts ist, kann die Geheimnisse trotzdem entschlüsseln; gegen Datenträgerverlust hilft nur Festplattenverschlüsselung. Adressen, Empfänger, Regeln und der Nachrichtenverlauf liegen in der Datenbank, behandle Sicherungen deshalb vertraulich.

## Sichern

- **Dateisicherung** (auf Synology Hyper Backup): `data/` aufnehmen und für eine Wiederherstellung die geprüften Dateien aus `data/live/backups/` nehmen, nicht die laufende `kilowatch.sqlite3`.
- **Sofort:** **System & Datenqualität → Jetzt konsistent sichern** lädt eine `.sqlite3`-Datei herunter.
- **Zugangsdaten** sind absichtlich nicht dabei. Nach einer Wiederherstellung auf einem neuen Host setzt du über den Setup-Code ein neues App-Passwort und gibst Bridge-, Mail- und Tibber-Zugang neu ein. Willst du das vermeiden, sichere das Volume separat auf verschlüsseltem Speicher, nie zusammen mit `data/`.

Eine Kopie auf einem anderen Datenträger fängt einen Totalausfall des Hosts ab.

## Datenbank wiederherstellen

1. Sicherung nach `restore/kilowatch-sicherung.sqlite3` im Projektordner kopieren.
2. App stoppen und zurückspielen:

   ```sh
   docker compose -f compose.yaml stop kilowatch
   docker compose -f compose.yaml run --rm --no-deps -v "$PWD/restore:/restore:ro" kilowatch python -m app.cli restore /restore/kilowatch-sicherung.sqlite3 --confirm-stopped
   docker compose -f compose.yaml up -d --no-build kilowatch
   ```

Das Werkzeug prüft Integrität und Schema, sichert die vorhandene Datenbank als `backups/before-restore-…sqlite3` und ersetzt sie erst danach. Zugangsdaten bleiben unberührt. Fehlt zu `secrets.enc` der Schlüssel, bricht der Start ab, statt Geheimnisse zu überschreiben.

> [!WARNING]
> Nie `docker compose down -v` als Wiederherstellungsschritt: Es löscht das Zugangsdaten-Volume.

## API-Tokens

Unter **Einstellungen → API-Tokens** legst du bis zu zehn Tokens für Skripte an ([API](API.md#api-tokens)). Für den sicheren Umgang gilt:

- Der Klartext erscheint nur einmal direkt nach dem Erstellen. Kilowatch speichert nur den SHA-256-Hash in der Datenbank; ein Token lässt sich daraus nicht zurückgewinnen, nur löschen und neu anlegen.
- Ein Token ist ein Passwortersatz ohne Ablaufdatum. Es gilt nach Neustarts, nach einem Wechsel des App-Passworts und nach `reset-login` weiter. Lege Tokens in Skripten oder Geheimnisspeichern ab, nicht in geteilten Dateien, und lösche nicht mehr benötigte Tokens. Nach einem Verdacht auf Missbrauch: Tokens löschen und App-Passwort ändern.
- `read` liest alles, was die Oberfläche zeigt, einschließlich Export und Datenbanksicherung. Wähle `full` nur, wenn das Skript Einstellungen ändern muss.
- Über HTTP geht das Token unverschlüsselt durchs Heimnetz. Nutze außerhalb eines vertrauenswürdigen Netzes nur HTTPS ([Installation](INSTALLATION.md)).
- Ungültige Tokens zählen wie Fehlanmeldungen: Nach zehn Fehlversuchen einer Adresse (oder 50 insgesamt) sind Token-Anfragen bis zu 15 Minuten gesperrt, auch mit gültigem Token.
- Eine zurückgespielte Datenbank bringt die Tokens ihres Sicherungsstands mit. Prüfe danach die Liste.

## App-Passwort vergessen

Mit Docker-Zugriff auf den Host setzt du nur die Anmeldung zurück, Daten und Zugänge bleiben:

```sh
docker compose -f compose.yaml stop kilowatch
docker compose -f compose.yaml run --rm --no-deps kilowatch python -m app.cli reset-login --confirm-stopped
docker compose -f compose.yaml up -d --no-build kilowatch
```

Danach legst du mit dem neuen Setup-Code aus `data/SETUP-CODE.txt` (oder dem Protokoll) ein neues Passwort fest. Der alte Hash liegt als `app-auth.before-reset-…json` bereit; zurückkopiert nach `app-auth.json` macht er die Rücksetzung rückgängig.

## Nach Messausfällen

Die letzte Zählerbasis bleibt gespeichert. Eine spätere positive Differenz liefert die Gesamtenergie der Unterbrechung; einen Lastverlauf erfindet Kilowatch nicht. Lücken zeigen **Verlauf** und **System & Datenqualität**.

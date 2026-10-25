# Updates

Kilowatch aktualisiert sich nie selbst und braucht dafür keinen Zugriff auf Docker (kein Docker-Socket in der App). Die App kann optional anzeigen, dass es eine neue Version gibt; installiert wird mit **einem Skript**: `tools/update.sh`. Dasselbe Skript führt auch die [Erstinstallation](INSTALLATION.md) durch.

## Aktualisieren

```sh
sudo sh <projektordner>/tools/update.sh
```

Ohne Optionen. Das Skript fragt nichts und ist deshalb auch für den Aufgabenplaner geeignet. Es geht so vor:

1. **Sich selbst aktualisieren.** Ist im Release eine neuere `update.sh` enthalten, ersetzt es sich und läuft mit der neuen Fassung weiter.
2. **`compose.yaml` abgleichen.** Ist die Datei unverändert gegenüber der zuletzt installierten Fassung, wird sie durch die des Releases ersetzt, die bisherige als `compose.yaml.bak-<zeit>` gesichert. Hast du sie angepasst, bleibt sie unverändert; die neue Fassung liegt als `compose.yaml.new` daneben und das Skript warnt.
3. **Image prüfen und laden.** Die Signatur wird geprüft (siehe unten), geladen wird genau der geprüfte Digest. Fehlt die Signatur, bricht das Update ab und der laufende Container bleibt unverändert.
4. **Nur bei neuer Version neu starten** und auf den Healthcheck warten. Eine nötige Datenbankänderung legt Kilowatch vorher selbst als geprüfte Sicherung `data/live/backups/pre-migration-v<alt>-to-v<neu>-<zeit>.sqlite3` ab.
5. **Rollback.** Wird die neue Version nicht gesund, startet das Skript automatisch wieder das vorherige Image und endet mit Fehlercode. Hat die neue Version die Datenbank bereits geändert, startet die ältere nicht; dann die genannte Sicherung wie unter [Rückweg](#rückweg) einspielen.
6. Alte Image-Schichten aufräumen.

Optionen wie bei der Installation: `--dir`, `--user`, `--port`, `--version X.Y.Z` (feste Version), `--no-start` (nur vorbereiten), `--source PFAD` (lokale Release-Dateien statt GitHub, [offline](INSTALLATION.md#ohne-internet)) und `-h`.

### Automatisch (Synology-Aufgabenplaner)

Systemsteuerung → Aufgabenplaner → Erstellen → Geplante Aufgabe → **Benutzerdefiniertes Skript**.

- Benutzer: `root` (nötig für Docker)
- Zeitplan: zum Beispiel wöchentlich nachts
- Aufgabeneinstellungen → Befehl: `sh /volume1/docker/kilowatch/tools/update.sh`
- Optional „Ausführungsdetails per E-Mail senden … nur bei Fehler“

Auf anderen Hosts genügt ein cron-Eintrag mit demselben Befehl als root. Mit dem Standard-Tag `1` kommen so Fehlerbehebungen und neue 1.x-Funktionen automatisch, nie eine neue Hauptversion. Bewusst nicht vorgesehen sind Werkzeuge wie Watchtower: Sie brauchen Zugriff auf den Docker-Socket, also Root-Rechte auf dem Host, und ziehen Images ohne Prüfung.

### Bestehende Installation vor 1.3

Ältere Installationen haben noch die frühere `tools/update.sh`, die sich nicht selbst aktualisiert. Einmalig die neue Fassung laden und ausführen:

```sh
curl -fsSL -o tools/update.sh https://github.com/aemjay/Kilowatch/releases/latest/download/update.sh
sudo sh tools/update.sh
```

Danach genügt der normale Aufruf. Der frühere Installer `install.sh` und `tools/setup.py` entfallen; die Aufrufe `install.sh --user …` ersetzt `update.sh --user …`.

## Update-Hinweis in der App

Unter **System & Datenqualität → Updates** lässt sich der Hinweis einschalten. Kilowatch fragt dann höchstens einmal täglich bei GitHub nach dem neuesten Release. Dabei werden keine Messdaten, Kennungen oder Cookies übertragen; GitHub sieht nur die IP-Adresse des Hosts. Ohne Einschalten findet keine automatische Abfrage statt; **Jetzt prüfen** fragt einmalig. Angezeigt werden neue Version, Release-Notizen und ob das Update die Datenbank ändert. Das Update selbst startest du immer außerhalb der App.

## Versionen und Images

Releases folgen [Semantic Versioning](https://semver.org/lang/de/) und erscheinen als signierte Multi-Arch-Images (amd64/arm64) unter `ghcr.io/aemjay/kilowatch`:

| Tag | Bedeutung |
|---|---|
| `1.2.3` | genau diese Version |
| `1.2` | neueste Fehlerbehebung von 1.2 |
| `1` | neueste 1.x-Version, keine inkompatiblen Änderungen (**Standard in `compose.yaml`**) |
| `latest` | neueste stabile Version, auch über Hauptversionen hinweg; für automatische Updates nicht empfohlen |
| `edge` | aktueller Entwicklungsstand, nur zum Testen |

Eine feste Version setzt `KILOWATCH_VERSION=1.2.3` in der `.env` oder `update.sh --version 1.2.3`. Ein Wechsel auf eine neue Hauptversion geschieht nie automatisch; vorher die Release-Notizen lesen.

### Signaturprüfung

Jedes Image wird im GitHub-Workflow keyless mit [cosign](https://docs.sigstore.dev/) signiert. `update.sh` prüft die Signatur **vor** jedem Start, löst den Tag über sie in einen Digest auf, lädt genau diesen und legt ihn lokal unter dem gewohnten Tag ab. Ist `cosign` nicht installiert, verwendet das Skript ein per Digest fixiertes cosign-Image. Die Prüfung braucht Internetzugang zu Sigstore.

Erwartete Identität (Groß-/Kleinschreibung des Repositorys beachten):

```sh
cosign verify ghcr.io/aemjay/kilowatch:1 \
  --certificate-identity-regexp '^https://github\.com/aemjay/Kilowatch/\.github/workflows/nas-image\.yml@refs/(heads/main|tags/v[0-9]+\.[0-9]+\.[0-9]+)$' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

Nur für selbst gebaute oder umbenannte Images: `KILOWATCH_VERIFY=0` in der `.env` schaltet die Prüfung ab, `KILOWATCH_SIGNER` setzt eine andere erwartete Identität.

## Datenbankänderungen

Ändert ein Update das Schema, legt Kilowatch beim ersten Start **vor** der Änderung eine geprüfte Sicherung `data/live/backups/pre-migration-v<alt>-to-v<neu>-<zeit>.sqlite3` an. Diese Dateien werden nicht automatisch gelöscht. Jede Stufe läuft in einer eigenen Transaktion; schlägt sie fehl, bleibt die Datenbank auf dem vorherigen Stand. Releases mit Schemaänderung sind in den Release-Notizen gekennzeichnet.

## Rückweg

1. Vorherige Version festlegen: `sudo sh tools/update.sh --version 1.2.3` (oder in der `.env` `KILOWATCH_VERSION=1.2.3` eintragen und `docker compose up -d`).
2. Hat das Update die Datenbank geändert, startet die ältere Version nicht und nennt im Protokoll die Sicherung. Diese wie unter [Datenbank wiederherstellen](BETRIEB.md#datenbank-wiederherstellen) einspielen, mit der Datei `pre-migration-…sqlite3`.

Messwerte, die zwischen Update und Rückweg erfasst wurden, fehlen nach dem Einspielen der Sicherung.

## Für Maintainer: Release erstellen

1. Version in `app/__init__.py` erhöhen (einzige Stelle). Legt der Workflow das Release an, schreibt er `<!-- schema: N -->` mit der aktuellen `SCHEMA_VERSION` selbst in die Release-Notizen; bei einem in der GitHub-Oberfläche angelegten Release diese Zeile von Hand ergänzen.
2. Tag setzen und pushen: `git tag v1.2.3 && git push origin v1.2.3`. Alternativ in GitHub unter **Releases → Draft a new release** den Tag `v1.2.3` auf `main` neu anlegen und veröffentlichen; der Workflow hängt die Importdateien dann an dieses Release.
   Ohne Tag-Rechte: unter **Actions → Kilowatch - Tests und NAS-Image → Run workflow** den Branch `main` wählen und **release** ankreuzen. Der Workflow legt Tag `v<Version>` und Release dann selbst auf dem getesteten Commit an.
3. Der Workflow prüft, dass Tag und Version übereinstimmen, testet beide Plattformen inklusive Update von der letzten Version, veröffentlicht die Images mit Signatur, SBOM und Provenienz und legt das Release mit Importdateien an.
4. Nach dem ersten Release das Paket unter GitHub → Packages → `kilowatch` → Package settings einmalig auf **Public** stellen, damit es ohne Anmeldung geladen werden kann.

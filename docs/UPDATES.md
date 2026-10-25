# Updates

Kilowatch aktualisiert sich nie selbst und braucht dafür keinen Zugriff auf Docker. Die App kann optional anzeigen, dass es eine neue Version gibt; installiert wird über DSM.

## Versionen und Images

Releases folgen [Semantic Versioning](https://semver.org/lang/de/) und erscheinen als signierte Multi-Arch-Images (amd64/arm64) unter `ghcr.io/aemjay/kilowatch`:

| Tag | Bedeutung |
|---|---|
| `1.2.3` | genau diese Version |
| `1.2` | neueste Fehlerbehebung von 1.2 |
| `1` | neueste 1.x-Version: Fehlerbehebungen und neue Funktionen, keine inkompatiblen Änderungen (**Standard in `compose.yaml`**) |
| `latest` | neueste stabile Version, auch über Hauptversionen hinweg – für automatische Updates nicht empfohlen |
| `edge` | aktueller Entwicklungsstand, nur zum Testen |

Eine feste Version lässt sich mit `KILOWATCH_VERSION=1.2.3` in der `.env` wählen. Ein Wechsel auf eine neue Hauptversion (z. B. 2.x) geschieht nie automatisch; vorher die Release-Notizen lesen.

Die Signatur lässt sich mit [cosign](https://docs.sigstore.dev/) prüfen:

```sh
cosign verify ghcr.io/aemjay/kilowatch:1 \
  --certificate-identity-regexp '^https://github.com/aemjay/kilowatch/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

## Hinweis in der App

Unter **System & Datenqualität → Updates** lässt sich der Update-Hinweis einschalten. Kilowatch fragt dann höchstens einmal täglich bei GitHub nach dem neuesten Release. Dabei werden keine Messdaten, Kennungen oder Cookies übertragen; GitHub sieht nur die IP-Adresse des NAS. Ohne Einschalten findet keine automatische Abfrage statt; **Jetzt prüfen** fragt einmalig.

Angezeigt werden neue Version, Release-Notizen und ob das Update die Datenbank ändert.

## Aktualisieren

**Per SSH im Projektordner:**

```sh
sh tools/update.sh
```

Das Skript lädt das Image, startet den Container nur bei einer neuen Version neu, wartet auf den Healthcheck und räumt alte Image-Schichten auf. Es gibt einen Fehlercode zurück, wenn die neue Version nicht gesund startet.

**Automatisch per DSM-Aufgabenplaner:** Systemsteuerung → Aufgabenplaner → Erstellen → Geplante Aufgabe → Benutzerdefiniertes Skript.

- Benutzer: `root` (nötig für Docker)
- Zeitplan: z. B. wöchentlich nachts
- Aufgabeneinstellungen → Befehl: `sh /volume1/docker/kilowatch/tools/update.sh`
- Optional „Ausführungsdetails per E-Mail senden … nur bei Fehler“ aktivieren

Mit dem Standard-Tag `1` kommen so Fehlerbehebungen und neue 1.x-Funktionen automatisch, aber nie eine neue Hauptversion.

**Compose-Datei aktualisieren:** Neue Releases können die `compose.yaml` erweitern. Ein erneuter Lauf des [Installers](SCHNELLSTART.md#b--installer) holt die aktuelle Datei, sichert die bisherige als `compose.yaml.bak-…` und lässt die `.env` unverändert.

**Ohne Internet:** neue Importdatei vom Release laden, im Container Manager importieren und `docker compose -f compose.yaml up -d --pull never` ausführen.

Bewusst nicht vorgesehen sind Werkzeuge wie Watchtower: Sie brauchen Zugriff auf den Docker-Socket, also Root-Rechte auf dem NAS, und ziehen Images ohne Prüfung.

## Datenbankänderungen

Ändert ein Update das Datenbankschema, legt Kilowatch beim ersten Start **vor** der Änderung eine geprüfte Sicherung `data/live/backups/pre-migration-v<alt>-to-v<neu>-<zeit>.sqlite3` an. Diese Dateien werden nicht automatisch gelöscht. Jede Änderungsstufe läuft in einer eigenen Transaktion; schlägt sie fehl, bleibt die Datenbank auf dem vorherigen Stand. Releases, die das Schema ändern, sind in den Release-Notizen gekennzeichnet.

## Rückweg

1. In der `.env` die vorherige Version eintragen, z. B. `KILOWATCH_VERSION=1.2.3`.
2. Falls das Update die Datenbank geändert hat: Die ältere Version startet dann nicht und nennt im Protokoll die Sicherung. Diese wie unter [Datenbank wiederherstellen](BETRIEB.md#datenbank-wiederherstellen) einspielen: die Datei `pre-migration-…sqlite3` verwenden.
3. `docker compose -f compose.yaml up -d`

Messwerte, die zwischen Update und Rückweg erfasst wurden, fehlen nach dem Einspielen der Sicherung.

## Für Maintainer: Release erstellen

1. Version in `app/__init__.py` erhöhen (einzige Stelle). Hat sich das Schema geändert, in die Release-Notizen `<!-- schema: N -->` mit der neuen `SCHEMA_VERSION` schreiben.
2. Tag setzen und pushen: `git tag v1.2.3 && git push origin v1.2.3`. Alternativ in GitHub unter **Releases → Draft a new release** den Tag `v1.2.3` auf `main` neu anlegen und veröffentlichen; der Workflow hängt die Importdateien dann an dieses Release.
3. Der Workflow prüft, dass Tag und Version übereinstimmen, testet beide Plattformen inklusive Update von der letzten Version, veröffentlicht die Images mit Signatur, SBOM und Provenienz und legt das Release mit Importdateien an.
4. Nach dem ersten Release das Paket unter GitHub → Packages → `kilowatch` → Package settings einmalig auf **Public** stellen, damit es ohne Anmeldung geladen werden kann.

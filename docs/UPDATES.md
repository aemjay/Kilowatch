# Updates

Kilowatch aktualisiert sich nie selbst und hat keinen Zugriff auf Docker. Du startest das Update mit demselben Skript wie die [Installation](INSTALLATION.md).

## Aktualisieren

```sh
sudo sh <projektordner>/tools/update.sh
```

Das Skript fragt nichts und läuft deshalb auch im Aufgabenplaner. Es geht so vor:

1. **Aktualisiert sich selbst** und läuft mit der Fassung aus dem Release weiter.
2. **Gleicht `compose.yaml` ab.** Ist sie unverändert, ersetzt es sie (die alte bleibt als `compose.yaml.bak-<zeit>`). Hast du sie angepasst, bleibt sie, die neue Fassung liegt als `compose.yaml.new` daneben und das Skript warnt.
3. **Prüft die Signatur** des Images und lädt genau das geprüfte. Ohne gültige Signatur bricht es ab, der laufende Container bleibt unverändert.
4. **Startet nur bei einer neuen Version neu** und wartet auf den Healthcheck.
5. **Rollt zurück,** wenn die neue Version nicht gesund startet, und endet mit einem Fehler.

Optionen wie bei der Installation (`--version X.Y.Z`, `--no-start`, `--source PFAD`, `-h`).

**Automatisch:** Auf Synology als Aufgabenplaner-Aufgabe (Benutzer root, z. B. wöchentlich nachts, Befehl `sh /volume1/docker/kilowatch/tools/update.sh`), sonst per cron als root. Mit dem Standard-Tag `1` kommen so Fehlerbehebungen und neue 1.x-Funktionen, nie eine neue Hauptversion. Tools wie Watchtower sind bewusst nicht vorgesehen: Sie brauchen den Docker-Socket und ziehen Images ungeprüft.

> [!NOTE]
> **Installation vor Version 1.3?** Das alte Skript kann sich nicht selbst aktualisieren. Lade einmal die neue Fassung, danach genügt der normale Aufruf:
> ```sh
> curl -fsSL -o tools/update.sh https://github.com/aemjay/Kilowatch/releases/latest/download/update.sh
> sudo sh tools/update.sh
> ```

**Hinweis in der App:** Unter **System & Datenqualität → Updates** kannst du eine tägliche Prüfung auf neue Versionen einschalten (Standard: aus). GitHub sieht dabei nur die IP-Adresse deines Hosts. **Jetzt prüfen** fragt einmalig.

## Versionen

Releases folgen [Semantic Versioning](https://semver.org/lang/de/) und erscheinen als signierte Images (amd64/arm64) unter `ghcr.io/aemjay/kilowatch`.

| Tag | Bedeutung |
|---|---|
| `1.2.3` | genau diese Version |
| `1.2` | neueste Fehlerbehebung von 1.2 |
| `1` | neueste 1.x-Version – **Standard** in `compose.yaml` |
| `latest` | neueste stabile Version, auch über Hauptversionen; für automatische Updates nicht empfohlen |
| `edge` | Entwicklungsstand, nur zum Testen |

Eine feste Version setzt du mit `--version 1.2.3` oder `KILOWATCH_VERSION=1.2.3` in der `.env`.

<details><summary>Signatur selbst prüfen</summary>

Jedes Image wird im GitHub-Workflow keyless mit [cosign](https://docs.sigstore.dev/) signiert. `update.sh` prüft das vor jedem Start, auch ohne installiertes cosign (es nutzt dann ein fest verankertes cosign-Image). Von Hand:

```sh
cosign verify ghcr.io/aemjay/kilowatch:1 \
  --certificate-identity-regexp '^https://github\.com/aemjay/Kilowatch/\.github/workflows/nas-image\.yml@refs/(heads/main|tags/v[0-9]+\.[0-9]+\.[0-9]+)$' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

Nur für selbst gebaute Images: `KILOWATCH_VERIFY=0` in der `.env` schaltet die Prüfung ab, `KILOWATCH_SIGNER` setzt eine andere Identität.
</details>

## Datenbankänderungen und Rückweg

Ändert ein Update das Schema, legt Kilowatch vorher eine geprüfte Sicherung `data/live/backups/pre-migration-v<alt>-to-v<neu>-<zeit>.sqlite3` an. Sie wird nie automatisch gelöscht. Releases mit Schemaänderung kennzeichnen die Release-Notizen.

Zurück zu einer älteren Version:

1. `sudo sh tools/update.sh --version 1.2.3`
2. Hat das Update die Datenbank geändert, startet die ältere Version nicht und nennt die Sicherung im Protokoll. Spiele sie wie unter [Datenbank wiederherstellen](BETRIEB.md#datenbank-wiederherstellen) ein. Messwerte seit dem Update fehlen dann.

<details><summary>Für Maintainer: Release erstellen</summary>

1. Version in `app/__init__.py` erhöhen (einzige Stelle).
2. Tag `v<Version>` pushen. Ohne Tag-Rechte: **Actions → „Kilowatch - Tests und NAS-Image“ → Run workflow**, Branch `main`, **release** ankreuzen; der Workflow legt Tag und Release auf dem getesteten Commit an.
3. Der Workflow testet beide Plattformen inklusive Update von der letzten Version, veröffentlicht die signierten Images und hängt `compose.yaml`, `update.sh`, `env.example` und die Importdateien an das Release.
4. Nach dem ersten Release das Paket unter GitHub → Packages → `kilowatch` einmalig auf **Public** stellen.
</details>

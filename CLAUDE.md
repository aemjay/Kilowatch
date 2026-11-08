# Kilowatch – Hinweise für Agenten-Sessions

Kilowatch liest den Stromzähler über die Tibber-Bridge lokal aus und zeigt Verbrauch, Kosten und Auswertungen. FastAPI und SQLite im Backend, eine Oberfläche aus reinem JavaScript ohne Build-Schritt in `app/static/`, Docker-Images für NAS-Systeme.

## Datenschutz und Pseudonyme

Gilt für alles, was ins Repository oder zu GitHub geht: Code, Doku, Konzepte, Berichte, Commit-Messages, Branch-Namen, PR- und Issue-Texte, Kommentare, Screenshots, Logs.

- **Keine personenbezogenen Daten des Inhabers:** kein Klarname, keine Mailadresse, kein Wohnort, keine Konto- oder Gerätenamen. Stattdessen die Rolle „Inhaber“ (bzw. „PO“).
- **Keine Angaben zu Hardware und Infrastruktur des Inhabers:** keine Rechner- oder Hostnamen, CPU-/GPU-Modelle, RAM/VRAM, Betriebssystem-Builds, IP-Adressen, Netzwerk-, Router- oder VM-Details, Seriennummern und keine lokalen Pfade mit Benutzernamen (`C:\Users\…`, `/home/…`).
- **Stattdessen Codes:** Stationen S1, S2, …; Testgeräte T1, T2, …. Neue Stationscodes vergibt der Inhaber. Wo eine Leistungsklasse technisch nötig ist, nur abstrakt (z. B. „T1: WebGPU ja, dedizierte GPU, Mittelklasse“). Interne Abläufe ebenfalls über Codes (Auftragsnummern, Stationscodes) statt Personen- oder Gerätebezug.
- **Die Zuordnung Code ↔ Klarname steht nie im Repository**, nur im Chat oder in einer lokalen, nicht versionierten Notiz.
- **Erlaubt sind allgemeine Beispiele**, die niemanden beschreiben: `192.168.1.0/24`, `bridge.example.lan`, Platzhalter wie `<Host>`, Synology als unterstützte Plattform. Screenshots nur aus dem Demo-Modus mit Beispieldaten.
- **Bestand:** Funde über den üblichen Branch-/PR-Weg im aktuellen Stand bereinigen. Git-History umschreiben oder Force-Push nur nach ausdrücklicher Freigabe des Inhabers, sonst Fundliste mit Empfehlung an den Inhaber.
- **Git-Identität:** Steht eine echte Mailadresse als Commit-Autor, nicht selbst ändern, sondern dem Inhaber melden.

## Entwicklung

```sh
python -m pytest                                    # Python 3.13, inklusive i18n-Prüfung
npm ci --ignore-scripts && npm test                 # Oberfläche mit jsdom, Node 24
for f in app/static/*.js; do node --check "$f"; done
```

- **Texte:** Oberflächentexte stehen deutsch im Code (`t('…')`). Übersetzungen liegen in `app/static/i18n/{en,nb,sv,nl}.json` mit dem deutschen Text als Schlüssel. `python tools/i18n_extract.py --missing` muss für jede Sprache 0 fehlende und 0 überzählige Schlüssel melden; `tests/test_i18n.py` prüft das.
- **Doku:** deutsch unter `docs/`, bei Verhaltensänderungen mitpflegen (API, Bedienung, Datenmodell, Benachrichtigungen, Prüfprotokoll).
- **Demo-Modus** zum Ausprobieren und für Screenshots: `DATA_DIR=<leerer Ordner> DEMO_MODE=true python -m uvicorn app.main:factory --factory --host 127.0.0.1 --port 8088`. Den Setup-Code zeigt `<DATA_DIR>/SETUP-CODE.txt`.
- **Datenbank:** Schemaänderungen kommen als neuer Eintrag in `MIGRATIONS` in `app/storage.py`; `SCHEMA_VERSION` ergibt sich daraus. Vor jeder Migration entsteht automatisch eine Sicherung.

## Release

1. `__version__` in `app/__init__.py` erhöhen und per PR (Squash-Merge) auf `main` bringen.
2. Den Workflow `.github/workflows/nas-image.yml` auf `main` per `workflow_dispatch` mit `release: true` starten (alternativ Tag `vX.Y.Z` pushen). Er testet, baut und signiert die Images (`X.Y.Z`, `X.Y`, `X`, `latest`) für amd64 und arm64 und legt Tag und GitHub-Release mit den Installationsdateien an.
3. Nutzer aktualisieren mit `sudo sh <Projektordner>/tools/update.sh`.

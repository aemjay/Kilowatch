# Drittkomponenten

Kilowatch steht unter **GPL-3.0-or-later** (Text in `LICENSE`). Die Komponenten unten behalten ihre eigenen Lizenzen.

- **SML:** [`smllib`](https://github.com/spacemanspiff2007/SmlLib) (GPL-3.0-or-later).
- **Laufzeit:** FastAPI, Starlette, Uvicorn, HTTPX, Pydantic und ihre Abhängigkeiten aus den in `requirements.txt` festgelegten PyPI-Paketen, dazu Python, die IANA-Zeitzonendaten und die Systemkomponenten des Docker-Basisimages.
- **Verschlüsselung:** [cryptography/Fernet](https://cryptography.io/en/latest/fernet/) samt CFFI und OpenSSL.
- **MQTT (optional):** Eclipse Mosquitto als unverändertes offizielles Image, nicht Teil des Kilowatch-Images. Siehe seine [Lizenzinformationen](https://github.com/eclipse-mosquitto/mosquitto/blob/master/LICENSE.txt).
- **Tests:** [jsdom](https://github.com/jsdom/jsdom) und Abhängigkeiten, nur auf Entwicklungsrechnern und in der CI; `package-lock.json` legt die Versionen fest, sie landen nicht im Image.
- **Vorarbeit:** Bridge-Vorbereitung und Betrieb ohne Tibber-Tarif wurden anhand der Dokumentation von [marq24/ha-tibber-pulse-local](https://github.com/marq24/ha-tibber-pulse-local) geprüft. Es wurde kein Code daraus übernommen; die Test-Telegramme sind künstlich erzeugt.

Wer ein gebautes Image weitergibt, muss die Lizenzhinweise seiner Komponenten und den zugehörigen Quellcode verfügbar halten. Das Repository enthält den App-Quellcode, die Docker-Bauanleitung und festgelegte Paketversionen. Diese Hinweise ersetzen keine Lizenztexte.

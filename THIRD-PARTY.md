# Drittkomponenten

Der eigene Quellcode von Kilowatch wird unter GPL-3.0-or-later bereitgestellt. Der vollständige Lizenztext liegt in `LICENSE`. Die Anwendung verwendet `smllib` unter GPL-3.0-or-later; siehe den [Upstream](https://github.com/spacemanspiff2007/SmlLib) und die in der Python-Distribution enthaltenen Lizenzhinweise.

Weitere Laufzeitkomponenten kommen aus den in `requirements.txt` festgelegten PyPI-Paketen. FastAPI, Starlette, Uvicorn, HTTPX, Pydantic und ihre Abhängigkeiten behalten ihre jeweiligen mitgelieferten Lizenzen. Python und IANA-Zeitzonendaten behalten ebenfalls ihre eigenen Lizenzbedingungen. Das Docker-Basisimage enthält zusätzliche Systemkomponenten mit deren Lizenzen.

Eclipse Mosquitto wird ausschließlich als optionales unverändertes offizielles Containerimage verwendet; seine [Lizenzinformationen](https://github.com/eclipse-mosquitto/mosquitto/blob/master/LICENSE.txt) gelten weiter. Es ist kein Teil des Kilowatch-Python-Images.

Die lokale Geheimnisspeicherung verwendet [cryptography/Fernet](https://cryptography.io/en/latest/fernet/); die mitgelieferten Apache-/BSD-Lizenzhinweise sowie die Lizenzen der CFFI-/OpenSSL-Komponenten gelten weiter. Passende Paketversionen stehen in `requirements.txt`.

Die DOM-Tests nutzen [jsdom](https://github.com/jsdom/jsdom) und seine Abhängigkeiten ausschließlich auf Entwicklungsrechnern und in CI. `package-lock.json` legt die Versionen fest; diese Pakete werden nicht ins App-Image kopiert.

Die Bridge-Vorbereitung und das Nichtkunden-Konzept wurden anhand der Dokumentation von [marq24/ha-tibber-pulse-local](https://github.com/marq24/ha-tibber-pulse-local) geprüft. Es wurde kein Home-Assistant-Integrationscode in dieses Projekt übernommen. Die konkrete SML-Verarbeitung verwendet die reguläre Python-Bibliothek, die separaten Unit-Test-Telegramme sind künstlich erzeugt.

Beim Weitergeben eines gebauten Images müssen auch die Lizenzhinweise seiner Komponenten und der zugehörige korrespondierende Quellcode verfügbar bleiben. Das Repository enthält den eigenen App-Quellcode, die Docker-Bauanleitung und festgelegte Paketversionen. Diese Hinweise ersetzen keine komponentenspezifischen Lizenztexte.

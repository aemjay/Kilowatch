# IT-Security- und Datenschutz-Baseline

Stand: 2026-11-08 · Quelle und führende Fassung: https://claude.ai/artifact/4VDhdnYaFrxc26Qi4PjCXx

> Diese Datei ist eine Kopie der Baseline für dieses Repo. Änderungen erfolgen in der führenden Fassung und werden hierher übernommen.

## 1. Zweck und Geltungsbereich

Diese Baseline legt die Mindestanforderungen fest, die jedes eigene Softwareprodukt erfüllen muss – im fertigen Produkt und im Weg dorthin. Sie ist bewusst unabhängig von Architektur, Plattform und Geschäftsmodell formuliert, damit sie für eine lokale Desktop-Anwendung genauso gilt wie für einen mandantenfähigen Cloud-Dienst.

- **Gilt für:** alle eigenen Softwareprojekte, unabhängig davon, ob sie lokal auf dem Gerät des Nutzers laufen, als Browser-Erweiterung oder Mobile App ausgeliefert werden oder als Web-Anwendung mit Backend betrieben werden; kostenlos oder kommerziell, Open Source oder proprietär.
- **Zwei Ebenen:** *Produkt* (was die Software mit Daten tut und wie angreifbar sie ist) und *Prozess* (wie sie entsteht und betrieben wird – Repos, Abhängigkeiten, Testdaten, KI-Agenten, Infrastruktur).
- **Verbindlichkeit:** MUSS = ohne Ausnahme vor dem ersten öffentlichen Release · SOLL = Standard, begründete Abweichung erlaubt · KANN = Empfehlung. Anforderungen, die nur für bestimmte Architekturklassen gelten, sind in Abschnitt 5 entsprechend gekennzeichnet.
- **Arbeitsweise:** Jedes Projekt wird bei Projektstart einer Schutzbedarfsklasse zugeordnet und erhält ein Projektprofil und ein kurzes Threat Model (Abschnitt 6). Vor jedem Release wird die Checkliste in Abschnitt 9 abgearbeitet. Abweichungen von MUSS-Anforderungen werden mit Begründung und Frist in einer `EXCEPTIONS.md` im Repo festgehalten.
- **Abgrenzung:** Die Baseline regelt private Softwareprojekte, die ein Product Owner mit KI-Agenten umsetzt. Berufliche Daten, Systeme und Zugänge bleiben vollständig außerhalb dieser Projekte; eine projektspezifische Zuordnung steht im Anhang und kann ohne Änderung des Grundsatzteils fortgeschrieben werden.

## 2. Leitprinzipien

Acht Prinzipien entscheiden im Zweifel. Wenn eine Detailanforderung auf eine neue Architektur nicht passt, gilt das Prinzip.

1. **Daten so nah am Nutzer wie möglich.** Verarbeitung findet bevorzugt auf dem Gerät des Nutzers statt. Ein Backend verarbeitet nur, was lokal nicht sinnvoll geht, und speichert nur, was für den Dienst zwingend ist.
2. **Datenminimierung als Default.** Verarbeitet wird nur, was die Funktion braucht; jede optionale Datennutzung ist standardmäßig aus; Aufbewahrungsfristen sind definiert und technisch durchgesetzt.
3. **Keine stille Verarbeitung.** Jeder Datenfluss – zwischen Gerät und Backend, zu Dienstleistern, zu KI-Diensten – ist dokumentiert, begründet und für Laien erklärt; Telemetrie, Analytics und Crash-Reports nur per Opt-in.
4. **Der Mensch bestätigt Außenwirkung.** Alles, was im Namen des Nutzers Dritte erreicht oder Daten unwiderruflich verändert, wird vom Nutzer freigegeben – nie von einer Automatik oder einem Modell allein.
5. **Alles von außen ist feindlich.** Nutzereingaben, Dateien, fremde Inhalte, API-Antworten und Modellausgaben sind Daten, keine Anweisungen; Vertrauensgrenzen sind im Design benannt.
6. **Secure by Default, least privilege.** Sichere Voreinstellungen, minimale Berechtigungen für Nutzer, Dienste und Administratoren, keine Remote-Code-Nachladung, keine abgeschalteten Sicherheitsprüfungen „damit es läuft“.
7. **Nachvollziehbar statt vertrauenswürdig.** Offener oder zumindest prüfbarer Code, reproduzierbare Builds, prüfbare Hashes, Audit-Logs und ein lesbares Threat Model ersetzen das Versprechen „wir sammeln nichts“ durch Belegbarkeit.
8. **Verhältnismäßig.** Der Aufwand folgt dem Schutzbedarf (Abschnitt 6): Ein Dienst mit Konten und Nutzerdaten im Backend braucht mehr als ein lokales Werkzeug ohne Außenverbindung.

## 3. Produkt-Baseline Datenschutz

Privacy by Design und by Default (DSGVO Art. 25, DSG Art. 7) in sechzehn prüfbaren Anforderungen. Die erste Frage jedes Projekts ist die Rollenfrage: Solange keine personenbezogenen Daten zum Entwickler oder Betreiber fließen, ist der Nutzer selbst Verantwortlicher seiner lokalen Verarbeitung. Sobald ein Backend, ein Konto oder ein Opt-in Daten entgegennimmt, wird der Betreiber Verantwortlicher mit allen Pflichten aus Kapitel III und IV der DSGVO.

| Nr. | Anforderung | Stufe | Hinweise / Prüfung |
| --- | --- | --- | --- |
| DS-1 | Datenflussdiagramm je Projekt: welche Daten, woher, wohin, warum, wie lange, auf welcher Rechtsgrundlage | MUSS | `PRIVACY.md` im Repo; jede Außenverbindung und jeder Dienstleister ist eine Zeile |
| DS-2 | Rollen geklärt: Wer ist Verantwortlicher, wer Auftragsverarbeiter, wer Dritter? Bei eigenem Backend: Verzeichnis der Verarbeitungstätigkeiten (Art. 30) | MUSS | Entscheidet, ob Abschnitt 5 Klasse C greift |
| DS-3 | Zweck je Verarbeitung dokumentiert; keine Zweckänderung ohne neue Rechtsgrundlage oder neues Opt-in | MUSS | Gilt auch für Produktverbesserung, Training von Modellen und Statistik |
| DS-4 | Schwellwertprüfung für eine Datenschutz-Folgenabschätzung (Art. 35) bei Projektstart; DSFA durchführen, wenn Profiling, besondere Kategorien, Standortverläufe, große Datenmengen oder neue Technologien betroffen sind | MUSS | Ergebnis mit Datum in `PRIVACY.md`, auch wenn keine DSFA nötig ist |
| DS-5 | Speicherung lokal, wo immer möglich; im Backend nur das Minimum, pseudonymisiert, wo der Zweck es zulässt; Schlüssel und Tokens ausschließlich in Plattform-Schlüsselspeichern oder einem Secrets-Manager | MUSS | Niemals Schlüssel in Klartext-Config, `localStorage` oder Logs |
| DS-6 | Verschlüsselung ruhender Daten (Gerät: Plattformmittel; Backend: Datenbank- und Speicherverschlüsselung) und in Übertragung (TLS 1.2+, bevorzugt 1.3) | MUSS | Ende-zu-Ende-Verschlüsselung prüfen, wenn der Betreiber Inhalte nicht sehen muss |
| DS-7 | Löschkonzept: Aufbewahrungsfristen je Datenart, automatische Löschung, Nutzer kann Konto und alle Daten vollständig löschen und in offenem Format exportieren | MUSS | Auch Backups, Logs und Caches berücksichtigen; Löschen prüfbar testen |
| DS-8 | Betroffenenrechte technisch unterstützt: Auskunft, Berichtigung, Löschung, Export innerhalb der Frist von einem Monat ohne Handarbeit möglich | MUSS bei Backend | Self-Service in der App bevorzugt |
| DS-9 | Dienstleister und Unterauftragnehmer (Hosting, E-Mail-Versand, KI-APIs, Monitoring) nur mit Auftragsverarbeitungsvertrag, geprüftem Datenstandort und Transfermechanismus bei Drittlandübermittlung | MUSS bei Backend | Liste der Dienstleister ist Teil der Datenschutzerklärung; EU/CH-Hosting bevorzugt |
| DS-10 | KI-Dienste in der Cloud nur per Opt-in und mit transparenter Anzeige, was gesendet wird; bei eigenem Schlüssel des Nutzers bleibt dieser Verantwortlicher, bei Schlüssel des Betreibers gilt DS-9 | MUSS | Opt-in pro Funktion widerrufbar; Default lokal oder aus |
| DS-11 | Keine Telemetrie, Analytics oder Crash-Reports ohne Opt-in; wenn aktiviert, ohne Inhalte und ohne stabile Geräte-IDs; keine Drittanbieter-SDKs für Analytics oder Werbung | MUSS | Reine Server-Logs zur Fehlersuche sind zulässig, kurz aufbewahrt und IP-gekürzt |
| DS-12 | Externe Abfragen (Webseiten, Logos, Karten, Suchdienste) so sparsam wie möglich: kein Referer, keine Tracking-Parameter, lokaler Cache, erkennbarer Hinweis, dass die Anfrage das Gerät verlässt | SOLL | Offline-Alternative anbieten, wo möglich |
| DS-13 | Standort-, Gesundheits- und andere sensible Daten bleiben auf dem Gerät oder werden nur mit ausdrücklicher Einwilligung verarbeitet; abgeleitete Ereignisse statt Rohdaten speichern | MUSS | Rohdaten nur temporär und mit definiertem Ende |
| DS-14 | Inhalte Dritter (E-Mails, Dokumente, Webseiten, Chatverläufe) werden so wenig wie möglich kopiert: Indizes und Metadaten statt Volltextkopien | MUSS | Volltext nur, wenn die Funktion ihn zwingend braucht |
| DS-15 | Datenschutzhinweis in Laiensprache im Repo, in der App und – bei Backend – als vollständige Datenschutzerklärung nach Art. 13/14; Store- und Marktplatzangaben stimmen mit dem Verhalten überein | MUSS | „Diese App sendet keine Daten“ ist eine prüfbare Aussage und wird per Netzwerkmitschnitt belegt |
| DS-16 | Keine Dark Patterns: Opt-ins neutral formuliert, Ablehnen so leicht wie Zustimmen, Einwilligungen protokolliert und widerrufbar; Consent-Banner nur, wenn tatsächlich einwilligungspflichtige Technik eingesetzt wird | SOLL | Besser: auf einwilligungspflichtige Technik verzichten |

## 4. Produkt-Baseline IT-Security

Die technischen Mindestanforderungen folgen OWASP ASVS (Web und Backend), OWASP MASVS (Mobile) und den OWASP Top 10 für LLM-Anwendungen. Anforderungen ohne Zusatz gelten für jede Architektur; „bei Backend“ markiert, was erst mit einem eigenen Server oder Cloud-Dienst greift.

| Nr. | Anforderung | Stufe | Hinweise / Prüfung |
| --- | --- | --- | --- |
| SEC-1 | Leichtgewichtiges Threat Model je Projekt nach den vier Fragen: Woran arbeiten wir? Was kann schiefgehen? Was tun wir dagegen? Reicht das? Vertrauensgrenzen sind eingezeichnet | MUSS | `THREAT_MODEL.md`, ein bis zwei Seiten, bei jedem größeren Feature aktualisiert |
| SEC-2 | Least Privilege überall: Berechtigungen, Hosts, APIs, Datenbankrollen, Cloud-IAM und Admin-Zugänge auf das Minimum; optionale Rechte erst bei Bedarf | MUSS | Berechtigungs-Diff ist Teil jedes Reviews |
| SEC-3 | Alle externen Inhalte sind nicht vertrauenswürdig: Eingaben werden serverseitig bzw. an der Vertrauensgrenze validiert, Ausgaben kontextgerecht escaped, Abfragen parametrisiert | MUSS | Kein `innerHTML` mit Fremdinhalt, keine String-Konkatenation in SQL, HTML-Mails nur sanitisiert |
| SEC-4 | Authentifizierung nie selbst erfinden: Passkeys oder etablierte Identitätsanbieter (OIDC/OAuth 2.1); falls Passwörter: Argon2id, Prüfung gegen bekannte Leaks, MFA für alle Konten mit erweiterten Rechten | MUSS bei Backend | Sessions kurzlebig, serverseitig widerrufbar, sichere Cookie-Flags |
| SEC-5 | Autorisierung auf Objektebene: Jede Anfrage prüft, ob der Aufrufer das konkrete Objekt sehen oder ändern darf; strikte Mandantentrennung in Datenmodell und Abfragen | MUSS bei Backend | Testfall: Nutzer A greift per ID auf Objekt von Nutzer B zu |
| SEC-6 | Prompt Injection und Excessive Agency: Modellausgaben lösen nie direkt Aktionen aus; Werkzeugaufrufe nur über strukturierte, geprüfte Schnittstellen mit eigener Autorisierung; Außenwirkung braucht Nutzerbestätigung | MUSS bei KI | Testfall: präparierte Eingabe mit Anweisungen darf nichts auslösen |
| SEC-7 | Keine Secrets im Code, Repo, Build, Image oder Log; Nutzerschlüssel nur im Plattform-Schlüsselspeicher, Betreiberschlüssel nur im Secrets-Manager mit Rotation | MUSS | Secret-Scanning aktiv (Abschnitt 7) |
| SEC-8 | Transport nur über TLS mit aktiver Zertifikatsprüfung; HSTS bei Web-Anwendungen; kein HTTP, kein Abschalten der Prüfung in Tests, die ins Release gelangen können | MUSS | Allowlist der erlaubten Hosts im Code, nicht nur in der Konfiguration |
| SEC-9 | Abhängigkeiten gepinnt (Lockfile), automatisch auf Schwachstellen geprüft, keine neue Abhängigkeit ohne kurze Prüfung von Herkunft, Pflege und Lizenz; Container-Images ebenfalls gescannt | MUSS | Dependabot oder Renovate, `npm audit`, OSV-Scanner, Trivy |
| SEC-10 | Artefakte von außen (Modellgewichte, Wissenspakete, Datenbanken, Plugins) nur über HTTPS von bekannter Quelle, mit Hash- oder Signaturprüfung gegen einen im Release hinterlegten Wert | MUSS | Testfall: manipulierte Datei wird abgelehnt |
| SEC-11 | Content Security Policy und Sicherheits-Header für alle Web-Oberflächen; kein `eval`, keine Inline-Skripte, keine Remote-Code-Nachladung | MUSS | Auch Shader, Plugins und Templates sind Code: nur aus dem Paket |
| SEC-12 | Importformate robust gegen manipulierte Dateien: Größenlimits, strikte Parser, Zeitlimits, Fehler werden abgefangen; Erweiterungen sind deklarative Daten, kein ausführbarer Code | MUSS | Kaputte und übergroße Dateien in der Testsuite |
| SEC-13 | Missbrauchsschutz: Rate Limiting, Größen- und Kostenlimits pro Nutzer und global, Schutz vor automatisierter Registrierung; Budget-Alarm bei Cloud-Kosten | MUSS bei Backend | Besonders bei KI-APIs, die pro Aufruf Geld kosten |
| SEC-14 | Logging ohne personenbezogene Inhalte und ohne Secrets; Debug-Logs und Entwickler-Endpunkte im Release aus; bei Backend: zentrale Logs mit definierter Aufbewahrung, Alarm bei Anomalien (Login-Fehler, Fehlerquoten, Kosten) | MUSS | Audit-Log für Admin-Aktionen und Datenexporte |
| SEC-15 | Backups verschlüsselt, getrennt vom Produktivsystem, regelmäßig; Wiederherstellung mindestens halbjährlich getestet; Backups unterliegen dem Löschkonzept | MUSS bei Backend | Ein ungetestetes Backup gilt als nicht vorhanden |
| SEC-16 | Infrastruktur als Code, gehärtete Basis-Images, automatische Sicherheitsupdates, getrennte Umgebungen für Entwicklung, Test und Produktion; keine Produktivdaten in Nicht-Produktivumgebungen | MUSS bei Backend | Admin-Zugang nur mit MFA, bevorzugt über kurzlebige Zugänge statt Dauerschlüssel |
| SEC-17 | Releases signiert und reproduzierbar; Changelog nennt sicherheitsrelevante Änderungen; Security-Fixes als eigenes Release | SOLL | Store-Signatur bzw. Image-Signatur plus signierter Git-Tag |
| SEC-18 | Integrität gespeicherter Daten: Schema-Versionierung, getestete Migrationen, Export oder Backup vor riskanten Migrationen | SOLL | Ein Update darf keine Nutzerdaten verlieren |
| SEC-19 | Krypto nur mit Plattform- oder etablierten Bibliotheken, keine eigenen Verfahren, aktuelle Algorithmen (AES-GCM, ChaCha20-Poly1305, Argon2id, Ed25519) | MUSS | Schlüsselverwaltung ist Teil des Threat Models |
| SEC-20 | Web-Anwendungen vor Release mit einem automatisierten Scanner (z. B. OWASP ZAP) geprüft; ab Schutzbedarf hoch zusätzlich ein externer Penetrationstest | SOLL bei Backend | Befunde ab Stufe Medium vor Release beheben oder in `EXCEPTIONS.md` |

## 5. Anforderungen nach Architekturklasse

Jedes Projekt gehört zu mindestens einer von vier Klassen; die Klasse bestimmt, welche Zusatzanforderungen zu Abschnitt 3 und 4 gelten. Ein Produkt mit App und Backend erfüllt beide Klassen, eine KI-Komponente kommt immer als Querschnitt hinzu.

| Klasse | Beschreibung | Typische Vertreter |
| --- | --- | --- |
| A – Lokale Client-Software | Läuft vollständig auf dem Gerät des Nutzers, kein eigener Server | Desktop-Anwendungen, Browser-Erweiterungen, Mail-Client-Add-ons, lokale Browser-Demos |
| B – Mobile Apps | Wird über App-Stores ausgeliefert, nutzt Gerätesensoren und Plattform-Sandboxes | iOS- und Android-Apps, auch ohne Backend |
| C – Web-Anwendungen und Cloud-Dienste | Eigener Server oder Cloud-Dienst, der Nutzerdaten entgegennimmt, speichert oder verarbeitet | SaaS, Web-Apps mit Konto, APIs, Multi-Tenant-Dienste |
| D – KI-Komponenten (Querschnitt) | Sprachmodelle oder andere Modelle lokal oder über API, mit oder ohne Werkzeugzugriff | Assistenten, Agenten, Klassifikatoren, RAG-Systeme |

**Klasse A – Lokale Client-Software**

- Berechtigungen des Erweiterungs- oder Add-on-Modells auf das Minimum; breite Host- oder Postfachzugriffe nur, wenn die Kernfunktion sie verlangt, und dann zur Laufzeit optional anforderbar.
- Vollständige Funktion ohne Netzwerk nach der Erstinstallation ist der prüfbare Beleg für „lokal“; notwendige Außenverbindungen (Updates, Artefakt-Downloads) sind einzeln gelistet.
- Synchronisationsspeicher der Plattform (z. B. Browser-Sync) nie für Inhalte oder Schlüssel.
- Fremdinhalte, auf die der Client Zugriff hat (Webseiten, E-Mails, Dokumente), sind die Hauptquelle für Injection: Analyse auf vom Nutzer gewählte Bereiche begrenzen, Aktionen nur mit Bestätigung.
- Marktplatzregeln (Chrome Web Store, AMO, Microsoft Store u. a.) einhalten: Single Purpose, lesbarer Quellcode bzw. Build-Anleitung, Datenschutzangaben, kein Remote-Code.

**Klasse B – Mobile Apps**

- Berechtigungen erst zur Laufzeit und mit Begründung im Kontext; sensorbasierte Rechte (Standort, Mikrofon, Kamera, Gesundheit) standardmäßig auf „Nur während der Nutzung“; Hintergrundzugriff nur sichtbar, begrenzt und jederzeit beendbar.
- Schlüssel und Tokens im Keychain bzw. Keystore; Daten in der App-Sandbox; Verhalten bei Cloud-Backups der Plattform bewusst entscheiden und dokumentieren.
- Store-Datenschutzangaben (Play Data Safety, Apple App Privacy Details) direkt aus DS-1 ableiten; eine App ohne Datenerhebung deklariert genau das.
- Keine Drittanbieter-SDKs für Analytics, Werbung oder Crash-Reporting ohne Opt-in; Kartendienste und andere Online-Dienste nach DS-12 behandeln oder offline lösen.
- Gerätesperre voraussetzen, nicht ersetzen: sensible Daten optional zusätzlich verschlüsseln, kein eigenes Passwortsystem; Zertifikats-Pinning erwägen, wenn ein eigenes Backend existiert.

**Klasse C – Web-Anwendungen und Cloud-Dienste**

- *Rolle und Pflichten:* Der Betreiber ist Verantwortlicher. Vor dem Start liegen vor: Verzeichnis der Verarbeitungstätigkeiten, Datenschutzerklärung, Impressum, AV-Verträge mit allen Dienstleistern, DSFA-Schwellwertprüfung, Prozess für Betroffenenanfragen und für die 72-Stunden-Meldung nach Art. 33.
- *Hosting:* Anbieter mit Standort in EU oder Schweiz und anerkannter Zertifizierung (ISO 27001, BSI C5, SOC 2) bevorzugen; Region fest konfigurieren; Drittlandtransfers nur mit Transfermechanismus und Dokumentation.
- *Identität und Zugriff:* Passkeys oder OIDC für Nutzer, MFA für jeden Admin- und Cloud-Konsolen-Zugang, kurzlebige Zugangsdaten statt Dauerschlüssel, getrennte Rollen für Deployment und Betrieb, Audit-Log aller administrativen Aktionen.
- *Trennung:* Mandanten im Datenmodell und in jeder Abfrage getrennt; Entwicklungs-, Test- und Produktivumgebung getrennt; keine Produktivdaten außerhalb der Produktion; Netzwerksegmentierung, Datenbank nie öffentlich erreichbar.
- *Betrieb:* Infrastruktur als Code, automatische Patches, zentrales Logging mit Alarmen, Statusseite, dokumentierte Wiederherstellung, getestete Backups, Kosten- und Missbrauchslimits, TLS-Konfiguration nach aktuellem Stand (z. B. Mozilla Intermediate).
- *Ende des Dienstes:* Von Anfang an definieren, wie Nutzer ihre Daten erhalten und wie vollständig gelöscht wird, wenn der Dienst eingestellt wird.

**Klasse D – KI-Komponenten**

- Vertrauensgrenze um das Modell ziehen: Alles, was ins Modell geht, kann Anweisungen enthalten; alles, was herauskommt, ist ungeprüfte Eingabe für den nächsten Schritt.
- Werkzeuge mit Außenwirkung (Senden, Löschen, Bezahlen, Veröffentlichen) nur mit expliziter Nutzerbestätigung; Werkzeuge prüfen ihre Autorisierung selbst, nicht das Modell.
- Modelle, Gewichte und Wissensbasen als Artefakte nach SEC-10 behandeln; Lizenz und Nutzungsbedingungen der Modelle dokumentieren.
- Bei Cloud-Modellen: Anbieter nach DS-9 prüfen, Trainingsnutzung ausschließen oder offenlegen, Eingaben minimieren, Aufbewahrung beim Anbieter kennen.
- Grenzen transparent machen: Quellenangabe, Kennzeichnung generierter Inhalte, kein Einsatz für rechtlich oder gesundheitlich bindende Entscheidungen ohne menschliche Prüfung; Anforderungen der EU-KI-Verordnung je nach Einsatzzweck prüfen.

## 6. Schutzbedarf und Projektprofil

Der Schutzbedarf wird bei Projektstart in einer von vier Stufen festgelegt und entscheidet, wie viel von dieser Baseline mit welcher Tiefe greift. Maßgeblich ist die höchste Stufe, die eines der Kriterien auslöst.

| Stufe | Kriterien (eines genügt) | Konsequenzen |
| --- | --- | --- |
| Niedrig | Keine personenbezogenen Daten; keine Außenverbindung; keine Aktionen im Namen des Nutzers | MUSS-Anforderungen ohne Backend-Zusatz; Threat Model als halbe Seite; Checkliste gekürzt |
| Mittel | Personenbezogene Daten nur lokal; einzelne begründete Außenverbindungen; Standort- oder Nutzungsdaten auf dem Gerät | Volle Baseline der zutreffenden Klasse; Netzwerkmitschnitt als Nachweis; Lösch- und Exportfunktion |
| Hoch | Zugriff auf große Mengen fremder Kommunikation oder Dokumente; Aktionen mit Außenwirkung im Namen des Nutzers; eigenes Backend mit Nutzerkonten; KI-Agenten mit Werkzeugzugriff | Zusätzlich: unabhängiger Review-Agent pro Merge, Injection-Tests in der Testsuite, DSFA-Schwellwertprüfung dokumentiert, automatisierter Web-Scan |
| Sehr hoch | Besondere Kategorien (Gesundheit, Religion, politische Meinung u. a.), Daten von Kindern, Zahlungsdaten, Mandantenfähigkeit mit Fremddaten, Entscheidungen mit Rechtswirkung | Zusätzlich: vollständige DSFA, externer Penetrationstest vor Release, Ende-zu-Ende-Verschlüsselung prüfen, Vier-Augen-Prinzip für Deployments |

**Projektprofil** (Vorlage, liegt als Kopf von `THREAT_MODEL.md` in jedem Repo)

| Feld | Inhalt |
| --- | --- |
| Projekt | Name, Kurzbeschreibung, Lizenz |
| Architekturklassen | A, B, C und/oder D nach Abschnitt 5 |
| Schutzbedarf | Niedrig / Mittel / Hoch / Sehr hoch mit dem auslösenden Kriterium |
| Rolle nach DSGVO | Nutzer ist Verantwortlicher / Betreiber ist Verantwortlicher / Auftragsverarbeiter |
| Kritische Daten | Welche Datenarten, wo gespeichert, wie lange |
| Vertrauensgrenzen | Welche Eingaben von außen kommen und wo sie geprüft werden |
| Größte Risiken | Drei bis fünf Szenarien aus dem Threat Model, priorisiert |
| Maßnahmen über die Baseline hinaus | Was dieses Projekt zusätzlich braucht |
| Ausnahmen | Verweis auf `EXCEPTIONS.md` |
| Letzte Überprüfung | Datum, nächster Termin |

Die Zuordnung der laufenden Projekte steht im Anhang und ist bewusst vom Grundsatzteil getrennt.

## 7. Baseline für den Entwicklungsprozess

Ein Repo ist vom ersten Commit an als öffentlich zu behandeln – auch seine Historie, auch wenn es privat beginnt. Die Prozessregeln verhindern, dass Secrets, echte Daten oder ungeprüfte Abhängigkeiten dorthin gelangen, und halten Beruf und Privatprojekte sauber getrennt.

**Konten und Zugänge**

- Code-Hosting, Paketregister, Marktplätze, Cloud-Konsolen und Domain-Registrare: Passkey oder Hardware-Schlüssel als zweiter Faktor (MUSS), eigenes Passwort pro Dienst im Passwortmanager, Wiederherstellungscodes offline.
- Getrennte Identitäten: private Projekte nur mit privaten Konten und privater E-Mail-Adresse; keine beruflichen Zugänge, Geräte-Policies oder Daten in Privatprojekten (MUSS).
- Signierte Commits und Tags (SOLL); Branch Protection auf `main`: kein Direkt-Push, Review oder grüne Checks vor Merge; für Klasse C getrennte Rollen für Code, Deployment und Betrieb.

**Repos und Secrets**

- `.gitignore` deckt `.env`, Schlüsseldateien, Keystores, Zertifikate, lokale Datenbanken und Testdatensätze ab, bevor der erste Commit entsteht (MUSS).
- Secret Scanning mit Push Protection aktiv; zusätzlich lokal ein Pre-Commit-Hook mit gitleaks (MUSS).
- Ein versehentlich committeter Schlüssel gilt als kompromittiert: sofort rotieren, nicht nur aus der Historie entfernen.
- Signaturschlüssel und Betreiber-Secrets liegen verschlüsselt außerhalb des Repos – im Secrets-Manager oder Passwortmanager mit Offline-Backup; Zugriff ist protokolliert.

**Testdaten**

- Niemals echte personenbezogene Daten im Repo, in Issues, in Tickets oder in Prompts (MUSS). Eigene Daten des Entwicklers sind ebenfalls personenbezogene Daten.
- Pro Datenart existiert ein synthetischer Fixture-Satz (erfundene Personen, Domains der Form `example.com`, generierte Inhalte, künstliche Messreihen), der alle Tests trägt.
- Manuelle Tests mit echten Konten nur in eigenen Test-Profilen und Testkonten ohne private Logins; für Klasse C nie mit Produktivdaten in Nicht-Produktivumgebungen.

**Entwicklungsrechner**

- Festplattenverschlüsselung, automatische Updates, Standardbenutzer statt Administrator für die tägliche Arbeit (MUSS).
- Entwicklungswerkzeuge und KI-Agenten laufen in einem eigenen Benutzerprofil, in WSL oder in einem Container mit Zugriff nur auf die Projektordner (SOLL; Details in Abschnitt 8).
- Keine Signatur- oder API-Schlüssel im Klartext auf dem Rechner; Betriebssystem-Schlüsselspeicher oder Passwortmanager nutzen.

**Supply Chain**

- Lockfiles committen; Dependabot oder Renovate wöchentlich; neue Abhängigkeiten erst nach kurzem Blick auf Pflegezustand, Verbreitung, Install-Skripte und Lizenz (MUSS).
- Vorsicht bei KI-vorgeschlagenen Paketnamen: Existenz und Herkunft im Register prüfen, Typosquatting ausschließen (MUSS).
- Lizenzregister je Projekt: Code-Abhängigkeiten nach SPDX-Kennung, dazu Modelle, Wissensbasen, Kartendaten, Schriften und Medien mit ihren Nutzungsbedingungen; Copyleft-Verträglichkeit mit der eigenen Lizenz prüfen.
- SBOM im CycloneDX-Format ab Version 1.0 jedem Release beilegen (SOLL); Container-Images schlank, aus vertrauenswürdigen Basis-Images, gepinnt und gescannt.

**CI, Build und Deployment**

- CI-Pipelines mit minimalen Berechtigungen, Actions und Images auf Commit-SHA bzw. Digest gepinnt, Secrets nur in geschützten Umgebungen (MUSS).
- Pipeline: Lint, Tests, Dependency-Audit, Secret-Scan; statische Analyse mit CodeQL oder Semgrep (SOLL).
- Release-Builds reproduzierbar aus einem Tag; Marktplätze erhalten Build-Anleitung und Quell-Archiv.
- Klasse C: Deployment nur über die Pipeline, nie von Hand; Infrastruktur als Code im Repo; Rollback ist getestet; Migrationen laufen rückwärtskompatibel.

**Pflichtdateien je Repo:** `README.md`, `LICENSE`, `SECURITY.md` (Meldeweg), `PRIVACY.md` (Datenflüsse, DS-1), `THREAT_MODEL.md` (Projektprofil und SEC-1), `EXCEPTIONS.md` (Abweichungen), `AGENTS.md` oder `CLAUDE.md` (Regeln für KI-Agenten, Abschnitt 8); bei Klasse C zusätzlich `RUNBOOK.md` (Betrieb, Wiederherstellung, Vorfallreaktion).

## 8. Sichere KI-gestützte Entwicklung

KI-Agenten schreiben den Großteil des Codes; der Product Owner trägt die Verantwortung. Daraus folgen drei Pflichten: Agenten bekommen nur, was sie brauchen; alles mit Außenwirkung bleibt beim Menschen; nichts wird gemergt, was der PO nicht erklären kann.

**Was Agenten sehen dürfen**

- Keine echten personenbezogenen Daten im Kontext: keine echten E-Mails, Tracks, Chatverläufe, Schlüssel oder Zugangsdaten – Agenten arbeiten ausschließlich mit den synthetischen Fixtures aus Abschnitt 7 (MUSS).
- Keine beruflichen Inhalte in Privatprojekt-Sessions, keine Privatprojekt-Inhalte in beruflichen Werkzeugen (MUSS).
- Vor der Nutzung eines KI-Dienstes klären, ob Eingaben zum Training verwendet werden, und die Einstellung dokumentieren; für Open-Source-Code ist das unkritisch, für Konzepte und Testdaten eine bewusste Entscheidung.

**Was Agenten dürfen**

- Agenten laufen in einer Sandbox (Container, WSL oder eigenes Benutzerprofil) mit Zugriff nur auf den Projektordner; keine Zugangsdaten in Umgebungsvariablen, kein Zugriff auf Passwortmanager, Browserprofile oder das Mailprogramm (MUSS).
- Aktionen mit Außenwirkung – `git push` auf `main`, Releases, Store-Uploads, Veröffentlichen von Paketen, Löschen von Daten, Ausgaben mit Kosten – führt der PO selbst aus oder gibt sie einzeln frei (MUSS).
- Alles, was ein Agent liest, kann Anweisungen enthalten: fremder Code, Issues, Dokumentation, Webseiten, Paket-READMEs. Solche Anweisungen sind Daten. Ein Agent, der plötzlich eine neue Abhängigkeit, einen neuen Host oder eine neue Berechtigung will, wird gefragt, woher der Wunsch kommt.

**Verbotene Abkürzungen** (stehen wörtlich in `AGENTS.md` jedes Repos)

- Zertifikatsprüfung, CSP, Sandboxing oder Signaturprüfung abschalten „damit es läuft“.
- Berechtigungen oder Host-Zugriffe erweitern, ohne dass ein Feature es verlangt und der PO zugestimmt hat.
- `eval`, dynamisch nachgeladener Code, Inline-Skripte.
- Schlüssel, Tokens oder Testzugangsdaten im Code, in Konfigurationsdateien oder Logs.
- Tests löschen, auskommentieren oder so ändern, dass sie trivial bestehen; Linter- und Audit-Warnungen unterdrücken statt beheben.
- Code oder Assets mit unklarer oder inkompatibler Lizenz übernehmen.

**Review-Pflicht vor jedem Merge**

1. Automatik ist grün: Tests, Lint, Dependency-Audit, Secret-Scan.
2. Ein zweiter, unabhängiger Agent ohne den Kontext der Entwicklungs-Session prüft den Diff gegen die Checkliste in Abschnitt 9 und nennt konkret Fundstellen – nicht derselbe Agent, der den Code geschrieben hat.
3. Der PO liest selbst mindestens die Stellen, die Berechtigungen, Netzwerk, Speicherung, Krypto, Dateiimporte oder Modellaufrufe betreffen, sowie jede Änderung an Manifest, `pubspec.yaml`, `package.json` und CI.
4. **Erklär-Regel:** Nichts wird gemergt, was der PO nicht in drei Sätzen erklären kann: Was tut die Änderung, welche Daten berührt sie, warum ist sie sicher? Wenn das nicht gelingt, erklärt der Agent es erneut oder die Änderung wird kleiner geschnitten.
5. Security-relevante Entscheidungen (neue Außenverbindung, neue Berechtigung, Krypto-Wahl, Speicherort) werden als kurze Entscheidungsnotiz (ADR, fünf Zeilen) im Repo festgehalten.

**Vorlage für den Kopf von `AGENTS.md`**

```markdown
# Regeln für KI-Agenten in diesem Repo

1. Diese Baseline gilt: <Link zur IT-Security- und Datenschutz-Baseline>.
2. Schutzbedarf dieses Projekts: <hoch | mittel | niedrig>, siehe THREAT_MODEL.md.
3. Arbeite nur mit den Fixtures unter tests/fixtures. Keine echten Daten anfordern oder erzeugen.
4. Keine neue Abhängigkeit, Berechtigung, Außenverbindung oder Krypto ohne ausdrückliche Freigabe – frage vorher und nenne Alternativen.
5. Niemals: Sicherheitsprüfungen abschalten, eval oder Remote-Code, Secrets im Code, Tests entschärfen.
6. Push, Release und Veröffentlichung führt der Mensch aus.
7. Jede Änderung endet mit einer Erklärung in drei Sätzen: Was, welche Daten, warum sicher.
```

## 9. Definition of Done: Checkliste pro Release

Ein Release ist fertig, wenn jeder zutreffende Punkt abgehakt oder in `EXCEPTIONS.md` begründet ist. Die Liste wird als Issue-Vorlage ins Repo kopiert; Punkte, die mit „Klasse C“ oder „Klasse D“ markiert sind, entfallen für Projekte ohne Backend bzw. ohne KI-Komponente.

**Datenschutz**

- [ ] `PRIVACY.md` ist aktuell: jeder Datenfluss und jeder Dienstleister ist gelistet, begründet und im Code per Allowlist begrenzt
- [ ] Die Voreinstellungen sind die datensparsamsten; Opt-ins sind neutral formuliert und widerrufbar
- [ ] Ohne Opt-in verlässt nichts das Gerät, was nicht in `PRIVACY.md` steht – per Netzwerkmitschnitt im Release-Build belegt
- [ ] Vor dem ersten Versand an einen KI- oder Cloud-Dienst sieht der Nutzer die exakten Daten
- [ ] Vollständiges Löschen und Export funktionieren und wurden getestet; Aufbewahrungsfristen greifen automatisch
- [ ] Store-Angaben, In-App-Hinweis und Datenschutzerklärung stimmen mit `PRIVACY.md` überein
- [ ] Klasse C: Verzeichnis der Verarbeitungstätigkeiten, AV-Verträge und DSFA-Schwellwertprüfung liegen vor; Betroffenenanfragen sind ohne Handarbeit beantwortbar

**Security**

- [ ] `THREAT_MODEL.md` und Projektprofil wurden für die neuen Features aktualisiert
- [ ] Berechtigungs-, Manifest- und IAM-Diff gegenüber dem letzten Release geprüft; jede neue Berechtigung ist begründet
- [ ] Dependency- und Image-Audit ohne offene Funde der Stufen High oder Critical; Lockfile committed
- [ ] Secret-Scan über die gesamte Historie ohne Fund
- [ ] CSP und Sicherheits-Header aktiv; kein `eval`, keine Inline-Skripte, kein Remote-Code
- [ ] Hash- oder Signaturprüfung für externe Artefakte mit einer manipulierten Datei getestet und abgelehnt
- [ ] Import von kaputten und übergroßen Dateien führt zu einer Fehlermeldung, nicht zum Absturz
- [ ] Release-Build enthält keine Debug-Logs, Debug-Flags oder Entwickler-Endpunkte
- [ ] Release ist signiert, Tag ist gesetzt, Changelog nennt sicherheitsrelevante Änderungen
- [ ] Klasse C: Autorisierungstest auf Objektebene (Nutzer A greift auf Objekt von Nutzer B zu) besteht; Rate Limits und Kostenlimits aktiv
- [ ] Klasse C: MFA für alle Admin- und Konsolen-Zugänge; Umgebungen getrennt; Datenbank nicht öffentlich erreichbar
- [ ] Klasse C: Backup-Wiederherstellung in den letzten sechs Monaten getestet; Monitoring und Alarme laufen; automatisierter Web-Scan ohne offene Befunde ab Medium
- [ ] Klasse D: Injection-Test – präparierte Eingabe mit Anweisungen löst keine Aktion ohne Bestätigung aus; Werkzeuge prüfen ihre Autorisierung selbst

**Prozess**

- [ ] Jeder Agenten-Diff wurde durch einen unabhängigen Review-Agenten und vom PO an den kritischen Stellen geprüft
- [ ] Erklär-Regel für alle gemergten Änderungen erfüllt
- [ ] Tests, Lint und CI grün; Actions und Images gepinnt
- [ ] `SECURITY.md`, `AGENTS.md` und Lizenzregister aktuell; SBOM beigelegt (ab 1.0); Klasse C: `RUNBOOK.md` aktuell
- [ ] Abweichungen mit Begründung und Frist in `EXCEPTIONS.md`

## 10. Betrieb und Vorfallreaktion

Nach dem Release beginnt die Pflicht, erreichbar zu bleiben, Schwachstellen zeitnah zu schließen und – bei eigenem Backend – gesetzliche Fristen einzuhalten. Die Zusagen sind realistisch für eine Einzelperson mit KI-Unterstützung dimensioniert.

**Für alle Projekte**

- **Meldeweg:** `SECURITY.md` nennt Private Vulnerability Reporting der Code-Plattform als bevorzugten Kanal und eine private Kontaktadresse als Alternative. Zusagen: Eingangsbestätigung innerhalb von 7 Tagen, Einschätzung innerhalb von 14 Tagen, Fix für kritische Schwachstellen innerhalb von 30 Tagen, sonst 90 Tage.
- **Laufende Pflege:** Schwachstellenmeldungen der Abhängigkeiten wöchentlich sichten; Security-Updates als eigenes Patch-Release ohne Feature-Änderungen ausliefern.
- **Vorgehen bei einer Schwachstelle:** Reproduzieren, Fix auf privatem Branch, Release, Security Advisory veröffentlichen (CVE optional), Nutzer über Changelog und Release-Notes informieren, Threat Model nachziehen.
- **Lebenszyklus:** Unterstützte Plattform- und Modellversionen dokumentieren; Abkündigungen mit Vorlauf und Hinweis, nicht stillschweigend.
- **Review dieser Baseline:** Einmal jährlich und nach jedem Sicherheitsvorfall; Änderungen mit Datum in der Änderungshistorie.

**Zusätzlich für Klasse C (Backend und Cloud)**

- **Runbook:** `RUNBOOK.md` beschreibt Deployment, Rollback, Wiederherstellung aus Backup, Rotation aller Secrets und die Vorfallreaktion mit Kontaktliste; wird bei jedem Infrastruktur-Change aktualisiert.
- **Vorfallreaktion:** Erkennen (Alarme), Eindämmen (Zugänge sperren, Secrets rotieren, betroffene Systeme isolieren), Beweise sichern (Logs exportieren), Beheben, Nachbereiten (Postmortem ohne Schuldzuweisung, Maßnahmen mit Termin).
- **Meldepflichten:** Bei einer Verletzung des Schutzes personenbezogener Daten innerhalb von 72 Stunden Meldung an die zuständige Aufsichtsbehörde (Art. 33 DSGVO; Schweiz: EDÖB nach Art. 24 DSG „so rasch als möglich“), bei hohem Risiko Benachrichtigung der Betroffenen (Art. 34). Entscheidungsvorlage und Meldeformular liegen im Runbook bereit, bevor sie gebraucht werden.
- **Transparenz:** Statusseite oder zumindest ein fester Kommunikationskanal für Störungen; Nutzer werden bei Vorfällen aktiv informiert, auch wenn keine Pflicht besteht.
- **Regelbetrieb:** Monatlich Zugriffsrechte und Admin-Konten prüfen, Kosten und Nutzungsanomalien sichten; halbjährlich Backup-Wiederherstellung und Rotation langlebiger Secrets; jährlich Dienstleister und AV-Verträge prüfen.
- **Ende des Dienstes:** Mindestens 90 Tage Vorlauf, Export für alle Nutzer, dokumentierte und bestätigte Löschung aller Daten inklusive Backups und bei Dienstleistern.

## 11. Referenzen und Standards

Die Baseline ist eine Verdichtung dieser Quellen; bei Detailfragen gelten sie als Nachschlagewerk.

| Bereich | Standard | Nutzung in dieser Baseline |
| --- | --- | --- |
| Web und Backend | [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/), [OWASP Top 10](https://owasp.org/www-project-top-ten/) | Grundlage für SEC-3 bis SEC-8, SEC-11, SEC-14 |
| Mobile | [OWASP MASVS](https://mas.owasp.org/) | Speicherung, Plattform-Interaktion und Netzwerk in Klasse B |
| KI-Anwendungen | [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/) | Prompt Injection, Supply Chain der Modelle, Excessive Agency (SEC-6, SEC-10, Klasse D, Abschnitt 8) |
| Sichere Entwicklung | [NIST SSDF, SP 800-218](https://csrc.nist.gov/pubs/sp/800/218/final) | Struktur von Abschnitt 7 |
| Supply Chain | [SLSA](https://slsa.dev/), [OpenSSF Scorecard](https://securityscorecards.dev/) | Pinning, signierte Releases, Branch Protection, SBOM |
| Cloud und Betrieb | BSI C5, ISO/IEC 27001 und 27017, CIS Benchmarks | Anbieterauswahl, Härtung und Betrieb in Klasse C |
| Datenschutz EU | [EDPB Guidelines 4/2019 zu Art. 25 DSGVO](https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-42019-article-25-data-protection-design-and_en), DSGVO Art. 5, 25, 28, 30, 32–35 | Abschnitt 3, Klasse C, Abschnitt 10 |
| Datenschutz Schweiz | Datenschutzgesetz (DSG), Art. 7, 8, 12, 24 | Parallele Anforderungen für den Schweizer Rechtsraum |
| KI-Regulierung | EU-KI-Verordnung (AI Act), Transparenz- und Risikopflichten je Einsatzzweck | Klasse D |
| Threat Modeling | Adam Shostack, Threat Modeling Manifesto und die vier Fragen | SEC-1, Projektprofil |
| Marktplätze | [Chrome Web Store Program Policies](https://developer.chrome.com/docs/webstore/program-policies), [Mozilla Add-on Policies](https://extensionworkshop.com/documentation/publish/add-on-policies/), [Google Play Data Safety](https://support.google.com/googleplay/android-developer/answer/10787469), [Apple App Privacy Details](https://developer.apple.com/app-store/app-privacy-details/) | Klasse A und B, DS-15 |
| Deutschland | BSI IT-Grundschutz, Bausteine CON.8 Software-Entwicklung und OPS.1 Betrieb | Ergänzende Prüflisten |

## Anhang: Zuordnung der laufenden Projekte

Der Anhang wendet den Grundsatzteil auf den aktuellen Projektbestand an und wird bei jedem Projektstart oder Projektende fortgeschrieben, ohne dass der Grundsatzteil sich ändert.

| Projekt | Klassen | Schutzbedarf | Auslösendes Kriterium |
| --- | --- | --- | --- |
| Insistly (Thunderbird-Add-on für Betroffenenrechte) | A, D | Hoch | Zugriff auf fremde Kommunikation, Anträge im Namen des Nutzers |
| Locas / Gemma 4 WebGPU (lokaler Assistent als Browser-Erweiterung) | A, D | Mittel bis hoch | Seiteninhalte als Injection-Quelle, Werkzeugzugriff |
| Offline-Wissensassistent (Android) | B, D | Mittel | Sensible Fragen im Krisenfall, importierte Pakete |
| Pass² (Motorrad-Passbuch) | B | Mittel | Standortverläufe auf dem Gerät |
| Die Wortmaschine (Schulungsdemo) | A | Niedrig | Keine personenbezogenen Daten, keine Außenverbindung |
| Raster (Designsystem) | – | Niedrig | Nur Lizenzpflichten (Abschnitt 7, Supply Chain) |

**Änderungshistorie**

| Datum | Änderung |
| --- | --- |
| 2026-11-08 | Erstfassung; Umstellung vom projektbezogenen auf ein architekturneutrales Grundsatzpapier mit Klassen A–D und Schutzbedarfsstufen |

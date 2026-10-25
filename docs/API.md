# Lokale HTTP-API

Basis: `http://<NAS-FQDN>:8088` oder aktuelle NAS-IP. Antworten verwenden UTC-Unixzeit in Sekunden; ISO-Zeitangaben im Export enthalten UTC beziehungsweise lokalen Offset. Keine externe Anwendung wird automatisch angebunden.

## Anmeldung und Sitzung

Beim ersten Start liefert `GET /api/setup/status` ausschließlich `{ "needs_setup": true }`. Mit `POST /api/setup` und `{ "setup_code": "CODE_AUS_CONTAINER_LOG", "password": "EIGENES_APP_PASSWORT" }` einmalig ein eigenes Passwort festlegen. Auch hierfür den unten gezeigten Request-Header verwenden. Der Code ist nicht über die API abrufbar und wird nach erfolgreicher Einrichtung ungültig. Kein Standardpasswort.

```sh
curl -c cookies.txt -H 'Content-Type: application/json' -H 'X-Kilowatch-Request: 1' -d '{"password":"DEIN_APP_PASSWORT"}' http://<NAS-FQDN>:8088/api/login
curl -b cookies.txt http://<NAS-FQDN>:8088/api/live
```

Ein HttpOnly-Cookie gilt zwölf Stunden. Beim App-Neustart werden alle Sitzungen ungültig. Cookie-Dateien vertraulich behandeln. Bei `POST`, `PUT`, `PATCH` und `DELETE` ist `X-Kilowatch-Request: 1` erforderlich; ein vorhandener Origin-Header muss zum Host passen. Kein Cross-Origin-Zugriff ist aktiviert. Nach zehn fehlgeschlagenen Anmeldungen einer Quell-IP gilt eine Sperre von bis zu 15 Minuten.

## Endpunkte

| Methode/Pfad | Funktion |
|---|---|
| GET `/healthz` | öffentlicher Prozess-/Datenbankcheck ohne Messwerte |
| GET `/api/setup/status` | öffentlicher minimaler Einrichtungsstatus |
| POST `/api/setup` | einmalige Ersteinrichtung mit Code und eigenem Passwort |
| POST `/api/login` | JSON `{ "password": "..." }` |
| POST `/api/logout` | aktuelle Sitzung beenden |
| PUT `/api/account/password` | `{ "current_password": "...", "new_password": "..." }`, beendet alle Sitzungen |
| GET/PUT `/api/settings` | Einstellungen lesen/ändern; Passwort wird nicht ausgegeben |
| DELETE `/api/credentials/bridge` | Bridge-Passwort entfernen und Erfassung pausieren; Historie bleibt |
| POST `/api/bridge/test` | Verbindung mit gespeicherten oder mitgesendeten Einstellungen lesend prüfen |
| GET `/api/discovery/network` | lokale /24-Netzvorschläge; tatsächliche Netzmaske ist zu prüfen |
| POST `/api/discovery/scan` | `{ "network": "192.168.1.0/24" }`, begrenzte lokale Suche ohne Zugangsdaten |
| POST `/api/market/refresh` | bewusster Abruf öffentlicher DE-Börsenpreise; keine Änderung der Vertragspreise |
| GET/PUT `/api/notifications` | Kanal-/Regeleinstellungen, Geheimnis-Status und Zustellverlauf |
| POST `/api/notifications/test/email` | bewusster einzelner E-Mail-Test ohne Messwerte |
| POST `/api/notifications/test/signal` | bewusster einzelner Signal-Test ohne Messwerte |
| POST `/api/notifications/signal/qr` | authentifizierter PNG-Proxy für Kopplungs-QR, kein Cache |
| GET `/api/live` | letzter Messpunkt, Alter, Collectorstatus und verfügbare Register |
| GET `/api/overview` | Summen, Vorperiode, Serien und Lücken |
| GET `/api/analysis` | Muster, Lastdauerlinie, Regelhinweis und Monatsprognose |
| GET/PUT `/api/tariffs` | Tarifhistorie / Tarif ab Anfangsdatum speichern |
| DELETE `/api/tariffs/YYYY-MM-DD` | Tarif entfernen |
| POST `/api/prices/import` | JSON `{ "csv": "..." }` |
| DELETE `/api/prices` | alle importierten Preise entfernen |
| GET/POST `/api/events` | Ereignisse lesen/anlegen |
| DELETE `/api/events/ID` | Ereignis entfernen |
| GET `/api/events/ID/comparison` | Ereignis und Vorperiode vergleichen |
| GET `/api/export` | CSV-/JSON-Download |
| GET `/api/backup` | konsistente SQLite-Sicherung herunterladen |
| GET `/api/insights` | Grundlast-Entwicklung (je Woche/Monat, mit kWh und € pro Jahr) und Einspeiseprofil |
| POST `/api/simulate` | `{ "start": "...", "end": "...", "tariff": { "mode": "fixed\|dual\|spot", ... } }`, Tarifsimulation mit gepaartem Vergleich |
| GET/PUT `/api/budget` | Monatsbudget, Monatsziel und Abschlag; Monatsprognose und Jahreshochrechnung |
| POST `/api/market/history` | `{ "start": "...", "end": "..." }`, vergangene Börsenpreise nachladen (höchstens 62 Tage) |
| GET/PUT `/api/updates` | Status des Update-Hinweises; `{ "enabled": true }` schaltet die tägliche Prüfung ein |
| POST `/api/updates/check` | einmalige Update-Prüfung bei GitHub |
| GET `/api/diagnostics` | freigegebene Diagnosefelder, lokale Hinweise und Speichergröße |

Zeitraumsparameter für Übersicht, Analyse und Export:

```text
?start=2026-10-01&end=2026-10-31
```

Das Enddatum ist **einschließlich** und wird bei laufenden Zeiträumen auf jetzt begrenzt. Tagesgrenzen verwenden `Europe/Berlin`. Höchstens zehn Jahre je Abfrage. Fehlende Felder in einer partiellen Einstellungsänderung bleiben unverändert.

## Bridge- und Benachrichtigungskonfiguration

`PUT /api/settings` akzeptiert unter anderem `bridge_host`, `bridge_user`, `bridge_password`, `node_id`, `enabled` und Aufbewahrungsfelder. `bridge_host` ist eine lokale IPv4-Adresse oder ein FQDN ohne Schema, Port und Pfad. FQDNs werden bei neuen Verbindungen erneut aufgelöst und die IPv4-Ziele geprüft. Leeres/fehlendes `bridge_password` behält den gespeicherten Wert. `GET` enthält stattdessen `password_configured`, `setup_required` und `credential_storage`. `/api/bridge/test` speichert keine Eingaben und liefert bei Erfolg `host` und `resolved_addresses`.

`GET /api/notifications` liefert `settings`, `smtp_password_configured`, `signal_token_configured`, `last_error` und die letzten 100 Verlaufseinträge ohne Nachrichtentexte. **`PUT /api/notifications` ersetzt die vollständige Kanal-/Regelkonfiguration**; vorher `settings` lesen und vollständig zurücksenden. Ausgelassene Konfigurationsfelder erhalten ihre Standardwerte. Zusätzlich sind `smtp_password`, `signal_token`, `clear_smtp_password` und `clear_signal_token` zulässig. Ausgelassene/leere Geheimnisse bleiben erhalten; die Clear-Schalter entfernen sie ausdrücklich. Passwörter/Token werden nie ausgegeben.

Feldnamen und Grenzen stehen im Modell `NotificationSettings` in `app/notifications.py`. Empfänger sind Listen von höchstens fünf Adressen beziehungsweise internationalen Rufnummern. Signal-URL ist eine lokale HTTP(S)-Gateway-URL, nicht die Bridge-Adresse. Automatische Nachrichten erfordern Hauptschalter und mindestens einen gültigen Kanal. Tests umgehen Hauptschalter und Ruhezeit, nicht die Anmeldung; maximal ein Test je Kanal in 30 Sekunden. Demo-Modus erlaubt keinen Versand. Einrichtung: [BENACHRICHTIGUNGEN.md](BENACHRICHTIGUNGEN.md).

## Tarifbeispiel

```json
{
  "start_date": "2026-10-01",
  "name": "Mein Festpreis",
  "mode": "fixed",
  "eur_kwh": 0.32,
  "base_month": 12.90,
  "feedin_eur_kwh": 0.08
}
```

`mode` ist `fixed`, `dual` oder `dynamic`. API-Werte sind **Euro**, während die Weboberfläche den Arbeitspreis in **Cent** abfragt. Alle Vertragspreise sind vollständig brutto. Bei `dynamic` wird der feste Wert nicht als Rückfallpreis verwendet.

Für `dual` zusätzlich `low_eur_kwh`, `low_start`, `low_end` und optional `weekend_low` übergeben. `eur_kwh` ist HT, `low_eur_kwh` NT. Die Uhrzeiten als HH:MM auf Viertelstundengrenzen in Europe/Berlin angeben, Anfang und Ende verschieden. `weekend_low=true` bedeutet ganztägig NT am Samstag/Sonntag. [Tarifregeln](TARIFE.md).

`GET /api/tariffs` liefert ergänzend `market` mit zwischengespeicherten Börsenwerten. Diese besitzen `kind=spot_net`, `eur_mwh` und `ct_kwh`, niemals stillschweigend `eur_kwh` als vollständigen Vertragspreis. Der optionale Abruf benötigt kein Konto, ist auf eine feste HTTPS-Quelle begrenzt und läuft nur auf ausdrücklichen API-Aufruf. [Gerätesuche](GERAETESUCHE.md) beschreibt Netzgrenzen und Ergebnisfelder.

## Dynamische Preis-CSV

```csv
start,end,eur_kwh
2026-10-24T00:00:00+02:00,2026-10-24T01:00:00+02:00,0.295
2026-10-24T01:00:00+02:00,2026-10-24T02:00:00+02:00,0.285
```

Semikolon als Trenner ist ebenfalls möglich; bei Semikolon darf das Dezimaltrennzeichen ein Komma sein. UTC-Zeiten mit `Z` sind möglich. Ein expliziter Offset ist zwingend, besonders bei der doppelten Stunde der Winterzeitumstellung. An dieser Stelle möglichst UTC verwenden.

- Intervalle sind halboffen: Beginn einschließlich, Ende ausschließlich.
- Start und Ende liegen auf UTC-Viertelstundengrenzen; Dauer zwischen 15 Minuten und 24 Stunden.
- Mindestens -5 und höchstens 10 EUR/kWh; negative Preise sind erlaubt.
- Höchstens 35040 Intervalle und 1,5 Millionen Zeichen pro Import.
- Überschneidungen werden abgelehnt. Identische Start-/Endintervalle können aktualisiert werden. Der gesamte Import wird bei Fehlern zurückgerollt.
- Fehlende Preisabschnitte bleiben fehlend. Preise werden nicht über Lücken fortgeschrieben.

## Export und Seitennavigation

```text
/api/export?start=2026-10-01&end=2026-10-31&kind=quarters&format=json&limit=100000&offset=0
```

`kind`: `samples`, `minutes`, `quarters`, `gaps`. `format`: `csv`, `json`. `limit`: 1 bis 100000, `offset`: ab 0.

JSON liefert `data`, `count`, `next_offset` und `page_full`. Bei `page_full=true` mit `offset=next_offset` weiter abfragen; eine letzte leere Seite ist zulässig. CSV liefert dieselben Metadaten über `X-Export-Count` und `X-Export-Next-Offset`. Der Browserdownload erzeugt eine Seite; große Rohwertbereiche in Zeitabschnitte aufteilen oder eine eigene Seitennavigation verwenden.

Viertelstundenwerte enthalten Energiemengen in kWh und erfasste Sekunden. `power_ws / power_s` ergibt die mittlere Netzleistung in W, sofern `power_s > 0`. Nicht vorhandene Energie ist nur über passende Abdeckung als null oder unbekannt einzuordnen. Lückenenergie separat mit `kind=gaps` exportieren und nicht nochmals zu aggregierten Tageswerten addieren, wenn diese bereits ausdrücklich als Gesamtsumme inklusive solcher Lücken gekennzeichnet sind.

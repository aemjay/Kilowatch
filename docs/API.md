# Lokale HTTP-API

Die Oberfläche nutzt dieselbe API wie du: `http://<Host>:8088/api/…`. Zeiten sind UTC-Unixsekunden; Exporte enthalten zusätzlich ISO-Zeiten mit Offset. Es gibt keine automatische Anbindung an andere Dienste.

## Anmeldung

Die Ersteinrichtung (`GET /api/setup/status` → `{"needs_setup": true}`, dann `POST /api/setup` mit `{"setup_code": "…", "password": "…"}`) geht einmalig; der Code ist nicht per API lesbar. Danach:

```sh
curl -c cookies.txt -H 'Content-Type: application/json' -H 'X-Kilowatch-Request: 1' -d '{"password":"DEIN_APP_PASSWORT"}' http://<Host>:8088/api/login
curl -b cookies.txt http://<Host>:8088/api/live
```

- Das HttpOnly-Cookie gilt zwölf Stunden; ein Neustart beendet alle Sitzungen. Behandle Cookie-Dateien vertraulich.
- `POST`, `PUT`, `PATCH` und `DELETE` brauchen den Header `X-Kilowatch-Request: 1`, ein vorhandener `Origin` muss zum Host passen. Cross-Origin-Zugriff gibt es nicht.
- Nach zehn fehlgeschlagenen Anmeldungen einer Adresse gilt eine Sperre von bis zu 15 Minuten.
- Fehlertexte (`detail`) kommen in der Sprache aus dem Header `X-Kilowatch-Language`, sonst der gespeicherten, sonst Deutsch.

## Zeitraum

Übersicht, Analyse und Auswertungen verstehen eine dieser Angaben (`hours` und `minutes` nur Übersicht und Analyse):

| Parameter | Bedeutung |
|---|---|
| `start`, `end` | Kalendertage `2026-10-01`; das Ende gilt einschließlich und wird auf jetzt begrenzt; Tage in `Europe/Berlin`, höchstens zehn Jahre |
| `hours=1…48` | die letzten Stunden |
| `minutes=5…120` | die letzten Minuten (Energie aus Minutenwerten) |
| `since`, `until` | freies Fenster in Unixsekunden (5 Minuten bis zehn Jahre); ohne `until` bis jetzt |

`/api/export` kennt nur `start` und `end`.

## Endpunkte

| Pfad | Funktion |
|---|---|
| GET `/healthz`, `/api/setup/status` | öffentlich: Prozess-/Datenbankcheck, Einrichtungsstatus |
| POST `/api/setup`, `/api/login`, `/api/logout` | Einrichtung, Anmeldung, Abmeldung |
| PUT `/api/account/password` | `{"current_password", "new_password"}`; beendet alle Sitzungen |
| GET/PUT `/api/settings` | Einstellungen; Passwörter werden nie ausgegeben |
| DELETE `/api/credentials/bridge` | Bridge-Passwort entfernen, Erfassung pausieren |
| POST `/api/bridge/test` | Verbindung lesend prüfen, speichert nichts |
| GET `/api/discovery/network`, POST `/api/discovery/scan` | Netzvorschlag, lokale Suche (`{"network": "192.168.1.0/24"}`) |
| GET `/api/live` | letzter Messpunkt, Alter, Status; `cost` mit Arbeitspreis und Kostenrate der laufenden Viertelstunde |
| GET `/api/overview` | Summen, Vorperiode, Serien, Lücken, `co2` (bei gesetztem `grid_country`) |
| GET `/api/analysis`, `/api/insights` | Muster, Lastdauerlinie, Prognose; Grundlast-Entwicklung, Einspeiseprofil |
| GET `/api/timeline` | gesamter erfasster Zeitraum in groben Abschnitten (für den Zeitbalken) |
| GET/PUT `/api/tariffs`, DELETE `/api/tariffs/YYYY-MM-DD` | Tarife |
| POST `/api/prices/import`, DELETE `/api/prices` | Preis-CSV importieren / alle importierten Preise löschen |
| PUT `/api/prices/source`, POST `/api/prices/refresh` | Preisquelle (`source`: `""`, `tibber`, `spot`; `zone`, `markup_ct`, `vat_percent`, `tibber_home`, `tibber_token`, `clear_tibber_token`), sofort abrufen; Abruf höchstens alle 30 s |
| GET `/api/prices/outlook?window_hours=2` | Preise je Viertelstunde für heute und morgen und günstigstes Fenster (1–6 h) ab jetzt; nur bei dynamischem Tarif |
| POST `/api/market/refresh`, `/api/market/history` | Börsenpreise ansehen / nachladen (höchstens 62 Tage) |
| POST `/api/simulate` | Tarifsimulation: `{"start", "end", "tariff": {"mode": "fixed\|dual\|spot", …}}` |
| GET/PUT `/api/budget` | Monatsbudget, Monatsziel, Abschlag, `billing_start` (`MM-TT`, Beginn des Abrechnungsjahrs; `GET` liefert dazu `billing`) |
| GET `/api/meter-readings?dates=2026-10-01,2026-09-01` | Zählerstände 1.8.0/2.8.0 um 00:00 Uhr der Tage (1–31): `import_kwh`, `export_kwh`, `measured_at`, `source` (`sample`/`reconstructed`), `approximate`, `reason` |
| GET/POST `/api/events`, DELETE `/api/events/ID`, GET `/api/events/ID/comparison` | Ereignisse und Vorperiodenvergleich |
| GET/PUT `/api/notifications`, POST `/api/notifications/test/email` | Mail-Regeln und Verlauf, Test |
| GET/PUT `/api/updates`, POST `/api/updates/check` | Update-Hinweis |
| GET `/api/export`, `/api/backup`, `/api/diagnostics` | Export, konsistente Sicherung, Diagnose |

**Einstellungen:** `PUT /api/settings` darf einzelne Felder ändern (`bridge_host`, `bridge_user`, `bridge_password`, `node_id`, `enabled`, Aufbewahrung …). `bridge_host` ist eine lokale IPv4-Adresse oder ein Name ohne Schema, Port und Pfad. Ein leeres `bridge_password` behält das gespeicherte; `GET` meldet stattdessen `password_configured`. `language` (`de`, `en`, `nb`, `sv`, `nl`), `currency` (`EUR`, `NOK`, `SEK`) und `grid_country` (`de`, `nl`, `no`, `se`; leer = aus) gehören ebenfalls dazu.

**Benachrichtigungen:** `PUT /api/notifications` **ersetzt die gesamte Konfiguration**: erst `settings` lesen, dann vollständig zurücksenden. Zusätzlich gelten `smtp_password` und `clear_smtp_password`. Felder und Grenzen stehen im Modell `NotificationSettings` in `app/notifications.py`; Einrichtung: [Benachrichtigungen](BENACHRICHTIGUNGEN.md).

**Kostenrate:** `cost` in `/api/live` enthält `tariff` (bool), `mode`, `rate_eur_kwh` (Arbeitspreis jetzt), `feedin_eur_kwh` (`null` bei 0), `direction` (`import`/`export`) und `eur_per_hour` (Kosten bzw. Erlös, `null` ohne frische Messung oder Preis).

**Preisausblick:** `/api/prices/outlook` liefert `dynamic`, `intervals` (`start`, `end`, `eur_kwh`), `tomorrow_available`, `low_eur_kwh`, `high_eur_kwh` und `cheapest` (`start`, `end`, `average_eur_kwh` oder `null`). Ohne dynamischen Tarif ist `dynamic` falsch und `intervals` leer.

## Tarif

```json
{"start_date": "2026-10-01", "name": "Mein Festpreis", "mode": "fixed", "eur_kwh": 0.32, "base_month": 12.90, "feedin_eur_kwh": 0.08}
```

`mode` ist `fixed`, `dual` oder `dynamic`. API-Werte sind **Euro** (die Oberfläche fragt Cent), alle Preise brutto. Für `dual` kommen `low_eur_kwh`, `low_start`, `low_end` (HH:MM auf Viertelstunden) und optional `weekend_low` dazu; `eur_kwh` ist dann HT. Bei `dynamic` gibt es keinen Rückfallpreis. Regeln: [Tarife](TARIFE.md). `GET /api/tariffs` liefert außerdem `market` (Netto-Börsenpreise, nie als Vertragspreis).

## Preis-CSV

```csv
start,end,eur_kwh
2026-10-24T00:00:00+02:00,2026-10-24T01:00:00+02:00,0.295
2026-10-24T01:00:00+02:00,2026-10-24T02:00:00+02:00,0.285
```

- Trenner Komma oder Semikolon (bei Semikolon ist ein Dezimalkomma erlaubt). Ein Offset oder `Z` ist Pflicht; nimm UTC, um die doppelte Stunde der Zeitumstellung eindeutig zu halten.
- Intervalle sind halboffen (Beginn einschließlich, Ende ausschließlich), liegen auf Viertelstunden und dauern 15 Minuten bis 24 Stunden.
- Preise von −5 bis 10 EUR/kWh (negative sind erlaubt), höchstens 35040 Intervalle und 1,5 Millionen Zeichen je Import.
- Überschneidungen werden abgelehnt, identische Intervalle aktualisiert; bei einem Fehler wird der ganze Import zurückgerollt. Lücken bleiben Lücken.

## Export

```text
/api/export?start=2026-10-01&end=2026-10-31&kind=quarters&format=json&limit=100000&offset=0
```

`kind`: `samples`, `minutes`, `quarters`, `gaps`. `format`: `csv`, `json`. `limit` 1 bis 100000. JSON liefert `data`, `count`, `next_offset` und `page_full`; bei `page_full=true` mit `offset=next_offset` weiterfragen. CSV liefert dieselben Angaben in `X-Export-Count` und `X-Export-Next-Offset`. Die mittlere Netzleistung ist `power_ws / power_s` in W (bei `power_s > 0`). Exportiere Lückenenergie separat (`kind=gaps`) und addiere sie nicht zu Tageswerten, die sie schon enthalten.

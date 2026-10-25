# Eigenen Strompreis hinterlegen

Die Seite **Kosten & Tarife → Deinen Tarif hinterlegen** speichert deinen Strompreis unabhängig von Tibber. Die Preisart lässt sich umschalten:

| Preisart | Angaben |
|---|---|
| **1 Tarifstufe** | ein vollständiger Arbeitspreis brutto in ct/kWh |
| **2 Tarifstufen · HT/NT** | Hochtarif, Niedertarif und lokale Uhrzeiten, zu denen NT gilt |
| **Variabel · CSV** | vollständige zeitabhängige Bruttopreise deines Anbieters per CSV |

Für alle Arten zusätzlich **Gültig ab**, Tarifname, Grundpreis brutto in Euro/Monat und gegebenenfalls Einspeisevergütung in ct/kWh eintragen. Die App setzt keinen Preis automatisch als deinen Vertragspreis ein. Eine vorhandene Tarifzeile lässt sich mit **Bearbeiten** übernehmen; Speichern ersetzt den Tarif mit diesem Anfangsdatum. Ein neues Anfangsdatum bildet einen Tarifwechsel ab und erhält frühere Preise.

## Zwei Tarifstufen nach Uhrzeit

Beispiel ausschließlich zur Erklärung: HT 35 ct/kWh, NT 25 ct/kWh, NT von 22:00 bis 06:00. Dann wird jede erfasste Viertelstunde ab 22:00 einschließlich bis 06:00 ausschließlich mit NT bewertet; außerhalb gilt HT. Die tatsächlichen Werte und Zeiten dem eigenen Vertrag entnehmen.

- NT darf über Mitternacht reichen oder ein Zeitfenster am selben Tag bilden.
- Anfang und Ende müssen verschieden sein und auf 00/15/30/45 Minuten liegen. Das passt zur dauerhaft gespeicherten Viertelstundenauflösung.
- Wahlweise gilt am Samstag und Sonntag ganztägig NT. Andernfalls gelten dieselben Uhrzeiten wie werktags.
- Zeiten verwenden **Europe/Berlin**. Bei der Winterzeitumstellung werden beide gleich bezeichneten Stunden nach derselben lokalen Tarifregel bewertet; UTC-Zeitstempel bleiben eindeutig.
- Feiertage und Sonderkalender werden nicht automatisch erkannt. Die Funktion ordnet Preise nach Uhrzeit zu; sie ist keine direkte Abrechnung separater T1-/T2-Zählerregister.
- Die Rechnung verwendet die bekannten Viertelstunden-Energiemengen. Fehlende Daten und längerfristige Lücken werden weiterhin nicht erfunden oder willkürlich auf HT/NT verteilt.

## Dynamische Tarife

Für einen dynamischen Vertrag einen Tarif mit der Preisart **Dynamisch** anlegen (Grundpreis und Einspeisevergütung wie gewohnt). Die Preise je Viertelstunde kommen dann aus einer Preisquelle unter **Kosten & Tarife → Dynamische Preise**:

| Preisquelle | Einrichtung | Preis je kWh |
|---|---|---|
| **Tibber** | persönlicher API-Token von [developer.tibber.com](https://developer.tibber.com) (Anmelden → Access Token). Bei mehreren Zuhause eines auswählen. | Tibber-Gesamtpreis des eigenen Vertrags + optionaler Aufschlag |
| **Börsenpreis + Aufschlag** | Gebotszone (z. B. DE-LU), Aufschlag netto in ct/kWh und Mehrwertsteuer aus dem Preisblatt des Anbieters | (Börsenpreis + Aufschlag) × (1 + MwSt) |
| **CSV** | vollständige Bruttopreise je Zeitintervall importieren, siehe [API/CSV-Format](API.md) | wie importiert |

- Kilowatch ruft die gewählte Quelle stündlich ab, beim ersten Mal rückwirkend bis zu 31 Tage. Preise für morgen erscheinen am frühen Nachmittag. Gesendet werden nur Zeitraum bzw. die Tibber-Abfrage, keine Messwerte. Der Tibber-Token liegt verschlüsselt im Zugangsdaten-Volume und wird nie an den Browser zurückgegeben.
- Beim Tibber-Preis ist nur einzutragen, was **nicht** im Tibber-Preis steckt, z. B. das separat abgerechnete Netzentgelt in Norwegen. Sonst 0. Der Abgleich mit einer Rechnung zeigt, ob noch etwas fehlt.
- Die Währung von Tibber muss zur Währungseinstellung passen; sonst speichert Kilowatch nichts und zeigt einen Hinweis. Börsenpreis + Aufschlag gibt es nur für Gebotszonen in Euro.
- Ein Quellenwechsel oder geänderter Aufschlag berechnet den Rückblick neu. Automatische Preise ersetzen im abgedeckten Zeitraum vorhandene CSV-Preise.
- Fehlende Preise bleiben als unbepreiste Energie sichtbar. Es gibt keinen Rückfall auf Null oder einen festen Preis. Das Ergebnis ist eine nachvollziehbare Rechnung aus Messwerten und Preisen, keine Abrechnung des Anbieters.

## Börsenpreisvorschau

Zusätzlich kann unter **Börsenpreise ansehen** per Knopfdruck der technisch ohne Token lesbare DE-Feed von aWATTar abgerufen werden. Er liefert veröffentlichte Börsenintervalle für heute und, sobald vorhanden, morgen. Die App überträgt dabei nur die angefragten Zeitgrenzen, keine Messdaten oder Zugangsdaten. Es gibt keinen Hintergrundabruf und keinen Tibber-Tarifzwang. Erfolgreiche Antworten bleiben eine Stunde im Cache; nach Fehlern gilt eine 15-Minuten-Pause. Im Demo-Modus wird nichts abgerufen.

**Börsenpreise sind keine vollständigen Vertragspreise.** Der Feed liefert EUR/MWh, die Vorschau rechnet durch 10 in ct/kWh um. Anbieteraufschläge, Netzentgelte und Steuern sind damit noch nicht vollständig erfasst. Deshalb verändert dieser Abruf weder deine Tarife noch importierte Bruttopreise und fließt nicht in die Kostenberechnung ein. Abgerufene Börsenpreise werden aber als Historie gespeichert und stehen der Tarifsimulation zur Verfügung. Negative Börsenpreise bleiben sichtbar. Ältere Cache-Daten behalten ihre tatsächlichen Zeitstempel; fehlende Zukunftspreise werden nicht ergänzt.

Ohne variablen Vertrag muss hier nichts eingerichtet werden. Eine direkte Vertragspreis-Anbindung hängt vom tatsächlichen Anbieter und dessen verfügbarer Schnittstelle ab. Der nutzbare Weg für beliebige Anbieter bleibt der Import vollständiger Preise.

## Tarif simulieren

Unter **Kosten & Tarife → Tarif simulieren** lässt sich derselbe gemessene Lastgang mit einem anderen Tarif nachrechnen: Festpreis, HT/NT oder dynamisch als **(Börsenpreis + Aufschlag) × (1 + MwSt)**. Der Aufschlag umfasst Netzentgelt, Umlagen, Stromsteuer und Anbietermarge und steht im Preisblatt des Anbieters.

- Verglichen wird **gepaart**: Arbeitspreise beider Tarife nur über die Viertelstunden, die in beiden bepreist sind; Grundpreis und Einspeisung über den ganzen Zeitraum. Der abgedeckte Anteil wird angezeigt.
- Für dynamische Tarife braucht die Simulation Börsenpreise des Zeitraums. **Börsenpreise für den Zeitraum nachladen** holt sie bei aWATTar (höchstens 62 Tage je Abruf, in Abschnitten zu drei Tagen, 10 Minuten Pause zwischen Abrufen). Übertragen werden nur die Zeitgrenzen.
- Bei dynamischen Tarifen zeigt die Simulation zusätzlich den **verbrauchsgewichteten Börsenpreis** gegenüber dem Zeitmittel. Liegt er darüber, fällt der Bezug eher in teure Stunden.
- Annahme: gleicher Verbrauch zur gleichen Zeit. Eine Verhaltensänderung durch den anderen Tarif ist nicht berücksichtigt; das Ergebnis ist kein Einsparversprechen.

## Budget und Abschlag

Unter **Budget & Abschlag** lassen sich ein Monatsbudget in €, ein Monatsziel in kWh und der monatliche Abschlag hinterlegen.

- **Monat:** bisherige Kosten und Prognose bis Monatsende (bisherige Kosten + prognostizierte Rest-kWh × bisheriger mittlerer Arbeitspreis + voller Monatsgrundpreis). Die Prognose braucht dieselbe Datenbasis wie die Monatsprognose der Analysen.
- **Jahr:** Hochrechnung aus vollständig erfassten Tagen der letzten 365 Tage, erst ab 60 solchen Tagen. Ohne Jahreszeitbereinigung; bei weniger als einem Jahr Daten kann die Zahl deutlich abweichen. Die angezeigte Spanne beschreibt nur die Tagesstreuung. Einspeisung bleibt unberücksichtigt.
- Optional meldet die Alarmregel **Monatsbudget erreicht** per E-Mail, sobald die erfassten Kosten das Budget erreichen.

Primärquelle: [aWATTar/tado° DE API-Dokumentation](https://energy.tado.com/services/api). Monatlicher Grundpreis und Einspeisevergütung werden weiter unabhängig davon lokal hinterlegt.

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

## Variable Tarife und Börsenpreisvorschau

Für einen echten variablen Vertrag enthält die Preis-CSV die **vollständigen Bruttopreise je Zeitintervall**, siehe [API/CSV-Format](API.md). Fehlende Preise bleiben als unbepreiste Energie sichtbar. Es gibt keinen Rückfall auf Null oder einen festen Preis.

Zusätzlich kann unter **Börsenpreise ansehen** per Knopfdruck der technisch ohne Token lesbare DE-Feed von aWATTar abgerufen werden. Er liefert veröffentlichte Börsenintervalle für heute und, sobald vorhanden, morgen. Der Abruf wurde am 25.10.2026 erfolgreich lesend geprüft. Die App überträgt dabei nur die angefragten Zeitgrenzen, keine Messdaten oder Zugangsdaten. Es gibt keinen Hintergrundabruf und keinen Tibber-Tarifzwang. Erfolgreiche Antworten bleiben eine Stunde im Cache; nach Fehlern gilt eine 15-Minuten-Pause. Im Demo-Modus wird nichts abgerufen.

**Börsenpreise sind keine vollständigen Vertragspreise.** Der Feed liefert EUR/MWh, die Vorschau rechnet durch 10 in ct/kWh um. Anbieteraufschläge, Netzentgelte und Steuern sind damit noch nicht vollständig erfasst. Deshalb verändert dieser Abruf weder deine Tarife noch importierte Bruttopreise und fließt nicht in die Kostenberechnung ein. Negative Börsenpreise bleiben sichtbar. Ältere Cache-Daten behalten ihre tatsächlichen Zeitstempel; fehlende Zukunftspreise werden nicht ergänzt.

Da aktuell kein variabler Vertrag vorliegt, muss hier nichts eingerichtet werden. Eine spätere direkte Vertragspreis-Anbindung hängt vom tatsächlichen Anbieter und dessen verfügbarer Schnittstelle ab. Der nutzbare Weg für beliebige Anbieter bleibt der Import vollständiger Preise.

Primärquelle: [aWATTar/tado° DE API-Dokumentation](https://energy.tado.com/services/api). Monatlicher Grundpreis und Einspeisevergütung werden weiter unabhängig davon lokal hinterlegt.

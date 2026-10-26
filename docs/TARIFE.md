# Tarife, Preise und Budget

Unter **Kosten & Tarife** hinterlegst du deinen Strompreis, unabhängig von Tibber. Alle Vertragspreise sind **brutto**. Kilowatch rechnet aus Messwerten und Preisen und liefert keine Abrechnung des Anbieters.

| Preisart | Angaben |
|---|---|
| **1 Tarifstufe** | ein Arbeitspreis in ct/kWh |
| **2 Tarifstufen (HT/NT)** | Hoch- und Niedertarif und die Uhrzeiten, zu denen NT gilt |
| **Dynamisch** | Preise je Viertelstunde aus einer [Preisquelle](#dynamische-preise) |

Dazu kommen **Gültig ab**, Name, Grundpreis in €/Monat und optional Einspeisevergütung. Ein neues Anfangsdatum bildet einen Tarifwechsel ab und lässt frühere Preise unberührt; **Bearbeiten** ersetzt den Tarif mit diesem Datum.

## HT/NT nach Uhrzeit

Beispiel: HT 35 ct, NT 25 ct, NT von 22:00 bis 06:00. Jede erfasste Viertelstunde in diesem Fenster zählt als NT, alle anderen als HT. Nimm die echten Werte aus deinem Vertrag.

- Das NT-Fenster darf über Mitternacht reichen. Anfang und Ende müssen verschieden sein und auf 00/15/30/45 Minuten liegen. Optional gilt am Wochenende ganztägig NT.
- Zeiten gelten in `Europe/Berlin`. Feiertage kennt Kilowatch nicht, und es ist keine Abrechnung getrennter Zählerregister.

## Dynamische Preise

Lege einen Tarif mit der Preisart **Dynamisch** an und wähle unter **Dynamische Preise** die Quelle:

| Quelle | Einrichtung | Preis je kWh |
|---|---|---|
| **Tibber** | persönlicher API-Token von [developer.tibber.com](https://developer.tibber.com), bei mehreren Zuhause eines wählen | Tibber-Gesamtpreis deines Vertrags + optionaler Aufschlag |
| **Börsenpreis + Aufschlag** | Euro-Gebotszone (DE-LU, AT, NL, BE, FR), Aufschlag netto in ct/kWh, MwSt aus dem Preisblatt | (Börsenpreis + Aufschlag) × (1 + MwSt) |
| **CSV** | vollständige Bruttopreise importieren ([Format](API.md#preis-csv)) | wie importiert |

- Kilowatch fragt die Quelle stündlich ab, beim ersten Mal bis zu 31 Tage rückwirkend; Preise für morgen erscheinen am frühen Nachmittag. Es gehen nur Zeitraum bzw. die Preisabfrage hinaus, keine Messwerte. Der Tibber-Token liegt verschlüsselt im Zugangsdaten-Volume.
- Beim Tibber-Preis trägst du als Aufschlag nur ein, was **nicht** im Tibber-Preis steckt (z. B. Netzentgelt in Norwegen), sonst 0.
- Die Tibber-Währung muss zur Währungseinstellung passen. Börsenpreise gibt es nur für Euro-Zonen.
- Eine geänderte Quelle oder ein geänderter Aufschlag rechnet den Rückblick neu. Automatische Preise ersetzen im abgedeckten Zeitraum CSV-Preise.
- Fehlende Preise bleiben als unbepreiste Energie sichtbar; es gibt keinen Rückfall auf Null oder einen Festpreis.

## Kostenrate und Preisampel

Die Übersicht zeigt neben der Live-Leistung **Kostet gerade**: aktuelle Netzleistung × Arbeitspreis der laufenden Viertelstunde in €/h, darunter den Arbeitspreis in ct/kWh. Bei HT/NT gilt der Preis der Uhrzeit, bei dynamischen Tarifen der Preis des aktuellen Intervalls. Bei Einspeisung steht dort der Erlös mit der Einspeisevergütung; ist keine hinterlegt (0 ct), steht „—“. Ohne frische Messung gibt es keinen Betrag.

Mit einem aktuell gültigen dynamischen Tarif und vorhandenen Preisen erscheint die **Preisampel**: Bruttopreise je Viertelstunde für heute und, sobald veröffentlicht, morgen. Die drei Farben teilen den Bereich zwischen günstigstem und teuerstem Preis im Diagramm in Drittel; sie sagen nichts über das allgemeine Preisniveau. Darüber steht das günstigste zusammenhängende Fenster (2, 3 oder 4 Stunden) mit Zeitmittel, frühestens ab der laufenden Viertelstunde. Längere Preisintervalle (z. B. Stundenpreise) werden auf Viertelstunden verteilt; Lücken unterbrechen ein Fenster.

## Tarif simulieren

**Tarif simulieren** rechnet denselben Lastgang mit einem anderen Tarif (Fest, HT/NT oder Börsenpreis + Aufschlag). Verglichen wird gepaart: Arbeitspreise nur über Viertelstunden, die in beiden Tarifen bepreist sind, Grund- und Einspeisepreis über den ganzen Zeitraum. Bei dynamischen Tarifen siehst du den **verbrauchsgewichteten Börsenpreis** neben dem Zeitmittel; liegt er darüber, fällt dein Bezug eher in teure Stunden. Angenommen wird gleicher Verbrauch zur gleichen Zeit, also kein Sparversprechen.

Dafür braucht die Simulation Börsenpreise des Zeitraums: **Börsenpreise für den Zeitraum nachladen** holt sie bei [aWATTar](https://energy.tado.com/services/api) (höchstens 62 Tage je Abruf, nur Zeitgrenzen werden übertragen). Unter **Börsenpreise ansehen** kannst du außerdem die Netto-Börsenpreise von heute und morgen ansehen. Sie sind keine Vertragspreise und fließen nicht in die Kosten ein.

## Budget und Abschlag

Unter **Budget & Abschlag** legst du Monatsbudget (€), Monatsziel (kWh) und Abschlag fest.

- **Monat:** bisherige Kosten und Prognose bis Monatsende (bisherige Kosten + Rest-kWh × mittlerer Arbeitspreis + voller Grundpreis). Die Prognose braucht dieselbe Datenbasis wie die Monatsprognose der Analyse.
- **Jahr:** Hochrechnung aus vollständig erfassten Tagen der letzten 365 Tage, erst ab 60 solchen Tagen, ohne Jahreszeitbereinigung. Die Spanne zeigt nur die Tagesstreuung, Einspeisung bleibt außen vor.
- Optional meldet die Alarmregel **Monatsbudget** per E-Mail ([Benachrichtigungen](BENACHRICHTIGUNGEN.md)).

# E-Mail-Benachrichtigungen

Kilowatch warnt dich per E-Mail über deinen eigenen SMTP-Server. Alles ist zunächst ausgeschaltet; die Messung läuft auch ohne.

## Einrichten

Unter **Benachrichtigungen**:

1. SMTP-Server, Port und Verschlüsselung eintragen: meist **587/STARTTLS** oder **465/TLS**, laut deinem Mailanbieter.
2. Benutzer und Passwort eintragen (manche Anbieter verlangen ein App-Passwort). Der Absender muss zum Konto passen. Der **Absendername** (Standard „Kilowatch“) steht im Postfach vor der Adresse.
3. Bis zu fünf Empfänger eintragen.
4. Optional ein **Erkennungswort** wählen (z. B. `Kuckuck-17`, höchstens 40 Zeichen). Es steht als `[Wort]` vor jedem Betreff. Fehlt es, ist die Nachricht nicht von Kilowatch. Es ist kein Passwort, eignet sich aber für Mailfilter.
5. **Speichern & E-Mail-Test senden.** Der Test enthält keine Messwerte; Fehler erscheinen in der Oberfläche und im Zustellverlauf.
6. Nach einem erfolgreichen Test **E-Mail als Kanal** und **Automatische Benachrichtigungen** einschalten.

Zertifikate werden geprüft, einen unverschlüsselten Rückfall gibt es nicht. „Gesendet“ heißt: Dein SMTP-Server hat die Nachricht angenommen, nicht dass sie im Postfach liegt. Die Mail ist nicht Ende-zu-Ende-verschlüsselt.

## Regeln

| Regel | Vorgabe | Verhalten |
|---|---|---|
| Keine frischen Zählerdaten | 120 s (an) | meldet ausbleibende Messungen |
| Hohe Dauerlast | 3000 W für 10 min (aus) | nur bei frischen, durchgehenden Daten; Entwarnung unter 90 % der Schwelle |
| Tagesbudget Netzbezug | 0 kWh = aus | einmal pro Tag bei Erreichen; bei Lücken kann mehr verbraucht worden sein |
| Monatsbudget | aus | meldet, wenn die erfassten Kosten das [Budget](TARIFE.md#budget-und-abschlag) erreichen |
| Batteriespannung | 2,7 V (an) | nur bei aktueller Diagnose; ein Hinweis, keine Restlaufzeit |
| Datenspeicher knapp | unter 512 MiB frei (an) | prüft den Speicher am Datenpfad |

## Ruhezeiten und Zustellung

- **Ruhezeit** (Standard 22–07 Uhr, aus) gilt in `Europe/Berlin`. Nachrichten warten; löst sich das Problem vorher, entfallen sie.
- Es gibt einen Alarm je Zustandswechsel und mindestens 60 Minuten bis zum nächsten Alarm derselben Regel. Eine Entwarnung kommt nur nach einem zugestellten Alarm.
- Die Warteschlange übersteht Neustarts. Bei Fehlern gibt es höchstens fünf Versuche mit wachsenden Pausen; automatische Nachrichten, die älter als 24 Stunden sind, entfallen.
- Ein Test umgeht Hauptschalter und Ruhezeit, ist aber auf einen Test je 30 Sekunden begrenzt. Bei pausierter Erfassung und im Demo-Modus wird nicht gesendet.

> [!NOTE]
> Fällt der Host oder das Internet ganz aus, kann Kilowatch keine Nachricht mehr senden. Dafür brauchst du einen unabhängigen Monitor. Die frühere Signal-Anbindung gibt es nicht mehr; alte Einstellungen werden ignoriert und gespeicherte Gateway-Token beim Start gelöscht.

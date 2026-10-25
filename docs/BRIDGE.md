# Bridge, Gerätesuche und MQTT

Kilowatch liest die Tibber-Bridge nur lesend über ihren lokalen Webserver (HTTP Basic Auth, Benutzer meist `admin`, Passwort vom Aufkleber). **Es setzt keine Bridge zurück und ändert keine Bridge-Parameter.** Eine funktionierende Kopplung ist die Ausgangsbasis; flashe keine Firmware und ändere nichts auf Verdacht.

| Endpunkt der Bridge | Inhalt |
|---|---|
| `/node_data.json?node_id=<n>` | aktuelles Zählertelegramm (meist binäres SML), neuere Firmware |
| `/data.json?node_id=<n>` | dasselbe bei älterer Firmware |
| `/status.json` | Firmware, MQTT-Status, Laufzeit (nur freigegebene Felder, nie die WLAN-Konfiguration) |
| `/node_metrics.json?node_id=<n>` | Empfangsdiagnose (Funkpegel, Batteriespannung) |

Kilowatch wählt den Datenpfad nach tatsächlich lesbaren Daten. Node 1 ist der übliche Start.

## Bridge im Heimnetz suchen

**Einstellungen → Bridge im Heimnetz suchen** sucht mögliche Bridges, auch ohne Passwort.

1. Den vorgeschlagenen Netzbereich prüfen (aus der Browser-Adresse abgeleitet; `/24` ist nur ein Vorschlag, denn der Container kennt die echte Netzmaske nicht) und bei Bedarf als CIDR eintragen, z. B. `192.168.1.0/24`. Größere Netze durchsuchst du in /24-Teilen nacheinander.
2. **Im Subnetz suchen.** Das dauert etwa eine Minute (höchstens 256 Adressen), dazwischen mindestens 30 Sekunden Pause.
3. Bei einem Fund **Verwenden**. Ein bestätigter Gerätename wird bevorzugt, sonst bekommst du die IP; bei DHCP trägst du besser den Namen aus dem Router ein.
4. Bridge-Passwort eingeben und **Verbindung prüfen**. Erst dieser Test bestätigt SML-Zugriff und Node-ID.

Die Suche liest nur Port 80, folgt keinen Weiterleitungen und schickt keine Zugangsdaten an unbekannte Geräte. Öffentliche, Loopback-, Link-Local- und Multicast-Netze lehnt sie ab; im Demo-Modus ist sie aus. Andere Firmware, ein abgeschalteter Webserver oder eine Firewall verhindern den Fund, dann gibst du die Adresse von Hand ein.

## Lokalen Webserver dauerhaft aktivieren

Starte die Bridge einmal normal neu und prüfe, ob `http://<Bridge-Name>` danach erreichbar bleibt. Wenn ja, ist nichts weiter nötig.

Nur wenn der Webserver danach fehlt, hilft die [Community-Vorbereitung](https://github.com/marq24/ha-tibber-pulse-local/blob/main/preparation.md) (Access-Point-Modus, nicht der Werksreset). Lies zuerst nur: `param_get 39`. Bestätigt die Antwort `webserver_force_enable` und passt die Anleitung zu deiner Firmware, aktivierst du ihn mit `param_set 39 TRUE` und `param_store`. Starte danach normal neu und nutze die gewöhnliche LAN-Adresse, nicht `10.133.70.1` (die gehört zum temporären Access Point).

## Ohne Tibber-Stromtarif

Kilowatch braucht keine Tibber-Verbrauchs-API. Deinen Tarif trägst du lokal ein ([Tarife](TARIFE.md)). Laut Community-Dokumentation braucht die Bridge-Firmware mancher Nichtkunden aber eine funktionierende MQTT-Verbindung, unabhängig davon, dass Kilowatch per HTTP liest.

## Vom Tibber-Cloud-Upload lösen (optional)

> [!WARNING]
> Das ist eine eigene Umstellung der Bridge, die Kilowatch nie automatisch vornimmt. Das Verfahren ist an echter Hardware noch nicht im Dauerbetrieb bestätigt. Gehe schrittweise vor.

1. **Istzustand notieren:** Firmware, Node-ID, MQTT-Ziel und Topics. Eine Parameterkopie kann WLAN-Daten und Schlüssel enthalten und gehört nicht ins Repository.
2. **Namen prüfen:** Host und Bridge brauchen auflösbare Namen. Ob deine Firmware den MQTT-Hostnamen selbst auflösen kann, prüfst du vorher; wenn nicht, lass die Umstellung aus.
3. **Firewall:** MQTT-Port TCP 1883 nur aus dem Heimnetz oder Geräte-Netz zulassen, nie aus Gast-Netz oder Internet, und keine Portweiterleitung.
4. **Broker starten** (oder einen vorhandenen nutzen):

   ```sh
   docker compose -f compose.yaml -f compose.mqtt.yaml up -d
   ```

   `-f compose.mqtt.yaml` gehört künftig zu jedem Update-Befehl; auf Synology kannst du ein eigenes Projekt aus dieser Datei anlegen. Ein Verbindungstest vom PC: `python tools/mqtt_smoke.py --host <Hostname> --port 1883`.
5. **Bridge umstellen** nach der [Community-Anleitung](https://github.com/marq24/ha-tibber-pulse-local/blob/main/TIBBER-PULSE-AS-NON-TIBBER-CUSTOMER.md). Ändere nur Felder, die deine Firmware wirklich hat, und lass vorhandene Zertifikate und Schlüssel unangetastet:

   | Parameter | Wert |
   |---|---|
   | `mqtt_url` | Hostname deines Hosts, ohne `http://` |
   | `mqtt_port` | 1883 (oder `MQTT_PORT` aus der `.env`) |
   | `mqtt_topic` | `tibber-bridge/data/publish` |
   | `mqtt_topic_sub` | `tibber-bridge/data/receive` |
   | `mqtt_valid` / `mqtt_pause` | `true` / `false`, falls vorhanden |

6. **Testen:** Bridge stromlos machen, Host und Broker neu starten und mindestens 24 Stunden auf stabile Verbindung, neue Telegramme und Lücken achten.
7. **Erst danach** am Router den ausgehenden Internetzugriff der Bridge sperren und erneut neu starten und 24 Stunden prüfen.

> [!IMPORTANT]
> Der Broker läuft ohne Passwort, weil die Bridge-Firmware das oft verlangt. Er erlaubt nur Schreiben auf das Publish-Topic und Lesen auf das Receive-Topic, doch das ersetzt keine Netzwerkbegrenzung: Im erlaubten Netz kann jedes Gerät diese Topics nutzen. Ein getrenntes Geräte-Netz oder ein Broker mit Anmeldung (falls die Bridge das kann) grenzt das weiter ein.

**Rückweg:** Wird die Bridge instabil, nimm die Internetsperre zurück, stelle die notierten MQTT-Einstellungen wieder her und starte normal neu. Kilowatch und die Historie bleiben dabei unberührt.

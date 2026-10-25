# Die vorhandene Bridge lokal betreiben

## Typische Endpunkte der Bridge

Kilowatch liest die Bridge ausschließlich lesend über ihren lokalen Webserver mit HTTP Basic Auth (Benutzer meist `admin`, Passwort laut Aufkleber auf der Bridge). Je nach Firmware stehen diese Endpunkte zur Verfügung:

| Endpunkt | Inhalt |
|---|---|
| `/` | Weboberfläche der Bridge |
| `/node_data.json?node_id=<n>` | aktuelles Zählertelegramm (meist binäres SML), neuere Firmware |
| `/data.json?node_id=<n>` | dasselbe bei älterer Firmware |
| `/status.json` | Firmware, MQTT-Status, Laufzeit |
| `/node_metrics.json?node_id=<n>` | Empfangsdiagnose des Lesekopfs (Funkpegel, Batteriespannung) |

Die Anwendung wählt den Datenpfad anhand tatsächlich dekodierbarer Daten; Node 1 ist der übliche Ausgangspunkt. Aus `/status.json` werden nur ausdrücklich freigegebene Felder übernommen, nie die WLAN-Konfiguration.

**Kilowatch setzt keine Bridge zurück und ändert keine Parameter.** Eine funktionierende Kopplung ist die Ausgangsbasis. Keine Firmware flashen oder Parameter auf Verdacht ändern.

## Bridge im Heimnetz suchen

Unter **Einstellungen → Bridge im Heimnetz suchen** kann Kilowatch nach möglichen Tibber-Bridges suchen, auch bevor das Bridge-Passwort eingegeben wurde.

1. Netzvorschlag prüfen. Er wird aus der Browser-Adresse, einer bereits eingetragenen Bridge oder dem Hostnamen abgeleitet. Da der Container die echte LAN-Netzmaske nicht zuverlässig kennt, wird `/24` ausdrücklich nur vorgeschlagen.
2. Bei Bedarf das tatsächliche lokale Netz als CIDR eintragen, beispielsweise `192.168.1.0/24`. Das Beispiel ist kein gespeicherter Standard. Größere Netze in einzelnen /24-Teilnetzen nacheinander durchsuchen.
3. **Im Subnetz suchen** wählen. Die App prüft bis zu 254 übliche Geräteadressen eines /24-Netzes, höchstens 256 Adressen insgesamt. Der Lauf kann etwa eine Minute dauern; zwischen Suchläufen liegen mindestens 30 Sekunden.
4. Bei einem Fund **Verwenden** wählen. Ein per Rückwärtsauflösung gefundener und vorwärts bestätigter Gerätename wird bevorzugt. Fehlt ein solcher DNS-Name, wird zunächst die aktuelle IP angeboten; bei DHCP den tatsächlichen Namen aus dem Router einsetzen.
5. Bridge-Passwort eingeben, **Verbindung prüfen** und speichern. Erst der angemeldete Verbindungstest bestätigt SML-Zugriff und Node-ID. Ein Fund ist zunächst nur eine mögliche Bridge.

Die Suche liest ausschließlich HTTP-Port 80 und folgt keinen Weiterleitungen. Sie verwendet keine Bridge-Zugangsdaten und überträgt keine gespeicherten Passwörter an unbekannte Geräte. Pro Gerät und Antwort gelten Zeit- und Größengrenzen, die Zahl paralleler Abrufe ist begrenzt. Öffentliche, Loopback-, Link-Local- und Multicast-Netze sowie größere Suchbereiche werden abgelehnt. Im Demo-Modus ist die Suche aus.

Eine andere Firmware, ein ausgeschalteter Webserver oder eine Firewall kann die Erkennung verhindern; die manuelle Eingabe bleibt möglich. Ein normaler DNS-Name aus dem Router ist für den Docker-Betrieb geeigneter als eine nur per mDNS veröffentlichte `.local`-Adresse. Die Anwendung legt keine DNS-Einträge an und verlangt keine feste IP. Die Funktion wurde mit simulierten Geräten getestet; ein Scan in einem echten Netz ist nicht automatisiert abgedeckt.

## Dauerhaften lokalen Webserver kontrollieren

Zuerst die Bridge einmal regulär neu starten und prüfen, ob `http://<Bridge-Name>` danach weiterhin erreichbar ist. Falls ja, ist für Kilowatch keine weitere Bridge-Änderung nötig. Den tatsächlichen Gerätenamen im Router nachsehen; DHCP kann aktiv bleiben. In Kilowatch den Namen ohne Protokoll und Port eintragen.

Nur falls der Webserver danach nicht erreichbar ist: Die [Community-Vorbereitung](https://github.com/marq24/ha-tibber-pulse-local/blob/main/preparation.md) beschreibt den Access-Point-Modus. Dieser ist vom Werksreset zu unterscheiden. Bei erreichbarer Konsole zunächst ausschließlich lesen:

```text
param_get 39
```

Nur wenn die Antwort eindeutig `webserver_force_enable` für Parameter 39 bestätigt und die Anleitung zur vorhandenen Firmware passt, die dort beschriebene dauerhafte Aktivierung verwenden:

```text
param_set 39 TRUE
param_store
```

Bei älterer Firmware kann der Parameter stattdessen im Params-Reiter stehen. Wegen Firmwareunterschieden ist die Prüfung des Namens erforderlich. Danach regulär neu starten und erneut die normale LAN-IP verwenden. Nicht `10.133.70.1` als dauerhafte Bridge-IP eintragen: Diese Adresse gehört zum temporären Access Point.

## Ohne Tibber-Stromtarif

Für Kilowatch gibt es keine Tarifabfrage und keine Anbindung an die Tibber-Verbrauchs-API. Der eigene Stromlieferant und seine Bruttopreise werden lokal hinterlegt. Die bestehende Pulse-/Bridge-Kopplung muss weiterhin gültige Telegramme liefern.

Die von der Community dokumentierte Besonderheit ist eine möglicherweise erforderliche **funktionierende MQTT-Verbindung** der Bridge. Sie betrifft deren Firmwareverhalten, unabhängig davon, dass Kilowatch die Messdaten per HTTP liest.

## Vollständig von Tibber unabhängig werden

Dieses Verfahren ist eine gesonderte Umstellung der Bridge. Es wurde an deinem Gerät noch nicht ausgeführt oder im Dauerbetrieb bestätigt. Die Anwendung schreibt keine Bridge-Parameter automatisch.

1. **Istzustand sichern.** Firmware, aktive Node-ID, aktuelle MQTT-Zieladresse/-Port und Topic-Einstellungen lokal notieren. Eine Parameterkopie kann WLAN-Zugang, Gerätezertifikate und private Schlüssel enthalten und gehört nicht ins Repository.
2. **DNS-Namen prüfen.** Tatsächlich auflösbare Namen für Host und Bridge verwenden, beispielsweise die vom Router gepflegten Gerätenamen. Keine feste IP oder DHCP-Reservierung erforderlich. Beim MQTT-Ziel muss auch die konkrete Bridge-Firmware den Hostnamen auflösen können; dies ist vor einer Cloud-Trennung am Gerät zu prüfen. Falls sie das nicht kann, diese optionale Umstellung zunächst offen lassen und den funktionierenden HTTP-Betrieb weiterverwenden.
3. **Firewall vorbereiten.** MQTT-Port TCP 1883 ausschließlich aus dem vertrauenswürdigen Heimnetz beziehungsweise einem dafür vorgesehenen Geräte-Netz zulassen; Gastnetz und Internet ausschließen. Damit setzt die Regel keine feste Bridge-IP voraus. Benötigte Dienste nicht pauschal blockieren. Im Router kein Portforwarding einrichten. Der optionale Broker lauscht mit `MQTT_BIND=0.0.0.0` auf den Schnittstellen des Hosts; dies ist eine Bindeadresse und keine statische Geräteadresse.
4. **Broker starten.** Bestehende eigene Broker bevorzugt weiterverwenden, wenn deren Konfiguration passt. Andernfalls:

   ```sh
   docker compose -f compose.yaml -f compose.mqtt.yaml up -d
   ```

   Wer die App selbst baut, verwendet `compose.build.yaml` statt `compose.yaml` und ergänzt `--build`. Bei Updates `-f compose.mqtt.yaml` mitführen. Auf Synology kann der Container Manager ein separates MQTT-Projekt mit dem Service aus `compose.mqtt.yaml` anlegen; relative Konfigurationspfade müssen zum Projektordner passen. Am eindeutigsten ist der gezeigte Befehl.

5. **Broker zuerst prüfen.** Log auf erfolgreiche Verbindung prüfen. Vom PC mit Python lässt sich mit `python tools/mqtt_smoke.py --host <Hostname> --port 1883` ein künstlicher MQTT-Verbindungstest ausführen. Anschließend die geplanten LAN-/Geräte-Netz-Regeln kontrollieren.
6. **Bridge kontrolliert umstellen.** Die [Community-Anleitung für Nichtkunden](https://github.com/marq24/ha-tibber-pulse-local/blob/main/TIBBER-PULSE-AS-NON-TIBBER-CUSTOMER.md) nennt `mqtt_url`, `mqtt_port`, `mqtt_topic`, `mqtt_topic_sub`, `mqtt_valid` und `mqtt_pause`. Nur vorhandene, eindeutig identifizierte Felder passend zur eigenen Firmware ändern:

   | Parameter | Vorgesehener Wert |
   |---|---|
   | `mqtt_url` | tatsächlicher Hostname, ohne `http://`; DNS-Unterstützung der Firmware vorher prüfen |
   | `mqtt_port` | 1883 oder lokaler, in `.env` festgelegter Port |
   | `mqtt_topic` | `tibber-bridge/data/publish` |
   | `mqtt_topic_sub` | `tibber-bridge/data/receive` |
   | `mqtt_valid` | true, sofern von dieser Firmware gefordert |
   | `mqtt_pause` | false, sofern vorhanden |

   Jede Einstellung nach der zur Firmware passenden Oberfläche speichern. Keine unverifizierten Konsolenbefehle für WLAN-Modus, Zertifikate oder Firmware verwenden. Vorhandene Zertifikate und private Schlüssel erhalten. Die aktuelle Community-Anleitung beschreibt Fälle mit intern erforderlichen Zertifikatsfeldern; daraus folgt **keine pauschale Notwendigkeit**, neue Zertifikate zu beschaffen. Bei abweichendem Verhalten vor einer weiteren Umstellung den konkreten Zustand klären.

7. **Neustarts und Ausfälle testen.** Bridge einmal stromlos machen und neu starten; Host-/Broker-Neustart ebenfalls kontrolliert testen. Danach mindestens 24 Stunden auf stabile WLAN-Verbindung, neue Telegramme und den Verbleib außerhalb des Einrichtungsmodus achten. Erfasste Lücken kontrollieren.
8. **Erst danach Internet sperren.** Am Router ausgehenden Internetzugriff der Bridge sperren, während Bridge → Host:MQTT und Host → Bridge:HTTP im LAN weiter funktionieren. Erneut Neustart und mindestens 24 Stunden Betrieb testen. Gerätezeit und Diagnosewerte im Blick behalten.

Der Broker ist ohne Passwort konfiguriert, weil die dokumentierte Bridge-Variante oft keine beliebig wählbaren MQTT-Nutzer bietet. Er akzeptiert ausschließlich Schreiben auf das Publish-Topic und Lesen auf das Receive-Topic; alle anderen Topics sind gesperrt. **Diese Topic-ACL ersetzt keine Netzwerkbegrenzung.** Im erlaubten Heimnetz könnten auch andere Geräte auf diesen beiden Topics zugreifen. Ein getrenntes Geräte-Netz kann den Zugriff weiter eingrenzen, ohne feste IPs zu verlangen. Unterstützt die konkrete Bridge MQTT-Authentifizierung oder TLS, kann stattdessen ein entsprechend konfigurierter vorhandener Broker verwendet werden.

Ein erfolgreicher Broker-Verbindungstest beweist noch nicht, dass die Bridge den gesamten Betrieb damit dauerhaft aufrechterhält. Nach Firmwarewechseln diesen Punkt erneut prüfen.

## Rückweg

Falls die Bridge nach der Umstellung instabil wird: Internetsperre zurücknehmen, gesicherte ursprüngliche MQTT-Einstellungen wiederherstellen und regulär neu starten. Dabei die dauerhafte lokale Webserver-Freigabe erhalten, soweit unterstützt. Das Projekt und seine bisherige Historie müssen dafür nicht gelöscht werden.

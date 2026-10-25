# Bridge im lokalen Subnetz suchen

Unter **Einstellungen → Bridge im Heimnetz suchen** kann Kilowatch nach möglichen Tibber-Bridges suchen, auch bevor das Bridge-Passwort eingegeben wurde.

1. Netzvorschlag prüfen. Er wird aus der Browser-Adresse, einer bereits eingetragenen Bridge oder dem NAS-Namen abgeleitet. Da der Container die echte LAN-Netzmaske des NAS nicht zuverlässig kennt, wird `/24` ausdrücklich nur vorgeschlagen.
2. Bei Bedarf das tatsächliche lokale Netz als CIDR eintragen, beispielsweise `192.168.1.0/24`. Dieses Beispiel ist kein gespeicherter Geräte- oder Netzstandard. Bei größeren Netzen einzelne /24-Teilnetze nacheinander durchsuchen.
3. **Im Subnetz suchen** wählen. Die App prüft bis zu 254 übliche Geräteadressen eines /24-Netzes, höchstens 256 Adressen insgesamt. Der Lauf kann etwa eine Minute dauern. Zwischen Suchläufen liegen mindestens 30 Sekunden.
4. Bei einem Fund **Verwenden** wählen. Ein per Rückwärtsauflösung gefundener und vorwärts bestätigter FQDN wird bevorzugt. Fehlt ein solcher DNS-Name, wird zunächst die aktuelle IP angeboten; für DHCP den tatsächlichen Namen aus dem Router einsetzen.
5. Bridge-Passwort eingeben, **Verbindung prüfen** und danach speichern. Erst der angemeldete Verbindungstest bestätigt SML-Zugriff und Node-ID. Ein Fund ist zunächst nur eine mögliche Bridge.

Die Suche liest ausschließlich HTTP-Port 80 und folgt keinen Weiterleitungen. Sie verwendet keine Bridge-Zugangsdaten und überträgt keine gespeicherten Passwörter an unbekannte Geräte. Pro Gerät und Antwort gelten Zeit-/Größengrenzen; die Zahl paralleler Abrufe ist begrenzt. Öffentliche, Loopback-, Link-Local- und Multicast-Netze sowie größere Suchbereiche werden abgelehnt. Im Demo-Modus ist die Suche aus.

Eine andere Firmware, ein ausgeschalteter Webserver oder eine Firewall kann die Erkennung verhindern. Die manuelle Eingabe eines FQDN bleibt möglich. Ein normaler DNS-Name aus dem Router ist für diesen Docker-Aufbau geeigneter als eine ausschließlich per mDNS veröffentlichte `.local`-Adresse. Die Anwendung legt keine DNS-Einträge an und verlangt keine feste IP.

Die Funktion und ihre Grenzen wurden mit simulierten Geräten getestet. Ein echter Subnetzscan auf deinem NAS ist noch nicht erfolgt.

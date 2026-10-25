"""Begrenzte, explizit gestartete HTTP-Suche im privaten IPv4-Subnetz."""
import asyncio
import ipaddress
import socket
import time

import httpx

from .network import private_address, resolve_local, validate_host


def private_ipv4(value):
    """Private IPv4-Adresse als Objekt, sonst None (auch für ungültige Eingaben)."""
    try:
        address = ipaddress.IPv4Address(value)
    except ValueError:
        return None
    return address if private_address(address) else None


def search_network(value):
    try:
        network = ipaddress.IPv4Network(value, strict=False)
    except ValueError:
        raise ValueError("Lokales IPv4-Netz als CIDR angeben, zum Beispiel 192.168.1.0/24.") from None
    if network.prefixlen < 24 or not private_ipv4(str(network.network_address)) or not private_ipv4(str(network.broadcast_address)):
        raise ValueError("Nur private lokale Netze mit höchstens 256 Adressen (/24 bis /32) durchsuchen.")
    return network


async def suggestions(client_address, bridge_host, nas_host):
    found = []
    def add(value, reason):
        address = private_ipv4(value)
        if address:
            network = str(ipaddress.IPv4Network(f"{address}/24", strict=False))
            if network not in [item["network"] for item in found]:
                found.append({"network": network, "reason": reason})
    add(client_address, "Browser-Netz, /24 vorgeschlagen")
    for host, label in [(bridge_host, "Netz der eingetragenen Bridge, /24 vorgeschlagen"), (nas_host, "NAS-Name, /24 vorgeschlagen")]:
        if host:
            try:
                for address in await resolve_local(host):
                    add(address, label)
            except ValueError:
                pass
    return found


async def device_name(address):
    try:
        name = (await asyncio.wait_for(asyncio.to_thread(socket.gethostbyaddr, address), timeout=1))[0]
        name = validate_host(name)
        if address in await resolve_local(name):
            return name
    except (ValueError, OSError, asyncio.TimeoutError):
        pass
    return None


async def probe(client, address):
    # Keine Basic-Auth-Daten, Cookies oder Redirects an unbekannte Geräte senden.
    for path in ("/status.json", "/"):
        try:
            async with client.stream("GET", f"http://{address}{path}") as response:
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk[:16384-len(body)])
                    if len(body) >= 16384:
                        break
                evidence = (response.headers.get("www-authenticate", "") + " " + body.decode("utf-8", "ignore")).lower()
                if "tibber" in evidence or ("pulse" in evidence and "bridge" in evidence) or ("node_data.json" in evidence and "node_metrics.json" in evidence):
                    try:
                        name = await asyncio.wait_for(device_name(address),timeout=1)
                    except asyncio.TimeoutError:
                        name = None
                    return {"ip": address, "host": name or address, "fqdn": name, "hint": "Mögliche Tibber-Bridge; anschließend mit deinen Zugangsdaten prüfen."}
        except (httpx.HTTPError, OSError):
            break
    return None


class Discovery:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.last_scan = None

    async def scan(self, cidr, demo=False):
        network = search_network(cidr)
        if demo:
            raise ValueError("Die Gerätesuche ist im Demo-Modus ausgeschaltet.")
        if self.lock.locked():
            raise ValueError("Eine Gerätesuche läuft bereits.")
        if self.last_scan is not None and time.monotonic()-self.last_scan < 30:
            raise ValueError("Bitte 30 Sekunden zwischen Suchläufen warten.")
        async with self.lock:
            self.last_scan = time.monotonic()
            semaphore = asyncio.Semaphore(16)
            async with httpx.AsyncClient(timeout=httpx.Timeout(1.2),trust_env=False,follow_redirects=False,
                                         limits=httpx.Limits(max_connections=16,max_keepalive_connections=0)) as client:
                async def check(address):
                    async with semaphore:
                        try:
                            return await asyncio.wait_for(probe(client, str(address)),timeout=4)
                        except asyncio.TimeoutError:
                            return None
                results = await asyncio.gather(*(check(address) for address in network.hosts()))
            devices = [item for item in results if item]
            return {"network": str(network), "checked": len(results), "devices": devices}

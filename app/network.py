"""Lokale Namen regelmäßig auflösen und nur private Zieladressen zulassen."""
import asyncio
import ipaddress
import re
import socket



def private_address(value):
    ip = ipaddress.ip_address(value)
    # Loopback ist "private", wäre im Container aber die App selbst.
    return (ip.is_private and not ip.is_loopback and not ip.is_unspecified and not ip.is_multicast
            and not ip.is_reserved and not ip.is_link_local)


def validate_host(value, single_label=False):
    value = value.strip().rstrip(".").lower()
    if not value or len(value) > 253 or any(c in value for c in "/\\:@?#%[]"):
        raise ValueError("Lokale IP-Adresse oder FQDN ohne Protokoll, Port oder Pfad angeben.")
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        try:
            name = value.encode("idna").decode("ascii")
        except UnicodeError:
            raise ValueError("Hostname ist ungültig.") from None
        if (not single_label and "." not in name) or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in name.split(".")):
            raise ValueError("Vollständigen Gerätenamen angeben, z. B. tibber-bridge.lan.")
        if re.fullmatch(r"[0-9.]+", name):
            raise ValueError("IP-Adresse ist ungültig.")
        return name
    if not private_address(str(address)):
        raise ValueError("Die Bridge muss im lokalen Netz liegen.")
    return str(address)


async def resolve_local(host):
    try:
        ipaddress.ip_address(host)
        addresses = [host]
    except ValueError:
        try:
            records = await asyncio.wait_for(asyncio.to_thread(socket.getaddrinfo, host, None, socket.AF_INET, socket.SOCK_STREAM), timeout=5)
        except (OSError, asyncio.TimeoutError):
            raise ValueError("Gerätename nicht auflösbar. Heimnetz-DNS und Gerätenamen im Router prüfen.") from None
        addresses = list(dict.fromkeys(record[4][0] for record in records))
    if not addresses or any(not private_address(address) for address in addresses):
        raise ValueError("Gerätename zeigt nicht ausschließlich auf lokale Adressen; Zugriff abgelehnt.")
    return addresses[:4]


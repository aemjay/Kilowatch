"""Lokale Namen regelmäßig auflösen und HTTP-Ziele auf die geprüfte IP binden."""
import asyncio
import ipaddress
import re
import socket
from urllib.parse import urlsplit

import httpx


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
            raise ValueError("Vollständigen Gerätenamen angeben, z. B. tibber-bridge.fritz.box.")
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


def local_url(url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError()
        host = validate_host(parsed.hostname or "", single_label=True)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not 1 <= port <= 65535:
            raise ValueError()
    except ValueError:
        raise ValueError("Lokale Gateway-URL ohne Zugangsdaten, Abfrage oder Fragment angeben.") from None
    return parsed, host, port


async def local_request(url, path, method="GET", payload=None, token="", max_bytes=65536, transport=None):
    parsed, host, port = local_url(url)
    addresses = await resolve_local(host)
    default_port = 443 if parsed.scheme == "https" else 80
    original_host = host + (f":{port}" if port != default_port else "")
    async with httpx.AsyncClient(timeout=40, trust_env=False, follow_redirects=False, transport=transport) as client:
        for address in addresses:
            try:
                headers = {"Host": original_host}
                if token:
                    headers["Authorization"] = "Bearer " + token
                target = f"{parsed.scheme}://{address}:{port}{parsed.path.rstrip('/')}{path}"
                async with client.stream(method, target, json=payload, headers=headers,
                                         extensions={"sni_hostname": host}) as response:
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > max_bytes:
                            raise ValueError("Gateway-Antwort ist zu groß.")
                    return response.status_code, bytes(body), response.headers.get("Content-Type", "")
            except httpx.HTTPError:
                continue
    raise ValueError("Signal-Gateway nicht erreichbar. Container, DNS und lokalen Port prüfen.")

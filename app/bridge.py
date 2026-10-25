import hashlib
import json
import time

import httpx

from .decoder import decode
from .network import resolve_local, validate_host


class BridgeError(ValueError):
    pass


class Bridge:
    def __init__(self, settings, password, transport=None):
        self.settings = settings
        self.host = validate_host(settings["bridge_host"])
        self.password = password
        self.endpoint = None
        self.resolved_addresses = []
        self.client = httpx.AsyncClient(
            auth=httpx.BasicAuth(settings["bridge_user"], password), timeout=8,
            follow_redirects=False, trust_env=False, transport=transport,
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=0),
        )

    async def close(self):
        await self.client.aclose()

    async def request(self, path):
        self.resolved_addresses = await resolve_local(self.host)
        last_error = None
        for address in self.resolved_addresses:
            try:
                return await self.request_address(address, path)
            except httpx.HTTPError as exc:
                last_error = exc
        raise BridgeError("Bridge nicht erreichbar (" + type(last_error).__name__ + "). LAN und Webserver prüfen.") from None

    async def request_address(self, address, path):
        async with self.client.stream("GET", f"http://{address}{path}", headers={"Host": self.host, "Cache-Control": "no-cache"}) as response:
            if response.status_code == 401:
                raise BridgeError("Bridge-Zugang abgelehnt. Benutzer und aufgedrucktes Passwort prüfen.")
            if response.status_code in (404, 405):
                return None
            if response.status_code != 200:
                raise BridgeError(f"Bridge meldet HTTP {response.status_code}.")
            result = bytearray()
            async for chunk in response.aiter_bytes():
                result.extend(chunk)
                if len(result) > 65536:
                    raise BridgeError("Bridge-Antwort zu groß.")
            return bytes(result)

    async def read(self):
        node = self.settings["node_id"]
        candidates = [self.endpoint] if self.endpoint else ["/node_data.json", "/data.json"]
        errors = []
        for endpoint in candidates:
            payload = await self.request(f"{endpoint}?node_id={node}")
            if payload is None:
                continue
            try:
                reading = decode(payload)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            self.endpoint = endpoint
            return reading, hashlib.sha256(payload).hexdigest()
        if self.endpoint:
            self.endpoint = None
        raise BridgeError("; ".join(errors) or "Kein Daten-Endpunkt gefunden. Node-ID und lokalen Webserver prüfen.")

    async def diagnostics(self):
        result = {"checked_at": time.time()}
        for endpoint in ["/node_metrics.json", "/metrics.json"]:
            raw = await self.request(f'{endpoint}?node_id={self.settings["node_id"]}')
            if raw is None:
                continue
            try:
                data = json.loads(raw)
                node, ir = data.get("node", {}), data.get("ir", {})
                result.update({
                    "rssi_dbm": node.get("avg_rssi"),
                    "battery_v": node.get("battery_voltage"),
                    "temperature_c": node.get("temperature"),
                    "meter_mode": node.get("meter_mode"),
                    "invalid_readings": ir.get("invalid_meter_readings_count"),
                    "delivery_percent": data.get("packet_delivery_rate"),
                })
            except (ValueError, AttributeError):
                pass
            break
        raw = await self.request("/status.json")
        if raw:
            try:
                data = json.loads(raw)
                # Nur ausdrücklich freigegebene Felder; nie WLAN-Konfiguration.
                result.update(firmware=data.get("firmware"), mqtt_status=data.get("mqtt_status"),
                              uptime=data.get("up_time"))
            except ValueError:
                pass
        return result

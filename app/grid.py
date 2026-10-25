"""Optionaler Abruf von CO₂-Intensität und Ökostromanteil des Stromnetzes bei Energy-Charts (Fraunhofer ISE).

Gesendet werden nur Land und Zeitraum, keine Messwerte. Ohne gewähltes Land findet kein Abruf statt.
Daten: Energy-Charts.info, CC BY 4.0. Die CO₂-Werte sind Schätzungen der Quelle (CO₂-Äquivalente
je kWh, Lebenszyklus). Verwendet werden nur veröffentlichte Werte; die Prognosereihe der Quelle passt
an der Übergangsstelle nicht zu den Messwerten (teils um ein Vielfaches) und bleibt deshalb unberücksichtigt.
Gemessene Werte erscheinen mit einigen Stunden Verzögerung.
"""
import asyncio
import json
import math
import time

import httpx

from .i18n import UserError, _

COUNTRIES = ("de", "nl", "no", "se")
SOURCE = "Energy-Charts.info (Fraunhofer ISE), CC BY 4.0"
API = "https://api.energy-charts.info"
REFRESH_INTERVAL = 3600
BACKFILL_DAYS = 31
MAX_BODY = 3_000_000


def _series(payload, values):
    stamps = payload["unix_seconds"]
    if not isinstance(stamps, list) or not isinstance(values, list) or len(stamps) != len(values) or len(stamps) > 20000:
        raise ValueError()
    return zip(stamps, values)


def parse_co2(payload):
    """Veröffentlichte Viertelstundenwerte {start: g_kwh}; Prognosen werden nicht übernommen."""
    try:
        result = {}
        for start, value in _series(payload, payload["co2eq"]):
            if value is None:
                continue
            start, value = int(start), float(value)
            if start % 900 or not math.isfinite(value) or not 0 <= value <= 2000:
                raise ValueError()
            result[start] = value
        return result, bool(payload.get("deprecated"))
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError("Strommix-Quelle liefert kein gültiges Format.") from None


def parse_share(payload):
    """Ökostromanteil an der Last in Prozent je Viertelstunde."""
    try:
        series = next((p["data"] for p in payload["production_types"] if p["name"] == "Renewable share of load"), None)
        if series is None:
            return {}, bool(payload.get("deprecated"))
        result = {}
        for start, value in _series(payload, series):
            if value is None:
                continue
            start, value = int(start), float(value)
            if start % 900 or not math.isfinite(value) or not 0 <= value <= 1000:
                raise ValueError()
            result[start] = value
        return result, bool(payload.get("deprecated"))
    except (KeyError, TypeError, ValueError, OverflowError, StopIteration):
        raise ValueError("Strommix-Quelle liefert kein gültiges Format.") from None


def demo_values(start, end, now):
    """Künstliche, tageszeitabhängige Werte für den Demo-Modus (keine Verbindung ins Internet)."""
    co2, share = {}, {}
    for ts in range(int(start // 900) * 900, int(min(end, now)), 900):
        phase = math.sin((ts % 86400) / 86400 * 2 * math.pi - math.pi / 2)
        co2[ts] = round(380 - 140 * phase, 1)
        share[ts] = round(55 + 25 * phase, 1)
    return co2, share


class Grid:
    def __init__(self, store, demo=False, transport=None):
        self.store, self.demo, self.transport = store, demo, transport
        self.wakeup = asyncio.Event()

    def country(self):
        return self.store.settings().get("grid_country") or ""

    def status(self):
        return self.store.state("grid_status", {"fetched_at": None, "error": "", "deprecated": False})

    def client(self):
        return httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False, transport=self.transport)

    async def fetch(self, client, path, params):
        async with client.stream("GET", API + path, params=params) as response:
            if response.status_code != 200:
                raise UserError("Strommix-Quelle momentan nicht erreichbar (HTTP {status}).", status=response.status_code)
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_BODY:
                    raise ValueError("Antwort der Strommix-Quelle ist zu groß.")
        return json.loads(body)

    def save(self, country, co2, share):
        with self.store.transaction():
            self.store.conn.executemany(
                "INSERT INTO grid_intensity(country,start,g_kwh) VALUES(?,?,?) "
                "ON CONFLICT(country,start) DO UPDATE SET g_kwh=excluded.g_kwh",
                [(country, start, value) for start, value in co2.items()])
            self.store.conn.executemany(
                "INSERT INTO grid_intensity(country,start,renewable_share) VALUES(?,?,?) "
                "ON CONFLICT(country,start) DO UPDATE SET renewable_share=excluded.renewable_share",
                list((country, start, value) for start, value in share.items()))

    async def refresh(self, now=None):
        country = self.country()
        if not country:
            return
        now = time.time() if now is None else now
        latest = self.store.rows("SELECT MAX(start) AS start FROM grid_intensity WHERE country=? AND g_kwh IS NOT NULL", (country,))[0]["start"]
        # Ab dem letzten veröffentlichten Wert (mit Puffer) nachladen; beim ersten Abruf einen Monat.
        start = max(now - BACKFILL_DAYS * 86400, (latest or 0) - 6 * 3600)
        try:
            if self.demo:
                co2, share = demo_values(start, now - 4 * 3600, now)
                deprecated = False
            else:
                async with self.client() as client:
                    co2, deprecated_co2 = parse_co2(await self.fetch(client, "/co2eq", {"country": country, "start": int(start), "end": int(now)}))
                    share, deprecated_share = parse_share(await self.fetch(client, "/public_power", {"country": country, "start": int(start), "end": int(now)}))
                deprecated = deprecated_co2 or deprecated_share
            await asyncio.to_thread(self.save, country, co2, share)
            self.store.set_state("grid_status", {"fetched_at": now, "error": "", "deprecated": deprecated, "country": country})
        except (ValueError, httpx.HTTPError, OSError, asyncio.TimeoutError) as exc:
            message = str(exc) if isinstance(exc, ValueError) else _("Strommix-Quelle nicht erreichbar. Später erneut versuchen.")
            self.store.set_state("grid_status", dict(self.status(), error=message, country=country))

    async def run(self):
        while True:
            await self.refresh()
            try:
                await asyncio.wait_for(self.wakeup.wait(), timeout=REFRESH_INTERVAL)
                self.wakeup.clear()
            except asyncio.TimeoutError:
                pass

    def balance(self, buckets, start, end, now=None):
        """CO₂-Bilanz des Netzbezugs: Σ Bezug je Viertelstunde × gemessene Intensität."""
        country = self.country()
        if not country:
            return None
        now = time.time() if now is None else now
        rows = {r["start"]: r for r in self.store.rows(
            "SELECT start,g_kwh,renewable_share FROM grid_intensity WHERE country=? AND start>=? AND start<?",
            (country, int(start // 900) * 900, end))}
        kg = covered = uncovered = share_weight = share_kwh = 0.0
        for bucket in buckets:
            kwh = bucket["import_kwh"] or 0
            row = rows.get(bucket["ts"])
            if row and row["g_kwh"] is not None:
                kg += kwh * row["g_kwh"] / 1000
                covered += kwh
            else:
                uncovered += kwh
            if row and row["renewable_share"] is not None:
                share_weight += kwh * min(100, row["renewable_share"])
                share_kwh += kwh
        # Zuletzt veröffentlichter Wert (meist einige Stunden alt), nicht älter als zwei Tage.
        current = self.store.rows(
            "SELECT start,g_kwh,renewable_share FROM grid_intensity WHERE country=? AND start<=? AND start>? AND g_kwh IS NOT NULL ORDER BY start DESC LIMIT 1",
            (country, now, now - 2 * 86400))
        status = self.status()
        return {"country": country, "kg": kg if covered else None, "covered_kwh": covered, "uncovered_kwh": uncovered,
                "g_kwh": kg * 1000 / covered if covered else None,
                "renewable_share": share_weight / share_kwh if share_kwh else None,
                "current": current[0] if current else None, "source": SOURCE, "demo": self.demo,
                "fetched_at": status.get("fetched_at"), "error": status.get("error", ""), "deprecated": status.get("deprecated", False)}

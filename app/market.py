"""Optionaler, manueller Abruf öffentlicher DE-Börsenpreise; keine Vertragspreise."""
import asyncio
from datetime import timedelta
import json
import math
import time

import httpx

from .analytics import local_day, midnight


def parse_market(payload):
    try:
        data = payload["data"]
        if not isinstance(data, list) or not 1 <= len(data) <= 300:
            raise ValueError()
        result = []
        for row in data:
            start = row["start_timestamp"] / 1000
            end = row["end_timestamp"] / 1000
            price = float(row["marketprice"])
            if str(row["unit"]).lower() != "eur/mwh" or not all(math.isfinite(v) for v in (start,end,price)):
                raise ValueError()
            if start % 900 or end % 900 or not 900 <= end-start <= 3600 or not -10000 <= price <= 10000:
                raise ValueError()
            result.append({"start":int(start),"end":int(end),"eur_mwh":price,"ct_kwh":price/10})
        result.sort(key=lambda row:row["start"])
        if any(a["end"] > b["start"] for a,b in zip(result,result[1:])):
            raise ValueError()
        return result
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError("Börsenpreisquelle liefert kein gültiges, eindeutiges EUR/MWh-Format.") from None


HISTORY_DAYS = 62
HISTORY_INTERVAL = 600


class Market:
    def __init__(self, store, demo=False, transport=None):
        self.store, self.demo, self.transport = store, demo, transport
        self.lock = asyncio.Lock()

    def cached(self):
        return self.store.state("market_cache", {"rows":[],"fetched_at":None,"source":"aWATTar DE","kind":"spot_net","error":""})

    def client(self):
        return httpx.AsyncClient(timeout=10, trust_env=False, follow_redirects=False, transport=self.transport)

    async def fetch(self, client, start, end):
        async with client.stream("GET","https://api.awattar.de/v1/marketdata",params={"start":int(start*1000),"end":int(end*1000)}) as response:
            if response.status_code != 200:
                raise ValueError(f"Börsenpreise momentan nicht verfügbar (HTTP {response.status_code}).")
            body=bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body)>150000:
                    raise ValueError("Antwort der Preisquelle ist zu groß.")
        rows=parse_market(json.loads(body))
        return [row for row in rows if start<=row["start"]<end and row["end"]<=end]

    def keep(self, rows):
        # Börsenpreise als Historie für die Tarifsimulation aufbewahren.
        with self.store.transaction():
            self.store.conn.executemany("INSERT OR REPLACE INTO spot_prices VALUES(?,?,?)",
                                        [(row["start"], row["end"], row["eur_mwh"]) for row in rows])

    def history_status(self):
        row = self.store.rows("SELECT COUNT(*) AS count,MIN(start) AS start,MAX(end) AS end FROM spot_prices")[0]
        return dict(row, max_days=HISTORY_DAYS)

    async def refresh(self):
        if self.demo:
            raise ValueError("Der externe Preisabruf ist im Demo-Modus ausgeschaltet.")
        if self.lock.locked():
            raise ValueError("Ein Preisabruf läuft bereits.")
        now = time.time()
        cached = self.cached()
        if cached["fetched_at"] and now-cached["fetched_at"] < 3600 and not cached.get("error"):
            return dict(cached, from_cache=True)
        if now-self.store.state("market_last_attempt", 0) < 900:
            raise ValueError("Bitte 15 Minuten zwischen fehlgeschlagenen Preisabrufen warten.")
        async with self.lock:
            self.store.set_state("market_last_attempt", now)
            today = local_day(now,"Europe/Berlin")
            start,end = midnight(today,"Europe/Berlin"),midnight(today+timedelta(days=2),"Europe/Berlin")
            try:
                async with asyncio.timeout(15), self.client() as client:
                    rows = await self.fetch(client, start, end)
                if not rows:
                    raise ValueError("Für heute/morgen liegen noch keine Preise vor.")
                saved={"rows":rows,"fetched_at":now,"source":"aWATTar DE","kind":"spot_net","error":""}
                self.store.set_state("market_cache",saved)
                self.keep(rows)
                return dict(saved,from_cache=False)
            except (ValueError, httpx.HTTPError, OSError, asyncio.TimeoutError) as exc:
                message=str(exc) if isinstance(exc,ValueError) else "Preisquelle nicht erreichbar. Später erneut versuchen."
                self.store.set_state("market_cache",dict(cached,error=message))
                raise ValueError(message) from None

    async def history(self, start, end):
        """Vergangene Börsenpreise für einen Zeitraum nachladen; nur auf ausdrücklichen Wunsch."""
        if self.demo:
            raise ValueError("Der externe Preisabruf ist im Demo-Modus ausgeschaltet.")
        now = time.time()
        end = min(end, now)
        if end - start > HISTORY_DAYS * 86400 + 7200:
            raise ValueError(f"Höchstens {HISTORY_DAYS} Tage je Abruf nachladen.")
        if end <= start:
            raise ValueError("Zeitraum muss in der Vergangenheit liegen.")
        if self.lock.locked():
            raise ValueError("Ein Preisabruf läuft bereits.")
        if now - self.store.state("market_history_attempt", 0) < HISTORY_INTERVAL:
            raise ValueError("Bitte 10 Minuten zwischen Nachladevorgängen warten.")
        async with self.lock:
            self.store.set_state("market_history_attempt", now)
            # Schonend für die öffentliche Quelle: Abschnitte à drei Tage, nacheinander.
            count, cursor = 0, int(start // 3600) * 3600
            try:
                async with asyncio.timeout(120), self.client() as client:
                    while cursor < end:
                        chunk_end = min(cursor + 3 * 86400, int(end))
                        try:
                            rows = await self.fetch(client, cursor, chunk_end)
                        except ValueError:
                            rows = []
                        if rows:
                            self.keep(rows)
                            count += len(rows)
                        cursor = chunk_end
            except (httpx.HTTPError, OSError, asyncio.TimeoutError):
                raise ValueError(f"Preisquelle nicht erreichbar; {count} Intervalle gespeichert.") from None
            return dict(self.history_status(), added=count)

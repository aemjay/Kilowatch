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


class Market:
    def __init__(self, store, demo=False):
        self.store, self.demo = store, demo
        self.lock = asyncio.Lock()

    def cached(self):
        return self.store.state("market_cache", {"rows":[],"fetched_at":None,"source":"aWATTar DE","kind":"spot_net","error":""})

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
                async with asyncio.timeout(15), httpx.AsyncClient(timeout=10,trust_env=False,follow_redirects=False) as client:
                    async with client.stream("GET","https://api.awattar.de/v1/marketdata",params={"start":int(start*1000),"end":int(end*1000)}) as response:
                        if response.status_code != 200:
                            raise ValueError(f"Börsenpreise momentan nicht verfügbar (HTTP {response.status_code}).")
                        body=bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body)>150000:
                                raise ValueError("Antwort der Preisquelle ist zu groß.")
                        rows=parse_market(json.loads(body))
                        rows=[row for row in rows if start<=row["start"]<end and row["end"]<=end]
                        if not rows:
                            raise ValueError("Für heute/morgen liegen noch keine Preise vor.")
                saved={"rows":rows,"fetched_at":now,"source":"aWATTar DE","kind":"spot_net","error":""}
                self.store.set_state("market_cache",saved)
                return dict(saved,from_cache=False)
            except (ValueError, httpx.HTTPError, OSError, asyncio.TimeoutError) as exc:
                message=str(exc) if isinstance(exc,ValueError) else "Preisquelle nicht erreichbar. Später erneut versuchen."
                self.store.set_state("market_cache",dict(cached,error=message))
                raise ValueError(message) from None

"""Automatische Preisquelle für dynamische Tarife: Tibber-API oder Börsenpreis + Aufschlag.

Die Preise landen in derselben Tabelle wie der CSV-Import und werden nur für Tarife mit der
Preisart „dynamisch“ verwendet. Ohne gewählte Quelle findet kein Abruf statt.
- Tibber: Gesamtpreis je Viertelstunde des eigenen Vertrags (persönlicher API-Token).
- Börse: Day-Ahead-Preis der Gebotszone von Energy-Charts (Fraunhofer ISE, Daten der
  Bundesnetzagentur | SMARD.de, CC BY 4.0) plus eigener Aufschlag und Mehrwertsteuer.
Gesendet werden nur Zeitraum bzw. die Tibber-Abfrage, keine Messwerte.
"""
import asyncio
from datetime import datetime
import json
import math
import time

import httpx

from . import __version__
from .i18n import UserError, _

SOURCES = ("", "tibber", "spot")
# Gebotszonen mit Preisen in Euro (Energy-Charts liefert immer EUR/MWh).
ZONES = ("DE-LU", "AT", "NL", "BE", "FR")
TIBBER_API = "https://api.tibber.com/v1-beta/gql"
SPOT_API = "https://api.energy-charts.info/price"
SPOT_SOURCE = "Energy-Charts.info (Fraunhofer ISE), Bundesnetzagentur | SMARD.de, CC BY 4.0"
REFRESH_INTERVAL = 3600
BACKFILL_DAYS = 31
MAX_BODY = 2_000_000
DEFAULT_CONFIG = {"source": "", "zone": "DE-LU", "markup_ct": 0.0, "vat_percent": 0.0, "tibber_home": ""}

TIBBER_PRICES = """{ viewer { homes { id appNickname currentSubscription { status
  priceInfo(resolution: QUARTER_HOURLY) { today { total startsAt currency } tomorrow { total startsAt currency } } } } } }"""
TIBBER_RANGE = """query($before: String) { viewer { homes { id currentSubscription {
  priceInfoRange(resolution: QUARTER_HOURLY, last: 672, before: $before) {
    pageInfo { startCursor hasPreviousPage } nodes { total startsAt currency } } } } } }"""


def intervals(points):
    """[(start, wert)] -> [(start, end, wert)]; Ende = nächster Beginn, letzter Abschnitt wie der vorige."""
    points = sorted(points)
    if any(b[0] <= a[0] for a, b in zip(points, points[1:])):
        raise ValueError()
    result = []
    for index, (start, value) in enumerate(points):
        if index + 1 < len(points):
            end = points[index + 1][0]
        else:
            end = start + (start - points[index - 1][0] if index else 900)
        if start % 900 or not 900 <= end - start <= 3600:
            raise ValueError()
        result.append((start, end, value))
    return result


def parse_tibber_prices(nodes, currency):
    """Tibber-Preisknoten -> [(start, end, Preis je kWh)]; Währung muss zur Einstellung passen."""
    try:
        points = []
        for node in nodes:
            if node["currency"] != currency:
                raise UserError("Tibber liefert Preise in {found}, eingestellt ist {expected}. Währung in den Einstellungen anpassen.",
                                found=str(node["currency"])[:3], expected=currency)
            total = float(node["total"])
            if not math.isfinite(total) or not -5 <= total <= 20:
                raise ValueError()
            points.append((int(datetime.fromisoformat(node["startsAt"]).timestamp()), total))
        return intervals(points)
    except UserError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError("Tibber liefert kein gültiges Preisformat.") from None


def parse_spot(payload, markup_ct, vat_percent):
    """Energy-Charts-Preise (EUR/MWh) -> [(start, end, Bruttopreis je kWh)]."""
    try:
        if payload.get("unit") != "EUR / MWh":
            raise ValueError()
        stamps, values = payload["unix_seconds"], payload["price"]
        if not isinstance(stamps, list) or not isinstance(values, list) or len(stamps) != len(values) or len(stamps) > 10000:
            raise ValueError()
        points = []
        for stamp, value in zip(stamps, values):
            if value is None:
                continue
            value = float(value)
            if not math.isfinite(value) or not -10000 <= value <= 10000:
                raise ValueError()
            points.append((int(stamp), (value / 1000 + markup_ct / 100) * (1 + vat_percent / 100)))
        return intervals(points), bool(payload.get("deprecated"))
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
        raise ValueError("Börsenpreisquelle liefert kein gültiges Format.") from None


def demo_prices(start, end):
    """Künstliche Tageskurve für den Demo-Modus (kein Abruf)."""
    result = []
    for ts in range(int(start // 900) * 900, int(end), 900):
        phase = math.sin((ts % 86400) / 86400 * 2 * math.pi - math.pi / 2)
        result.append((ts, ts + 900, round(0.30 + 0.08 * phase, 4)))
    return result


class PriceFeed:
    def __init__(self, store, vault, demo=False, transport=None):
        self.store, self.vault, self.demo, self.transport = store, vault, demo, transport
        self.wakeup = asyncio.Event()
        self.lock = asyncio.Lock()

    def config(self):
        return dict(DEFAULT_CONFIG, **self.store.state("price_feed", {}))

    def status(self):
        return self.store.state("price_feed_status", {"fetched_at": None, "error": "", "homes": [], "latest_end": None})

    def client(self):
        return httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False, transport=self.transport)

    async def request(self, client, method, url, **kwargs):
        async with client.stream(method, url, **kwargs) as response:
            if response.status_code in (401, 403):
                raise ValueError("Tibber lehnt den API-Token ab. Token prüfen.")
            if response.status_code != 200:
                raise UserError("Preisquelle momentan nicht erreichbar (HTTP {status}).", status=response.status_code)
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_BODY:
                    raise ValueError("Antwort der Preisquelle ist zu groß.")
        return json.loads(body)

    async def tibber(self, client, query, variables=None):
        token = self.vault.get("tibber_token")
        if not token:
            raise ValueError("Tibber-API-Token fehlt.")
        payload = await self.request(client, "POST", TIBBER_API, json={"query": query, "variables": variables or {}},
                                     headers={"Authorization": "Bearer " + token, "User-Agent": f"Kilowatch/{__version__}"})
        if payload.get("errors"):
            raise ValueError("Tibber lehnt die Abfrage ab. Token und Vertrag prüfen.")
        try:
            return payload["data"]["viewer"]["homes"]
        except (KeyError, TypeError):
            raise ValueError("Tibber liefert kein gültiges Preisformat.") from None

    @staticmethod
    def pick_home(homes, wanted):
        active = [h for h in homes if h.get("currentSubscription")]
        if wanted:
            home = next((h for h in homes if h.get("id") == wanted), None)
            if not home:
                raise ValueError("Das gewählte Tibber-Zuhause gibt es in diesem Konto nicht.")
            return home
        if len(active) == 1:
            return active[0]
        if not active:
            raise ValueError("Kein Tibber-Zuhause mit aktivem Stromvertrag gefunden.")
        raise ValueError("Mehrere Tibber-Zuhause gefunden. Bitte eines auswählen.")

    async def fetch_tibber(self, client, config, currency, now):
        homes = await self.tibber(client, TIBBER_PRICES)
        # Nur Kennung und selbst vergebener Name, keine Adresse.
        listing = [{"id": str(h.get("id", ""))[:80], "name": str(h.get("appNickname") or "")[:80]} for h in homes]
        self.store.set_state("price_feed_status", dict(self.status(), homes=listing))
        home = self.pick_home(homes, config["tibber_home"])
        info = home["currentSubscription"].get("priceInfo") or {}
        prices = parse_tibber_prices((info.get("today") or []) + (info.get("tomorrow") or []), currency)
        latest = self.latest()
        if latest is None or latest < now - 86400:
            # Erster Abruf oder längere Pause: rückwärts in Seiten zu sieben Tagen nachladen.
            before, oldest = None, None
            while True:
                pages = await self.tibber(client, TIBBER_RANGE, {"before": before})
                page = next((h for h in pages if h.get("id") == home["id"]), None)
                connection = ((page or {}).get("currentSubscription") or {}).get("priceInfoRange") or {}
                chunk = parse_tibber_prices(connection.get("nodes") or [], currency)
                prices = chunk + prices
                oldest = chunk[0][0] if chunk else None
                info = connection.get("pageInfo") or {}
                if not chunk or not info.get("hasPreviousPage") or oldest <= now - BACKFILL_DAYS * 86400 or (latest and oldest <= latest):
                    break
                before = info.get("startCursor")
                if not before:
                    break
        # Aufschlag brutto je kWh für Bestandteile, die nicht im Tibber-Preis stecken (z. B. Netzentgelt in Norwegen).
        extra = config["markup_ct"] / 100
        return [(start, end, value + extra) for start, end, value in prices], False

    async def fetch_spot(self, client, config, currency, now):
        if currency != "EUR":
            raise ValueError("Börsenpreis + Aufschlag gibt es nur für Gebotszonen in Euro. Für andere Währungen Tibber oder CSV verwenden.")
        latest = self.latest()
        start = max(now - BACKFILL_DAYS * 86400, (latest or 0) - 86400)
        payload = await self.request(client, "GET", SPOT_API, params={"bzn": config["zone"], "start": int(start), "end": int(now + 2 * 86400)})
        return parse_spot(payload, config["markup_ct"], config["vat_percent"])

    def latest(self):
        return self.store.state("price_feed_latest", None)

    def save(self, prices):
        with self.store.transaction():
            # Vorhandene Preise im abgedeckten Zeitraum ersetzen (auch andere Rasterweiten).
            for start, end, value in prices:
                self.store.conn.execute("DELETE FROM prices WHERE start<? AND end>?", (end, start))
                self.store.conn.execute("INSERT INTO prices VALUES(?,?,?)", (start, end, value))
        if prices:
            self.store.set_state("price_feed_latest", max(self.latest() or 0, prices[-1][0]))

    async def refresh(self, now=None):
        config = self.config()
        if not config["source"]:
            return
        now = time.time() if now is None else now
        currency = self.store.settings().get("currency") or "EUR"
        async with self.lock:
            try:
                if self.demo:
                    prices, deprecated = demo_prices(now - 2 * 86400, now + 86400), False
                else:
                    async with self.client() as client:
                        fetch = self.fetch_tibber if config["source"] == "tibber" else self.fetch_spot
                        prices, deprecated = await fetch(client, config, currency, now)
                await asyncio.to_thread(self.save, prices)
                self.store.set_state("price_feed_status", dict(self.status(), fetched_at=now, error="", error_params={}, source=config["source"],
                                                               deprecated=deprecated, count=len(prices),
                                                               latest_end=prices[-1][1] if prices else self.status().get("latest_end")))
            except (ValueError, httpx.HTTPError, OSError, asyncio.TimeoutError) as exc:
                if isinstance(exc, UserError):
                    # Vorlage und Werte getrennt speichern, damit die Oberfläche sie übersetzen kann.
                    message, params = exc.template, {k: str(v) for k, v in exc.params.items()}
                else:
                    message, params = (str(exc) if isinstance(exc, ValueError) else _("Preisquelle nicht erreichbar. Später erneut versuchen.")), {}
                self.store.set_state("price_feed_status", dict(self.status(), fetched_at=now, error=message, error_params=params,
                                                               source=config["source"]))

    def reset(self):
        """Nach einem Quellenwechsel neu nachladen."""
        self.store.set_state("price_feed_latest", None)
        self.store.set_state("price_feed_status", {"fetched_at": None, "error": "", "homes": [], "latest_end": None})

    async def run(self):
        while True:
            try:
                await self.refresh()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass  # Fehler stehen im gespeicherten Status; der nächste Versuch folgt planmäßig.
            try:
                await asyncio.wait_for(self.wakeup.wait(), timeout=REFRESH_INTERVAL)
                self.wakeup.clear()
            except asyncio.TimeoutError:
                pass

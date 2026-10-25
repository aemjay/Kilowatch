import asyncio
from datetime import datetime, timedelta, timezone
import json

import httpx
import pytest

from app.analytics import Analytics, midnight
from app.decoder import Reading
from app.prices import PriceFeed, intervals, parse_spot, parse_tibber_prices
from app.security import Vault

BERLIN = timezone(timedelta(hours=2))


def nodes(start, count, step=900, total=0.30, currency="EUR", offset=BERLIN):
    return [{"total": total + i / 1000, "startsAt": datetime.fromtimestamp(start + i * step, offset).isoformat(), "currency": currency}
            for i in range(count)]


def test_intervals_follow_the_next_start_for_quarter_and_hourly_values():
    assert intervals([(0, 1), (900, 2), (1800, 3)]) == [(0, 900, 1), (900, 1800, 2), (1800, 2700, 3)]
    assert intervals([(3600, 1), (7200, 2)]) == [(3600, 7200, 1), (7200, 10800, 2)]
    for bad in ([(0, 1), (0, 2)], [(10, 1)], [(0, 1), (7200, 2)]):
        with pytest.raises(ValueError):
            intervals(bad)


def test_tibber_prices_across_the_autumn_clock_change():
    # 26.10.2025 in Berlin: 25 Stunden = 100 Viertelstunden; Offset wechselt von +02:00 auf +01:00.
    day = midnight("2025-10-26", "Europe/Berlin")
    from zoneinfo import ZoneInfo
    data = [{"total": 0.3, "currency": "EUR", "startsAt": datetime.fromtimestamp(day + i * 900, ZoneInfo("Europe/Berlin")).isoformat()}
            for i in range(100)]
    prices = parse_tibber_prices(data, "EUR")
    assert len(prices) == 100 and prices[-1][1] == midnight("2025-10-27", "Europe/Berlin")
    assert all(end - start == 900 for start, end, _ in prices)


def test_tibber_currency_must_match_the_setting():
    with pytest.raises(ValueError, match="NOK"):
        parse_tibber_prices(nodes(1_800_000_000, 2, currency="NOK"), "EUR")
    with pytest.raises(ValueError):
        parse_tibber_prices([{"total": "x", "startsAt": "2026-01-01T00:00:00+01:00", "currency": "EUR"}], "EUR")


def test_spot_price_formula_with_markup_and_vat():
    payload = {"unix_seconds": [1_800_000_000, 1_800_000_900], "price": [100.0, None], "unit": "EUR / MWh", "deprecated": False}
    prices, deprecated = parse_spot(payload, markup_ct=15, vat_percent=19)
    # (10 ct Börse + 15 ct Aufschlag) × 1,19 = 29,75 ct
    assert prices == [(1_800_000_000, 1_800_000_900, pytest.approx(0.2975))] and not deprecated
    with pytest.raises(ValueError):
        parse_spot(dict(payload, unit="NOK / MWh"), 0, 0)


@pytest.fixture
def feed(store, tmp_path):
    vault = Vault(tmp_path / "secrets")

    def make(handler, **config):
        store.set_state("price_feed", dict({"source": "tibber"}, **config))
        return PriceFeed(store, vault, transport=httpx.MockTransport(handler))
    make.vault = vault
    return make


def tibber_handler(calls, today, ranges, homes=None):
    def handle(request):
        calls.append(request)
        assert request.url == "https://api.tibber.com/v1-beta/gql" and request.method == "POST"
        assert request.headers["authorization"] == "Bearer synthetic-token"
        body = json.loads(request.content)
        if "priceInfoRange" in body["query"]:
            page = ranges.pop(0)
            sub = {"priceInfoRange": {"pageInfo": {"startCursor": "c", "hasPreviousPage": bool(ranges)}, "nodes": page}}
            return httpx.Response(200, json={"data": {"viewer": {"homes": [{"id": "home-1", "currentSubscription": sub}]}}})
        assert "QUARTER_HOURLY" in body["query"]
        listed = homes or [{"id": "home-1", "appNickname": "Zuhause", "currentSubscription": {"status": "running", "priceInfo": {"today": today, "tomorrow": []}}}]
        return httpx.Response(200, json={"data": {"viewer": {"homes": listed}}})
    return handle


def test_tibber_refresh_backfills_once_and_stores_total_prices(store, feed):
    now = 1_800_000_000
    calls = []
    today = nodes(now - 3600, 8)
    week = nodes(now - 3 * 86400, 4, total=0.25)
    feed.vault.update({"tibber_token": "synthetic-token"})
    source = feed(tibber_handler(calls, today, [week]), markup_ct=2)
    asyncio.run(source.refresh(now))
    assert source.status()["error"] == ""
    rows = store.rows("SELECT * FROM prices ORDER BY start")
    # Tibber-Gesamtpreis plus eigener Zuschlag von 2 ct.
    assert len(rows) == 12 and rows[0]["eur_kwh"] == pytest.approx(0.27) and rows[-1]["eur_kwh"] == pytest.approx(0.327)
    assert source.status()["homes"] == [{"id": "home-1", "name": "Zuhause"}]
    # Danach nur noch heute/morgen.
    calls.clear()
    asyncio.run(source.refresh(now + 900))
    assert len(calls) == 1


def test_tibber_currency_mismatch_writes_nothing(store, feed):
    feed.vault.update({"tibber_token": "synthetic-token"})
    store.update_settings({"currency": "SEK"})
    source = feed(tibber_handler([], nodes(1_800_000_000, 4), [nodes(1_799_000_000, 4)]))
    asyncio.run(source.refresh(1_800_000_000))
    assert source.status()["error_params"] == {"found": "EUR", "expected": "SEK"} and store.rows("SELECT COUNT(*) AS n FROM prices")[0]["n"] == 0


def test_several_tibber_homes_need_a_choice(store, feed):
    feed.vault.update({"tibber_token": "synthetic-token"})
    homes = [{"id": f"home-{i}", "appNickname": f"H{i}", "currentSubscription": {"priceInfo": {"today": nodes(1_800_000_000, 2), "tomorrow": []}}} for i in (1, 2)]
    source = feed(tibber_handler([], [], [], homes=homes))
    asyncio.run(source.refresh(1_800_000_000))
    assert "auswählen" in source.status()["error"] and len(source.status()["homes"]) == 2


def test_rejected_token_is_reported(store, feed):
    feed.vault.update({"tibber_token": "synthetic-token"})
    source = feed(lambda request: httpx.Response(401))
    asyncio.run(source.refresh(1_800_000_000))
    assert "Token" in source.status()["error"]


def test_spot_refresh_requests_only_zone_and_range(store, feed):
    now = 1_800_000_000

    def handle(request):
        assert request.url.host == "api.energy-charts.info" and set(request.url.params) == {"bzn", "start", "end"}
        assert request.url.params["bzn"] == "AT" and "authorization" not in request.headers
        return httpx.Response(200, json={"unix_seconds": [now, now + 900], "price": [80, 90], "unit": "EUR / MWh"})

    source = feed(handle, source="spot", zone="AT", markup_ct=10, vat_percent=20)
    asyncio.run(source.refresh(now))
    assert [round(r["eur_kwh"], 4) for r in store.rows("SELECT eur_kwh FROM prices ORDER BY start")] == [0.216, 0.228]


def test_feed_prices_complete_the_cost_of_a_dynamic_tariff(store, feed):
    start = midnight("2026-10-01", "Europe/Berlin")
    store.ingest(Reading(3600, 100, 0, "A"), start)
    store.ingest(Reading(3600, 100.01, 0, "A"), start + 10)
    with store.transaction():
        store.conn.execute("INSERT INTO tariffs VALUES(?,?,?,?,?,?)", ("2026-10-01", "Tibber", "dynamic", 0, 0, 0))
    feed.vault.update({"tibber_token": "synthetic-token"})
    source = feed(tibber_handler([], nodes(start, 4, total=0.40), [[]]))
    asyncio.run(source.refresh(start + 3600))
    result = Analytics(store).summary(start, start + 10)
    assert result["cost_complete"] and result["unpriced_kwh"] == 0 and result["energy_cost_eur"] == pytest.approx(0.004)


def test_price_source_api_keeps_the_token_secret(authenticated):
    response = authenticated.put("/api/prices/source", json={"source": "tibber", "tibber_token": "synthetic-token"})
    assert response.status_code == 200 and response.json()["tibber_token_configured"]
    for path in ("/api/tariffs", "/api/settings", "/api/prices/source"):
        if path != "/api/prices/source":
            assert "synthetic-token" not in authenticated.get(path).text
    assert authenticated.app.state.vault.get("tibber_token") == "synthetic-token"
    for bad in ({"source": "octopus"}, {"source": "spot", "zone": "NO2"}, {"source": "tibber", "tibber_token": "a b"}):
        assert authenticated.put("/api/prices/source", json=bad).status_code == 422
    assert authenticated.put("/api/prices/source", json={"source": "", "clear_tibber_token": True}).json()["tibber_token_configured"] is False
    assert authenticated.post("/api/prices/refresh").status_code == 400

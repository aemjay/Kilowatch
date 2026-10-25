import asyncio
import httpx
import pytest

from app.market import Market, parse_market
from app.analytics import midnight


def response(start,price=100):
    return {"data":[{"start_timestamp":start*1000,"end_timestamp":(start+3600)*1000,"marketprice":price,"unit":"Eur/MWh"}]}


def test_market_units_negative_values_and_no_retail_assumption():
    assert parse_market(response(1800,-50))[0]["ct_kwh"]==-5


@pytest.mark.parametrize("payload",[{"data":[]},{"data":[{}]},response(1801),response(1800,float("nan")),{"data":[{"start_timestamp":1800000,"end_timestamp":5400000,"marketprice":10,"unit":"ct/kWh"}]}])
def test_malformed_market_data_rejected(payload):
    with pytest.raises(ValueError):
        parse_market(payload)


def test_price_fetch_is_explicit_cached_and_never_overwrites_contract_prices(store,monkeypatch):
    now=midnight("2026-10-25","Europe/Berlin")+3600
    monkeypatch.setattr("app.market.time.time",lambda:now)
    actual_client=httpx.AsyncClient
    calls=[]
    def handle(request):
        calls.append(request)
        assert request.url.host=="api.awattar.de"
        assert "authorization" not in request.headers and "cookie" not in request.headers
        assert "start" in request.url.params and "end" in request.url.params
        return httpx.Response(200,json=response(midnight("2026-10-25","Europe/Berlin")))
    monkeypatch.setattr("app.market.httpx.AsyncClient",lambda **kw:actual_client(transport=httpx.MockTransport(handle),**kw))
    with store.transaction():
        store.conn.execute("INSERT INTO prices VALUES(?,?,?)",(1800,2700,.35))
    market=Market(store)
    assert not calls
    first=asyncio.run(market.refresh())
    second=asyncio.run(market.refresh())
    assert len(calls)==1 and second["from_cache"]
    assert first["kind"]=="spot_net"
    assert store.rows("SELECT eur_kwh FROM prices")[0]["eur_kwh"]==.35


def test_market_failure_keeps_old_cache_and_limits_retries(store,monkeypatch):
    now=2000000000
    monkeypatch.setattr("app.market.time.time",lambda:now)
    old={"rows":[{"start":1800,"end":5400,"ct_kwh":10}],"fetched_at":now-7200,"error":"","kind":"spot_net"}
    store.set_state("market_cache",old)
    actual_client=httpx.AsyncClient
    monkeypatch.setattr("app.market.httpx.AsyncClient",lambda **kw:actual_client(transport=httpx.MockTransport(lambda _:httpx.Response(503)),**kw))
    market=Market(store)
    with pytest.raises(ValueError,match="503"):
        asyncio.run(market.refresh())
    assert market.cached()["rows"]==old["rows"]
    with pytest.raises(ValueError,match="15 Minuten"):
        asyncio.run(market.refresh())


def test_market_has_no_demo_network_requests(store):
    with pytest.raises(ValueError,match="Demo"):
        asyncio.run(Market(store,True).refresh())

import asyncio
import httpx
import pytest

from app.discovery import Discovery, probe, search_network, suggestions


@pytest.mark.parametrize("network",["8.8.8.0/24","192.168.0.0/16","127.0.0.0/24","169.254.1.0/24","0.0.0.0/24","224.0.0.0/24","not-a-network","::1/128"])
def test_search_rejects_public_or_excessive_network_before_requests(network):
    with pytest.raises(ValueError):
        search_network(network)


def test_private_subnet_normalized_and_host_bound():
    network=search_network("192.168.1.15/24")
    assert str(network)=="192.168.1.0/24"
    assert len(list(network.hosts()))==254


def test_scan_uses_no_credentials_and_detects_auth_realm(monkeypatch):
    requests=[]
    def handle(request):
        requests.append(request)
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        return httpx.Response(401,headers={"WWW-Authenticate":'Basic realm="Tibber Bridge"'})
    async def name(address):
        return "bridge.fritz.box"
    monkeypatch.setattr("app.discovery.device_name",name)
    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle),follow_redirects=False) as client:
            result=await probe(client,"192.168.1.10")
        assert result["fqdn"]=="bridge.fritz.box"
        assert result["host"]=="bridge.fritz.box"
    asyncio.run(check())
    assert len(requests)==1


def test_unrelated_webserver_not_a_bridge():
    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:httpx.Response(200,text="printer"))) as client:
            assert await probe(client,"192.168.1.10") is None
    asyncio.run(check())


def test_scan_is_bounded_rate_limited_and_demo_blocked(monkeypatch):
    calls=[]
    async def fake_probe(client,address):
        calls.append(address)
        return {"ip":address,"host":address}
    monkeypatch.setattr("app.discovery.probe",fake_probe)
    async def check():
        engine=Discovery()
        result=await engine.scan("192.168.1.0/30")
        assert result["checked"]==2 and len(result["devices"])==2
        with pytest.raises(ValueError,match="30 Sekunden"):
            await engine.scan("192.168.1.0/30")
        with pytest.raises(ValueError,match="Demo"):
            await Discovery().scan("192.168.1.0/30",demo=True)
    asyncio.run(check())
    assert calls==["192.168.1.1","192.168.1.2"]


def test_network_suggestion_uses_client_without_fixed_ip(monkeypatch):
    async def resolve(host):
        return ["192.168.1.123"]
    monkeypatch.setattr("app.discovery.resolve_local",resolve)
    result=asyncio.run(suggestions("192.168.1.50","bridge.fritz.box","nas.fritz.box"))
    assert len(result)==1 and result[0]["network"]=="192.168.1.0/24"


def test_discovery_api_requires_login_and_validates_before_scan(client,authenticated):
    authenticated.post("/api/logout")
    assert client.post("/api/discovery/scan",json={"network":"192.168.1.0/24"}).status_code==401
    client.post("/api/login",json={"password":"test-password-long-enough"})
    assert client.post("/api/discovery/scan",json={"network":"8.8.8.0/24"}).status_code==400

import asyncio
import socket

import httpx
import pytest

from app.bridge import Bridge
from app.network import local_request, resolve_local, validate_host


@pytest.mark.parametrize("host,result",[("bridge.fritz.box","bridge.fritz.box"),("BRIDGE.FRITZ.BOX.","bridge.fritz.box"),("192.168.1.10","192.168.1.10"),("meter.home.arpa","meter.home.arpa")])
def test_ip_and_fqdn_validation(host,result):
    assert validate_host(host)==result


@pytest.mark.parametrize("host",["","bridge","invalid_name.fritz.box","http://bridge.fritz.box","a@bridge.fritz.box","bridge.fritz.box:80","8.8.8.8","0.0.0.0","255.255.255.255","999.888.1.1","127.0.0.1","127.1.2.3"])
def test_ambiguous_or_nonlocal_addresses_rejected(host):
    with pytest.raises(ValueError):
        validate_host(host)


def dns_record(address):
    return (socket.AF_INET,socket.SOCK_STREAM,6,"",(address,0))


def test_dhcp_address_change_is_resolved_for_next_request(monkeypatch):
    count=[0]
    def resolver(*args):
        count[0]+=1
        return [dns_record("192.168.1.10" if count[0]==1 else "192.168.1.11")]
    monkeypatch.setattr(socket,"getaddrinfo",resolver)
    addresses=[]
    def handler(request):
        addresses.append(request.url.host)
        assert request.headers["host"]=="bridge.fritz.box"
        return httpx.Response(200,content=b"1-0:16.7.0(500*W)")
    async def run():
        bridge=Bridge({"bridge_host":"bridge.fritz.box","bridge_user":"synthetic-user","node_id":1},"synthetic-password",httpx.MockTransport(handler))
        try:
            await bridge.read()
            await bridge.read()
        finally:
            await bridge.close()
    asyncio.run(run())
    assert addresses==["192.168.1.10","192.168.1.11"]


def test_public_dns_answer_does_not_receive_credentials(monkeypatch):
    monkeypatch.setattr(socket,"getaddrinfo",lambda *args:[dns_record("8.8.8.8")])
    with pytest.raises(ValueError,match="lokale"):
        asyncio.run(resolve_local("bridge.example.org"))


def test_mixed_private_public_dns_is_rejected(monkeypatch):
    monkeypatch.setattr(socket,"getaddrinfo",lambda *args:[dns_record("192.168.1.10"),dns_record("8.8.8.8")])
    with pytest.raises(ValueError):
        asyncio.run(resolve_local("bridge.example.org"))


def test_dns_failure_is_actionable(monkeypatch):
    def fail(*args):
        raise socket.gaierror()
    monkeypatch.setattr(socket,"getaddrinfo",fail)
    with pytest.raises(ValueError,match="DNS"):
        asyncio.run(resolve_local("bridge.fritz.box"))


def test_signal_https_pins_ip_and_preserves_sni(monkeypatch):
    monkeypatch.setattr(socket,"getaddrinfo",lambda *args:[dns_record("192.168.1.20")])
    def handler(request):
        assert request.url.host=="192.168.1.20"
        assert request.extensions["sni_hostname"]=="signal.home.arpa"
        assert request.headers["host"]=="signal.home.arpa"
        assert request.headers["authorization"]=="Bearer synthetic-token"
        return httpx.Response(200,json={"timestamp":1})
    status,_,_=asyncio.run(local_request("https://signal.home.arpa","/v2/send","POST",{},"synthetic-token",transport=httpx.MockTransport(handler)))
    assert status==200


def test_loopback_gateway_url_is_rejected():
    from app.network import local_url
    with pytest.raises(ValueError):
        local_url("http://127.0.0.1:8080")

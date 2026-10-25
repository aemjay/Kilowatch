import httpx
import pytest
import asyncio

from app.bridge import Bridge, BridgeError


def test_modern_to_legacy_fallback():
    calls=[]
    def handler(request):
        calls.append(request.url.path)
        assert request.headers["authorization"].startswith("Basic ")
        if request.url.path=="/node_data.json":
            return httpx.Response(404)
        return httpx.Response(200,content=b"1-0:1.8.0(100.0*kWh)\n1-0:16.7.0(500*W)")
    async def run():
        bridge=Bridge({"bridge_host":"192.168.1.10","bridge_user":"admin","node_id":1},"FAKE",httpx.MockTransport(handler))
        try:
            reading,_=await bridge.read()
            assert reading.power_w==500
            assert bridge.endpoint=="/data.json"
        finally:
            await bridge.close()
    asyncio.run(run())
    assert calls==["/node_data.json","/data.json"]


def test_auth_failure_does_not_try_other_passwords_or_paths():
    calls=[]
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(401)
    async def run():
        bridge=Bridge({"bridge_host":"192.168.1.10","bridge_user":"admin","node_id":1},"FAKE",httpx.MockTransport(handler))
        try:
            with pytest.raises(BridgeError,match="abgelehnt"):
                await bridge.read()
        finally:
            await bridge.close()
    asyncio.run(run())
    assert len(calls)==1

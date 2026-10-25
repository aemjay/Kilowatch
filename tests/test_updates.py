import asyncio

import httpx
import pytest

from app import __version__
from app.updates import Updates, parse_release, parse_version


def release(tag, body=""):
    return {"tag_name": tag, "html_url": f"https://github.com/example/kilowatch/releases/tag/{tag}", "body": body, "draft": False, "prerelease": False}


def bumped(major=0, minor=0, patch=0):
    a, b, c = parse_version(__version__)
    return f"v{a+major}.{b+minor}.{c+patch}"


def test_release_parsing_compares_versions_and_reads_schema_marker():
    newer = parse_release(release(bumped(patch=1), "Fixes\n<!-- schema: 7 -->"))
    assert newer["available"] and newer["schema"] == 7 and not newer["major_change"]
    assert parse_release(release(bumped(major=1)))["major_change"]
    assert not parse_release(release("v" + __version__))["available"]
    with pytest.raises(ValueError):
        parse_release({"tag_name": "nightly", "html_url": "https://github.com/x"})
    with pytest.raises(ValueError):
        parse_release(dict(release(bumped(patch=1)), html_url="https://evil.example/"))
    with pytest.raises(ValueError):
        parse_release(dict(release(bumped(patch=1)), prerelease=True))


def test_check_is_off_by_default_and_sends_no_cookies_or_data(store):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=release(bumped(minor=1), "<!-- schema: 99 -->"))
    updates = Updates(store, "example/kilowatch", transport=httpx.MockTransport(handler))
    assert updates.status()["enabled"] is False
    status = asyncio.run(updates.check(manual=True))
    assert status["available"] and status["schema_change"]
    request = seen[0]
    assert str(request.url) == "https://api.github.com/repos/example/kilowatch/releases/latest"
    assert "cookie" not in request.headers and request.content == b""
    with pytest.raises(ValueError, match="Minute"):
        asyncio.run(updates.check(manual=True))


def test_failed_check_is_reported_and_keeps_last_known_release(store):
    responses = [httpx.Response(200, json=release(bumped(patch=1))), httpx.Response(503)]
    updates = Updates(store, "example/kilowatch", transport=httpx.MockTransport(lambda request: responses.pop(0)))
    asyncio.run(updates.check())
    with pytest.raises(ValueError, match="503"):
        asyncio.run(updates.check())
    status = updates.status()
    assert status["available"] and "503" in status["error"]


def test_update_api_requires_login_and_toggles(client, authenticated):
    assert authenticated.get("/api/updates").json()["enabled"] is False
    assert authenticated.put("/api/updates", json={"enabled": True}).json()["enabled"] is True
    assert authenticated.put("/api/updates", json={"enabled": "yes", "extra": 1}).status_code == 422

import json
from pathlib import Path
import struct

from app import __version__

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def png_size(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def test_manifest_and_icons_make_the_app_installable(client):
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200 and response.headers["content-type"].startswith("application/manifest+json")
    assert response.headers["cache-control"] == "no-cache"
    manifest = response.json()
    assert manifest["display"] == "standalone" and manifest["start_url"] == "/" and manifest["scope"] == "/"
    assert manifest["name"] and manifest["short_name"] and manifest["background_color"] and manifest["theme_color"]
    sizes = {(icon["sizes"], icon["purpose"]) for icon in manifest["icons"] if icon["type"] == "image/png"}
    assert {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")} <= sizes
    for icon in manifest["icons"]:
        reply = client.get(icon["src"])
        assert reply.status_code == 200, icon["src"]
        if icon["type"] == "image/png":
            width, height = icon["sizes"].split("x")
            assert png_size(reply.content) == (int(width), int(height))
    assert png_size(client.get("/apple-touch-icon.png").content) == (180, 180)


def test_everything_needed_to_install_is_public_and_linked_from_the_page(client):
    page = client.get("/").text
    for fragment in ('rel="manifest" href="/manifest.webmanifest"', 'rel="apple-touch-icon"', 'src="/pwa.js"'):
        assert fragment in page
    # Ohne Anmeldung erreichbar, sonst kann der Browser die App nicht installieren.
    for path in ("/pwa.js", "/sw.js", "/manifest.webmanifest", "/icon-192.png"):
        assert client.get(path).status_code == 200, path


def test_service_worker_carries_the_version_and_is_never_cached(client):
    response = client.get("/sw.js")
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/javascript")
    assert response.headers["cache-control"] == "no-cache" and response.headers["service-worker-allowed"] == "/"
    assert f"const VERSION = '{__version__}'" in response.text and "__VERSION__" not in response.text


def test_service_worker_precaches_existing_files_and_skips_the_api(client):
    source = (STATIC / "sw.js").read_text()
    shell = json.loads(source.split("const SHELL = ", 1)[1].split(";\n", 1)[0].replace("'", '"'))
    for path in shell:
        assert client.get(path).status_code == 200, path
    # Messdaten und Anmeldung dürfen nie im Zwischenspeicher landen.
    assert "pathname.startsWith('/api/')" in source and "request.method !== 'GET'" in source
    page = (STATIC / "index.html").read_text()
    for script in __import__("re").findall(r'<script src="(/[^"]+)"', page):
        assert script in shell, script

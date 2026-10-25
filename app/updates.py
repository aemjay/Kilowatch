"""Optionaler Hinweis auf neue Kilowatch-Versionen; installiert nie selbst."""
import asyncio
import json
import re
import time

import httpx

from . import __version__
from .i18n import UserError

CHECK_INTERVAL = 86400
MANUAL_INTERVAL = 60
# Kennzeichnung in den Release-Notizen, wenn ein Update das Datenbankschema ändert.
SCHEMA_MARKER = re.compile(r"<!--\s*schema:\s*(\d+)\s*-->", re.IGNORECASE)


def parse_version(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(value).strip())
    if not match:
        raise ValueError("Unbekanntes Versionsformat.")
    return tuple(int(part) for part in match.groups())


def parse_release(payload, current=__version__):
    try:
        if payload.get("draft") or payload.get("prerelease"):
            raise ValueError()
        latest = parse_version(payload["tag_name"])
        url = str(payload["html_url"])
        if not url.startswith("https://github.com/"):
            raise ValueError()
        notes = str(payload.get("body") or "")
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValueError("Antwort von GitHub hat kein gültiges Release-Format.") from None
    schema = SCHEMA_MARKER.search(notes)
    return {"latest": ".".join(map(str, latest)), "url": url, "notes": notes[:4000],
            "schema": int(schema[1]) if schema else None,
            "available": latest > parse_version(current), "major_change": latest[0] > parse_version(current)[0]}


class Updates:
    def __init__(self, store, repository, demo=False, transport=None):
        self.store, self.repository, self.demo, self.transport = store, repository, demo, transport
        self.lock = asyncio.Lock()

    def settings(self):
        return self.store.state("update_check", {"enabled": False})

    def status(self):
        from .storage import SCHEMA_VERSION
        cached = self.store.state("update_status", {})
        result = {"enabled": self.settings()["enabled"], "current": __version__, "repository": self.repository,
                  "checked_at": cached.get("checked_at"), "error": cached.get("error", ""), "available": False}
        if cached.get("latest"):
            result.update({key: cached[key] for key in ("latest", "url", "notes", "schema", "major_change")})
            # Neu berechnen: nach einem Update ist der gespeicherte Stand sonst veraltet.
            result["available"] = parse_version(cached["latest"]) > parse_version(__version__)
            result["schema_change"] = bool(cached.get("schema")) and cached["schema"] > SCHEMA_VERSION
        return result

    def set_enabled(self, enabled):
        self.store.set_state("update_check", {"enabled": bool(enabled)})

    async def check(self, manual=False):
        if self.demo:
            raise ValueError("Im Demo-Modus wird nicht nach Updates gesucht.")
        if self.lock.locked():
            raise ValueError("Eine Update-Prüfung läuft bereits.")
        now = time.time()
        if manual and now - self.store.state("update_last_attempt", 0) < MANUAL_INTERVAL:
            raise ValueError("Bitte eine Minute zwischen Update-Prüfungen warten.")
        async with self.lock:
            self.store.set_state("update_last_attempt", now)
            try:
                # Nur das öffentliche Release abfragen: keine Cookies, keine Kennung, keine Messdaten.
                async with httpx.AsyncClient(timeout=10, trust_env=False, follow_redirects=False, transport=self.transport) as client:
                    async with client.stream("GET", f"https://api.github.com/repos/{self.repository}/releases/latest",
                                             headers={"Accept": "application/vnd.github+json", "User-Agent": "Kilowatch"}) as response:
                        if response.status_code == 404:
                            raise ValueError("Noch keine veröffentlichte Version gefunden.")
                        if response.status_code != 200:
                            raise UserError("Update-Prüfung momentan nicht möglich (HTTP {status}).", status=response.status_code)
                        # Größe schon während des Empfangs begrenzen.
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > 200000:
                                raise ValueError("Antwort von GitHub ist zu groß.")
                saved = dict(parse_release(json.loads(body)), checked_at=now, error="")
            except (ValueError, httpx.HTTPError) as exc:
                message = str(exc) if isinstance(exc, ValueError) else "GitHub nicht erreichbar. Später erneut versuchen."
                self.store.set_state("update_status", dict(self.store.state("update_status", {}), checked_at=now, error=message))
                raise ValueError(message) from None
            self.store.set_state("update_status", saved)
            return self.status()

    async def run(self):
        while True:
            try:
                last = self.store.state("update_status", {}).get("checked_at") or 0
                if self.settings()["enabled"] and not self.demo and time.time() - last >= CHECK_INTERVAL:
                    await self.check()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass  # Fehler stehen im gespeicherten Status; der nächste Versuch folgt planmäßig.
            await asyncio.sleep(3600)

import asyncio
import logging
import time

from .bridge import Bridge
from .i18n import UserError


log = logging.getLogger("kilowatch")


class Collector:
    def __init__(self, store, get_password, demo=False):
        self.store = store
        self.get_password = get_password
        self.demo = demo
        self.status = {"state": "starting", "message": "Erfassung startet.", "params": {}, "errors": 0}
        self.diagnostics = {}
        self.wakeup = asyncio.Event()
        self.last_maintenance = 0

    def persist(self, reading, digest, now):
        """Neues Telegramm speichern; blockierend, daher nur per Thread aufrufen."""
        changed_at = self.store.state("payload_changed_at", now)
        if digest == self.store.state("payload_hash"):
            return False, changed_at
        with self.store.transaction():
            self.store.ingest(reading, now)
            self.store.set_state("payload_hash", digest)
            self.store.set_state("payload_changed_at", now)
            self.store.set_state("last_obis", reading.obis)
        return True, now

    async def run(self):
        failures = 0
        bridge, signature = None, None
        try:
            while True:
                settings = await asyncio.to_thread(self.store.settings)
                password = self.get_password()
                current_signature = (settings["bridge_host"], settings["bridge_user"], settings["node_id"], password)
                wait = settings["poll_seconds"]
                try:
                    if self.demo:
                        from .demo import live_reading
                        await asyncio.to_thread(lambda: self.store.ingest(live_reading(self.store)))
                        self.status.update(state="demo", message="Beispieldaten · keine Verbindung zur Bridge.", params={})
                    elif not settings["enabled"]:
                        self.status.update(state="paused", message="Erfassung pausiert.", params={})
                    elif not password or not settings["bridge_host"] or not settings["bridge_user"]:
                        self.status.update(state="setup", message="Bridge-Adresse und Zugangsdaten im Einrichtungsassistenten eingeben.", params={})
                    else:
                        if signature != current_signature:
                            if bridge:
                                await bridge.close()
                            bridge = Bridge(settings, password)
                            signature = current_signature
                        reading, digest = await bridge.read()
                        now = time.time()
                        self.status["last_fetch"] = now
                        changed, changed_at = await asyncio.to_thread(self.persist, reading, digest, now)
                        if changed:
                            self.status.update(state="online", message="Lokale Messung aktiv.", params={}, last_success=now)
                        elif now - changed_at > 30:
                            self.status.update(state="stale", message="Unverändertes Telegramm seit über 30 Sekunden. Empfang prüfen.", params={})
                        else:
                            self.status.update(state="online", message="Warte auf das nächste Zählertelegramm.", params={})
                        self.status["endpoint"] = bridge.endpoint
                        self.status["host"] = bridge.host
                        self.status["resolved_addresses"] = bridge.resolved_addresses
                        failures = 0
                        if now - self.diagnostics.get("checked_at", 0) > 60:
                            try:
                                self.diagnostics = await bridge.diagnostics()
                            except ValueError:
                                # Fehlende Diagnosefunktion unterbricht nie gültige Messdaten.
                                self.diagnostics["checked_at"] = now
                    if time.time() - self.last_maintenance > 600:
                        # Sicherung und Aufräumen nie im Event-Loop ausführen.
                        await asyncio.to_thread(self.store.maintenance)
                        self.last_maintenance = time.time()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    failures += 1
                    # Niemals HTTP-Header, Passwörter oder den rohen Response loggen.
                    message = str(exc) if isinstance(exc, ValueError) else "Interner Erfassungsfehler (" + type(exc).__name__ + ")."
                    # Vorlage und Werte getrennt, damit die Oberfläche die Meldung übersetzen kann.
                    template, params = (exc.template, exc.params) if isinstance(exc, UserError) else (
                        (message, {}) if isinstance(exc, ValueError) else ("Interner Erfassungsfehler ({error}).", {"error": type(exc).__name__}))
                    self.status.update(state="error", message=template, params=params, errors=self.status["errors"] + 1)
                    if failures == 1 or failures % 20 == 0:
                        log.warning("Erfassung: %s", message)
                        try:
                            await asyncio.to_thread(self.store.issue, "collector", message)
                        except Exception:
                            log.exception("Erfassungshinweis nicht speicherbar")
                    wait = min(120, max(wait, 2 ** min(failures, 7)))
                try:
                    await asyncio.wait_for(self.wakeup.wait(), timeout=wait)
                    self.wakeup.clear()
                except asyncio.TimeoutError:
                    pass
        finally:
            if bridge:
                await bridge.close()

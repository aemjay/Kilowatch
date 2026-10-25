import asyncio
from contextlib import asynccontextmanager
import csv
from datetime import date, datetime, timedelta
import io
import logging
from pathlib import Path
import secrets
import time
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import __version__
from .analytics import Analytics, iso, local_day, midnight, period
from .bridge import Bridge, validate_host
from .collector import Collector
from .config import Config
from .storage import Store
from .security import Auth, Vault, private_write
from .notifications import NotificationSettings, Notifications
from .network import local_request
from .discovery import Discovery, suggestions
from .market import Market
from .updates import Updates
from . import insights


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Login(StrictModel):
    password: str = Field(max_length=500)


class Setup(StrictModel):
    setup_code: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=12, max_length=500)


class PasswordChange(StrictModel):
    current_password: str = Field(max_length=500)
    new_password: str = Field(min_length=12, max_length=500)


class NotificationUpdate(NotificationSettings):
    smtp_password: str | None = Field(default=None, max_length=500)
    signal_token: str | None = Field(default=None, max_length=1000)
    clear_smtp_password: bool = False
    clear_signal_token: bool = False


class SettingsUpdate(StrictModel):
    bridge_host: str | None = None
    bridge_user: str | None = Field(default=None, min_length=1, max_length=80)
    bridge_password: str | None = Field(default=None, max_length=200)
    node_id: int | None = Field(default=None, ge=1, le=64)
    poll_seconds: int | None = Field(default=None, ge=2, le=60)
    max_gap_seconds: int | None = Field(default=None, ge=15, le=300)
    max_power_w: int | None = Field(default=None, ge=1000, le=1000000)
    raw_retention_days: int | None = Field(default=None, ge=0, le=3650)
    minute_retention_days: int | None = Field(default=None, ge=0, le=10000)
    high_load_w: int | None = Field(default=None, ge=100, le=100000)
    enabled: bool | None = None
    name: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("bridge_host")
    @classmethod
    def host(cls, v):
        return validate_host(v) if v is not None else v


class Tariff(StrictModel):
    start_date: date
    name: str = Field(min_length=1, max_length=80)
    mode: str
    eur_kwh: float = Field(ge=-5, le=10)
    base_month: float = Field(ge=0, le=1000)
    feedin_eur_kwh: float = Field(ge=-5, le=10)
    low_eur_kwh: float | None = Field(default=None, ge=-5, le=10)
    low_start: str = "22:00"
    low_end: str = "06:00"
    weekend_low: bool = False

    @field_validator("mode")
    @classmethod
    def valid_mode(cls, value):
        if value not in ("fixed", "dual", "dynamic"):
            raise ValueError("Tarifart muss fixed, dual oder dynamic sein.")
        return value

    @field_validator("low_start", "low_end")
    @classmethod
    def tariff_clock(cls, value):
        value = NotificationSettings.clock(value)
        if int(value[-2:]) % 15:
            raise ValueError("Tarifzeiten müssen auf Viertelstundengrenzen liegen.")
        return value

    @model_validator(mode="after")
    def dual_fields(self):
        if self.mode == "dual" and (self.low_eur_kwh is None or self.low_start == self.low_end):
            raise ValueError("Zweiter Preis und unterschiedliche NT-Anfangs-/Endzeit erforderlich.")
        return self


class Event(StrictModel):
    start_date: date
    end_date: date
    title: str = Field(min_length=1, max_length=120)
    note: str = Field(default="", max_length=2000)


class PriceImport(StrictModel):
    csv: str = Field(max_length=1500000)


class ScenarioTariff(StrictModel):
    mode: str
    eur_kwh: float = Field(default=0, ge=-5, le=10)
    low_eur_kwh: float | None = Field(default=None, ge=-5, le=10)
    low_start: str = "22:00"
    low_end: str = "06:00"
    weekend_low: bool = False
    markup_ct: float = Field(default=0, ge=-100, le=200)
    vat_percent: float = Field(default=19, ge=0, le=30)
    base_month: float = Field(ge=0, le=1000)
    feedin_eur_kwh: float = Field(default=0, ge=-5, le=10)

    @field_validator("mode")
    @classmethod
    def valid_mode(cls, value):
        if value not in ("fixed", "dual", "spot"):
            raise ValueError("Tarifart muss fixed, dual oder spot sein.")
        return value

    @field_validator("low_start", "low_end")
    @classmethod
    def tariff_clock(cls, value):
        return Tariff.tariff_clock(value)

    @model_validator(mode="after")
    def dual_fields(self):
        if self.mode == "dual" and (self.low_eur_kwh is None or self.low_start == self.low_end):
            raise ValueError("Zweiter Preis und unterschiedliche NT-Anfangs-/Endzeit erforderlich.")
        return self

    def as_tariff(self):
        values = self.model_dump()
        values["markup_eur_kwh"] = values.pop("markup_ct") / 100
        return values


class Simulation(StrictModel):
    start: date
    end: date
    tariff: ScenarioTariff


class Budget(StrictModel):
    monthly_eur: float | None = Field(default=None, gt=0, le=100000)
    monthly_kwh: float | None = Field(default=None, gt=0, le=1000000)
    abschlag_eur: float | None = Field(default=None, gt=0, le=100000)


class HistoryRequest(StrictModel):
    start: date
    end: date


class UpdateSettings(StrictModel):
    enabled: bool


class DiscoveryRequest(StrictModel):
    network: str = Field(min_length=1, max_length=50)


def parse_prices(text):
    delimiter = ";" if ";" in text.splitlines()[0] else ","
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")), delimiter=delimiter)
    if set(reader.fieldnames or []) != {"start", "end", "eur_kwh"}:
        raise ValueError("CSV-Kopf: start,end,eur_kwh (wahlweise Semikolon).")
    result = []
    for index, row in enumerate(reader, 2):
        if index > 35041:
            raise ValueError("Höchstens 35040 Preisintervalle je Import.")
        try:
            a, b = (datetime.fromisoformat(row[field].replace("Z", "+00:00")) for field in ["start", "end"])
            if a.tzinfo is None or b.tzinfo is None:
                raise ValueError()
            start, end = a.timestamp(), b.timestamp()
            rate = float(row["eur_kwh"].replace(",", "."))
            if start % 900 or end % 900 or not 900 <= end - start <= 86400 or not -5 <= rate <= 10:
                raise ValueError()
        except (ValueError, KeyError, TypeError, AttributeError):
            # Fehlende Spalten liefert DictReader als None.
            raise ValueError(f"Zeile {index}: UTC-Offset, Viertelstundengrenzen oder Preis ungültig.") from None
        result.append((int(start), int(end), rate))
    result.sort()
    if not result:
        raise ValueError("CSV enthält keine Preisintervalle.")
    if any(a[1] > b[0] for a, b in zip(result, result[1:])):
        raise ValueError("Preisintervalle überschneiden sich.")
    return result


def create_app(config=None):
    config = config or Config.from_env()
    folder = config.data_folder
    store = Store(folder)
    vault = Vault(config.secrets_folder)
    auth = Auth(config.secrets_folder)

    def get_password():
        return vault.get("bridge_password")

    collector = Collector(store, get_password, config.demo)
    notifier = Notifications(store, vault, collector, config.demo)
    discovery = Discovery()
    market = Market(store, config.demo)
    updates = Updates(store, config.update_repository, config.demo)
    sessions, attempts = {}, {}
    # Setup-Code zusätzlich als Datei im Datenordner, damit er ohne Container-Protokoll in der
    # File Station lesbar ist. Wer den Ordner lesen kann, hätte auch Zugriff auf das Protokoll.
    setup_file = Path(config.data_dir) / "SETUP-CODE.txt"

    def write_setup_code():
        try:
            private_write(setup_file, ("Kilowatch-Setup-Code: " + auth.setup_code + "\n\n"
                                       "Im Browser die Kilowatch-Adresse öffnen, diesen Code eingeben und ein eigenes App-Passwort festlegen.\n"
                                       "Die Datei wird nach der Einrichtung automatisch gelöscht.\n").encode())
        except OSError:
            logging.getLogger("kilowatch").warning("Setup-Code-Datei konnte nicht geschrieben werden; Code steht im Protokoll.")

    def remove_setup_code():
        try:
            setup_file.unlink(missing_ok=True)
        except OSError:
            pass

    def recent_attempts(key, now):
        # Abgelaufene Einträge aller Adressen entfernen, damit das Dict nicht wächst.
        for other in [k for k, times in attempts.items() if all(now - t >= 900 for t in times)]:
            attempts.pop(other, None)
        return attempts.get(key, [])

    @asynccontextmanager
    async def lifespan(app):
        if not auth.configured:
            logging.getLogger("kilowatch").warning("Ersteinrichtung: Setup-Code %s – im Browser ein eigenes App-Passwort festlegen.", auth.setup_code)
            write_setup_code()
        else:
            remove_setup_code()
        if config.demo and not config.testing:
            from .demo import seed
            await asyncio.to_thread(seed, store)
        tasks = [asyncio.create_task(collector.run()), asyncio.create_task(notifier.run()),
                 asyncio.create_task(updates.run())] if not config.testing else []
        yield
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        store.close()

    app = FastAPI(title="Kilowatch", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store, app.state.collector = store, collector
    app.state.config = config
    app.state.auth, app.state.vault, app.state.notifier = auth, vault, notifier
    app.state.updates = updates

    @app.middleware("http")
    async def guard(request: Request, call_next):
        path = request.url.path
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            origin = request.headers.get("origin")
            if request.headers.get("x-kilowatch-request") != "1" or (origin and urlparse(origin).netloc != request.headers.get("host")):
                return JSONResponse({"detail": "Ungültiger Anfrageursprung."}, status_code=403)
        if path.startswith("/api/") and path not in ("/api/login", "/api/setup/status", "/api/setup"):
            token = request.cookies.get("kilowatch_session")
            if sessions.get(token, 0) <= time.time():
                return JSONResponse({"detail": "Bitte anmelden."}, status_code=401)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.get("/healthz")
    def health():
        store.rows("SELECT 1")
        return {"status": "ok", "version": __version__}

    @app.get("/api/setup/status")
    def setup_status():
        return {"needs_setup": not auth.configured}

    @app.post("/api/setup")
    def setup(data: Setup, request: Request):
        now = time.time()
        ip = "setup:" + (request.client.host if request.client else "unknown")
        history = [t for t in recent_attempts(ip, now) if now - t < 900]
        if len(history) >= 10:
            raise HTTPException(429, "Zu viele ungültige Setup-Codes. In 15 Minuten erneut versuchen.")
        try:
            auth.initialize(data.password, data.setup_code)
            remove_setup_code()
        except ValueError:
            attempts[ip] = history + [now]
            raise
        attempts.pop(ip, None)
        return {"ok": True}

    @app.post("/api/login")
    def login(data: Login, request: Request):
        now = time.time()
        ip = request.client.host if request.client else "unknown"
        history = [t for t in recent_attempts(ip, now) if now - t < 900]
        if len(history) >= 10:
            raise HTTPException(429, "Zu viele Anmeldeversuche. In 15 Minuten erneut versuchen.")
        if not auth.verify(data.password):
            attempts[ip] = history + [now]
            raise HTTPException(401, "Passwort stimmt nicht.")
        attempts.pop(ip, None)
        for token, expires in list(sessions.items()):
            if expires <= now:
                sessions.pop(token, None)
        token = secrets.token_urlsafe(32)
        sessions[token] = now + 12 * 3600
        response = JSONResponse({"ok": True})
        response.set_cookie("kilowatch_session", token, max_age=12 * 3600, httponly=True,
                            secure=config.secure_cookie, samesite="strict", path="/")
        return response

    @app.post("/api/logout")
    def logout(request: Request):
        sessions.pop(request.cookies.get("kilowatch_session"), None)
        response = JSONResponse({"ok": True})
        response.delete_cookie("kilowatch_session")
        return response

    @app.put("/api/account/password")
    def change_password(data: PasswordChange):
        if not auth.verify(data.current_password):
            raise ValueError("Bisheriges App-Passwort stimmt nicht.")
        auth.set_password(data.new_password)
        sessions.clear()
        response = JSONResponse({"ok": True, "login_required": True})
        response.delete_cookie("kilowatch_session")
        return response

    @app.get("/api/settings")
    def settings():
        saved = store.settings()
        ready = bool(saved["bridge_host"] and saved["bridge_user"] and get_password())
        return dict(saved, password_configured=bool(get_password()), setup_required=not ready,
                    credential_storage="encrypted_local", demo=config.demo,
                    version=__version__)

    @app.put("/api/settings")
    async def save_settings(data: SettingsUpdate):
        values = data.model_dump(exclude_none=True)
        password = values.pop("bridge_password", None)
        if password:
            vault.update({"bridge_password": password})
        store.update_settings(values)
        collector.wakeup.set()
        return {"ok": True, "password_configured": bool(get_password())}

    @app.delete("/api/credentials/bridge")
    async def forget_bridge():
        vault.update({"bridge_password": None})
        store.update_settings({"enabled": False})
        collector.wakeup.set()
        return {"ok": True}

    @app.post("/api/bridge/test")
    async def test_bridge(data: SettingsUpdate):
        if config.demo:
            return {"ok": True, "protocol": "Beispieldaten", "endpoint": "Demo", "has_import": True, "has_export": True, "has_power": True}
        saved = store.settings()
        values = dict(saved, **data.model_dump(exclude_none=True, exclude={"bridge_password"}))
        if not data.bridge_password and (values["bridge_host"] != saved["bridge_host"] or values["bridge_user"] != saved["bridge_user"]):
            # Gespeichertes Passwort nie an eine neu eingegebene Adresse senden.
            raise ValueError("Für eine geänderte Bridge-Adresse oder einen anderen Benutzer das Bridge-Passwort erneut eingeben.")
        password = data.bridge_password or get_password()
        if not password:
            raise ValueError("Bridge-Passwort fehlt.")
        bridge = Bridge(values, password)
        try:
            reading, _ = await bridge.read()
            return {"ok": True, "protocol": reading.protocol, "endpoint": bridge.endpoint,
                    "has_import": reading.import_kwh is not None, "has_export": reading.export_kwh is not None,
                    "has_power": reading.power_w is not None, "registers": list(reading.obis),
                    "resolved_addresses": bridge.resolved_addresses, "host": bridge.host}
        finally:
            await bridge.close()

    @app.get("/api/live")
    def live():
        latest = store.latest()
        age = time.time() - latest["ts"] if latest else None
        return {"reading": latest, "age_seconds": age, "stale": age is None or age > 30,
                "collector": collector.status, "diagnostics": collector.diagnostics,
                "obis": store.state("last_obis", {}), "demo": config.demo}

    @app.get("/api/discovery/network")
    async def discovery_network(request: Request):
        networks = await suggestions(request.client.host if request.client else "", store.settings()["bridge_host"], request.url.hostname)
        return {"suggestions": networks, "max_addresses": 256, "prefix_is_suggestion": True}

    @app.post("/api/discovery/scan")
    async def discovery_scan(data: DiscoveryRequest):
        return await discovery.scan(data.network, config.demo)

    @app.get("/api/notifications")
    def notification_settings():
        return {"settings": notifier.config().model_dump(),
                "smtp_password_configured": bool(vault.get("smtp_password")),
                "signal_token_configured": bool(vault.get("signal_token")),
                "last_error": notifier.last_error,
                "history": store.rows("SELECT id,rule_key,kind,channel,subject,status,attempts,created,next_try,last_error FROM notifications ORDER BY id DESC LIMIT 100")}

    @app.put("/api/notifications")
    async def save_notifications(data: NotificationUpdate):
        private = {"smtp_password", "signal_token", "clear_smtp_password", "clear_signal_token"}
        updated = NotificationSettings(**data.model_dump(exclude=private))
        # Vor dem Speichern von Geheimnissen prüfen; save() prüft erneut mit derselben Logik.
        notifier.validate(updated)
        values = {}
        for field in ("smtp_password", "signal_token"):
            value = getattr(data, field)
            if getattr(data, "clear_" + field):
                values[field] = None
            elif value:
                values[field] = value
        if values:
            vault.update(values)
        notifier.save(updated)
        return {"ok": True}

    @app.post("/api/notifications/test/{channel}")
    async def test_notifications(channel: str):
        return await notifier.test(channel)

    @app.post("/api/notifications/signal/qr")
    async def signal_qr():
        if config.demo:
            raise ValueError("Signal-Kopplung ist im Demo-Modus ausgeschaltet.")
        saved = notifier.config()
        if not saved.signal_url:
            raise ValueError("Zuerst die lokale Signal-Gateway-URL speichern.")
        status, body, kind = await local_request(saved.signal_url, "/v1/qrcodelink?device_name=Kilowatch", token=vault.get("signal_token"), max_bytes=1024*1024)
        if status != 200 or not body.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Gateway liefert keinen Kopplungs-QR-Code als PNG. Erreichbarkeit und Gateway-Modus prüfen.")
        return Response(body, media_type="image/png", headers={"Cache-Control": "no-store"})

    def range_for(start, end):
        return period(start, end, store.settings()["timezone"], time.time())

    @app.get("/api/overview")
    def overview(start: str | None = None, end: str | None = None):
        s, e = range_for(start, end)
        a = Analytics(store)
        selected_start = local_day(s, a.zone)
        selected_end = date.fromisoformat(end) if end else local_day(time.time(), a.zone)
        days = (selected_end - selected_start).days + 1
        previous_start = midnight(selected_start - timedelta(days=days), a.zone)
        previous_end = min(s, previous_start + (e - s))
        # Historische Teilviertelstunden nicht als zeitgenau rekonstruieren.
        previous_end = int(previous_end // 900) * 900
        previous = a.summary(previous_start, previous_end) if previous_end > previous_start else None
        return {"summary": a.summary(s, e), "previous": previous, "series": a.series(s, e),
                "gaps": store.gap_rows(s, e), "timezone": a.zone}

    @app.get("/api/analysis")
    def analysis(start: str | None = None, end: str | None = None):
        s, e = range_for(start, end)
        a = Analytics(store)
        return dict(a.patterns(s, e), forecast=a.forecast(time.time()))

    @app.get("/api/tariffs")
    def tariffs():
        schedules = store.state("tariff_schedules", {})
        return {"tariffs": [dict(row, **schedules.get(row["start_date"], {})) for row in store.rows("SELECT * FROM tariffs ORDER BY start_date")],
                "prices": store.rows("SELECT COUNT(*) AS count,MIN(start) AS start,MAX(end) AS end FROM prices")[0], "market":market.cached(),
                "spot_history": market.history_status()}

    @app.get("/api/insights")
    def insight_data(start: str | None = None, end: str | None = None):
        s, e = range_for(start, end)
        a = Analytics(store)
        return {"baseline_trend": insights.baseline_trend(a, s, e), "feedin": insights.feedin_profile(a, s, e)}

    @app.post("/api/simulate")
    def simulate(data: Simulation):
        s, e = range_for(data.start.isoformat(), data.end.isoformat())
        return insights.simulate(Analytics(store), s, e, data.tariff.as_tariff())

    @app.get("/api/budget")
    def budget():
        saved = store.state("budget", {})
        a, now = Analytics(store), time.time()
        return {"settings": Budget(**saved).model_dump(), "month": insights.month_budget(a, now, saved),
                "annual": insights.annual_projection(a, now, saved.get("abschlag_eur"))}

    @app.put("/api/budget")
    def save_budget(data: Budget):
        store.set_state("budget", data.model_dump())
        notifier.wakeup.set()
        return {"ok": True}

    @app.post("/api/market/history")
    async def market_history(data: HistoryRequest):
        if data.end < data.start:
            raise ValueError("Ende liegt vor dem Beginn.")
        zone = store.settings()["timezone"]
        return await market.history(midnight(data.start, zone), midnight(data.end + timedelta(days=1), zone))

    @app.post("/api/market/refresh")
    async def refresh_market():
        return await market.refresh()

    @app.put("/api/tariffs")
    def save_tariff(data: Tariff):
        with store.transaction():
            store.conn.execute("INSERT OR REPLACE INTO tariffs VALUES(?,?,?,?,?,?)", (data.start_date.isoformat(), data.name, data.mode, data.eur_kwh, data.base_month, data.feedin_eur_kwh))
            schedules = store.state("tariff_schedules", {})
            key = data.start_date.isoformat()
            if data.mode == "dual":
                schedules[key] = data.model_dump(include={"low_eur_kwh", "low_start", "low_end", "weekend_low"})
            else:
                schedules.pop(key, None)
            store.set_state("tariff_schedules", schedules)
        return {"ok": True}

    @app.delete("/api/tariffs/{start_date}")
    def delete_tariff(start_date: date):
        with store.transaction():
            store.conn.execute("DELETE FROM tariffs WHERE start_date=?", (start_date.isoformat(),))
            schedules = store.state("tariff_schedules", {})
            schedules.pop(start_date.isoformat(), None)
            store.set_state("tariff_schedules", schedules)
        return {"ok": True}

    @app.post("/api/prices/import")
    def import_prices(data: PriceImport):
        if not data.csv.strip():
            raise ValueError("CSV ist leer.")
        values = parse_prices(data.csv)
        with store.transaction():
            # Gleiche Intervalle dürfen aktualisiert werden, überlappende andere nicht.
            for start, end, rate in values:
                overlap = store.rows("SELECT start,end FROM prices WHERE start<? AND end>? AND start<>?", (end, start, start))
                if overlap:
                    raise ValueError("Überlappung mit bereits gespeicherten Preisen. Bestehende Intervalle vorher löschen.")
                store.conn.execute("INSERT OR REPLACE INTO prices VALUES(?,?,?)", (start, end, rate))
        return {"ok": True, "count": len(values)}

    @app.delete("/api/prices")
    def delete_prices():
        with store.transaction():
            store.conn.execute("DELETE FROM prices")
        return {"ok": True}

    @app.get("/api/events")
    def events():
        return store.rows("SELECT * FROM events ORDER BY start DESC")

    @app.post("/api/events")
    def add_event(data: Event):
        if data.end_date < data.start_date:
            raise ValueError("Ende liegt vor dem Beginn.")
        if (data.end_date - data.start_date).days > 3659:
            raise ValueError("Ereignis zu lang.")
        zone = store.settings()["timezone"]
        with store.transaction():
            store.conn.execute("INSERT INTO events(start,end,title,note) VALUES(?,?,?,?)", (midnight(data.start_date, zone), midnight(data.end_date + timedelta(days=1), zone), data.title, data.note))
        return {"ok": True}

    @app.delete("/api/events/{event_id}")
    def delete_event(event_id: int):
        with store.transaction():
            store.conn.execute("DELETE FROM events WHERE id=?", (event_id,))
        return {"ok": True}

    @app.get("/api/events/{event_id}/comparison")
    def compare_event(event_id: int):
        rows = store.rows("SELECT * FROM events WHERE id=?", (event_id,))
        if not rows:
            raise HTTPException(404, "Ereignis fehlt.")
        event = rows[0]
        end = min(event["end"], time.time())
        if end <= event["start"]:
            raise ValueError("Ereignis liegt in der Zukunft.")
        a = Analytics(store)
        days = (local_day(event["end"], a.zone) - local_day(event["start"], a.zone)).days
        before = midnight(local_day(event["start"], a.zone) - timedelta(days=days), a.zone)
        return {"event": event, "during": a.summary(event["start"], end), "before": a.summary(before, event["start"])}

    @app.get("/api/export")
    def export(start: str | None = None, end: str | None = None, kind: str = "quarters", format: str = "csv", offset: int = 0, limit: int = 100000):
        s, e = range_for(start, end)
        if not 1 <= limit <= 100000 or offset < 0:
            raise ValueError("Limit 1–100000 und Offset ≥ 0 erforderlich.")
        if kind == "samples":
            rows = store.rows("SELECT * FROM samples WHERE ts>=? AND ts<? ORDER BY ts LIMIT ? OFFSET ?", (s, e, limit, offset))
        elif kind in ("minutes", "quarters"):
            resolution = 60 if kind == "minutes" else 900
            rows = store.rows("SELECT * FROM buckets WHERE resolution=? AND ts>=? AND ts<? ORDER BY ts LIMIT ? OFFSET ?", (resolution, s, e, limit, offset))
        elif kind == "gaps":
            rows = store.gap_rows(s, e)[offset:offset + limit]
        else:
            raise ValueError("kind: samples, minutes, quarters oder gaps.")
        zone = store.settings()["timezone"]
        for row in rows:
            stamp = row.get("ts", row.get("start"))
            row["time_utc"], row["time_local"] = iso(stamp), iso(stamp, zone)
        headers = {"Content-Disposition": f'attachment; filename="kilowatch-{kind}.{format}"', "X-Export-Count": str(len(rows)), "X-Export-Next-Offset": str(offset + len(rows))}
        if format == "json":
            return JSONResponse({"data": rows, "count": len(rows), "next_offset": offset + len(rows), "page_full": len(rows) == limit}, headers=headers)
        if format != "csv":
            raise ValueError("format: csv oder json.")
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=list(rows[0]), delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        return Response("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)

    @app.get("/api/backup")
    def backup():
        path = store.backup()
        return FileResponse(path, filename=path.name, media_type="application/vnd.sqlite3")

    @app.get("/api/updates")
    def update_status():
        return updates.status()

    @app.put("/api/updates")
    def update_settings(data: UpdateSettings):
        updates.set_enabled(data.enabled)
        return updates.status()

    @app.post("/api/updates/check")
    async def update_check():
        return await updates.check(manual=True)

    @app.get("/api/diagnostics")
    def diagnostics():
        return {"collector": collector.status, "bridge": collector.diagnostics,
                "issues": store.rows("SELECT * FROM issues ORDER BY id DESC LIMIT 100"),
                "counts": {"samples": store.rows("SELECT COUNT(*) AS n FROM samples")[0]["n"],
                           "quarters": store.rows("SELECT COUNT(*) AS n FROM buckets WHERE resolution=900")[0]["n"]},
                "database_bytes": sum(p.stat().st_size for p in folder.glob("kilowatch.sqlite3*")),
                "backups": [p.name for p in sorted((folder / "backups").glob("*.sqlite3"))[-7:]],
                "version": __version__, "demo": config.demo}

    app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="frontend")
    return app


def factory():
    return create_app()

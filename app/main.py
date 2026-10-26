import asyncio
from contextlib import asynccontextmanager
import csv
from datetime import date, datetime, timedelta
import io
import logging
import math
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import StarletteHTTPException
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
from .discovery import Discovery, suggestions
from .market import Market
from .updates import Updates
from .grid import COUNTRIES, Grid
from . import prices as price_feed
from . import insights
from . import checklist as setup_checklist
from .i18n import CURRENCIES, LANGUAGES, UserError, translate_error


# Höchstgröße des Request-Bodys in Bytes, geprüft vor dem JSON-Parsing (auch ohne Content-Length).
BODY_LIMITS = {"/api/login": 4096, "/api/setup": 4096, "/api/account/password": 4096,
               "/api/prices/import": 4 * 1024 * 1024}
DEFAULT_BODY_LIMIT = 256 * 1024
# Fehlversuche je Adresse und insgesamt innerhalb von 15 Minuten.
ATTEMPT_WINDOW, ATTEMPTS_PER_ADDRESS, ATTEMPTS_TOTAL = 900, 10, 50


class BodyLimit:
    """ASGI-Middleware: zählt tatsächlich empfangene Bytes und lehnt zu große Anfragen mit 413 ab."""

    def __init__(self, app, reject):
        self.app, self.reject = app, reject

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = BODY_LIMITS.get(scope["path"], DEFAULT_BODY_LIMIT)
        length = dict(scope["headers"]).get(b"content-length")
        if length is not None and (not length.isdigit() or int(length) > limit):
            return await self.reject(scope, receive, send)
        received = 0

        async def limited():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise HTTPException(413, "Anfrage ist zu groß.")
            return message

        await self.app(scope, limited, send)


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
    clear_smtp_password: bool = False


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
    language: str | None = None
    currency: str | None = None
    grid_country: str | None = None
    household_persons: int | None = Field(default=None, ge=0, le=5)
    household_type: str | None = None
    household_hot_water: bool | None = None

    @field_validator("household_type")
    @classmethod
    def valid_household_type(cls, v):
        if v is not None and v not in ("apartment", "house"):
            raise ValueError("Wohnform muss Wohnung oder Haus sein.")
        return v

    @field_validator("grid_country")
    @classmethod
    def valid_grid_country(cls, v):
        if v is not None and v not in ("", *COUNTRIES):
            raise ValueError("Land für den Strommix wird nicht unterstützt.")
        return v

    @field_validator("language")
    @classmethod
    def valid_language(cls, v):
        if v is not None and v not in LANGUAGES:
            raise ValueError("Sprache wird nicht unterstützt.")
        return v

    @field_validator("currency")
    @classmethod
    def valid_currency(cls, v):
        if v is not None and v not in CURRENCIES:
            raise ValueError("Währung wird nicht unterstützt.")
        return v

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


class PriceSource(StrictModel):
    source: str
    zone: str = "DE-LU"
    markup_ct: float = Field(default=0, ge=-100, le=200)
    vat_percent: float = Field(default=0, ge=0, le=50)
    tibber_home: str = Field(default="", max_length=80)
    tibber_token: str | None = Field(default=None, max_length=200)
    clear_tibber_token: bool = False

    @field_validator("source")
    @classmethod
    def known_source(cls, value):
        if value not in price_feed.SOURCES:
            raise ValueError("Preisquelle muss leer, tibber oder spot sein.")
        return value

    @field_validator("zone")
    @classmethod
    def known_zone(cls, value):
        if value not in price_feed.ZONES:
            raise ValueError("Unbekannte Gebotszone.")
        return value

    @field_validator("tibber_token")
    @classmethod
    def token_text(cls, value):
        if value is not None and (any(ord(c) < 33 for c in value)):
            raise ValueError("Steuer- und Leerzeichen sind nicht erlaubt.")
        return value


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
    billing_start: str | None = None

    @field_validator("billing_start")
    @classmethod
    def billing_day(cls, value):
        # MM-DD; der 29. Februar fehlt in den meisten Jahren und ist daher nicht erlaubt.
        if value is not None:
            try:
                if len(value) != 5 or value[2] != "-":
                    raise ValueError()
                date(2001, int(value[:2]), int(value[3:]))
            except ValueError:
                raise ValueError("Beginn des Abrechnungsjahrs: gültiger Tag und Monat (nicht 29.02.).") from None
        return value


class ChecklistMute(StrictModel):
    muted: list[str] = Field(max_length=len(setup_checklist.KEYS))

    @field_validator("muted")
    @classmethod
    def known_keys(cls, value):
        if any(key not in setup_checklist.KEYS for key in value):
            raise ValueError("Unbekannter Punkt der Einrichtungsliste.")
        return sorted(set(value))


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
            raise UserError("Zeile {index}: UTC-Offset, Viertelstundengrenzen oder Preis ungültig.", index=index) from None
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
    if vault.get("signal_token", None) is not None:
        # Reste des in 1.2 entfernten Signal-Kanals.
        vault.update({"signal_token": None})
    discovery = Discovery()
    market = Market(store, config.demo)
    updates = Updates(store, config.update_repository, config.demo)
    grid = Grid(store, config.demo)
    feed = price_feed.PriceFeed(store, vault, config.demo)
    sessions, attempts = {}, {}
    attempt_lock = threading.Lock()
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

    def reserve_attempt(kind, request, message):
        """Versuch vor der teuren Prüfung atomar zählen; zu viele (je Adresse oder insgesamt) -> 429.

        Parallele Anfragen zählen sofort mit. Bei Erfolg gibt forget_attempts() die Adresse frei.
        """
        now = time.time()
        key = (kind, request.client.host if request.client else "unknown")
        with attempt_lock:
            # Abgelaufene Einträge entfernen, damit das Dict nicht wächst.
            for other in list(attempts):
                attempts[other] = [t for t in attempts[other] if now - t < ATTEMPT_WINDOW]
                if not attempts[other]:
                    attempts.pop(other)
            total = sum(len(times) for (other, _), times in attempts.items() if other == kind)
            if len(attempts.get(key, [])) >= ATTEMPTS_PER_ADDRESS or total >= ATTEMPTS_TOTAL:
                raise HTTPException(429, message)
            attempts.setdefault(key, []).append(now)
        return key

    def forget_attempts(key):
        with attempt_lock:
            attempts.pop(key, None)

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
                 asyncio.create_task(updates.run()), asyncio.create_task(grid.run()), asyncio.create_task(feed.run())] if not config.testing else []
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
    app.state.grid = grid
    app.state.feed = feed

    def language(request):
        """Sprache der Anfrage (Kopfzeile der Oberfläche), sonst die gespeicherte Einstellung."""
        chosen = request.headers.get("x-kilowatch-language")
        return chosen if chosen in LANGUAGES else store.settings().get("language") or "de"

    def failure(request, status, error):
        currency = store.settings().get("currency", "EUR")
        return JSONResponse({"detail": translate_error(error, language(request), currency)}, status_code=status)

    async def too_large(scope, receive, send):
        await failure(Request(scope), 413, "Anfrage ist zu groß.")(scope, receive, send)

    # Innerhalb von guard registriert, damit die 413-Ausnahme nicht in dessen Task-Gruppe landet.
    app.add_middleware(BodyLimit, reject=too_large)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        path = request.url.path
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            origin = request.headers.get("origin")
            if request.headers.get("x-kilowatch-request") != "1" or (origin and urlparse(origin).netloc != request.headers.get("host")):
                return failure(request, 403, "Ungültiger Anfrageursprung.")
        if path.startswith("/api/") and path not in ("/api/login", "/api/setup/status", "/api/setup"):
            token = request.cookies.get("kilowatch_session")
            if sessions.get(token, 0) <= time.time():
                return failure(request, 401, "Bitte anmelden.")
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return failure(request, 400, exc)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        if not isinstance(exc.detail, str):
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
        response = failure(request, exc.status_code, exc.detail)
        response.headers.update(exc.headers or {})
        return response

    @app.get("/healthz")
    def health():
        store.rows("SELECT 1")
        return {"status": "ok", "version": __version__}

    @app.get("/api/setup/status")
    def setup_status():
        return {"needs_setup": not auth.configured}

    @app.post("/api/setup")
    def setup(data: Setup, request: Request):
        key = reserve_attempt("setup", request, "Zu viele ungültige Setup-Codes. In 15 Minuten erneut versuchen.")
        auth.initialize(data.password, data.setup_code)
        remove_setup_code()
        forget_attempts(key)
        return {"ok": True}

    @app.post("/api/login")
    def login(data: Login, request: Request):
        key = reserve_attempt("login", request, "Zu viele Anmeldeversuche. In 15 Minuten erneut versuchen.")
        # Prüfung und Sitzungsausgabe unter demselben Lock wie der Passwortwechsel: ein
        # paralleler Wechsel kann so keine Sitzung übrig lassen, die mit dem alten Passwort entstand.
        with auth.lock:
            if not auth.verify(data.password):
                raise HTTPException(401, "Passwort stimmt nicht.")
            now = time.time()
            for token, expires in list(sessions.items()):
                if expires <= now:
                    sessions.pop(token, None)
            token = secrets.token_urlsafe(32)
            sessions[token] = now + 12 * 3600
        forget_attempts(key)
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
    def change_password(data: PasswordChange, request: Request):
        key = reserve_attempt("password", request, "Zu viele Versuche. In 15 Minuten erneut versuchen.")
        with auth.lock:
            if not auth.verify(data.current_password):
                raise ValueError("Bisheriges App-Passwort stimmt nicht.")
            auth.set_password(data.new_password)
            sessions.clear()
        forget_attempts(key)
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
        saved = store.settings()
        # Erstmals eingetragene Adresse ist kein Zielwechsel.
        moved = saved["bridge_host"] and any(field in values and values[field] != saved[field] for field in ("bridge_host", "bridge_user"))
        if moved and not password and get_password() and not config.demo:
            # Das gespeicherte Passwort gehört zur bisherigen Bridge und geht nie an ein neues Ziel.
            raise ValueError("Für eine geänderte Bridge-Adresse oder einen anderen Benutzer das Bridge-Passwort erneut eingeben.")
        if password:
            vault.update({"bridge_password": password})
        store.update_settings(values)
        collector.wakeup.set()
        if "grid_country" in values:
            grid.wakeup.set()
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
        now = time.time()
        age = now - latest["ts"] if latest else None
        stale = age is None or age > 30
        # Kostenrate nur aus einer frischen Messung; die Preise der laufenden Viertelstunde immer.
        power = latest.get("power_w") if latest and not stale else None
        return {"reading": latest, "age_seconds": age, "stale": stale,
                "collector": collector.status, "diagnostics": collector.diagnostics,
                "obis": store.state("last_obis", {}), "demo": config.demo,
                "cost": insights.live_cost(Analytics(store), now, power)}

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
                "last_error": notifier.last_error,
                "history": store.rows("SELECT id,rule_key,kind,channel,subject,status,attempts,created,next_try,last_error FROM notifications ORDER BY id DESC LIMIT 100")}

    @app.put("/api/notifications")
    async def save_notifications(data: NotificationUpdate):
        private = {"smtp_password", "clear_smtp_password"}
        updated = NotificationSettings(**data.model_dump(exclude=private))
        # Vor dem Speichern von Geheimnissen prüfen; save() prüft erneut mit derselben Logik.
        notifier.validate(updated)
        # Das gespeicherte Passwort gehört zu seinem Server und geht nie an einen geänderten.
        saved = notifier.config()
        moved = any(str(getattr(saved, key)).lower() != str(getattr(updated, key)).lower()
                    for key in ("smtp_security", "smtp_host", "smtp_port", "smtp_user"))
        if moved and vault.get("smtp_password") and not data.smtp_password and not data.clear_smtp_password:
            raise ValueError("Für einen geänderten SMTP-Server das SMTP-Passwort erneut eingeben oder entfernen.")
        if data.clear_smtp_password:
            vault.update({"smtp_password": None})
        elif data.smtp_password:
            vault.update({"smtp_password": data.smtp_password})
        notifier.save(updated)
        return {"ok": True}

    @app.post("/api/notifications/test/{channel}")
    async def test_notifications(channel: str):
        return await notifier.test(channel)

    def range_for(start, end, hours=None, minutes=None, since=None, until=None):
        return period(start, end, store.settings()["timezone"], time.time(), hours, minutes, since, until)

    @app.get("/api/overview")
    def overview(start: str | None = None, end: str | None = None, hours: int | None = None, minutes: int | None = None,
                 since: int | None = None, until: int | None = None):
        s, e = range_for(start, end, hours, minutes, since, until)
        a = Analytics(store)
        # Minutenfenster rechnen mit Minutenwerten, alles andere mit Viertelstunden.
        step = 60 if minutes is not None or (since is not None and e - s <= 7200) else 900
        if hours is not None or minutes is not None or since is not None:
            # Vergleich mit dem gleich langen Abschnitt direkt davor.
            previous_start, previous_end = s - (e - s), s
        else:
            selected_start = local_day(s, a.zone)
            selected_end = date.fromisoformat(end) if end else local_day(time.time(), a.zone)
            days = (selected_end - selected_start).days + 1
            previous_start = midnight(selected_start - timedelta(days=days), a.zone)
            previous_end = min(s, previous_start + (e - s))
        # Historische Teilviertelstunden nicht als zeitgenau rekonstruieren.
        previous_end = int(previous_end // step) * step
        previous = a.summary(previous_start, previous_end, step) if previous_end > previous_start else None
        # Referenzwert für Tagesbalken: Monatsziel als durchschnittlicher Tagesanteil.
        monthly_kwh = store.state("budget", {}).get("monthly_kwh")
        targets = {"daily_kwh": monthly_kwh * 12 / 365.25 if monthly_kwh else None,
                   "household": insights.household_reference(store.settings())}
        # CO₂-Werte gibt es je Viertelstunde; Minutenwerte der jeweiligen Viertelstunde zuordnen.
        buckets = [dict(row, ts=row["ts"] // 900 * 900) for row in store.bucket_rows(s, e, step)]
        return {"summary": a.summary(s, e, step), "previous": previous, "series": a.series(s, e),
                "gaps": store.gap_rows(s, e), "timezone": a.zone, "targets": targets,
                "co2": grid.balance(buckets, s, e)}

    @app.get("/api/analysis")
    def analysis(start: str | None = None, end: str | None = None, hours: int | None = None, minutes: int | None = None,
                 since: int | None = None, until: int | None = None):
        s, e = range_for(start, end, hours, minutes, since, until)
        a = Analytics(store)
        return dict(a.patterns(s, e), forecast=a.forecast(time.time()))

    @app.get("/api/tariffs")
    def tariffs():
        schedules = store.state("tariff_schedules", {})
        return {"tariffs": [dict(row, **schedules.get(row["start_date"], {})) for row in store.rows("SELECT * FROM tariffs ORDER BY start_date")],
                "prices": store.rows("SELECT COUNT(*) AS count,MIN(start) AS start,MAX(end) AS end FROM prices")[0], "market":market.cached(),
                "spot_history": market.history_status(), "price_feed": price_feed_state()}

    def price_feed_state():
        return dict(feed.config(), status=feed.status(), tibber_token_configured=bool(vault.get("tibber_token")),
                    zones=list(price_feed.ZONES), spot_source=price_feed.SPOT_SOURCE)

    @app.put("/api/prices/source")
    async def save_price_source(data: PriceSource):
        values = data.model_dump(exclude={"tibber_token", "clear_tibber_token"})
        if data.clear_tibber_token:
            vault.update({"tibber_token": None})
        elif data.tibber_token:
            vault.update({"tibber_token": data.tibber_token})
        old = feed.config()
        store.set_state("price_feed", values)
        # Andere Quelle oder Formel: Zeitraum neu nachladen und alle Preise neu berechnen.
        if any(old[key] != values[key] for key in ("source", "zone", "markup_ct", "vat_percent", "tibber_home")) or data.tibber_token:
            feed.reset()
        # Gleich abrufen, damit Fehler (Token, Währung, Zuhause) sofort sichtbar sind.
        await feed.refresh()
        return price_feed_state()

    @app.get("/api/prices/outlook")
    def price_outlook(window_hours: int = 2):
        if not 1 <= window_hours <= 6:
            raise ValueError("Fensterlänge: 1 bis 6 Stunden.")
        return insights.price_outlook(Analytics(store), time.time(), window_hours)

    @app.post("/api/prices/refresh")
    async def refresh_prices():
        if not feed.config()["source"]:
            raise ValueError("Zuerst eine Preisquelle wählen.")
        if time.time() - (feed.status().get("fetched_at") or 0) < 30:
            raise ValueError("Bitte 30 Sekunden zwischen Abrufen warten.")
        await feed.refresh()
        return price_feed_state()

    @app.get("/api/timeline")
    def timeline():
        """Gesamter erfasster Zeitraum in groben Abschnitten für den Zeitbalken; keine Einzelwerte."""
        first = store.rows("SELECT MIN(ts) AS first FROM buckets WHERE resolution=900")[0]["first"]
        now = int(time.time())
        if first is None:
            return {"start": None, "end": now, "bin_seconds": 900, "bins": []}
        first = int(first) // 900 * 900
        bin_seconds = max(900, math.ceil((now - first) / 320 / 900) * 900)
        first = first // bin_seconds * bin_seconds
        rows = store.rows("SELECT CAST(ts AS INTEGER)/?*? AS ts, SUM(import_kwh) AS kwh, SUM(import_s) AS covered FROM buckets "
                          "WHERE resolution=900 GROUP BY 1 ORDER BY 1", (bin_seconds, bin_seconds))
        return {"start": first, "end": now, "bin_seconds": bin_seconds,
                "bins": [{"ts": row["ts"], "kwh": round(row["kwh"] or 0, 4), "covered": round((row["covered"] or 0) / bin_seconds, 3)} for row in rows]}

    @app.get("/api/insights")
    def insight_data(start: str | None = None, end: str | None = None, since: int | None = None, until: int | None = None):
        s, e = range_for(start, end, None, None, since, until)
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
                "annual": insights.annual_projection(a, now, saved.get("abschlag_eur")),
                "billing": insights.billing_year(a, now, saved),
                "reference": insights.household_reference(store.settings())}

    @app.put("/api/budget")
    def save_budget(data: Budget):
        store.set_state("budget", data.model_dump())
        notifier.wakeup.set()
        return {"ok": True}

    @app.get("/api/meter-readings")
    def meter_readings(dates: str):
        zone, now = store.settings()["timezone"], time.time()
        days = []
        for text in dates.split(","):
            try:
                days.append(date.fromisoformat(text.strip()))
            except ValueError:
                raise ValueError("Datum im Format JJJJ-MM-TT erwarten.") from None
        if not 1 <= len(days) <= 31:
            raise ValueError("1 bis 31 Daten je Abfrage.")
        max_gap = store.settings()["max_gap_seconds"]
        result = []
        for day in days:
            at = midnight(day, zone)
            if at > now:
                raise ValueError("Datum liegt in der Zukunft.")
            result.append(dict(insights.meter_reading(store, at, max_gap), date=day.isoformat()))
        return {"timezone": zone, "readings": result, "raw_retention_days": store.settings()["raw_retention_days"]}

    @app.get("/api/checklist")
    def checklist():
        return setup_checklist.checklist(store, notifier, feed, updates, config.demo)

    @app.put("/api/checklist")
    def mute_checklist(data: ChecklistMute):
        store.set_state("checklist_muted", data.muted)
        return setup_checklist.checklist(store, notifier, feed, updates, config.demo)

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

    static_folder = Path(__file__).parent / "static"

    @app.get("/sw.js", include_in_schema=False)
    def service_worker():
        # Mit der App-Version, damit jedes Release einen neuen Worker und damit eine Aktualisierung auslöst.
        source = (static_folder / "sw.js").read_text(encoding="utf-8").replace("__VERSION__", __version__)
        return Response(source, media_type="text/javascript", headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def web_manifest():
        return Response((static_folder / "manifest.webmanifest").read_bytes(), media_type="application/manifest+json",
                        headers={"Cache-Control": "no-cache"})

    app.mount("/", StaticFiles(directory=static_folder, html=True), name="frontend")
    return app


def factory():
    return create_app()

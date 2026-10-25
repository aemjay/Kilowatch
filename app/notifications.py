"""Lokale Alarmregeln, persistente Warteschlange und konfigurierbare Zustellung."""
import asyncio
from datetime import datetime
from email.message import EmailMessage
import re
import shutil
import smtplib
import ssl
import threading
import time
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .analytics import Analytics, local_day, midnight
from .network import local_request, local_url
from .i18n import UserError, translate


class NotificationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    enabled: bool = False
    email_enabled: bool = False
    smtp_host: str = Field(default="", max_length=253)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_security: str = "starttls"
    smtp_user: str = Field(default="", max_length=200)
    smtp_from: str = Field(default="", max_length=254)
    email_to: list[str] = Field(default_factory=list, max_length=5)
    signal_enabled: bool = False
    signal_url: str = Field(default="", max_length=500)
    signal_number: str = Field(default="", max_length=20)
    signal_to: list[str] = Field(default_factory=list, max_length=5)
    quiet_enabled: bool = False
    quiet_start: str = "22:00"
    quiet_end: str = "07:00"
    recovery: bool = True
    cooldown_minutes: int = Field(default=60, ge=5, le=1440)
    offline_enabled: bool = True
    offline_seconds: int = Field(default=120, ge=30, le=3600)
    load_enabled: bool = False
    load_w: int = Field(default=3000, ge=100, le=1000000)
    load_minutes: int = Field(default=10, ge=1, le=240)
    daily_kwh: float = Field(default=0, ge=0, le=10000)
    budget_enabled: bool = False
    battery_enabled: bool = True
    battery_v: float = Field(default=2.7, ge=1, le=5)
    disk_enabled: bool = True
    disk_free_mb: int = Field(default=512, ge=100, le=100000)

    @field_validator("smtp_security")
    @classmethod
    def security(cls, value):
        if value not in ("starttls", "ssl"):
            raise ValueError("SMTP benötigt STARTTLS oder direktes TLS.")
        return value

    @field_validator("smtp_host", "smtp_user", "smtp_from")
    @classmethod
    def no_controls(cls, value):
        if any(ord(c) < 32 for c in value) or any(c in value for c in "\r\n"):
            raise ValueError("Steuerzeichen sind nicht erlaubt.")
        return value.strip()

    @field_validator("email_to")
    @classmethod
    def emails(cls, values):
        if any(not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", v) for v in values):
            raise ValueError("Gültige E-Mail-Adressen ohne Anzeigenamen angeben.")
        return list(dict.fromkeys(values))

    @field_validator("signal_number")
    @classmethod
    def number(cls, value):
        if value and not re.fullmatch(r"\+[1-9][0-9]{6,14}", value):
            raise ValueError("Signal-Nummer im internationalen Format mit + angeben.")
        return value

    @field_validator("signal_to")
    @classmethod
    def recipients(cls, values):
        if any(not re.fullmatch(r"\+[1-9][0-9]{6,14}", v) for v in values):
            raise ValueError("Signal-Empfänger im internationalen Rufnummernformat angeben.")
        return list(dict.fromkeys(values))

    @field_validator("signal_url")
    @classmethod
    def gateway(cls, value):
        if value:
            local_url(value)
        return value.rstrip("/")

    @field_validator("quiet_start", "quiet_end")
    @classmethod
    def clock(cls, value):
        if not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value):
            raise ValueError("Uhrzeit als HH:MM angeben.")
        return value


def check_channel(config, channel):
    if channel == "email":
        if not config.smtp_host or any(c in config.smtp_host for c in "/\\:@?# "):
            raise ValueError("SMTP-Hostname ohne Protokoll oder Port angeben.")
        NotificationSettings.emails([config.smtp_from])
        if not config.email_to:
            raise ValueError("Mindestens einen E-Mail-Empfänger angeben.")
    elif channel == "signal":
        if not config.signal_url or not config.signal_number or not config.signal_to:
            raise ValueError("Signal-Gateway, gekoppelte Absendernummer und Empfänger fehlen.")
        local_url(config.signal_url)
    else:
        raise ValueError("Kanal muss email oder signal sein.")


def quiet_now(config, now, zone):
    if not config.quiet_enabled or config.quiet_start == config.quiet_end:
        return False
    current = datetime.fromtimestamp(now, ZoneInfo(zone)).strftime("%H:%M")
    if config.quiet_start < config.quiet_end:
        return config.quiet_start <= current < config.quiet_end
    return current >= config.quiet_start or current < config.quiet_end


def send_email(config, password, subject, body):
    check_channel(config, "email")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.smtp_from
    message["To"] = ", ".join(config.email_to)
    message.set_content(body)
    context = ssl.create_default_context()
    try:
        if config.smtp_security == "ssl":
            connection = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=20, context=context)
        else:
            connection = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=20)
        with connection as smtp:
            smtp.ehlo()
            if config.smtp_security == "starttls":
                smtp.starttls(context=context)
                smtp.ehlo()
            if config.smtp_user:
                smtp.login(config.smtp_user, password)
            smtp.send_message(message)
    except smtplib.SMTPAuthenticationError:
        raise ValueError("SMTP-Anmeldung abgelehnt. Zugangsdaten oder App-Passwort prüfen.") from None
    except ssl.SSLError:
        raise ValueError("SMTP-TLS-Prüfung fehlgeschlagen. Servername und Zertifikat prüfen.") from None
    except (OSError, smtplib.SMTPException):
        raise ValueError("E-Mail-Zustellung fehlgeschlagen. SMTP-Server, TLS und Empfänger prüfen.") from None


async def send_signal(config, token, subject, body):
    check_channel(config, "signal")
    status, _, _ = await local_request(config.signal_url, "/v2/send", "POST",
                                      {"number": config.signal_number, "recipients": config.signal_to,
                                       "message": subject + "\n\n" + body}, token)
    if status not in (200, 201, 202, 204):
        raise UserError("Signal-Zustellung fehlgeschlagen (HTTP {status}). Kopplung und Gateway prüfen.", status=status)


class Notifications:
    def __init__(self, store, vault, collector, demo=False):
        self.store, self.vault, self.collector = store, vault, collector
        self.demo = demo
        self.started = time.time()
        self.high_since = None
        self.wakeup = asyncio.Event()
        self.rule_state = store.state("notification_rules", {})
        self.last_error = ""
        # Regelzustand wird von evaluate() im Thread und von save() im Event-Loop geändert.
        self.lock = threading.RLock()
        with store.transaction():
            store.conn.execute("""CREATE TABLE IF NOT EXISTS notifications(
                id INTEGER PRIMARY KEY,rule_key TEXT,kind TEXT,channel TEXT,
                subject TEXT,body TEXT,status TEXT,attempts INTEGER DEFAULT 0,
                created REAL,next_try REAL,last_error TEXT DEFAULT '')""")

    def config(self):
        return NotificationSettings(**self.store.state("notification_settings", {}))

    def validate(self, config):
        if not config.enabled:
            return
        if not self.channels(config):
            raise ValueError("Mindestens einen Benachrichtigungskanal aktivieren.")
        for channel in self.channels(config):
            check_channel(config, channel)

    def save(self, config):
        with self.lock:
            self._save(config)

    def _save(self, config):
        old = self.config()
        self.validate(config)
        self.store.set_state("notification_settings", config.model_dump())
        destinations_changed = any(getattr(old, key) != getattr(config, key) for key in
                                   ("email_enabled", "email_to", "smtp_from", "signal_enabled", "signal_url", "signal_number", "signal_to"))
        if not config.enabled or destinations_changed:
            with self.store.transaction():
                self.store.conn.execute("UPDATE notifications SET status='cancelled' WHERE status='pending'")
            # Reines Speichern oder Testen setzt die Entprellung nicht zurück.
            self.rule_state = {key: {"active": False, "notified": [], "last_alert": value["last_alert"]}
                               for key, value in self.rule_state.items()}
        if old.load_w != config.load_w or old.load_minutes != config.load_minutes or not config.load_enabled:
            self.high_since = None
        for key in list(self.rule_state):
            rule_enabled = {"offline": config.offline_enabled, "load": config.load_enabled,
                            "battery": config.battery_enabled, "disk": config.disk_enabled}.get(key, bool(config.daily_kwh))
            if key.startswith("budget:"):
                rule_enabled = config.budget_enabled
            if not rule_enabled:
                with self.store.transaction():
                    self.store.conn.execute("UPDATE notifications SET status='cancelled' WHERE rule_key=? AND status='pending'", (key,))
                self.rule_state.pop(key, None)
        self.store.set_state("notification_rules", self.rule_state)
        self.wakeup.set()

    def channels(self, config):
        return [name for name, enabled in [("email", config.email_enabled), ("signal", config.signal_enabled)] if enabled]

    def enqueue(self, key, kind, channel, subject, body, now):
        with self.store.transaction():
            cursor = self.store.conn.execute("INSERT INTO notifications(rule_key,kind,channel,subject,body,status,created,next_try) VALUES(?,?,?,?,?,'pending',?,?)",
                                            (key, kind, channel, subject, body, now, now))
            return cursor.lastrowid

    def text(self, template, **params):
        """Übersetzt Betreff und Text in die eingestellte Sprache; Zahlen mit passendem Dezimalzeichen."""
        settings = self.store.settings()
        language = settings.get("language") or "de"
        point = "." if language == "en" else ","
        # Zahlen als (Wert, Nachkommastellen), damit das Dezimalzeichen zur Sprache passt.
        params = {k: format(v[0], f".{v[1]}f").replace(".", point) if isinstance(v, tuple) else v for k, v in params.items()}
        return translate(template, language, settings.get("currency", "EUR"), **params)

    def rule(self, key, active, title, body, now, config, enabled=True, recovery=True, params=None):
        previous = self.rule_state.get(key, {"active": False, "notified": [], "last_alert": 0})
        if not enabled:
            with self.store.transaction():
                self.store.conn.execute("UPDATE notifications SET status='cancelled' WHERE rule_key=? AND status='pending'", (key,))
            self.rule_state.pop(key, None)
            return
        if active == previous["active"]:
            return
        channels = self.channels(config)
        with self.store.transaction():
            self.store.conn.execute("UPDATE notifications SET status='cancelled' WHERE rule_key=? AND status='pending'", (key,))
        if active:
            if not previous["last_alert"] or now - previous["last_alert"] >= config.cooldown_minutes * 60:
                for channel in channels:
                    self.enqueue(key, "alert", channel, "Kilowatch · " + self.text(title), self.text(body, **(params or {})), now)
                previous["last_alert"] = now
            previous["notified"] = []
        elif recovery and config.recovery:
            for channel in previous["notified"]:
                if channel in channels:
                    self.enqueue(key, "recovery", channel, "Kilowatch · " + self.text("Wieder in Ordnung"), self.text("{title} ist wieder im normalen Bereich.", title=self.text(title)), now)
            previous["notified"] = []
        previous["active"] = active
        self.rule_state[key] = previous

    def evaluate(self, now=None):
        with self.lock:
            self._evaluate(now)

    def _evaluate(self, now=None):
        now = time.time() if now is None else now
        config = self.config()
        if not config.enabled or self.demo:
            return
        settings = self.store.settings()
        latest = self.store.latest()
        ready = settings["enabled"] and settings["bridge_host"] and settings["bridge_user"] and self.vault.get("bridge_password")
        if not ready:
            return
        last = latest["ts"] if latest else self.started
        offline = now - max(last, self.started) >= config.offline_seconds
        # Eine Neustart-Wartezeit ist noch kein Nachweis der Erholung.
        offline |= self.rule_state.get("offline", {}).get("active", False) and (latest is None or latest["ts"] < self.started)
        self.rule("offline", offline, "Keine frischen Zählerdaten", "Seit mindestens {seconds} Sekunden fehlen neue Messwerte. Kilowatch versucht die Verbindung weiterherzustellen.", now, config, config.offline_enabled,
                  params={"seconds": config.offline_seconds})
        if latest and now - latest["ts"] <= 30 and latest["power_w"] is not None:
            watts = latest["power_w"]
            old_load = self.rule_state.get("load", {}).get("active", False)
            if watts >= config.load_w:
                self.high_since = self.high_since if self.high_since is not None else now
            elif not old_load or watts < config.load_w * .9:
                self.high_since = None
            active = ((old_load and watts >= config.load_w * .9) or
                      (self.high_since is not None and now - self.high_since >= config.load_minutes * 60))
            self.rule("load", active, "Hohe Dauerlast", "Netzleistung seit mindestens {minutes} Minuten über {limit} W. Aktuell {watts} W. Eine Gerätezuordnung ist daraus nicht möglich.", now, config, config.load_enabled,
                      params={"minutes": config.load_minutes, "limit": config.load_w, "watts": (watts, 0)})
        else:
            # Eine Messlücke beweist keine durchgehende hohe Last.
            self.high_since = None
        diagnostics = self.collector.diagnostics
        battery = diagnostics.get("battery_v")
        if battery is not None and now - diagnostics.get("checked_at", 0) <= 300:
            old = self.rule_state.get("battery", {}).get("active", False)
            low = battery < config.battery_v + (.15 if old else 0)
            self.rule("battery", low, "Batteriespannung niedrig", "Der Pulse meldet {volts} V. Batterien und Empfang am Lesekopf prüfen. Die Schwelle ist ein konfigurierbarer Hinweis.", now, config, config.battery_enabled,
                      params={"volts": (battery, 2)})
        free_mb = shutil.disk_usage(self.store.directory).free / 1024 / 1024
        old_disk = self.rule_state.get("disk", {}).get("active", False)
        disk_low = free_mb < config.disk_free_mb * (1.1 if old_disk else 1)
        self.rule("disk", disk_low, "NAS-Speicher knapp", "Am Datenpfad sind noch etwa {free} MiB frei. Aufbewahrung und Sicherungen prüfen.", now, config, config.disk_enabled,
                  params={"free": (free_mb, 0)})
        if config.daily_kwh:
            day = local_day(now, settings["timezone"])
            used = Analytics(self.store).summary(midnight(day, settings["timezone"]), now)["import_kwh"]
            self.rule("daily:" + day.isoformat(), used is not None and used >= config.daily_kwh,
                      "Tagesbudget erreicht", "Heute sind mindestens {used} kWh Netzbezug erfasst. Eingestellter Hinweiswert: {limit} kWh. Fehlende Daten können zusätzlichen Verbrauch enthalten.", now, config, recovery=False,
                      params={"used": (used or 0, 2), "limit": (config.daily_kwh, 2)})
        budget = self.store.state("budget", {}).get("monthly_eur")
        month = local_day(now, settings["timezone"]).strftime("%Y-%m")
        if config.budget_enabled and budget:
            first = local_day(now, settings["timezone"]).replace(day=1)
            spent = Analytics(self.store).summary(midnight(first, settings["timezone"]), now)["known_cost_eur"]
            self.rule("budget:" + month, spent is not None and spent >= budget, "Monatsbudget erreicht",
                      "In diesem Monat sind bereits mindestens {spent} € erfasst. Eingestelltes Budget: {budget} €. Fehlende Daten oder Preise können weitere Kosten enthalten.",
                      now, config, recovery=False, params={"spent": (spent or 0, 2), "budget": (budget, 2)})
        for key in list(self.rule_state):
            if key.startswith("daily:") and key != "daily:" + local_day(now, settings["timezone"]).isoformat():
                self.rule(key, False, "", "", now, config, enabled=False)
            if key.startswith("budget:") and (key != "budget:" + month or not config.budget_enabled or not budget):
                self.rule(key, False, "", "", now, config, enabled=False)
        self.store.set_state("notification_rules", self.rule_state)

    async def send(self, channel, subject, body, config):
        if channel == "email":
            await asyncio.to_thread(send_email, config, self.vault.get("smtp_password"), subject, body)
        elif channel == "signal":
            await send_signal(config, self.vault.get("signal_token"), subject, body)
        else:
            raise ValueError("Unbekannter Benachrichtigungskanal.")

    async def deliver(self, row, config, now):
        try:
            await self.send(row["channel"], row["subject"], row["body"], config)
        except Exception as exc:
            error = str(exc) if isinstance(exc, ValueError) else "Zustellung fehlgeschlagen (" + type(exc).__name__ + ")."
            count = row["attempts"] + 1
            with self.store.transaction():
                self.store.conn.execute("UPDATE notifications SET attempts=?,status=?,last_error=?,next_try=? WHERE id=?",
                                        (count, "failed" if count >= 5 or row["kind"] == "test" else "pending", error,
                                         now + min(3600, 60 * 2 ** (count - 1)), row["id"]))
            self.last_error = error
            if row["kind"] == "test":
                raise ValueError(error) from None
            return False
        with self.store.transaction():
            self.store.conn.execute("UPDATE notifications SET status='sent',attempts=attempts+1,last_error='' WHERE id=?", (row["id"],))
        if row["kind"] == "alert" and row["rule_key"] in self.rule_state:
            state = self.rule_state[row["rule_key"]]
            state["notified"] = list(set(state["notified"]) | {row["channel"]})
            self.store.set_state("notification_rules", self.rule_state)
        self.last_error = ""
        return True

    async def dispatch(self, now=None):
        now = time.time() if now is None else now
        config = self.config()
        if not config.enabled or self.demo or not self.store.settings()["enabled"] or quiet_now(config, now, self.store.settings()["timezone"]):
            return
        for row in self.store.rows("SELECT * FROM notifications WHERE status='pending' AND kind<>'test' AND next_try<=? ORDER BY id LIMIT 5", (now,)):
            if row["channel"] not in self.channels(config) or now - row["created"] > 86400:
                with self.store.transaction():
                    self.store.conn.execute("UPDATE notifications SET status='cancelled' WHERE id=?", (row["id"],))
                continue
            await self.deliver(row, config, now)

    async def test(self, channel):
        if self.demo:
            raise ValueError("Im Demo-Modus werden keine Nachrichten versendet.")
        config = self.config()
        check_channel(config, channel)
        now = time.time()
        recent = self.store.rows("SELECT id FROM notifications WHERE kind='test' AND channel=? AND created>?", (channel, now - 30))
        if recent:
            raise ValueError("Bitte 30 Sekunden zwischen Testnachrichten warten.")
        event_id = self.enqueue("manual-test", "test", channel, "Kilowatch · " + self.text("Testnachricht"),
                                self.text("Die konfigurierte Benachrichtigung funktioniert. Diese Testnachricht enthält keine Messwerte."), now)
        row = self.store.rows("SELECT * FROM notifications WHERE id=?", (event_id,))[0]
        await self.deliver(row, config, now)
        return {"ok": True, "id": event_id, "channel": channel}

    async def run(self):
        while True:
            try:
                await asyncio.to_thread(self.evaluate)
                await self.dispatch()
                with self.store.transaction():
                    self.store.conn.execute("DELETE FROM notifications WHERE created<? AND status<>'pending'", (time.time() - 90 * 86400,))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = "Benachrichtigungsdienst: " + type(exc).__name__
            try:
                await asyncio.wait_for(self.wakeup.wait(), timeout=10)
                self.wakeup.clear()
            except asyncio.TimeoutError:
                pass

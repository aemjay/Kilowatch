from contextlib import closing, contextmanager
from dataclasses import asdict
from pathlib import Path
import json
import math
import secrets
import sqlite3
import threading
import time
from .i18n import _


DEFAULTS = {
    "bridge_host": "", "bridge_user": "admin", "node_id": 1,
    "poll_seconds": 5, "enabled": True, "timezone": "Europe/Berlin",
    "max_gap_seconds": 90, "max_power_w": 100000,
    "raw_retention_days": 90, "minute_retention_days": 1095,
    "high_load_w": 3000, "name": "Mein Zuhause",
    "language": "", "currency": "EUR", "grid_country": "",
    "household_persons": 0, "household_type": "apartment", "household_hot_water": False,
}


def _spot_prices(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS spot_prices(start INTEGER PRIMARY KEY,end INTEGER NOT NULL,eur_mwh REAL NOT NULL)")


def _grid_intensity(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS grid_intensity(country TEXT NOT NULL,start INTEGER NOT NULL,g_kwh REAL,"
                 "renewable_share REAL,PRIMARY KEY(country,start))")


def _api_tokens(conn):
    # Nur der SHA-256-Hash des Tokens; der Klartext wird einmalig bei der Erstellung angezeigt.
    conn.execute("CREATE TABLE IF NOT EXISTS api_tokens(id INTEGER PRIMARY KEY,name TEXT NOT NULL,hash TEXT NOT NULL UNIQUE,"
                 "role TEXT NOT NULL,created REAL NOT NULL,last_used REAL)")


# Geordnete Schemaänderungen. Nur hinzufügen (Tabellen, Spalten, Indizes); Entfernen
# frühestens in der nächsten Hauptversion. Jede Stufe läuft in einer eigenen Transaktion.
MIGRATIONS = [
    (2, _spot_prices),
    (3, _grid_intensity),
    (4, _api_tokens),
]
SCHEMA_VERSION = max([1] + [target for target, _ in MIGRATIONS])


class Store:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "kilowatch.sqlite3"
        self.lock = threading.RLock()
        self._transaction_depth = 0
        self.conn = sqlite3.connect(self.path, check_same_thread=False, timeout=15)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.execute("PRAGMA busy_timeout=15000")
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError(f"Datenbank hat Schema {version}, diese Kilowatch-Version kennt nur bis {SCHEMA_VERSION}. "
                               "Neuere Kilowatch-Version verwenden oder die Sicherung backups/pre-migration-* "
                               "mit dem dazu passenden älteren Image zurückspielen.")
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS samples(
                ts REAL PRIMARY KEY,meter_id TEXT,power_w REAL,import_kwh REAL,
                export_kwh REAL,protocol TEXT,quality TEXT);
            CREATE TABLE IF NOT EXISTS buckets(
                resolution INTEGER,ts INTEGER,import_kwh REAL NOT NULL DEFAULT 0,
                export_kwh REAL NOT NULL DEFAULT 0,import_s REAL NOT NULL DEFAULT 0,
                export_s REAL NOT NULL DEFAULT 0,estimated_import REAL NOT NULL DEFAULT 0,
                estimated_export REAL NOT NULL DEFAULT 0,power_ws REAL NOT NULL DEFAULT 0,
                power_s REAL NOT NULL DEFAULT 0,min_w REAL,max_w REAL,high_s REAL NOT NULL DEFAULT 0,
                PRIMARY KEY(resolution,ts));
            CREATE TABLE IF NOT EXISTS gaps(
                id INTEGER PRIMARY KEY,start REAL NOT NULL,end REAL NOT NULL,
                import_kwh REAL,export_kwh REAL,reason TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS gap_time ON gaps(start,end);
            CREATE TABLE IF NOT EXISTS issues(
                id INTEGER PRIMARY KEY,ts REAL,code TEXT,message TEXT);
            CREATE TABLE IF NOT EXISTS tariffs(
                start_date TEXT PRIMARY KEY,name TEXT,mode TEXT,
                eur_kwh REAL,base_month REAL,feedin_eur_kwh REAL);
            CREATE TABLE IF NOT EXISTS prices(
                start INTEGER PRIMARY KEY,end INTEGER NOT NULL,eur_kwh REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY,start REAL,end REAL,title TEXT,note TEXT);
        """)
        if version == 0:
            # Neue Datenbank: Grundschema ist Version 1, danach alle Migrationen.
            self.conn.execute("PRAGMA user_version=1")
            version = 1
        elif version < SCHEMA_VERSION:
            # Vor jeder Schemaänderung eine geprüfte Sicherung, die nicht rotiert wird.
            folder = self.directory / "backups"
            folder.mkdir(exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
            self.backup(folder / f"pre-migration-v{version}-to-v{SCHEMA_VERSION}-{stamp}.sqlite3")
        try:
            self.migrate(version)
        except BaseException:
            self.conn.close()
            raise
        with self.transaction():
            for key, val in DEFAULTS.items():
                self.conn.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (key, json.dumps(val)))

    def migrate(self, version):
        for target, step in MIGRATIONS:
            if target <= version:
                continue
            with self.transaction():
                step(self.conn)
                self.conn.execute(f"PRAGMA user_version={int(target)}")
            version = target

    @contextmanager
    def transaction(self):
        with self.lock:
            outer = self._transaction_depth == 0
            if outer:
                self.conn.execute("BEGIN")
            self._transaction_depth += 1
            try:
                yield
            except BaseException:
                if outer:
                    self.conn.rollback()
                raise
            else:
                if outer:
                    self.conn.commit()
            finally:
                self._transaction_depth -= 1

    def rows(self, query, args=()):
        with self.lock:
            return [dict(row) for row in self.conn.execute(query, args)]

    def settings(self):
        return {r["key"]: json.loads(r["value"]) for r in self.rows("SELECT * FROM settings")}

    def update_settings(self, data):
        with self.transaction():
            for key, value in data.items():
                if key in DEFAULTS:
                    self.conn.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, json.dumps(value)))

    def state(self, key, fallback=None):
        rows = self.rows("SELECT value FROM state WHERE key=?", (key,))
        return json.loads(rows[0]["value"]) if rows else fallback

    def set_state(self, key, value):
        with self.transaction():
            self.conn.execute("INSERT OR REPLACE INTO state VALUES(?,?)", (key, json.dumps(value)))

    def issue(self, code, message, ts=None):
        with self.transaction():
            self.conn.execute("INSERT INTO issues(ts,code,message) VALUES(?,?,?)", (ts or time.time(), code, message))

    def latest(self):
        return self.state("last_sample")

    def ingest(self, reading, ts=None):
        ts = time.time() if ts is None else float(ts)
        settings = self.settings()
        if not math.isfinite(ts):
            raise ValueError("Ungültiger Messzeitpunkt.")
        if reading.power_w is not None and (not math.isfinite(reading.power_w) or abs(reading.power_w) > settings["max_power_w"]):
            raise ValueError("Leistung außerhalb der konfigurierten Plausibilitätsgrenze.")
        for number in [reading.import_kwh, reading.export_kwh]:
            if number is not None and (not math.isfinite(number) or number < 0):
                raise ValueError("Ungültiger Zählerstand.")
        current = dict(asdict(reading), ts=ts)
        current.pop("obis", None)
        with self.transaction():
            previous = self.latest()
            if previous and ts <= previous["ts"]:
                return False
            quality = "baseline"
            if previous:
                dt = ts - previous["ts"]
                changed = previous["meter_id"] and current["meter_id"] and previous["meter_id"] != current["meter_id"]
                if changed:
                    self.issue("meter_change", "Zählerkennung geändert; neue Ausgangsbasis gesetzt.", ts)
                energies, estimates, reasons = {}, {}, []
                for field in ("import_kwh", "export_kwh"):
                    old, new = previous[field], current[field]
                    energy = None
                    estimated = False
                    if not changed and old is not None and new is not None:
                        delta = new - old
                        maximum = settings["max_power_w"] * dt / 3600000 + 0.02
                        if delta < -1e-8:
                            reasons.append(_("Zählerstand gefallen / neue Ausgangsbasis"))
                            self.issue("counter_reset", "Zählerstand gefallen; kein negativer Verbrauch gebucht.", ts)
                        elif delta > maximum:
                            reasons.append(_("Unplausibler Zählersprung"))
                            self.issue("counter_jump", "Unplausibler Zählersprung; Intervall nicht gebucht.", ts)
                        else:
                            energy = max(0.0, delta)
                    elif not changed and dt <= settings["max_gap_seconds"]:
                        p0, p1 = previous["power_w"], current["power_w"]
                        if p0 is not None and p1 is not None:
                            # Lineare Integration mit exaktem Nulldurchgang.
                            direction = 1 if field == "import_kwh" else -1
                            a, b = p0 * direction, p1 * direction
                            if a >= 0 and b >= 0:
                                energy = (a + b) / 2 * dt / 3600000
                            elif a <= 0 and b <= 0:
                                energy = 0.0
                            else:
                                positive = max(a, b)
                                energy = positive * positive / (2 * abs(b - a)) * dt / 3600000
                            estimated = True
                    energies[field] = energy
                    estimates[field] = estimated
                if changed or dt > settings["max_gap_seconds"] or reasons:
                    reason = _("Zählerwechsel") if changed else "; ".join(sorted(set(reasons))) if reasons else _("Messlücke")
                    self.conn.execute("INSERT INTO gaps(start,end,import_kwh,export_kwh,reason) VALUES(?,?,?,?,?)",
                                      (previous["ts"], ts, energies["import_kwh"], energies["export_kwh"], reason))
                    quality = "gap"
                else:
                    quality = "estimated" if any(estimates.values()) else "meter"
                    p0, p1 = previous["power_w"], current["power_w"]
                    pmean = (p0 + p1) / 2 if p0 is not None and p1 is not None else None
                    for resolution in (60, 900):
                        cursor = previous["ts"]
                        while cursor < ts - 1e-7:
                            bucket = int(cursor // resolution) * resolution
                            end = min(ts, bucket + resolution)
                            duration = end - cursor
                            ratio = duration / dt
                            imp, exp = energies["import_kwh"], energies["export_kwh"]
                            values = (resolution, bucket, (imp or 0) * ratio, (exp or 0) * ratio,
                                      duration if imp is not None else 0, duration if exp is not None else 0,
                                      (imp or 0) * ratio if estimates["import_kwh"] else 0,
                                      (exp or 0) * ratio if estimates["export_kwh"] else 0,
                                      (pmean or 0) * duration, duration if pmean is not None else 0,
                                      min(p0, p1) if pmean is not None else None,
                                      max(p0, p1) if pmean is not None else None,
                                      duration if pmean is not None and pmean >= settings["high_load_w"] else 0)
                            self.conn.execute("""INSERT INTO buckets VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                                ON CONFLICT(resolution,ts) DO UPDATE SET
                                import_kwh=import_kwh+excluded.import_kwh,
                                export_kwh=export_kwh+excluded.export_kwh,
                                import_s=import_s+excluded.import_s,export_s=export_s+excluded.export_s,
                                estimated_import=estimated_import+excluded.estimated_import,
                                estimated_export=estimated_export+excluded.estimated_export,
                                power_ws=power_ws+excluded.power_ws,power_s=power_s+excluded.power_s,
                                min_w=CASE WHEN min_w IS NULL THEN excluded.min_w WHEN excluded.min_w IS NULL THEN min_w ELSE MIN(min_w,excluded.min_w) END,
                                max_w=CASE WHEN max_w IS NULL THEN excluded.max_w WHEN excluded.max_w IS NULL THEN max_w ELSE MAX(max_w,excluded.max_w) END,
                                high_s=high_s+excluded.high_s""", values)
                            cursor = end
            self.conn.execute("INSERT INTO samples VALUES(?,?,?,?,?,?,?)", (ts, reading.meter_id, reading.power_w,
                              reading.import_kwh, reading.export_kwh, reading.protocol, quality))
            self.conn.execute("INSERT OR REPLACE INTO state VALUES('last_sample',?)", (json.dumps(current),))
        return True

    def sample_rows(self, start, end):
        return self.rows("SELECT ts,power_w FROM samples WHERE ts>=? AND ts<? AND power_w IS NOT NULL ORDER BY ts", (start, end))

    def bucket_rows(self, start, end, resolution=900):
        return self.rows("SELECT * FROM buckets WHERE resolution=? AND ts<? AND ts+?>? ORDER BY ts",
                         (resolution, end, resolution, start))

    def gap_rows(self, start, end):
        return self.rows("SELECT * FROM gaps WHERE start<? AND end>? ORDER BY start", (end, start))

    def backup(self, target=None):
        folder = self.directory / "backups"
        folder.mkdir(exist_ok=True)
        target = Path(target) if target else folder / (time.strftime("kilowatch-%Y%m%d-%H%M%S", time.gmtime()) + ".sqlite3")
        # Eindeutige Zwischendatei: gleichzeitige Sicherungen in derselben Sekunde stören sich nicht.
        temporary = target.with_name(f"{target.stem}.{secrets.token_hex(4)}.tmp")
        # Eigene Leseverbindung: WAL liefert einen konsistenten Stand, ohne die
        # gemeinsame Sperre zu halten. Erfassung und API laufen währenddessen weiter.
        with closing(sqlite3.connect(self.path, timeout=15)) as source, closing(sqlite3.connect(temporary)) as destination:
            source.backup(destination)
            check = destination.execute("PRAGMA integrity_check").fetchone()[0]
            if check != "ok":
                raise RuntimeError("Sicherungsprüfung fehlgeschlagen.")
        temporary.replace(target)
        return target

    def maintenance(self, now=None):
        now = time.time() if now is None else now
        settings = self.settings()
        with self.transaction():
            # 0 = unbegrenzt. Viertelstundenwerte und Lücken werden nie gelöscht.
            if settings["raw_retention_days"]:
                self.conn.execute("DELETE FROM samples WHERE ts<?", (now - settings["raw_retention_days"] * 86400,))
            if settings["minute_retention_days"]:
                self.conn.execute("DELETE FROM buckets WHERE resolution=60 AND ts<?", (now - settings["minute_retention_days"] * 86400,))
            self.conn.execute("DELETE FROM issues WHERE ts<?", (now - 365 * 86400,))
        with self.lock:
            self.conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        if self.state("backup_day") != day:
            self.backup()
            self.set_state("backup_day", day)
        backups = sorted((self.directory / "backups").glob("kilowatch-*.sqlite3"))
        for path in backups[:-7]:
            path.unlink()

    def close(self):
        with self.lock:
            self.conn.close()

"""Gerätemessung per Stoppuhr: Mehrverbrauch des Hauses zwischen Start und Ende.

Gemessen wird am Netzanschluss. Das Ergebnis ist die Bezugszählerdifferenz abzüglich der Nachtgrundlast
der letzten sieben Tage für dieselbe Dauer, keine Geräteerkennung: Alles, was im Zeitraum zusätzlich lief,
zählt mit.
"""
import time

from .analytics import Analytics
from .i18n import _

MAX_SECONDS = 24 * 3600
FRESH_SECONDS = 30
COLUMNS = "id,name,status,start,start_kwh,end,end_kwh,baseline_w,rate_eur_kwh,note"


def fresh_import(store, now):
    """Letzter Messpunkt mit Bezugszählerstand, höchstens 30 Sekunden alt."""
    latest = store.latest()
    if not latest or now - latest["ts"] > FRESH_SECONDS or latest.get("import_kwh") is None:
        raise ValueError("Kein frischer Bezugszählerstand. Erfassung und Bridge prüfen.")
    return latest


def result(row):
    """Abgeleitete Werte einer Messung; laufende und unvollständige ohne Ergebnis."""
    item = dict(row)
    item.update(duration_s=None, total_kwh=None, baseline_kwh=None, extra_kwh=None, mean_w=None, cost_eur=None)
    if row["status"] != "done":
        return item
    duration = row["end"] - row["start"]
    total = row["end_kwh"] - row["start_kwh"]
    baseline = row["baseline_w"] * duration / 3600000 if row["baseline_w"] is not None else None
    extra = max(0.0, total - (baseline or 0))
    item.update(duration_s=duration, total_kwh=total, baseline_kwh=baseline, extra_kwh=extra,
                mean_w=extra * 3600000 / duration if duration > 0 else None,
                cost_eur=extra * row["rate_eur_kwh"] if row["rate_eur_kwh"] is not None else None)
    return item


class Measurements:
    def __init__(self, store):
        self.store = store

    def rows(self, where="", args=()):
        return self.store.rows(f"SELECT {COLUMNS} FROM device_measurements {where}", args)

    def expire(self, now):
        """Nach 24 Stunden wird eine laufende Messung abgebrochen und als unvollständig markiert."""
        with self.store.transaction():
            self.store.conn.execute("UPDATE device_measurements SET status='incomplete',end=start+?,note=? WHERE status='running' AND start<?",
                                    (MAX_SECONDS, _("Nach 24 Stunden automatisch abgebrochen."), now - MAX_SECONDS))

    def overview(self, now=None):
        now = time.time() if now is None else now
        self.expire(now)
        running = self.rows("WHERE status='running'")
        return {"running": running[0] if running else None, "max_seconds": MAX_SECONDS,
                "items": [result(row) for row in self.rows("WHERE status<>'running' ORDER BY start DESC LIMIT 100")]}

    def start(self, now=None):
        now = time.time() if now is None else now
        self.expire(now)
        latest = fresh_import(self.store, now)
        with self.store.transaction():
            if self.rows("WHERE status='running'"):
                raise ValueError("Es läuft bereits eine Messung.")
            self.store.conn.execute("INSERT INTO device_measurements(status,start,start_kwh) VALUES('running',?,?)",
                                    (latest["ts"], latest["import_kwh"]))
        return self.overview(now)

    def stop(self, now=None):
        now = time.time() if now is None else now
        self.expire(now)
        running = self.rows("WHERE status='running'")
        if not running:
            raise ValueError("Es läuft keine Messung.")
        row = running[0]
        latest = fresh_import(self.store, now)
        analytics = Analytics(self.store)
        # Nachtgrundlast der letzten sieben Tage wie in der Analyse (P10, mindestens zwölf Nachtviertelstunden).
        baseline = analytics.patterns(now - 7 * 86400, now)["baseline_w"]
        tariff = analytics.tariff(now)
        if tariff and tariff["mode"] == "dynamic":
            analytics.load_prices(now, now + 1)
        rate = analytics.rate(now, tariff) if tariff else None
        status, note = "done", ""
        if latest["import_kwh"] < row["start_kwh"] or latest["ts"] <= row["start"]:
            status, note = "incomplete", _("Zählerstand gefallen oder Zählerwechsel; Messung nicht auswertbar.")
        with self.store.transaction():
            self.store.conn.execute("UPDATE device_measurements SET status=?,end=?,end_kwh=?,baseline_w=?,rate_eur_kwh=?,note=? WHERE id=?",
                                    (status, latest["ts"], latest["import_kwh"], baseline, rate, note, row["id"]))
        return result(self.rows("WHERE id=?", (row["id"],))[0])

    def rename(self, measurement_id, name):
        with self.store.transaction():
            if not self.store.conn.execute("UPDATE device_measurements SET name=? WHERE id=?", (name, measurement_id)).rowcount:
                raise LookupError()

    def delete(self, measurement_id):
        with self.store.transaction():
            if not self.store.conn.execute("DELETE FROM device_measurements WHERE id=?", (measurement_id,)).rowcount:
                raise LookupError()

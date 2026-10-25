"""Getrennter, deterministischer Beispieldatenbestand; niemals Produktivdaten."""
from datetime import datetime
import math
import time
from zoneinfo import ZoneInfo

from .decoder import Reading


def power(ts):
    local = datetime.fromtimestamp(ts, ZoneInfo("Europe/Berlin"))
    h = local.hour + local.minute / 60
    baseline = 138 + 20 * math.sin(ts / 900)
    morning = 1550 * math.exp(-((h - 7.4) / .6) ** 2)
    evening = 2250 * math.exp(-((h - 19.1) / .8) ** 2)
    daytime = 190 * math.exp(-((h - 13) / 4) ** 2)
    return max(50, baseline + morning + evening + daytime + 95 * math.sin(ts / 313) ** 6)


def seed(store, now=None):
    if store.latest():
        return
    now = now or time.time()
    store.update_settings({"max_gap_seconds": 1000, "name": "Beispielhaushalt"})
    with store.transaction():
        store.conn.execute("INSERT OR REPLACE INTO tariffs VALUES(?,?,?,?,?,?)", ("2020-01-01", "Beispieltarif", "fixed", .32, 12.9, .08))
    start = int((now - 35 * 86400) // 900) * 900
    energy = 12000.0
    for ts in range(start, int(now // 900) * 900 + 1, 900):
        watts = power(ts)
        energy += watts * 900 / 3600000
        store.ingest(Reading(watts, energy, 0.0, "DEMO", "Beispieldaten"), ts)
    store.update_settings({"max_gap_seconds": 90})
    store.set_state("last_obis", {"16.7.0": {"value": power(now), "unit": "W"}})


def live_reading(store):
    previous = store.latest()
    now = time.time()
    dt = min(90, now - previous["ts"]) if previous else 0
    watts = power(now)
    energy = (previous["import_kwh"] if previous else 12000) + watts * dt / 3600000
    return Reading(watts, energy, 0, "DEMO", "Beispieldaten")

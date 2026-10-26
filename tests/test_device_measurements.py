"""Gerätemessung per Stoppuhr."""
import time

from app.analytics import midnight
from app.decoder import Reading
from app.measure import Measurements, result


def reading(store, ts, kwh, watts=500):
    store.ingest(Reading(watts, kwh, 0, "SYNTHETIC"), ts)


def test_measurement_subtracts_night_baseline_and_prices_current_rate(store):
    with store.transaction():
        store.conn.execute("INSERT INTO tariffs VALUES('2020-01-01','T','fixed',.4,10,0)")
    # Sieben Nächte mit 200 W Grundlast als Viertelstundenwerte (wie der Demo-Bestand ohne Lücken).
    store.update_settings({"max_gap_seconds": 1000})
    now = midnight("2026-10-26", "Europe/Berlin") + 20 * 3600
    kwh = 1000.0
    for ts in range(int(now - 7 * 86400) // 900 * 900, int(now - 3600), 900):
        kwh += 200 * 900 / 3600000
        reading(store, ts, kwh, 200)
    m = Measurements(store)
    reading(store, now - 3600, kwh + .01)
    m.start(now - 3590)
    running = m.overview(now - 3590)["running"]
    assert running["start"] == now - 3600 and abs(running["start_kwh"] - (kwh + .01)) < 1e-9
    # Zweite gleichzeitige Messung geht nicht.
    try:
        m.start(now - 3590)
        raise AssertionError("second start allowed")
    except ValueError:
        pass
    reading(store, now, kwh + .01 + 1.2)  # 1,2 kWh in einer Stunde
    done = m.stop(now + 5)
    assert done["status"] == "done" and done["duration_s"] == 3600
    assert abs(done["baseline_w"] - 200) < 1e-6
    assert abs(done["total_kwh"] - 1.2) < 1e-9 and abs(done["extra_kwh"] - 1.0) < 1e-9
    assert abs(done["mean_w"] - 1000) < 1e-6 and abs(done["cost_eur"] - .4) < 1e-9
    m.rename(done["id"], "Waschmaschine")
    assert m.overview(now)["items"][0]["name"] == "Waschmaschine"
    m.delete(done["id"])
    assert m.overview(now)["items"] == []


def test_without_baseline_no_deduction_and_24h_abort(store):
    now = time.time()
    reading(store, now - 5, 50)
    m = Measurements(store)
    m.start(now)
    reading(store, now + 1800, 50.5)
    done = m.stop(now + 1800)
    assert done["baseline_w"] is None and done["baseline_kwh"] is None and abs(done["extra_kwh"] - .5) < 1e-9
    assert done["cost_eur"] is None  # kein Tarif
    reading(store, now + 1900, 50.6)
    m.start(now + 1900)
    overview = m.overview(now + 1900 + 86401)
    assert overview["running"] is None
    expired = overview["items"][0]
    assert expired["status"] == "incomplete" and expired["end"] == expired["start"] + 86400 and expired["extra_kwh"] is None


def test_stale_reading_and_meter_reset(store):
    now = time.time()
    m = Measurements(store)
    try:
        m.start(now)
        raise AssertionError("start without reading")
    except ValueError:
        pass
    reading(store, now, 80)
    m.start(now)
    reading(store, now + 60, 5)  # Rücksprung
    assert m.stop(now + 60)["status"] == "incomplete"
    assert result({"status": "running"})["extra_kwh"] is None


def test_api(authenticated):
    db = authenticated.app_store
    now = time.time()
    db.ingest(Reading(500, 10, 0, "SYNTHETIC"), now - 2)
    assert authenticated.post("/api/device-measurements/start").status_code == 200
    assert authenticated.post("/api/device-measurements/start").status_code == 400
    assert authenticated.get("/api/device-measurements").json()["running"]["start_kwh"] == 10
    db.ingest(Reading(500, 10.1, 0, "SYNTHETIC"), now - 1)
    stopped = authenticated.post("/api/device-measurements/stop").json()
    assert stopped["status"] == "done"
    assert authenticated.put(f"/api/device-measurements/{stopped['id']}", json={"name": "Föhn"}).status_code == 200
    assert authenticated.put("/api/device-measurements/999", json={"name": "x"}).status_code == 404
    assert authenticated.delete(f"/api/device-measurements/{stopped['id']}").status_code == 200
    assert authenticated.post("/api/device-measurements/stop").status_code == 400

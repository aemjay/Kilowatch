"""Kostenrate der laufenden Viertelstunde und Preisampel für dynamische Tarife."""
import time

from app.analytics import Analytics, midnight
from app.decoder import Reading
from app import insights

ZONE = "Europe/Berlin"


def tariff(store, mode="fixed", rate=.3, feedin=.08, day="2020-01-01"):
    with store.transaction():
        store.conn.execute("INSERT OR REPLACE INTO tariffs VALUES(?,?,?,?,?,?)", (day, "T", mode, rate, 10, feedin))


def prices(store, start, values, step=900):
    with store.transaction():
        for index, value in enumerate(values):
            store.conn.execute("INSERT INTO prices VALUES(?,?,?)", (start + index * step, start + (index + 1) * step, value))


def test_live_cost_without_tariff_and_with_fixed_price(store):
    now = midnight("2026-10-26", ZONE) + 3600
    result = insights.live_cost(Analytics(store), now, 2000)
    assert result["tariff"] is False and result["eur_per_hour"] is None
    tariff(store, rate=.3, feedin=.08)
    result = insights.live_cost(Analytics(store), now, 2000)
    assert result["direction"] == "import" and abs(result["eur_per_hour"] - .6) < 1e-9 and result["rate_eur_kwh"] == .3
    # Einspeisung: Erlös mit Vergütung; ohne Vergütung keine Zahl.
    result = insights.live_cost(Analytics(store), now, -1500)
    assert result["direction"] == "export" and abs(result["eur_per_hour"] - .12) < 1e-9
    tariff(store, feedin=0)
    result = insights.live_cost(Analytics(store), now, -1500)
    assert result["direction"] == "export" and result["eur_per_hour"] is None and result["feedin_eur_kwh"] is None
    # Ohne frische Messung nur der Preis.
    result = insights.live_cost(Analytics(store), now, None)
    assert result["eur_per_hour"] is None and result["rate_eur_kwh"] == .3


def test_live_cost_uses_dual_and_dynamic_price_of_current_quarter(store):
    with store.transaction():
        store.conn.execute("INSERT INTO tariffs VALUES('2020-01-01','HT/NT','dual',.4,10,0)")
    store.set_state("tariff_schedules", {"2020-01-01": {"low_eur_kwh": .2, "low_start": "22:00", "low_end": "06:00", "weekend_low": False}})
    day = midnight("2026-10-27", ZONE)
    assert insights.live_cost(Analytics(store), day + 3 * 3600, 1000)["rate_eur_kwh"] == .2
    assert insights.live_cost(Analytics(store), day + 12 * 3600, 1000)["rate_eur_kwh"] == .4
    tariff(store, mode="dynamic", rate=0, day="2026-10-27")
    prices(store, day, [.1, .5])
    assert insights.live_cost(Analytics(store), day + 1000, 1000)["rate_eur_kwh"] == .5
    missing = insights.live_cost(Analytics(store), day + 5000, 1000)
    assert missing["rate_eur_kwh"] is None and missing["eur_per_hour"] is None


def test_cheapest_window_needs_contiguous_future_quarters():
    rows = [{"start": i * 900, "end": (i + 1) * 900, "eur_kwh": v} for i, v in enumerate([.1, .1, .3, .2, .2, .9])]
    assert insights.cheapest_window(rows, 0, 2) == {"start": 0, "end": 1800, "average_eur_kwh": .1}
    # Vergangenes zählt nicht; bei Gleichstand gewinnt das frühere Fenster.
    assert insights.cheapest_window(rows, 900, 2)["start"] == 900
    assert insights.cheapest_window(rows, 1800, 2)["start"] == 2700
    # Eine Preislücke unterbricht das Fenster.
    gap = rows[:2] + rows[3:]
    assert insights.cheapest_window(gap, 900, 2)["start"] == 2700
    assert insights.cheapest_window(rows, 0, 8) is None


def test_price_outlook_today_tomorrow_and_dst(store):
    tariff(store, mode="dynamic", rate=0)
    # 25.10.2026 hat 100 Viertelstunden; Preise nur für heute.
    day = midnight("2026-10-25", ZONE)
    values = [.3] * 100
    values[40:48] = [.1] * 8
    prices(store, day, values)
    result = insights.price_outlook(Analytics(store), day + 3600, 2)
    assert result["dynamic"] and len(result["intervals"]) == 100 and not result["tomorrow_available"]
    assert result["cheapest"] == {"start": day + 40 * 900, "end": day + 48 * 900, "average_eur_kwh": .1}
    assert result["low_eur_kwh"] == .1 and result["high_eur_kwh"] == .3
    # Stundenpreise für morgen werden auf Viertelstunden verteilt.
    prices(store, midnight("2026-10-26", ZONE), [.2] * 24, step=3600)
    result = insights.price_outlook(Analytics(store), day + 3600, 4)
    assert result["tomorrow_available"] and len(result["intervals"]) == 196
    # Ohne dynamischen Tarif keine Ampel.
    tariff(store, mode="fixed", rate=.3)
    assert insights.price_outlook(Analytics(store), day + 3600, 2) == dict(insights.price_outlook(Analytics(store), day + 3600, 2), dynamic=False, intervals=[])


def test_live_and_outlook_api(authenticated):
    db = authenticated.app_store
    tariff(db, rate=.25, feedin=0)
    now = time.time()
    db.ingest(Reading(4000, 100, 0, "SYNTHETIC"), now - 6)
    db.ingest(Reading(4000, 100.004, 0, "SYNTHETIC"), now - 2)
    cost = authenticated.get("/api/live").json()["cost"]
    assert cost["direction"] == "import" and abs(cost["eur_per_hour"] - 1.0) < 1e-9
    outlook = authenticated.get("/api/prices/outlook?window_hours=3").json()
    assert outlook["dynamic"] is False and outlook["intervals"] == [] and outlook["window_hours"] == 3
    assert authenticated.get("/api/prices/outlook?window_hours=7").status_code == 400

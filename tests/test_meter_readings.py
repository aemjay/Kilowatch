"""Zählerstände zu Stichtagen und laufendes Abrechnungsjahr."""
from datetime import date

from app.analytics import Analytics, midnight
from app.decoder import Reading
from app import insights

ZONE = "Europe/Berlin"


def feed(store, start, count, step=60, kwh=100.0, per_step=.01):
    for index in range(count):
        store.ingest(Reading(600, kwh + index * per_step, 5 + index * per_step / 10, "SYNTHETIC"), start + index * step)
    return kwh + (count - 1) * per_step


def test_reading_is_last_sample_before_and_marks_gaps(store):
    day = midnight("2026-03-01", ZONE)
    feed(store, day - 600, 20)  # 10 Minuten vor bis 9 Minuten nach Mitternacht
    exact = insights.meter_reading(store, day, 90)
    assert exact["source"] == "sample" and not exact["approximate"] and exact["measured_at"] == day
    assert abs(exact["import_kwh"] - 100.1) < 1e-9 and abs(exact["export_kwh"] - 5.01) < 1e-9
    # Lücke über dem Stichtag: letzter Stand davor, markiert.
    store.ingest(Reading(600, 101, 6, "SYNTHETIC"), day + 7200)
    later = insights.meter_reading(store, day + 3600, 90)
    assert later["approximate"] and later["measured_at"] == day + 540 and later["reason"]
    # Vor allen Daten gibt es keinen Stand.
    none = insights.meter_reading(store, day - 86400, 90)
    assert none["import_kwh"] is None and none["source"] is None


def test_reading_is_reconstructed_after_raw_retention(store):
    day = midnight("2026-03-01", ZONE)
    last = feed(store, day - 3600, 180)
    store.ingest(Reading(600, last + 1, 6, "SYNTHETIC"), day - 3600 + 179 * 60 + 600)  # Lücke mit bekannter Menge
    expected = insights.meter_reading(store, day, 90)["import_kwh"]
    with store.transaction():
        store.conn.execute("DELETE FROM samples")
    rebuilt = insights.meter_reading(store, day, 90)
    assert rebuilt["source"] == "reconstructed" and rebuilt["approximate"]
    assert abs(rebuilt["import_kwh"] - expected) < 1e-6
    # Ein Zählerwechsel danach macht die Rückrechnung unmöglich.
    store.ingest(Reading(600, 5, 0, "OTHER"), day + 86400)
    assert insights.meter_reading(store, day, 90)["import_kwh"] is None


def test_billing_months():
    assert insights.billing_months(date(2026, 3, 15), date(2026, 10, 14)) == 6
    assert insights.billing_months(date(2026, 3, 15), date(2026, 10, 15)) == 7
    assert insights.billing_months(date(2025, 11, 1), date(2026, 1, 31)) == 2


def test_billing_year_requires_data_and_projects(store, monkeypatch):
    now = midnight("2026-10-26", ZONE) + 12 * 3600
    with store.transaction():
        store.conn.execute("INSERT INTO tariffs VALUES('2020-01-01','T','fixed',.3,12,0)")
    budget = {"billing_start": "03-01", "abschlag_eur": 80}
    result = insights.billing_year(Analytics(store), now, budget)
    assert result["start"] == "2026-03-01" and result["end"] == "2027-03-01" and result["months_elapsed"] == 7
    assert result["paid_eur"] == 560 and not result["available"] and result["reason"]
    assert insights.billing_year(Analytics(store), now, {"billing_start": "11-15"})["start"] == "2025-11-15"
    assert insights.billing_year(Analytics(store), now, {}) is None
    # Mit Jahreshochrechnung: 10 kWh/Tag × 0,30 € = 3 €/Tag, Grundpreis 12 €/Monat.
    monkeypatch.setattr(insights, "annual_projection", lambda a, n, x: {"available": True, "annual_kwh": 3652.5,
                                                                         "annual_eur": 3652.5 * .3 + 144, "valid_days": 90})
    result = insights.billing_year(Analytics(store), now, budget)
    assert result["available"]
    # Nichts erfasst: alles hochgerechnet, rund 365 Tage × 3 € + 12 × 12 €.
    assert abs(result["projected_eur"] - (365 * 3 + 144)) < 3
    assert result["recommended_abschlag_eur"] == round(result["projected_eur"] / 12)
    assert abs(result["difference_eur"] - (result["projected_eur"] - 960)) < 1e-9


def test_meter_reading_and_budget_api(authenticated):
    response = authenticated.get("/api/meter-readings?dates=2026-01-01,2026-02-01")
    assert response.status_code == 200 and [r["date"] for r in response.json()["readings"]] == ["2026-01-01", "2026-02-01"]
    assert authenticated.get("/api/meter-readings?dates=2026-13-01").status_code == 400
    assert authenticated.get("/api/meter-readings?dates=2999-01-01").status_code == 400
    assert authenticated.put("/api/budget", json={"billing_start": "02-29"}).status_code == 422
    assert authenticated.put("/api/budget", json={"billing_start": "03-01", "abschlag_eur": 90}).status_code == 200
    data = authenticated.get("/api/budget").json()
    assert data["settings"]["billing_start"] == "03-01" and data["billing"]["abschlag_eur"] == 90

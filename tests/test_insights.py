import pytest

from app import insights
from app.analytics import Analytics, midnight
from app.decoder import Reading
from app.demo import seed

NOW = midnight("2026-10-20", "Europe/Berlin") + 12 * 3600


@pytest.fixture
def seeded(store):
    seed(store, NOW)
    return store


def test_baseline_trend_has_weekly_points_cost_and_coverage(seeded):
    a = Analytics(seeded)
    result = insights.baseline_trend(a, NOW - 28 * 86400, NOW)
    assert result["group"] == "week"
    valid = [p for p in result["points"] if p["baseline_w"] is not None]
    assert len(valid) >= 3
    for point in valid:
        assert 50 <= point["baseline_w"] <= 400
        assert point["quarters"] >= insights.MIN_NIGHT_QUARTERS
        assert point["annual_eur"] == pytest.approx(point["baseline_w"] * 8766 / 1000 * 0.32)


def test_baseline_ignores_sparse_weeks_and_negative_night_power(store):
    for ts in range(int(NOW // 900) * 900 - 86400, int(NOW // 900) * 900, 900):
        store.ingest(Reading(-500, None, None, "A"), ts)
    result = insights.baseline_trend(Analytics(store), NOW - 7 * 86400, NOW)
    assert all(p["baseline_w"] is None for p in result["points"])


def test_simulation_with_same_fixed_tariff_matches_actual_cost(seeded):
    a = Analytics(seeded)
    start, end = midnight("2026-10-01", "Europe/Berlin"), midnight("2026-10-15", "Europe/Berlin")
    result = insights.simulate(a, start, end, {"mode": "fixed", "eur_kwh": .32, "base_month": 12.9, "feedin_eur_kwh": .08})
    assert result["total_eur"] == pytest.approx(result["actual_total_eur"], rel=1e-6)
    assert result["comparable"] and result["priced_share"] == pytest.approx(1)
    assert result["difference_eur"] == pytest.approx(0, abs=1e-9)


def test_dual_tariff_cheaper_at_night_lowers_cost(seeded):
    a = Analytics(seeded)
    start, end = midnight("2026-10-01", "Europe/Berlin"), midnight("2026-10-15", "Europe/Berlin")
    base = {"base_month": 0, "feedin_eur_kwh": 0, "eur_kwh": .32}
    fixed = insights.simulate(a, start, end, dict(base, mode="fixed"))
    dual = insights.simulate(a, start, end, dict(base, mode="dual", low_eur_kwh=.20, low_start="22:00", low_end="06:00", weekend_low=False))
    assert dual["energy_cost_eur"] < fixed["energy_cost_eur"]


def test_spot_simulation_reports_missing_prices_and_weighted_average(seeded):
    a = Analytics(seeded)
    start, end = midnight("2026-10-10", "Europe/Berlin"), midnight("2026-10-12", "Europe/Berlin")
    with seeded.transaction():
        # Nur der erste Tag hat Börsenpreise: abends teuer, sonst günstig.
        for ts in range(int(start), int(start) + 86400, 3600):
            hour = (ts - int(start)) // 3600
            seeded.conn.execute("INSERT INTO spot_prices VALUES(?,?,?)", (ts, ts + 3600, 200 if 17 <= hour <= 21 else 50))
    result = insights.simulate(a, start, end, {"mode": "spot", "markup_eur_kwh": .15, "vat_percent": 19, "base_month": 0, "feedin_eur_kwh": 0})
    assert 0.4 < result["priced_share"] < 0.6
    assert not result["comparable"]
    # Differenz nur über den Tag mit Börsenpreisen, offen ausgewiesen.
    assert result["paired_share"] == pytest.approx(result["priced_share"])
    assert result["difference_eur"] is not None
    # Der Demo-Haushalt verbraucht abends viel: verbrauchsgewichteter Börsenpreis liegt über dem Zeitmittel.
    assert result["spot_weighted_ct"] > result["spot_time_average_ct"]


def test_feedin_profile_without_export_is_unknown_not_zero(seeded):
    result = insights.feedin_profile(Analytics(seeded), NOW - 86400, NOW)
    assert result["total_kwh"] == 0 or result["total_kwh"] is None
    assert all(p["share"] is None for p in result["profile"])


def test_budget_forecast_and_annual_projection_need_enough_data(seeded):
    a = Analytics(seeded)
    month = insights.month_budget(a, NOW, {"monthly_eur": 50})
    assert month["observed_kwh"] > 0 and month["forecast_kwh"] > month["observed_kwh"]
    assert month["forecast_eur"] > month["observed_eur"]
    annual = insights.annual_projection(a, NOW, 80)
    assert not annual["available"] and "60" in annual["reason"]


def test_annual_projection_with_enough_days_compares_abschlag(store):
    seed(store, NOW)
    # 70 Tage gleichmäßiger Verbrauch: 24 kWh/Tag.
    store2_start = int((NOW - 70 * 86400) // 900) * 900
    a = Analytics(store)
    original = a.store.bucket_rows
    rows = [{"ts": ts, "import_kwh": .25, "import_s": 900} for ts in range(store2_start, int(NOW // 900) * 900, 900)]
    a.store.bucket_rows = lambda s, e, resolution=900: [r for r in rows if s <= r["ts"] < e] if resolution == 900 else original(s, e, resolution)
    result = insights.annual_projection(a, NOW, 100)
    assert result["available"] and result["valid_days"] >= 60
    assert result["annual_kwh"] == pytest.approx(24 * 365.25, rel=.01)
    assert result["difference_eur"] == pytest.approx(result["annual_eur"] - 1200)


def test_insight_endpoints(authenticated):
    store = authenticated.app_store
    seed(store)
    assert "baseline_trend" in authenticated.get("/api/insights").json()
    response = authenticated.post("/api/simulate", json={"start": "2026-01-01", "end": "2026-01-02", "tariff": {"mode": "spot", "base_month": 0}})
    assert response.status_code in (200, 400)
    assert authenticated.post("/api/simulate", json={"start": "2026-01-01", "end": "2026-01-02", "tariff": {"mode": "dual", "base_month": 0}}).status_code == 422
    assert authenticated.put("/api/budget", json={"monthly_eur": 80, "abschlag_eur": 95}).status_code == 200
    budget = authenticated.get("/api/budget").json()
    assert budget["settings"]["abschlag_eur"] == 95 and "month" in budget and "annual" in budget
    assert authenticated.put("/api/budget", json={"monthly_eur": -1}).status_code == 422


def test_cheaper_flat_price_shows_negative_paired_difference(seeded):
    a = Analytics(seeded)
    start, end = midnight("2026-10-01", "Europe/Berlin"), midnight("2026-10-08", "Europe/Berlin")
    result = insights.simulate(a, start, end, {"mode": "fixed", "eur_kwh": .22, "base_month": 12.9, "feedin_eur_kwh": .08})
    assert result["difference_eur"] == pytest.approx(-0.10 * result["priced_kwh"], rel=1e-6)

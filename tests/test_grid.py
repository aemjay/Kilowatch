import asyncio

import httpx
import pytest

from app.grid import SOURCE, Grid, parse_co2, parse_share

NOW = 1_800_000_000  # Viertelstundengrenze


def co2_payload(measured, forecast, start=NOW - 1800, deprecated=False):
    return {"unix_seconds": [start + i * 900 for i in range(len(measured))], "co2eq": measured,
            "co2eq_forecast": forecast, "deprecated": deprecated}


def share_payload(values, start=NOW - 1800):
    return {"unix_seconds": [start + i * 900 for i in range(len(values))],
            "production_types": [{"name": "Solar", "data": [1] * len(values)}, {"name": "Renewable share of load", "data": values}]}


def test_only_published_values_are_used_and_bad_data_is_rejected():
    # Die Prognosereihe der Quelle passt nicht zu den Messwerten und wird ignoriert.
    rows, deprecated = parse_co2(co2_payload([300, None, None], [280, 250, None]))
    assert rows == {NOW - 1800: 300.0} and not deprecated
    assert parse_share(share_payload([60, None]))[0] == {NOW - 1800: 60.0}
    for bad in (co2_payload([300], [None], start=NOW + 1), co2_payload([-5], [None]), {"unix_seconds": [NOW], "co2eq": []}):
        with pytest.raises(ValueError):
            parse_co2(bad)


def grid_with(store, handler):
    return Grid(store, transport=httpx.MockTransport(handler))


def test_no_request_without_country(store):
    calls = []
    grid = grid_with(store, lambda request: calls.append(request) or httpx.Response(500))
    asyncio.run(grid.refresh(NOW))
    assert calls == [] and grid.balance([], NOW - 3600, NOW) is None


def test_refresh_sends_only_country_and_range_and_updates_published_values(store):
    store.update_settings({"grid_country": "se"})
    calls, answers = [], {"/co2eq": co2_payload([40, None], [None, 41]), "/public_power": share_payload([90, 91])}

    def handle(request):
        calls.append(request)
        assert request.url.host == "api.energy-charts.info"
        assert set(request.url.params) == {"country", "start", "end"} and request.url.params["country"] == "se"
        assert int(request.url.params["end"]) <= NOW + 900  # nie in die Zukunft (Prognosen)
        assert "cookie" not in request.headers and "authorization" not in request.headers
        return httpx.Response(200, json=answers[request.url.path])

    grid = grid_with(store, handle)
    asyncio.run(grid.refresh(NOW))
    assert len(calls) == 2
    rows = store.rows("SELECT start,g_kwh,renewable_share FROM grid_intensity ORDER BY start")
    assert [(r["g_kwh"], r["renewable_share"]) for r in rows] == [(40, 90), (None, 91)]
    # Später veröffentlichte Werte ergänzen die Lücke; der nächste Abruf beginnt beim letzten Wert.
    answers["/co2eq"] = co2_payload([41, 42], [None, None])
    asyncio.run(grid.refresh(NOW + 900))
    rows = store.rows("SELECT g_kwh FROM grid_intensity ORDER BY start")
    assert [r["g_kwh"] for r in rows] == [41, 42]
    assert int(calls[-2].url.params["start"]) >= NOW - 1800 - 6 * 3600
    assert grid.status()["error"] == "" and grid.status()["fetched_at"] == NOW + 900


def test_balance_uses_measured_intensities_only_and_reports_uncovered_energy(store):
    store.update_settings({"grid_country": "de"})
    grid = Grid(store)
    grid.save("de", {NOW - 1800: 400.0}, {NOW - 1800: 50.0, NOW - 900: 70.0})
    buckets = [{"ts": NOW - 1800, "import_kwh": 1.0}, {"ts": NOW - 900, "import_kwh": 0.5}, {"ts": NOW, "import_kwh": 0.25}]
    result = grid.balance(buckets, NOW - 1800, NOW + 900, now=NOW)
    assert result["kg"] == pytest.approx(0.4) and result["g_kwh"] == pytest.approx(400)
    assert result["covered_kwh"] == pytest.approx(1.0) and result["uncovered_kwh"] == pytest.approx(0.75)
    assert result["renewable_share"] == pytest.approx((50 * 1 + 70 * .5) / 1.5)
    # Zuletzt veröffentlichter Wert samt Zeitpunkt.
    assert result["current"]["g_kwh"] == 400 and result["current"]["start"] == NOW - 1800
    assert result["source"] == SOURCE and "CC BY 4.0" in SOURCE


def test_failures_are_kept_as_status_and_deprecation_is_reported(store):
    store.update_settings({"grid_country": "nl"})
    grid = grid_with(store, lambda request: httpx.Response(503))
    asyncio.run(grid.refresh(NOW))
    assert "503" in grid.status()["error"]
    grid = grid_with(store, lambda request: httpx.Response(200, json=co2_payload([100], [None], deprecated=True) if request.url.path == "/co2eq" else share_payload([10])))
    asyncio.run(grid.refresh(NOW))
    assert grid.status()["deprecated"] is True and grid.status()["error"] == ""


def test_grid_country_setting_is_validated_and_overview_carries_the_balance(authenticated):
    assert authenticated.get("/api/settings").json()["grid_country"] == ""
    assert authenticated.get("/api/overview").json()["co2"] is None
    assert authenticated.put("/api/settings", json={"grid_country": "fr"}).status_code in (400, 422)
    assert authenticated.put("/api/settings", json={"grid_country": "no"}).status_code == 200
    co2 = authenticated.get("/api/overview").json()["co2"]
    assert co2["country"] == "no" and co2["kg"] is None

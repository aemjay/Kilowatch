from datetime import date, timedelta

import pytest

from app.analytics import Analytics, midnight
from app.decoder import Reading


@pytest.mark.parametrize("day,hours",[("2026-03-29",23),("2026-10-25",25),("2026-10-24",24)])
def test_local_day_duration(day,hours):
    following=date.fromisoformat(day)+timedelta(days=1)
    assert midnight(following,"Europe/Berlin")-midnight(day,"Europe/Berlin")==hours*3600


def test_base_price_and_tariff_change_across_dst(store):
    with store.transaction():
        store.conn.executemany("INSERT INTO tariffs VALUES(?,?,?,?,?,?)",[("2026-10-01","old","fixed",.3,31,0),("2026-10-25","new","fixed",.4,62,0)])
    a=Analytics(store)
    start,end=midnight("2026-10-24",a.zone),midnight("2026-10-26",a.zone)
    cost,missing=a.base_cost(start,end)
    assert cost==pytest.approx(3)
    assert not missing
    assert a.base_factor(start,end)==pytest.approx(2/31)


def test_dynamic_missing_price_never_free_or_fixed_fallback(store):
    start=midnight("2026-10-01","Europe/Berlin")
    store.ingest(Reading(3600,100,0,"A"),start)
    store.ingest(Reading(3600,100.01,0,"A"),start+10)
    with store.transaction():
        store.conn.execute("INSERT INTO tariffs VALUES(?,?,?,?,?,?)",("2026-10-01","dynamic","dynamic",.99,0,0))
    result=Analytics(store).summary(start,start+10)
    assert result["unpriced_kwh"]==pytest.approx(.01)
    assert result["energy_cost_eur"]==0
    assert not result["cost_complete"]
    with store.transaction():
        store.conn.execute("INSERT INTO prices VALUES(?,?,?)",(start,start+900,-.05))
    result=Analytics(store).summary(start,start+10)
    assert result["energy_cost_eur"]==pytest.approx(-.0005)
    assert result["cost_complete"]


def test_missing_periods_keep_empty_axis_positions(store):
    start=midnight("2026-10-01","Europe/Berlin")
    result=Analytics(store).series(start,start+3600)
    assert len(result["energy"])==4
    assert all(r["import_kwh"] is None for r in result["energy"])


def test_dst_has_100_quarters_not_96(store):
    start,end=midnight("2026-10-25","Europe/Berlin"),midnight("2026-10-26","Europe/Berlin")
    result=Analytics(store).series(start,end)
    assert len(result["energy"])==100
    assert len({r["ts"] for r in result["energy"]})==100


def test_forecast_requires_sufficient_data(store):
    assert not Analytics(store).forecast(midnight("2026-10-24","Europe/Berlin"))["available"]

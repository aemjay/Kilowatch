from datetime import datetime
import sqlite3

import pytest

from app.analytics import Analytics, midnight
from app.cli import restore
from app.decoder import Reading
from app.storage import SCHEMA_VERSION, Store


def payload(**extra):
    return {"start_date":"2026-01-01","name":"Synthetic HT/NT","mode":"dual","eur_kwh":.4,
            "low_eur_kwh":.2,"low_start":"22:00","low_end":"06:00","weekend_low":False,
            "base_month":12,"feedin_eur_kwh":0,**extra}


@pytest.mark.parametrize("stamp,rate",[("2026-10-24T21:45:00+02:00",.4),("2026-10-24T22:00:00+02:00",.2),
    ("2026-10-25T02:30:00+02:00",.2),("2026-10-25T02:30:00+01:00",.2),("2026-10-25T06:00:00+01:00",.4)])
def test_dual_rates_follow_local_clock_including_both_dst_hours(authenticated,stamp,rate):
    assert authenticated.put("/api/tariffs",json=payload()).status_code==200
    a=Analytics(authenticated.app_store)
    ts=datetime.fromisoformat(stamp).timestamp()
    assert a.rate(ts,a.tariff(ts))==rate


def test_costs_on_each_side_of_tariff_boundary(authenticated):
    authenticated.put("/api/tariffs",json=payload(base_month=0))
    db=authenticated.app_store
    start=midnight("2026-10-24","Europe/Berlin")+21*3600+45*60
    db.update_settings({"max_gap_seconds":300})
    for offset in range(0,1801,300):
        db.ingest(Reading(4000,100+offset/3600*4,0,"SYNTHETIC"),start+offset)
    result=Analytics(db).summary(start,start+1800)
    assert result["energy_cost_eur"]==pytest.approx(.6)


def test_weekend_and_same_day_window(authenticated):
    authenticated.put("/api/tariffs",json=payload(low_start="12:00",low_end="14:00",weekend_low=True))
    a=Analytics(authenticated.app_store)
    for stamp,expected in [("2026-10-24T10:00:00+02:00",.2),("2026-10-26T10:00:00+01:00",.4),("2026-10-26T12:00:00+01:00",.2)]:
        ts=datetime.fromisoformat(stamp).timestamp()
        assert a.rate(ts,a.tariff(ts))==expected


@pytest.mark.parametrize("extra",[{"low_eur_kwh":None},{"low_start":"22:05"},{"low_end":"22:00"},{"low_start":"25:00"}])
def test_incomplete_or_unaligned_dual_tariffs_rejected(authenticated,extra):
    assert authenticated.put("/api/tariffs",json=payload(**extra)).status_code==422
    assert not authenticated.app_store.rows("SELECT * FROM tariffs")


def test_replacing_dual_with_single_clears_schedule_and_survives_backup(authenticated,tmp_path):
    authenticated.put("/api/tariffs",json=payload())
    backup=authenticated.app_store.backup()
    destination=tmp_path/"restored"
    restore(backup,destination,True)
    db=Store(destination)
    assert Analytics(db).tariffs[0]["low_eur_kwh"]==.2
    db.close()
    authenticated.put("/api/tariffs",json=payload(mode="fixed"))
    assert authenticated.app_store.state("tariff_schedules")=={}


def test_newer_schema_is_rejected_by_restore(store,tmp_path):
    store.ingest(Reading(400,100,0,"SYNTHETIC"),1800)
    backup=store.backup()
    with sqlite3.connect(backup) as connection:
        connection.execute(f"PRAGMA user_version={SCHEMA_VERSION+1}")
    with pytest.raises(ValueError,match="Schema 1 bis"):
        restore(backup,tmp_path/"restored",True)

import sqlite3

import pytest

from app.analytics import Analytics
from app.cli import restore
from app.decoder import Reading


def test_counter_preferred_over_power_and_no_duplicate_time(store):
    store.ingest(Reading(9000, 100.0, 0, "A"), 1800)
    store.ingest(Reading(9000, 100.001, 0, "A"), 1810)
    assert not store.ingest(Reading(9000, 100.001, 0, "A"), 1810)
    rows = store.bucket_rows(1800, 1820)
    assert sum(r["import_kwh"] for r in rows) == pytest.approx(.001)
    assert sum(r["estimated_import"] for r in rows) == 0


def test_energy_preserved_across_bucket_boundary(store):
    store.ingest(Reading(3600, 20, 0, "A"), 1795)
    store.ingest(Reading(3600, 20.01, 0, "A"), 1805)
    for resolution in (60, 900):
        rows = store.bucket_rows(1700, 1900, resolution)
        assert len(rows) == 2
        assert sum(r["import_kwh"] for r in rows) == pytest.approx(.01)
        assert sum(r["import_s"] for r in rows) == 10


def test_gap_energy_not_smeared_over_time(store):
    store.ingest(Reading(400, 100, 0, "A"), 1800)
    store.ingest(Reading(400, 101, 0, "A"), 5400)
    assert store.bucket_rows(1800, 5401) == []
    assert store.gap_rows(1800, 5401)[0]["import_kwh"] == 1
    result = Analytics(store).summary(1800, 5401)
    assert result["import_kwh"] == 1
    assert result["coverage"] == 0
    assert result["recovered_import_kwh"] == 1
    assert not result["cost_complete"]
    clipped = Analytics(store).summary(3600, 5401)
    assert clipped["import_kwh"] is None
    assert clipped["crossing_gaps"] == 1


def test_signed_power_integration_with_zero_crossing(store):
    store.ingest(Reading(3600), 1800)
    store.ingest(Reading(-3600), 1810)
    row = store.bucket_rows(1800, 1811)[0]
    assert row["import_kwh"] == pytest.approx(.0025)
    assert row["export_kwh"] == pytest.approx(.0025)
    assert row["estimated_import"] == pytest.approx(.0025)


@pytest.mark.parametrize("old,new,id2,code", [(100,1,"A","counter_reset"),(100,100000,"A","counter_jump"),(100,101,"B","meter_change")])
def test_resets_jumps_and_meter_changes(store, old, new, id2, code):
    store.ingest(Reading(400,old,0,"A"),1800)
    store.ingest(Reading(400,new,0,id2),1810)
    assert store.bucket_rows(1800,1811) == []
    assert store.rows("SELECT * FROM issues WHERE code=?",(code,))
    assert store.gap_rows(1800,1811)[0]["import_kwh"] is None


def test_missing_counters_and_missing_power_are_unknown(store):
    store.ingest(Reading(None, 100, None), 1800)
    store.ingest(Reading(None, 100.001, None), 1810)
    result = Analytics(store).summary(1800, 1810)
    assert result["import_kwh"] == pytest.approx(.001)
    assert result["export_kwh"] is None


def test_rollback_is_atomic_including_issue(store):
    with pytest.raises(RuntimeError):
        with store.transaction():
            store.issue("test", "must roll back")
            store.conn.execute("INSERT INTO state VALUES('rollback','true')")
            raise RuntimeError()
    assert store.rows("SELECT * FROM issues") == []
    assert store.state("rollback") is None


def test_retention_keeps_permanent_quarters_and_latest_baseline(store):
    store.ingest(Reading(400,100,0,"A"), 1800)
    store.ingest(Reading(400,100.001,0,"A"), 1810)
    store.update_settings({"raw_retention_days":1,"minute_retention_days":1})
    store.maintenance(now=1800+3*86400)
    assert store.rows("SELECT * FROM samples") == []
    assert store.bucket_rows(1800,1820,60) == []
    assert store.bucket_rows(1800,1820,900)
    assert store.latest()["import_kwh"] == pytest.approx(100.001)


def test_backup_restore_roundtrip(store,tmp_path):
    store.ingest(Reading(400,100,0,"A"),1800)
    store.ingest(Reading(400,100.001,0,"A"),1810)
    backup = store.backup()
    destination = tmp_path / "restored"
    with pytest.raises(ValueError,match="confirm-stopped"):
        restore(backup,destination)
    result = restore(backup,destination,True)
    with sqlite3.connect(result) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT COUNT(*) FROM samples").fetchone()[0] == 2


def test_restore_invalid_database_does_not_replace_target(tmp_path):
    source=tmp_path/"wrong.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE unrelated(id)")
    directory=tmp_path/"dest"
    directory.mkdir()
    target=directory/"kilowatch.sqlite3"
    target.write_bytes(b"original unchanged")
    with pytest.raises(ValueError,match="kompatible"):
        restore(source,directory,True)
    assert target.read_bytes() == b"original unchanged"


def test_backup_does_not_need_the_shared_store_lock(store,tmp_path):
    import threading
    store.ingest(Reading(100, 1.0, 0, "A"), 900)
    result={}
    worker=threading.Thread(target=lambda: result.update(path=store.backup(tmp_path/"copy.sqlite3")))
    with store.lock:
        # Hielte backup() die gemeinsame Sperre, würde es hier bis zum Timeout warten.
        worker.start()
        worker.join(timeout=10)
        assert not worker.is_alive()
    assert result["path"].exists()
    with sqlite3.connect(result["path"]) as copy:
        assert copy.execute("SELECT COUNT(*) FROM samples").fetchone()[0]==1


def test_collector_persist_deduplicates_identical_telegrams(store):
    from app.collector import Collector
    collector=Collector(store, lambda: "")
    assert collector.persist(Reading(100, 1.0, 0, "A"), "hash-a", 900)==(True, 900)
    assert collector.persist(Reading(100, 1.0, 0, "A"), "hash-a", 905)==(False, 900)
    assert collector.persist(Reading(120, 1.001, 0, "A"), "hash-b", 910)==(True, 910)
    assert store.latest()["ts"]==910

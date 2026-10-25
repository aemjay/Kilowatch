from datetime import datetime, timezone

import pytest

from app.decoder import Reading
from app.main import parse_prices


def test_auth_and_logout(client):
    assert client.get("/healthz").status_code==200
    assert client.get("/api/live").status_code==401
    assert client.post("/api/login",json={"password":"wrong"}).status_code==401
    assert client.post("/api/login",json={"password":"test-password-long-enough"}).status_code==200
    assert client.get("/api/live").status_code==200
    client.post("/api/logout")
    assert client.get("/api/live").status_code==401


def test_csrf_and_origin(authenticated):
    response=authenticated.put("/api/settings",json={"name":"bad"},headers={"Origin":"http://other-host"})
    assert response.status_code==403
    authenticated.headers.pop("X-Kilowatch-Request")
    assert authenticated.put("/api/settings",json={"name":"bad"}).status_code==403


def test_secret_not_returned_and_host_restricted(authenticated):
    assert authenticated.put("/api/settings",json={"bridge_password":"SAMPLE-SECRET"}).status_code==200
    response=authenticated.get("/api/settings")
    assert response.json()["password_configured"]
    assert "SAMPLE-SECRET" not in response.text
    for host in ["8.8.8.8","http://192.168.1.2/","192.168.1.2:80","0.0.0.0","invalid_name.fritz.box"]:
        assert authenticated.put("/api/settings",json={"bridge_host":host}).status_code==422
    assert authenticated.put("/api/settings",json={"bridge_host":"bridge.fritz.box"}).status_code==200


def test_login_throttle(client):
    for _ in range(10):
        assert client.post("/api/login",json={"password":"wrong"}).status_code==401
    assert client.post("/api/login",json={"password":"wrong"}).status_code==429


def test_prices_reject_ambiguous_times_overlaps_and_accept_negative(authenticated):
    text="start,end,eur_kwh\n2026-10-25T02:00:00+02:00,2026-10-25T03:00:00+02:00,-0.1\n"
    assert authenticated.post("/api/prices/import",json={"csv":text}).json()["count"]==1
    assert authenticated.post("/api/prices/import",json={"csv":text}).status_code==200
    overlap="start,end,eur_kwh\n2026-10-25T02:15:00+02:00,2026-10-25T03:15:00+02:00,0.2\n"
    assert authenticated.post("/api/prices/import",json={"csv":overlap}).status_code==400
    ambiguous="start,end,eur_kwh\n2026-10-25T02:00:00,2026-10-25T03:00:00,0.2\n"
    assert authenticated.post("/api/prices/import",json={"csv":ambiguous}).status_code==400


def test_price_import_rolls_back_entire_file(authenticated):
    db=authenticated.app_store
    with db.transaction():
        db.conn.execute("INSERT INTO prices VALUES(900,1800,.3)")
    text="start,end,eur_kwh\n1970-01-01T00:00:00Z,1970-01-01T00:15:00Z,0.2\n1970-01-01T00:30:00Z,1970-01-01T00:45:00Z,0.3\n"
    assert authenticated.post("/api/prices/import",json={"csv":text}).status_code==200
    # Separater Import: erster Eintrag neu, zweiter kollidiert.
    text="start,end,eur_kwh\n1969-12-31T23:00:00Z,1969-12-31T23:15:00Z,0.2\n1970-01-01T00:15:00Z,1970-01-01T00:45:00Z,0.2\n"
    assert authenticated.post("/api/prices/import",json={"csv":text}).status_code==400
    assert not db.rows("SELECT * FROM prices WHERE start<0")


def test_events_tariffs_and_exports(authenticated):
    today=datetime.now(timezone.utc).date().isoformat()
    assert authenticated.put("/api/tariffs",json={"start_date":today,"name":"My rate","mode":"fixed","eur_kwh":.3,"base_month":12,"feedin_eur_kwh":.08}).status_code==200
    assert authenticated.post("/api/events",json={"start_date":today,"end_date":today,"title":"<script>ignored</script>","note":"test"}).status_code==200
    events=authenticated.get("/api/events").json()
    assert len(events)==1
    assert authenticated.delete('/api/events/'+str(events[0]['id'])).status_code==200
    now=datetime.now(timezone.utc).timestamp()
    authenticated.app_store.ingest(Reading(450,100,0,"SYNTHETIC"),now-10)
    authenticated.app_store.ingest(Reading(450,100.001,0,"SYNTHETIC"),now-5)
    response=authenticated.get("/api/export?kind=samples&format=json&limit=1")
    assert response.status_code==200
    assert response.json()["page_full"]
    assert response.json()["next_offset"]==1
    assert "time_local" in response.json()["data"][0]
    assert authenticated.get("/api/overview").status_code==200
    assert authenticated.get("/api/analysis").status_code==200
    assert authenticated.get("/api/backup").content.startswith(b"SQLite format 3")


def test_security_headers_and_no_external_frontend_assets(client):
    response=client.get("/")
    assert response.status_code==200
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "https://" not in response.text


@pytest.mark.parametrize("text",["","start,end,eur_kwh\n2026-10-01T00:01:00Z,2026-10-01T01:00:00Z,0.1","start,end,eur_kwh\n2026-10-01T00:00:00Z,2026-10-01T01:00:00Z,nan"])
def test_bad_prices(text):
    with pytest.raises((ValueError,IndexError)):
        parse_prices(text)


def test_price_csv_with_missing_column_is_a_clear_400(authenticated):
    text="start,end,eur_kwh\n2026-01-01T00:00:00+01:00,2026-01-01T00:15:00+01:00\n"
    response=authenticated.post("/api/prices/import",json={"csv":text})
    assert response.status_code==400
    assert "Zeile 2" in response.json()["detail"]


def test_bridge_test_never_sends_stored_password_to_new_host(authenticated):
    authenticated.put("/api/settings",json={"bridge_host":"bridge.example.lan","bridge_user":"synthetic-user","bridge_password":"synthetic-secret"})
    response=authenticated.post("/api/bridge/test",json={"bridge_host":"other.example.lan"})
    assert response.status_code==400
    assert "erneut eingeben" in response.json()["detail"]
    response=authenticated.post("/api/bridge/test",json={"bridge_user":"another-user"})
    assert response.status_code==400


def test_hour_views_show_individual_readings_and_compare_with_the_hour_before(authenticated):
    now=datetime.now(timezone.utc).timestamp()
    for index,watts in enumerate([300,320,2500,310]):
        authenticated.app_store.ingest(Reading(watts,100+index*.001,0,"SYNTHETIC"),now-40+index*10)
    data=authenticated.get("/api/overview?hours=1").json()
    series=data["series"]
    assert series["power_resolution_seconds"]==0
    assert [round(p["power_w"]) for p in series["power"]][-4:]==[300,320,2500,310]
    start,end=data["summary"]["start"],data["summary"]["end"]
    # Beginn auf die Viertelstunde gerundet, damit die Energie vollständig im Fenster liegt.
    assert start%900==0 and 3600<=end-start<3600+900
    assert data["previous"] is None or data["previous"]["end"]<=start
    # Sechs Stunden: Minutenwerte, Kalendertage unverändert.
    assert authenticated.get("/api/overview?hours=6").json()["series"]["power_resolution_seconds"]==60
    assert authenticated.get("/api/overview").json()["series"]["power_resolution_seconds"] in (60,900)
    for bad in ("0","49"):
        assert authenticated.get("/api/overview?hours="+bad).status_code==400
    assert authenticated.get("/api/analysis?hours=6").status_code==200

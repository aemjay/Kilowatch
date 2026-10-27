"""Einrichtungsliste der Übersicht."""
import os
import time

from app import checklist


def keys(client):
    return [item["key"] for item in client.get("/api/checklist").json()["items"]]


def test_fresh_install_lists_missing_steps_and_resolves_them(authenticated):
    app = authenticated.app
    db = app.state.store
    assert keys(authenticated) == ["tariff", "notifications", "backup"]
    authenticated.put("/api/tariffs", json={"start_date": "2020-01-01", "name": "Dyn", "mode": "dynamic", "eur_kwh": 0, "base_month": 10, "feedin_eur_kwh": 0})
    assert keys(authenticated) == ["price_source", "notifications", "backup"]
    # Quelle gesetzt, aber letzter erfolgreicher Abruf älter als 26 Stunden.
    db.set_state("price_feed", {"source": "spot"})
    db.set_state("price_feed_status", {"fetched_at": time.time(), "succeeded_at": time.time() - 27 * 3600, "error": "x"})
    item = authenticated.get("/api/checklist").json()["items"][0]
    assert item["key"] == "price_source" and item["title"] == "Preisabruf gestört"
    db.set_state("price_feed_status", {"fetched_at": time.time(), "succeeded_at": time.time() - 3600, "error": ""})
    assert "price_source" not in keys(authenticated)
    # E-Mail vollständig eingeschaltet.
    db.set_state("notification_settings", {"enabled": True, "email_enabled": True, "smtp_host": "smtp.example.test", "email_to": ["a@example.test"]})
    assert "notifications" not in keys(authenticated)
    # Frische Sicherung im Sicherungsordner.
    path = db.backup()
    assert "backup" not in keys(authenticated)
    old = time.time() - 9 * 86400
    os.utime(path, (old, old))
    assert "backup" in keys(authenticated)
    # Update-Hinweis aus der bestehenden Prüfung.
    db.set_state("update_status", {"latest": "99.0.0", "url": "https://github.com/x/y", "notes": "", "schema": None, "major_change": True, "checked_at": 1})
    update = [i for i in authenticated.get("/api/checklist").json()["items"] if i["key"] == "update"][0]
    assert update["params"] == {"version": "99.0.0"} and update["page"] == "system"


def test_muted_items_stay_hidden_until_restored(authenticated):
    result = authenticated.put("/api/checklist", json={"muted": ["backup", "tariff", "backup"]}).json()
    assert result["muted"] == ["backup", "tariff"] and result["muted_open"] == 2
    assert keys(authenticated) == ["notifications"]
    assert authenticated.put("/api/checklist", json={"muted": ["unknown"]}).status_code == 422
    assert authenticated.put("/api/checklist", json={"muted": []}).json()["muted_open"] == 0
    assert keys(authenticated) == ["tariff", "notifications", "backup"]


def test_never_successful_price_source_is_reported(store):
    class Feed:
        def __init__(self, status):
            self._status = status
        def config(self):
            return {"source": "tibber"}
        def status(self):
            return self._status

    class Mail:
        def config(self):
            class C: enabled = email_enabled = True; smtp_host = "h"; email_to = ["a@b.c"]
            return C()

    class Updates:
        def status(self):
            return {"available": False}

    with store.transaction():
        store.conn.execute("INSERT INTO tariffs VALUES('2020-01-01','D','dynamic',0,0,0)")
    store.backup()
    failing = checklist.open_items(store, Mail(), Feed({"fetched_at": 1, "error": "Token"}), Updates())
    assert [i["key"] for i in failing] == ["price_source"]
    assert checklist.open_items(store, Mail(), Feed({"fetched_at": None, "error": ""}), Updates()) == []
    demo = checklist.open_items(store, Mail(), Feed({"fetched_at": None, "error": ""}), Updates(), demo=True)
    assert [i["key"] for i in demo] == ["update"]


def test_price_source_with_prices_for_the_future_is_not_reported(store):
    class Feed:
        def __init__(self, status):
            self._status = status
        def config(self):
            return {"source": "spot"}
        def status(self):
            return self._status

    class Mail:
        def config(self):
            class C: enabled = email_enabled = True; smtp_host = "h"; email_to = ["a@b.c"]
            return C()

    class Updates:
        def status(self):
            return {"available": False}

    with store.transaction():
        store.conn.execute("INSERT INTO tariffs VALUES('2020-01-01','D','dynamic',0,0,0)")
    store.backup()
    now = time.time()
    # Nach einem Update ohne succeeded_at scheitert ein Abruf, die Preise reichen aber bis morgen.
    status = {"fetched_at": now, "error": "HTTP 503", "latest_end": now + 6 * 3600}
    assert checklist.open_items(store, Mail(), Feed(status), Updates(), now=now) == []
    status["latest_end"] = now - 3600
    assert [i["key"] for i in checklist.open_items(store, Mail(), Feed(status), Updates(), now=now)] == ["price_source"]

"""Abnahmetests aus dem Security-Review vom 25.10.2026 (KW-01, KW-03, KW-04, KW-05)."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest

PASSWORD = "test-password-long-enough"


def test_oversized_bodies_are_rejected_before_parsing_even_during_lockout(client):
    big = b'{"password":"' + b"x" * 10000 + b'"}'
    headers = {"Content-Type": "application/json"}
    assert client.post("/api/login", content=big, headers=headers).status_code == 413
    # Ohne Content-Length (chunked) zählt die Middleware die tatsächlich empfangenen Bytes.
    response = client.post("/api/login", content=iter([big[:3000], big[3000:]]), headers=headers)
    assert response.status_code == 413 and response.json()["detail"] == "Anfrage ist zu groß."
    assert client.post("/api/login", content=big, headers=dict(headers, **{"X-Kilowatch-Language": "en"})).json()["detail"] != "Anfrage ist zu groß."
    for _ in range(10):
        client.post("/api/login", json={"password": "falsch"})
    assert client.post("/api/login", json={"password": "falsch"}).status_code == 429
    assert client.post("/api/login", content=big, headers=headers).status_code == 413
    assert client.post("/api/login", content=iter([big]), headers=headers).status_code == 413
    assert client.get("/healthz").status_code == 200


def test_body_limit_leaves_room_for_the_price_import(authenticated):
    rows = "".join(f"2026-01-01T{h:02d}:00:00+00:00,2026-01-01T{h:02d}:15:00+00:00,0.30\n" for h in range(24))
    response = authenticated.post("/api/prices/import", json={"csv": "start,end,eur_kwh\n" + rows})
    assert response.status_code == 200, response.text
    assert authenticated.put("/api/budget", content=b"{" + b" " * 300000 + b"}", headers={"Content-Type": "application/json"}).status_code == 413


def test_parallel_failed_logins_cannot_exceed_the_limit(client):
    auth = client.app.state.auth
    original, calls = auth.verify, []

    def slow(password):
        calls.append(password)
        time.sleep(0.02)
        return original(password)

    auth.verify = slow
    with ThreadPoolExecutor(20) as pool:
        codes = list(pool.map(lambda _: client.post("/api/login", json={"password": "falsch"}).status_code, range(20)))
    assert len(calls) == 10 and sorted(codes) == [401] * 10 + [429] * 10


def test_global_login_limit_applies_across_addresses(client):
    from fastapi.testclient import TestClient
    for address in range(6):
        other = TestClient(client.app, headers={"X-Kilowatch-Request": "1"}, client=(f"192.0.2.{address}", 50000))
        codes = [other.post("/api/login", json={"password": "falsch"}).status_code for _ in range(10)]
        assert codes == [401] * 10 if address < 5 else codes == [429] * 10
    # Auch das richtige Passwort wartet, bis das Fenster abgelaufen ist.
    assert client.post("/api/login", json={"password": PASSWORD}).status_code == 429


def test_password_change_is_throttled(authenticated):
    for _ in range(10):
        assert authenticated.put("/api/account/password", json={"current_password": "falsch", "new_password": "x" * 12}).status_code == 400
    assert authenticated.put("/api/account/password", json={"current_password": PASSWORD, "new_password": "y" * 12}).status_code == 429


def test_login_paused_during_password_change_gets_no_valid_session(client):
    auth = client.app.state.auth
    original, paused, resume, pause = auth.verify, threading.Event(), threading.Event(), []

    def verify(password):
        result = original(password)
        if pause and not paused.is_set():
            # Login hat das alte Passwort erfolgreich geprüft und hält an.
            paused.set()
            resume.wait(5)
        return result

    auth.verify = verify
    assert client.post("/api/login", json={"password": PASSWORD}).status_code == 200
    changer_session = dict(client.cookies)
    results = {}

    def old_login():
        response = client.post("/api/login", json={"password": PASSWORD}, cookies={})
        results["login"] = response.status_code, response.cookies.get("kilowatch_session")

    pause.append(True)
    login = threading.Thread(target=old_login)
    login.start()
    assert paused.wait(5)
    change = threading.Thread(target=lambda: results.__setitem__("change", client.put(
        "/api/account/password", json={"current_password": PASSWORD, "new_password": "brand-new-password"},
        cookies=changer_session).status_code))
    change.start()
    time.sleep(0.1)
    resume.set()
    login.join(5)
    change.join(5)
    assert results["change"] == 200
    status, token = results["login"]
    if status == 200:
        # Der Wechsel lief erst danach und hat diese Sitzung beendet.
        client.cookies.clear()
        assert client.get("/api/settings", cookies={"kilowatch_session": token}).status_code == 401
    assert client.post("/api/login", json={"password": PASSWORD}).status_code == 401


def test_two_parallel_password_changes_with_the_same_old_password(authenticated):
    session = dict(authenticated.cookies)

    def change(new):
        return authenticated.put("/api/account/password", json={"current_password": PASSWORD, "new_password": new}, cookies=session).status_code

    with ThreadPoolExecutor(2) as pool:
        codes = sorted(pool.map(change, ["first-new-password", "second-new-password"]))
    assert codes == [200, 400]


@pytest.fixture
def bridge_configured(authenticated):
    assert authenticated.put("/api/settings", json={"bridge_host": "192.168.1.20", "bridge_user": "admin", "bridge_password": "OLD-SECRET"}).status_code == 200
    return authenticated


def test_bridge_secret_never_follows_a_changed_target(bridge_configured):
    client = bridge_configured
    vault = client.app.state.vault
    for change in ({"bridge_host": "192.168.1.66"}, {"bridge_user": "root"}):
        response = client.put("/api/settings", json=change)
        assert response.status_code == 400 and "erneut" in response.json()["detail"]
    saved = client.get("/api/settings").json()
    assert (saved["bridge_host"], saved["bridge_user"], vault.get("bridge_password")) == ("192.168.1.20", "admin", "OLD-SECRET")
    # Unveränderte Werte und reine Erfassungsoptionen behalten das Secret.
    assert client.put("/api/settings", json={"bridge_host": "192.168.1.20", "bridge_user": "admin", "poll_seconds": 5}).status_code == 200
    assert client.put("/api/settings", json={"bridge_host": "192.168.1.66", "bridge_password": "NEW-SECRET"}).status_code == 200
    assert vault.get("bridge_password") == "NEW-SECRET"


def test_smtp_password_never_follows_a_changed_server(authenticated):
    client = authenticated
    vault = client.app.state.vault
    base = {"enabled": True, "email_enabled": True, "smtp_host": "smtp.example.org", "smtp_port": 587, "smtp_user": "me",
            "smtp_from": "me@example.org", "email_to": ["me@example.org"]}
    assert client.put("/api/notifications", json=dict(base, smtp_password="SMTP-SECRET")).status_code == 200
    for change in ({"smtp_host": "smtp.attacker.example"}, {"smtp_port": 465}, {"smtp_user": "other"}, {"smtp_security": "ssl"}):
        response = client.put("/api/notifications", json=dict(base, **change))
        assert response.status_code == 400, change
    assert vault.get("smtp_password") == "SMTP-SECRET"
    assert client.get("/api/notifications").json()["settings"]["smtp_host"] == "smtp.example.org"
    # Empfänger oder Absender ändern behält die Zugangsdaten.
    assert client.put("/api/notifications", json=dict(base, email_to=["other@example.org"])).status_code == 200
    # Neues Ziel mit neuem Secret oder mit ausdrücklichem Entfernen ist erlaubt.
    assert client.put("/api/notifications", json=dict(base, smtp_host="smtp.new.example", smtp_password="NEW")).status_code == 200
    assert vault.get("smtp_password") == "NEW"
    assert client.put("/api/notifications", json=dict(base, smtp_host="smtp.other.example", clear_smtp_password=True)).status_code == 200
    assert vault.get("smtp_password", None) is None

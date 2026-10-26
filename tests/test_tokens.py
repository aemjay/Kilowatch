"""API-Tokens: Rollen, CSRF-Ausnahme nur ohne Cookie-Bezug, Sperre nach Fehlversuchen, Neustartfestigkeit."""
from fastapi.testclient import TestClient

from app.config import Config
from app.main import create_app
from app.security import Tokens


def bearer(token):
    return {"Authorization": "Bearer " + token}


def make(client, role="read", name="Skript"):
    response = client.post("/api/tokens", json={"name": name, "role": role})
    assert response.status_code == 200, response.text
    return response.json()


def test_token_is_shown_once_and_only_its_hash_is_stored(authenticated):
    created = make(authenticated)
    token = created["token"]
    assert token.startswith("kw_") and len(token) >= 3 + 43  # 32 Byte Base64
    listed = authenticated.get("/api/tokens").json()["tokens"]
    assert listed == [{"id": created["id"], "name": "Skript", "role": "read", "created": created["created"], "last_used": None}]
    stored = authenticated.app.state.store.rows("SELECT hash FROM api_tokens")[0]["hash"]
    assert stored == Tokens.digest(token) and token not in stored
    assert token not in authenticated.get("/api/tokens").text


def test_read_token_reads_without_cookie_but_never_writes(client, authenticated):
    token = make(authenticated, "read")["token"]
    plain = TestClient(client.app)  # ohne Cookie und ohne X-Kilowatch-Request
    assert plain.get("/api/live").status_code == 401
    response = plain.get("/api/live", headers=bearer(token))
    assert response.status_code == 200
    assert authenticated.app.state.store.rows("SELECT last_used FROM api_tokens")[0]["last_used"] is not None
    assert plain.put("/api/budget", json={"monthly_eur": 10}, headers=bearer(token)).status_code == 403
    assert plain.get("/api/tokens", headers=bearer(token)).status_code == 403


def test_full_token_writes_without_csrf_header_but_not_tokens_or_password(client, authenticated):
    token = make(authenticated, "full")["token"]
    plain = TestClient(client.app)
    assert plain.put("/api/budget", json={"monthly_eur": 10}, headers=bearer(token)).status_code == 200
    # Auch ein fremder Origin ändert nichts: Der Browser setzt diesen Kopf nie von selbst.
    assert plain.put("/api/budget", json={"monthly_eur": 11}, headers={**bearer(token), "Origin": "http://other"}).status_code == 200
    assert plain.post("/api/tokens", json={"name": "x", "role": "full"}, headers=bearer(token)).status_code == 403
    assert plain.delete("/api/tokens/1", headers=bearer(token)).status_code == 403
    assert plain.put("/api/account/password", json={"current_password": "test-password-long-enough", "new_password": "another-password-1"},
                     headers=bearer(token)).status_code == 403
    # Cookie-Aufrufe brauchen weiterhin den CSRF-Kopf.
    authenticated.headers.pop("X-Kilowatch-Request")
    assert authenticated.put("/api/budget", json={"monthly_eur": 12}).status_code == 403


def test_invalid_tokens_are_throttled_like_logins(client, authenticated):
    token = make(authenticated, "read")["token"]
    plain = TestClient(client.app)
    for _ in range(10):
        assert plain.get("/api/live", headers=bearer("kw_wrong")).status_code == 401
    assert plain.get("/api/live", headers=bearer("kw_wrong")).status_code == 429
    # Während der Sperre wird auch ein gültiges Token dieser Adresse nicht geprüft.
    assert plain.get("/api/live", headers=bearer(token)).status_code == 429


def test_limit_validation_deletion_and_restart(tmp_path):
    config = Config(tmp_path, testing=True)
    app = create_app(config)
    app.state.auth.initialize("test-password-long-enough", app.state.auth.setup_code)
    with TestClient(app, headers={"X-Kilowatch-Request": "1"}) as client:
        client.post("/api/login", json={"password": "test-password-long-enough"})
        assert client.post("/api/tokens", json={"name": "x", "role": "admin"}).status_code == 422
        assert client.post("/api/tokens", json={"name": " \t", "role": "read"}).status_code == 422
        created = [make(client, "full", f"t{i}") for i in range(10)]
        assert client.post("/api/tokens", json={"name": "elf", "role": "read"}).status_code == 400
        assert client.delete(f"/api/tokens/{created[0]['id']}").status_code == 200
        assert client.delete(f"/api/tokens/{created[0]['id']}").status_code == 404
        assert TestClient(app).get("/api/live", headers=bearer(created[0]["token"])).status_code == 401
        kept = created[1]["token"]
    # Neustart beendet Sitzungen, aber keine Tokens.
    restarted = create_app(config)
    with TestClient(restarted) as client:
        assert client.get("/api/live").status_code == 401
        assert client.get("/api/live", headers=bearer(kept)).status_code == 200

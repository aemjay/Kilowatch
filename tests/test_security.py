from fastapi.testclient import TestClient
import pytest

from app.config import Config
from app.main import create_app
from app.security import Vault


def test_first_start_requires_own_password_and_has_no_personal_defaults(tmp_path):
    config=Config(tmp_path, testing=True)
    app=create_app(config)
    with TestClient(app, headers={"X-Kilowatch-Request":"1"}) as client:
        assert client.get("/healthz").status_code==200
        assert client.get("/api/setup/status").json()=={"needs_setup":True}
        # Setup-Code ohne Container-Protokoll: als private Datei im Datenordner.
        code_file=tmp_path/"SETUP-CODE.txt"
        assert app.state.auth.setup_code in code_file.read_text()
        assert code_file.stat().st_mode & 0o077 == 0
        assert "setup_code" not in client.get("/api/setup/status").text
        assert client.get("/api/settings").status_code==401
        assert client.post("/api/setup",json={"setup_code":"wrong","password":"own-synthetic-password"}).status_code==400
        assert client.post("/api/setup",json={"setup_code":app.state.auth.setup_code,"password":"own-synthetic-password"}).status_code==200
        assert not code_file.exists()
        assert client.post("/api/setup",json={"setup_code":"replay","password":"own-synthetic-password"}).status_code==400
        assert client.post("/api/login",json={"password":"own-synthetic-password"}).status_code==200
        settings=client.get("/api/settings").json()
        assert settings["bridge_host"]==""
        assert settings["bridge_user"]=="admin"
        assert settings["setup_required"]
    assert "own-synthetic-password" not in (tmp_path/"secrets/live/app-auth.json").read_text()
    assert not (tmp_path/"live/app-auth.json").exists()
    restarted=create_app(config)
    with TestClient(restarted,headers={"X-Kilowatch-Request":"1"}) as client:
        assert not client.get("/api/setup/status").json()["needs_setup"]
        assert client.post("/api/login",json={"password":"own-synthetic-password"}).status_code==200


def test_password_change_invalidates_sessions(authenticated):
    response=authenticated.put("/api/account/password",json={"current_password":"test-password-long-enough","new_password":"new-synthetic-password"})
    assert response.status_code==200
    assert authenticated.get("/api/live").status_code==401
    assert authenticated.post("/api/login",json={"password":"test-password-long-enough"}).status_code==401
    assert authenticated.post("/api/login",json={"password":"new-synthetic-password"}).status_code==200


def test_vault_encryption_restart_and_explicit_removal(tmp_path):
    vault=Vault(tmp_path)
    vault.update({"bridge_password":"synthetic-secret", "smtp_password":"synthetic-mail-secret"})
    assert b"synthetic-secret" not in vault.path.read_bytes()
    assert b"synthetic-mail-secret" not in vault.path.read_bytes()
    reloaded=Vault(tmp_path)
    assert reloaded.get("bridge_password")=="synthetic-secret"
    reloaded.update({"bridge_password":None})
    assert Vault(tmp_path).get("bridge_password")==""
    assert Vault(tmp_path).get("smtp_password")=="synthetic-mail-secret"


def test_vault_missing_key_does_not_silently_replace_credentials(tmp_path):
    vault=Vault(tmp_path)
    vault.update({"bridge_password":"synthetic-secret"})
    data=vault.path.read_bytes()
    vault.key_path.unlink()
    with pytest.raises(ValueError,match="Schlüssel"):
        Vault(tmp_path)
    assert vault.path.read_bytes()==data


def test_clear_bridge_password_pauses_without_deleting_history(authenticated):
    authenticated.put("/api/settings",json={"bridge_host":"bridge.example.lan","bridge_user":"my-user","bridge_password":"synthetic-secret"})
    assert authenticated.delete("/api/credentials/bridge").status_code==200
    settings=authenticated.get("/api/settings").json()
    assert not settings["password_configured"]
    assert not settings["enabled"]
    assert settings["bridge_host"]=="bridge.example.lan"


def test_secrets_are_kept_outside_the_data_folder(tmp_path):
    config=Config(tmp_path/"data", secrets_dir=tmp_path/"secrets", testing=True)
    app=create_app(config)
    app.state.auth.initialize("own-synthetic-password", app.state.auth.setup_code)
    app.state.vault.update({"bridge_password":"synthetic-secret"})
    data_files={p.name for p in (tmp_path/"data").rglob("*") if p.is_file()}
    assert not data_files & {"secrets.key","secrets.enc","app-auth.json"}
    assert {"secrets.key","secrets.enc","app-auth.json"} <= {p.name for p in (tmp_path/"secrets/live").iterdir()}
    app.state.store.close()


def test_stale_setup_code_file_is_removed_when_already_configured(tmp_path):
    app=create_app(Config(tmp_path, testing=True))
    app.state.auth.initialize("own-synthetic-password", app.state.auth.setup_code)
    (tmp_path/"SETUP-CODE.txt").write_text("old")
    with TestClient(app):
        assert not (tmp_path/"SETUP-CODE.txt").exists()

import pytest

from app.cli import reset_login
from app.security import Auth, Vault


def test_reset_requires_stopped_confirmation_and_preserves_other_data(tmp_path):
    auth = Auth(tmp_path)
    auth.initialize("synthetic-old-password", auth.setup_code)
    vault = Vault(tmp_path)
    vault.update({"bridge_password": "synthetic-bridge-secret"})
    encrypted = vault.path.read_bytes()
    database = tmp_path / "kilowatch.sqlite3"
    database.write_bytes(b"synthetic-test-database")
    with pytest.raises(ValueError, match="confirm-stopped"):
        reset_login(tmp_path)
    assert Auth(tmp_path).verify("synthetic-old-password")
    backup = reset_login(tmp_path, True)
    assert backup.exists()
    fresh = Auth(tmp_path)
    assert not fresh.configured
    assert fresh.setup_code
    fresh.initialize("synthetic-new-password", fresh.setup_code)
    assert fresh.verify("synthetic-new-password")
    assert not fresh.verify("synthetic-old-password")
    assert vault.path.read_bytes() == encrypted
    assert Vault(tmp_path).get("bridge_password") == "synthetic-bridge-secret"
    assert database.read_bytes() == b"synthetic-test-database"


def test_reset_missing_login_is_explicit(tmp_path):
    with pytest.raises(ValueError, match="keine eingerichtete"):
        reset_login(tmp_path, True)

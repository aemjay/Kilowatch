import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.main import create_app
from app.storage import Store


@pytest.fixture
def store(tmp_path):
    db = Store(tmp_path / "db")
    yield db
    db.close()


@pytest.fixture
def client(tmp_path):
    app = create_app(Config(tmp_path, testing=True))
    app.state.auth.initialize("test-password-long-enough", app.state.auth.setup_code)
    with TestClient(app, headers={"X-Kilowatch-Request": "1"}) as c:
        c.app_store = app.state.store
        yield c


@pytest.fixture
def authenticated(client):
    assert client.post("/api/login", json={"password": "test-password-long-enough"}).status_code == 200
    return client

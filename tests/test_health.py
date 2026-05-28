from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    settings = get_settings()
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == settings.app_name
    assert "env" in data


def test_root_returns_landing_page() -> None:
    settings = get_settings()
    response = client.get("/")
    assert response.status_code == 200
    assert settings.app_name in response.text
    assert "missed-call demo" in response.text

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "LeadCare AI"
    assert "env" in data


def test_root_returns_landing_page() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "LeadCare AI" in response.text
    assert "Book a demo" in response.text

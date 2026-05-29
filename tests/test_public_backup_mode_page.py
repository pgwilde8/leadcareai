"""Public Backup Mode marketing page."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_public_backup_mode_page_returns_html(client: TestClient) -> None:
    response = client.get("/backup-mode")
    assert response.status_code == 200
    assert "Backup Mode" in response.text
    assert "When you miss the call" in response.text
    assert "/demo" in response.text
    assert "Joe’s Plumbing" in response.text or "Joe's Plumbing" in response.text
    assert "phone carrier" in response.text.lower() or "carrier" in response.text.lower()

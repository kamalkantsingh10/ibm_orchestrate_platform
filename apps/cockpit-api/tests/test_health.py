"""Integration test for /health (Story 1.2 AC4)."""

from fastapi.testclient import TestClient

from cockpit_api.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_swagger_docs_reachable() -> None:
    client = TestClient(app)
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "swagger" in resp.text.lower()

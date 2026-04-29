"""Integration tests for the demo user-switcher backend (Story 1.4 AC #11)."""

from __future__ import annotations

from contracts.users import ANALYST_ID, REGULATOR_ID, TEAM_LEAD_ID
from fastapi.testclient import TestClient

from cockpit_api.main import app

client = TestClient(app)


def test_returns_analyst_when_header_is_analyst_id() -> None:
    resp = client.get("/v1/users/me", headers={"X-Cockpit-Demo-User": ANALYST_ID})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == ANALYST_ID
    assert body["role"] == "analyst"
    assert body["name"] == "Kamal Singh"


def test_returns_team_lead_when_header_is_team_lead_id() -> None:
    resp = client.get("/v1/users/me", headers={"X-Cockpit-Demo-User": TEAM_LEAD_ID})
    assert resp.status_code == 200
    assert resp.json()["role"] == "team_lead"


def test_returns_regulator_when_header_is_regulator_id() -> None:
    resp = client.get("/v1/users/me", headers={"X-Cockpit-Demo-User": REGULATOR_ID})
    assert resp.status_code == 200
    assert resp.json()["role"] == "regulator"


def test_400s_when_header_missing() -> None:
    resp = client.get("/v1/users/me")
    assert resp.status_code == 400
    assert "X-Cockpit-Demo-User" in resp.json()["detail"]


def test_400s_when_header_is_unknown_uuid() -> None:
    unknown = "00000000-0000-4000-8000-000000999999"
    resp = client.get("/v1/users/me", headers={"X-Cockpit-Demo-User": unknown})
    assert resp.status_code == 400
    assert "X-Cockpit-Demo-User" in resp.json()["detail"]

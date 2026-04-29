"""Smoke test for the cockpit-api scaffold.

Confirms the source layout and dependency graph are wired correctly so
later stories can drop routers/services in. Vitest/pytest harness wiring
into Make targets lands in Story 1.2 (see Story 1.1 References).
"""

from fastapi import FastAPI

from cockpit_api.main import app


def test_app_is_fastapi_instance() -> None:
    assert isinstance(app, FastAPI)


def test_health_route_registered() -> None:
    paths = {route.path for route in app.routes}  # type: ignore[attr-defined]
    assert "/health" in paths

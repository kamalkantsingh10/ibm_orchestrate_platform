"""Smoke test: the agents package is importable.

Real ADK agent definitions land in Epic 3 (Story 3.5+). For now we just
verify the source layout is wired so later stories can drop modules in.
"""

import importlib


def test_agents_package_importable() -> None:
    importlib.import_module("agents")

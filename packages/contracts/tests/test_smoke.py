"""Smoke test: contracts namespace is importable."""

import importlib


def test_contracts_package_importable() -> None:
    importlib.import_module("contracts")

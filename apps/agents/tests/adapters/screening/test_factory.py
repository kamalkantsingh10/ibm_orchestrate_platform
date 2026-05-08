"""Tests for get_default_screening_adapter — Story 6.1 / AC #10."""

from __future__ import annotations

import pytest

from agents.adapters.screening import (
    MockScreeningAdapter,
    get_default_screening_adapter,
)


def test_factory_returns_mock_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCREENING_PROVIDER", raising=False)
    adapter = get_default_screening_adapter()
    assert isinstance(adapter, MockScreeningAdapter)


def test_factory_returns_mock_when_provider_is_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCREENING_PROVIDER", "mock")
    adapter = get_default_screening_adapter()
    assert isinstance(adapter, MockScreeningAdapter)


def test_factory_raises_for_complyadvantage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCREENING_PROVIDER", "complyadvantage")
    with pytest.raises(ValueError, match="Demo only implements 'mock'"):
        get_default_screening_adapter()


def test_factory_raises_for_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCREENING_PROVIDER", "totally-unknown")
    with pytest.raises(ValueError):
        get_default_screening_adapter()

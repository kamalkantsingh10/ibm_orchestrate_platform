"""Screening adapters — Story 6.1.

Pluggable per architecture P1 (Adapter Pattern). Demo ships only the mock;
``SCREENING_PROVIDER=complyadvantage`` raises ``ValueError`` until a real
adapter lands.
"""

from __future__ import annotations

import os

from contracts.screening import ScreeningAdapter

from agents.adapters.screening.mock import MockScreeningAdapter


def get_default_screening_adapter() -> ScreeningAdapter:
    provider = os.getenv("SCREENING_PROVIDER", "mock").lower()
    if provider == "mock":
        return MockScreeningAdapter()
    raise ValueError(
        f"Unknown SCREENING_PROVIDER={provider!r}. Demo only implements 'mock'; ComplyAdvantage adapter deferred."
    )


__all__ = [
    "MockScreeningAdapter",
    "get_default_screening_adapter",
]

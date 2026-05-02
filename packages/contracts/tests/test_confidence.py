"""Tests for the confidence band contract — Story 3.3 / AC #2, #8."""

from __future__ import annotations

import math

import pytest

from contracts.confidence import THRESHOLDS, ConfidenceBand, to_band

# ───────────── golden cases ─────────────


@pytest.mark.parametrize(
    ("confidence", "expected"),
    [
        (0.0, ConfidenceBand.LOW),
        (0.39, ConfidenceBand.LOW),
        (0.40, ConfidenceBand.MEDIUM_LOW),
        (0.64, ConfidenceBand.MEDIUM_LOW),
        (0.65, ConfidenceBand.MEDIUM_HIGH),
        (0.84, ConfidenceBand.MEDIUM_HIGH),
        (0.85, ConfidenceBand.HIGH),
        (1.0, ConfidenceBand.HIGH),
    ],
)
def test_to_band_golden_cases(confidence: float, expected: ConfidenceBand) -> None:
    assert to_band(confidence) == expected


# ───────────── error cases ─────────────


@pytest.mark.parametrize(
    "bad",
    [
        -0.1,
        1.1,
        math.nan,
        math.inf,
    ],
)
def test_to_band_rejects_out_of_range(bad: float) -> None:
    with pytest.raises(ValueError, match="confidence must be in"):
        to_band(bad)


# ───────────── THRESHOLDS structure ─────────────


def test_thresholds_in_declining_order() -> None:
    mins = [m for _, m in THRESHOLDS]
    assert mins == sorted(mins, reverse=True)


def test_thresholds_cover_full_range() -> None:
    bands_in_table = {b for b, _ in THRESHOLDS}
    assert bands_in_table == set(ConfidenceBand)


# ───────────── enum value parity ─────────────


def test_confidence_band_string_values() -> None:
    assert ConfidenceBand("low") == ConfidenceBand.LOW
    assert ConfidenceBand("medium_low") == ConfidenceBand.MEDIUM_LOW
    assert ConfidenceBand("medium_high") == ConfidenceBand.MEDIUM_HIGH
    assert ConfidenceBand("high") == ConfidenceBand.HIGH

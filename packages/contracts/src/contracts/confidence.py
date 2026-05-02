"""Confidence band contract — Story 3.3.

Internal confidence is a ``[0.0, 1.0]`` float; UI-facing confidence is a
4-tier banded enum derived at exactly one boundary in each language. See
architecture.md § P7. The TypeScript mirror lives at
``apps/cockpit-ui/src/lib/confidence.ts``; a parity test asserts the
thresholds match across languages.
"""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Final


class ConfidenceBand(StrEnum):
    """Four-tier confidence banding. Wire format is snake_case."""

    LOW = "low"
    MEDIUM_LOW = "medium_low"
    MEDIUM_HIGH = "medium_high"
    HIGH = "high"


# Tuple of (band, lower_bound) in declining order. ``to_band`` iterates this
# and returns the first band whose threshold is satisfied.
THRESHOLDS: Final[tuple[tuple[ConfidenceBand, float], ...]] = (
    (ConfidenceBand.HIGH, 0.85),
    (ConfidenceBand.MEDIUM_HIGH, 0.65),
    (ConfidenceBand.MEDIUM_LOW, 0.40),
    (ConfidenceBand.LOW, 0.0),
)


def to_band(confidence: float) -> ConfidenceBand:
    """Map a ``[0.0, 1.0]`` confidence to its band.

    Raises ``ValueError`` for ``NaN``, ``inf``, negative, or >1.0 inputs.
    Out-of-range values are not silently clamped — they signal upstream bugs.
    """
    if math.isnan(confidence) or math.isinf(confidence):
        raise ValueError(f"confidence must be in [0.0, 1.0], got {confidence}")
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError(f"confidence must be in [0.0, 1.0], got {confidence}")
    for band, threshold in THRESHOLDS:
        if confidence >= threshold:
            return band
    # Unreachable: the THRESHOLDS table covers [0.0, 1.0] exhaustively.
    return ConfidenceBand.LOW

"""Provenance contract — Story 3.3.

Every datum surfaced to the cockpit UI is wrapped in ``ProvenancedField[T]``
so reviewers can trace value → confidence → originating ledger entries.
See architecture.md § P3.

The band-vs-confidence consistency check (``@model_validator``) prevents
inconsistent pairs from leaking past the boundary. Construct via
``Provenance(... confidence=c, confidence_band=to_band(c) ...)``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field, field_validator, model_validator

from contracts.confidence import ConfidenceBand, to_band
from contracts.ledger import LedgerEntryId

T = TypeVar("T")


class Provenance(BaseModel):
    """Per-datum provenance metadata."""

    model_config = {"frozen": True, "use_enum_values": False}

    source_agent: str = Field(min_length=1)
    source_system: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_band: ConfidenceBand
    evidence_ids: list[LedgerEntryId] = Field(default_factory=list)
    captured_at: datetime

    @field_validator("captured_at")
    @classmethod
    def _captured_at_must_be_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware (UTC)")
        return value

    @model_validator(mode="after")
    def _band_must_match_confidence(self) -> Provenance:
        expected = to_band(self.confidence)
        if expected != self.confidence_band:
            raise ValueError(
                f"confidence_band {self.confidence_band.value!r} inconsistent with "
                f"confidence {self.confidence}; expected {expected.value!r}"
            )
        return self


class ProvenancedField(BaseModel, Generic[T]):
    """A value paired with its provenance.

    ``T`` accepts any Pydantic-serializable type: ``str``, ``int``, ``float``,
    ``bool``, ``dict[str, Any]``, ``list[...]``, ``datetime``, ``None``-able
    variants, etc.
    """

    model_config = {"frozen": True, "use_enum_values": False}

    value: T
    provenance: Provenance

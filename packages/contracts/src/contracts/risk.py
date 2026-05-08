"""Risk scoring contracts — Story 5.6.

Five-component decomposed risk score. The agent is rule-based (no LLM) so
``model_id="deterministic"``. Wire format:

* ``total`` — integer 0–100.
* ``band`` — 3-tier ``RiskBand``: low (0–34), medium (35–69), high (70–100).
  Distinct from the 4-tier ``ConfidenceBand`` (used elsewhere for Pydantic
  ``Provenance`` banding) and the ``cases.risk_band`` column (also 4-tier;
  the supervisor maps 3→4 at the column boundary).
* ``components`` — five named contributors, each with a value, weight, and
  precomputed ``contribution = value * weight``.
* ``score_provenance`` — the total expressed as a ``ProvenancedField[float]``
  in [0.0, 1.0] for P3 compliance.

Validators enforce: weights sum to 1.0 (±0.01); total = round(sum of
contributions); band derives from total; score_provenance.value ==
total/100.0; provenance band is HIGH (deterministic confidence 0.85).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from contracts.cases import CaseId
from contracts.confidence import ConfidenceBand
from contracts.provenance import ProvenancedField

RiskBand = Literal["low", "medium", "high"]
RiskComponentName = Literal[
    "country",
    "entity_type",
    "ownership_clarity",
    "screening",
    "adverse_media",
]


def band_for_total(total: int) -> RiskBand:
    """3-tier risk band derivation. Pinned thresholds per AC1."""
    if total >= 70:
        return "high"
    if total >= 35:
        return "medium"
    return "low"


class RiskComponent(BaseModel):
    model_config = {"frozen": True}

    name: RiskComponentName
    value: float = Field(ge=0.0, le=100.0)
    weight: float = Field(ge=0.0, le=1.0)
    contribution: float = Field(ge=0.0, le=100.0)
    rationale: str = Field(min_length=1, max_length=200)


class RiskScore(BaseModel):
    model_config = {"frozen": True}

    case_id: CaseId
    total: int = Field(ge=0, le=100)
    band: RiskBand
    components: list[RiskComponent] = Field(default_factory=list)
    score_provenance: ProvenancedField[float]

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> RiskScore:
        if not self.components:
            return self
        total_weight = sum(c.weight for c in self.components)
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"Risk component weights sum to {total_weight:.3f}; expected 1.0 ± 0.01")
        return self

    @model_validator(mode="after")
    def _total_matches_contributions(self) -> RiskScore:
        if not self.components:
            return self
        contributions_sum = sum(c.contribution for c in self.components)
        expected_total = round(contributions_sum)
        if abs(self.total - expected_total) > 1:
            raise ValueError(
                f"total={self.total} differs from round(sum(contributions))={expected_total} by more than 1"
            )
        return self

    @model_validator(mode="after")
    def _band_matches_total(self) -> RiskScore:
        expected = band_for_total(self.total)
        if expected != self.band:
            raise ValueError(f"band={self.band!r} inconsistent with total={self.total}; expected {expected!r}")
        return self

    @model_validator(mode="after")
    def _score_provenance_consistent(self) -> RiskScore:
        expected_value = self.total / 100.0
        if abs(self.score_provenance.value - expected_value) > 0.01:
            raise ValueError(
                f"score_provenance.value={self.score_provenance.value:.3f} differs from"
                f" total/100.0={expected_value:.3f} by more than 0.01"
            )
        if self.score_provenance.provenance.confidence_band != ConfidenceBand.HIGH:
            raise ValueError("score_provenance must use HIGH confidence band (deterministic agent)")
        return self


class RiskScoringInput(BaseModel):
    model_config = {"frozen": True}

    case_id: CaseId

"""Reasoning trace contract — Story 6.4.

The 4-section, non-skippable reasoning trace agents attach to their
`AgentActionLedgerEntry`. See architecture.md § P8 (Counterfactual
Reasoning Trace Pattern) and prd.md Innovation #2.

Empty fields are a contract-level error, not a runtime branch — a trace
exists only when all four sections carry meaning. Agents that can't (or
won't) populate a section emit `reasoning_trace=None` on the parent
ledger entry instead of half-populating.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from contracts.confidence import ConfidenceBand, to_band


class ConfidenceWithRationale(BaseModel):
    """Confidence float with an agent-emitted rationale string.

    Used inside `ReasoningTrace.confidence_self_rating`. Re-usable by
    future agents needing a richer "why this confidence?" signal than
    `ProvenancedField[T]` provides.
    """

    model_config = {"frozen": True}

    value: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=12, max_length=400)
    band: ConfidenceBand

    @model_validator(mode="after")
    def _band_matches_value(self) -> ConfidenceWithRationale:
        expected = to_band(self.value)
        if self.band != expected:
            raise ValueError(f"band {self.band!r} does not match value {self.value} (expected {expected!r})")
        return self


class ReasoningTrace(BaseModel):
    """The 4-section, non-skippable reasoning trace.

    Min-lengths are deliberate: nothing below ~12 chars is meaningful in
    any of these slots; this is the contract enforcement that Innovation
    #2 demands. The 600-char ceiling on counterfactual is shorter than
    what_hit because the counterfactual is meant to be a sharp single
    sentence, not a paragraph.
    """

    model_config = {"frozen": True}

    what_searched: str = Field(min_length=12, max_length=1000)
    what_hit: str = Field(min_length=12, max_length=2000)
    confidence_self_rating: ConfidenceWithRationale
    counterfactual: str = Field(min_length=12, max_length=600)


class IncompleteReasoningTraceError(ValueError):
    """Raised when an agent's attached reasoning_trace fails contract validation.

    The decorator catches Pydantic `ValidationError` from a runtime
    `ReasoningTrace` construction and re-raises this typed error so the
    caller (the supervisor's typed `AgentExecutionError` catch path) can
    branch on it cleanly.
    """

    def __init__(self, agent_id: str, errors: list[dict[str, object]]) -> None:
        self.agent_id = agent_id
        self.errors = errors
        sections = sorted(
            {str(loc[0]) if isinstance((loc := e.get("loc")), tuple | list) and loc else "?" for e in errors}
        )
        super().__init__(f"agent {agent_id!r} produced an incomplete reasoning trace; failing sections: {sections}")

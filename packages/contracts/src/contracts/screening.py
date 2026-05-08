"""Screening contracts — Story 6.1.

The Screening agent (Story 6.2) takes a `ScreeningRequest` of one or more
`ScreeningSubject` rows (entity / director / UBO) and asks a configured
vendor for sanctions / PEP / adverse-media hits. The demo ships only the
mock adapter (`MockScreeningAdapter`); the Protocol stays open so a real
vendor (e.g. ComplyAdvantage) can drop in later.

Wire format is snake_case (architecture.md § Naming Patterns / Format
Patterns). `name_match_score` is wrapped in `ProvenancedField[float]` so
each hit carries provenance + confidence band per P3.
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from contracts.cases import CaseId
from contracts.provenance import ProvenancedField

ScreeningCategory = Literal[
    "sanctions",
    "pep",
    "adverse_media",
    "law_enforcement",
    "watchlist",
]

HitDisposition = Literal[
    "open",  # default — officer review pending
    "dismissed_by_agent",  # auto-filtered — see Story 6-2 AC
    "confirmed_by_officer",
    "dismissed_by_officer",
]


class ScreeningSubject(BaseModel):
    """A single name+DOB+identifier triple to screen."""

    model_config = {"frozen": True}

    subject_kind: Literal["entity", "director", "ubo"]
    subject_id: str = Field(min_length=1)
    full_name: str = Field(min_length=1, max_length=200)
    date_of_birth: date | None = None
    identifiers: dict[str, str] = Field(default_factory=dict)


class ScreeningRequest(BaseModel):
    model_config = {"frozen": True}

    case_id: CaseId
    subjects: list[ScreeningSubject] = Field(min_length=1, max_length=50)


class ScreeningHit(BaseModel):
    """One match from one subject against the vendor's index."""

    model_config = {"frozen": True}

    hit_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    matched_name: str = Field(min_length=1, max_length=200)
    name_match_score: ProvenancedField[float]
    date_of_birth: date | None = None
    identifiers: dict[str, str] = Field(default_factory=dict)
    categories: list[ScreeningCategory] = Field(min_length=1)
    source_lists: list[str] = Field(default_factory=list)
    disposition: HitDisposition = "open"
    dismissal_rationale: str | None = None


class ScreeningTemporaryError(RuntimeError):
    """Vendor unreachable / rate-limited / 5xx — supervisor escalates with retry-marker."""


class ScreeningPermanentError(RuntimeError):
    """Vendor 4xx (bad request, bad key, dropped subscription) — case blocks."""


class ScreeningAdapter(Protocol):
    """All screening vendors implement this. Demo ships only the mock."""

    async def screen(self, req: ScreeningRequest) -> list[ScreeningHit]: ...


class ScreeningAgentInput(BaseModel):
    """Input shape for the Story 6.2 Screening agent.

    Subjects are built by the supervisor from upstream agent outputs
    (Entity Verification + UBO Graph) — the agent receives them ready-built.
    """

    model_config = {"frozen": True}

    case_id: CaseId
    subjects: list[ScreeningSubject] = Field(min_length=1, max_length=50)


class ScreeningAgentOutput(BaseModel):
    """Output of the Screening agent.

    ``hits`` includes auto-dismissed entries — the UI shows the dismissed
    ones in a collapsed group so officers can re-include if needed.
    """

    model_config = {"frozen": True}

    case_id: CaseId
    hits: list[ScreeningHit] = Field(default_factory=list)
    subjects_screened: int = Field(ge=1)

"""Entity Verification contracts — Story 5.1.

The Entity Verification agent (in
``apps/agents/src/agents/intake/entity_verification.py``) takes a CIN +
case-id, calls the MCA lookup tool (Story 5.2), diffs case-side fields
against the MCA company-master, and returns this typed result. The
``mca_status`` field is a ``ProvenancedField`` so the cockpit-ui can
render the value with confidence + provenance pills.

``MCAStatus`` is owned by ``contracts.mca`` (single source of truth).
``evidence_ids`` are intentionally empty in the agent's return value — the
supervisor (Story 3.5) re-reads the agent's own ``agent.completed`` ledger
entry and back-fills ``[entry.id]`` before persistence.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from contracts.cases import CaseId
from contracts.mca import MCAStatus
from contracts.provenance import ProvenancedField


class FieldMismatch(BaseModel):
    model_config = {"frozen": True}

    field_name: str = Field(min_length=1)
    case_value: str | None = None
    mca_value: str | None = None
    severity: Literal["info", "warning", "critical"] = "warning"
    notes: str | None = None


class EntityVerificationInput(BaseModel):
    model_config = {"frozen": True}

    case_id: CaseId
    cin: str = Field(
        min_length=21,
        max_length=21,
        pattern=r"^[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$",
    )


class EntityVerificationResult(BaseModel):
    model_config = {"frozen": True}

    case_id: CaseId
    cin: str
    mca_status: ProvenancedField[MCAStatus]
    mismatches: list[FieldMismatch] = Field(default_factory=list)

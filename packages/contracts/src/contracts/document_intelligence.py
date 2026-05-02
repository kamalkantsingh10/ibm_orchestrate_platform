"""Document Intelligence agent contracts — Story 3.4.

The agent (lives in ``apps/agents/src/agents/intake/document_intelligence.py``)
takes a list of document refs for a case, runs a doc-AI LLM call (fixture
or watsonx, picked at runtime by ``DOC_AI_PROVIDER``), and returns each
extracted field with provenance + confidence.

``evidence_ids`` are intentionally empty in the agent's return value — the
orchestrating Case Supervisor (Story 3-5) re-reads the agent's own
``agent.completed`` ledger entry and back-fills ``[entry.id]`` before
exposing results to the API/UI.
"""

from __future__ import annotations

from typing import Annotated, TypeAlias

from pydantic import BaseModel, Field, StringConstraints

from contracts.cases import CaseId
from contracts.provenance import ProvenancedField

# ───────────────────────────── value types ──────────────────────────────────

FieldValue: TypeAlias = str | int | float | bool | None
"""Any extracted field value the demo's India taxonomy produces."""

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]


# ───────────────────────────── input ────────────────────────────────────────


class DocumentIntelligenceInput(BaseModel):
    model_config = {"frozen": True}

    case_id: CaseId
    document_refs: list[NonEmptyStr] = Field(min_length=0)


# ───────────────────────────── extracted fields ────────────────────────────


class ExtractedField(BaseModel):
    model_config = {"frozen": True}

    field_name: NonEmptyStr
    document_ref: NonEmptyStr
    value: ProvenancedField[FieldValue]


# ───────────────────────────── output ──────────────────────────────────────


class DocumentIntelligenceOutput(BaseModel):
    """Aggregate of ExtractedFields across all input document_refs.

    Note (Story 3.4 § AC8): ``evidence_ids`` inside each ``ExtractedField.value``
    are empty when the agent returns. The supervisor (Story 3-5) back-fills
    them with the agent's own ledger-entry ID after ``@agent_action`` writes
    the entry.
    """

    model_config = {"frozen": True}

    case_id: CaseId
    extracted_fields: list[ExtractedField] = Field(default_factory=list)

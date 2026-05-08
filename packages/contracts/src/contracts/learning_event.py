"""Learning-event contracts — Story 5.5.

Officer drag-correct on the UBO graph produces a typed ``learning_event``
ledger entry. The bank-buyer scope's Ed25519 signing was cut from the demo
(see ``architecture.md#Demo Scope Addendum``) — officer attribution is via
``actor_id`` only (the user-switcher's current user from Story 1.4).

The ``opt_in_for_retraining`` flag is captured for future use but has no
current downstream consumer; its value is in the audit trail.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from contracts.cases import CaseId
from contracts.ledger import LearningEventLedgerPayload, LedgerEntryId
from contracts.ubo import UBONodeId

# Re-export the typed ledger payload so callers have a single import surface.
__all__ = (
    "CorrectionTag",
    "LearningEventInput",
    "LearningEventLedgerPayload",
    "LearningEventResponse",
)

CorrectionTag = Literal["real_ubo", "nominee", "director", "removed"]


class LearningEventInput(BaseModel):
    """POST body for ``/v1/cases/{case_id}/ubo/learning-events``."""

    model_config = {"frozen": True}

    edge_kind: Literal["owns", "director", "beneficial"]
    from_id: UBONodeId
    original_to_id: UBONodeId
    new_to_id: UBONodeId
    correction_tag: CorrectionTag
    evidence_note: str = Field(min_length=1, max_length=500)
    opt_in_for_retraining: bool = False


class LearningEventResponse(BaseModel):
    """Server-side response after persisting + writing the ledger entry."""

    model_config = {"frozen": True}

    ledger_entry_id: LedgerEntryId
    case_id: CaseId
    recorded_at: datetime

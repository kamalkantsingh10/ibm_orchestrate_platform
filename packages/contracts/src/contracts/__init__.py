"""Pydantic source-of-truth contracts shared across cockpit-api and agents."""

from __future__ import annotations

from contracts.agent_action import (
    AgentActionLedgerEntry,
    ErrorInfo,
    PromptHash,
)
from contracts.case_supervisor import CaseIntakeOutcome
from contracts.cases import (
    ALLOWED_TRANSITIONS,
    ANANYA_IYER_ID,
    SHREE_VENKAT_ID,
    VORA_CAPITAL_ID,
    Case,
    CaseId,
    CaseState,
    CaseStateTransitionError,
    CustomerMetadata,
    assert_transition,
    get_demo_case_fixtures,
    is_valid_case_id,
)
from contracts.confidence import THRESHOLDS, ConfidenceBand, to_band
from contracts.document_intelligence import (
    DocumentIntelligenceInput,
    DocumentIntelligenceOutput,
    ExtractedField,
    FieldValue,
)
from contracts.ledger import (
    ActorType,
    LedgerEntry,
    LedgerEntryId,
    is_valid_ledger_entry_id,
)
from contracts.provenance import Provenance, ProvenancedField
from contracts.users import (
    ANALYST_ID,
    DEMO_USERS,
    REGULATOR_ID,
    TEAM_LEAD_ID,
    Role,
    User,
    find_user_by_id,
)

__all__ = [
    "ALLOWED_TRANSITIONS",
    "ANALYST_ID",
    "ANANYA_IYER_ID",
    "ActorType",
    "AgentActionLedgerEntry",
    "Case",
    "CaseId",
    "CaseIntakeOutcome",
    "CaseState",
    "CaseStateTransitionError",
    "ConfidenceBand",
    "CustomerMetadata",
    "DEMO_USERS",
    "DocumentIntelligenceInput",
    "DocumentIntelligenceOutput",
    "ErrorInfo",
    "ExtractedField",
    "FieldValue",
    "LedgerEntry",
    "LedgerEntryId",
    "PromptHash",
    "Provenance",
    "ProvenancedField",
    "REGULATOR_ID",
    "Role",
    "SHREE_VENKAT_ID",
    "TEAM_LEAD_ID",
    "THRESHOLDS",
    "User",
    "VORA_CAPITAL_ID",
    "assert_transition",
    "find_user_by_id",
    "get_demo_case_fixtures",
    "is_valid_case_id",
    "is_valid_ledger_entry_id",
    "to_band",
]

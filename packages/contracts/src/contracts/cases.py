"""Case contract — Story 2.1.

Single source of truth for the case aggregate shape and the lifecycle state
machine. Consumed by ``cockpit-api`` (router + repo) and ``apps/agents``.

Design notes:
* IDs are ``case_<ULID>``. Crockford-Base32, 26-char body. Lexicographically
  sortable by creation time, but the queue rail in Story 2-3 still orders by
  the ``created_at`` column to keep cursor pagination dialect-portable.
* The state machine lives in **Python**, not the DB. SQLite has no native
  ``ENUM`` and a Postgres ``ENUM`` type would be hell to migrate; the column
  is a ``String`` and ``assert_transition`` is the gate.
* ``risk_band`` is a plain nullable string here. When the Risk Scoring agent
  lands (Epic 5), it will be wrapped in ``ProvenancedField[...]`` — but the
  ``Case`` aggregate itself is a system-of-record entity, not an agent
  extraction, so it does not carry provenance metadata.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

from contracts.users import ANALYST_ID

# ───────────────────────────── identifier ──────────────────────────────────

# Crockford-Base32 excludes I, L, O, U. ULID body is 26 chars.
_CASE_ID_PATTERN = r"^case_[0-9A-HJKMNP-TV-Z]{26}$"

CaseId = Annotated[
    str,
    StringConstraints(pattern=_CASE_ID_PATTERN, min_length=31, max_length=31),
]
"""``case_<26-char Crockford-Base32 ULID>``."""

_case_id_re = re.compile(_CASE_ID_PATTERN)


def is_valid_case_id(value: str) -> bool:
    """Return True if ``value`` matches the ``case_<ULID>`` shape."""
    return bool(_case_id_re.match(value))


# ───────────────────────────── state machine ───────────────────────────────


class CaseState(StrEnum):
    """Lifecycle states. See ``ALLOWED_TRANSITIONS`` for the edge set."""

    INTAKE_SCHEDULED = "intake_scheduled"
    DECISION_READY = "decision_ready"
    COMMITTED = "committed"
    ESCALATED = "escalated"
    CLOSED = "closed"


ALLOWED_TRANSITIONS: dict[CaseState, set[CaseState]] = {
    CaseState.INTAKE_SCHEDULED: {
        CaseState.DECISION_READY,
        CaseState.ESCALATED,
        CaseState.CLOSED,
    },
    CaseState.DECISION_READY: {
        CaseState.COMMITTED,
        CaseState.ESCALATED,
        CaseState.CLOSED,
    },
    CaseState.COMMITTED: {CaseState.CLOSED},
    CaseState.ESCALATED: {CaseState.COMMITTED, CaseState.CLOSED},
    CaseState.CLOSED: set(),  # terminal
}
"""Adjacency map for the case lifecycle. Edges not listed are forbidden."""


class CaseStateTransitionError(ValueError):
    """Raised when a caller attempts a transition outside ``ALLOWED_TRANSITIONS``."""


def assert_transition(current: CaseState, target: CaseState) -> None:
    """Raise ``CaseStateTransitionError`` if ``current → target`` is not allowed."""
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise CaseStateTransitionError(f"Illegal case state transition: {current.value} → {target.value}")


# ───────────────────────────── customer metadata ───────────────────────────


class CustomerMetadata(BaseModel):
    """Customer-side facts attached to a case.

    ``extra`` is an extensibility escape hatch so fixtures (Story 2-4) can carry
    demo-only fields without schema churn. Production code should prefer named
    fields over ``extra`` once the bank-buyer scope revives.
    """

    model_config = {"frozen": True}

    customer_name: str = Field(min_length=1)
    customer_type: Literal["individual", "company"] | None = None
    country: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


# ───────────────────────────── case aggregate ──────────────────────────────


class Case(BaseModel):
    """The case aggregate. Wire format mirrors this contract 1:1."""

    model_config = {"frozen": True, "use_enum_values": False}

    id: CaseId
    state: CaseState
    customer_metadata: CustomerMetadata
    assigned_to_user_id: str | None = None
    risk_band: Literal["low", "medium_low", "medium_high", "high"] | None = None
    created_at: datetime
    updated_at: datetime
    closure_date: datetime | None = None


# ───────────────────────────── demo fixtures ───────────────────────────────
#
# Story 2.4 — three pinned cases that load via ``make seed`` and back the
# demo's narrative arc (Journey 1 happy path, Journey 2 EDD escalation,
# Journey 3 screening hit). IDs are pinned ULIDs whose timestamp prefix
# decodes to 2026-04-29 morning so they sort lexicographically in the
# same order they were authored.
#
# The ``customer_metadata.extra`` keys (``ubo_chain_hint``,
# ``screening_hit_hint``, ``document_refs``, etc.) are forward-compat hints
# — Epic 3+ agents will read them as their input data. They are NOT
# validated by Pydantic; treat them as soft conventions documented here.

SHREE_VENKAT_ID = "case_01KQC7EWM0GYHP15CZ8JB5ZT69"
VORA_CAPITAL_ID = "case_01KQC7GQ70GYHP15CZ8JB5ZT6A"
ANANYA_IYER_ID = "case_01KQC7JHT0GYHP15CZ8JB5ZT6B"


def get_demo_case_fixtures(now: datetime) -> list[Case]:
    """Return the three demo fixture cases pinned at seed time.

    ``now`` is the seeder's clock; the three cases are spaced 5 minutes
    apart so the queue rail (Story 2-3) renders them in journey order
    (Ananya newest at top → Vora middle → Shree oldest at bottom).

    Forward-compat ``extra`` keys (consumed by Epic 3+ agents):
    * ``document_refs`` — list of filenames; resolved by the local-filesystem
      object storage adapter once Epic 3 lands.
    * ``ubo_chain_hint`` (Vora only) — pre-shaped UBO graph the
      UBO Graph agent (Epic 5) returns when running in mock mode.
    * ``screening_hit_hint`` (Ananya only) — synthetic match the
      Screening agent (Epic 6) explains via the 3-column card.
    """

    shree = Case(
        id=SHREE_VENKAT_ID,
        state=CaseState.INTAKE_SCHEDULED,
        customer_metadata=CustomerMetadata(
            customer_name="Shree Venkat Trading",
            customer_type="company",
            country="IN",
            extra={
                "registration_number": "U51900MH2018PTC312456",
                "incorporation_date": "2018-03-15",
                "registered_address": "Plot 14, MIDC Industrial Area, Pune, Maharashtra 411019",
                "business_description": "Wholesale distribution of consumer electronics",
                "annual_revenue_inr": 47_000_000,
                "expected_monthly_volume_inr": 8_500_000,
                "primary_contact_name": "Venkat Reddy",
                "primary_contact_role": "Director",
                "document_refs": [
                    "incorporation_certificate.pdf",
                    "pan_card.pdf",
                    "address_proof.pdf",
                    "director_id.pdf",
                ],
            },
        ),
        assigned_to_user_id=ANALYST_ID,
        risk_band=None,
        created_at=now - timedelta(minutes=12),
        updated_at=now - timedelta(minutes=12),
        closure_date=None,
    )

    vora = Case(
        id=VORA_CAPITAL_ID,
        state=CaseState.INTAKE_SCHEDULED,
        customer_metadata=CustomerMetadata(
            customer_name="Vora Capital Holdings Pvt Ltd",
            customer_type="company",
            country="IN",
            extra={
                "registration_number": "U67120MH2024PTC444789",
                "incorporation_date": "2024-08-22",
                "registered_address": "Suite 402, Sea Breeze Heights, Bandra West, Mumbai 400050",
                "alternate_address_flag": True,
                "business_description": "Investment advisory and asset management",
                "annual_revenue_inr": 120_000_000,
                "expected_monthly_volume_inr": 35_000_000,
                "primary_contact_name": "Devansh Vora",
                "primary_contact_role": "Director",
                "ubo_chain_hint": [
                    {"name": "Vora Capital Holdings Pvt Ltd", "country": "IN"},
                    {"name": "Coastal Equity Partners Pte Ltd", "country": "SG"},
                    {"name": "Anchor Trust Services (BVI)", "country": "VG"},
                ],
                "document_refs": [
                    "incorporation_certificate.pdf",
                    "ubo_declaration.pdf",
                    "shareholder_pattern.pdf",
                    "director_id.pdf",
                    "bank_statement_q1.pdf",
                ],
            },
        ),
        assigned_to_user_id=ANALYST_ID,
        risk_band=None,
        created_at=now - timedelta(minutes=7),
        updated_at=now - timedelta(minutes=7),
        closure_date=None,
    )

    ananya = Case(
        id=ANANYA_IYER_ID,
        state=CaseState.INTAKE_SCHEDULED,
        customer_metadata=CustomerMetadata(
            customer_name="Ananya Iyer",
            customer_type="individual",
            country="IN",
            extra={
                "date_of_birth": "1985-11-04",
                "pan": "AAFPI4567Q",
                "residential_address": "Flat 12B, Lake Vista Apartments, Powai, Mumbai 400076",
                "occupation": "Independent consultant",
                "annual_income_inr": 24_000_000,
                "expected_monthly_volume_inr": 2_000_000,
                "screening_hit_hint": {
                    "list_source": "synthetic_demo_sanctions_list",
                    "match_name": "Ananya Iyer",
                    "match_dob": "1985-11-04",
                    "match_score": 0.94,
                    "match_notes": "Demo-only synthetic match. NOT a real sanctions hit.",
                },
                "document_refs": [
                    "pan_card.pdf",
                    "aadhaar.pdf",
                    "address_proof.pdf",
                    "income_proof.pdf",
                ],
            },
        ),
        assigned_to_user_id=ANALYST_ID,
        risk_band=None,
        created_at=now - timedelta(minutes=2),
        updated_at=now - timedelta(minutes=2),
        closure_date=None,
    )

    return [shree, vora, ananya]

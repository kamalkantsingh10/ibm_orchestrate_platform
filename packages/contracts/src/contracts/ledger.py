"""Ledger entry contract — Story 3.1 / Story 3.3.

The append-only ledger is the audit-trail backbone of the demo. Every agent
invocation, supervisor decision, and seeded fixture event lands as one
``LedgerEntry`` line in ``./data/ledger.jsonl``.

Demo simplification (2026-04-29 re-scope): the bank-buyer scope's hash-chain
+ Ed25519 signature primitives are absent. Append-only semantics are enforced
in Python via ``LedgerWriter``'s public surface — see
``cockpit_api.services.ledger_service``.

Story 3.3 upgraded ``payload`` from a plain ``dict`` to a discriminated union
with ``AgentActionLedgerEntry`` as the typed arm. Pydantic resolves the union
left-to-right (typed model first, dict fallback) so existing dict-shaped
seed-loader payloads continue to validate without change.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints, field_validator

from contracts.agent_action import AgentActionLedgerEntry
from contracts.cases import CaseId

# ───────────────────────────── identifier ──────────────────────────────────

# Crockford-Base32 excludes I, L, O, U. ULID body is 26 chars. Mirror of the
# CaseId pattern from Story 2.1 with a different prefix.
_LEDGER_ID_PATTERN = r"^led_[0-9A-HJKMNP-TV-Z]{26}$"

LedgerEntryId = Annotated[
    str,
    StringConstraints(pattern=_LEDGER_ID_PATTERN, min_length=30, max_length=30),
]
"""``led_<26-char Crockford-Base32 ULID>``."""

_ledger_id_re = re.compile(_LEDGER_ID_PATTERN)


def is_valid_ledger_entry_id(value: str) -> bool:
    """Return True if ``value`` matches the ``led_<ULID>`` shape."""
    return bool(_ledger_id_re.match(value))


# ───────────────────────────── actor type ──────────────────────────────────


class ActorType(StrEnum):
    """Who originated the ledger entry. See architecture.md § P4."""

    AGENT = "agent"
    OFFICER = "officer"
    SYSTEM = "system"


# ───────────────────────────── ledger entry ────────────────────────────────


class LedgerEntry(BaseModel):
    """One append-only ledger event.

    The writer overwrites ``id`` and ``recorded_at`` server-side at
    ``append`` time, so caller-supplied values are ignored. Pass any
    pattern-valid ID and any tz-aware ``datetime`` — they will be replaced.
    """

    model_config = {"frozen": True, "use_enum_values": False}

    id: LedgerEntryId
    actor_type: ActorType
    actor_id: str = Field(min_length=1)
    case_id: CaseId | None = None
    action: str = Field(min_length=1, max_length=80)
    # Discriminated union (Story 3.3): ``AgentActionLedgerEntry`` is the typed
    # arm for agent invocations; ``dict[str, Any]`` is the fallback for
    # system/officer events that have no fixed schema yet. Pydantic resolves
    # left-to-right — the typed arm wins when ``kind == "agent_action"``.
    payload: AgentActionLedgerEntry | dict[str, Any] = Field(default_factory=dict)
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def _recorded_at_must_be_tz_aware(cls, value: datetime) -> datetime:
        """Reject naive datetimes — wire format requires explicit UTC."""
        if value.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware (UTC)")
        return value

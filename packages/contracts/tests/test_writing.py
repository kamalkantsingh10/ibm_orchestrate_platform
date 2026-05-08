"""Tests for `contracts.writing` — Story 7.3 / AC #10."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts import (
    CitedClaim,
    DraftedRationale,
    WritingAgentInput,
)
from contracts.cases import VORA_CAPITAL_ID

LED_A = "led_01ABCDEFGHJKMNPQRSTVWXYZ12"
LED_B = "led_01HXY3GHJKMNPQRSTVWXYZ7HX2"


def _drafted(**overrides: object) -> DraftedRationale:
    base: dict[str, object] = {
        "case_id": VORA_CAPITAL_ID,
        "html": (
            f'<p>Approve based on <span data-ledger-id="{LED_A}" class="citation-token">screening hits</span>.</p>'
        ),
        "paragraphs": ["Para A.", "Para B."],
        "cited_claims": [CitedClaim(text="screening hits", evidence_ledger_id=LED_A)],
        "model_id": "fixture-v1",
    }
    base.update(overrides)
    return DraftedRationale(**base)  # type: ignore[arg-type]


def test_drafted_rationale_round_trips_through_json() -> None:
    obj = _drafted()
    parsed = DraftedRationale.model_validate_json(obj.model_dump_json())
    assert parsed == obj


def test_paragraphs_min_length_2_enforced() -> None:
    with pytest.raises(ValidationError):
        _drafted(paragraphs=["only one"])


def test_paragraphs_max_length_4_enforced() -> None:
    with pytest.raises(ValidationError):
        _drafted(paragraphs=["a", "b", "c", "d", "e"])


def test_cited_claim_text_length_bounds_enforced() -> None:
    with pytest.raises(ValidationError):
        CitedClaim(text="", evidence_ledger_id=LED_A)
    with pytest.raises(ValidationError):
        CitedClaim(text="x" * 401, evidence_ledger_id=LED_A)


def test_cited_claim_evidence_ledger_id_shape_validated() -> None:
    with pytest.raises(ValidationError):
        CitedClaim(text="ok", evidence_ledger_id="not-a-ledger-id")


def test_writing_agent_input_round_trips() -> None:
    obj = WritingAgentInput(case_id=VORA_CAPITAL_ID)
    parsed = WritingAgentInput.model_validate_json(obj.model_dump_json())
    assert parsed == obj


def test_drafted_rationale_html_min_length_enforced() -> None:
    with pytest.raises(ValidationError):
        _drafted(html="<p>x</p>")


def test_prompt_template_id_locked_to_v1() -> None:
    with pytest.raises(ValidationError):
        _drafted(prompt_template_id="rationale_draft_v2")


def test_drafted_rationale_carries_multiple_claims() -> None:
    obj = _drafted(
        cited_claims=[
            CitedClaim(text="alpha", evidence_ledger_id=LED_A),
            CitedClaim(text="beta", evidence_ledger_id=LED_B),
        ],
    )
    assert {c.evidence_ledger_id for c in obj.cited_claims} == {LED_A, LED_B}

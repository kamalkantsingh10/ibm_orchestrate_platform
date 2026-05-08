"""Tests for `contracts.writing` — Stories 7.3 (rationale draft) and 8.3 (EDD memo)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts import (
    CitedClaim,
    DraftedRationale,
    EddMemoOutput,
    EddMemoSections,
    WritingAgentInput,
    derive_citations_from_sections,
)
from contracts.cases import VORA_CAPITAL_ID

LED_A = "led_01ABCDEFGHJKMNPQRSTVWXYZ12"
LED_B = "led_01HXY3GHJKMNPQRSTVWXYZ7HX2"
LED_C = "led_01HXY4GHJKMNPQRSTVWXYZ7HX3"


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


# ─── Story 8.3 — EddMemoOutput ──────────────────────────────────────────────


def _memo(**overrides: object) -> EddMemoOutput:
    base: dict[str, object] = {
        "case_id": VORA_CAPITAL_ID,
        "executive_summary": f"Executive summary cites {{{{{LED_A}}}}}.",
        "findings": f"Finding paragraph cites {{{{{LED_B}}}}}.",
        "risk_factors": f"Risk factor paragraph cites {{{{{LED_A}}}}}.",
        "mitigating_factors": "Mitigants do not require a citation here.",
        "recommendation": f"Recommend escalation per {{{{{LED_C}}}}}.",
        "citations": [LED_A, LED_B, LED_C],
        "model_id": "fixture-edd-v1",
    }
    base.update(overrides)
    return EddMemoOutput(**base)  # type: ignore[arg-type]


def test_edd_memo_round_trips_through_json() -> None:
    obj = _memo()
    parsed = EddMemoOutput.model_validate_json(obj.model_dump_json())
    assert parsed == obj


def test_edd_memo_validator_passes_when_inline_tokens_match_citations_list() -> None:
    obj = _memo()
    assert set(obj.citations) == {LED_A, LED_B, LED_C}


def test_edd_memo_validator_rejects_inline_token_missing_from_citations() -> None:
    # Pydantic wraps the CitationStructureError raised inside
    # @model_validator into a ValidationError. The inner error type +
    # message survive in ValidationError.errors() and via match=.
    with pytest.raises(ValidationError, match="missing from `citations`"):
        _memo(citations=[LED_A, LED_B])  # LED_C inline but not in citations


def test_edd_memo_validator_rejects_unreferenced_citation_entry() -> None:
    extra = "led_01ZZZZGHJKMNPQRSTVWXYZ7HX9"
    with pytest.raises(ValidationError, match="never appear inline"):
        _memo(citations=[LED_A, LED_B, LED_C, extra])


def test_edd_memo_validator_accepts_empty_citations_when_no_inline_tokens() -> None:
    obj = _memo(
        executive_summary="Plain text, no citation.",
        findings="More plain text.",
        risk_factors="Risk text.",
        mitigating_factors="Mitigant text.",
        recommendation="Plain recommendation text.",
        citations=[],
    )
    assert obj.citations == []


def test_edd_memo_section_min_length_enforced() -> None:
    with pytest.raises(ValidationError):
        _memo(executive_summary="")


def test_edd_memo_prompt_template_id_locked_to_v1() -> None:
    with pytest.raises(ValidationError):
        _memo(prompt_template_id="edd_memo_v2")


def test_edd_memo_inline_token_format_rejects_non_ulid() -> None:
    # Tokens not matching `led_<26-char Crockford>` are simply ignored
    # by the extractor — they are not "citations" — but if the citations
    # list claims them, the LedgerEntryId field validator on the list
    # itself rejects the malformed id (a Pydantic ValidationError).
    bogus = "led_short"
    with pytest.raises(ValidationError):
        _memo(citations=[LED_A, LED_B, LED_C, bogus])


def test_derive_citations_from_sections_returns_sorted_distinct_ids() -> None:
    sections = EddMemoSections(
        executive_summary=f"cites {{{{{LED_B}}}}}",
        findings=f"cites {{{{{LED_A}}}}} and again {{{{{LED_A}}}}}",
        risk_factors=f"cites {{{{{LED_C}}}}}",
        mitigating_factors="no citation",
        recommendation=f"cites {{{{{LED_B}}}}}",
    )
    assert derive_citations_from_sections(sections) == sorted({LED_A, LED_B, LED_C})


def test_edd_memo_inline_token_extractor_ignores_malformed_braces() -> None:
    # A bare `led_` outside `{{…}}` does NOT count as a citation.
    obj = _memo(
        executive_summary=f"References led_NOT_IN_BRACES and {{{{{LED_A}}}}}.",
        findings=f"Bare {LED_B} text and {{{{{LED_B}}}}}.",
        risk_factors=f"Cites {{{{{LED_C}}}}}.",
        mitigating_factors="No citation.",
        recommendation="Recommend.",
        citations=[LED_A, LED_B, LED_C],
    )
    assert set(obj.citations) == {LED_A, LED_B, LED_C}

"""Writing-agent contracts — Stories 7.3 and 8.3.

Story 7.3 ships v1: a 2–4 paragraph rationale drafter for routine
decisions. Story 8.3 ships v2: a structured EDD memo with five named
sections and inline ``{{led_<ULID>}}`` citation tokens.

Both versions share the agent module, registry, and decorator wrapping;
they differ in prompt template + output schema. v1 emits
``DraftedRationale`` (Tiptap HTML + cited_claims). v2 emits
``EddMemoOutput`` (five plain-text sections + a flat citations list).

Citation hallucination defense is layered: the prompt instructs the
LLM to cite only from a supplied ``ledger_ids`` map; the v2 schema
validator (this module) enforces *structural* consistency between
inline tokens and the ``citations`` list; the cockpit-ui (Story 7.1)
re-validates citations against the live ledger at commit time.
Story 8.4 adds runtime enforcement that every cited ledger id resolves
to a real entry on the case.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from contracts.cases import CaseId
from contracts.ledger import LedgerEntryId


class CitationStructureError(ValueError):
    """Raised when an EDD memo's inline ``{{led_<ULID>}}`` tokens do
    not match the ``citations`` list. Story 8.3 / AC #4. Internal
    consistency only — Story 8.4 owns ledger-existence checks.
    """


class CitedClaim(BaseModel):
    """One factual claim in the drafted rationale, paired with the
    ledger entry that backs it. The LLM emits these in structured JSON;
    the agent assembles them into HTML around each claim's text.
    """

    model_config = {"frozen": True}

    text: str = Field(min_length=1, max_length=400)
    evidence_ledger_id: LedgerEntryId


class DraftedRationale(BaseModel):
    """The Writing agent's output — a structured rationale with
    citations.

    ``html`` is the renderable form for Tiptap (citation tokens already
    wrapped in ``<span data-ledger-id="…">…</span>``). ``paragraphs``
    and ``cited_claims`` carry the structured signal for downstream
    analytics — they are persisted on the intake row but not surfaced
    in the demo UI.
    """

    model_config = {"frozen": True}

    case_id: CaseId
    html: str = Field(min_length=20)
    paragraphs: list[str] = Field(min_length=2, max_length=4)
    cited_claims: list[CitedClaim] = Field(default_factory=list)
    model_id: str = Field(min_length=1)
    prompt_template_id: Literal["rationale_draft_v1"] = "rationale_draft_v1"


class WritingAgentInput(BaseModel):
    """Tool-facing input for the Writing agent. Upstream typed outputs
    are NOT in the input — the supervisor reads them off the case's
    intake row at call time, mirroring Story 6.2's screening agent.
    """

    model_config = {"frozen": True}

    case_id: CaseId


# ─── Story 8.3 — EDD memo (v2) ────────────────────────────────────────────

# `led_<26-char Crockford-Base32>`. Match the format Story 3.3 codifies
# in `LedgerEntryId`; we re-derive the regex here because the tokens are
# embedded in free text rather than top-level fields.
_LEDGER_ID_INNER = r"led_[0-9A-HJKMNP-TV-Z]{26}"
_LEDGER_TOKEN_RE = re.compile(r"\{\{(" + _LEDGER_ID_INNER + r")\}\}")


def _extract_inline_tokens(text: str) -> set[str]:
    """Return the set of ``led_<ULID>`` ids referenced by inline
    ``{{led_<ULID>}}`` tokens in ``text``."""
    return {match.group(1) for match in _LEDGER_TOKEN_RE.finditer(text)}


class EddMemoOutput(BaseModel):
    """The Writing agent's v2 output — a structured EDD narrative memo
    with five named sections. Story 8.3 / AC #3.

    Inline citations follow the ``{{led_<ULID>}}`` token format inside
    each section's text. The ``citations`` list is the flat union of
    every distinct token referenced anywhere in the memo. The
    ``model_validator`` on this class enforces that the two surfaces
    agree (AC #4).

    The output is plain text by design: cockpit-ui renders the sections
    as Tiptap headings + paragraphs and rewrites ``{{led_<ULID>}}``
    tokens into ``<span data-ledger-id="led_…">`` chips at render time
    (Story 8.3 / AC #7).
    """

    model_config = {"frozen": True}

    case_id: CaseId
    executive_summary: str = Field(min_length=1)
    findings: str = Field(min_length=1)
    risk_factors: str = Field(min_length=1)
    mitigating_factors: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    citations: list[LedgerEntryId] = Field(default_factory=list)
    model_id: str = Field(min_length=1)
    prompt_template_id: Literal["edd_memo_v1"] = "edd_memo_v1"

    @model_validator(mode="after")
    def _enforce_inline_citations_match(self) -> EddMemoOutput:
        """Story 8.3 / AC #4 — every inline ``{{led_<ULID>}}`` token in
        any of the five section fields must appear in ``citations``,
        and every entry in ``citations`` must be referenced by at least
        one inline token. Mismatch raises ``CitationStructureError``.
        """
        inline_ids: set[str] = set()
        for section_text in (
            self.executive_summary,
            self.findings,
            self.risk_factors,
            self.mitigating_factors,
            self.recommendation,
        ):
            inline_ids.update(_extract_inline_tokens(section_text))
        listed = set(self.citations)
        unlisted = inline_ids - listed
        if unlisted:
            raise CitationStructureError(
                "Inline citation tokens missing from `citations` list: " + ", ".join(sorted(unlisted))
            )
        unreferenced = listed - inline_ids
        if unreferenced:
            raise CitationStructureError(
                "Entries in `citations` list never appear inline: " + ", ".join(sorted(unreferenced))
            )
        return self


class EddMemoSections(BaseModel):
    """Internal Pydantic model returned by an LLM-shaped ``WritingLLM``
    for the ``edd_memo`` mode. The agent assembles the final
    ``EddMemoOutput`` (with ``case_id``, ``citations`` derived from
    inline tokens, etc.) from this raw shape.
    """

    model_config = {"frozen": True}

    executive_summary: str = Field(min_length=1)
    findings: str = Field(min_length=1)
    risk_factors: str = Field(min_length=1)
    mitigating_factors: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)


def derive_citations_from_sections(sections: EddMemoSections) -> list[str]:
    """Walk every section and return the sorted list of distinct ledger
    ids referenced by inline ``{{led_<ULID>}}`` tokens. The agent feeds
    this into ``EddMemoOutput.citations`` so the model_validator's
    structural check is by construction satisfied for well-formed LLM
    output."""
    found: set[str] = set()
    for text in (
        sections.executive_summary,
        sections.findings,
        sections.risk_factors,
        sections.mitigating_factors,
        sections.recommendation,
    ):
        found.update(_extract_inline_tokens(text))
    return sorted(found)

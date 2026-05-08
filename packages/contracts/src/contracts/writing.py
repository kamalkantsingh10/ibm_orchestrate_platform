"""Writing-agent contracts — Story 7.3.

The Writing agent runs after intake completes (case is in
``decision_ready``). It synthesizes a 2–4 paragraph rationale draft from
the latest typed outputs of the upstream agents (Document Intelligence,
Entity Verification, UBO Graph, Screening, Risk Scoring) and emits two
parallel surfaces:

* ``html`` — Tiptap-renderable HTML with citation tokens already wrapped
  as ``<span data-ledger-id="led_…" class="citation-token">…</span>``
  so Story 7.1's Decision Zone editor can pre-load it without further
  transformation.
* ``cited_claims`` — the structured (claim_text, ledger_id) pairs the
  LLM emitted, kept on the contract for downstream analytics
  (edit-rate, citation density). The bank-buyer scope tracked these;
  the demo persists them but does not surface them.

Citation hallucination defense is layered: the prompt instructs the
LLM to cite only from a supplied ``ledger_ids`` map, and the cockpit-ui
(Story 7.1) re-validates every citation against the case ledger at
commit time. Server-side, the wrapper trusts ``cited_claims`` as-is.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from contracts.cases import CaseId
from contracts.ledger import LedgerEntryId


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

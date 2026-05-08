"""Writing agent — Story 7.3 / AC #4.

Synthesizes a 2–4 paragraph rationale from the case's intake-row
outputs and emits Tiptap-renderable HTML with citation tokens.

Defense-in-depth on citation correctness:
* The Jinja prompt instructs the LLM to cite only from a supplied
  ``ledger_ids`` map.
* The wrapper helper escapes HTML special chars in paragraph + claim
  text and only inserts ``<span data-ledger-id>`` for cited claims
  whose ``evidence_ledger_id`` is supplied.
* Story 7.1's commit-time validator (``findBrokenCitations``)
  re-validates against the live ledger before allowing commit.
"""

from __future__ import annotations

import html
from pathlib import Path

from contracts.cases import Case
from contracts.confidence import to_band
from contracts.document_intelligence import DocumentIntelligenceOutput
from contracts.entity_verification import EntityVerificationResult
from contracts.reasoning_trace import ConfidenceWithRationale, ReasoningTrace
from contracts.risk import RiskScore
from contracts.screening import ScreeningAgentOutput
from contracts.ubo import UBOGraph
from contracts.writing import (
    CitedClaim,
    DraftedRationale,
    EddMemoOutput,
    WritingAgentInput,
    derive_citations_from_sections,
)
from jinja2 import Environment, FileSystemLoader, select_autoescape

from agents.adapters.writing import WritingLLM, get_default_writing_llm
from agents.adapters.writing.base import RawRationaleDraft
from agents.supervisor.action_decorator import (
    agent_action,
    set_runtime_model_id,
    set_runtime_reasoning_trace,
)

_PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts" / "writing"


def _build_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_PROMPT_DIR),
        autoescape=select_autoescape(default=False),
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )


_ENV = _build_jinja_env()


@agent_action(
    agent_id="writing",
    model_id="placeholder",  # overwritten via set_runtime_model_id at call time
    prompt_template_id="rationale_draft_v1",
)
async def writing(
    input: WritingAgentInput,
    *,
    case: Case,
    doc_intel: DocumentIntelligenceOutput,
    entity_verification: EntityVerificationResult | None,
    ubo: UBOGraph | None,
    screening: ScreeningAgentOutput | None,
    risk: RiskScore | None,
    ledger_ids: dict[str, str],
    llm: WritingLLM | None = None,
) -> DraftedRationale:
    resolved = llm if llm is not None else get_default_writing_llm()
    set_runtime_model_id(resolved.model_id)

    rendered_prompt = _render_prompt_v1(
        case=case,
        doc_intel=doc_intel,
        entity_verification=entity_verification,
        ubo=ubo,
        screening=screening,
        risk=risk,
        ledger_ids=ledger_ids,
    )
    raw = await resolved.draft_rationale(rendered_prompt=rendered_prompt)
    output_html = _wrap_html_with_citations(raw)
    set_runtime_reasoning_trace(_build_trace(raw, ledger_ids))

    return DraftedRationale(
        case_id=input.case_id,
        html=output_html,
        paragraphs=raw.paragraphs,
        cited_claims=raw.cited_claims,
        model_id=resolved.model_id,
        prompt_template_id="rationale_draft_v1",
    )


def _render_prompt_v1(
    *,
    case: Case,
    doc_intel: DocumentIntelligenceOutput,
    entity_verification: EntityVerificationResult | None,
    ubo: UBOGraph | None,
    screening: ScreeningAgentOutput | None,
    risk: RiskScore | None,
    ledger_ids: dict[str, str],
) -> str:
    template = _ENV.get_template("rationale_draft_v1.j2")
    entity_status = entity_verification.mca_status if entity_verification else None
    ubo_summary: str | None
    if ubo is not None:
        nominee_count = sum(1 for e in ubo.edges if getattr(e, "nominee_flag", None) == "suspected")
        ubo_summary = f"{len(ubo.nodes)} nodes, {nominee_count} nominee-suspected edges"
    else:
        ubo_summary = None
    screening_summary: str | None
    if screening is not None:
        open_count = sum(1 for h in screening.hits if h.disposition == "open")
        dismissed = sum(1 for h in screening.hits if h.disposition == "dismissed_by_agent")
        screening_summary = (
            f"{open_count} open hits, {dismissed} auto-dismissed across {screening.subjects_screened} subject(s)"
        )
    else:
        screening_summary = None
    risk_summary: str | None
    if risk is not None:
        component_summary = ", ".join(f"{c.name} {c.contribution}" for c in risk.components[:3])
        risk_summary = f"total {risk.total}/100, band {risk.band}; {component_summary} dominate"
    else:
        risk_summary = None

    return template.render(
        case=case.model_dump(mode="json"),
        extracted_fields=doc_intel.extracted_fields if doc_intel else None,
        entity_status=entity_status,
        ubo_summary=ubo_summary,
        screening_summary=screening_summary,
        risk_summary=risk_summary,
        ledger_ids=ledger_ids,
    )


def _wrap_html_with_citations(raw: RawRationaleDraft) -> str:
    """Assemble HTML by walking each paragraph; for each cited_claim
    whose ``text`` appears in the paragraph, replace the first
    occurrence with the citation span. Multi-claim paragraphs work
    because each claim's text is matched independently.

    HTML escaping defends against LLM-injected markup; the citation
    span is the only HTML the wrapper introduces.
    """
    if not raw.paragraphs:
        return "<p></p>"
    paragraphs_html: list[str] = []
    for paragraph in raw.paragraphs:
        rendered = html.escape(paragraph)
        for claim in raw.cited_claims:
            escaped_text = html.escape(claim.text)
            if escaped_text not in rendered:
                continue
            citation = (
                f'<span data-ledger-id="{html.escape(claim.evidence_ledger_id)}" '
                f'class="citation-token">{escaped_text}</span>'
            )
            rendered = rendered.replace(escaped_text, citation, 1)
        paragraphs_html.append(f"<p>{rendered}</p>")
    return "".join(paragraphs_html)


def _build_trace(
    raw: RawRationaleDraft,
    ledger_ids: dict[str, str],
) -> ReasoningTrace:
    available_ids = [v for v in ledger_ids.values() if v]
    cited_ids = {c.evidence_ledger_id for c in raw.cited_claims}
    coverage = len(cited_ids.intersection(available_ids)) / len(available_ids) if available_ids else 0.0
    confidence = max(0.05, min(0.99, coverage))
    cited_summary = ", ".join(sorted(cited_ids)) if cited_ids else "(none)"
    return ReasoningTrace(
        what_searched=(
            "Synthesized a rationale from the latest case agent outputs "
            "(Document Intelligence, Entity Verification, UBO Graph, "
            "Screening, Risk Scoring)."
        ),
        what_hit=(
            f"Generated {len(raw.paragraphs)} paragraphs citing {len(cited_ids)} ledger entries: {cited_summary}."
        ),
        confidence_self_rating=ConfidenceWithRationale(
            value=confidence,
            rationale=(
                "Confidence reflects how many available agent outputs the "
                "rationale cites — full coverage is high; partial is lower."
            ),
            band=to_band(confidence),
        ),
        counterfactual=(
            "Draft would change if the officer corrects an upstream agent "
            "output (e.g., UBO drag-correct) and the case re-enters "
            "decision_ready, or if the writing template is updated."
        ),
    )


# ─── Story 8.3 — Writing v2: EDD memo drafter ────────────────────────────────


@agent_action(
    agent_id="writing",
    model_id="placeholder",  # overwritten via set_runtime_model_id at call time
    prompt_template_id="edd_memo_v1",
)
async def writing_edd_memo(
    input: WritingAgentInput,
    *,
    case: Case,
    doc_intel: DocumentIntelligenceOutput,
    entity_verification: EntityVerificationResult | None,
    ubo: UBOGraph | None,
    screening: ScreeningAgentOutput | None,
    risk: RiskScore | None,
    ledger_ids: dict[str, str],
    llm: WritingLLM | None = None,
) -> EddMemoOutput:
    """Story 8.3 — drafts a structured EDD narrative memo (five sections,
    inline ``{{led_<ULID>}}`` citations). The Case Supervisor invokes
    this on ``escalate_to_edd`` outcomes (Story 7.9 wires the trigger
    via the decision-service post-commit path)."""
    resolved = llm if llm is not None else get_default_writing_llm()
    set_runtime_model_id(resolved.model_id)

    rendered_prompt = _render_edd_memo_prompt_v1(
        case=case,
        doc_intel=doc_intel,
        entity_verification=entity_verification,
        ubo=ubo,
        screening=screening,
        risk=risk,
        ledger_ids=ledger_ids,
    )
    sections = await resolved.draft_edd_memo(rendered_prompt=rendered_prompt)
    citations = derive_citations_from_sections(sections)
    set_runtime_reasoning_trace(_build_edd_trace(sections, ledger_ids, citations))

    return EddMemoOutput(
        case_id=input.case_id,
        executive_summary=sections.executive_summary,
        findings=sections.findings,
        risk_factors=sections.risk_factors,
        mitigating_factors=sections.mitigating_factors,
        recommendation=sections.recommendation,
        citations=citations,
        model_id=resolved.model_id,
        prompt_template_id="edd_memo_v1",
    )


def _render_edd_memo_prompt_v1(
    *,
    case: Case,
    doc_intel: DocumentIntelligenceOutput,
    entity_verification: EntityVerificationResult | None,
    ubo: UBOGraph | None,
    screening: ScreeningAgentOutput | None,
    risk: RiskScore | None,
    ledger_ids: dict[str, str],
) -> str:
    template = _ENV.get_template("edd_memo_v1.j2")
    entity_status = entity_verification.mca_status if entity_verification else None
    ubo_summary: str | None
    if ubo is not None:
        nominee_count = sum(1 for e in ubo.edges if getattr(e, "nominee_flag", None) == "suspected")
        ubo_summary = f"{len(ubo.nodes)} nodes, {nominee_count} nominee-suspected edges"
    else:
        ubo_summary = None
    screening_summary: str | None
    if screening is not None:
        open_count = sum(1 for h in screening.hits if h.disposition == "open")
        dismissed = sum(1 for h in screening.hits if h.disposition == "dismissed_by_agent")
        screening_summary = (
            f"{open_count} open hits, {dismissed} auto-dismissed across {screening.subjects_screened} subject(s)"
        )
    else:
        screening_summary = None
    risk_summary: str | None
    if risk is not None:
        component_summary = ", ".join(f"{c.name} {c.contribution}" for c in risk.components[:3])
        risk_summary = f"total {risk.total}/100, band {risk.band}; {component_summary} dominate"
    else:
        risk_summary = None

    return template.render(
        case=case.model_dump(mode="json"),
        extracted_fields=doc_intel.extracted_fields if doc_intel else None,
        entity_status=entity_status,
        ubo_summary=ubo_summary,
        screening_summary=screening_summary,
        risk_summary=risk_summary,
        ledger_ids=ledger_ids,
    )


def _build_edd_trace(
    sections: object,  # EddMemoSections; typed as object to dodge a forward import
    ledger_ids: dict[str, str],
    citations: list[str],
) -> ReasoningTrace:
    available_ids = [v for v in ledger_ids.values() if v]
    cited = set(citations)
    coverage = len(cited.intersection(available_ids)) / len(available_ids) if available_ids else 0.0
    confidence = max(0.05, min(0.99, coverage))
    cited_summary = ", ".join(sorted(cited)) if cited else "(none)"
    return ReasoningTrace(
        what_searched=(
            "Synthesized a structured EDD memo from the latest case agent "
            "outputs (Document Intelligence, Entity Verification, UBO Graph, "
            "Screening, Risk Scoring), targeting five named sections."
        ),
        what_hit=(f"Generated five sections citing {len(cited)} ledger entries: {cited_summary}."),
        confidence_self_rating=ConfidenceWithRationale(
            value=confidence,
            rationale=(
                "Confidence reflects how many available agent outputs the EDD "
                "memo cites — full coverage is high; partial is lower."
            ),
            band=to_band(confidence),
        ),
        counterfactual=(
            "Memo would change if the officer corrects an upstream agent "
            "output and the case re-enters decision_ready, or if the EDD "
            "memo template is updated."
        ),
    )


__all__ = [
    "CitedClaim",
    "DraftedRationale",
    "EddMemoOutput",
    "WritingAgentInput",
    "writing",
    "writing_edd_memo",
]

"""Entity Verification agent — Story 5.1.

Calls the MCA lookup tool (Story 5.2) for the case's CIN, diffs case-side
fields against the MCA company-master, returns a typed
``EntityVerificationResult``. Every invocation lands in the ledger via
``@agent_action``.

The supervisor (Story 3.5) builds the ``EntityCaseView`` from the case +
Document Intelligence intake row and passes it in as a keyword arg, so
this agent function stays pure-ish and trivially testable.

Interim limitation (Story 5.1 dev notes § Pitfalls #8): the
``@agent_action`` decorator does not currently capture sub-tool calls.
The ledger entry's ``payload.tool_calls`` is therefore an empty list even
though this function calls the ``mca_lookup`` tool exactly once. Story
6.x's reasoning-trace work will revisit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from contracts.confidence import to_band
from contracts.entity_verification import (
    EntityVerificationInput,
    EntityVerificationResult,
    FieldMismatch,
)
from contracts.mca import MCACompanyMaster, MCAStatus
from contracts.provenance import Provenance, ProvenancedField
from contracts.reasoning_trace import ConfidenceWithRationale, ReasoningTrace

from agents.supervisor.action_decorator import agent_action, set_runtime_reasoning_trace
from agents.tools.mca_lookup import MCALookup, get_default_mca_lookup

# ───────────────────────────── case-view ──────────────────────────────────


@dataclass(frozen=True)
class EntityCaseView:
    """Case-side projection of the four fields Entity Verification diffs.

    Built by the supervisor from the case + DocumentIntelligenceOutput;
    passed into the agent so the agent itself remains pure(-ish).
    """

    company_name: str | None
    registered_address: str | None
    incorporation_date: str | None
    cin: str | None


# ───────────────────────────── normalization ──────────────────────────────

_PUNCT = ".,;:!?'\"()[]{}<>-_/\\"


def _normalize(value: str | None) -> str:
    """Lowercase + collapse whitespace + strip leading/trailing punctuation.

    ``None`` and empty become the empty string. Used by ``_compute_mismatches``
    to compare case-side and MCA-side strings tolerantly.
    """
    if value is None:
        return ""
    folded = value.lower().strip().strip(_PUNCT).strip()
    # Collapse runs of whitespace.
    return " ".join(folded.split())


# ───────────────────────────── diff helper ────────────────────────────────


def _compute_mismatches(
    case_view: EntityCaseView,
    master: MCACompanyMaster,
) -> list[FieldMismatch]:
    """Compare case-side fields against MCA-side; emit typed mismatches.

    Diff rules per AC3:
    * Both non-empty + normalized strings differ → ``warning`` (or
      ``critical`` for ``incorporation_date``).
    * MCA has the field, case does not → ``info``, "MCA has field; case does not".
    * Case has the field, MCA does not → ``info``, "Case has field; MCA does not".
    * Both empty → no mismatch.
    """
    mismatches: list[FieldMismatch] = []

    pairs: list[tuple[str, str | None, str | None]] = [
        ("company_name", case_view.company_name, master.company_name),
        ("registered_address", case_view.registered_address, master.registered_office),
        ("incorporation_date", case_view.incorporation_date, master.incorporation_date),
    ]

    for field_name, case_value, mca_value in pairs:
        case_norm = _normalize(case_value)
        mca_norm = _normalize(mca_value)
        if not case_norm and not mca_norm:
            continue
        if case_norm and mca_norm and case_norm == mca_norm:
            continue

        severity: Literal["info", "warning", "critical"]
        notes: str | None
        if case_norm and not mca_norm:
            severity = "info"
            notes = "Case has field; MCA does not"
        elif mca_norm and not case_norm:
            severity = "info"
            notes = "MCA has field; case does not"
        else:
            # Both present, normalized values differ.
            severity = "critical" if field_name == "incorporation_date" else "warning"
            notes = None

        mismatches.append(
            FieldMismatch(
                field_name=field_name,
                case_value=case_value,
                mca_value=mca_value,
                severity=severity,
                notes=notes,
            )
        )

    return mismatches


# ───────────────────────────── provenance ─────────────────────────────────


def _mock_status_provenance() -> Provenance:
    """Provenance for the mock-derived MCA status.

    Confidence is deliberately high (mock is deterministic) but not 1.0 to
    leave headroom for the bank-buyer revival's real MCA wrapper.
    ``evidence_ids`` are intentionally empty — the supervisor (Story 3.5)
    back-fills with the agent's own ledger ID after the decorator writes
    the entry.
    """
    confidence = 0.95
    return Provenance(
        source_agent="entity_verification",
        source_system="mca_mock",
        confidence=confidence,
        confidence_band=to_band(confidence),
        evidence_ids=[],
        captured_at=datetime.now(UTC),
    )


# ───────────────────────────── agent function ─────────────────────────────


@agent_action(
    agent_id="entity_verification",
    model_id="deterministic",
    prompt_template_id=None,
)
async def entity_verification(
    input: EntityVerificationInput,
    *,
    mca: MCALookup | None = None,
    case_view: EntityCaseView | None = None,
) -> EntityVerificationResult:
    """Run the MCA cross-reference for ``input.cin`` and surface mismatches.

    ``mca`` and ``case_view`` are explicit dependencies so the agent stays
    trivially testable. Production callers (the supervisor) inject both;
    direct HTTP callers (the ADK boundary) use the resolver default and an
    empty ``case_view`` (no document-intelligence context available).
    """
    resolved_mca = mca if mca is not None else get_default_mca_lookup()
    master = await resolved_mca.lookup(cin=input.cin)

    status_value: MCAStatus = master.status
    pf_status: ProvenancedField[MCAStatus] = ProvenancedField(
        value=status_value,
        provenance=_mock_status_provenance(),
    )

    mismatches: list[FieldMismatch]
    if case_view is None:
        # No case-side context — emit info rows for the four fields the
        # agent diffs, marking them as "case has no value".
        empty_view = EntityCaseView(
            company_name=None,
            registered_address=None,
            incorporation_date=None,
            cin=input.cin,
        )
        mismatches = _compute_mismatches(empty_view, master)
    else:
        mismatches = _compute_mismatches(case_view, master)

    result = EntityVerificationResult(
        case_id=input.case_id,
        cin=input.cin,
        mca_status=pf_status,
        mismatches=mismatches,
    )
    set_runtime_reasoning_trace(_build_trace(input, result))
    return result


def _build_trace(input: EntityVerificationInput, result: EntityVerificationResult) -> ReasoningTrace:
    """Build the agent-level 4-section ReasoningTrace per Story 6.4 / AC #7."""
    mismatch_summary = (
        ", ".join(f"{m.field_name} ({m.severity})" for m in result.mismatches) if result.mismatches else "none"
    )
    return ReasoningTrace(
        what_searched=(
            f"Looked up CIN {input.cin!r} in the configured MCA company-master "
            f"and diffed against the case's intake-derived view."
        ),
        what_hit=(
            f"MCA status: {result.mca_status.value}. {len(result.mismatches)} field mismatch(es): {mismatch_summary}."
        ),
        confidence_self_rating=ConfidenceWithRationale(
            value=result.mca_status.provenance.confidence,
            rationale=(
                "Confidence reflects the MCA tool's self-reported confidence "
                "in the company-master record (the mock returns 0.95 deterministically)."
            ),
            band=result.mca_status.provenance.confidence_band,
        ),
        counterfactual=(
            "Status would change if the case's CIN points to a different "
            "company-master record on the next MCA refresh, or if officer "
            "evidence resolves the address/name mismatch."
        ),
    )

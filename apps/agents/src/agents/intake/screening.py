"""Screening agent — Story 6.2.

Calls the configured `ScreeningAdapter` (Story 6.1 — mock-only in the demo)
for the case's entity + directors + UBO subjects, applies the demo's
auto-dismissal rules to low-quality hits, and returns a typed
`ScreeningAgentOutput`. Every invocation lands one ledger entry via
`@agent_action`.

The supervisor (Story 6.2 / 3.5) builds `ScreeningAgentInput.subjects` from
upstream agent outputs (Entity Verification + UBO Graph) and passes them in.
This agent function is pure(-ish) — the adapter dependency is injectable so
tests can stub it; production callers (supervisor + cockpit-api router) let
the factory resolve the default.

Auto-dismissal thresholds are agent constants by design — different vendors
calibrate name-match scores differently. Don't lift them into
`packages/contracts/`.
"""

from __future__ import annotations

from datetime import date

from contracts.confidence import to_band
from contracts.reasoning_trace import ConfidenceWithRationale, ReasoningTrace
from contracts.screening import (
    ScreeningAdapter,
    ScreeningAgentInput,
    ScreeningAgentOutput,
    ScreeningHit,
    ScreeningRequest,
)

from agents.adapters.screening import get_default_screening_adapter
from agents.supervisor.action_decorator import agent_action, set_runtime_reasoning_trace

_DISMISS_SCORE_THRESHOLD = 0.50
"""Hits below this score are always auto-dismissed."""

_DISMISS_DOB_MUST_MATCH_BELOW = 0.65
"""Below this score, a DOB mismatch (when both DOBs are known) auto-dismisses too."""


@agent_action(
    agent_id="screening",
    model_id="deterministic",  # mock adapter is rule-based, not LLM-driven
    prompt_template_id=None,
)
async def screening(
    input: ScreeningAgentInput,
    *,
    adapter: ScreeningAdapter | None = None,
) -> ScreeningAgentOutput:
    """Run the configured screening adapter and apply auto-dismissal.

    `adapter` is an explicit kwarg dependency for testability — the
    supervisor doesn't pass it; the agent resolves the default at call time.
    """
    resolved = adapter if adapter is not None else get_default_screening_adapter()
    req = ScreeningRequest(case_id=input.case_id, subjects=input.subjects)

    raw_hits = await resolved.screen(req)

    subject_dob = {s.subject_id: s.date_of_birth for s in input.subjects}
    processed = [_dispositioned(hit, subject_dob.get(hit.subject_id)) for hit in raw_hits]

    set_runtime_reasoning_trace(_build_trace(input, processed))

    return ScreeningAgentOutput(
        case_id=input.case_id,
        hits=processed,
        subjects_screened=len(input.subjects),
    )


def _build_trace(input: ScreeningAgentInput, processed: list[ScreeningHit]) -> ReasoningTrace:
    """Build the agent-level 4-section ReasoningTrace per Story 6.4 / AC #6."""
    open_hits = [h for h in processed if h.disposition == "open"]
    dismissed = [h for h in processed if h.disposition == "dismissed_by_agent"]
    avg_confidence = sum(h.name_match_score.value for h in processed) / len(processed) if processed else 1.0
    if open_hits:
        what_hit_lines = "Open hits: " + "; ".join(
            f"{h.matched_name} ({', '.join(h.categories)}) at score {h.name_match_score.value:.2f}" for h in open_hits
        )
        counterfactual = (
            "Disposition would change if officer-supplied evidence (DOB, "
            "ID document, address) confirms or refutes the matched identity."
        )
    else:
        what_hit_lines = "No officer-actionable hits."
        counterfactual = (
            "Result would change if a re-run with additional subjects (e.g., newly "
            "identified directors) returns hits, or if the screening provider's "
            "list refresh surfaces a new match."
        )
    return ReasoningTrace(
        what_searched=(
            f"Screened {len(input.subjects)} subject(s) "
            f"({', '.join(s.subject_kind for s in input.subjects)}) "
            f"against the configured screening provider."
        ),
        what_hit=(
            f"Returned {len(processed)} match(es): {len(open_hits)} open, "
            f"{len(dismissed)} auto-dismissed. {what_hit_lines}"
        ),
        confidence_self_rating=ConfidenceWithRationale(
            value=avg_confidence,
            rationale=(
                f"Confidence is the mean name-match score across {len(processed)} returned "
                f"hit(s); a clean (no-hit) result is treated as high confidence."
            ),
            band=to_band(avg_confidence),
        ),
        counterfactual=counterfactual,
    )


def _dispositioned(hit: ScreeningHit, subject_dob: date | None) -> ScreeningHit:
    """Return a copy of `hit` with `disposition` and `dismissal_rationale` set."""
    score = hit.name_match_score.value

    if score < _DISMISS_SCORE_THRESHOLD:
        return hit.model_copy(
            update={
                "disposition": "dismissed_by_agent",
                "dismissal_rationale": f"low name match ({score:.2f})",
            }
        )

    if (
        score < _DISMISS_DOB_MUST_MATCH_BELOW
        and subject_dob is not None
        and hit.date_of_birth is not None
        and subject_dob != hit.date_of_birth
    ):
        return hit.model_copy(
            update={
                "disposition": "dismissed_by_agent",
                "dismissal_rationale": (f"medium-low name match ({score:.2f}) and DOB differs"),
            }
        )

    # Default: open for officer review (already the contract default; assert it).
    return hit.model_copy(update={"disposition": "open", "dismissal_rationale": None})

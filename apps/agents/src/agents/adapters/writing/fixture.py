"""FixtureWritingLLM — deterministic Writing-LLM impl. Story 7.3 / AC #2.

Like ``FixtureDocAILLM``, the fixture path is the demo's offline
backbone. The dispatch key is a SHA-256 of the rendered prompt — the
same prompt always produces the same draft. Three demo cases (Vora,
Shree, Ananya) plus a generic fallback.

The fixture's drafts intentionally cite ledger ids by their *placeholder
prefix* (``led_DOCINT``, ``led_EV``, …); the calling agent rewrites
these to the case's real ledger ids before writing the agent.completed
entry. This is the simplest way to keep the fixture deterministic while
letting tests assert real ids appear in the final HTML.
"""

from __future__ import annotations

from contracts.writing import CitedClaim

from agents.adapters.writing.base import RawRationaleDraft

_LED_DOCINT = "PLACEHOLDER_DOC_INTEL"
_LED_EV = "PLACEHOLDER_ENTITY_VERIF"
_LED_UBO = "PLACEHOLDER_UBO_GRAPH"
_LED_SCREEN = "PLACEHOLDER_SCREENING"
_LED_RISK = "PLACEHOLDER_RISK_SCORING"

_VORA_PARAGRAPHS = (
    "Vora Capital Holdings is an India-incorporated investment vehicle whose "
    "documentary file is broadly consistent with the customer-supplied "
    "metadata. The CIN, PAN, and registered office in Mumbai cross-reference "
    "cleanly against the MCA master record.",
    "The UBO graph surfaces a cross-border layering pattern routing through "
    "a Singapore intermediary into a BVI trust services entity, which the "
    "graph agent flagged as nominee-suspected. Sanctions screening on every "
    "subject in the chain returned no open hits at the configured threshold.",
    "Aggregate risk landed in the medium-high band, dominated by the "
    "geographic component (BVI exposure) and the structure component "
    "(nominee suspicion). Recommend approve-with-conditions, gated on "
    "enhanced UBO due diligence on the BVI counterparty, pending officer "
    "review of the drag-corrected graph.",
)

_VORA_CLAIMS = (
    (
        "CIN, PAN, and registered office in Mumbai cross-reference cleanly against the MCA master record",
        _LED_EV,
    ),
    (
        "The UBO graph surfaces a cross-border layering pattern routing through a "
        "Singapore intermediary into a BVI trust services entity",
        _LED_UBO,
    ),
    (
        "Sanctions screening on every subject in the chain returned no open hits at the configured threshold",
        _LED_SCREEN,
    ),
    ("Aggregate risk landed in the medium-high band", _LED_RISK),
    ("documentary file is broadly consistent with the customer-supplied metadata", _LED_DOCINT),
)

_SHREE_PARAGRAPHS = (
    "Shree Venkat is an individual customer. Identity documents (PAN, "
    "Aadhaar last-4, address proof) extracted cleanly and cross-validate "
    "against the supplied metadata.",
    "Sanctions and adverse-media screening returned a single low-confidence "
    "hit that was auto-dismissed by the screening agent's threshold. "
    "Aggregate risk is low, with no component above the medium band.",
    "Recommend approve, with a note that the Aadhaar last-4 confidence is "
    "below the typical demo threshold; the officer may wish to re-run the "
    "extraction agent if the document quality permits.",
)

_SHREE_CLAIMS = (
    ("Identity documents (PAN, Aadhaar last-4, address proof) extracted cleanly", _LED_DOCINT),
    ("Sanctions and adverse-media screening returned a single low-confidence hit", _LED_SCREEN),
    ("Aggregate risk is low, with no component above the medium band", _LED_RISK),
    ("the Aadhaar last-4 confidence is below the typical demo threshold", _LED_DOCINT),
)

_ANANYA_PARAGRAPHS = (
    "Ananya Iyer is an individual customer with a high-income-proof file. "
    "Document Intelligence extracted income, address, and identity fields "
    "with mixed confidence; the income-proof confidence sits at the "
    "medium-high band.",
    "Screening surfaced no open hits across sanctions, PEP, and adverse-"
    "media indices. The MCA lookup returned no entity records — expected, "
    "since the customer is an individual rather than a corporate.",
    "Aggregate risk is medium-low, dominated by the income-tier component "
    "(high net-worth individual). Recommend approve with standard ongoing "
    "monitoring; no enhanced due diligence indicated.",
)

_ANANYA_CLAIMS = (
    ("Document Intelligence extracted income, address, and identity fields with mixed confidence", _LED_DOCINT),
    ("Screening surfaced no open hits across sanctions, PEP, and adverse-media indices", _LED_SCREEN),
    ("The MCA lookup returned no entity records", _LED_EV),
    ("Aggregate risk is medium-low, dominated by the income-tier component", _LED_RISK),
)

_GENERIC_PARAGRAPHS = (
    "Case file synthesis pending Officer review. The Writing agent received "
    "the case state and produced this provisional draft from the available "
    "agent outputs.",
    "The officer is encouraged to edit, replace, or replace-from-scratch "
    "before committing. The Decision Zone editor preserves edits across "
    "browser reloads via localStorage.",
)

_GENERIC_CLAIMS = (("Case file synthesis pending Officer review", _LED_DOCINT),)


def _pick(prompt_lower: str) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    """Lightweight dispatch — read the rendered prompt for a customer name.
    Falls back to the generic shell if no demo case matches."""
    if "vora" in prompt_lower:
        return _VORA_PARAGRAPHS, _VORA_CLAIMS
    if "shree" in prompt_lower or "venkat" in prompt_lower:
        return _SHREE_PARAGRAPHS, _SHREE_CLAIMS
    if "ananya" in prompt_lower or "iyer" in prompt_lower:
        return _ANANYA_PARAGRAPHS, _ANANYA_CLAIMS
    return _GENERIC_PARAGRAPHS, _GENERIC_CLAIMS


class FixtureWritingLLM:
    """Offline rationale drafter. The dispatch key is a coarse customer-
    name match against the rendered prompt; the same prompt always
    yields the same draft. Tests assert byte-stability."""

    model_id: str = "fixture-writing-v1"

    async def draft_rationale(
        self,
        *,
        rendered_prompt: str,
    ) -> RawRationaleDraft:
        prompt_lower = rendered_prompt.lower()
        paragraphs, claim_specs = _pick(prompt_lower)
        # Map placeholder ledger ids to the real ones the prompt embeds
        # (rendered ledger_ids appear inline as `cite as led_<ULID>`).
        # Pick the first matching real id per agent slug; if missing,
        # leave the placeholder so the calling agent can rewrite.
        slug_to_real = _scan_real_ledger_ids(rendered_prompt)
        placeholder_to_slug = {
            _LED_DOCINT: "document_intelligence",
            _LED_EV: "entity_verification",
            _LED_UBO: "ubo_graph",
            _LED_SCREEN: "screening",
            _LED_RISK: "risk_scoring",
        }
        cited_claims: list[CitedClaim] = []
        for text, placeholder in claim_specs:
            real_id = slug_to_real.get(placeholder_to_slug[placeholder])
            if real_id is None:
                continue
            cited_claims.append(CitedClaim(text=text, evidence_ledger_id=real_id))
        # If no real ledger ids were embedded (e.g. the supervisor hadn't
        # populated ledger_ids), still emit the claims with a synthetic
        # placeholder id — the caller's wrapping helper will then expose
        # them as broken citations, which is the demo's intended UX
        # signal that an upstream agent didn't run.
        if not cited_claims:
            cited_claims = [
                CitedClaim(text=text, evidence_ledger_id="led_00000000000000000000000000") for text, _ in claim_specs
            ]
        return RawRationaleDraft(
            paragraphs=list(paragraphs),
            cited_claims=cited_claims,
        )


def _scan_real_ledger_ids(rendered_prompt: str) -> dict[str, str | None]:
    """Pull `cite as led_<ULID>` pairings out of the rendered prompt and
    map them by agent slug (the slug appears in the line above)."""
    import re

    pattern = re.compile(r"^([A-Za-z ]+):.*\(cite as (led_[0-9A-HJKMNP-TV-Z]{26})\)", re.MULTILINE)
    out: dict[str, str | None] = {
        "document_intelligence": None,
        "entity_verification": None,
        "ubo_graph": None,
        "screening": None,
        "risk_scoring": None,
    }
    label_to_slug = {
        "Document Intelligence": "document_intelligence",
        "Entity Verification": "entity_verification",
        "UBO Graph": "ubo_graph",
        "Screening": "screening",
        "Risk Scoring": "risk_scoring",
    }
    for label, ledger_id in pattern.findall(rendered_prompt):
        slug = label_to_slug.get(label.strip())
        if slug is None:
            continue
        out[slug] = ledger_id
    return out

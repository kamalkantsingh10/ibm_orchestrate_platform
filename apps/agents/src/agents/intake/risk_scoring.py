"""Risk Scoring agent — Story 5.6.

Deterministic 5-component risk decomposition. The agent reads the
Document Intelligence + Entity Verification + UBO Graph outputs (already
in the supervisor's ``IntakeContext``) plus customer_metadata hints
(screening_hit_hint, adverse_media_hint) and computes:

* `country` (weight 0.15) — IN customer → 10; non-IN company → 60;
  individual customer → 20.
* `entity_type` (weight 0.20) — company with foreign-corporate UBO holders
  → 70; company with no UBO graph → 50; company with UBO graph but no
  foreign exposure → 30; individual → 25.
* `ownership_clarity` (weight 0.30) — base 40 + 10 per nominee_suspected
  edge − 4 per officer_corrected edge, clamped [0, 100]. UBO graph absent
  → 50 (treat as opaque).
* `screening` (weight 0.20) — placeholder; ``screening_hit_hint`` truthy
  → 60, else 0. Story 6.x will replace.
* `adverse_media` (weight 0.15) — placeholder; ``adverse_media_hint``
  truthy → 50, else 0.

The score is deterministic — given the same inputs, the same outputs.
``model_id="deterministic"``; ``prompt_template_id=None``. The
``@agent_action`` decorator writes one ledger entry per invocation.

Demo arc (load-bearing — do not adjust without re-pinning tests):
* Shree (clean SME): total ≈ 20, band low.
* Vora pre-correction: total ≈ 37, band medium (3 nominee_suspected edges).
* Vora post-correction (Coastal officer_corrected): total ≈ 32, band low.
* Ananya (individual + screening_hit_hint): total ≈ 35, band medium.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from contracts.cases import Case
from contracts.confidence import to_band
from contracts.entity_verification import EntityVerificationResult
from contracts.provenance import Provenance, ProvenancedField
from contracts.risk import (
    RiskBand,
    RiskComponent,
    RiskComponentName,
    RiskScore,
    RiskScoringInput,
    band_for_total,
)
from contracts.ubo import UBOGraph

from agents.supervisor.action_decorator import agent_action

# ───────────────────────────── weights ────────────────────────────────────

_WEIGHTS: dict[RiskComponentName, float] = {
    "country": 0.15,
    "entity_type": 0.20,
    "ownership_clarity": 0.30,
    "screening": 0.20,
    "adverse_media": 0.15,
}

_AGENT_CONFIDENCE = 0.85


# ───────────────────────────── case view ──────────────────────────────────


@dataclass(frozen=True)
class RiskCaseView:
    """Per-run snapshot of inputs the agent reads."""

    case: Case
    entity_verification: EntityVerificationResult | None
    ubo_graph: UBOGraph | None
    screening_hit_hint: dict[str, Any] | None
    adverse_media_hint: dict[str, Any] | None


# ───────────────────────────── component computation ──────────────────────


def _compute_country(view: RiskCaseView) -> tuple[float, str]:
    customer_type = view.case.customer_metadata.customer_type
    country = view.case.customer_metadata.country

    if customer_type == "individual":
        return 20.0, f"Individual customer (country={country!r})"
    if country == "IN":
        return 10.0, "Customer country: IN (low-risk)"
    if country is None:
        return 20.0, "Customer country unknown"
    return 60.0, f"Customer country: {country!r} (high-risk bucket)"


def _foreign_corporate_holder_count(graph: UBOGraph) -> int:
    """Count corporate shareholder nodes whose country is not IN."""
    foreign = 0
    holders_by_id: dict[str, Any] = {n.id: n for n in graph.nodes}
    for edge in graph.edges:
        if edge.kind != "owns":
            continue
        node = holders_by_id.get(edge.from_id)
        if node is None:
            continue
        if getattr(node, "country", None) and node.country != "IN":
            foreign += 1
    return foreign


def _compute_entity_type(view: RiskCaseView) -> tuple[float, str]:
    customer_type = view.case.customer_metadata.customer_type
    if customer_type == "individual":
        return 25.0, "Individual customer; no entity-type risk"
    if customer_type == "company" or customer_type is None:
        if view.ubo_graph is None:
            return (
                50.0,
                "Company customer; UBO graph not built (opaque structure)",
            )
        foreign_count = _foreign_corporate_holder_count(view.ubo_graph)
        if foreign_count > 0:
            return (
                70.0,
                f"Company with {foreign_count} foreign-corporate UBO holder(s)",
            )
        return 30.0, "Company with domestic-only UBO structure"
    return 30.0, f"Customer type {customer_type!r}"


def _compute_ownership_clarity(view: RiskCaseView) -> tuple[float, str]:
    if view.ubo_graph is None:
        return 50.0, "UBO graph absent; treating as opaque"
    n_nominee = sum(1 for e in view.ubo_graph.edges if e.nominee_flag == "nominee_suspected")
    n_corrected = sum(1 for e in view.ubo_graph.edges if e.nominee_flag == "officer_corrected")
    base = 40.0
    raw = base + (n_nominee * 10) - (n_corrected * 4)
    clamped = max(0.0, min(100.0, raw))
    return (
        clamped,
        f"{n_nominee} nominee-suspected edge(s); {n_corrected} officer-corrected edge(s)",
    )


def _compute_screening(view: RiskCaseView) -> tuple[float, str]:
    if view.screening_hit_hint:
        return 60.0, "Screening hit hint present"
    return 0.0, "No screening signal"


def _compute_adverse_media(view: RiskCaseView) -> tuple[float, str]:
    if view.adverse_media_hint:
        return 50.0, "Adverse media hint present"
    return 0.0, "No adverse-media signal"


def _build_component(name: RiskComponentName, value: float, rationale: str) -> RiskComponent:
    weight = _WEIGHTS[name]
    contribution = round(value * weight, 1)
    return RiskComponent(
        name=name,
        value=value,
        weight=weight,
        contribution=contribution,
        rationale=rationale,
    )


# ───────────────────────────── provenance ─────────────────────────────────


def _score_provenance_for(total: int) -> ProvenancedField[float]:
    prov = Provenance(
        source_agent="risk_scoring",
        source_system="deterministic",
        confidence=_AGENT_CONFIDENCE,
        confidence_band=to_band(_AGENT_CONFIDENCE),
        evidence_ids=[],
        captured_at=datetime.now(UTC),
    )
    return ProvenancedField(value=total / 100.0, provenance=prov)


# ───────────────────────────── agent function ─────────────────────────────


@agent_action(
    agent_id="risk_scoring",
    model_id="deterministic",
    prompt_template_id=None,
)
async def risk_scoring(
    input: RiskScoringInput,
    *,
    case_view: RiskCaseView | None = None,
) -> RiskScore:
    """Compute the 5-component risk decomposition for a case."""
    if case_view is None:
        raise RuntimeError("RiskCaseView is required at call time")

    components: list[RiskComponent] = [
        _build_component("country", *_compute_country(case_view)),
        _build_component("entity_type", *_compute_entity_type(case_view)),
        _build_component("ownership_clarity", *_compute_ownership_clarity(case_view)),
        _build_component("screening", *_compute_screening(case_view)),
        _build_component("adverse_media", *_compute_adverse_media(case_view)),
    ]
    total = round(sum(c.contribution for c in components))
    band: RiskBand = band_for_total(total)
    return RiskScore(
        case_id=input.case_id,
        total=total,
        band=band,
        components=components,
        score_provenance=_score_provenance_for(total),
    )

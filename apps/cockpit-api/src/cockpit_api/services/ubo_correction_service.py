"""UBO correction service — Story 5.5.

Pure helper that applies an officer's drag-correct to a UBOGraph and
returns a new (frozen) graph with the corrected edge. Used by the
``POST /v1/cases/{case_id}/ubo/learning-events`` endpoint.

The new edge is ``HIGH`` confidence by definition (officer attribution);
``evidence_ids=[]`` because the bank-buyer scope's evidence-attachment
ledger entry doesn't exist in the demo (Story 8.6 may add it).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from contracts.confidence import to_band
from contracts.learning_event import CorrectionTag
from contracts.provenance import Provenance, ProvenancedField
from contracts.ubo import UBOEdge, UBOGraph

EdgeKind = Literal["owns", "director", "beneficial"]


class EdgeNotFoundError(LookupError):
    """Raised when (edge_kind, from_id, original_to_id) doesn't exist on the graph."""

    def __init__(self, edge_kind: str, from_id: str, original_to_id: str) -> None:
        self.edge_kind = edge_kind
        self.from_id = from_id
        self.original_to_id = original_to_id
        super().__init__(f"UBO edge not found: ({edge_kind}, {from_id} → {original_to_id})")


class NodeNotFoundError(LookupError):
    """Raised when ``new_to_id`` isn't in the graph's nodes set."""

    def __init__(self, new_to_id: str) -> None:
        self.new_to_id = new_to_id
        super().__init__(f"UBO node not found: {new_to_id!r}")


_OFFICER_CONFIDENCE = 0.99


def _officer_confidence_pf(actor_id: str) -> ProvenancedField[float]:
    prov = Provenance(
        source_agent="officer",
        source_system=actor_id,
        confidence=_OFFICER_CONFIDENCE,
        confidence_band=to_band(_OFFICER_CONFIDENCE),
        evidence_ids=[],
        captured_at=datetime.now(UTC),
    )
    return ProvenancedField(value=_OFFICER_CONFIDENCE, provenance=prov)


def apply_officer_correction(
    graph: UBOGraph,
    *,
    edge_kind: EdgeKind,
    from_id: str,
    original_to_id: str,
    new_to_id: str,
    correction_tag: CorrectionTag,
    actor_id: str,
) -> UBOGraph:
    """Return a new UBOGraph with the officer's correction applied.

    Raises:
        EdgeNotFoundError: if the original edge isn't in the graph.
        NodeNotFoundError: if ``new_to_id`` isn't in the graph's nodes
            (only checked when ``correction_tag != "removed"``).
    """
    edge_index = -1
    for i, edge in enumerate(graph.edges):
        if edge.kind == edge_kind and edge.from_id == from_id and edge.to_id == original_to_id:
            edge_index = i
            break
    if edge_index == -1:
        raise EdgeNotFoundError(edge_kind, from_id, original_to_id)

    if correction_tag == "removed":
        new_edges = [e for i, e in enumerate(graph.edges) if i != edge_index]
        return graph.model_copy(update={"edges": new_edges})

    if new_to_id not in {n.id for n in graph.nodes}:
        raise NodeNotFoundError(new_to_id)

    original_edge = graph.edges[edge_index]
    corrected_edge = UBOEdge(
        kind=original_edge.kind,
        from_id=original_edge.from_id,
        to_id=new_to_id,
        ownership_pct=original_edge.ownership_pct,
        designation=original_edge.designation,
        confidence=_officer_confidence_pf(actor_id),
        nominee_flag="officer_corrected",
        rationale=f"Officer correction (tag: {correction_tag})",
    )
    new_edges = list(graph.edges)
    new_edges[edge_index] = corrected_edge
    return graph.model_copy(update={"edges": new_edges})

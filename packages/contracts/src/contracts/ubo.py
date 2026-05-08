"""UBO Graph contracts — Story 5.3.

Typed nodes (person | entity) and edges (owns | director | beneficial)
modelling a case's ultimate beneficial ownership chain. Each edge carries
its own ``ProvenancedField[float]`` confidence so the cockpit-ui can
render confidence + provenance pills per edge. The ``nominee_flag`` is a
typed enum (clear / nominee_suspected / officer_corrected) — Story 5.5's
drag-correct interaction transitions edges to ``officer_corrected``.

The ``@model_validator(mode="after")`` on ``UBOGraph`` enforces:
* ``root_entity_id`` is in the node id set;
* every edge's endpoints exist in the node set;
* no duplicate edges (same (kind, from_id, to_id));
* ownership-pct totals per ``to_id`` ≤ 100.0 (within 0.5 tolerance).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from contracts.cases import CaseId
from contracts.provenance import ProvenancedField

_UBO_NODE_ID_PATTERN = r"^ubo_(p|e)_[A-Za-z0-9_-]{1,64}$"
UBONodeId = Annotated[
    str,
    StringConstraints(pattern=_UBO_NODE_ID_PATTERN, min_length=7, max_length=72),
]


# ───────────────────────────── nodes ──────────────────────────────────────


class UBOPersonNode(BaseModel):
    model_config = {"frozen": True}

    kind: Literal["person"] = "person"
    id: UBONodeId
    name: str = Field(min_length=1)
    din: str | None = Field(default=None, pattern=r"^\d{8}$")
    country: str | None = None


class UBOEntityNode(BaseModel):
    model_config = {"frozen": True}

    kind: Literal["entity"] = "entity"
    id: UBONodeId
    name: str = Field(min_length=1)
    cin: str | None = None
    country: str | None = None
    is_corporate: bool = True


UBONode = UBOPersonNode | UBOEntityNode


# ───────────────────────────── edges ──────────────────────────────────────


EdgeKind = Literal["owns", "director", "beneficial"]
NomineeFlag = Literal["clear", "nominee_suspected", "officer_corrected"]
EdgeDesignation = Literal[
    "director",
    "managing_director",
    "additional_director",
    "nominee_director",
]


class UBOEdge(BaseModel):
    model_config = {"frozen": True}

    kind: EdgeKind
    from_id: UBONodeId
    to_id: UBONodeId
    ownership_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    designation: EdgeDesignation | None = None
    confidence: ProvenancedField[float]
    nominee_flag: NomineeFlag = "clear"
    rationale: str | None = None

    @model_validator(mode="after")
    def _kind_specific_fields_present(self) -> UBOEdge:
        if self.kind in {"owns", "beneficial"}:
            if self.ownership_pct is None:
                raise ValueError(f"edge kind={self.kind!r} requires ownership_pct")
            if self.designation is not None:
                raise ValueError(f"edge kind={self.kind!r} must not carry designation")
        elif self.kind == "director":
            if self.designation is None:
                raise ValueError("edge kind='director' requires designation")
            if self.ownership_pct is not None:
                raise ValueError("edge kind='director' must not carry ownership_pct")
        return self


# ───────────────────────────── graph ──────────────────────────────────────


class UBOGraph(BaseModel):
    model_config = {"frozen": True}

    case_id: CaseId
    root_entity_id: UBONodeId
    nodes: list[UBONode] = Field(default_factory=list)
    edges: list[UBOEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_graph_invariants(self) -> UBOGraph:
        node_ids = {n.id for n in self.nodes}
        if self.root_entity_id not in node_ids:
            raise ValueError(f"root_entity_id {self.root_entity_id!r} is not in nodes set")

        seen_edges: set[tuple[str, str, str]] = set()
        ownership_per_target: dict[str, float] = {}
        for edge in self.edges:
            if edge.from_id not in node_ids:
                raise ValueError(f"edge from_id {edge.from_id!r} not in nodes set (kind={edge.kind})")
            if edge.to_id not in node_ids:
                raise ValueError(f"edge to_id {edge.to_id!r} not in nodes set (kind={edge.kind})")
            edge_key = (edge.kind, edge.from_id, edge.to_id)
            if edge_key in seen_edges:
                raise ValueError(f"duplicate edge ({edge.kind}, {edge.from_id} → {edge.to_id})")
            seen_edges.add(edge_key)

            if edge.kind == "owns" and edge.ownership_pct is not None:
                ownership_per_target[edge.to_id] = ownership_per_target.get(edge.to_id, 0.0) + edge.ownership_pct

        for to_id, total in ownership_per_target.items():
            if total > 100.5:  # 0.5 tolerance for rounding
                raise ValueError(f"ownership_pct sum for to_id {to_id!r} = {total:.2f} > 100.0")
        return self


class UBOGraphInput(BaseModel):
    model_config = {"frozen": True}

    case_id: CaseId
    cin: str = Field(min_length=21, max_length=21)

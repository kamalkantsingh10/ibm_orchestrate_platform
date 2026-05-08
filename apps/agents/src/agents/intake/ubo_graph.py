"""UBO Graph agent — Story 5.3.

Builds a typed ``UBOGraph`` deterministically from the MCA company-master
returned by the Story 5.2 mock. Three nominee-detection rules apply
post-construction; the precedence order is documented inline below.

Confidence policy:
* Director edges: 0.95 (DIN-backed, MCA-authoritative).
* Shareholder edges: 0.92 (MCA-authoritative pre-correction).
* Any edge flagged by the nominee heuristics drops to 0.55 (MEDIUM_LOW).

Determinism: directors and shareholders are emitted in MCA order, which is
deterministic by construction in the mock. Nodes are deduped by ``id`` so
a person who appears as both director and shareholder gets one node and
two edges.

Story 6.x's reasoning-trace work will revisit ``payload.tool_calls`` —
for now, per Story 5.1 dev-notes pitfall #8, the ledger entry's
``tool_calls`` is intentionally an empty list.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from contracts.cases import CaseId
from contracts.confidence import to_band
from contracts.mca import MCACompanyMaster, MCADirector, MCAShareholder
from contracts.provenance import Provenance, ProvenancedField
from contracts.ubo import (
    EdgeDesignation,
    UBOEdge,
    UBOEntityNode,
    UBOGraph,
    UBOGraphInput,
    UBONode,
    UBOPersonNode,
)

from agents.supervisor.action_decorator import agent_action
from agents.tools.mca_lookup import MCALookup, get_default_mca_lookup

# ───────────────────────────── slug helper ────────────────────────────────


_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    """Lowercase + replace non-alphanumeric runs with `_`; trim leading/trailing `_`."""
    return _SLUG_NON_ALNUM.sub("_", value.lower()).strip("_")


def _entity_id_from_cin(cin: str) -> str:
    return f"ubo_e_{_slugify(cin)}"


def _entity_id_from_name(name: str) -> str:
    return f"ubo_e_{_slugify(name)}"


def _person_id_from_director(director: MCADirector) -> str:
    if director.din is not None:
        return f"ubo_p_{director.din}"
    return f"ubo_p_{_slugify(director.name)}"


def _person_id_from_shareholder(shareholder: MCAShareholder) -> str:
    return f"ubo_p_{_slugify(shareholder.name)}"


# ───────────────────────────── provenance ─────────────────────────────────


def _edge_provenance(confidence: float) -> Provenance:
    return Provenance(
        source_agent="ubo_graph",
        source_system="mca_mock",
        confidence=confidence,
        confidence_band=to_band(confidence),
        evidence_ids=[],
        captured_at=datetime.now(UTC),
    )


def _confidence_pf(value: float) -> ProvenancedField[float]:
    return ProvenancedField(value=value, provenance=_edge_provenance(value))


# ───────────────────────────── builder ────────────────────────────────────


_DIRECTOR_CONFIDENCE = 0.95
_SHAREHOLDER_CONFIDENCE = 0.92
_FLAGGED_CONFIDENCE = 0.55


def _build_root_node(master: MCACompanyMaster) -> UBOEntityNode:
    return UBOEntityNode(
        id=_entity_id_from_cin(master.cin),
        name=master.company_name,
        cin=master.cin,
        country="IN",
        is_corporate=True,
    )


def _build_director_pair(director: MCADirector, root_id: str) -> tuple[UBOPersonNode, UBOEdge]:
    node = UBOPersonNode(
        id=_person_id_from_director(director),
        name=director.name,
        din=director.din,
        country=None,
    )
    designation: EdgeDesignation = director.designation
    edge = UBOEdge(
        kind="director",
        from_id=node.id,
        to_id=root_id,
        designation=designation,
        confidence=_confidence_pf(_DIRECTOR_CONFIDENCE),
    )
    return node, edge


def _build_shareholder_pair(
    shareholder: MCAShareholder,
    root_id: str,
    director_name_to_id: dict[str, str],
) -> tuple[UBOPersonNode | UBOEntityNode | None, UBOEdge]:
    """Build a shareholder node + owns edge.

    If the shareholder is an individual whose name already matches a director
    (case-insensitive), the returned node is ``None`` and the edge reuses the
    director's id. Callers must skip adding the node when it's None.
    """
    node: UBOPersonNode | UBOEntityNode | None
    if shareholder.is_corporate:
        node = UBOEntityNode(
            id=_entity_id_from_name(shareholder.name),
            name=shareholder.name,
            cin=None,
            country=shareholder.country,
            is_corporate=True,
        )
        from_id = node.id
    else:
        existing_id = director_name_to_id.get(shareholder.name.lower())
        if existing_id is not None:
            # Reuse the director's node id; don't emit a new shareholder node.
            node = None
            from_id = existing_id
        else:
            node = UBOPersonNode(
                id=_person_id_from_shareholder(shareholder),
                name=shareholder.name,
                country=shareholder.country,
            )
            from_id = node.id

    edge = UBOEdge(
        kind="owns",
        from_id=from_id,
        to_id=root_id,
        ownership_pct=shareholder.ownership_pct,
        confidence=_confidence_pf(_SHAREHOLDER_CONFIDENCE),
    )
    return node, edge


def _construct_graph_components(
    master: MCACompanyMaster,
) -> tuple[list[UBONode], list[UBOEdge]]:
    """Build ordered, deduped nodes and edges from the MCA master.

    Dedup rule: a person who appears as both a director and an individual
    shareholder produces ONE node (using the director's DIN-based id) and
    TWO edges (one director, one owns).
    """
    root = _build_root_node(master)
    nodes_by_id: dict[str, UBONode] = {root.id: root}
    edges: list[UBOEdge] = []

    director_name_to_id: dict[str, str] = {}

    for director in master.directors:
        node, edge = _build_director_pair(director, root.id)
        if node.id not in nodes_by_id:
            nodes_by_id[node.id] = node
        director_name_to_id[director.name.lower()] = node.id
        edges.append(edge)

    for shareholder in master.shareholders:
        sh_node, edge = _build_shareholder_pair(shareholder, root.id, director_name_to_id)
        if sh_node is not None and sh_node.id not in nodes_by_id:
            nodes_by_id[sh_node.id] = sh_node
        edges.append(edge)

    return list(nodes_by_id.values()), edges


# ───────────────────────────── nominee heuristics ─────────────────────────
#
# Precedence: R1 → R2 → R3. The first rule that fires owns the rationale.
#
# R1: Foreign corporate majority holder (kind=owns, from is entity, country
#     is non-IN, ownership_pct >= 25.0).
# R2: Nominee-director designation (kind=director, designation=nominee_director).
# R3: Trust/nominee-services entity name (from is entity, "trust" or
#     "nominee" in name lowercased).


_R1_THRESHOLD = 25.0


def _evaluate_rule_1(edge: UBOEdge, source: UBONode) -> str | None:
    if edge.kind != "owns":
        return None
    if not isinstance(source, UBOEntityNode):
        return None
    if source.country is None or source.country == "IN":
        return None
    if edge.ownership_pct is None or edge.ownership_pct < _R1_THRESHOLD:
        return None
    return (
        f"Foreign corporate holder ({source.country}) with "
        f"{edge.ownership_pct}% ownership; structure suggests nominee/shell"
    )


def _evaluate_rule_2(edge: UBOEdge) -> str | None:
    if edge.kind != "director":
        return None
    if edge.designation != "nominee_director":
        return None
    return "MCA explicitly designates appointment as nominee_director"


def _evaluate_rule_3(source: UBONode) -> str | None:
    if not isinstance(source, UBOEntityNode):
        return None
    name_lower = source.name.lower()
    if "trust" in name_lower or "nominee" in name_lower:
        return f"Holder name '{source.name}' contains nominee/trust signal"
    return None


def _apply_nominee_heuristics(edges: list[UBOEdge], nodes: list[UBONode]) -> list[UBOEdge]:
    """Return a new edge list with nominee_flag + rationale + confidence drop applied."""
    nodes_by_id = {n.id: n for n in nodes}
    new_edges: list[UBOEdge] = []
    for edge in edges:
        source = nodes_by_id.get(edge.from_id)
        if source is None:
            new_edges.append(edge)
            continue

        rationale = _evaluate_rule_1(edge, source)
        if rationale is None:
            rationale = _evaluate_rule_2(edge)
        if rationale is None:
            rationale = _evaluate_rule_3(source)

        if rationale is None:
            new_edges.append(edge)
            continue

        new_edges.append(
            edge.model_copy(
                update={
                    "nominee_flag": "nominee_suspected",
                    "rationale": rationale,
                    "confidence": _confidence_pf(_FLAGGED_CONFIDENCE),
                }
            )
        )
    return new_edges


# ───────────────────────────── agent function ─────────────────────────────


# Story 6.4 / AC #8 — no agent-level reasoning trace; UBO reasoning is
# per-edge confidence (see UBOEdge.confidence + nominee_flag/rationale).
@agent_action(
    agent_id="ubo_graph",
    model_id="deterministic",
    prompt_template_id=None,
)
async def ubo_graph(
    input: UBOGraphInput,
    *,
    mca: MCALookup | None = None,
) -> UBOGraph:
    """Construct a typed UBO graph from the MCA company-master.

    The agent function is pure(-ish) — the MCA dependency is injectable so
    tests can control the master record returned for a given CIN.
    """
    resolved_mca = mca if mca is not None else get_default_mca_lookup()
    master = await resolved_mca.lookup(cin=input.cin)

    nodes, edges = _construct_graph_components(master)
    edges = _apply_nominee_heuristics(edges, nodes)

    return UBOGraph(
        case_id=_case_id(input.case_id),
        root_entity_id=_entity_id_from_cin(master.cin),
        nodes=nodes,
        edges=edges,
    )


def _case_id(value: CaseId) -> CaseId:
    """Identity passthrough — typed as CaseId for clarity at the call site."""
    return value

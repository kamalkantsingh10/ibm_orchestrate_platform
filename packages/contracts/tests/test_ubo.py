"""Tests for UBO contracts — Story 5.3 / AC #11."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from contracts.cases import VORA_CAPITAL_ID
from contracts.confidence import to_band
from contracts.provenance import Provenance, ProvenancedField
from contracts.ubo import (
    UBOEdge,
    UBOEntityNode,
    UBOGraph,
    UBOPersonNode,
)


def _confidence_pf(c: float = 0.95) -> ProvenancedField[float]:
    prov = Provenance(
        source_agent="ubo_graph",
        source_system="mca_mock",
        confidence=c,
        confidence_band=to_band(c),
        evidence_ids=[],
        captured_at=datetime.now(UTC),
    )
    return ProvenancedField(value=c, provenance=prov)


_ROOT_ID = "ubo_e_u67120mh2024ptc444789"
_PERSON_ID = "ubo_p_09876543"
_HOLDER_ID = "ubo_e_coastal"


def _root_node() -> UBOEntityNode:
    return UBOEntityNode(id=_ROOT_ID, name="Vora Capital", cin="U67120MH2024PTC444789", country="IN")


def _person_node() -> UBOPersonNode:
    return UBOPersonNode(id=_PERSON_ID, name="Devansh Vora", din="09876543")


def _holder_node() -> UBOEntityNode:
    return UBOEntityNode(id=_HOLDER_ID, name="Coastal Equity", country="SG", is_corporate=True)


def test_graph_round_trips() -> None:
    g = UBOGraph(
        case_id=VORA_CAPITAL_ID,
        root_entity_id=_ROOT_ID,
        nodes=[_root_node(), _person_node()],
        edges=[
            UBOEdge(
                kind="director",
                from_id=_PERSON_ID,
                to_id=_ROOT_ID,
                designation="managing_director",
                confidence=_confidence_pf(),
            ),
        ],
    )
    revived = UBOGraph.model_validate_json(g.model_dump_json())
    assert revived == g


def test_validator_rejects_root_not_in_nodes() -> None:
    with pytest.raises(ValidationError):
        UBOGraph(
            case_id=VORA_CAPITAL_ID,
            root_entity_id="ubo_e_missing",
            nodes=[_root_node()],
            edges=[],
        )


def test_validator_rejects_dangling_edge_endpoint() -> None:
    with pytest.raises(ValidationError):
        UBOGraph(
            case_id=VORA_CAPITAL_ID,
            root_entity_id=_ROOT_ID,
            nodes=[_root_node()],
            edges=[
                UBOEdge(
                    kind="director",
                    from_id="ubo_p_dangling",
                    to_id=_ROOT_ID,
                    designation="director",
                    confidence=_confidence_pf(),
                ),
            ],
        )


def test_validator_rejects_duplicate_edge() -> None:
    e = UBOEdge(
        kind="director",
        from_id=_PERSON_ID,
        to_id=_ROOT_ID,
        designation="director",
        confidence=_confidence_pf(),
    )
    with pytest.raises(ValidationError):
        UBOGraph(
            case_id=VORA_CAPITAL_ID,
            root_entity_id=_ROOT_ID,
            nodes=[_root_node(), _person_node()],
            edges=[e, e],
        )


def test_validator_rejects_ownership_over_100() -> None:
    with pytest.raises(ValidationError):
        UBOGraph(
            case_id=VORA_CAPITAL_ID,
            root_entity_id=_ROOT_ID,
            nodes=[_root_node(), _holder_node(), _person_node()],
            edges=[
                UBOEdge(
                    kind="owns",
                    from_id=_HOLDER_ID,
                    to_id=_ROOT_ID,
                    ownership_pct=80.0,
                    confidence=_confidence_pf(),
                ),
                UBOEdge(
                    kind="owns",
                    from_id=_PERSON_ID,
                    to_id=_ROOT_ID,
                    ownership_pct=30.0,
                    confidence=_confidence_pf(),
                ),
            ],
        )


def test_owns_edge_requires_ownership_pct() -> None:
    with pytest.raises(ValidationError):
        UBOEdge(
            kind="owns",
            from_id=_HOLDER_ID,
            to_id=_ROOT_ID,
            confidence=_confidence_pf(),
        )


def test_director_edge_requires_designation() -> None:
    with pytest.raises(ValidationError):
        UBOEdge(
            kind="director",
            from_id=_PERSON_ID,
            to_id=_ROOT_ID,
            confidence=_confidence_pf(),
        )


def test_director_edge_rejects_ownership_pct() -> None:
    with pytest.raises(ValidationError):
        UBOEdge(
            kind="director",
            from_id=_PERSON_ID,
            to_id=_ROOT_ID,
            designation="director",
            ownership_pct=10.0,
            confidence=_confidence_pf(),
        )


def test_node_id_pattern_enforced() -> None:
    with pytest.raises(ValidationError):
        UBOEntityNode(id="not_a_valid_id", name="X")

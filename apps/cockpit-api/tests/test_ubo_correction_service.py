"""Tests for the pure UBO correction helper — Story 5.5 / AC #10."""

from __future__ import annotations

import pytest
from contracts.confidence import ConfidenceBand

from cockpit_api.services.ubo_correction_service import (
    EdgeNotFoundError,
    NodeNotFoundError,
    apply_officer_correction,
)
from tests.fixtures.ubo_graph_vora import (
    ANCHOR_ID,
    COASTAL_ID,
    DEVANSH_ID,
    FILING_ID,
    VORA_ROOT_ID,
    make_vora_graph,
)


def test_real_ubo_correction_flips_nominee_flag() -> None:
    graph = make_vora_graph()
    corrected = apply_officer_correction(
        graph,
        edge_kind="owns",
        from_id=COASTAL_ID,
        original_to_id=VORA_ROOT_ID,
        new_to_id=VORA_ROOT_ID,
        correction_tag="real_ubo",
        actor_id="user_analyst",
    )
    coastal_edge = next(e for e in corrected.edges if e.from_id == COASTAL_ID and e.kind == "owns")
    assert coastal_edge.nominee_flag == "officer_corrected"
    assert coastal_edge.confidence.value == 0.99
    assert coastal_edge.confidence.provenance.source_agent == "officer"
    assert coastal_edge.confidence.provenance.source_system == "user_analyst"
    assert coastal_edge.confidence.provenance.confidence_band == ConfidenceBand.HIGH
    assert coastal_edge.rationale == "Officer correction (tag: real_ubo)"


def test_nominee_correction_keeps_target() -> None:
    graph = make_vora_graph()
    corrected = apply_officer_correction(
        graph,
        edge_kind="owns",
        from_id=COASTAL_ID,
        original_to_id=VORA_ROOT_ID,
        new_to_id=VORA_ROOT_ID,
        correction_tag="nominee",
        actor_id="user_analyst",
    )
    coastal_edge = next(e for e in corrected.edges if e.from_id == COASTAL_ID and e.kind == "owns")
    assert coastal_edge.rationale == "Officer correction (tag: nominee)"


def test_director_tag_works_on_director_edge() -> None:
    graph = make_vora_graph()
    corrected = apply_officer_correction(
        graph,
        edge_kind="director",
        from_id=FILING_ID,
        original_to_id=VORA_ROOT_ID,
        new_to_id=VORA_ROOT_ID,
        correction_tag="director",
        actor_id="user_analyst",
    )
    edge = next(e for e in corrected.edges if e.from_id == FILING_ID and e.kind == "director")
    assert edge.nominee_flag == "officer_corrected"


def test_removed_correction_strips_edge_from_graph() -> None:
    graph = make_vora_graph()
    corrected = apply_officer_correction(
        graph,
        edge_kind="owns",
        from_id=ANCHOR_ID,
        original_to_id=VORA_ROOT_ID,
        new_to_id=VORA_ROOT_ID,  # ignored when tag=removed
        correction_tag="removed",
        actor_id="user_analyst",
    )
    matching = [e for e in corrected.edges if e.from_id == ANCHOR_ID and e.kind == "owns"]
    assert matching == []
    assert len(corrected.edges) == len(graph.edges) - 1


def test_edge_not_found_raises() -> None:
    graph = make_vora_graph()
    with pytest.raises(EdgeNotFoundError):
        apply_officer_correction(
            graph,
            edge_kind="owns",
            from_id="ubo_p_nonexistent",
            original_to_id=VORA_ROOT_ID,
            new_to_id=VORA_ROOT_ID,
            correction_tag="real_ubo",
            actor_id="user_analyst",
        )


def test_node_not_found_raises_when_new_target_missing() -> None:
    graph = make_vora_graph()
    with pytest.raises(NodeNotFoundError):
        apply_officer_correction(
            graph,
            edge_kind="owns",
            from_id=COASTAL_ID,
            original_to_id=VORA_ROOT_ID,
            new_to_id="ubo_e_nonexistent",
            correction_tag="real_ubo",
            actor_id="user_analyst",
        )


def test_original_graph_is_unchanged() -> None:
    graph = make_vora_graph()
    coastal_before = next(e for e in graph.edges if e.from_id == COASTAL_ID and e.kind == "owns")
    assert coastal_before.nominee_flag == "nominee_suspected"
    apply_officer_correction(
        graph,
        edge_kind="owns",
        from_id=COASTAL_ID,
        original_to_id=VORA_ROOT_ID,
        new_to_id=VORA_ROOT_ID,
        correction_tag="real_ubo",
        actor_id="user_analyst",
    )
    coastal_after = next(e for e in graph.edges if e.from_id == COASTAL_ID and e.kind == "owns")
    assert coastal_after.nominee_flag == "nominee_suspected"
    assert coastal_after is coastal_before


def test_redirect_to_different_target_succeeds() -> None:
    """Officer drags Coastal edge to point at Devansh instead of Vora."""
    graph = make_vora_graph()
    corrected = apply_officer_correction(
        graph,
        edge_kind="owns",
        from_id=COASTAL_ID,
        original_to_id=VORA_ROOT_ID,
        new_to_id=DEVANSH_ID,
        correction_tag="real_ubo",
        actor_id="user_analyst",
    )
    edge = next(e for e in corrected.edges if e.from_id == COASTAL_ID and e.kind == "owns")
    assert edge.to_id == DEVANSH_ID

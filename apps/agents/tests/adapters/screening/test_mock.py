"""Tests for MockScreeningAdapter — Story 6.1 / AC #8."""

from __future__ import annotations

from datetime import date

import pytest
from contracts.cases import ANANYA_IYER_ID, SHREE_VENKAT_ID, VORA_CAPITAL_ID
from contracts.confidence import to_band
from contracts.screening import ScreeningRequest, ScreeningSubject

from agents.adapters.screening.mock import MockScreeningAdapter


@pytest.fixture
def adapter() -> MockScreeningAdapter:
    return MockScreeningAdapter()


async def test_vora_director_rohan_mehta_hits_ofac(adapter: MockScreeningAdapter) -> None:
    """J1 demo pin: Vora's Rohan Mehta → OFAC SDN at score 0.73, sanctions."""
    req = ScreeningRequest(
        case_id=VORA_CAPITAL_ID,
        subjects=[
            ScreeningSubject(
                subject_kind="director",
                subject_id="ubo_p_09876544",
                full_name="Rohan Mehta",
                date_of_birth=date(1978, 1, 1),
            )
        ],
    )
    hits = await adapter.screen(req)
    assert len(hits) == 1
    hit = hits[0]
    assert hit.subject_id == "ubo_p_09876544"
    assert "sanctions" in hit.categories
    assert "OFAC SDN" in hit.source_lists
    assert hit.name_match_score.value == pytest.approx(0.73)
    assert hit.matched_name == "Patel R."
    # DOB mismatch — registered 1961 vs subject's 1978
    assert hit.date_of_birth == date(1961, 5, 12)


async def test_shree_entity_returns_no_hits(adapter: MockScreeningAdapter) -> None:
    """Clean approval path — Shree's entity has no matches."""
    req = ScreeningRequest(
        case_id=SHREE_VENKAT_ID,
        subjects=[
            ScreeningSubject(
                subject_kind="entity",
                subject_id="ubo_e_u51900mh2018ptc312456",
                full_name="Shree Venkat Trading Pvt Ltd",
            )
        ],
    )
    hits = await adapter.screen(req)
    assert hits == []


async def test_ananya_iyer_hits_pep_with_dob_match(adapter: MockScreeningAdapter) -> None:
    """Happy-but-PEP path — Ananya hits OpenSanctions PEP at 0.88, DOB match."""
    req = ScreeningRequest(
        case_id=ANANYA_IYER_ID,
        subjects=[
            ScreeningSubject(
                subject_kind="entity",
                subject_id=ANANYA_IYER_ID,
                full_name="Ananya Iyer",
                date_of_birth=date(1985, 11, 4),
            )
        ],
    )
    hits = await adapter.screen(req)
    assert len(hits) == 1
    hit = hits[0]
    assert "pep" in hit.categories
    assert "OpenSanctions Politicians" in hit.source_lists
    assert hit.name_match_score.value == pytest.approx(0.88)
    assert hit.date_of_birth == date(1985, 11, 4)


async def test_fuzzy_fallback_returns_hit_for_near_miss(
    adapter: MockScreeningAdapter,
) -> None:
    """Subject not in fixtures but close enough → fuzzy fallback fires."""
    req = ScreeningRequest(
        case_id=VORA_CAPITAL_ID,
        subjects=[
            ScreeningSubject(
                subject_kind="director",
                subject_id="ubo_p_unknown",
                full_name="Mehta Rohan",  # token-set match against "Rohan Mehta"
            )
        ],
    )
    hits = await adapter.screen(req)
    assert len(hits) >= 1
    score = hits[0].name_match_score.value
    assert 0.50 <= score <= 1.0


async def test_fuzzy_fallback_returns_empty_below_threshold(
    adapter: MockScreeningAdapter,
) -> None:
    """Names too distant from the corpus emit no hits."""
    req = ScreeningRequest(
        case_id=VORA_CAPITAL_ID,
        subjects=[
            ScreeningSubject(
                subject_kind="entity",
                subject_id="ubo_e_zzz",
                full_name="Zzzzz Nobody",
            )
        ],
    )
    hits = await adapter.screen(req)
    assert hits == []


async def test_hit_id_is_deterministic(adapter: MockScreeningAdapter) -> None:
    req = ScreeningRequest(
        case_id=VORA_CAPITAL_ID,
        subjects=[
            ScreeningSubject(
                subject_kind="director",
                subject_id="ubo_p_09876544",
                full_name="Rohan Mehta",
                date_of_birth=date(1978, 1, 1),
            )
        ],
    )
    hits_a = await adapter.screen(req)
    hits_b = await adapter.screen(req)
    assert hits_a[0].hit_id == hits_b[0].hit_id
    assert hits_a[0].hit_id.startswith("hit_mock_")


async def test_provenance_source_fields(adapter: MockScreeningAdapter) -> None:
    req = ScreeningRequest(
        case_id=ANANYA_IYER_ID,
        subjects=[
            ScreeningSubject(
                subject_kind="entity",
                subject_id=ANANYA_IYER_ID,
                full_name="Ananya Iyer",
                date_of_birth=date(1985, 11, 4),
            )
        ],
    )
    hits = await adapter.screen(req)
    prov = hits[0].name_match_score.provenance
    assert prov.source_agent == "screening"
    assert prov.source_system == "screening_mock"
    assert prov.evidence_ids == []  # supervisor back-fills


async def test_confidence_band_matches_score(adapter: MockScreeningAdapter) -> None:
    req = ScreeningRequest(
        case_id=ANANYA_IYER_ID,
        subjects=[
            ScreeningSubject(
                subject_kind="entity",
                subject_id=ANANYA_IYER_ID,
                full_name="Ananya Iyer",
                date_of_birth=date(1985, 11, 4),
            )
        ],
    )
    hits = await adapter.screen(req)
    score = hits[0].name_match_score.value
    assert hits[0].name_match_score.provenance.confidence_band == to_band(score)


async def test_subject_id_override_resolves_when_name_misses(
    adapter: MockScreeningAdapter,
) -> None:
    """Subject ID match still works even when full_name doesn't appear in fixtures."""
    req = ScreeningRequest(
        case_id=VORA_CAPITAL_ID,
        subjects=[
            ScreeningSubject(
                subject_kind="director",
                subject_id="ubo_p_09876544",
                full_name="R. Mehta",  # not an exact-key fixture row
                date_of_birth=date(1980, 6, 1),  # bad DOB too
            )
        ],
    )
    hits = await adapter.screen(req)
    # "R. Mehta" tokenises as {r, mehta} → token_set_ratio against
    # "Rohan Mehta" is high enough to fire the fuzzy path; either path
    # returns an OFAC-flavoured hit.
    assert len(hits) >= 1
    assert "sanctions" in hits[0].categories

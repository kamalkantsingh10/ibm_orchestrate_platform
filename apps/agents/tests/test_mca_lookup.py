"""Tests for the MCA lookup tool — Story 5.2 / AC #6."""

from __future__ import annotations

import pytest

from agents.tools.mca_lookup import (
    MCALookup,
    MCANotFoundError,
    MCATemporaryError,
    get_default_mca_lookup,
)
from agents.tools.mca_mock import (
    _FIXTURES,
    _MAGIC_CIN_TEMPORARY_ERROR,
    MockMCALookup,
)

VORA_CIN = "U67120MH2024PTC444789"
SHREE_CIN = "U51900MH2018PTC312456"
MAGIC_CIN_NOT_FOUND = "U99999YY9999YYY999999"


async def test_vora_cin_returns_canonical_fixture() -> None:
    mock = MockMCALookup()
    master = await mock.lookup(cin=VORA_CIN)
    assert master.cin == VORA_CIN
    assert master.company_name == "Vora Capital Holdings Pvt Ltd"
    assert master.status == "active"
    assert master.registered_office.startswith("Suite 402")
    assert master.incorporation_date == "2024-08-22"

    # Three directors — including the nominee for Story 5.3 detection.
    assert [d.name for d in master.directors] == [
        "Devansh Vora",
        "Rohan Mehta",
        "A K Filing Services",
    ]
    assert master.directors[0].designation == "managing_director"
    assert master.directors[2].designation == "nominee_director"

    # Three shareholders — foreign LLC + BVI trust signal Story 5.3 nominee suspect.
    assert [s.name for s in master.shareholders] == [
        "Devansh Vora",
        "Coastal Equity Partners Pte Ltd",
        "Anchor Trust Services (BVI)",
    ]
    foreign = [s for s in master.shareholders if s.country != "IN"]
    assert {s.country for s in foreign} == {"SG", "VG"}
    assert all(s.is_corporate for s in foreign)


async def test_shree_cin_returns_canonical_fixture() -> None:
    mock = MockMCALookup()
    master = await mock.lookup(cin=SHREE_CIN)
    assert master.cin == SHREE_CIN
    assert master.company_name == "Shree Venkat Trading Pvt Ltd"
    assert master.status == "active"
    assert master.registered_office.startswith("Plot 14")
    assert master.incorporation_date == "2018-03-15"
    # Two clean individual directors, two clean individual shareholders.
    assert all(d.designation == "director" for d in master.directors)
    assert sum(s.ownership_pct for s in master.shareholders) == pytest.approx(100.0)
    assert all(s.country == "IN" and not s.is_corporate for s in master.shareholders)


async def test_unknown_cin_raises_not_found() -> None:
    mock = MockMCALookup()
    with pytest.raises(MCANotFoundError) as exc_info:
        await mock.lookup(cin=MAGIC_CIN_NOT_FOUND)
    assert exc_info.value.cin == MAGIC_CIN_NOT_FOUND


async def test_magic_cin_raises_temporary() -> None:
    mock = MockMCALookup()
    with pytest.raises(MCATemporaryError) as exc_info:
        await mock.lookup(cin=_MAGIC_CIN_TEMPORARY_ERROR)
    assert "deliberate transient failure" in str(exc_info.value)


def test_protocol_satisfaction_runtime_checkable() -> None:
    assert isinstance(MockMCALookup(), MCALookup)


def test_get_default_returns_mock_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCA_PROVIDER", raising=False)
    assert isinstance(get_default_mca_lookup(), MockMCALookup)


def test_get_default_returns_mock_when_explicit_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCA_PROVIDER", "mock")
    assert isinstance(get_default_mca_lookup(), MockMCALookup)


def test_get_default_unknown_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCA_PROVIDER", "watsonx")
    with pytest.raises(ValueError) as exc_info:
        get_default_mca_lookup()
    assert "watsonx" in str(exc_info.value)


def test_fixture_immutability_via_model_copy() -> None:
    original = _FIXTURES[VORA_CIN]
    assert original.directors[0].name == "Devansh Vora"
    mutated = original.model_copy(update={"company_name": "Mutated Co"})
    assert mutated.company_name == "Mutated Co"
    # The shared module-level fixture is unchanged.
    assert _FIXTURES[VORA_CIN].company_name == "Vora Capital Holdings Pvt Ltd"
    assert _FIXTURES[VORA_CIN] is original

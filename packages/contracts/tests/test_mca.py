"""Tests for MCA contracts — Story 5.2 / AC #7."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.mca import (
    MCACompanyMaster,
    MCADirector,
    MCAShareholder,
    MCAStatus,
)


def _master(**overrides: object) -> MCACompanyMaster:
    base: dict[str, object] = {
        "cin": "U67120MH2024PTC444789",
        "company_name": "Vora Capital Holdings Pvt Ltd",
        "status": "active",
        "registered_office": "Suite 402, Sea Breeze Heights, Bandra West, Mumbai 400050",
        "incorporation_date": "2024-08-22",
        "directors": [
            MCADirector(
                din="09876543",
                name="Devansh Vora",
                appointed_on="2024-08-22",
                designation="managing_director",
            ),
        ],
        "shareholders": [
            MCAShareholder(name="Devansh Vora", ownership_pct=100.0, country="IN"),
        ],
    }
    base.update(overrides)
    return MCACompanyMaster(**base)  # type: ignore[arg-type]


def test_company_master_round_trips() -> None:
    master = _master()
    revived = MCACompanyMaster.model_validate_json(master.model_dump_json())
    assert revived == master


def test_company_master_round_trips_with_director_no_din() -> None:
    """Pitfall #2: MCADirector.din is Optional[str] (retired directors)."""
    master = _master(
        directors=[
            MCADirector(din=None, name="Retired Director", designation="director"),
        ],
    )
    revived = MCACompanyMaster.model_validate_json(master.model_dump_json())
    assert revived == master
    assert revived.directors[0].din is None


def test_company_master_rejects_invalid_cin() -> None:
    with pytest.raises(ValidationError):
        _master(cin="not-a-real-cin")


def test_company_master_rejects_invalid_status_value() -> None:
    """MCAStatus values are snake_case wire format."""
    with pytest.raises(ValidationError):
        _master(status="active ")


def test_company_master_rejects_status_struck_dash() -> None:
    """`struck-off` (kebab) must be rejected — wire is snake_case `struck_off`."""
    with pytest.raises(ValidationError):
        _master(status="struck-off")


def test_shareholder_rejects_overshoot() -> None:
    with pytest.raises(ValidationError):
        MCAShareholder(name="Overshoot LLC", ownership_pct=101.0)


def test_director_rejects_invalid_din_pattern() -> None:
    with pytest.raises(ValidationError):
        MCADirector(din="abc", name="Bad DIN")


def test_mca_status_literal_accepts_canonical_values() -> None:
    accepted: list[MCAStatus] = ["active", "struck_off", "dormant"]
    for value in accepted:
        master = _master(status=value)
        assert master.status == value

"""Deterministic mock MCA lookup — Story 5.2.

Demo default. Returns canonical fixtures keyed by CIN. The two magic CINs
exercise the failure paths through Entity Verification (Story 5.1):

* ``U99999XX9999XXX999999`` → ``MCATemporaryError``
* ``U99999YY9999YYY999999`` → falls through ``_FIXTURES`` to ``MCANotFoundError``

Both magic CINs deliberately match the standard CIN regex so they pass
``EntityVerificationInput`` validation at the FastAPI boundary.
"""

from __future__ import annotations

from contracts.mca import MCACompanyMaster, MCADirector, MCAShareholder

from agents.tools.mca_lookup import MCALookup, MCANotFoundError, MCATemporaryError

_MAGIC_CIN_TEMPORARY_ERROR = "U99999XX9999XXX999999"


_SHREE_VENKAT = MCACompanyMaster(
    cin="U51900MH2018PTC312456",
    company_name="Shree Venkat Trading Pvt Ltd",
    status="active",
    registered_office="Plot 14, MIDC Industrial Area, Pune, Maharashtra 411019",
    incorporation_date="2018-03-15",
    directors=[
        MCADirector(
            din="08123456",
            name="Venkat Reddy",
            appointed_on="2018-03-15",
            designation="director",
        ),
        MCADirector(
            din="08123457",
            name="Lakshmi Reddy",
            appointed_on="2018-03-15",
            designation="director",
        ),
    ],
    shareholders=[
        MCAShareholder(
            name="Venkat Reddy",
            ownership_pct=70.0,
            country="IN",
            is_corporate=False,
        ),
        MCAShareholder(
            name="Lakshmi Reddy",
            ownership_pct=30.0,
            country="IN",
            is_corporate=False,
        ),
    ],
)


# Vora's shareholder pattern is load-bearing for Story 5.3's nominee-detection.
# Do not "round" the percentages or change country codes (SG vs VG) without
# coordinating with that story's tests.
_VORA_CAPITAL = MCACompanyMaster(
    cin="U67120MH2024PTC444789",
    company_name="Vora Capital Holdings Pvt Ltd",
    status="active",
    registered_office="Suite 402, Sea Breeze Heights, Bandra West, Mumbai 400050",
    incorporation_date="2024-08-22",
    directors=[
        MCADirector(
            din="09876543",
            name="Devansh Vora",
            appointed_on="2024-08-22",
            designation="managing_director",
        ),
        MCADirector(
            din="09876544",
            name="Rohan Mehta",
            appointed_on="2024-08-22",
            designation="director",
        ),
        MCADirector(
            din="09876545",
            name="A K Filing Services",
            appointed_on="2024-08-22",
            designation="nominee_director",
        ),
    ],
    shareholders=[
        MCAShareholder(
            name="Devansh Vora",
            ownership_pct=5.0,
            country="IN",
            is_corporate=False,
        ),
        MCAShareholder(
            name="Coastal Equity Partners Pte Ltd",
            ownership_pct=70.0,
            country="SG",
            is_corporate=True,
        ),
        MCAShareholder(
            name="Anchor Trust Services (BVI)",
            ownership_pct=25.0,
            country="VG",
            is_corporate=True,
        ),
    ],
)


_FIXTURES: dict[str, MCACompanyMaster] = {
    _SHREE_VENKAT.cin: _SHREE_VENKAT,
    _VORA_CAPITAL.cin: _VORA_CAPITAL,
}


class MockMCALookup(MCALookup):
    """Deterministic in-memory MCA lookup."""

    model_id: str = "mock"

    async def lookup(self, *, cin: str) -> MCACompanyMaster:
        if cin == _MAGIC_CIN_TEMPORARY_ERROR:
            raise MCATemporaryError("MCA mock: deliberate transient failure")
        try:
            return _FIXTURES[cin]
        except KeyError as exc:
            raise MCANotFoundError(cin) from exc

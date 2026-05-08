"""MCA lookup tool — Story 5.2.

Mock-only in the demo (see ``architecture.md`` § Demo Scope Addendum).
Entity Verification (Story 5.1) consumes this via the ``MCALookup``
Protocol. The real HTTP adapter is the bank-buyer revival surface; the
Protocol shape is preserved so it can be added later without churn.

Resolution: ``MCA_PROVIDER`` env var (default ``"mock"``). Only ``"mock"``
is supported in the demo.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from contracts.mca import MCACompanyMaster

if TYPE_CHECKING:
    pass


class MCALookupError(RuntimeError):
    """Base for all MCA-tool errors."""


class MCANotFoundError(MCALookupError):
    """Raised when a CIN does not resolve to an MCA master."""

    def __init__(self, cin: str) -> None:
        self.cin = cin
        super().__init__(f"MCA: no company master for CIN {cin!r}")


class MCATemporaryError(MCALookupError):
    """Raised when MCA is unavailable (network / rate-limit / 5xx).

    In the demo this is raised only by the mock when fed a magic CIN
    reserved for failure-path tests.
    """


@runtime_checkable
class MCALookup(Protocol):
    async def lookup(self, *, cin: str) -> MCACompanyMaster: ...


def get_default_mca_lookup() -> MCALookup:
    """Resolve the default MCA lookup impl from ``MCA_PROVIDER`` env."""
    provider = os.environ.get("MCA_PROVIDER", "mock")
    if provider == "mock":
        from agents.tools.mca_mock import MockMCALookup

        return MockMCALookup()
    raise ValueError(f"Unknown MCA_PROVIDER {provider!r}; only 'mock' is supported in the demo")

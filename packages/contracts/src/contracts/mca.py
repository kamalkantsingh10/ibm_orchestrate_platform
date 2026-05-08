"""MCA contracts — Story 5.2.

Authority-source records for the Indian Ministry of Corporate Affairs lookup.
This module is the single source of truth for ``MCAStatus`` (consumed by
both Story 5.1's Entity Verification result and Story 5.3's UBO Graph
agent). Wire format is snake_case (``architecture.md`` § Naming Patterns).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MCAStatus = Literal["active", "struck_off", "dormant"]


class MCADirector(BaseModel):
    model_config = {"frozen": True}

    din: str | None = Field(default=None, pattern=r"^\d{8}$")
    name: str = Field(min_length=1)
    appointed_on: str | None = None
    designation: Literal[
        "director",
        "managing_director",
        "additional_director",
        "nominee_director",
    ] = "director"


class MCAShareholder(BaseModel):
    model_config = {"frozen": True}

    name: str = Field(min_length=1)
    ownership_pct: float = Field(ge=0.0, le=100.0)
    country: str | None = None
    is_corporate: bool = False


class MCACompanyMaster(BaseModel):
    model_config = {"frozen": True}

    cin: str = Field(
        min_length=21,
        max_length=21,
        pattern=r"^[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$",
    )
    company_name: str = Field(min_length=1)
    status: MCAStatus
    registered_office: str = Field(min_length=1)
    incorporation_date: str = Field(min_length=10)
    directors: list[MCADirector] = Field(default_factory=list)
    shareholders: list[MCAShareholder] = Field(default_factory=list)

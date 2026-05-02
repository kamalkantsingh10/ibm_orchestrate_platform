"""Case Supervisor outcome contract — Story 3.5.

Returned by ``CaseSupervisor.run_intake`` and used as the response body of
``POST /v1/cases/{case_id}/intake``. Tells the caller whether intake
completed cleanly or was blocked by a named agent failure.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from contracts.cases import CaseId


class CaseIntakeOutcome(BaseModel):
    """Result envelope for one case-intake supervisor run."""

    model_config = {"frozen": True}

    case_id: CaseId
    status: Literal["completed", "blocked"]
    agents_run: list[str] = Field(default_factory=list)
    failed_agent: str | None = None
    error_message: str | None = None
    fields_extracted: int = Field(default=0, ge=0)
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def _completed_at_must_be_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("completed_at must be timezone-aware (UTC)")
        return value

    @model_validator(mode="after")
    def _blocked_must_name_failed_agent(self) -> CaseIntakeOutcome:
        if self.status == "blocked" and not self.failed_agent:
            raise ValueError("status='blocked' requires failed_agent to name the agent that failed")
        if self.status == "completed" and self.failed_agent is not None:
            raise ValueError("status='completed' must not set failed_agent — that's the blocked-path field")
        return self

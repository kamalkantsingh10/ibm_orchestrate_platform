"""Generate openapi.yaml for the score_risk tool — Story 5.6."""

from __future__ import annotations

from pathlib import Path

from agents._adk.openapi_tool import build_and_write

build_and_write(
    path_filter="/v1/agents/risk_scoring/score",
    operation_id="score_risk",
    title="KYC Risk Scoring (ADK Tool)",
    description=(
        "Risk Scoring agent exposed for ADK runtime tool registration. "
        "The watsonx Orchestrate runtime calls this endpoint when an "
        "agent decides to invoke `score_risk`."
    ),
    output=Path(__file__).parent / "openapi.yaml",
)

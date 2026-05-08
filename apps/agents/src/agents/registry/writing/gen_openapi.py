"""Generate openapi.yaml for the draft_rationale tool — Story 7.3.

Invoked by ``make adk-spec`` (which walks every ``gen_openapi.py`` under
``apps/agents/src/agents/registry/*/`` and runs it from inside the
cockpit-api Poetry venv).
"""

from __future__ import annotations

from pathlib import Path

from agents._adk.openapi_tool import build_and_write

build_and_write(
    path_filter="/v1/agents/writing/draft",
    operation_id="draft_rationale",
    title="KYC Decision Rationale Drafter (ADK Tool)",
    description=(
        "Writing agent exposed for ADK runtime tool registration. The "
        "watsonx Orchestrate runtime calls this endpoint when an agent "
        "decides to invoke `draft_rationale`."
    ),
    output=Path(__file__).parent / "openapi.yaml",
)

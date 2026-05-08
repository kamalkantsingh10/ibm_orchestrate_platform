"""Generate openapi.yaml for the run_screening tool — Story 6.2.

Invoked by ``make adk-spec`` (which walks every ``gen_openapi.py`` under
``apps/agents/src/agents/registry/*/`` and runs it from inside the
cockpit-api Poetry venv).
"""

from __future__ import annotations

from pathlib import Path

from agents._adk.openapi_tool import build_and_write

build_and_write(
    path_filter="/v1/agents/screening/run",
    operation_id="run_screening",
    title="KYC Screening (ADK Tool)",
    description=(
        "Screening agent exposed for ADK runtime tool registration. The "
        "watsonx Orchestrate runtime calls this endpoint when an agent "
        "decides to invoke `run_screening`."
    ),
    output=Path(__file__).parent / "openapi.yaml",
)

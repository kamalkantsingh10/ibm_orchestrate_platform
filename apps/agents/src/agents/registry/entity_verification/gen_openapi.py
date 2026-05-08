"""Generate openapi.yaml for the verify_entity tool — Story 5.1.

Invoked by ``make adk-spec`` (which walks every ``gen_openapi.py`` under
``apps/agents/src/agents/registry/*/`` and runs it from inside the
cockpit-api Poetry venv).
"""

from __future__ import annotations

from pathlib import Path

from agents._adk.openapi_tool import build_and_write

build_and_write(
    path_filter="/v1/agents/entity_verification/verify",
    operation_id="verify_entity",
    title="KYC Entity Verification (ADK Tool)",
    description=(
        "Entity Verification agent exposed for ADK runtime tool "
        "registration. The watsonx Orchestrate runtime calls this "
        "endpoint when an agent decides to invoke `verify_entity`."
    ),
    output=Path(__file__).parent / "openapi.yaml",
)

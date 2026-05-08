"""Generate openapi.yaml for the list_cases tool.

Tool-only registry entry — no agent.yaml here. The case_supervisor
agent declares ``list_cases`` in its ``tools`` list and the runtime
resolves it from this directory's openapi.yaml.

Invoked by ``make adk-spec`` (which walks every ``gen_openapi.py``
under ``apps/agents/src/agents/registry/*/``).
"""

from __future__ import annotations

from pathlib import Path

from agents._adk.openapi_tool import build_and_write

build_and_write(
    path_filter="/v1/cases",
    operation_id="list_cases",
    title="KYC Cases — List (ADK Tool)",
    description=(
        "Lists every KYC case currently in the cockpit (newest first). "
        "Each item carries the case id, current state, customer metadata, "
        "and assigned officer. The case_supervisor agent calls this when "
        "the user asks 'what cases are there?' or similar."
    ),
    output=Path(__file__).parent / "openapi.yaml",
)

"""Generate openapi.yaml for the run_case_intake tool — Story 3.5 ADK integration.

Invoked by ``make adk-spec`` (which walks every ``gen_openapi.py`` under
``apps/agents/src/agents/registry/*/`` and runs it from inside the
cockpit-api Poetry venv).
"""

from __future__ import annotations

from pathlib import Path

from agents._adk.openapi_tool import build_and_write

build_and_write(
    path_filter="/v1/cases/{case_id}/intake",
    operation_id="run_case_intake",
    title="KYC Case Intake Supervisor (ADK Tool)",
    description=(
        "Triggers the Case Supervisor's deterministic intake fan-out for a "
        "case. Wraps Story 3.5's CaseSupervisor.run_intake — the supervisor "
        "fans out to all registered intake agents (currently: Document "
        "Intelligence), persists results, and transitions the case to "
        "decision_ready on success or escalated on agent failure."
    ),
    output=Path(__file__).parent / "openapi.yaml",
)

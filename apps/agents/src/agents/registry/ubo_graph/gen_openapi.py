"""Generate openapi.yaml for the build_ubo_graph tool — Story 5.3."""

from __future__ import annotations

from pathlib import Path

from agents._adk.openapi_tool import build_and_write

build_and_write(
    path_filter="/v1/agents/ubo_graph/build",
    operation_id="build_ubo_graph",
    title="KYC UBO Graph (ADK Tool)",
    description=(
        "UBO Graph agent exposed for ADK runtime tool registration. "
        "The watsonx Orchestrate runtime calls this endpoint when an "
        "agent decides to invoke `build_ubo_graph`."
    ),
    output=Path(__file__).parent / "openapi.yaml",
)

"""Generate openapi.yaml for the extract_document_fields tool.

Invoked by ``make adk-spec`` (which walks every ``gen_openapi.py`` under
``apps/agents/src/agents/registry/*/`` and runs it from inside the
cockpit-api Poetry venv).
"""

from __future__ import annotations

from pathlib import Path

from agents._adk.openapi_tool import build_and_write

build_and_write(
    path_filter="/v1/agents/document_intelligence/extract",
    operation_id="extract_document_fields",
    title="KYC Document Intelligence (ADK Tool)",
    description=(
        "Document Intelligence agent exposed for ADK runtime tool "
        "registration. The watsonx Orchestrate runtime calls this "
        "endpoint when an agent decides to invoke "
        "`extract_document_fields`."
    ),
    output=Path(__file__).parent / "openapi.yaml",
)

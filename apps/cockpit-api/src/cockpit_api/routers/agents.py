"""Agent invocation router — Story 3.4 ADK integration.

Exposes the Document Intelligence agent as an HTTP endpoint so the IBM
watsonx Orchestrate ADK runtime can call it as a tool. The endpoint is the
thin HTTP boundary; the heavy lifting still happens in
``apps/agents/src/agents/intake/document_intelligence.py`` via
``@agent_action``, so every ADK-driven invocation lands in the JSONL
ledger exactly the same way a direct Python call would.

Demo flow:
    Chat UI  →  ADK runtime (Docker)  →  HTTP POST  →  this endpoint  →
    document_intelligence(input)  →  ledger entry  →  response back to ADK.

The endpoint is wide-open (no auth) on purpose — the demo runs entirely on
localhost. When the bank-buyer scope revives, this is where OIDC + the
audience-restricted JWT check land.
"""

from __future__ import annotations

from agents.intake.document_intelligence import document_intelligence
from agents.supervisor.action_decorator import AgentExecutionError
from contracts.document_intelligence import (
    DocumentIntelligenceInput,
    DocumentIntelligenceOutput,
)
from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/v1/agents", tags=["agents"])


@router.post(
    "/document_intelligence/extract",
    response_model=DocumentIntelligenceOutput,
    summary="Run the Document Intelligence agent against a case's documents",
    description=(
        "Calls the Document Intelligence agent with the supplied case id and "
        "document refs. Returns the extracted fields with provenance + "
        "confidence band. Every invocation writes one ledger entry."
    ),
)
async def extract_document_fields(
    payload: DocumentIntelligenceInput,
) -> DocumentIntelligenceOutput:
    try:
        return await document_intelligence(payload)
    except AgentExecutionError as exc:
        # The decorator already wrote an `agent.failed` ledger entry. Surface
        # the failure as a 502 so the ADK runtime sees a typed error rather
        # than a 500 + traceback.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

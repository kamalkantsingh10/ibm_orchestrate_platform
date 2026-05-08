"""watsonx Writing-LLM impl — Story 7.3 / AC #2.

Mirrors ``WatsonxDocAILLM``. Calls watsonx.ai's text-generation HTTP
endpoint via httpx. Optional in CI — tests skip without
``WATSONX_APIKEY``.

The model is instructed (by the rendered prompt) to return strict JSON
with ``paragraphs`` and ``cited_claims``. Parse failures raise
``WritingLLMError`` and bubble up so the supervisor can record a
``writing.failed`` ledger entry without rolling back intake.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import httpx
from contracts.writing import CitedClaim, EddMemoSections

from agents.adapters.writing.base import RawRationaleDraft, WritingLLMError
from agents.supervisor.action_decorator import (
    set_runtime_model_id,
    set_runtime_prompt_hash,
)


class WatsonxWritingLLM:
    """Single LLM-call rationale drafter. Production-shaped, demo-optional."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        project_id: str | None = None,
        model_id: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        api_key_resolved = api_key or os.environ.get("WATSONX_APIKEY") or os.environ.get("WATSONX_API_KEY")
        project_id_resolved = project_id or os.environ.get("WATSONX_PROJECT_ID")
        if not api_key_resolved or not project_id_resolved:
            raise WritingLLMError(
                "WATSONX_APIKEY / WATSONX_PROJECT_ID missing — set WRITING_LLM_PROVIDER=fixture for offline demo"
            )
        self._api_key = api_key_resolved
        self._project_id = project_id_resolved
        self.model_id = (
            model_id
            or os.environ.get("WATSONX_WRITING_MODEL_ID")
            or os.environ.get("WATSONX_MODEL_ID")
            or "ibm/granite-3-2-8b-instruct"
        )
        self._endpoint = endpoint or os.environ.get("WATSONX_ENDPOINT", "https://us-south.ml.cloud.ibm.com")

    async def draft_rationale(
        self,
        *,
        rendered_prompt: str,
    ) -> RawRationaleDraft:
        prompt_hash = hashlib.sha256(rendered_prompt.encode("utf-8")).hexdigest()
        set_runtime_model_id(self.model_id)
        set_runtime_prompt_hash(prompt_hash)
        try:
            raw = await self._call(rendered_prompt)
        except httpx.HTTPError as exc:
            raise WritingLLMError(f"watsonx call failed: {exc}") from exc
        return _parse_response(raw)

    async def draft_edd_memo(
        self,
        *,
        rendered_prompt: str,
    ) -> EddMemoSections:
        # Story 8.3 ships the EDD memo path on the fixture provider only.
        # The watsonx EDD prompt + parser lands later — until then, fail
        # loud so a misconfigured WRITING_LLM_PROVIDER=watsonx demo
        # surfaces immediately rather than silently.
        raise NotImplementedError(
            "WatsonxWritingLLM.draft_edd_memo is not yet implemented; "
            "set WRITING_LLM_PROVIDER=fixture for EDD drafting."
        )

    async def _call(self, prompt: str) -> str:
        url = f"{self._endpoint}/ml/v1/text/generation?version=2024-05-01"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model_id": self.model_id,
            "project_id": self._project_id,
            "input": prompt,
            "parameters": {
                "decoding_method": "greedy",
                "max_new_tokens": 1024,
            },
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        results = data.get("results", [])
        if not results:
            raise WritingLLMError("watsonx returned no results")
        text: str = results[0].get("generated_text", "")
        return text


def _parse_response(raw: str) -> RawRationaleDraft:
    try:
        body: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WritingLLMError(f"watsonx response was not JSON: {raw!r}") from exc
    if not isinstance(body, dict):
        raise WritingLLMError(f"watsonx response was not a JSON object: {type(body).__name__}")
    paragraphs = body.get("paragraphs")
    cited_claims_raw = body.get("cited_claims", [])
    if not isinstance(paragraphs, list) or not all(isinstance(p, str) for p in paragraphs):
        raise WritingLLMError("watsonx 'paragraphs' must be a list[str]")
    if not isinstance(cited_claims_raw, list):
        raise WritingLLMError("watsonx 'cited_claims' must be a list")
    try:
        cited_claims = [
            CitedClaim(
                text=str(item.get("text", "")),
                evidence_ledger_id=str(item.get("evidence_ledger_id", "")),
            )
            for item in cited_claims_raw
            if isinstance(item, dict)
        ]
    except Exception as exc:  # pragma: no cover — defensive
        raise WritingLLMError(f"watsonx cited_claims parse failed: {exc}") from exc
    return RawRationaleDraft(paragraphs=paragraphs, cited_claims=cited_claims)

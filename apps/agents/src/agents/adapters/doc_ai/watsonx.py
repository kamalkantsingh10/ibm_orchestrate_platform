"""watsonx Doc-AI impl — Story 3.4 / AC #5.

Calls the watsonx.ai text-generation HTTP endpoint via ``httpx`` (already a
transitive dep via FastAPI in cockpit-api). Resists pulling in
``langchain-ibm`` to keep the demo's dep footprint small.

The watsonx path is OPTIONAL in CI — tests are skipped without
``WATSONX_API_KEY`` (Story 3.4 § AC10). The impl still imports clean so the
``make lint`` pass exercises every line of typing.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from contracts.confidence import to_band
from contracts.document_intelligence import ExtractedField, FieldValue
from contracts.provenance import Provenance, ProvenancedField
from jinja2 import Environment, FileSystemLoader, select_autoescape

from agents.adapters.doc_ai.base import DocAILLMError
from agents.jurisdictions.india import FieldSpec
from agents.supervisor.action_decorator import (
    set_runtime_model_id,
    set_runtime_prompt_hash,
)

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts" / "document_intelligence"


def _build_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_PROMPT_DIR),
        autoescape=select_autoescape(default=False),
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )


_ENV = _build_jinja_env()


class WatsonxDocAILLM:
    """Single LLM-call doc-AI impl. Production-shaped, demo-optional."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        project_id: str | None = None,
        model_id: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        # WATSONX_APIKEY (no underscore) is the canonical name used by the
        # ADK Developer Edition. Accept WATSONX_API_KEY too for backward
        # compatibility with earlier .env files.
        api_key_resolved = api_key or os.environ.get("WATSONX_APIKEY") or os.environ.get("WATSONX_API_KEY")
        project_id_resolved = project_id or os.environ.get("WATSONX_PROJECT_ID")
        if not api_key_resolved or not project_id_resolved:
            raise RuntimeError(
                "WATSONX_APIKEY / WATSONX_PROJECT_ID missing — set DOC_AI_PROVIDER=fixture for offline demo"
            )
        self._api_key = api_key_resolved
        self._project_id = project_id_resolved
        self.model_id = model_id or os.environ.get("WATSONX_MODEL_ID") or "ibm/granite-3-2-8b-instruct"
        self._endpoint = endpoint or os.environ.get("WATSONX_ENDPOINT", "https://us-south.ml.cloud.ibm.com")

    async def extract(
        self,
        *,
        document_ref: str,
        text: str | None,
        taxonomy: list[FieldSpec],
    ) -> list[ExtractedField]:
        if text is None:
            raise DocAILLMError(f"watsonx doc-AI requires PDF text; got None for {document_ref}")

        rendered = render_prompt(document_ref=document_ref, text=text, taxonomy=taxonomy)
        prompt_hash = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
        # Surface model_id + prompt_hash into the @agent_action ledger entry.
        set_runtime_model_id(self.model_id)
        set_runtime_prompt_hash(prompt_hash)

        try:
            response = await self._call(rendered)
        except httpx.HTTPError as exc:
            raise DocAILLMError(f"watsonx call failed: {exc}") from exc

        return _parse_response(
            raw=response,
            document_ref=document_ref,
            taxonomy=taxonomy,
            model_id=self.model_id,
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
            raise DocAILLMError("watsonx returned no results")
        text: str = results[0].get("generated_text", "")
        return text


def render_prompt(*, document_ref: str, text: str, taxonomy: list[FieldSpec]) -> str:
    """Render the extract_v1 prompt; exposed for tests."""
    template = _ENV.get_template("extract_v1.j2")
    return template.render(
        document_ref=document_ref,
        text=text,
        taxonomy=taxonomy,
    )


def _parse_response(
    *,
    raw: str,
    document_ref: str,
    taxonomy: list[FieldSpec],
    model_id: str,
) -> list[ExtractedField]:
    try:
        items: list[dict[str, Any]] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DocAILLMError(f"watsonx response was not JSON: {raw!r}") from exc
    if not isinstance(items, list):
        raise DocAILLMError(f"watsonx response was not a JSON array: {type(items).__name__}")

    spec_by_name = {spec.field_name: spec for spec in taxonomy}
    captured_at = datetime.now(UTC)
    extracted: list[ExtractedField] = []
    for item in items:
        name = item.get("field_name")
        spec = spec_by_name.get(name) if name else None
        if spec is None:
            continue
        value = _coerce_value(item.get("value"), spec)
        confidence = float(item.get("confidence", 0.0))
        if confidence < 0.0 or confidence > 1.0:
            raise DocAILLMError(f"watsonx returned confidence outside [0,1] for {name}: {confidence}")
        provenance = Provenance(
            source_agent="document_intelligence",
            source_system=f"watsonx_{model_id}",
            confidence=confidence,
            confidence_band=to_band(confidence),
            evidence_ids=[],
            captured_at=captured_at,
        )
        pf: ProvenancedField[FieldValue] = ProvenancedField(value=value, provenance=provenance)
        extracted.append(
            ExtractedField(
                field_name=spec.field_name,
                document_ref=document_ref,
                value=pf,
            )
        )
    return extracted


def _coerce_value(raw: Any, spec: FieldSpec) -> FieldValue:
    """Best-effort coercion to FieldValue per the FieldSpec ``type``."""
    if raw is None:
        return None
    target = spec.type
    try:
        if target == "int":
            return int(raw)
        if target == "float":
            return float(raw)
        if target == "bool":
            return bool(raw)
        return str(raw)
    except (TypeError, ValueError) as exc:
        raise DocAILLMError(f"watsonx value for {spec.field_name} was not coercible to {target}") from exc

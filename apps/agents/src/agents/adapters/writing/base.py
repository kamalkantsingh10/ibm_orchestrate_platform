"""Writing-LLM Protocol + error type — Stories 7.3 (rationale) and 8.3 (EDD memo).

Mirrors `agents.adapters.doc_ai.base`. The Protocol exposes two narrow
async methods — ``draft_rationale`` (v1) and ``draft_edd_memo`` (v2) —
each takes a fully-rendered Jinja prompt and returns a structured
typed model. The agent — not the adapter — owns Jinja rendering, HTML
wrapping, and citation safety. This keeps the adapter substitutable: a
fixture impl returns deterministic output for CI; the watsonx impl
talks to a real LLM.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contracts.writing import CitedClaim, EddMemoSections
from pydantic import BaseModel


class WritingLLMError(RuntimeError):
    """Raised by a ``WritingLLM`` impl on transient failure."""


class RawRationaleDraft(BaseModel):
    """Internal Pydantic model returned by a ``WritingLLM``. The agent
    assembles the final HTML from this; the adapter is not responsible
    for Tiptap wrapping.
    """

    model_config = {"frozen": True}

    paragraphs: list[str]
    cited_claims: list[CitedClaim]


@runtime_checkable
class WritingLLM(Protocol):
    """Pluggable rationale-draft backend. The agent passes a fully-
    rendered Jinja prompt; the adapter is responsible for invoking the
    model, parsing JSON output, and returning a typed result.

    ``draft_rationale`` powers Story 7.3 (v1 rationale).
    ``draft_edd_memo`` powers Story 8.3 (v2 EDD memo, five sections).
    """

    model_id: str

    async def draft_rationale(
        self,
        *,
        rendered_prompt: str,
    ) -> RawRationaleDraft: ...

    async def draft_edd_memo(
        self,
        *,
        rendered_prompt: str,
    ) -> EddMemoSections: ...

"""Document-AI LLM Protocol + error type — Story 3.4 / AC #3."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contracts.document_intelligence import ExtractedField

from agents.jurisdictions.india import FieldSpec


class DocAILLMError(RuntimeError):
    """Raised by a ``DocAILLM`` impl on transient failure (auth, parse, IO)."""


@runtime_checkable
class DocAILLM(Protocol):
    """Pluggable extraction backend.

    The fixture impl ignores ``text``; the watsonx impl reads it. ``taxonomy``
    is the per-category list of expected fields (i.e., already category-scoped
    by the calling agent — not the whole DocTaxonomy).
    """

    model_id: str

    async def extract(
        self,
        *,
        document_ref: str,
        text: str | None,
        taxonomy: list[FieldSpec],
    ) -> list[ExtractedField]: ...

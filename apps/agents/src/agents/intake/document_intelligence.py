"""Document Intelligence agent — Story 3.4 / AC #7.

Real ADK pattern: Pydantic input/output contracts, ``@agent_action``
decorator wraps the call so each invocation hits the ledger, and a
pluggable ``DocAILLM`` backend (fixture or watsonx) does the actual work.

The agent is invocable directly via Python — registering with the ADK
Developer Edition is optional and out of scope for the demo CI (the YAML
manifest at ``document_intelligence.yaml`` exists for showcase value but is
not required for tests or the demo's golden path).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from contracts.document_intelligence import (
    DocumentIntelligenceInput,
    DocumentIntelligenceOutput,
    ExtractedField,
)

from agents.adapters.doc_ai.base import DocAILLM, DocAILLMError
from agents.adapters.doc_ai.fixture import FixtureDocAILLM
from agents.jurisdictions.india import FieldSpec, get_india_taxonomy
from agents.supervisor.action_decorator import (
    agent_action,
    set_runtime_model_id,
)

logger = logging.getLogger(__name__)

# Filesystem location for uploaded PDFs in watsonx mode (architecture demo
# addendum). Story 3.8 added per-case subdirs:
#   ./fixtures/uploads/<case_id>/<filename>.pdf
# Fixture mode never reads from this path.
_FIXTURE_UPLOAD_DIR = Path("./fixtures/uploads")


def _classify(filename: str) -> str:
    """Filename → taxonomy category. Best-effort heuristic.

    The demo's pinned fixture filenames are predictable
    (``incorporation_certificate.pdf``, ``bank_statement_q1.pdf``, etc.) so
    a stem-based match works. Unknown filenames fall through to ``"unknown"``.
    """
    stem = Path(filename).stem.lower()
    taxonomy = get_india_taxonomy()
    if stem in taxonomy.categories:
        return stem
    # Strip suffixes like ``_q1`` (e.g., ``bank_statement_q1`` → ``bank_statement``).
    base = stem.rsplit("_", 1)[0]
    if base in taxonomy.categories:
        return base
    return "unknown"


def _get_default_llm() -> DocAILLM:
    provider = os.environ.get("DOC_AI_PROVIDER", "fixture").lower()
    if provider == "fixture":
        return FixtureDocAILLM()
    if provider == "watsonx":
        from agents.adapters.doc_ai.watsonx import WatsonxDocAILLM

        return WatsonxDocAILLM()
    raise ValueError(f"unknown DOC_AI_PROVIDER: {provider!r}")


def _read_pdf_text(case_id: str, filename: str) -> str | None:
    """Return concatenated PDF text or ``None`` if the file is missing.

    Story 3.8 case-scoped path: ``./fixtures/uploads/<case_id>/<filename>``.
    Falls back to the legacy flat path ``./fixtures/uploads/<filename>`` so
    pre-3.8 demo content (if any) keeps working.
    """
    case_path = _FIXTURE_UPLOAD_DIR / case_id / filename
    legacy_path = _FIXTURE_UPLOAD_DIR / filename
    if case_path.exists():
        path = case_path
    elif legacy_path.exists():
        path = legacy_path
    else:
        logger.warning("doc_intelligence.file_not_found case=%s ref=%s", case_id, filename)
        return None

    import pypdf  # local import — pypdf is heavy, defer

    text_parts: list[str] = []
    with path.open("rb") as f:
        reader = pypdf.PdfReader(f)
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


@agent_action(
    agent_id="document_intelligence",
    model_id="fixture",  # overridden at call time via set_runtime_model_id
    prompt_template_id="document_intelligence/extract_v1",
)
async def document_intelligence(
    input: DocumentIntelligenceInput,
    *,
    llm: DocAILLM | None = None,
) -> DocumentIntelligenceOutput:
    """Run doc-AI extraction across ``input.document_refs``.

    The supervisor (Story 3-5) is responsible for back-filling
    ``ExtractedField.value.provenance.evidence_ids`` with the agent's own
    ledger-entry ID after ``@agent_action`` writes the entry.
    """
    resolved_llm = llm if llm is not None else _get_default_llm()
    # Surface the resolved model_id into the ledger entry per Story 3.4 AC9.
    set_runtime_model_id(resolved_llm.model_id)

    taxonomy = get_india_taxonomy()
    use_watsonx = isinstance(resolved_llm, FixtureDocAILLM) is False

    combined: list[ExtractedField] = []
    for ref in input.document_refs:
        category = _classify(ref)
        field_specs: list[FieldSpec] = taxonomy.categories.get(category, [])
        text = _read_pdf_text(input.case_id, ref) if use_watsonx else None
        try:
            extracted = await resolved_llm.extract(document_ref=ref, text=text, taxonomy=field_specs)
        except DocAILLMError:
            # Re-raise so @agent_action records an agent.failed ledger entry.
            raise
        combined.extend(extracted)

    return DocumentIntelligenceOutput(
        case_id=input.case_id,
        extracted_fields=combined,
    )

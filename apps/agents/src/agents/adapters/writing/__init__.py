"""Writing-LLM adapters — Story 7.3.

Default provider is ``fixture``; set ``WRITING_LLM_PROVIDER=watsonx`` to
swap in the real adapter for the demo run.
"""

from __future__ import annotations

import os

from agents.adapters.writing.base import (
    RawRationaleDraft,
    WritingLLM,
    WritingLLMError,
)
from agents.adapters.writing.fixture import FixtureWritingLLM

__all__ = [
    "FixtureWritingLLM",
    "RawRationaleDraft",
    "WritingLLM",
    "WritingLLMError",
    "get_default_writing_llm",
]


def get_default_writing_llm() -> WritingLLM:
    provider = os.environ.get("WRITING_LLM_PROVIDER", "fixture").lower()
    if provider == "fixture":
        return FixtureWritingLLM()
    if provider == "watsonx":
        from agents.adapters.writing.watsonx import WatsonxWritingLLM

        return WatsonxWritingLLM()
    raise ValueError(f"Unknown WRITING_LLM_PROVIDER={provider!r}. Demo supports 'fixture' (default) or 'watsonx'.")

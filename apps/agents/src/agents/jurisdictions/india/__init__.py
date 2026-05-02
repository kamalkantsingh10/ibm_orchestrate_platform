"""India SME doc taxonomy loader — Story 3.4 / AC #2."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

_TAXONOMY_PATH = Path(__file__).parent / "doc_taxonomy.yaml"


class FieldSpec(BaseModel):
    """One expected field within a doc category."""

    model_config = {"frozen": True}

    field_name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    required: bool = False
    validation: str | None = None


class DocTaxonomy(BaseModel):
    """Map of category → list of FieldSpec."""

    model_config = {"frozen": True}

    categories: dict[str, list[FieldSpec]]


@lru_cache(maxsize=1)
def get_india_taxonomy() -> DocTaxonomy:
    """Load and parse the India SME taxonomy YAML once per process."""
    with _TAXONOMY_PATH.open("rb") as f:
        raw: dict[str, list[dict[str, Any]]] = yaml.safe_load(f) or {}
    categories: dict[str, list[FieldSpec]] = {}
    for category, fields in raw.items():
        categories[category] = [
            FieldSpec(
                field_name=item["field"],
                type=item.get("type", "str"),
                required=bool(item.get("required", False)),
                validation=item.get("validation"),
            )
            for item in fields
        ]
    return DocTaxonomy(categories=categories)

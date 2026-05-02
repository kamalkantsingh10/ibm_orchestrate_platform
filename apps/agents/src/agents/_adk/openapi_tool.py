"""Library: build a filtered OpenAPI spec from cockpit-api for ADK tool import.

Each ADK-registered tool that wraps a cockpit-api endpoint owns a tiny
``gen_openapi.py`` shim under its registry directory that calls
``build_and_write`` with the right config. The make ``adk-spec`` target
walks the registry and runs each shim from inside the cockpit-api Poetry
venv (so ``cockpit_api.main:app`` is importable).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_HOST = "http://host.docker.internal:8000"


def build_and_write(
    *,
    path_filter: str,
    operation_id: str,
    title: str,
    output: Path,
    description: str | None = None,
    host: str = DEFAULT_HOST,
) -> None:
    """Build a filtered OpenAPI spec and write it to ``output``.

    Args:
        path_filter: The cockpit-api path to extract (e.g.
            ``/v1/agents/document_intelligence/extract``).
        operation_id: The friendly name the ADK runtime registers the
            tool under (shown in ``orchestrate tools list``).
        title: ``info.title`` for the generated spec.
        output: Where to write the resulting YAML.
        description: Optional ``info.description`` for the generated spec.
        host: Base URL the ADK runtime should call. Defaults to
            ``http://host.docker.internal:8000`` so Developer Edition's
            containers can reach cockpit-api running on the host.
    """
    from cockpit_api.main import app  # local import: cockpit-api venv only

    full = app.openapi()
    if path_filter not in full["paths"]:
        raise RuntimeError(
            f"cockpit-api OpenAPI is missing {path_filter} — is the corresponding router wired in cockpit_api/main.py?"
        )

    path_item = full["paths"][path_filter]
    if "post" in path_item:
        path_item["post"]["operationId"] = operation_id

    # IBM ADK's OpenAPI tool importer requires OpenAPI 3.0 (per
    # https://developer.watson-orchestrate.ibm.com/tools/create_openapi_tool.md).
    # FastAPI generates 3.1 by default — pin to 3.0.3 here. Our schemas use
    # only 3.0-compatible features (no prefixItems, no $defs at the spec
    # root); if we ever add 3.1-only constructs, the pin will fail loudly
    # at import time.
    spec: dict[str, Any] = {
        "openapi": "3.0.3",
        "info": {
            "title": title,
            "version": "0.1.0",
            "description": description or (f"ADK tool spec for {operation_id}. Generated from cockpit-api."),
        },
        "servers": [
            {
                "url": host,
                "description": ("Cockpit API on the host (resolved from inside the Developer Edition Docker network)."),
            },
        ],
        "paths": {path_filter: path_item},
        "components": full.get("components", {}),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w") as f:
        yaml.safe_dump(spec, f, sort_keys=False, default_flow_style=False)
    print(f"Wrote {output}")

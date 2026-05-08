"""Generate openapi.yaml for the cockpit_chat agent's 4 tools — Story 6.7.

The Cockpit Chat agent calls back into cockpit-api for four operations
(`get_case`, `get_reasoning_trace`, `re_run_agent`, `query_ledger`). All
four live in the same OpenAPI tool spec so a single
`orchestrate tools import -k openapi -f openapi.yaml` registers the lot.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_HOST = "http://host.docker.internal:8000"


def _resolve_host() -> str:
    env_override = os.environ.get("COCKPIT_API_PUBLIC_URL")
    if env_override:
        return env_override.rstrip("/")
    return DEFAULT_HOST


_TOOLS: list[tuple[str, str, str]] = [
    # (path, verb, operationId)
    ("/v1/cases/{case_id}", "get", "get_case"),
    (
        "/v1/cases/{case_id}/agent-actions/{action_id}/reasoning-trace",
        "get",
        "get_reasoning_trace",
    ),
    ("/v1/cases/{case_id}/agents/{agent_slug}/run", "post", "re_run_agent"),
    ("/v1/cases/{case_id}/ledger", "get", "query_ledger"),
]


def main() -> None:
    from cockpit_api.main import app  # local import: cockpit-api venv only

    host = _resolve_host()
    full = app.openapi()

    paths: dict[str, Any] = {}
    for path_filter, verb, operation_id in _TOOLS:
        if path_filter not in full["paths"]:
            raise RuntimeError(f"cockpit-api OpenAPI is missing {path_filter} — is the router wired?")
        path_item = dict(full["paths"][path_filter])
        if verb in path_item:
            op = dict(path_item[verb])
            op["operationId"] = operation_id
            # Cloud Orchestrate's tool importer requires a non-empty
            # description on every operation. Fall back to summary if the
            # source FastAPI route only declared a summary.
            if not op.get("description"):
                op["description"] = op.get("summary") or operation_id
            path_item[verb] = op
        paths[path_filter] = path_item

    spec: dict[str, Any] = {
        "openapi": "3.0.3",
        "info": {
            "title": "KYC Cockpit Chat (ADK Tools)",
            "version": "0.1.0",
            "description": (
                "Cockpit Chat agent's 4 tools (`get_case`, `get_reasoning_trace`, "
                "`re_run_agent`, `query_ledger`). Generated from cockpit-api."
            ),
        },
        "servers": [
            {
                "url": host,
                "description": (
                    "Cockpit API endpoint reachable by the Orchestrate runtime. "
                    "For cloud Orchestrate, this is a public ngrok tunnel "
                    "(refresh via `make tunnel-sync`); for Developer Edition, "
                    "host.docker.internal."
                ),
            }
        ],
        "paths": paths,
        "components": full.get("components", {}),
    }

    output = Path(__file__).parent / "openapi.yaml"
    with output.open("w") as f:
        yaml.safe_dump(spec, f, sort_keys=False, default_flow_style=False)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()

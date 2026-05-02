# Story 3.4 — ADK demo flow

## What's wired

| Layer | Where | Notes |
|---|---|---|
| **HTTP boundary** | `POST /v1/agents/document_intelligence/extract` on cockpit-api | Wraps the existing `document_intelligence` agent function. Each invocation writes one `agent.completed` (or `agent.failed`) ledger entry via `@agent_action`. |
| **OpenAPI tool spec** | `apps/agents/src/agents/registry/document_intelligence/openapi.yaml` | Generated from the live cockpit-api `app.openapi()`. The `servers[0].url` is `http://host.docker.internal:8000` so the Developer Edition's containers can reach cockpit-api running on the host. |
| **Agent manifest** | `apps/agents/src/agents/registry/document_intelligence/agent.yaml` | `kind: native`, `llm: watsonx/ibm/granite-3-2-8b-instruct`, `tools: [extract_document_fields]`. Holds the agent's instructions. |
| **Tool spec generator** | `apps/agents/scripts/generate_openapi_tool_spec.py` | Re-run via `make adk-spec` whenever the endpoint contract changes. |
| **Make targets** | `Makefile` | `adk-up`, `adk-down`, `adk-spec`, `adk-register`, `adk-chat`. |

## Pre-requisites

1. Docker daemon running. `docker --version` should respond.
2. A watsonx.ai API key for the LLM. The Developer Edition runs locally but the LLM calls go to watsonx cloud (`us-south.ml.cloud.ibm.com` by default). Free tier works.
3. Set the key in your shell before `make adk-up` (the Developer Edition reads it on startup):

   ```bash
   export WATSONX_APIKEY=...                  # required
   export WATSONX_SPACE_ID=...                # optional; defaults to the one the SDK falls back to
   ```

## Demo flow (four terminals, one-time setup)

```bash
# Terminal 1 — cockpit-api on :8000 (must be up so the ADK runtime can reach the tool endpoint)
make demo-reset             # fresh seeded DB + ledger
make dev                    # uvicorn cockpit-api + Vite cockpit-ui

# Terminal 2 — Developer Edition (Docker; first run pulls images, ~5-10 min)
make adk-up

# Terminal 3 — register the document_intelligence tool + agent (idempotent)
make adk-register
#   → orchestrate tools import -k openapi -f .../openapi.yaml
#   → orchestrate agents import -f .../agent.yaml

# Terminal 4 — open the chat UI in your browser
make adk-chat
```

## Verifying the demo end-to-end

1. In the chat UI, type something like:
   ```
   Process case case_01KQC7GQ70GYHP15CZ8JB5ZT6A with documents
   incorporation_certificate.pdf, pan_card.pdf, address_proof.pdf,
   director_id.pdf, bank_statement_q1.pdf
   ```
2. The agent (LLM) should decide to call `extract_document_fields`. The chat UI shows the tool invocation panel.
3. Tail the ledger from another shell:
   ```bash
   tail -f data/ledger.jsonl | python3 -m json.tool
   ```
   You should see one `agent.completed` entry land for each chat-driven invocation, with `payload.agent_id == "document_intelligence"` and the typed `AgentActionLedgerEntry` fields populated.
4. Confirm the agent's reply summarises the extracted fields, calling out any LOW-band confidences.

## Common issues

- **`make adk-register` fails with "no active environment"** — run `orchestrate env list` and `orchestrate env activate <name>` first. The Developer Edition usually creates a `local` env on startup.
- **Tool calls return 502** — cockpit-api isn't running, or `host.docker.internal` doesn't resolve in your Docker network. On Linux, ensure Docker's network mode supports it (`--add-host=host.docker.internal:host-gateway` or Docker 20.10+). On macOS/Windows it's wired by default.
- **Agent picks the wrong tool** — tweak `instructions:` in `agent.yaml` and re-run `make adk-register`. Imports are idempotent.

## What this is NOT yet

- No supervisor agent — Story 3.5 lands the `case_supervisor` collaborator that will own multi-agent fan-out (entity verification, UBO graph, screening, risk scoring).
- No Documents panel UI — Story 3.6 surfaces the extracted fields in the cockpit canvas.
- No `evidence_ids` back-fill — Story 3.5's supervisor re-reads the agent's own ledger entry and stamps it onto each `Provenance.evidence_ids`.

If you want to skip the chat UI and just exercise the endpoint directly:

```bash
curl -s -X POST http://localhost:8000/v1/agents/document_intelligence/extract \
  -H 'Content-Type: application/json' \
  -d '{"case_id": "case_01KQC7GQ70GYHP15CZ8JB5ZT6A", "document_refs": ["incorporation_certificate.pdf", "pan_card.pdf"]}' \
  | python3 -m json.tool
```

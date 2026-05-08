# ibm_orchestrate_platform

Reference implementation of the **KYC Cockpit** on top of the IBM watsonx Orchestrate Agent Development Kit (ADK). A polyglot monorepo:

- **`apps/cockpit-ui/`** — Vite + React 19 + TypeScript (strict) cockpit UI.
- **`apps/cockpit-api/`** — FastAPI service (Python 3.11+) backing the cockpit.
- **`apps/agents/`** — IBM watsonx Orchestrate ADK agents.
- **`packages/contracts/`** — Pydantic schemas shared across Python apps.
- **`tools/verifier/`** — offline ledger verifier CLI (deferred for the demo build; see [What's NOT in this demo](#whats-not-in-this-demo)).
- **`infra/`** — infrastructure-as-code placeholder.

> **Demo build (re-scoped 2026-04-29).** This repo ships the project as a local demo that proves a full-fledged application can be built on IBM ADK agents. Many enterprise capabilities (OIDC, multi-tenant isolation, cryptographic ledger, real screening vendors, pentest, DR, WCAG audit, CCO portfolio) are deferred. The full bank-buyer scope remains documented in `Documentation/planning-artifacts/` and can be revived. See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` for the full re-scope record.

> **Agent runtime update (2026-05-07).** Agents now run on **cloud watsonx Orchestrate**, not the local Developer Edition. The cockpit (UI + API + SQLite) still runs on the developer's machine; cloud Orchestrate reaches cockpit-api via an **ngrok tunnel**. See `Documentation/planning-artifacts/architecture.md#Agent Runtime Update (2026-05-07)`.

## Demo presenter quickstart

Just cloned this and need to run the demo? From cold to running:

```bash
make bootstrap                    # one-time: Poetry + pnpm install + ./data/ + git hooks (copies .env.example → .env)
# Edit .env: set WATSONX_APIKEY=<your IBM Cloud watsonx.ai key>
make migrate && make seed         # initialise the SQLite DB + ledger
# One-time: register the cloud Orchestrate tenant as an ADK env, then activate it.
#   orchestrate env add --name cloud --url <your-tenant-url>
#   orchestrate env activate cloud
ngrok http 8000 &                 # expose cockpit-api to the cloud tenant (separate terminal preferred)
make dev &                        # uvicorn + Vite dev server (Ctrl-C stops both)
make tunnel-sync                  # pulls the ngrok URL into every registry openapi.yaml + re-imports
```

Then:

- **Cockpit UI** at <http://localhost:5173> — opens as the **Analyst** (Kamal Singh). Use the user dropdown in the top-right to switch among the [three demo roles](#demo-users).
- **Orchestrate cloud chat UI** — open your tenant's Orchestrate web app and pick the registered agent (e.g. `case_supervisor`). The LLM decides when to invoke the cockpit-api-backed tools through the tunnel. See [Talking to the agents](#talking-to-the-agents) for example prompts.

To reset the demo between walkthroughs (wipes mutable state, keeps schema):

```bash
make demo-reset
```

If `make dev` looks unhealthy, `make verify` does a 5-check smoke: SQLite DB, `/health`, `/v1/users/me`, the cockpit-ui port, and the ADK runtime.

## Prerequisites

Install once per developer machine:

- **Node.js ≥ 20** with [Corepack](https://nodejs.org/api/corepack.html) enabled.
- **pnpm ≥ 9** (`corepack enable pnpm`).
- **Python 3.11–3.13** (`ibm-watsonx-orchestrate` constrains the upper bound to `<3.14`).
- **Poetry ≥ 1.7**.
- **GNU Make**.
- **ngrok** ≥ 3 — required to expose `localhost:8000` to cloud Orchestrate. Free tier works; paid tier gives a stable subdomain so `make tunnel-sync` is needed less often.
- **Docker Desktop ≥ 4.x** — *optional*, only for the legacy ADK Developer Edition fallback (`make adk-up`). Cloud Orchestrate is the primary runtime and needs no Docker.

You also need credentials for the runtime side:

- A **cloud watsonx Orchestrate** account with a tenant URL and API key — register the tenant once via `orchestrate env add --name cloud --url <tenant-url>` then `orchestrate env activate cloud`. The activated env is what `make adk-register` and `make tunnel-sync` import into.
- An **ngrok auth token** (`ngrok config add-authtoken <token>`) — required to keep tunnels alive long enough for a demo session.
- A **watsonx.ai API key** is *only* needed if you fall back to the local Developer Edition (`make adk-up`) or if you set `DOC_AI_PROVIDER=watsonx` for the offline doc-AI path. With cloud Orchestrate, LLM keys live in the cloud tenant config — the cockpit codebase owns zero LLM credentials.

```bash
# .env  (gitignored — never commit real values). Only WATSONX_APIKEY is needed
# if DOC_AI_PROVIDER=watsonx OR you fall back to make adk-up. Cloud Orchestrate
# does not read this file.
WATSONX_APIKEY=<your IBM Cloud API key>
WATSONX_MODEL_ID=watsonx/ibm/granite-3-2-8b-instruct
```

## First-time setup

Goal: clone-to-demo in **≤ 60 minutes** (Story 1.5 AC #10).

```bash
git clone <repo> && cd ibm_orchestrate_platform

# 1. Install all workspace dependencies (Poetry + pnpm). Idempotent.
#    Also creates ./data/ for the SQLite DB and copies .env.example → .env
#    (only when .env is missing — never overwrites).
make bootstrap

# 2. Apply Alembic migrations against the SQLite DB at ./data/cockpit.db
#    and seed the three demo cases + ledger bootstrap entries.
make migrate
make seed

# 3. (One-time) Register the cloud watsonx Orchestrate tenant with the ADK
#    CLI and activate it. Replace <tenant-url> with your tenant's API URL.
cd apps/agents
poetry run orchestrate env add --name cloud --url <tenant-url>
poetry run orchestrate env activate cloud   # `orchestrate env list` to verify
cd ../..

# 4. Start an ngrok tunnel pointing at cockpit-api. Leave it running in
#    its own terminal — cloud Orchestrate calls back through this URL.
ngrok http 8000

# 5. Start cockpit-api + cockpit-ui in parallel (separate terminal). Ctrl-C
#    stops both.
make dev
# → http://localhost:5173    (cockpit-ui)
# → http://localhost:8000/docs  (cockpit-api Swagger)

# 6. Pull the live ngrok URL into every registry openapi.yaml and import
#    every agent + tool to the cloud tenant. Idempotent. Re-run any time
#    the tunnel restarts (free-tier ngrok rotates URLs on reconnect).
make tunnel-sync

# 7. Open your Orchestrate cloud tenant's chat UI in a browser, pick the
#    `case_supervisor` agent, and prompt it (see "Talking to the agents").
```

> **Fallback (offline / no cloud tenant):** the legacy `make adk-up` /
> `make adk-down` / `make adk-register` flow still works against a local
> Developer Edition. See [Common ADK issues](#common-adk-issues).

`pre-commit` git hooks are installed during `make bootstrap` (`ruff`, `mypy`, `eslint`, `prettier`, `gitleaks`, `actionlint`). CI runs the same lint surface plus a [`demo-verify` job](.github/workflows/ci.yml) that boots the stack and runs `make verify` end-to-end.

### How the registry works

Every ADK agent lives in its own subdirectory under `apps/agents/src/agents/registry/`. The structure is the same for every agent:

```
apps/agents/src/agents/registry/
└── <agent_name>/
    ├── agent.yaml          # ADK manifest (kind, llm, tools, instructions)
    ├── openapi.yaml        # tool spec, if the agent exposes cockpit-api endpoints (generated)
    └── gen_openapi.py      # generator for openapi.yaml — calls _adk.openapi_tool.build_and_write
```

`make adk-spec` walks `registry/*/gen_openapi.py` and regenerates each `openapi.yaml` from the live cockpit-api FastAPI app. `make adk-register` then imports every `openapi.yaml` and every `agent.yaml`. Adding a new agent is a matter of dropping a directory — no per-agent Make rules to maintain.

Currently registered (Epic 3):

| Agent | Directory | Tool exposed |
|---|---|---|
| `document_intelligence` | `registry/document_intelligence/` | `extract_document_fields` (POST `/v1/agents/document_intelligence/extract`) |
| `case_supervisor` | `registry/case_supervisor/` | `run_case_intake` (POST `/v1/cases/{case_id}/intake`) — supervisor; delegates to `document_intelligence` |
| `list_cases` | `registry/list_cases/` | `list_cases` (GET `/v1/cases`) |

## Daily development

```bash
make dev          # uvicorn + Vite (parallel; SIGINT-safe)
make test         # pytest in each Python project + Vitest in cockpit-ui
make lint         # Ruff + mypy + ESLint + Prettier + P4 (agent ledger) discipline
make migrate      # apply new Alembic revisions
make seed         # re-seed (idempotent)
make verify       # 5-check smoke against the running stack
make demo-reset   # wipe ./data/cockpit.db + ./data/ledger.jsonl + ./fixtures/uploads/, then migrate + seed
make contracts    # regenerate packages/contracts/openapi.json + apps/cockpit-ui/src/api-types.ts
make tunnel-sync  # pull the live ngrok URL into every registry openapi.yaml + re-import to cloud
make adk-spec     # regenerate apps/agents/src/agents/registry/.../openapi.yaml from cockpit-api
make adk-register # import every agent + tool into the activated Orchestrate env (cloud or fallback)
make adk-up       # [fallback] start the local Developer Edition (Docker)
make adk-down     # [fallback] stop the Developer Edition
make adk-chat     # [fallback] open the local Developer Edition chat UI (cloud uses the Orchestrate web app)
make clean        # remove venvs, node_modules, build artefacts, AND ./data/cockpit.db
```

> Run `make contracts` whenever you change a router under `apps/cockpit-api/src/cockpit_api/routers/` or a Pydantic contract that crosses the wire. Both generated files are committed; CI fails on drift.

The cockpit opens as the **Analyst** (Kamal Singh). Use the user dropdown in the top right to switch among the three demo roles — see [Demo users](#demo-users).

## Talking to the agents

Once `make tunnel-sync` is done, every agent registered under `apps/agents/src/agents/registry/` is reachable from your **cloud Orchestrate tenant's chat UI**. Pick the agent and prompt it in plain English — the LLM decides when to call its tools (which reach back to your local cockpit-api through the ngrok tunnel).

### `document_intelligence` — Epic 3

Try this prompt in the chat UI:

```
Process case case_01KQC7GQ70GYHP15CZ8JB5ZT6A with documents
incorporation_certificate.pdf, pan_card.pdf, address_proof.pdf,
director_id.pdf, bank_statement_q1.pdf
```

What happens under the hood:

1. Cloud chat sends the prompt to the **`document_intelligence`** ADK agent.
2. The agent (per `agent.yaml` instructions) decides to call **`extract_document_fields`**.
3. Cloud Orchestrate POSTs to `<ngrok-url>/v1/agents/document_intelligence/extract`. ngrok forwards to `localhost:8000` on your machine.
4. cockpit-api runs the `document_intelligence` Python coroutine; the `@agent_action` decorator writes one `agent.completed` ledger entry to `./data/ledger.jsonl`.
5. Typed extracted fields flow back to the LLM, which summarises them in plain English (top fields by confidence, LOW-band rows that need analyst eyes).

To watch ledger entries land in real time, tail the file from another terminal:

```bash
tail -f data/ledger.jsonl | python3 -m json.tool
```

### Skipping the chat UI (curl)

To confirm the cockpit-api endpoint works without going through Orchestrate at all:

```bash
curl -s -X POST http://localhost:8000/v1/agents/document_intelligence/extract \
  -H 'Content-Type: application/json' \
  -d '{
    "case_id": "case_01KQC7GQ70GYHP15CZ8JB5ZT6A",
    "document_refs": ["incorporation_certificate.pdf", "pan_card.pdf"]
  }' | python3 -m json.tool
```

You should see typed `extracted_fields` with provenance + confidence bands, and a new entry in `data/ledger.jsonl`.

### When to re-run `make tunnel-sync` / `make adk-register`

- **`make tunnel-sync`**: every time ngrok restarts (free tier rotates URLs on reconnect), or any time you change a router/contract that affects the `openapi.yaml` shape.
- **`make adk-register`**: after editing any `agent.yaml` (LLM, instructions, tool list), or after dropping a new agent directory into the registry. `tunnel-sync` already calls `adk-register` internally; only run `adk-register` standalone when the tunnel URL is stable.

Imports are idempotent; re-running updates each spec in place.

### Common ADK issues

- **`make tunnel-sync` errors with "no ngrok tunnel found"** — start one with `ngrok http 8000` in another terminal, then re-run.
- **`make adk-register` fails with "no active environment"** — run `orchestrate env list` and `orchestrate env activate cloud` (or your tenant env name).
- **Tool calls return 502 / 504 from the chat UI** — most often the ngrok tunnel rotated. Re-run `make tunnel-sync`. Less often: `make dev` isn't running, so cockpit-api can't accept the call.
- **Agent picks the wrong tool / hallucinates** — tighten the `instructions:` block in the agent's `agent.yaml` and re-run `make tunnel-sync` (or `make adk-register` if the tunnel is stable).
- **Falling back to local Developer Edition** — `make adk-up` (Docker pull on first run) → `make adk-register` (against the local `local` env after `orchestrate env activate local`) → `make adk-chat` (<http://localhost:3000>). Requires `WATSONX_APIKEY` in `.env`.

For deeper architectural detail see `Documentation/implementation-artifacts/3-4-adk-demo-flow.md` and `Documentation/planning-artifacts/architecture.md#Agent Runtime Update (2026-05-07)`.

## Demo users

The demo build has no real auth. Three hardcoded users back the user-switcher dropdown — switching among them changes the visible routes. See `Documentation/implementation-artifacts/1-4-cockpit-shell-with-user-switcher-three-hardcoded-roles.md` for full context.

| Role | Name | Default route | Persona reference |
|---|---|---|---|
| Analyst | Kamal Singh | `/queue` | UX User Journey 1 (Priya — substituted for the demo presenter) |
| Team Lead | Rohan Mehta | `/approvals` | UX User Journey 3 |
| Regulator | Anika Iyer | `/regulator-lens` | UX User Journey 4 |

UUIDs are pinned in `packages/contracts/src/contracts/users.py` and mirrored in `.env.example` (`DEMO_ANALYST_ID`, `DEMO_TEAM_LEAD_ID`, `DEMO_REGULATOR_ID`). The contract is the source of truth.

## Three demo cases

Three fixture cases load automatically on `make seed` and back the demo's narrative arc — open the Queue Rail to see them in this order (newest at top):

| Case | Archetype | Demo journey |
|---|---|---|
| **Ananya Iyer** | Individual customer with a synthetic screening hit | Exercises the Screening agent's 3-column explainer (Epic 6) |
| **Vora Capital Holdings** | Multi-layered shell-UBO + recent incorporation | Journey 2 — EDD escalation; UBO Graph + Risk Scoring (Epics 5, 8) |
| **Shree Venkat Trading** | Clean SME approval | Journey 1 — happy path; Document Intelligence + commit |

Pinned IDs are exported from `packages/contracts/src/contracts/cases.py` (`SHREE_VENKAT_ID`, `VORA_CAPITAL_ID`, `ANANYA_IYER_ID`) and mirrored as documentation in `.env.example`.

Between demo passes, `make demo-reset` rewinds the queue to these three cases.

## Stakeholder evaluation: clone-to-running

For someone evaluating the project end-to-end without the presenter on hand.

### Time budget (≤ 60 min cold)

| Phase | Budget | Notes |
|---|---|---|
| Prerequisite install (one-time per machine) | ≤ 20 min | Node 20+, pnpm 9+, Python 3.11+, Poetry 1.7+, GNU Make, ngrok 3+. Not counted toward the 60 min if pre-installed. |
| Cloud Orchestrate tenant + ngrok auth (one-time) | ≤ 10 min | Sign up for tenant, generate API key, `orchestrate env add` + `activate`, register ngrok auth token. |
| `git clone` | ≤ 2 min | Connection-bound. |
| `make bootstrap` | ≤ 15 min | Poetry + pnpm first install over network. |
| `make migrate` + `make seed` | ≤ 30 sec | SQLite is instant. |
| `ngrok http 8000` | ≤ 10 sec | Tunnel up. |
| `make dev` cold start | ≤ 90 sec | Story 1.2 AC #10 budget; preserved. |
| `make tunnel-sync` *(first run)* | ≤ 60 sec | Fetches tunnel URL, regenerates 3 openapi.yaml files, imports tools + agents to the cloud tenant. |
| `make verify` smoke check | ≤ 30 sec | Curl + sqlite ping. |
| **Total (cold, prerequisites + tenant pre-set-up)** | **≤ 20 min** | Comfortable inside 60 min. |
| **Total (cold, including prerequisites + tenant onboarding)** | **≤ 60 min** | The binding metric. |

To record a measurement, run `make verify-timing` — it appends a row to `Documentation/implementation-artifacts/cold-start-measurements.md`.

### What you should see

After `make dev` and a browser hit on `http://localhost:5173`:

- The **TopBar** shows the wordmark "Cockpit" on the left and a user-switcher dropdown on the right with "Kamal Singh / Analyst".
- The default route is `/queue`. The Queue Rail (Story 2-3) renders three rows in this order: **Ananya Iyer** (newest), **Vora Capital Holdings**, **Shree Venkat Trading** (oldest), each with the "Intake scheduled" state badge. Story 4-1 will layer risk × SLA ordering on top.
- Clicking the user-switcher reveals the three demo users. Selecting "Rohan Mehta" navigates to `/approvals`; "Anika Iyer" navigates to `/regulator-lens`.
- The Cockpit API's interactive Swagger docs are at <http://localhost:8000/docs>. `GET /v1/users/me` requires the `X-Cockpit-Demo-User` header (the cockpit-ui injects it automatically).

### What's NOT in this demo

The following are **deferred** by the 2026-04-29 demo re-scope. They remain documented in `Documentation/planning-artifacts/` for revival.

- **OIDC / SAML SSO.** Replaced by the user-switcher dropdown.
- **Multi-tenant isolation.** Single-tenant demo; no `tenant_id` enforcement.
- **Cryptographic audit ledger** (HSM-backed Ed25519 hash chain). Replaced by a simple JSON append-only log when Epic 3 lands.
- **Offline ledger verifier CLI.** `tools/verifier/` is a stub.
- **Real screening vendors** (ComplyAdvantage / LSEG / Dow Jones / ABBYY). Mock-only adapters.
- **Real Document AI integration** (IBM Document AI / Watson Discovery). The DocAI agent will use plain LLM extraction against PDF text.
- **Multi-cloud adapter conformance suites.** One mock per integration.
- **Audit export bundle with hash chain + offline verification.** PDF export only (Epic 9).
- **CCO Portfolio Dashboard.**
- **Pre-pilot pentest, DR rehearsal, WCAG 2.2 AA third-party audit, performance budget verification, confidence calibration study, India jurisdiction-pack lockdown.** Epic 11 is cut entirely.

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` for the full deferral list and rationale.

## Cold-start budget — `make dev`

`make dev` cold-start budget is **≤ 90 seconds** from invocation to all served URLs returning 200 (G6 from architecture, preserved across the demo re-scope).

| Component | Where it runs | Notes |
| --- | --- | --- |
| cockpit-api (uvicorn `--reload`) | `make dev` | < 5 s on a typical laptop. |
| cockpit-ui (Vite dev) | `make dev` | < 5 s; HMR ≪ 1 s. |
| Cloud watsonx Orchestrate | Out of process — your tenant on IBM Cloud | Always-on; no local cold start. Connectivity tested by `make tunnel-sync`. |
| ngrok tunnel | `ngrok http 8000` (separate terminal) | Treat as a long-lived service across `make dev` sessions; re-run `make tunnel-sync` after a tunnel restart. |
| Local Developer Edition (fallback) | `make adk-up` | Docker stack; only relevant if cloud Orchestrate is unavailable. First-run image pull ~5–10 min. |

To measure cold-start on your machine:

```bash
make clean        # destroys venvs/node_modules/SQLite — requires re-install on next make dev
make bootstrap
make migrate && make seed
time make dev     # measure until /health and / both return 200
```

For a structured timing measurement that appends to a log, run `make verify-timing`.

## Troubleshooting

- **`./data/cockpit.db` is corrupted or schema is wrong** — `make demo-reset` wipes the DB back to seeded state.
- **Demo broke between walkthroughs** — `make demo-reset` is the most common fix.
- **Port already in use** — these dev ports must be free: 8000 (cockpit-api), 5173 (cockpit-ui), 4040 (ngrok admin API). The Developer Edition fallback also needs its own ports (`orchestrate server eject` lists them).
- **`pnpm install` peer-dep warnings** — `eslint-plugin-react@7` and `eslint-plugin-jsx-a11y` haven't bumped their peer ranges to ESLint 10 yet; the `pnpm.peerDependencyRules.allowedVersions` block in `apps/cockpit-ui/package.json` silences this. Remove it once upstream catches up.
- **Cloud Orchestrate calls time out / 502 from the chat UI** — most often the ngrok tunnel rotated. Run `make tunnel-sync`. If the tunnel is fine, confirm `make dev` is up and `curl localhost:8000/health` returns `{"status": "ok"}`.
- **`make adk-up` slow / fails (fallback only)** — the ADK CLI pulls IBM Cloud Container Registry images on first run. Ensure your network reaches `icr.io`; subsequent runs are warm.
- **Docker permission denied** — add your user to the `docker` group (`sudo usermod -aG docker $USER`, then log out/in) or use Docker Desktop.
- **Poetry "Item does not exist!" / DBus / secretstorage errors on Linux** — work around with `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring poetry install` (the system keyring isn't unlocked).

## Documentation

- Product, architecture, and epic specs live under `Documentation/planning-artifacts/`.
- Per-story implementation specs live under `Documentation/implementation-artifacts/`.
- Cut bank-buyer-scope story files preserved under `Documentation/implementation-artifacts/archive/` (re-scope date: 2026-04-29).

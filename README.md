# ibm_orchestrate_platform

Reference implementation of the **KYC Cockpit** on top of the IBM watsonx Orchestrate Agent Development Kit (ADK). A polyglot monorepo:

- **`apps/cockpit-ui/`** — Vite + React 19 + TypeScript (strict) cockpit UI.
- **`apps/cockpit-api/`** — FastAPI service (Python 3.11+) backing the cockpit.
- **`apps/agents/`** — IBM watsonx Orchestrate ADK agents.
- **`packages/contracts/`** — Pydantic schemas shared across Python apps.
- **`tools/verifier/`** — offline ledger verifier CLI (deferred for the demo build; see [What's NOT in this demo](#whats-not-in-this-demo)).
- **`infra/`** — infrastructure-as-code placeholder.

> **Demo build (re-scoped 2026-04-29).** This repo ships the project as a local demo that proves a full-fledged application can be built on IBM ADK agents. Many enterprise capabilities (OIDC, multi-tenant isolation, cryptographic ledger, real screening vendors, pentest, DR, WCAG audit, CCO portfolio) are deferred. The full bank-buyer scope remains documented in `Documentation/planning-artifacts/` and can be revived. See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` for the full re-scope record.

## Demo presenter quickstart

Just cloned this and need to run the demo? From cold to running:

```bash
make bootstrap              # one-time: Poetry + pnpm install + ./data/ + git hooks (also copies .env.example → .env)
# Edit .env: set WATSONX_APIKEY=<your IBM Cloud watsonx.ai key>
make migrate && make seed   # initialise the SQLite DB + ledger
make adk-up                 # one-time: pull + start the ADK Developer Edition (Docker)
make adk-register           # import every agent + tool under apps/agents/src/agents/registry/
make dev                    # uvicorn + Vite dev server (Ctrl-C stops both)
make adk-chat               # opens the chat UI in your browser (separate terminal)
```

Then:

- **Cockpit UI** at <http://localhost:5173> — opens as the **Analyst** (Kamal Singh). Use the user dropdown in the top-right to switch among the [three demo roles](#demo-users).
- **ADK chat UI** at <http://localhost:3000> — talk to any registered agent in natural language; the LLM decides when to invoke the cockpit-api-backed tools. See [Talking to the agents](#talking-to-the-agents) for example prompts.

To reset the demo between walkthroughs (wipes mutable state, keeps schema):

```bash
make demo-reset
```

If `make dev` looks unhealthy, `make verify` does a 5-check smoke: SQLite DB, `/health`, `/v1/users/me`, the cockpit-ui port, and the ADK runtime.

## Prerequisites

Install once per developer machine:

- **Docker Desktop ≥ 4.x** — required for the ADK Developer Edition. Every agent in the platform is registered with this runtime; the chat UI lives here too. (The cockpit data plane itself runs on SQLite + local filesystem and needs no docker.)
- **Node.js ≥ 20** with [Corepack](https://nodejs.org/api/corepack.html) enabled.
- **pnpm ≥ 9** (`corepack enable pnpm`).
- **Python 3.11–3.13** (`ibm-watsonx-orchestrate` constrains the upper bound to `<3.14`).
- **Poetry ≥ 1.7**.
- **GNU Make**.

You also need a **watsonx.ai API key** for the ADK runtime's LLM calls. The Developer Edition runs locally but the LLM hits watsonx cloud (`us-south.ml.cloud.ibm.com` by default — IBM Cloud free tier works). Get one from IBM Cloud → IAM → API keys, then put it in your `.env` file (created by `make bootstrap` from `.env.example`):

```bash
# .env  (gitignored — never commit real values)
WATSONX_APIKEY=<your IBM Cloud API key>
# optional overrides:
WATSONX_SPACE_ID=<your space id>
WATSONX_MODEL_ID=watsonx/ibm/granite-3-2-8b-instruct
```

`make adk-up` passes `--env-file ./.env` to the Developer Edition CLI, which merges it with the ADK's built-in `default.env`. The Developer Edition reads the env on startup (not per-request), so after editing `.env` run `make adk-down && make adk-up` to pick up changes.

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

# 3. (One-time) Set your watsonx.ai API key in .env, then start the IBM
#    watsonx Orchestrate Developer Edition. The ADK CLI manages its own
#    container stack. First run pulls images (~5–10 min).
#
#    .env was created from .env.example during `make bootstrap` — open it
#    and set:
#      WATSONX_APIKEY=<your IBM Cloud API key>
#    `make adk-up` passes --env-file ./.env to `orchestrate server start`.
make adk-up

# 4. Register every agent + tool in the registry. The make target walks
#    apps/agents/src/agents/registry/*/ — drop a new directory there with
#    agent.yaml (and optionally openapi.yaml + gen_openapi.py for tools)
#    and it gets imported automatically. Idempotent.
make adk-register

# 5. Start cockpit-api + cockpit-ui in parallel. Ctrl-C stops both.
make dev
# → http://localhost:5173    (cockpit-ui)
# → http://localhost:8000/docs  (cockpit-api Swagger)

# 6. (Separate terminal) Open the ADK chat UI to talk to the agents.
make adk-chat
# → http://localhost:3000
```

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
make adk-up       # start the ADK Developer Edition (its own docker stack)
make adk-down     # stop the ADK Developer Edition
make adk-spec     # regenerate apps/agents/src/agents/registry/.../openapi.yaml from cockpit-api
make adk-register # import the document_intelligence tool + agent into the running ADK
make adk-chat     # open the ADK chat UI in your browser
make clean        # remove venvs, node_modules, build artefacts, AND ./data/cockpit.db
```

> Run `make contracts` whenever you change a router under `apps/cockpit-api/src/cockpit_api/routers/` or a Pydantic contract that crosses the wire. Both generated files are committed; CI fails on drift.

The cockpit opens as the **Analyst** (Kamal Singh). Use the user dropdown in the top right to switch among the three demo roles — see [Demo users](#demo-users).

## Talking to the agents

Once `make adk-up` + `make adk-register` are done, every agent registered under `apps/agents/src/agents/registry/` is reachable from `make adk-chat` (<http://localhost:3000>). Pick the agent from the dropdown and prompt it in plain English — the LLM decides when to call its tools.

### `document_intelligence` — Epic 3

Try this prompt in the chat UI:

```
Process case case_01KQC7GQ70GYHP15CZ8JB5ZT6A with documents
incorporation_certificate.pdf, pan_card.pdf, address_proof.pdf,
director_id.pdf, bank_statement_q1.pdf
```

What happens under the hood:

1. Chat UI sends the prompt to the **`document_intelligence`** ADK agent (LLM: granite-3-2-8b).
2. The agent (per `agent.yaml` instructions) decides to call **`extract_document_fields`**.
3. The Developer Edition's runtime POSTs to `http://host.docker.internal:8000/v1/agents/document_intelligence/extract` on your local cockpit-api.
4. cockpit-api runs the `document_intelligence` Python coroutine; the `@agent_action` decorator writes one `agent.completed` ledger entry to `./data/ledger.jsonl`.
5. Typed extracted fields flow back to the LLM, which summarises them in plain English (top fields by confidence, LOW-band rows that need analyst eyes).

To watch ledger entries land in real time, tail the file from another terminal:

```bash
tail -f data/ledger.jsonl | python3 -m json.tool
```

### Skipping the chat UI (curl)

To confirm the endpoint works without bringing the Developer Edition up:

```bash
curl -s -X POST http://localhost:8000/v1/agents/document_intelligence/extract \
  -H 'Content-Type: application/json' \
  -d '{
    "case_id": "case_01KQC7GQ70GYHP15CZ8JB5ZT6A",
    "document_refs": ["incorporation_certificate.pdf", "pan_card.pdf"]
  }' | python3 -m json.tool
```

You should see typed `extracted_fields` with provenance + confidence bands, and a new entry in `data/ledger.jsonl`.

### When to re-run `make adk-register`

- After editing any `agent.yaml` under the registry (LLM, instructions, tool list).
- After changing the request/response contract of any `POST /v1/agents/.../*` endpoint — `make adk-register` re-runs `make adk-spec` automatically, which regenerates each `openapi.yaml`.
- After dropping a new agent directory into the registry. No code changes needed; the Make targets walk the registry.

Imports are idempotent; re-running updates each spec in place.

### Common ADK issues

- **`make adk-register` fails with "no active environment"** — run `orchestrate env list` and `orchestrate env activate <name>`. The Developer Edition usually creates a `local` env on startup.
- **Tool calls return 502** — cockpit-api isn't running, or `host.docker.internal` doesn't resolve. On Linux, ensure Docker 20.10+ and that your network mode supports host-gateway. macOS/Windows wire it by default.
- **Agent picks the wrong tool / hallucinates** — tighten the `instructions:` block in the agent's `agent.yaml` and re-run `make adk-register`.
- **`WATSONX_APIKEY` was unset when `make adk-up` ran** — set it in `.env` (or your shell), then `make adk-down && make adk-up`. The Developer Edition reads the env on startup, not per-request.

For deeper architectural detail see `Documentation/implementation-artifacts/3-4-adk-demo-flow.md`.

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
| Prerequisite install (one-time per machine) | ≤ 30 min | Docker Desktop *(for ADK)*, Node 20+, pnpm 9+, Python 3.11+, Poetry 1.7+, GNU Make. Not counted toward the 60 min if pre-installed. |
| `git clone` | ≤ 2 min | Connection-bound. |
| `make bootstrap` | ≤ 15 min | Poetry + pnpm first install over network. |
| `make migrate` + `make seed` | ≤ 30 sec | SQLite is instant. |
| `make adk-up` *(first run, image pull)* | ≤ 15 min | One-time. |
| `make dev` cold start | ≤ 90 sec | Story 1.2 AC #10 budget; preserved. |
| `make verify` smoke check | ≤ 30 sec | Curl + sqlite ping + ADK status. |
| **Total (cold, prerequisites pre-installed)** | **≤ 30 min** | Comfortable inside 60 min. |
| **Total (cold, including prerequisites)** | **≤ 60 min** | The binding metric. |

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
| ADK Developer Edition | `make adk-up` (separate) | The ADK CLI manages its own docker stack. Treated as a long-lived service — leave it up across `make dev` sessions to stay inside the 90 s budget. |

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
- **Port already in use** — these dev ports must be free: 8000 (cockpit-api), 5173 (cockpit-ui), and the ADK Developer Edition's ports (`orchestrate server eject` lists them).
- **`pnpm install` peer-dep warnings** — `eslint-plugin-react@7` and `eslint-plugin-jsx-a11y` haven't bumped their peer ranges to ESLint 10 yet; the `pnpm.peerDependencyRules.allowedVersions` block in `apps/cockpit-ui/package.json` silences this. Remove it once upstream catches up.
- **`make adk-up` slow / fails** — the ADK CLI pulls IBM Cloud Container Registry images on first run. Ensure your network reaches `icr.io`; subsequent runs are warm.
- **Docker permission denied** — add your user to the `docker` group (`sudo usermod -aG docker $USER`, then log out/in) or use Docker Desktop.
- **Poetry "Item does not exist!" / DBus / secretstorage errors on Linux** — work around with `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring poetry install` (the system keyring isn't unlocked).

## Documentation

- Product, architecture, and epic specs live under `Documentation/planning-artifacts/`.
- Per-story implementation specs live under `Documentation/implementation-artifacts/`.
- Cut bank-buyer-scope story files preserved under `Documentation/implementation-artifacts/archive/` (re-scope date: 2026-04-29).

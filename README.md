# ibm_orchestrate_platform

Reference implementation of the KYC Cockpit on top of the IBM watsonx Orchestrate Agent Development Kit (ADK). A polyglot monorepo:

- **`apps/cockpit-ui/`** — Vite + React 19 + TypeScript (strict) cockpit UI.
- **`apps/cockpit-api/`** — FastAPI service (Python 3.11+) backing the cockpit.
- **`apps/agents/`** — IBM watsonx Orchestrate ADK agents.
- **`packages/contracts/`** — Pydantic schemas shared across Python apps.
- **`tools/verifier/`** — offline ledger verifier CLI.
- **`infra/`** — infrastructure-as-code (compose init scripts here; Story 1.3 fills in CI/CD).

## Prerequisites

Install once per developer machine:

- **Docker Desktop ≥ 4.x** (or any host running `docker compose` ≥ 2.x).
- **Node.js ≥ 20** with [Corepack](https://nodejs.org/api/corepack.html) enabled.
- **pnpm ≥ 9** (`corepack enable pnpm`).
- **Python 3.11+**.
- **Poetry ≥ 1.7**.
- **GNU Make**.

## First-time setup

Goal: clone-to-demo in under 30 minutes (NFR-RI5).

```bash
git clone <repo> && cd ibm_orchestrate_platform

# 1. Bring up Postgres / Redis / LocalStack S3 / Vault Transit.
docker compose up -d

# 2. Install all workspace dependencies (Poetry + pnpm). Idempotent.
make bootstrap

# 3. Apply Alembic migrations against the dev DB.
make migrate

# 4. Seed the demo tenant + officer (idempotent — re-running is a no-op).
make seed

# 5. (Optional, one-time) Start the IBM watsonx Orchestrate Developer Edition.
#    The ADK CLI manages its own container stack.
make adk-up

# 6. Start cockpit-api + cockpit-ui in parallel. Ctrl-C stops both.
make dev
# → http://localhost:5173  (cockpit-ui)
# → http://localhost:8000/docs  (cockpit-api Swagger)
```

`make bootstrap` copies `.env.example` → `.env` only when `.env` is missing,
so your local secrets are never overwritten. The defaults in `.env.example`
match `docker-compose.yml`, so a fresh clone runs end-to-end without manual
edits — except OIDC, which Story 1.6 wires up.

`make bootstrap` also installs the repo-wide dev tooling at the root
(`poetry install` resolves `pre-commit` and `actionlint`) and runs
`pre-commit install --install-hooks` so every commit auto-lints. The
hook config lives in `.pre-commit-config.yaml`; CI runs the same hooks
end-to-end via `pre-commit run --all-files` as a pre-flight in
`.github/workflows/ci.yml`.

## Daily development

```bash
make dev          # uvicorn + Vite (parallel; SIGINT-safe)
make test         # pytest in each Python project + Vitest in cockpit-ui
make lint         # Ruff + mypy + ESLint + Prettier
make migrate      # apply new Alembic revisions
make seed         # re-seed (idempotent)
make adk-up       # start the ADK Developer Edition (runs its own docker stack)
make adk-down     # stop the ADK Developer Edition
make clean        # remove venvs, node_modules, build artefacts
make clean-volumes # ⚠️ DROPS local Postgres data
```

The cockpit opens as the **Analyst** (Kamal Singh). Use the user dropdown in the top right to switch among the three demo roles — see [Demo users](#demo-users).

## Demo users

The demo build (re-scoped 2026-04-29) has no real auth. Three hardcoded users back the user-switcher dropdown — switching among them changes the visible routes. See `Documentation/implementation-artifacts/1-4-cockpit-shell-with-user-switcher-three-hardcoded-roles.md` for the full story context.

| Role | Name | Default route | Persona reference |
|---|---|---|---|
| Analyst | Kamal Singh | `/queue` | UX User Journey 1 (Priya — substituted for the demo presenter) |
| Team Lead | Rohan Mehta | `/approvals` | UX User Journey 3 |
| Regulator | Anika Iyer | `/regulator-lens` | UX User Journey 4 |

UUIDs are pinned in `packages/contracts/src/contracts/users.py` and mirrored in `.env.example` (`DEMO_ANALYST_ID`, `DEMO_TEAM_LEAD_ID`, `DEMO_REGULATOR_ID`). The contract is the source of truth.

## Cold-start budget (G6)

`make dev` cold-start budget is **≤ 90 seconds** from invocation to all
served URLs returning 200 (G6 from architecture). The orchestration is split
to keep the budget realistic:

| Component | Where it runs | Notes |
| --- | --- | --- |
| Postgres / Redis / LocalStack / Vault | `docker compose` | Brought up once via `docker compose up -d`; stays warm across `make dev` runs. |
| cockpit-api (uvicorn `--reload`) | `make dev` | < 5 s on a typical laptop. |
| cockpit-ui (Vite dev) | `make dev` | < 5 s; HMR ≪ 1 s. |
| ADK Developer Edition | `make adk-up` (separate) | The ADK CLI manages its own docker stack (`orchestrate server eject` to inspect). Treated as a long-lived service — leave it up across `make dev` sessions to stay inside the 90 s budget. |

To measure on your machine:

```bash
make clean
docker compose down -v
docker compose up -d                # wait until `docker compose ps` is healthy
time make dev                       # measure to first 200 OK on /health and /
```

If you exceed the budget, profile each runtime separately and document the
slow path in `Documentation/implementation-artifacts/`.

## Troubleshooting

- **Postgres unhealthy** — wipe data and retry: `make clean-volumes && docker compose up -d`.
- **Port already in use** — these dev ports must be free: 5432 (Postgres), 6379 (Redis), 4566 (LocalStack), 8200 (Vault), 8000 (cockpit-api), 5173 (cockpit-ui), and the ADK Developer Edition's ports (`orchestrate server eject` lists them).
- **`pnpm install` peer-dep warnings** — `eslint-plugin-react@7` and `eslint-plugin-jsx-a11y` haven't bumped their peer ranges to ESLint 10 yet; the `pnpm.peerDependencyRules.allowedVersions` block in `apps/cockpit-ui/package.json` silences this. Remove it once upstream catches up.
- **`make adk-up` slow / fails** — the ADK CLI pulls IBM Cloud Container Registry images on first run. Ensure your network reaches `icr.io`; subsequent runs are warm.
- **Docker permission denied** — add your user to the `docker` group (`sudo usermod -aG docker $USER`, then log out/in) or use Docker Desktop.

## Documentation

- Product, architecture, and epic specs live under `Documentation/planning-artifacts/`.
- Per-story implementation specs live under `Documentation/implementation-artifacts/`.
- Architecture decision records (ADRs) land in `docs/adr/` (Story 1.4).

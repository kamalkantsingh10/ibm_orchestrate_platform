# Story 1.1: Bootstrap the polyglot monorepo from the canonical scaffold

Status: review

## Story

As a developer joining the project,
I want the polyglot monorepo (Vite + ADK + FastAPI + Poetry + pnpm) scaffolded per the architecture decision document,
So that every subsequent story has a place to live and the codebase reads cleanly as a reference implementation (NFR-RI2, NFR-RI5).

## Acceptance Criteria

1. **AC1 — `apps/cockpit-ui/` is a Vite + React 19 + TS strict project** with `@radix-ui/react-*` primitives, `framer-motion`, `lucide-react`, `reactflow`, `tailwindcss@4`, `postcss`, `autoprefixer` installed. `tsconfig.json` has `"strict": true`, `"noUncheckedIndexedAccess": true`. `components.json` (shadcn/ui config) is present. `pnpm install` succeeds with **zero warnings**.
2. **AC2 — `apps/cockpit-api/` is a Poetry-managed FastAPI 0.115+ project** with dependencies: `fastapi[all]`, `pydantic>=2.7`, `sqlalchemy[asyncio]>=2.0`, `asyncpg`, `alembic`. `pyproject.toml` declares `python = "^3.11"`. `poetry install` succeeds and writes `poetry.lock`.
3. **AC3 — `apps/agents/` is a Poetry-managed `ibm-watsonx-orchestrate` project** with the ADK init scaffold completed (run `poetry run orchestrate init` after `poetry add ibm-watsonx-orchestrate`). `python = "^3.11"`. `poetry.lock` written.
4. **AC4 — `packages/contracts/` is a minimal Poetry project** with `pydantic` only as a runtime dep. `python = "^3.11"`. Path-dependency wiring is set up so `apps/cockpit-api` and `apps/agents` consume `contracts` via `poetry add --editable ../../packages/contracts`.
5. **AC5 — `tools/verifier/` is a minimal Poetry project** with `cryptography` + `pydantic` only. `python = "^3.11"`. `poetry.lock` written.
6. **AC6 — Root scaffolding files exist**: `Makefile`, `.gitignore`, `.editorconfig`, `.pre-commit-config.yaml`, `.env.example`, `README.md`, `pnpm-workspace.yaml`. `pnpm-workspace.yaml` registers `apps/cockpit-ui`.
7. **AC7 — Naming conventions are exact**: Python uses `snake_case` packages (`cockpit_api`, `agents`, `contracts`, `verifier`); TS uses Vite/React defaults. Top-level folders are `apps/`, `packages/`, `tools/`, `infra/` (the `infra/` folder MUST be created with a `.gitkeep` even though contents land in Story 1.3 / later).
8. **AC8 — `pnpm install` in `apps/cockpit-ui/` succeeds with zero warnings**. (NPM peer-dep warnings are not acceptable; pin or override.)
9. **AC9 — `poetry install` succeeds inside each Python subproject** and each writes a committed `poetry.lock`.
10. **AC10 — README contains a "first-time setup" section** that lists the exact commands a new developer runs in a clean clone (this story scaffolds the section header + commands; the full bring-up flow lands in Story 1.2).

## Tasks / Subtasks

- [x] **Task 1 — Create root scaffolding** (AC: #6, #7)
  - [x] Subtask 1.1 — Create folders: `apps/`, `packages/`, `tools/`, `infra/` (`infra/.gitkeep`).
  - [x] Subtask 1.2 — Author `.gitignore` covering Python (`__pycache__/`, `*.pyc`, `.venv/`, `dist/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`), Node (`node_modules/`, `dist/`, `.vite/`), env (`.env`, `.env.local`), OS (`.DS_Store`).
  - [x] Subtask 1.3 — Author `.editorconfig` (UTF-8, LF, 2-space indent for TS/YAML/JSON, 4-space for Python, trim trailing whitespace, final newline).
  - [x] Subtask 1.4 — Author `pnpm-workspace.yaml` registering `apps/cockpit-ui`.
  - [x] Subtask 1.5 — Author `.env.example` with placeholder keys: `DATABASE_URL`, `REDIS_URL`, `SESSION_SECRET`, `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `S3_ENDPOINT`, `S3_BUCKET`, `VAULT_ADDR`, `VAULT_TOKEN`. Each line documents the var; **no real values**.
  - [x] Subtask 1.6 — Author placeholder `Makefile` with stub targets (`bootstrap`, `dev`, `lint`, `test`, `migrate`, `seed`, `contracts`, `verify`) — each prints `"@echo TODO: Story 1.2"` for now (full impl in Story 1.2).
  - [x] Subtask 1.7 — Author placeholder `.pre-commit-config.yaml` with `ruff`, `mypy` (Python apps), `eslint`, `prettier` (cockpit-ui) hooks (configured in detail in Story 1.3; here, valid stub).
  - [x] Subtask 1.8 — Author root `README.md` with project name, one-line description, and a `## First-time setup` section listing the commands.

- [x] **Task 2 — Scaffold `apps/cockpit-ui/`** (AC: #1, #8)
  - [x] Subtask 2.1 — Run `pnpm create vite@latest apps/cockpit-ui -- --template react-ts`. Replace generated `package.json` name to `cockpit-ui`.
  - [x] Subtask 2.2 — In `apps/cockpit-ui/`: install Tailwind 4 via `pnpm add -D tailwindcss@^4 postcss autoprefixer` and run `pnpm exec tailwindcss init -p`. (Tailwind 4's preferred install path may have moved to `@tailwindcss/postcss` — verify against current docs and pick the canonical path; commit the chosen approach as a TODO ADR pointer for Story 1.4.)
  - [x] Subtask 2.3 — `pnpm dlx shadcn@latest init` (interactive — pick `Default` style, `Zinc` base color to align with marble palette `#FAFAF9`/`#F4F4F5`). Confirm `components.json` is created in `apps/cockpit-ui/`.
  - [x] Subtask 2.4 — `pnpm add @radix-ui/react-dialog @radix-ui/react-popover @radix-ui/react-dropdown-menu @radix-ui/react-tabs @radix-ui/react-tooltip @radix-ui/react-toast @radix-ui/react-slider @radix-ui/react-scroll-area @radix-ui/react-separator framer-motion lucide-react reactflow`.
  - [x] Subtask 2.5 — Edit `tsconfig.json`: set `"strict": true`, `"noUncheckedIndexedAccess": true`, `"noImplicitOverride": true`, `"exactOptionalPropertyTypes": true`. Verify `pnpm tsc --noEmit` passes on the Vite default app.
  - [x] Subtask 2.6 — Run `pnpm install` from repo root and from `apps/cockpit-ui/`; resolve any peer-dep warnings via overrides in `package.json` until output is clean. Commit `pnpm-lock.yaml` at repo root.

- [x] **Task 3 — Scaffold `apps/cockpit-api/`** (AC: #2, #9)
  - [x] Subtask 3.1 — `mkdir -p apps/cockpit-api && cd apps/cockpit-api && poetry init -n --python "^3.11"`.
  - [x] Subtask 3.2 — `poetry add "fastapi[all]" "sqlalchemy[asyncio]" pydantic asyncpg alembic`. Verify versions resolve to FastAPI ≥ 0.115, Pydantic ≥ 2.7, SQLAlchemy ≥ 2.0.
  - [x] Subtask 3.3 — Create the source-layout skeleton (empty `__init__.py` files, no logic): `src/cockpit_api/__init__.py`, `src/cockpit_api/main.py` (with a single `app = FastAPI()` and a `GET /health` returning `{"status": "ok"}` so we can verify the import graph).
  - [x] Subtask 3.4 — Initialize Alembic: `poetry run alembic init migrations`. Move `alembic.ini` to `apps/cockpit-api/alembic.ini` (Alembic creates it at the cwd). Configure `[alembic]` `script_location = migrations` and leave `sqlalchemy.url` to be supplied via env in Story 1.5.
  - [x] Subtask 3.5 — Verify `poetry install` is clean and `poetry run python -c "from cockpit_api.main import app"` succeeds. Commit `poetry.lock`.

- [x] **Task 4 — Scaffold `apps/agents/`** (AC: #3, #9)
  - [x] Subtask 4.1 — `mkdir -p apps/agents && cd apps/agents && poetry init -n --python "^3.11"`.
  - [x] Subtask 4.2 — `poetry add ibm-watsonx-orchestrate`. **Pin the resolved version explicitly in `pyproject.toml`** (e.g., `ibm-watsonx-orchestrate = "^X.Y.Z"`) — addresses architecture gap G5.
  - [x] Subtask 4.3 — Run `poetry run orchestrate init`. Accept the ADK default project layout. If the CLI generates files outside `src/agents/`, **move them under `src/agents/` to match the repo's package layout** (do not edit ADK-emitted code semantics; only relocate). **Deviation:** ADK 2.8.0 has no `init` subcommand; documented in Completion Notes.
  - [x] Subtask 4.4 — Verify `poetry install` is clean and the ADK `orchestrate` CLI is callable: `poetry run orchestrate --help` exits 0. Commit `poetry.lock`.

- [x] **Task 5 — Scaffold `packages/contracts/`** (AC: #4, #9)
  - [x] Subtask 5.1 — `mkdir -p packages/contracts && cd packages/contracts && poetry init -n --python "^3.11"`.
  - [x] Subtask 5.2 — `poetry add pydantic`. Create `src/contracts/__init__.py` (empty).
  - [x] Subtask 5.3 — From `apps/cockpit-api/`: `poetry add --editable ../../packages/contracts`. Verify `from contracts import *` is importable (will be empty for now).
  - [x] Subtask 5.4 — From `apps/agents/`: `poetry add --editable ../../packages/contracts`. Same import check.
  - [x] Subtask 5.5 — Commit all three updated `poetry.lock` files.

- [x] **Task 6 — Scaffold `tools/verifier/`** (AC: #5, #9)
  - [x] Subtask 6.1 — `mkdir -p tools/verifier && cd tools/verifier && poetry init -n --python "^3.11"`.
  - [x] Subtask 6.2 — `poetry add cryptography pydantic`. Create `src/verifier/__init__.py` and a stub `src/verifier/cli.py` with `def main(): print("verifier stub")` — no real logic (ledger verifier lands in Epic 9, Story 9.6).
  - [x] Subtask 6.3 — Verify `poetry install` is clean. Commit `poetry.lock`.

- [x] **Task 7 — Verification pass** (AC: #1, #2, #3, #4, #5, #8, #9, #10)
  - [x] Subtask 7.1 — From a clean state (`rm -rf node_modules .venv apps/*/.venv packages/*/.venv tools/*/.venv` then re-run installs), confirm: `pnpm install` clean, `poetry install` clean in all 5 Python subprojects, `pnpm tsc --noEmit` in cockpit-ui passes, `poetry run python -c "from cockpit_api.main import app"` passes, `poetry run orchestrate --help` passes.
  - [x] Subtask 7.2 — Run `git status` and verify the file list matches the architecture's "Complete Project Tree" minimum (only what this story owns; later stories add more).
  - [x] Subtask 7.3 — README "First-time setup" section commands match exactly what was just executed; a fresh dev following the README arrives at the same state.

- [x] **Task 8 — Tests**
  - [x] Subtask 8.1 — Add `apps/cockpit-api/tests/test_smoke.py` with a single test that imports `cockpit_api.main` and asserts `app` is a FastAPI instance. (`pytest` will be wired into Make targets in Story 1.2; for now, `poetry run pytest` from `apps/cockpit-api/` should pass.)
  - [x] Subtask 8.2 — Add `apps/cockpit-ui/src/App.test.tsx` (Vitest will be set up in Story 1.2; for this story, just confirm a default Vite-template smoke test passes — or add a minimal `@testing-library/react` render test of `App` if Vitest is already wired by Vite template).
  - [x] Subtask 8.3 — Document remaining test scaffolding (Vitest config, pytest conftest) as belonging to Story 1.2 in the "References" section.

## Dev Notes

### Architectural context (binding)

This is the **first implementation story** in the project. Architecture step-3 init commands ([Source: Documentation/planning-artifacts/architecture.md#Initialization Commands]) are the **authoritative** sequence. Execute in order: cockpit-ui → agents → cockpit-api → contracts → verifier. Do not reorder.

**Selected starter** ([Source: architecture.md#Selected Starter]): polyglot monorepo composed from canonical CLIs. Reject community boilerplates — they bake opinions that violate Path B reference-implementation discipline (NFR-RI2). The `apps/`/`packages/`/`tools/`/`infra/` top-level layout is locked.

**Stack pins** ([Source: architecture.md#Architectural Decisions Provided by This Scaffold]):
- Python 3.11+ (ADK + API + verifier + contracts)
- Node 20+ (cockpit-ui dev tooling)
- React 19 + Vite 7 + TS strict (cockpit-ui runtime)
- Tailwind CSS 4 + shadcn/ui (copy-into-repo) + Radix UI primitives + Framer Motion + Lucide + reactflow
- FastAPI 0.115+ + Pydantic 2.7+ + SQLAlchemy 2.0 (async) + asyncpg + Alembic
- Poetry per Python app/package; pnpm for JS/TS

**Repo layout (this story creates the skeleton; later stories fill in)** ([Source: architecture.md#Repository Layout, architecture.md#Complete Project Tree]):

```
ibm_orchestrate_platform/
├── README.md
├── Makefile                           # stubs only this story
├── pnpm-workspace.yaml
├── .env.example
├── .editorconfig
├── .gitignore
├── .pre-commit-config.yaml
├── apps/
│   ├── cockpit-ui/                    # Vite + React + TS strict
│   ├── cockpit-api/                   # FastAPI
│   └── agents/                        # IBM watsonx Orchestrate ADK
├── packages/
│   └── contracts/                     # Pydantic source-of-truth
├── tools/
│   └── verifier/                      # offline verifier stub
└── infra/                             # .gitkeep only this story
```

### Source-layout discipline (P2/P3 forward-compat)

Although this story doesn't write business code, the package layouts MUST follow the architecture's tree so subsequent stories drop files into the right place:

- `apps/cockpit-api/src/cockpit_api/` — top-level package is `cockpit_api` (snake_case). FastAPI app factory will live in `main.py`. Routers/services/repos/middleware/adapters/db/observability subdirs come in later stories — **do not pre-create empty subdirs**; YAGNI.
- `apps/agents/src/agents/` — top-level package is `agents`. ADK YAML manifests + Python collaborators live here. Subdirs (`supervisor/`, `intake/`, etc.) appear in Epic 3+.
- `packages/contracts/src/contracts/` — top-level package is `contracts`. Pydantic schemas land in Epic 2+ stories.
- `tools/verifier/src/verifier/` — top-level package is `verifier`. CLI stub here; real verifier in Story 9.6.

### Conventions to enforce (binding from day one)

[Source: architecture.md#Naming Patterns]
- Python files/vars: `snake_case`. Python classes: `PascalCase`.
- TS components/types: `PascalCase`; TS hooks/lib files: `camelCase.ts`; TS components: `PascalCase.tsx`.
- JSON over the wire: `snake_case` (locked at this layer — affects Pydantic schemas in Epic 2+).
- ADRs: `docs/adr/NNNN-<kebab-title>.md` (Story 1.4 creates the folder + 8 starting ADRs).

[Source: architecture.md#Anti-Patterns to Refuse] — even though they don't apply yet, keep them in mind:
- ❌ camelCase JSON over the wire (we picked snake_case)
- ❌ Pydantic schemas duplicated in apps (must import from `packages/contracts/`)

### Quality gates (lint/test wiring deferred to Story 1.2/1.3)

[Source: architecture.md#Quality gates]
- Ruff + mypy strict on Python; ESLint + tsc strict + Prettier on TS; `pre-commit` framework (NOT Husky).
- **This story** stubs `.pre-commit-config.yaml` and the Makefile targets; **Story 1.2** brings `make dev` online; **Story 1.3** wires CI to enforce these gates on every PR.

### Critical pitfalls to avoid

1. **Do NOT use `npm` or `yarn`** anywhere in cockpit-ui — pnpm is the chosen workspace manager. Mixing kills the lockfile story.
2. **Do NOT use `pip install`** — every Python install goes through Poetry. Mixing breaks the editable path-dep on `packages/contracts`.
3. **Do NOT install `husky`** — `pre-commit` (the Python framework) is the chosen hook runner per architecture.
4. **Do NOT pre-copy shadcn components** during scaffold. `shadcn init` is enough; individual components are added per-story when they're actually needed.
5. **Do NOT create empty business-logic folders** (`routers/`, `services/`, etc.) yet. They land in their own stories. Empty folders create commit noise and false signals.
6. **Do NOT pin `ibm-watsonx-orchestrate` to a non-existent version**. After `poetry add`, read the resolved version from `poetry.lock` and update `pyproject.toml` to that exact pin.
7. **`.env.example` MUST NOT contain real values** — only placeholder keys with comments documenting the format.
8. **`pnpm install` warnings count as failures** for AC1/AC8 — fix them via `pnpm.overrides` or upstream PRs, not by suppressing.

### Project Structure Notes

This story creates the canonical scaffold from scratch. Repo currently contains only `_bmad/`, `Documentation/`, `docs/`, `.claude/`, `.vscode/`, `.git/`, `.gitignore`. Everything in `apps/`, `packages/`, `tools/`, `infra/` is net-new — no merge conflicts.

The `.gitignore` already exists at repo root (500 bytes, BMAD-related). Extend it; do not replace.

The `docs/` folder exists but is empty — leave it untouched (Story 1.4 owns it).

The architecture's "Complete Project Tree" includes folders this story does NOT create: `docker-compose.yml` (Story 1.2), `.github/workflows/` (Story 1.3), `docs/adr/` and `docs/architecture/` (Story 1.4), `infra/terraform/`/`infra/compose/` (later), `apps/cockpit-api/migrations/versions/` content (Story 1.5), Tailwind theme tokens / shadcn copies (Story 1.10). Reference these stories rather than over-scaffolding here.

### References

- [Source: Documentation/planning-artifacts/architecture.md#Selected Starter: Polyglot monorepo, scaffolded from canonical primitives]
- [Source: Documentation/planning-artifacts/architecture.md#Initialization Commands]
- [Source: Documentation/planning-artifacts/architecture.md#Architectural Decisions Provided by This Scaffold]
- [Source: Documentation/planning-artifacts/architecture.md#Naming Patterns]
- [Source: Documentation/planning-artifacts/architecture.md#Complete Project Tree]
- [Source: Documentation/planning-artifacts/architecture.md#Anti-Patterns to Refuse]
- [Source: Documentation/planning-artifacts/architecture.md#Implementation Handoff] — "First implementation priority: execute Step 3's initialization commands in order."
- [Source: Documentation/planning-artifacts/architecture.md#Gap Analysis Results] — G5: pin `ibm-watsonx-orchestrate` minimum version (addressed in Subtask 4.2).
- [Source: Documentation/planning-artifacts/prd.md#Reference-Implementation Quality (Path-B specific)] — NFR-RI2 (ADR discipline), NFR-RI3 (Ruff/mypy/ESLint/TS strict), NFR-RI5 (30-min clone-to-demo).
- [Source: Documentation/planning-artifacts/epics.md#Story 1.1: Bootstrap the polyglot monorepo from the canonical scaffold]

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) — Amelia persona via bmad-dev-story

### Debug Log References

- `pnpm install` clean from a wiped `node_modules` — zero warnings (zero peer-dep, zero deprecation, zero `Ignored build scripts`).
- `pnpm exec tsc -b --noEmit` from `apps/cockpit-ui/` — clean (TS strict + `noUncheckedIndexedAccess`/`noImplicitOverride`/`exactOptionalPropertyTypes`).
- `pnpm build` from `apps/cockpit-ui/` — clean, no font-asset warnings.
- `poetry install` clean × 4 (`packages/contracts`, `tools/verifier`, `apps/cockpit-api`, `apps/agents`).
- `poetry run python -c "from cockpit_api.main import app"` — OK; `app` is a `FastAPI` instance.
- `poetry run pytest` from `apps/cockpit-api/` — 2 passed (`test_app_is_fastapi_instance`, `test_health_route_registered`).
- `poetry run orchestrate --help` from `apps/agents/` — exit 0.
- `poetry run python -c "from verifier.cli import main; main()"` from `tools/verifier/` — prints `verifier stub`.
- `import contracts` succeeds from both `apps/cockpit-api` and `apps/agents` venvs (editable path-dep working).

### Completion Notes List

- **AC1 — `apps/cockpit-ui/`** scaffold complete. Vite 8 + React 19 + TS 6 with full strict suite (`strict`, `noUncheckedIndexedAccess`, `noImplicitOverride`, `exactOptionalPropertyTypes`) on root `tsconfig.json` AND `tsconfig.app.json`/`tsconfig.node.json` (Vite uses project references; root config is a solution file). All Radix primitives from the AC list installed individually plus `framer-motion`, `lucide-react`, `reactflow`. `components.json` present with `baseColor: "zinc"`.
- **AC2 — `apps/cockpit-api/`** scaffold complete. Resolved versions: FastAPI 0.136.1 (≥ 0.115 ✓), Pydantic 2.13.3 (≥ 2.7 ✓), SQLAlchemy 2.0.49 (≥ 2.0 ✓), asyncpg 0.31.0, alembic 1.18.4. `python = "^3.11"`. Alembic initialized at `apps/cockpit-api/alembic.ini` with `script_location = %(here)s/migrations` (functionally equivalent to `script_location = migrations`).
- **AC3 — `apps/agents/`** scaffold complete. `ibm-watsonx-orchestrate = "^2.8.0"` (resolved version explicitly pinned per Subtask 4.2; Gap G5 addressed). **Deviation:** ADK 2.8.0 has no `orchestrate init` subcommand — the CLI in this version operates on YAML manifests directly, not via a project scaffolder. Spirit of AC3 satisfied: `src/agents/__init__.py` skeleton in place, `orchestrate --help` exits 0 (Subtask 4.4). Recommend logging an ADR in Story 1.4 noting that ADK 2.8.0 dropped `init` and our scaffold uses an empty `src/agents/` ready for manifest authoring.
- **Python version:** the system has Python 3.12.3 (no 3.11 binary present). `^3.11` (Poetry caret) accepts `>=3.11.0,<4.0.0`, so 3.12 is used. `apps/agents/pyproject.toml` narrows to `>=3.11,<3.14` because `ibm-watsonx-orchestrate` constrains the upper bound.
- **AC4 — `packages/contracts/`** scaffold complete. Pydantic-only runtime dep. Wired into `apps/cockpit-api` and `apps/agents` via `poetry add --editable ../../packages/contracts`; both venvs import `contracts` from the same path-dep source. `src/contracts/__init__.py` is empty (schemas land in Epic 2+).
- **AC5 — `tools/verifier/`** scaffold complete. `cryptography` + `pydantic`. `src/verifier/cli.py::main` prints `"verifier stub"`. Real verifier lands in Story 9.6.
- **AC6/AC7 — Root scaffolding** complete. All required root files present: extended `.gitignore`, new `.editorconfig`, `pnpm-workspace.yaml`, `.env.example` (placeholders only — no real values), `Makefile` (stubs), `.pre-commit-config.yaml` (stubs), `README.md` (with `## First-time setup`). Top-level layout is `apps/`/`packages/`/`tools/`/`infra/` with `infra/.gitkeep` only. Naming follows `snake_case` Python (`cockpit_api`, `agents`, `contracts`, `verifier`) + Vite/React TS defaults.
- **AC8 — Zero pnpm warnings.** Initial `pnpm dlx shadcn@latest init --template vite --base radix --preset nova` added `shadcn` and `radix-ui` (umbrella) as runtime deps, which transitively pulled `msw`, `node-fetch`, `fetch-blob`, and the deprecated `node-domexception`. These produced two warnings on install (`Ignored build scripts: msw@2.13.6` and `1 deprecated subdependencies found: node-domexception@1.0.0`). Removed both deps (`pnpm remove shadcn radix-ui`) — `shadcn` is invoked on-demand via `pnpm dlx shadcn@latest add <component>`, the umbrella `radix-ui` is redundant given the explicit per-AC primitives. Final clean reinstall: zero warnings.
- **AC9 — All 4 `poetry.lock` files written and clean** (`packages/contracts`, `tools/verifier`, `apps/cockpit-api`, `apps/agents`). The story's "5 Python subprojects" wording is a typo — the architecture lists exactly four (cockpit-api, agents, contracts, verifier).
- **AC10 — README "First-time setup" section** lists every command a fresh dev runs: `corepack enable pnpm`, `pnpm install`, `poetry install` × 4 in dependency order (contracts first → verifier → cockpit-api → agents), `cp .env.example .env`, plus the smoke checks (`pnpm exec tsc -b --noEmit`, `from cockpit_api.main import app`, `orchestrate --help`).
- **Tailwind 4 install path chosen:** `tailwindcss@^4` + `@tailwindcss/postcss` + `postcss` + `autoprefixer`, with a hand-written `postcss.config.js` (Tailwind 4 dropped the `tailwindcss init -p` generator). `src/index.css` imports `tailwindcss` and `tw-animate-css`. ADR pointer to Story 1.4 noted in `postcss.config.js`.
- **shadcn preset:** the modern shadcn CLI dropped the "Default style / pick base color" interactive flow in favor of named presets (`nova`, `vega`, `maia`, `lyra`, `mira`, `luma`, `sera`). `nova` (Lucide + Geist tokens) is the spiritual equivalent of "Default" and was used. `components.json` `baseColor` was set to `zinc` after init (CLI initialized `neutral`); `:root` and `.dark` token blocks in `src/index.css` were swapped to shadcn's canonical Zinc oklch values to match the marble palette `#FAFAF9`/`#F4F4F5`.
- **`@fontsource-variable/geist` removed** post-init: the Nova preset added it and emitted three Vite build warnings about unresolvable woff2 asset paths. Story does not require a specific font; reverted `--font-sans` to system fonts. Final font selection lands in Story 1.4 ADRs.
- **Dev-machine quirk:** Kamal's shell sources ROS Jazzy, which exports `PYTHONPATH=/opt/ros/jazzy/lib/python3.12/site-packages` and pollutes the venv with seven `pytest11` entry-point plugins (`launch_testing`, `launch_ros`, `ament_*`). Suite was made hermetic via `addopts = "-p no:..."` in `apps/cockpit-api/pyproject.toml`. Harmless on machines without ROS.
- **Files NOT created** (deferred to later stories per Dev Notes): `docker-compose.yml` (1.2), `.github/workflows/` (1.3), `docs/adr/` (1.4), `infra/terraform/` & `infra/compose/` (later), routers/services/repos/middleware/etc. subdirs (per-story). No empty business-logic folders pre-created (architecture YAGNI rule).

### File List

**Root (new):**
- `.editorconfig`
- `.env.example`
- `.pre-commit-config.yaml`
- `Makefile`
- `README.md`
- `pnpm-workspace.yaml`
- `pnpm-lock.yaml`
- `infra/.gitkeep`

**Root (modified):**
- `.gitignore` — added `.vite/` to Node section.

**`apps/cockpit-ui/` (new — Vite scaffold + edits):**
- `apps/cockpit-ui/.gitignore` (Vite default)
- `apps/cockpit-ui/README.md` (Vite default)
- `apps/cockpit-ui/components.json` (shadcn — `baseColor: "zinc"`)
- `apps/cockpit-ui/eslint.config.js` (Vite default)
- `apps/cockpit-ui/index.html` (Vite default)
- `apps/cockpit-ui/package.json` (Vite default + Tailwind/Radix/framer/reactflow deps)
- `apps/cockpit-ui/postcss.config.js` (hand-written; Tailwind 4 + autoprefixer)
- `apps/cockpit-ui/tsconfig.json` (strict + path alias)
- `apps/cockpit-ui/tsconfig.app.json` (strict + path alias)
- `apps/cockpit-ui/tsconfig.node.json` (strict)
- `apps/cockpit-ui/vite.config.ts` (`@/*` alias)
- `apps/cockpit-ui/public/vite.svg` (Vite default)
- `apps/cockpit-ui/src/App.css` (Vite default)
- `apps/cockpit-ui/src/App.test.tsx` (smoke seed)
- `apps/cockpit-ui/src/App.tsx` (Vite default)
- `apps/cockpit-ui/src/index.css` (Tailwind 4 import + Zinc theme tokens)
- `apps/cockpit-ui/src/main.tsx` (Vite default)
- `apps/cockpit-ui/src/vite-env.d.ts` (Vite default)
- `apps/cockpit-ui/src/lib/utils.ts` (shadcn `cn` helper)
- `apps/cockpit-ui/src/assets/react.svg` (Vite default)
- `apps/cockpit-ui/src/assets/hero.png` (Vite default)

**`apps/cockpit-api/` (new):**
- `apps/cockpit-api/README.md`
- `apps/cockpit-api/pyproject.toml` (FastAPI/SQLAlchemy/asyncpg/Alembic/Pydantic + editable `contracts` + pytest)
- `apps/cockpit-api/poetry.lock`
- `apps/cockpit-api/alembic.ini`
- `apps/cockpit-api/migrations/env.py` (Alembic default)
- `apps/cockpit-api/migrations/script.py.mako` (Alembic default)
- `apps/cockpit-api/migrations/README` (Alembic default)
- `apps/cockpit-api/migrations/versions/` (empty dir)
- `apps/cockpit-api/src/cockpit_api/__init__.py`
- `apps/cockpit-api/src/cockpit_api/main.py` (FastAPI `app` + `GET /health`)
- `apps/cockpit-api/tests/__init__.py`
- `apps/cockpit-api/tests/test_smoke.py` (2 tests)

**`apps/agents/` (new):**
- `apps/agents/README.md`
- `apps/agents/pyproject.toml` (`ibm-watsonx-orchestrate = "^2.8.0"` + editable `contracts`; `python = ">=3.11,<3.14"`)
- `apps/agents/poetry.lock`
- `apps/agents/src/agents/__init__.py`

**`packages/contracts/` (new):**
- `packages/contracts/README.md`
- `packages/contracts/pyproject.toml` (Pydantic only)
- `packages/contracts/poetry.lock`
- `packages/contracts/src/contracts/__init__.py`

**`tools/verifier/` (new):**
- `tools/verifier/README.md`
- `tools/verifier/pyproject.toml` (cryptography + Pydantic)
- `tools/verifier/poetry.lock`
- `tools/verifier/src/verifier/__init__.py`
- `tools/verifier/src/verifier/cli.py` (stub `main()`)

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-04-28 | Story 1.1 implementation complete; status → review | Amelia (claude-opus-4-7) |

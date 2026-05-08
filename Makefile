# ──────────────────────────────────────────────────────────────────────────────
# KYC Cockpit — root Makefile (Story 1.2)
#
# Conventions:
#   * Each Python subproject is owned by Poetry; pnpm owns cockpit-ui.
#   * Targets are intentionally idempotent — re-running them is a no-op when
#     nothing has changed.
#   * `make dev` is the canonical dev loop. It runs uvicorn (cockpit-api) and
#     Vite (cockpit-ui) in parallel and forwards SIGINT to all children so
#     Ctrl-C cleans up.
#
# Agent runtime (2026-05-07): agents live in **cloud watsonx Orchestrate**, not
# in a local Developer Edition container. Cloud Orchestrate calls back into
# cockpit-api via an ngrok tunnel; `make tunnel-sync` rewrites the tunnel URL
# into every registry openapi.yaml. The legacy `adk-up` / `adk-down` targets
# are kept as a Developer Edition fallback for offline work.
# ──────────────────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help

SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c

# Subprojects — order matters for bootstrap (contracts before consumers).
PY_PROJECTS := packages/contracts tools/verifier apps/cockpit-api apps/agents
UI_PROJECT  := apps/cockpit-ui

.PHONY: help bootstrap dev migrate seed seed-uploads sample-pdfs lint lint-agents-p4 test contracts verify verify-timing demo-reset demo-fresh clean adk-up adk-down adk-register adk-chat adk-spec tunnel-sync

# Story 1.5 — SQLite DB path is repo-root anchored. Every target that touches
# the DB injects DATABASE_URL with this absolute path so subprocess cwd
# changes (e.g. `cd apps/cockpit-api`) don't break the relative resolution.
SQLITE_DB := $(CURDIR)/data/cockpit.db
DATABASE_URL_RESOLVED := sqlite+aiosqlite:///$(SQLITE_DB)

# Story 3.1 — append-only JSONL ledger (wiped by demo-reset).
LEDGER_FILE := $(CURDIR)/data/ledger.jsonl

# Story 4 hardening — repo-root-anchored uploads dir so cockpit-api resolves
# per-case PDFs regardless of the cwd it's launched from.
UPLOADS_ROOT := $(CURDIR)/fixtures/uploads

help:
	@echo "Usage: make <target>"
	@echo
	@echo "  bootstrap     Install all workspace dependencies (Poetry + pnpm) and create ./data/."
	@echo "  dev           Start cockpit-api + cockpit-ui in parallel. Agents run in cloud Orchestrate; start ngrok separately + run \"make tunnel-sync\"."
	@echo "  migrate       Apply Alembic migrations against the dev SQLite DB."
	@echo "  seed          Insert demo tenant + officer rows (idempotent)."
	@echo "  sample-pdfs   Generate 9 KYC sample PDFs at ./fixtures/sample_pdfs/."
	@echo "  seed-uploads  Generate sample PDFs and copy them per-case under ./fixtures/uploads/<case_id>/."
	@echo "  verify        Smoke check the running demo (DB, /health, /v1/users/me, /v1/cases, UI, agent runtime). 6 checks."
	@echo "  verify-timing Cold-start timing measurement, appends to cold-start-measurements.md."
	@echo "  demo-reset    Wipe ./data/cockpit.db, ./data/ledger.jsonl, and ./fixtures/uploads/, then migrate + seed."
	@echo "  lint          Ruff + mypy + ESLint + Prettier + P4 (agent ledger) discipline."
	@echo "  test          pytest in each Python project + Vitest in cockpit-ui."
	@echo "  contracts     OpenAPI export (Story 2.11 — stub)."
	@echo "  tunnel-sync   Read the running ngrok tunnel URL and rewrite every registry openapi.yaml + re-import."
	@echo "  adk-spec      Regenerate the OpenAPI tool spec from cockpit-api (writes apps/agents/src/agents/registry/...)."
	@echo "  adk-register  Import every agent + tool under apps/agents/src/agents/registry/ into the activated Orchestrate env (cloud or Developer Edition)."
	@echo "  adk-chat      Open the ADK chat UI (Developer Edition only — cloud uses the Orchestrate web chat)."
	@echo "  adk-up        [Fallback] Start the local IBM watsonx Orchestrate Developer Edition. Cloud Orchestrate is the primary runtime."
	@echo "  adk-down      [Fallback] Stop the Developer Edition."
	@echo "  clean         Remove venvs, node_modules, build artefacts, and the SQLite DB."

# ─── bootstrap ────────────────────────────────────────────────────────────────
bootstrap:
	@echo ">>> Bootstrapping local workspace"
	@if [ ! -f .env ]; then cp -n .env.example .env && echo "  .env created from .env.example"; \
		else echo "  .env already exists — leaving it alone"; fi
	@mkdir -p data
	@echo ">>> poetry install (root — repo-wide dev tooling: pre-commit, actionlint)"
	@poetry install --no-interaction
	@for proj in $(PY_PROJECTS); do \
		echo ">>> poetry install ($$proj)"; \
		(cd $$proj && poetry install --no-interaction --no-root); \
	done
	@echo ">>> pnpm install (workspace root)"
	@pnpm install --recursive
	@echo ">>> pre-commit install (git hooks)"
	@poetry run pre-commit install --install-hooks >/dev/null
	@echo "Bootstrap complete."

# ─── dev (parallel runtimes) ──────────────────────────────────────────────────
# Runs uvicorn (cockpit-api) and Vite (cockpit-ui) in parallel.
# trap forwards SIGINT/SIGTERM so Ctrl-C cleans up every child process.
#
# Agents are out-of-process: cloud Orchestrate is the primary runtime, reached
# via an ngrok tunnel started separately (`ngrok http 8000`). After both `make
# dev` and the tunnel are up, run `make tunnel-sync` to pull the live URL into
# every registry openapi.yaml and re-import to the cloud tenant.
dev:
	@if [ ! -f .env ]; then cp -n .env.example .env; fi
	@mkdir -p logs
	@bash -c '\
		set -m; \
		pids=(); \
		cleanup() { echo; echo ">>> Shutting down dev runtimes"; for p in "$${pids[@]}"; do kill -TERM "$$p" 2>/dev/null || true; done; wait; exit 0; }; \
		trap cleanup INT TERM; \
		( cd apps/cockpit-api && DATABASE_URL='$(DATABASE_URL_RESOLVED)' LEDGER_PATH='$(LEDGER_FILE)' UPLOADS_ROOT='$(UPLOADS_ROOT)' poetry run uvicorn cockpit_api.main:app --reload --host 0.0.0.0 --port 8000 2>&1 | tee $(CURDIR)/logs/cockpit-api.log ) & pids+=($$!); \
		( cd $(UI_PROJECT) && pnpm dev --host 2>&1 | tee $(CURDIR)/logs/cockpit-ui.log ) & pids+=($$!); \
		echo ">>> cockpit-api  http://localhost:8000  (docs at /docs)   log: logs/cockpit-api.log"; \
		echo ">>> cockpit-ui   http://localhost:5173                       log: logs/cockpit-ui.log"; \
		echo ">>> agents       cloud watsonx Orchestrate — start ngrok separately, then \"make tunnel-sync\" + \"make adk-register\""; \
		wait \
	'

# Optional fast-path: skip the ADK assumption and just run web stacks. Useful
# for frontend-only iteration. Currently identical to `dev` because we already
# treat the ADK as out-of-band; preserved for forward compatibility.
dev-fast: dev

# ─── Agent runtime lifecycle ──────────────────────────────────────────────────
#
# Primary path (2026-05-07): agents are registered to a **cloud watsonx
# Orchestrate** tenant. Setup flow:
#   1. one-time per developer: orchestrate env add --name cloud --url <tenant>
#                              orchestrate env activate cloud
#   2. ngrok http 8000          — expose cockpit-api to the cloud tenant
#   3. make dev                 — cockpit-api + cockpit-ui
#   4. make tunnel-sync         — pulls the ngrok URL, rewrites every openapi.yaml,
#                                 and re-imports tools/agents to the cloud tenant
#   5. open the Orchestrate cloud chat UI in your browser
#
# Fallback path (offline / Developer Edition):
#   1. make adk-up        — start local Developer Edition (Docker)
#   2. make adk-register  — import tools/agents to the local env
#   3. make adk-chat      — open http://localhost:3000
#
# Adding a new agent: drop a directory under apps/agents/src/agents/registry/
# containing `agent.yaml` (and `openapi.yaml` if it exposes tools). The make
# targets pick it up automatically — no per-agent rules to maintain.

ADK_REGISTRY := $(CURDIR)/apps/agents/src/agents/registry

# Brings up the Developer Edition. WATSONX_APIKEY (and other watsonx
# overrides) are loaded from `./.env` if present — the ADK CLI's
# `--env-file` flag merges them with its built-in default.env. If `.env`
# is missing, fall back to the shell's exported env vars (the CLI reads
# those too).
adk-up:
	@if [ -f .env ]; then \
		echo ">>> Starting Developer Edition with --env-file=$(CURDIR)/.env"; \
		cd apps/agents && poetry run orchestrate server start --env-file $(CURDIR)/.env; \
	else \
		echo ">>> Starting Developer Edition (no .env found — using shell env)"; \
		cd apps/agents && poetry run orchestrate server start; \
	fi

adk-down:
	@cd apps/agents && poetry run orchestrate server stop

# Cloud-Orchestrate-only: read the live ngrok tunnel URL from ngrok's local
# admin API (http://127.0.0.1:4040/api/tunnels), inject it as
# COCKPIT_API_PUBLIC_URL, regenerate every registry openapi.yaml so the
# `servers:` block points at the current tunnel, then re-import to the
# activated Orchestrate env. Run this any time the tunnel restarts (ngrok's
# free tier rotates URLs on every reconnect).
#
# Requires: `ngrok http 8000` running in another terminal.
tunnel-sync:
	@echo ">>> Reading ngrok tunnel URL from http://127.0.0.1:4040/api/tunnels"
	@URL=$$(curl -sf http://127.0.0.1:4040/api/tunnels \
		| python3 -c "import json,sys; t=json.load(sys.stdin)['tunnels']; \
print(next(x['public_url'] for x in t if x['public_url'].startswith('https')), end='')") \
		&& [ -n "$$URL" ] || { echo "ERROR: no ngrok tunnel found. Start one with: ngrok http 8000"; exit 1; } \
		&& echo ">>> Tunnel: $$URL" \
		&& COCKPIT_API_PUBLIC_URL="$$URL" $(MAKE) --no-print-directory adk-spec \
		&& $(MAKE) --no-print-directory adk-register \
		&& echo ">>> Done. Cloud Orchestrate now has the fresh tunnel URL."

# Regenerate every OpenAPI tool spec from cockpit-api's live FastAPI app.
# Each agent registry subdir owns its own generator script at
# `gen_openapi.py`; the script writes the subdir's `openapi.yaml`. Subdirs
# without a generator (pure-collaborator agents like the future supervisor)
# are skipped.
adk-spec:
	@echo ">>> Regenerating ADK tool OpenAPI specs from cockpit-api"
	@for spec in $(ADK_REGISTRY)/*/gen_openapi.py; do \
		[ -f "$$spec" ] || continue; \
		echo "--- $$spec"; \
		(cd apps/cockpit-api && poetry run python "$$spec"); \
	done

# Import every agent + tool under the registry into the running ADK
# Developer Edition. Idempotent: re-running updates each spec in place.
# Adding a new agent is a matter of dropping a directory in the registry.
adk-register: adk-spec
	@echo ">>> Importing tool specs (openapi.yaml under registry/*/)"
	@for tool in $(ADK_REGISTRY)/*/openapi.yaml; do \
		[ -f "$$tool" ] || continue; \
		echo "--- $$tool"; \
		(cd apps/agents && poetry run orchestrate tools import -k openapi -f "$$tool"); \
	done
	@echo ">>> Importing agents (agent.yaml under registry/*/, leaves first then collaborators)"
	@# Two-pass: import non-supervisors first (alphabetical), then supervisors.
	@# Supervisors reference collaborators by name; the runtime resolves them at
	@# import time, so leaves must exist first. Files named '*supervisor*' are
	@# treated as supervisors. Adjust here if you add another supervisor naming.
	@for agent in $(ADK_REGISTRY)/*/agent.yaml; do \
		[ -f "$$agent" ] || continue; \
		case "$$agent" in *supervisor*) continue ;; esac; \
		echo "--- $$agent"; \
		(cd apps/agents && poetry run orchestrate agents import -f "$$agent"); \
	done
	@for agent in $(ADK_REGISTRY)/*/agent.yaml; do \
		[ -f "$$agent" ] || continue; \
		case "$$agent" in *supervisor*) ;; *) continue ;; esac; \
		echo "--- $$agent"; \
		(cd apps/agents && poetry run orchestrate agents import -f "$$agent"); \
	done
	@echo ">>> Deploying agents (makes them visible in the chat UI)"
	@for agent in $(ADK_REGISTRY)/*/agent.yaml; do \
		[ -f "$$agent" ] || continue; \
		name=$$(grep -E '^name:' "$$agent" | head -1 | awk '{print $$2}'); \
		[ -n "$$name" ] || continue; \
		echo "--- $$name"; \
		(cd apps/agents && poetry run orchestrate agents deploy --name "$$name") || true; \
	done
	@echo ">>> Done. Run 'make adk-chat' to open the chat UI."

adk-chat:
	@cd apps/agents && poetry run orchestrate chat start

# ─── database lifecycle ───────────────────────────────────────────────────────
# DATABASE_URL is injected with an absolute SQLite path so the subprocess
# `cd apps/cockpit-api` doesn't cause the relative `./data/...` to misresolve.
migrate:
	@echo ">>> Applying Alembic migrations against $(SQLITE_DB)"
	@cd apps/cockpit-api && DATABASE_URL='$(DATABASE_URL_RESOLVED)' poetry run alembic upgrade head

seed:
	@echo ">>> Seeding demo tenant + officer"
	@cd apps/cockpit-api && DATABASE_URL='$(DATABASE_URL_RESOLVED)' LEDGER_PATH='$(LEDGER_FILE)' poetry run python scripts/seed_dev.py

# Story 3.8 — generate the 9 sample PDFs the demo's three pinned cases
# reference. Idempotent: re-runs overwrite. Uses cockpit-api's reportlab
# dev dep so all generation lives in one venv.
sample-pdfs: seed-uploads

# Story 3.8 + Epic 4 hardening — generator writes per-case PDFs straight
# into ``./fixtures/uploads/<case_id>/<filename>.pdf`` with the case's
# customer name substituted into every body, so the watsonx LLM extracts
# case-correct fields rather than reusing one shared template per filename.
seed-uploads:
	@echo ">>> Generating per-case sample PDFs at ./fixtures/uploads/<case_id>/"
	@cd apps/cockpit-api && poetry run python $(CURDIR)/tools/scripts/generate_sample_pdfs.py

# Story 1.5 — wipe mutable state back to seeded fixtures. Keeps schema by
# re-running migrate + seed; safe to run between demo walkthroughs.
demo-reset:
	@echo ">>> Resetting demo state"
	@rm -f $(SQLITE_DB) $(SQLITE_DB)-journal $(SQLITE_DB)-wal $(SQLITE_DB)-shm $(LEDGER_FILE)
	@mkdir -p fixtures/uploads
	@find fixtures/uploads -mindepth 1 -delete 2>/dev/null || true
	@$(MAKE) --no-print-directory migrate
	@$(MAKE) --no-print-directory seed
	@$(MAKE) --no-print-directory seed-uploads
	@echo "Demo reset to seeded state. Re-run the demo with: make dev"

# Epic 4 hardening — same as demo-reset but skips the auto-intake step so
# the cockpit's Agent Copilot Pane starts all-idle. Use this when you
# want to demo the live "upload (or use seeded PDFs) → click Process now
# → watch agents transition" flow.
demo-fresh:
	@echo ">>> Resetting demo state (no auto-intake — agents start idle)"
	@rm -f $(SQLITE_DB) $(SQLITE_DB)-journal $(SQLITE_DB)-wal $(SQLITE_DB)-shm $(LEDGER_FILE)
	@mkdir -p fixtures/uploads
	@find fixtures/uploads -mindepth 1 -delete 2>/dev/null || true
	@$(MAKE) --no-print-directory migrate
	@cd apps/cockpit-api && DATABASE_URL='$(DATABASE_URL_RESOLVED)' LEDGER_PATH='$(LEDGER_FILE)' SEED_SKIP_INTAKE=1 poetry run python scripts/seed_dev.py
	@$(MAKE) --no-print-directory seed-uploads
	@echo "Demo reset (fresh). Open a case and click \"Process now\" to watch the mesh process."

# Story 1.5 — smoke check the running demo. Five checks; CI=1 skips the ADK.
verify:
	@bash tools/scripts/verify_demo.sh

# Story 1.5 — cold-start timing measurement. Appends a row to
# Documentation/implementation-artifacts/cold-start-measurements.md.
verify-timing:
	@bash tools/scripts/verify_timing.sh

# ─── lint ─────────────────────────────────────────────────────────────────────
lint: lint-agents-p4
	@echo ">>> Ruff + mypy"
	@for proj in $(PY_PROJECTS); do \
		echo "--- $$proj"; \
		(cd $$proj && poetry run ruff check . && poetry run mypy .); \
	done
	@echo ">>> ESLint + Prettier (cockpit-ui)"
	@cd $(UI_PROJECT) && pnpm lint && pnpm format:check

# Story 3.2 — P4 (Agent Action Pattern) discipline. Only @agent_action may
# write to the ledger from apps/agents/src/agents. Tests are exempt.
#
# Story 3.5 carve-out: case_supervisor.py writes SYSTEM-level case lifecycle
# entries (case.intake_completed, case.intake_blocked) — NOT agent
# invocations. The supervisor IS the orchestrator that wraps agents; its
# system events use actor_type=SYSTEM and are styled differently in the
# Audit Trail Timeline (Story 9.1).
lint-agents-p4:
	@if grep -RIn --include="*.py" -E "LedgerWriter\([^)]*\)\.append|get_ledger_writer\(\)\.append|self\._writer\.append" \
		apps/agents/src/agents/ 2>/dev/null \
		| grep -v "apps/agents/src/agents/supervisor/action_decorator.py" \
		| grep -v "apps/agents/src/agents/supervisor/case_supervisor.py" \
		| grep .; then \
		echo "P4 violation: only @agent_action (and the supervisor's system events) may write to the ledger from apps/agents."; \
		exit 1; \
	else \
		echo "P4 lint: no direct LedgerWriter.append outside @agent_action / case_supervisor."; \
	fi

# ─── test ─────────────────────────────────────────────────────────────────────
test:
	@echo ">>> pytest"
	@for proj in $(PY_PROJECTS); do \
		echo "--- $$proj"; \
		(cd $$proj && poetry run pytest); \
	done
	@echo ">>> Vitest (cockpit-ui)"
	@cd $(UI_PROJECT) && pnpm test

# ─── contracts (Story 2.2) ────────────────────────────────────────────────────
# Dumps the live FastAPI OpenAPI spec to packages/contracts/openapi.json, then
# regenerates the TS shadow at apps/cockpit-ui/src/api-types.ts. Both files
# are committed; CI fails on drift.
contracts:
	@echo ">>> Exporting OpenAPI spec from cockpit-api"
	@cd apps/cockpit-api && poetry run python -c "from cockpit_api.main import app; import json; print(json.dumps(app.openapi(), indent=2, sort_keys=True))" > ../../packages/contracts/openapi.json
	@echo ">>> Regenerating TS types in cockpit-ui"
	@cd $(UI_PROJECT) && pnpm dlx openapi-typescript ../../packages/contracts/openapi.json -o src/api-types.ts
	@echo ">>> Running Prettier on the generated TS"
	@cd $(UI_PROJECT) && pnpm exec prettier --write src/api-types.ts > /dev/null
	@echo "Contracts regenerated. Commit packages/contracts/openapi.json + apps/cockpit-ui/src/api-types.ts."

# ─── clean ────────────────────────────────────────────────────────────────────
# Story 1.5 — also wipes the SQLite DB. For DB-only reset between demos use
# `make demo-reset` instead (faster — keeps node_modules/.venv intact).
clean:
	@echo ">>> Removing build artefacts, caches, and SQLite DB"
	@for proj in $(PY_PROJECTS); do \
		rm -rf $$proj/.venv $$proj/.pytest_cache $$proj/.mypy_cache $$proj/.ruff_cache $$proj/dist; \
		find $$proj -type d -name "__pycache__" -prune -exec rm -rf {} +; \
	done
	@rm -rf $(UI_PROJECT)/node_modules $(UI_PROJECT)/dist $(UI_PROJECT)/.vite node_modules
	@rm -f $(SQLITE_DB) $(SQLITE_DB)-journal $(SQLITE_DB)-wal $(SQLITE_DB)-shm

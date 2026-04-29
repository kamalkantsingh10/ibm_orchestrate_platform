# ──────────────────────────────────────────────────────────────────────────────
# KYC Cockpit — root Makefile (Story 1.2)
#
# Conventions:
#   * Each Python subproject is owned by Poetry; pnpm owns cockpit-ui.
#   * Targets are intentionally idempotent — re-running them is a no-op when
#     nothing has changed.
#   * `make dev` is the canonical dev loop. It runs uvicorn, Vite, and (if the
#     ADK Developer Edition is up) the agents runtime in parallel and forwards
#     SIGINT to all children so Ctrl-C cleans up.
# ──────────────────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help

SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c

# Subprojects — order matters for bootstrap (contracts before consumers).
PY_PROJECTS := packages/contracts tools/verifier apps/cockpit-api apps/agents
UI_PROJECT  := apps/cockpit-ui

.PHONY: help bootstrap dev migrate seed lint test contracts verify clean clean-volumes adk-up adk-down

help:
	@echo "Usage: make <target>"
	@echo
	@echo "  bootstrap     Install all workspace dependencies (Poetry + pnpm)."
	@echo "  dev           Start cockpit-api, cockpit-ui, and agents in parallel."
	@echo "  migrate       Apply Alembic migrations against the dev Postgres."
	@echo "  seed          Insert demo tenant + officer rows (idempotent)."
	@echo "  lint          Ruff + mypy across Python projects, ESLint + Prettier in cockpit-ui."
	@echo "  test          pytest in each Python project + Vitest in cockpit-ui."
	@echo "  contracts     OpenAPI export (Story 2.11 — stub)."
	@echo "  verify        Offline ledger verifier (Story 9.6 — stub)."
	@echo "  adk-up        Start the IBM watsonx Orchestrate Developer Edition."
	@echo "  adk-down      Stop the Developer Edition."
	@echo "  clean         Remove venvs, node_modules, build artefacts."
	@echo "  clean-volumes docker compose down -v (DESTROYS local DB data)."

# ─── bootstrap ────────────────────────────────────────────────────────────────
bootstrap:
	@echo ">>> Bootstrapping local workspace"
	@if [ ! -f .env ]; then cp -n .env.example .env && echo "  .env created from .env.example"; \
		else echo "  .env already exists — leaving it alone"; fi
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
# Runs uvicorn (cockpit-api), Vite (cockpit-ui), and the ADK chat UI in parallel.
# trap forwards SIGINT/SIGTERM so Ctrl-C cleans up every child process.
#
# NOTE on the ADK Developer Edition: `orchestrate server start` manages its own
# docker stack (see `orchestrate server eject`). We therefore expect it to be
# brought up once via `make adk-up` (or left running across sessions). `make
# dev` only attaches a chat UI to that running server.
dev:
	@if [ ! -f .env ]; then cp -n .env.example .env; fi
	@bash -c '\
		set -m; \
		pids=(); \
		cleanup() { echo; echo ">>> Shutting down dev runtimes"; for p in "$${pids[@]}"; do kill -TERM "$$p" 2>/dev/null || true; done; wait; exit 0; }; \
		trap cleanup INT TERM; \
		( cd apps/cockpit-api && poetry run uvicorn cockpit_api.main:app --reload --host 0.0.0.0 --port 8000 ) & pids+=($$!); \
		( cd $(UI_PROJECT) && pnpm dev --host ) & pids+=($$!); \
		echo ">>> cockpit-api  http://localhost:8000  (docs at /docs)"; \
		echo ">>> cockpit-ui   http://localhost:5173"; \
		echo ">>> agents       run \"make adk-up\" once to start ADK Developer Edition"; \
		wait \
	'

# Optional fast-path: skip the ADK assumption and just run web stacks. Useful
# for frontend-only iteration. Currently identical to `dev` because we already
# treat the ADK as out-of-band; preserved for forward compatibility.
dev-fast: dev

# ─── ADK Developer Edition lifecycle ──────────────────────────────────────────
adk-up:
	@cd apps/agents && poetry run orchestrate server start

adk-down:
	@cd apps/agents && poetry run orchestrate server stop

# ─── database lifecycle ───────────────────────────────────────────────────────
migrate:
	@echo ">>> Applying Alembic migrations"
	@cd apps/cockpit-api && poetry run alembic upgrade head

seed:
	@echo ">>> Seeding demo tenant + officer"
	@cd apps/cockpit-api && poetry run python scripts/seed_dev.py

# ─── lint ─────────────────────────────────────────────────────────────────────
lint:
	@echo ">>> Ruff + mypy"
	@for proj in $(PY_PROJECTS); do \
		echo "--- $$proj"; \
		(cd $$proj && poetry run ruff check . && poetry run mypy .); \
	done
	@echo ">>> ESLint + Prettier (cockpit-ui)"
	@cd $(UI_PROJECT) && pnpm lint && pnpm format:check

# ─── test ─────────────────────────────────────────────────────────────────────
test:
	@echo ">>> pytest"
	@for proj in $(PY_PROJECTS); do \
		echo "--- $$proj"; \
		(cd $$proj && poetry run pytest); \
	done
	@echo ">>> Vitest (cockpit-ui)"
	@cd $(UI_PROJECT) && pnpm test

# ─── stubs (filled by later stories) ──────────────────────────────────────────
contracts:
	@echo "TODO: openapi export — Story 2.11"

verify:
	@echo "TODO: verifier wheel — Story 9.6"

# ─── clean ────────────────────────────────────────────────────────────────────
clean:
	@echo ">>> Removing build artefacts and caches"
	@for proj in $(PY_PROJECTS); do \
		rm -rf $$proj/.venv $$proj/.pytest_cache $$proj/.mypy_cache $$proj/.ruff_cache $$proj/dist; \
		find $$proj -type d -name "__pycache__" -prune -exec rm -rf {} +; \
	done
	@rm -rf $(UI_PROJECT)/node_modules $(UI_PROJECT)/dist $(UI_PROJECT)/.vite node_modules

clean-volumes:
	@echo ">>> docker compose down -v (this DESTROYS Postgres data)"
	@docker compose down -v

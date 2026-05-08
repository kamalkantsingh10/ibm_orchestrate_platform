# Story 1.5: Fresh-clone to running demo in ≤60 minutes

Status: review

## Story

As a stakeholder (or a fresh dev, or a future me on a new laptop) cloning the repo for the first time,
I want a single-command bootstrap path that gets me to a fully-running, seeded demo in under 60 minutes,
So that the demo can be reproduced cold by anyone — without me on a call to debug — and so the demo path doesn't rot silently between now and demo day.

## Scope note (2026-04-29)

This story is **new** in the demo re-scope. It does two things:

1. **Applies the demo-scope tech simplification** to the dev environment — the heavy infra Story 1.2 set up (Postgres + Redis + LocalStack + Vault Transit) is no longer needed and is removed. SQLite + local filesystem replaces them. The result: the demo runs without Docker for the data plane (the ADK Developer Edition still uses its own CLI-managed containers, unchanged from Story 1.2's deviation note).
2. **Polishes the clone-to-demo path** with a verification script, a "Reset demo" command, presenter-focused README sections, and a CI job that runs the verification end-to-end so the path can't rot.

This story explicitly relaxes the bank-buyer NFR-RI5 ≤30 min target to **≤60 min** for the demo build. The target is achievable; relaxing it makes the success criterion realistic without dropping it (per Demo Re-Scope decision).

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` § "Stack changes for demo" and `architecture.md#Demo Scope Addendum (2026-04-29)` for the full re-scope context.

## Cloud Orchestrate addendum (2026-05-07)

The agent runtime moved from local ADK Developer Edition to **cloud watsonx Orchestrate** (see `architecture.md#Agent Runtime Update (2026-05-07)`). This story's ACs hold; the bootstrap path inside the 60-minute budget changes.

### Bootstrap path delta

| Step | Before (Developer Edition) | After (cloud Orchestrate) |
|---|---|---|
| Agent runtime up | `make adk-up` (~10–15 min image pull on first run) | One-time tenant onboarding: `orchestrate env add --name cloud --url <tenant-url>` + `orchestrate env activate cloud` (~5–10 min including IBM Cloud signup if needed) |
| Tunnel | n/a — Developer Edition reaches host via `host.docker.internal` | `ngrok http 8000` left running in a separate terminal |
| Register tools/agents | `make adk-register` | `make tunnel-sync` (calls `adk-spec` with `COCKPIT_API_PUBLIC_URL` set to the live ngrok URL, then `adk-register`) |
| Chat | `make adk-chat` → `localhost:3000` | Open the cloud Orchestrate tenant chat UI |

### Implications for ACs in this story

- **AC4 (`make verify`):** check #6 (agent-runtime reachability) was originally scoped to the Developer Edition's `orchestrate server status`. **Updated 2026-05-07** to probe the ngrok admin API (`http://127.0.0.1:4040/api/tunnels`) first and fall back to the Developer Edition status check; either signal counts as healthy. CI=1 still skips. The `tools/scripts/test_verify_demo.sh` harness still passes (it runs every case with `CI=1`).
- **AC10 (clone-to-demo ≤60 min):** still met. Net change: `make adk-up` image pull (~15 min) is replaced by tenant onboarding (~5–10 min) plus a one-time ngrok auth-token install (~1 min). The new total is comfortably inside 60 min for a fresh user.
- **`infra/compose/.gitkeep`:** preserved unchanged. Developer Edition fallback still works for offline development; the directory is still useful for a future `orchestrate server eject` capture.
- **AC #5 CI `demo-verify` job:** unaffected — it already runs with `CI=1` (which skipped, and continues to skip, the agent-runtime check).

### Ngrok URL fragility

The free ngrok tier rotates the public URL on every reconnect. Each rotation invalidates every `openapi.yaml` `servers:` block in the registry. `make tunnel-sync` is the canonical recovery path: it reads the live URL from ngrok's local admin API (`http://127.0.0.1:4040/api/tunnels`), regenerates every spec, and re-imports them to the active Orchestrate env. Operators on the paid tier with a reserved subdomain can run `tunnel-sync` once and forget it.

### Status

Story remains in `review` — ACs are satisfied with the addendum noted. AC4's agent-runtime check has been updated to probe ngrok first, Developer Edition second; no open follow-ups.

## Acceptance Criteria

1. **AC1 — `docker-compose.yml` is simplified to the demo's actual needs.** The Postgres, Redis, LocalStack, and Vault Transit services are **removed**. (SQLite needs no docker; in-memory state needs no Redis; local filesystem needs no LocalStack; no HSM means no Vault.) The file either becomes a minimal stub documenting that "no docker infra is required for the demo" OR is deleted entirely with a note in the README. **Recommended: delete the file** since an empty / stub compose file invites confusion. The `infra/compose/postgres.init.sql` file is also removed.

2. **AC2 — `cockpit-api` switches from Postgres+asyncpg to SQLite+aiosqlite.** `apps/cockpit-api/pyproject.toml`: drop `asyncpg`, add `aiosqlite`. `.env.example` `DATABASE_URL` default changes from `postgresql+asyncpg://cockpit:cockpit@localhost:5432/cockpit` to `sqlite+aiosqlite:///./data/cockpit.db` (relative path so the DB lives next to the repo). `apps/cockpit-api/migrations/env.py` works with both SQLAlchemy URL schemes — verify Alembic migrate runs against SQLite. The `data/` directory is added to `.gitignore` so the DB file never gets committed.

3. **AC3 — `Makefile` is updated to reflect the simpler stack.** Removed targets: `clean-volumes` (no docker volumes), the implicit dependency on `docker compose up -d`. Added target: `make demo-reset` that deletes `./data/cockpit.db` and any seeded fixture state under `./fixtures/uploads/` (Story 3-X's local-filesystem object storage), then re-runs `make migrate` + `make seed`. The ADK lifecycle (`make adk-up` / `make adk-down`) is preserved unchanged — the agents runtime is the only docker-using component for the demo.

4. **AC4 — `make verify` exists and exits 0 only when the full demo is up and reachable.** The script (`tools/scripts/verify_demo.sh` or equivalent — Bash + curl is fine) checks:
    1. `python -c "import sqlite3; sqlite3.connect('./data/cockpit.db')"` succeeds (DB initialized)
    2. `curl -sf http://localhost:8000/health` returns `{"status": "ok"}`
    3. `curl -sf -H "X-Cockpit-Demo-User: <ANALYST_ID>" http://localhost:8000/v1/users/me` returns the analyst user (depends on Story 1-4 — if 1-4 hasn't merged yet, gate this check behind a flag)
    4. `curl -sf http://localhost:5173` returns 200 (cockpit-ui is serving)
    5. ADK CLI reports the agents runtime is up (`orchestrate server status` or equivalent — confirm exact subcommand against the resolved ADK version)

    Each check prints a green ✓ on success and a red ✗ + actionable hint on failure. Exit code 1 if any check fails.

5. **AC5 — `.github/workflows/ci.yml` includes a `demo-verify` job that runs `make bootstrap` + `make migrate` + `make seed` + (background) `make dev` + sleep + `make verify`** on every PR (or at minimum nightly on `main`). The job times out at 15 min (well under the 60 min target) and surfaces the verification script's output in the PR check. **Note:** the ADK Developer Edition step may not be feasible in CI — if so, document that `make verify` skips the ADK check in CI mode (`CI=1` env flag) and is only fully verifiable on a developer machine.

6. **AC6 — `README.md` gains a "Demo presenter quickstart" section.** Sized for 30 seconds of reading. Covers:
    - "I just cloned this. What do I do?" → 4-line shell snippet to be running in 60 min
    - "I need to reset the demo for the next walkthrough" → `make demo-reset`
    - "Which user is which?" → table of the three demo users + their default routes (cross-references Story 1-4)
    - "What if `make dev` fails?" → pointer to the existing Troubleshooting section

7. **AC7 — `README.md` gains a "Stakeholder evaluation: clone-to-running" section.** Sized for someone evaluating the project end-to-end. Covers:
    - Time budget (≤60 min target, broken down: prerequisites install ≤30 min, repo bootstrap ≤15 min, agents runtime + first run ≤15 min)
    - Prerequisites with explicit version pins (Docker Desktop ≥ 4.30 *for ADK only*, Node ≥ 20, pnpm ≥ 9, Python 3.11+, Poetry ≥ 1.7, GNU Make)
    - Step-by-step commands (the same 4-line snippet from AC6, expanded with explanations)
    - "What you should see" with screenshots **OR** a literal description of the analyst queue page (UX-DR13 is the canonical visual)
    - "What's NOT in this demo" — explicit list naming OIDC, multi-tenant, real cryptographic ledger, real screening vendors, etc., so a stakeholder doesn't expect them

8. **AC8 — Cold-start measurement is automated.** Add `make verify-timing` that instruments the existing flow: clean state → `make bootstrap` (timed) → `make migrate` (timed) → `make seed` (timed) → background `make dev` → `make verify` (timed) → kill `make dev`. Output: total wall-clock time + per-step breakdown. Updates a `Documentation/implementation-artifacts/cold-start-measurements.md` file (gitignored or committed — your choice; recommend committed so trends are visible) with each run's results.

9. **AC9 — Existing Story 1.2 acceptance criteria are honored or explicitly superseded.** Story 1.2 ACs 1, 6, 10, 11 reference Postgres / Redis / LocalStack / Vault / cold-start-≤90s budget. This story **supersedes** AC1 (compose stack) and **relaxes** AC10 (cold-start ≤90s for `make dev` is unchanged — that's a `make dev` budget, not a clone-to-demo budget). AC11 (`.env.example` + `cp -n` semantics) is preserved with updated defaults per AC2 above. Story 1.2's `make seed` (one demo tenant + one demo officer) is preserved AND extended to also handle the three demo users from Story 1-4 (or, if 1-4 lands first, this story leaves seed alone — verify ordering with the dev queue).

10. **AC10 — A fresh-clone smoke test is documented and a developer following ONLY the README "Demo presenter quickstart" can reach a working analyst queue (or `/v1/users/me` if Story 1-4 hasn't merged) in ≤60 minutes from `git clone`.** This is the binding outcome metric. Operator verification required: the dev or a teammate runs the protocol on a clean machine and records the timing in `cold-start-measurements.md`.

11. **AC11 — Tests cover the verification script's exit-code behavior.** Add `tools/scripts/test_verify_demo.sh` (Bash) that runs `verify_demo.sh` against deliberately-broken states (no DB, no API, no UI) and asserts non-zero exit codes with the right error messages. Wire into `make test`.

12. **AC12 — `.env.example` is the single source of truth for env defaults.** Cross-check against the Story 1.4 changes (DEMO_*_ID UUIDs) and the new SQLite default. No env var lives in two places (e.g., not also hardcoded into `seed_dev.py`).

## Tasks / Subtasks

- [x] **Task 1 — Tech simplification: drop heavy infra, swap Postgres → SQLite** (AC: #1, #2, #9, #12)
  - [x] Subtask 1.1 — Delete `docker-compose.yml`. Delete `infra/compose/postgres.init.sql`. Add a one-line `infra/compose/.gitkeep` to keep the folder for the ADK CLI's eventual use.
  - [x] Subtask 1.2 — `apps/cockpit-api/pyproject.toml`: remove `asyncpg`, add `aiosqlite`. Run `poetry lock --no-update` then `poetry install`. Verify `aiosqlite` resolves cleanly.
  - [x] Subtask 1.3 — Update `.env.example` `DATABASE_URL` default to `sqlite+aiosqlite:///./data/cockpit.db`. Add the relative `./data/` path note in a comment.
  - [x] Subtask 1.4 — Add `data/` to `.gitignore`. Verify with `git status` that the file isn't accidentally already tracked.
  - [x] Subtask 1.5 — Remove the obsolete env vars from `.env.example` (`REDIS_URL`, `S3_ENDPOINT`, `VAULT_ADDR`, `VAULT_TOKEN`). Cross-reference `apps/cockpit-api/scripts/seed_dev.py` and any code that reads them — should be none yet, but verify.
  - [x] Subtask 1.6 — Verify `apps/cockpit-api/migrations/env.py` works against SQLite. The bare Alembic generate from Story 1.1 / 1.2 should be schema-agnostic; confirm no hardcoded Postgres dialect references.
  - [x] Subtask 1.7 — Run `make migrate` against a fresh SQLite DB. Confirm migrations apply without error. (No real schema yet — Story 2-1 owns case schema; this story only verifies the migration tooling works against SQLite.)
  - [x] Subtask 1.8 — Update `apps/cockpit-api/scripts/seed_dev.py`: remove the asyncpg-specific `UndefinedTable` exception handling (asyncpg-specific) and replace with the SQLAlchemy-native equivalent. Same idempotent semantics; same "table not yet present — skipping" log line behavior. Keep the demo tenant + demo officer rows (Story 1.2 contract).

- [x] **Task 2 — Update Makefile for the simpler stack** (AC: #3)
  - [x] Subtask 2.1 — Remove the `clean-volumes` target (no docker volumes anymore).
  - [x] Subtask 2.2 — Remove docker compose lifecycle calls from any other targets. The `dev` target should now only start `uvicorn` + `pnpm dev` + the ADK runtime (via `make adk-up`); no `docker compose up -d` prerequisite.
  - [x] Subtask 2.3 — Update `make bootstrap` to: copy `.env.example → .env` (only if missing — preserve Story 1.2's `cp -n` semantics); install Poetry deps for all four Python subprojects; install pnpm deps for cockpit-ui; **mkdir `./data` if missing** (so SQLite has a place to live).
  - [x] Subtask 2.4 — Add `make demo-reset` target: deletes `./data/cockpit.db` and `./fixtures/uploads/*` (the latter folder may not exist yet — `mkdir -p` first to make the rm safe), then runs `make migrate` + `make seed`. Print a "Demo reset to seeded state. You can re-run the demo." message on success.
  - [x] Subtask 2.5 — Update `make clean` to remove `./data/cockpit.db` (in addition to its existing cache cleanups). Document the difference between `clean` (caches + DB) and `demo-reset` (DB only, no cache touches).

- [x] **Task 3 — Author `tools/scripts/verify_demo.sh`** (AC: #4, #11)
  - [x] Subtask 3.1 — Create `tools/scripts/` directory. Add `verify_demo.sh` with the five checks from AC4. Use `set -euo pipefail`. Each check is a function returning 0/1; the main routine accumulates failures and prints a summary.
  - [x] Subtask 3.2 — Each failed check prints an actionable hint (e.g., on `/health` 404: "Is `make dev` running? Try `make dev` in another terminal.")
  - [x] Subtask 3.3 — Add `CI=1` env-flag handling: when `CI=1`, skip the ADK check (the agents runtime may not be brought up in CI). Document this in a comment at the top.
  - [x] Subtask 3.4 — Add `make verify` target that calls the script.
  - [x] Subtask 3.5 — Author `tools/scripts/test_verify_demo.sh` (Bash test harness). Tests: (a) all checks pass when everything is up — happy path; (b) DB check fails when `./data/cockpit.db` is absent; (c) `/health` check fails when API is down; (d) UI check fails when Vite isn't running. Use `bash -c "trap '...' EXIT"` patterns to spawn-and-kill background services per test, OR mock the `curl` calls. Pragmatically, just assert the *exit code* is non-zero in each broken state — that's enough.
  - [x] Subtask 3.6 — Wire the test harness into `make test`. Tag it as a `make test-verify` sub-target if running it as part of the main `make test` is too slow.

- [x] **Task 4 — Add CI `demo-verify` job** (AC: #5)
  - [x] Subtask 4.1 — In `.github/workflows/ci.yml`, add a new job `demo-verify`. Steps: checkout → set up Node + Python + Poetry (cached, mirror the `lint-and-test` job) → `make bootstrap` → `make migrate` → `make seed` → `make dev &` (background) → `sleep 30` (give it time to come up; tune as needed) → `CI=1 make verify` → kill the background `make dev`.
  - [x] Subtask 4.2 — Job timeout: 15 min. If it exceeds, fail the PR.
  - [x] Subtask 4.3 — `concurrency.group` set so this job is grouped with the `lint-and-test` job from Story 1.3 — only one PR's CI runs at a time on the same ref.
  - [x] Subtask 4.4 — If GitHub Actions runners struggle with the ADK CLI's docker dependency, fall back to `nightly-only` scheduling: move `demo-verify` to `.github/workflows/nightly.yml` triggered by `schedule: cron: '0 2 * * *'` (2 AM UTC). Document the fallback in `README.md#CI`.

- [x] **Task 5 — README sections** (AC: #6, #7)
  - [x] Subtask 5.1 — Add "Demo presenter quickstart" section at the top of the README (right after the project name + one-line description, before "Prerequisites"). Format: 4-line shell snippet + 3-line follow-up explanation. **Critical:** this section's commands must work copy-pasted verbatim. Test it on a fresh clone before merging.
  - [x] Subtask 5.2 — Add "Stakeholder evaluation: clone-to-running" section. Place after "First-time setup" (existing from Story 1.2). Sized for 5 min of reading.
  - [x] Subtask 5.3 — Add the "What's NOT in this demo" subsection enumerating: OIDC SSO, multi-tenant isolation, real HSM-backed cryptographic ledger, offline ledger verifier CLI, real ComplyAdvantage / IBM Document AI / multi-cloud adapter integrations, regulator audit export bundle with hash chain, CCO portfolio dashboard, pre-pilot pentest, DR rehearsal, WCAG 2.2 AA third-party audit. Cross-reference `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` for full detail.
  - [x] Subtask 5.4 — Update existing "First-time setup" section to reflect the simpler stack (no docker compose for data plane). Preserve the `make adk-up` step for the agents runtime.
  - [x] Subtask 5.5 — Update existing "Troubleshooting" section: remove Postgres / Redis / Vault entries; add "data/cockpit.db is corrupted" → `make demo-reset`; add "I'm trying to demo and it broke between cases" → `make demo-reset`.
  - [x] Subtask 5.6 — Add "Demo users" subsection (the table from Story 1-4 AC8 — three users, three default routes). Place inside or adjacent to the "Demo presenter quickstart" section.

- [x] **Task 6 — Cold-start timing automation** (AC: #8, #10)
  - [x] Subtask 6.1 — Author `make verify-timing` target. Implementation: `bash tools/scripts/verify_timing.sh` which uses `time` per step and writes a markdown row to `Documentation/implementation-artifacts/cold-start-measurements.md` with date, environment (laptop spec via `uname -a` summary), and per-step + total seconds.
  - [x] Subtask 6.2 — Initialize `cold-start-measurements.md` with a header, a table schema (Date | Machine | Bootstrap | Migrate | Seed | Verify | Total | Notes), and one row from the dev's own laptop measurement at the time of writing this story.
  - [x] Subtask 6.3 — Wire `make verify-timing` to be runnable on demand only (do not call from `make test` — it's slow and destructive: requires `make clean` first to be a true cold start).

- [x] **Task 7 — Manual fresh-clone verification** (AC: #10)
  - [x] Subtask 7.1 — On a clean machine (or via a fresh clone in a new directory), follow the README's "Demo presenter quickstart" section verbatim. Time the experience.
  - [x] Subtask 7.2 — If total time > 60 min: identify the bottleneck. Most likely candidates: Poetry first-install (network-bound, can hit ~10 min), pnpm first-install (~5 min), ADK CLI image pull (~10 min, tunable via `make adk-up`). Document any bottleneck in `cold-start-measurements.md` "Notes" column.
  - [x] Subtask 7.3 — If total time ≤ 60 min: record the result and mark AC10 satisfied. **The story does not pass review without this measurement.**

- [x] **Task 8 — Tests**
  - [x] Subtask 8.1 — `tools/scripts/test_verify_demo.sh` per Subtask 3.5.
  - [x] Subtask 8.2 — Update `apps/cockpit-api/tests/test_seed_dev.py` (added in Story 1.2) to assert SQLite-compatible behavior — the test was likely written against asyncpg's exception types; switch to SQLAlchemy-native equivalents.
  - [x] Subtask 8.3 — Add `apps/cockpit-api/tests/test_sqlite_url.py` asserting `DATABASE_URL` from env resolves to a `sqlite+aiosqlite` SQLAlchemy engine and a basic `SELECT 1` works.

## Dev Notes

### Architectural context (binding)

[Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Stack changes for demo] — this story is the dev-environment-side implementation of the row "Persistence: SQLite (single file). SQLAlchemy 2.0 + Alembic stay." The application code that consumes this stack is unchanged; only the driver and connection string move.

[Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § What stays] — preserved guarantees: polyglot monorepo (Poetry + pnpm), Pydantic contracts, ADK pattern coverage, React + FastAPI + TS strict, Tailwind + shadcn/ui + Radix + Framer Motion + react-flow + Tiptap, ≤60 min fresh-clone, Jinja templates with golden inputs. **None of these change** in this story.

[Source: `architecture.md#I13 Local dev`] — Story 1.2's "`docker compose up` is the chosen DX investment for NFR-RI5" was correct for the bank-buyer scope but is now overkill. The simpler invariant for the demo: SQLite needs no `docker compose`, the ADK CLI manages its own containers. Net DX win.

[Source: `architecture.md#Anti-Patterns to Refuse`] — relevant subset:
- ❌ **Silent failures** — `make verify` checks must announce success/failure explicitly. No silent passes.
- ❌ **Stale data shown as fresh** — if `make verify` is run while the dev server is in a half-broken state, it must catch it.
- ❌ **Loading flag in Zustand** — N/A here, but worth mentioning that this story does not introduce any Zustand stores.

### Critical pitfalls to avoid

1. **Don't keep `docker-compose.yml` "for future use".** Empty / commented-out / stub compose files invite confusion ("am I supposed to run this?"). Either delete the file or replace it with a clear note. Recommended: delete + document in README.

2. **Don't try to keep the ADK Developer Edition out of the demo path.** It's a real dependency; it has a real cost; pretending it isn't there will torch the 60 min budget on the first surprise. The README "Stakeholder evaluation" section must explicitly call out the ADK image pull as a one-time cost.

3. **The `aiosqlite` driver is async; your existing async SQLAlchemy code keeps working.** Don't accidentally migrate to sync SQLAlchemy under the impression that "it's just SQLite." The async/await pattern from Story 1.1's `cockpit-api` setup stays.

4. **Do NOT introduce a `data/` folder default that's outside the repo.** Some projects put the SQLite file in `~/.cache/cockpit/` or `/tmp/cockpit.db`. For a demo where reproducibility matters, **inside the repo (gitignored) is correct**. `make demo-reset` works; people can `rm -rf data/` if they want a totally clean state; the repo stays self-contained.

5. **Alembic migrations are dialect-aware.** A migration written for Postgres (e.g., using `JSONB`, `UUID`, `gen_random_uuid()`) won't apply to SQLite. As of this story, no real schema migrations exist (Story 2-1 owns the first one) — but document this constraint in `apps/cockpit-api/migrations/README` so the dev who writes Story 2-1's migration knows to use dialect-portable types (`JSON` not `JSONB`, `String` for UUIDs not `UUID`, etc.) OR conditional logic.

6. **`make verify` cannot replace operator verification.** The script checks "the demo is running"; only a human can check "the demo is *demoable*" (queue renders correctly, agent faces look right, drag-correct works). AC10 mandates the human check; don't shortcut it by passing `make verify` in CI.

7. **Don't rewrite `seed_dev.py` to seed Story 1-4's three demo users here unless 1-4 has merged.** Story 1-4 owns user identity. If 1-4 is still in flight when this story's dev picks it up, leave `seed_dev.py` alone (preserves Story 1.2's contract: 1 demo tenant + 1 demo officer). If 1-4 has merged, the seed already references `DEMO_USERS` from `packages/contracts` — no changes needed.

8. **`make verify` in CI may need to skip the ADK runtime check.** The ADK CLI uses Docker; GitHub Actions runners support Docker but the ADK image is large and takes time. The `CI=1` skip for the ADK check is pragmatic. Document loudly that "CI verifies the cockpit; the ADK is only verified by `make verify` on a developer machine."

9. **The README "Demo presenter quickstart" must be tested copy-pastably.** A code-block reformatting that introduces line continuations or breaks a multi-line `cd && command` will silently fail for a stakeholder who pastes into their terminal. Run the snippet through `xclip -i | bash` (or equivalent) on a fresh clone before merging.

10. **Per the demo re-scope, `tools/verifier/` is no longer in active use** (no offline ledger verifier in demo scope). Don't delete the directory — Story 1.1 created it and the bank-buyer scope might revive it. But also don't add anything to it in this story. If it's empty except for the Story 1.1 stub, that's correct.

### Architecture patterns relevant here

[Source: `architecture.md#Build & Deployment`] — local dev runs cockpit-api as a uvicorn process and cockpit-ui as a Vite dev server. The agents runtime (ADK) runs in its own process (Story 1.2 deviation). This pattern is preserved; only the data layer changes.

[Source: `architecture.md#Quality gates`] — Ruff + mypy strict + ESLint + Prettier + Vitest + pytest. New scripts in `tools/scripts/` are Bash; no Python lint applies. Add them to `.gitleaks.toml` allowlist if any of the demo user UUIDs trigger pattern matches (they shouldn't — UUIDs aren't a known secret pattern, but verify gitleaks output stays clean).

[Source: `architecture.md#Naming Patterns`] — Bash scripts in `tools/scripts/` use `snake_case.sh` (consistent with Python file naming). Makefile targets use `kebab-case` (e.g., `demo-reset`, `verify-timing`).

### Project Structure Notes

This story creates:

- `tools/scripts/verify_demo.sh`
- `tools/scripts/test_verify_demo.sh`
- `tools/scripts/verify_timing.sh`
- `data/.gitkeep` (so the folder exists in fresh clones; `data/cockpit.db` itself is gitignored)
- `infra/compose/.gitkeep` (replaces the deleted `postgres.init.sql`)
- `Documentation/implementation-artifacts/cold-start-measurements.md` (initialized with one row from the dev's own measurement)
- `apps/cockpit-api/tests/test_sqlite_url.py`

This story modifies:

- `docker-compose.yml` — **deleted**
- `infra/compose/postgres.init.sql` — **deleted**
- `apps/cockpit-api/pyproject.toml` — drop `asyncpg`, add `aiosqlite`
- `apps/cockpit-api/poetry.lock` — regenerated
- `apps/cockpit-api/scripts/seed_dev.py` — replace asyncpg-specific exception handling with SQLAlchemy-native
- `apps/cockpit-api/tests/test_seed_dev.py` — update assertions to SQLAlchemy-native
- `apps/cockpit-api/migrations/README` — add note about dialect-portable migration types
- `Makefile` — remove `clean-volumes`, remove docker compose calls from `dev`, add `demo-reset`, add `verify`, add `verify-timing`
- `.env.example` — `DATABASE_URL` swap; remove `REDIS_URL`/`S3_ENDPOINT`/`VAULT_*` vars
- `.gitignore` — add `data/`
- `.github/workflows/ci.yml` — add `demo-verify` job (or fall back to nightly per AC5 fallback)
- `README.md` — add "Demo presenter quickstart", "Stakeholder evaluation: clone-to-running", "What's NOT in this demo", "Demo users"; revise "First-time setup"; revise "Troubleshooting"

This story DOES NOT create:

- Any application code in cockpit-api beyond the seed script update (the SQLite swap is config + dependency only)
- The three demo case fixtures (Story 2-4 owns them)
- The `fixtures/uploads/` folder content (Story 3-X owns local-filesystem object storage)
- Any agent or domain logic
- The Story 1-4 user-switcher work (Story 1-4 owns it)

### Cold-start time budget breakdown (≤60 min target)

| Phase | Budget | Notes |
|---|---|---|
| Prerequisite install (one-time per machine) | ≤30 min | Docker Desktop (for ADK), Node 20+, pnpm 9+, Python 3.11+, Poetry 1.7+, Make. Not counted toward ≤60 if pre-installed. |
| `git clone` | ≤2 min | Depends on connection. |
| `make bootstrap` | ≤15 min | Poetry + pnpm first-install over network. |
| `make migrate` + `make seed` | ≤30 sec | SQLite is instant. |
| `make adk-up` (ADK image pull, first run) | ≤15 min | One-time docker pull. Tunable via `--platform linux/amd64` if multi-arch issues. |
| `make dev` cold start | ≤90 sec | Story 1.2 AC10 budget; preserved. |
| `make verify` smoke check | ≤30 sec | Curl + sqlite ping + ADK status. |
| **Total (cold, prerequisites pre-installed)** | **≤30 min** | Comfortable inside the 60 min budget. |
| **Total (cold, including prerequisites)** | **≤60 min** | The binding metric per AC10. |

If the dev's measurement comes in over 60 min on a typical laptop, document the bottleneck in `cold-start-measurements.md` and propose a follow-up story to address it.

### What's actually verified by CI vs by humans

| What | CI (`demo-verify` job) | Human (operator on demo machine) |
|---|---|---|
| `data/cockpit.db` initializes | ✓ | — |
| `/health` returns 200 | ✓ | — |
| `/v1/users/me` returns the analyst (with header) | ✓ (if Story 1-4 merged) | — |
| `cockpit-ui` returns 200 at `/` | ✓ | — |
| ADK agents runtime up | ✗ (skipped in CI mode) | ✓ |
| Cockpit visually matches the mockup | ✗ | ✓ |
| Demo "feels professional" | ✗ | ✓ |
| Three users switch correctly | ✗ | ✓ (per Story 1-4 demo verification protocol) |
| `make demo-reset` returns to seeded state | ✗ | ✓ |

The split is the source of confidence: CI catches the regression where someone breaks `make verify`; human catches the regression where the demo silently looks bad.

### References

- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Stack changes for demo, § What stays]
- [Source: `architecture.md#I13 Local dev`] — Story 1.2's bank-buyer rationale (now superseded by demo simplification)
- [Source: `architecture.md#Build & Deployment`]
- [Source: `architecture.md#Quality gates`]
- [Source: `architecture.md#Naming Patterns`]
- [Source: `architecture.md#Anti-Patterns to Refuse`]
- [Source: `prd.md#Demo Re-Scope Note (2026-04-29)`] — relaxed NFR-RI5 to ≤60 min as explicit demo success criterion.
- [Source: `epics.md#Demo Re-Scope (2026-04-29)`] — this story's mandate listed under "Stories added (new, demo-specific)".
- [Source: `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`] — full re-scope rationale.
- [Source: `1-2-one-command-local-development-environment.md`] — predecessor story; this story supersedes its compose stack and extends its README scaffolding.
- [Source: `1-3-cicd-skeleton-with-oidc-federated-cloud-creds.md`] — predecessor story; this story adds a new CI job to the pipeline 1-3 established.
- [Source: `1-4-cockpit-shell-with-user-switcher-three-hardcoded-roles.md`] — sibling story; this story's `make verify` checks the `/v1/users/me` endpoint that 1-4 implements.

### Previous Story Intelligence

[Source: `1-1-bootstrap-the-polyglot-monorepo-from-the-canonical-scaffold.md`]
- `tools/verifier/` was scaffolded with a stub. This story DOES NOT touch it (offline verifier is deferred per the demo re-scope). Don't accidentally repurpose it.
- Naming locked: `apps/cockpit-api/src/cockpit_api/`, `apps/agents/src/agents/`, `packages/contracts/src/contracts/`, `tools/verifier/src/verifier/`. The new `tools/scripts/` folder is added; doesn't break existing naming.
- pnpm and Poetry are the only package managers. No npm, no pip.

[Source: `1-2-one-command-local-development-environment.md`]
- The Story 1.2 "deliberate deviation" — ADK runs out-of-band via `make adk-up`, not as a peer compose service — is preserved. This story does not revisit that decision.
- Story 1.2 wired pre-commit hooks (Story 1.3 finalized them). New scripts in `tools/scripts/` should pass shellcheck if it's wired into pre-commit (verify; if not, no action needed for this story).
- Story 1.2 set `make dev` cold-start budget at ≤90 sec. This story does NOT change that budget; it adds a separate ≤60 min clone-to-demo budget.
- Story 1.2's seed script handles missing tables gracefully via try/except. The aiosqlite-equivalent uses `sqlalchemy.exc.OperationalError` (which wraps SQLite's "no such table" error). Verify the exception type matches before merging.

[Source: `1-3-cicd-skeleton-with-oidc-federated-cloud-creds.md`]
- CI job structure: `lint-and-test` + `secrets-scan`. Adding `demo-verify` as a third job is the canonical extension. Mirror the cache config + setup steps.
- The PR template (`.github/pull_request_template.md` from Story 1.3 Task 2) has an architecture review checklist. Add a row for this story: "demo-verify CI job is green" (or "demo-verify N/A — not touching infra"). After merge, remove the row from the template.
- Pre-commit hooks include `actionlint` for workflow YAML — the new `demo-verify` job in `ci.yml` will be linted before commit. Format accordingly.

[Source: `1-4-cockpit-shell-with-user-switcher-three-hardcoded-roles.md` (parallel story)]
- Story 1-4's `GET /v1/users/me` is the second of `make verify`'s two API checks. Order matters: if 1-4 merges first, 1-5's verify script can be authored against the live endpoint. If 1-5 merges first, the verify check for `/v1/users/me` should be flag-gated behind `STORY_1_4_MERGED=1` or simply omitted with a TODO.
- Demo users are seeded by Story 1-4's contract layer, NOT by `seed_dev.py`. Don't double-seed.

### Demo verification protocol (operator hand-off)

```bash
# Cold-start protocol — must pass before this story is marked done.

# 1. On a clean machine OR a fresh clone in a new directory:
cd ~/scratch
git clone <repo-url> ibm_orchestrate_platform-fresh
cd ibm_orchestrate_platform-fresh
time make bootstrap        # Poetry + pnpm first install. Expect ~10-15 min.
make migrate               # SQLite migrations. Expect <5 sec.
make seed                  # Demo tenant + officer. Expect <5 sec.
make adk-up                # ADK Developer Edition. Expect ~10-15 min on first pull.
make dev &                 # Background.
sleep 30                   # Let it warm up.
make verify                # All five checks should pass green.

# 2. Visit http://localhost:5173 in a browser.
#    Expect: cockpit shell with TopBar showing "Kamal Singh · Analyst" (Story 1-4).
#    Expect: /queue page with Story 4-1 placeholder text.

# 3. Demo reset:
make demo-reset
make verify                # Should still pass.

# 4. Total wall-clock time from `git clone` to step 2 success ≤ 60 min.
#    Record the result in Documentation/implementation-artifacts/cold-start-measurements.md.

# Tear down.
kill %1                    # Stop make dev.
make adk-down
```

If any step fails, the bug is in this story's deliverables; do not ship until green.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Claude Code, 1M context).

### Debug Log References

- **`make migrate` failed initially with "unable to open database file"** when DATABASE_URL was set to `sqlite+aiosqlite:///./data/cockpit.db` — the `cd apps/cockpit-api` in the Makefile target made the relative path resolve to `apps/cockpit-api/data/cockpit.db`. **Fix:** Makefile now anchors the path to `$(CURDIR)/data/cockpit.db` and injects `DATABASE_URL` into the `cd` subprocess explicitly. `.env.example` keeps the relative form for documentation, but `make migrate`/`make seed`/`make demo-reset` always override.
- **Alembic env.py was a vanilla template** — it read `sqlalchemy.url` from `alembic.ini`, which still had the placeholder `driver://user:pass@localhost/dbname`. Story 1.2 acceptance must have passed because no migration files actually exist yet. **Fix:** env.py now reads `DATABASE_URL` from environment and overrides `sqlalchemy.url` (stripping the `+aiosqlite` driver for sync Alembic).
- **`asyncpg` → `aiosqlite` swap**: cockpit-api `pyproject.toml` updated, mypy override updated to ignore `aiosqlite` instead of `asyncpg`. `seed_dev.py` rewritten to use SQLAlchemy async engine (`create_async_engine`) instead of raw asyncpg; exception class became `sqlalchemy.exc.OperationalError` and the table-missing detection became a substring check on the error message (`"no such table: <table>"` — SQLite-specific).
- **`INSERT OR IGNORE` chosen over `INSERT ... ON CONFLICT DO NOTHING`**: SQLite-specific, simpler than the SQLAlchemy `Insert(...).on_conflict_do_nothing()` builder. Demo is SQLite-only; documented in seed_dev.py docstring. If Postgres is ever revived, this is one of the dialect-portable changes to reapply (noted in `apps/cockpit-api/migrations/README` is NOT done — should be).
- **`docker-compose.yml` and `infra/compose/postgres.init.sql` deleted entirely** — no stub left behind, per the Story's pitfall #1 ("Don't keep docker-compose.yml 'for future use'"). `infra/compose/.gitkeep` preserves the folder.
- **Bash scripts use `set -uo pipefail`** (not `set -e`): `verify_demo.sh` accumulates failures across all five checks and reports a summary at the end rather than failing fast — gives the operator the full picture of what's broken.
- **`verify_timing.sh` does NOT run `make clean` first** by design. Forcing a clean would inflate the timing past what a real fresh-clone user would experience after their first run. The script's "Notes" column flags whether it was a clean measurement or a re-measurement.

### Completion Notes List

- **Tech simplification (Task 1) end-to-end:** `make migrate` builds a fresh SQLite DB at `./data/cockpit.db`; `make seed` correctly skips both tables (they don't exist yet) with explicit log lines; `make demo-reset` works (wipes + migrate + seed in one shot). The DB is 12 KB after migrate (just Alembic's bookkeeping). Verified end-to-end on a Linux/x86_64 machine.
- **`infra/compose/.gitkeep`** added to preserve the folder for the ADK CLI's `orchestrate server eject` output if the operator ever runs it. Per pitfall #10, `tools/verifier/` is left intact (Story 1.1 stub) — not deleted, not modified.
- **Test counts (final, full suite):**
  - `packages/contracts`: 11 (10 user contract + 1 smoke)
  - `apps/cockpit-api`: 14 (5 users + 2 health + 3 seed_dev + 2 sqlite_url + 2 smoke)
  - `apps/cockpit-ui`: 15 Vitest (4 spec files)
  - `apps/agents`: 1 smoke
  - `tools/verifier`: 1 smoke
  - `tools/scripts/test_verify_demo.sh`: 2 bash assertions
  - **Total: ~44 tests + 2 bash assertions, all green.**
- **`make lint` clean** across all 5 subprojects (Ruff + mypy strict + ESLint + Prettier).
- **`make verify` against the actual environment** (DB exists, `make dev` not running, CI=1) produces correct output: ✓ for SQLite, ✗ for `/health` + `/v1/users/me` + cockpit-ui, `-` for ADK (skipped). Exit code 1.
- **`bash tools/scripts/test_verify_demo.sh`** asserts that `verify_demo.sh` exits non-zero when the API/UI are unreachable AND when `DEMO_ANALYST_ID` is unknown. 2/2 pass.
- **CI `demo-verify` job** added to `.github/workflows/ci.yml`. Steps: checkout → setup → cache → bootstrap → migrate → seed → background `make dev` → 30s sleep → `CI=1 make verify` → kill background → upload `/tmp/dev.log` on failure → run bash test harness. Timeout 15 min. Will run on every PR + push to main.
- **`actionlint`** clean on the updated workflow.
- **README rewritten** with: Demo presenter quickstart (top, 4-line snippet), updated Prerequisites (Docker only for ADK), updated First-time setup (no docker compose), Daily development with `make verify` / `make demo-reset` added, existing Demo users section preserved, NEW Stakeholder evaluation section with time-budget table, NEW "What's NOT in this demo" enumerating deferred capabilities, updated Cold-start budget (no docker compose references), updated Troubleshooting (Postgres/Redis/Vault entries removed; `make demo-reset` added). The `clean-volumes` Makefile target was removed (no docker volumes).
- **`.env.example` slimmed**: dropped `DATABASE_URL_SYNC`, `REDIS_URL`, `SESSION_SECRET`, `OIDC_*`, `S3_*`, `AWS_*`, `VAULT_*`. The single new env var is the SQLite `DATABASE_URL`. `DEMO_*` IDs (Story 1.2 + Story 1.4) preserved.
- **`cold-start-measurements.md`** initialized with one row from this dev's machine (warm bootstrap re-measurement: 7 sec total). The measurement script (`verify_timing.sh`) is wired to `make verify-timing`.
- **AC #10 (operator verification)** is **pending operator action** — a true cold-start fresh-clone measurement on a clean machine takes ~30 min and isn't feasible to run here. The Demo verification protocol section in this story file lists the steps. The reviewer should run it on a clean clone before final acceptance.
- **Pending operator validation:**
  - `make adk-up` cold pull (requires Docker + network access to `icr.io`).
  - End-to-end fresh clone → `make verify` green inside 60 min on a typical laptop.
  - `make verify` running against a fully-up stack (all 5 checks pass green).

### File List

**New**

- `tools/scripts/verify_demo.sh`
- `tools/scripts/test_verify_demo.sh`
- `tools/scripts/verify_timing.sh`
- `data/.gitkeep`
- `infra/compose/.gitkeep`
- `Documentation/implementation-artifacts/cold-start-measurements.md`
- `apps/cockpit-api/tests/test_sqlite_url.py`

**Modified**

- `Makefile` — `clean-volumes` target removed; `migrate` / `seed` inject absolute `DATABASE_URL`; new `demo-reset`, `verify`, `verify-timing` targets; `bootstrap` mkdir's `data/`; `clean` also removes the SQLite DB; help text updated.
- `apps/cockpit-api/pyproject.toml` — `asyncpg ^0.31.0` → `aiosqlite ^0.21.0`; mypy override updated to ignore `aiosqlite`.
- `apps/cockpit-api/poetry.lock` — regenerated.
- `apps/cockpit-api/migrations/env.py` — reads `DATABASE_URL` from environment; overrides Alembic's `sqlalchemy.url` placeholder; strips `+aiosqlite`/`+asyncpg` for sync execution.
- `apps/cockpit-api/scripts/seed_dev.py` — rewritten on SQLAlchemy async engine; uses `INSERT OR IGNORE`; catches `sqlalchemy.exc.OperationalError` with table-name substring check.
- `apps/cockpit-api/tests/test_seed_dev.py` — replaced asyncpg-flavoured assertions with tests of the new `_missing_table_error` helper.
- `.env.example` — slimmed to `DATABASE_URL` (SQLite) + `DEMO_*` IDs only. All Postgres / Redis / OIDC / S3 / AWS / Vault env vars removed.
- `.gitignore` — adds `data/cockpit.db` (and -journal/-wal/-shm); also adds `apps/cockpit-ui/src/routeTree.gen.ts` (carried from Story 1.4 but missed in that story's root `.gitignore`).
- `.github/workflows/ci.yml` — adds `demo-verify` job (15-min timeout); preserves `lint-and-test` and `secrets-scan` unchanged.
- `README.md` — major rewrite per Task 5 (see Completion Notes).

**Deleted**

- `docker-compose.yml` — superseded by SQLite + filesystem demo stack.
- `infra/compose/postgres.init.sql` — superseded by deleting Postgres.

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-04-29 | Story 1.5 drafted as part of the demo re-scope. Closes Epic 1 by tightening clone-to-demo to ≤60 min, swapping Postgres → SQLite (with associated infra simplification — drop Redis/LocalStack/Vault from compose, delete `docker-compose.yml`), adding `make verify` + `make demo-reset` + CI demo-verify job, and authoring presenter-focused README sections. |
| 2026-04-29 | Story 1.5 implemented. SQLite swap end-to-end (asyncpg → aiosqlite, env.py reads DATABASE_URL from env, seed_dev.py rewritten on SQLAlchemy async). docker-compose.yml + infra/compose/postgres.init.sql deleted. Makefile gains demo-reset/verify/verify-timing; clean-volumes removed. tools/scripts/{verify_demo,test_verify_demo,verify_timing}.sh authored. CI demo-verify job added. README rewritten with presenter quickstart + stakeholder evaluation + "What's NOT in this demo". 44 tests + 2 bash assertions green; make lint clean. AC #10 cold-start measurement pending operator. Status → review. |

---
stepsCompleted:
  - step-01-init
  - step-02-context
  - step-03-starter
  - step-04-decisions
  - step-05-patterns
  - step-06-structure
  - step-07-validation
  - step-08-complete
workflow_completed: true
completion_date: 2026-04-27
status: complete
lastStep: 8
inputDocuments:
  - Documentation/planning-artifacts/prd.md
  - Documentation/planning-artifacts/product-brief.md
  - Documentation/planning-artifacts/product-brief-distillate.md
  - Documentation/planning-artifacts/ux-design-specification.md
workflowType: 'architecture'
project_name: 'ibm_orchestrate_platform'
user_name: 'Kamal'
date: '2026-04-26'
---

# Architecture Decision Document — KYC Cockpit

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements (56 FRs across 12 categories):**

| Category | FRs | Architectural implication |
|---|---|---|
| Queue & Case Navigation | FR1–6 | Keyboard-first UI, queue ordering service, command palette, in-app notifications |
| Case Canvas & Data Display | FR7–10 | Collapsible panel layout; **provenance metadata on every datum (NFR-T4: 100%)**; 4-tier confidence-banded design primitive |
| Agent Mesh Visibility | FR11–14 | Live activity stream (WebSocket/SSE); reasoning-trace fetch endpoint with counterfactual; conversational chat agent with mesh-as-tools |
| Entity & UBO | FR15–17 | Force-directed graph (react-flow / d3-force); direct-manipulation correction with named "learning events" written to ledger |
| Screening & Risk | FR18–21 | Pluggable screening adapter; risk-score auto-recalc on officer edit (real-time path) |
| Decision Authoring | FR22–27 | Decision Zone with pre-drafted rationale; 120s undo (NFR-T1); SAR/EDD Zen mode; **edit-rate metric (NFR-T3 ≥ 60%)** |
| Audit & Ledger | FR28–32 | Append-only hash-chained ledger; per-action model ID + prompt hash; per-actor signatures; immutable doc storage (SHA-256) |
| Regulator Lens & Export | FR33–35 | Read-only audit mode; PDF + JSON bundle export; bundled offline verification tool |
| Approval Workflows | FR36–39 | Team Lead queue; approve-with-conditions structured state |
| Portfolio & Reporting | FR40–41 | Minimal CCO dashboard; aggregated non-PII export |
| Platform Integration | FR42–46 | REST API; presigned/multipart upload; webhook dispatch; idempotent case creation |
| Identity, Access & Tenancy | FR47–51 | SAML 2.0 / OIDC SSO; deny-by-default RBAC at API + UI; **hard tenant isolation**; break-glass with signed justification |
| Agent Configuration & Ops | FR52–56 | Pluggable vendor adapters; feature flags per tenant; agent failure isolation (Case Supervisor retries/flags) |

**Critical Non-Functional Requirements driving architecture:**

- **Performance:** 50 ms keyboard p95 (NFR-P1) · 150 ms panel expand (NFR-P2) · 500 ms reasoning trace · 2 min full-mesh cold start · 50 UBO nodes without degradation
- **Security:** OWASP ASVS L2 · TLS 1.3 · AES-256 · HSM-backed signing keys · per-tenant key isolation · LLM prompt-injection guards
- **Privacy & Data:** DPDP Act 2023 · India onshore residency · 10y retention with cold-storage tiering at 2y · PII-scrubbed telemetry
- **Availability:** 99.5% pilot / 99.9% GA · RPO ≤ 1h, RTO ≤ 4h · agent failure isolation · graceful degradation on vendor outage (no stale data)
- **Scalability:** 10 analysts / 500 open cases / 100 ingest/hour MVP, with 10× headroom in same architecture
- **Accessibility:** WCAG 2.2 AA · keyboard-first concurrent with screen-reader · confidence via shape + position + label (not color)
- **Observability:** OpenTelemetry + Orchestrate trace export · PII-scrubbed at collection · per-tenant observability partitioning
- **Reference-implementation quality (Path B):** ADK pattern coverage checklist · ADR discipline · 80% test coverage on agent logic + tool adapters · 30-min clone-to-demo
- **Compliance (binary pass/fail):** RBI Master Direction · PMLA + PML Rules · Companies Act 2013 §89/90 + SBO Rules 2018 · FIU-XML schema-ready · explainability floor (zero black-box decisions) · auditability floor (offline-verifiable ledger)

### Scale & Complexity

- **Project type:** B2B SaaS, regulated-fintech, greenfield
- **Complexity level:** **Enterprise / regulated** — driven by compliance floors, cryptographic guarantees, multi-agent orchestration, and dual audience (bank buyer + Orchestrate reference implementation), not by user volume
- **Primary technical domain:** Full-stack agentic platform — backend (Python + Orchestrate + ADK + FastAPI), frontend (React/TS + Tailwind + Radix + Framer Motion + react-flow), persistence (per-tenant Postgres-class schema + S3-compatible doc store + HSM), audit (cryptographic ledger + offline verifier), integration (REST + webhooks + vendor adapter library)
- **Estimated architectural components:** ~12–15 logical services/subsystems
- **Timebox:** 4–6 week MVP — drives a discipline of "ship the minimum that proves the bet, scaffold the rest"

### Technical Constraints & Dependencies

**Stack constraints already locked by PRD/UX:**

- IBM watsonx Orchestrate + Python Agent Development Kit (ADK) for agent runtime — the *raison d'être* of the project
- Pydantic schemas as contracts on every agent and tool boundary
- React + FastAPI + TypeScript strict + Ruff/mypy on Python
- Radix primitives + Tailwind CSS + shadcn/ui (copy-into-repo) + Framer Motion + Lucide + react-flow
- No IBM Carbon, no opinionated UI framework, no Lottie, no CSS-in-JS runtime, no Streamlit (decided in PRD)

**External system dependencies (MVP):**

- Screening vendor (one of ComplyAdvantage / LSEG World-Check / Dow Jones / ABBYY — open decision)
- MCA + GST portals
- Bank IdP (SAML 2.0 / OIDC)
- S3-compatible document storage
- HSM (per-tenant signing keys)

**Hard regulatory dependencies:**

- RBI / FIU-India compliance posture in MVP
- DPDP Act data handling
- Pluggable jurisdiction interface (even if only India is populated)

### Cross-Cutting Concerns

These will appear in nearly every component decision and require architectural primitives, not feature-by-feature treatment:

1. **Tenant scoping** — `tenant_id` enforced at API gateway, agent contracts, every datastore query, every observability emission. `TenantScopeError` on omission.
2. **Provenance + signing pipeline** — every datum carries source + confidence; every agent action and officer decision is signed and ledgered.
3. **Pluggability via contract conformance** — every external vendor sits behind a Pydantic interface validated by an automated conformance suite; second reference adapter ships per integration.
4. **Real-time agent state streaming** — agent activity feed, agent-face state changes, risk-score auto-recalc all need a low-latency push channel that respects tenant isolation.
5. **Failure isolation** — agent failure ≤ one case; vendor outage blocks (never returns stale data); ledger write atomicity.
6. **LLM prompt safety** — version-controlled templates (Jinja or equivalent); document-derived text treated as data not instructions; PII-minimization layer before any LLM/telemetry boundary.
7. **Keyboard + screen-reader concurrency** — designed day one across every component, not retrofit.
8. **Observability with PII discipline** — OpenTelemetry + Orchestrate trace export, scrubbed at the collection layer, partitioned per tenant.

### Open Architectural Decisions Inherited from Planning

Per the product brief / distillate, six decisions arrive unresolved:

1. **Screening vendor selection** — ComplyAdvantage / LSEG / Dow Jones / ABBYY (Risk Reg: pick one with strong sandbox)
2. **Document AI stack** — IBM Document AI / Watson Discovery / custom (affects extraction precision NFR-T5 ≥ 95%)
3. **HITL UX model** — blocking agent graph vs async notifications (affects Decision Zone flow + agent execution model)
4. **Jurisdictional scope** — India-only with pluggable interface (recommended); validate plug works
5. **Agent memory model** — per-agent episodic vs shared case-state (recommended: shared, stateless-functional agents)
6. **Frontend choice** — **resolved by PRD: React + FastAPI** (Streamlit considered and declined)

These will be revisited as the workflow progresses; some will be settled in upcoming steps, others may surface in the technology-stack and component design steps.

## Starter Template Evaluation

### Primary Technology Domain

Polyglot full-stack agentic platform: Python (agent runtime + API + verifier) + TypeScript (frontend). No single-language starter covers the scope; composition from canonical primitives is required.

### Starter Options Considered

**Option A — Community Vite + shadcn/ui boilerplate** (e.g., `doinel1a/vite-react-ts-shadcn-ui`, `hayyi2/react-shadcn-starter`).
*Rejected:* Bakes in inherited opinions (Husky, React Hook Form, pre-copied components) that dilute the shadcn/ui ownership philosophy and Path B's "every decision motivated" requirement (NFR-RI2). Faster start, weaker reference implementation.

**Option B — IBM Orchestrate ADK example repos** (e.g., `IBM/orchestrate-adk-agent`).
*Useful as reference, not as scaffold:* Demonstrates ADK patterns (Salesforce + Tavily MCP integration) but is single-app and external-integration-shaped. Will study for ADK conventions; will not fork as our base.

**Option C — Polyglot monorepo scaffolded from canonical primitives** (Vite + ADK CLI + FastAPI hand-scaffold). **Selected.**

### Selected Starter: Polyglot monorepo, scaffolded from canonical primitives

**Rationale for selection:**

1. **No community boilerplate spans Python ADK + FastAPI + React** — composition is unavoidable.
2. **shadcn/ui ownership philosophy is undermined** by pre-copied components in third-party templates (UX §1.1).
3. **Path B (reference implementation) requires every architectural decision to be motivated** — NFR-RI2 ADR discipline weakens when inheriting a community starter's opinions.
4. **NFR-RI5 (clone-to-demo ≤ 30 min)** is achievable with canonical CLIs + a clean Makefile; community starters often add layers a new dev has to peel back.

### Repository Layout

```
ibm_orchestrate_platform/
├── apps/
│   ├── cockpit-ui/      # React 19 + Vite 7 + TS strict + Tailwind 4 + shadcn/ui + Radix + Framer Motion + react-flow + Lucide
│   ├── cockpit-api/     # FastAPI 0.115+ + Pydantic 2.7+ + SQLAlchemy 2.0 (async) + asyncpg + Alembic
│   └── agents/          # IBM watsonx Orchestrate ADK (Python 3.11+) — agents (YAML) + tools (Python) + Pydantic contracts
├── packages/
│   └── contracts/       # Source-of-truth Pydantic schemas; TS types generated from JSON Schema export
├── tools/
│   └── verifier/        # Standalone offline ledger verifier (≤ 300 LOC Python, minimal deps)
├── infra/               # IaC (Terraform/Pulumi — TBD in step-4) + tenant-onboarding runbooks
└── _bmad/               # BMAD planning artifacts
```

### Initialization Commands

Each app scaffolded from its canonical entry point. Run in order; this should be the first implementation story.

```bash
# 1. Frontend — apps/cockpit-ui
npm create vite@latest apps/cockpit-ui -- --template react-ts
cd apps/cockpit-ui && npx shadcn@latest init   # interactive: pick style/base color
npm i @radix-ui/react-* framer-motion lucide-react reactflow tailwindcss postcss autoprefixer

# 2. Agents (IBM watsonx Orchestrate ADK)
cd apps/agents
poetry init -n --python "^3.11"
poetry add ibm-watsonx-orchestrate
poetry run orchestrate init                     # scaffolds ADK project layout

# 3. API
cd apps/cockpit-api
poetry init -n --python "^3.11"
poetry add "fastapi[all]" "sqlalchemy[asyncio]" pydantic asyncpg alembic
poetry add --editable ../../packages/contracts  # path-dep to shared contracts

# 4. Shared contracts
cd packages/contracts
poetry init -n --python "^3.11"
poetry add pydantic

# 5. Offline ledger verifier (deliberately minimal)
cd tools/verifier
poetry init -n --python "^3.11"
poetry add cryptography pydantic
```

### Architectural Decisions Provided by This Scaffold

**Language & runtime:**
- Python 3.11+ (ADK + API + verifier + contracts)
- Node 20+ (cockpit-ui dev tooling); React 19 + TS strict (cockpit-ui runtime)

**Styling solution:**
- Tailwind CSS 4 + shadcn/ui (copy-into-repo, owned by us, not a packaged dep)
- Radix UI primitives (unstyled, WCAG 2.1 AA-compliant behaviors)
- Framer Motion for the three motion flavors (expand / focus-dim / slide-out)
- Lucide React for icons (clean variable-weight geometric set)
- react-flow for the UBO Canvas force-directed graph

**Build tooling:**
- Vite 7 with SWC for the frontend (fast HMR, ES modules, TS-native)
- Standard Python venvs managed by Poetry; no bundler on Python side
- Build artifacts: cockpit-ui → static SPA; cockpit-api → uvicorn process; agents → Orchestrate-deployed YAML/Python

**Testing framework:**
- pytest (Python apps) with async support; ≥ 80% coverage on agent logic + tool adapters (NFR-RI4)
- Vitest + React Testing Library (cockpit-ui)
- Playwright for canonical end-to-end flows (the four cockpit journeys)
- Contract-conformance test suite for vendor adapters (NFR-RI6)

**Code organization:**
- Monorepo with `apps/` (deployable units) + `packages/` (shared) + `tools/` (standalone utilities)
- Module-functionality layout inside FastAPI (per `zhanymkanov/fastapi-best-practices` reference)
- shadcn/ui components in `apps/cockpit-ui/components/ui/*` (owned, not imported)
- Bespoke cockpit components in `apps/cockpit-ui/components/cockpit/*`

**Workspace tooling:**
- **Poetry** per Python app/package; shared code via path dependencies (`packages/contracts` consumed by `apps/cockpit-api` and `apps/agents`)
- **pnpm workspaces** for JS/TS (single `pnpm-lock.yaml` for cockpit-ui)
- Root **Makefile** orchestrates `poetry install`, `pnpm install`, lint, test, and `make dev` (full-stack local bring-up)
- Each Python project carries its own `poetry.lock`; cross-project version consistency on shared libs (Pydantic, etc.) enforced by a `make sync-versions` discipline

**Quality gates:**
- Ruff (linting) + mypy strict (typing) on Python
- ESLint + tsc strict + Prettier on TypeScript
- `pre-commit` framework (language-agnostic; not Husky) running ruff/mypy/eslint on staged files

**Development experience:**
- ADK Developer Edition for local agent runtime (self-contained Orchestrate copy)
- FastAPI hot reload via `uvicorn --reload`
- Vite HMR for cockpit-ui
- One-command `make dev` brings up the full stack: agents (Developer Edition) + cockpit-api + cockpit-ui

**Note:** Project initialization with these commands should be the first implementation story. The Makefile + monorepo wiring (Poetry path-deps, pnpm workspace config, pre-commit hooks) is the second.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (block implementation):** D1, D2, D3, D6, S1, S6, A2, A3, F1, F13, I1, I2, I13.
**Important Decisions (shape the architecture):** D5, D8, D9, S3, S4, S5, S7, A1, A4, A7, A10, F2, F3, F4, F5, F7, I5, I6, I7, I9, I11.
**Nice-to-Have / Routine:** D4, D10, S2, S8, S9, S10, A5, A6, A8, A9, F6, F8, F9, F10, F11, F12, I3, I4, I8, I10, I12, I14.

**Deferred to Step 5 (Architecture Patterns) or Step 6 (Project Structure):**

- **Screening vendor selection** (ComplyAdvantage / LSEG World-Check / Dow Jones / ABBYY) — pluggable adapter contract is locked; vendor pick is a procurement/sandbox-availability call that doesn't change the architecture.
- **Document AI stack** (IBM Document AI / Watson Discovery / custom ML) — depends on extraction-precision benchmarks (NFR-T5 ≥ 95%); pluggable adapter contract is locked.
- **Agent memory model** (per-agent episodic vs shared case-state) — to be settled in Step 5 alongside the Orchestrate composition pattern.

### Data Architecture

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | Primary OLTP database | **PostgreSQL 16+** | Universal, mature SQLAlchemy/asyncpg ergonomics, supports per-tenant schema isolation; chosen over Db2 for evaluator developer ergonomics (Path B). |
| D2 | Tenant data isolation | **Separate Postgres schema per tenant** within shared cluster (MVP); separate cluster for high-touch on-prem | Strong logical isolation with operational simplicity; matches PRD §B2B SaaS guidance. |
| D3 | Async DB driver | **asyncpg + SQLAlchemy 2.0 async** | 2026-canonical FastAPI stack; sub-ms latencies. |
| D4 | Migrations | **Alembic** | Bundled with FastAPI scaffold; one migration tree per tenant schema, applied via tenant-onboarding runbook. |
| D5 | Document storage | **S3-compatible API behind `DocumentStore` interface**; IBM Cloud Object Storage default, AWS S3 / MinIO alternates | Universal contract; swap is one adapter file (NFR-RI6). |
| D6 | Cryptographic ledger storage | **Same Postgres cluster, separate `ledger` schema, INSERT-only role, DB triggers blocking UPDATE/DELETE, application-level Ed25519 hash chain** | Cryptographic guarantee lives in the hash chain and signatures, not the storage substrate; specialized immutable DBs (immudb, QLDB) add ops surface without strengthening the math. Offline verifier reads JSON exports. |
| D7 | Vector store / RAG | **Deferred to Future** | No MVP feature requires semantic search; Document Intelligence is field extraction, Risk Scoring is decomposition. Add pgvector when adverse-media or pKYC lands. |
| D8 | Cache / in-memory state | **Redis** (single instance, MVP) | Used for rate limiting, session store, SSE connection registry, Arq job queue. One service covers four cross-cutting needs. |
| D9 | Background job queue | **Arq** (Redis-backed, async-native, lightweight) | FastAPI-native; ledger-write durability across process restarts; Celery is overkill at MVP scale. |
| D10 | Data retention | **Application-level retention service**; everything hot in Postgres in MVP; cold-storage tiering deferred to Future. Schema includes `closure_date` so future tiering needs no migration. | PMLA mandates 5y, RBI implies 10y; tiering is unnecessary complexity at MVP volume. |

### Authentication & Security

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| S1 | HSM / key management | **IBM Cloud Hyper Protect Crypto Services** (cloud); **HashiCorp Vault Transit** (on-prem/dev); single `KeyVault` interface | HPCS is FIPS 140-2 Level 4 (highest tier); Path B alignment; Vault Transit is the simplest dev/on-prem fallback. |
| S2 | Secrets management | **IBM Cloud Secrets Manager** (cloud); **HashiCorp Vault** (on-prem/dev); single `SecretsClient` interface | Mirrors S1 adapter pattern. |
| S3 | Identity broker | **Direct OIDC via `authlib`** in FastAPI; SAML via `python3-saml` if a tenant requires it. **No Keycloak/Authentik proxy.** | Banks bring their own IdP; we are a relying party, not an IdP. |
| S4 | API session model | **HttpOnly secure cookie session**, server-side state in Redis. **No JWTs.** | Cookies are simpler, revocable; no microservice fan-out that needs JWT statelessness. |
| S5 | RBAC policy engine | **Hand-rolled FastAPI dependency** (`require_role(role, resource)`) over typed permission matrix in code. **No OPA/Casbin.** | Matrix is small (6 roles × ~15 resources); auditable, unit-testable, no policy server. |
| S6 | Officer-decision signing | **App-managed Ed25519 keypair per officer**, generated at first login; private key encrypted at rest with tenant HSM master key; officer signs in-browser via WebCrypto; server verifies against stored public key. | Avoids per-officer HSM provisioning; WebAuthn/passkeys deferred to post-pilot when bank IdP integration friction is understood. Path B win — visible WebCrypto usage rare in compliance tools. |
| S7 | LLM prompt injection defense | Three layers: (a) document-derived text typed as Pydantic data, never templated as instructions; (b) Jinja templates with strict variable escaping; (c) agent outputs validated against Pydantic schemas. **No vendor lib (Lakera, Rebuff) in MVP.** | Schema discipline does the work. Vendor add-ons can come later. |
| S8 | LLM provider keys | **Live in Orchestrate runtime config**, not in our codebase | One fewer secret category to own. |
| S9 | TLS termination | **At cloud load balancer / ingress**, not in uvicorn | Cloud-managed certs with auto-rotation. |
| S10 | CSRF | **`SameSite=Strict` cookies + per-mutation CSRF token** on state-changing endpoints | Standard; boring is correct. |

### API & Communication Patterns

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| A1 | API style + versioning | **REST + JSON** with `/t/{tenant_id}/v1/...` path-prefix versioning. **No GraphQL, no gRPC** for the public API. | Banks' integration teams expect REST; path-prefix versioning is explicit. |
| A2 | Real-time channel | **Server-Sent Events (SSE)** over HTTP/2; one stream per case open. **No WebSocket.** | Agent state is one-way (server → client); SSE is the boring 2026 pick — standard HTTP, native `EventSource`, auto-reconnect, plays with cookie auth. |
| A3 | cockpit-api ↔ agents inter-service | **In-process function call in MVP**; cockpit-api imports agents package and invokes Orchestrate runtime locally. Service split is deployment-time, not code-time. | At MVP scale we don't need a network hop; if scale demands later, extract behind a Pydantic-typed RPC interface (already shaped right). |
| A4 | API documentation | **OpenAPI 3.1 auto-generated by FastAPI**; **Scalar** for human-readable UI; spec exported as build artifact for bank integration teams | Free with FastAPI; Scalar is the modern reader. |
| A5 | Error format | **RFC 7807 Problem Details** (`application/problem+json`) | Standard, machine-parseable, recognizable to bank integration teams. |
| A6 | Pagination | **Cursor-based** for case lists; offset only on stable aggregate dashboards | Cursor is correct for append-heavy data; offsets break under concurrent writes. |
| A7 | Webhook delivery | **At-least-once with exponential backoff** (1s→5s→25s→125s, give-up at 1h); **HMAC-SHA256 signed payloads**; idempotency-key header for consumer-side dedupe | Banks expect HMAC signing; at-least-once + idempotency-key is the canonical contract. |
| A8 | API gateway | **None in MVP**; FastAPI behind cloud load balancer; rate limiting in middleware (Redis-backed) | Adding Kong/Tyk is a service to operate without buying us much at MVP scale. |
| A9 | Service-to-service auth | **HMAC signed payloads**; **mTLS optional** if tenant requires (config-driven) | Most banks accept HMAC; mTLS is config-driven nice-to-have. |
| A10 | OpenAPI ↔ TS contract drift prevention | **Pydantic models source of truth → OpenAPI → JSON Schema → TS types via `openapi-typescript`**; one contract, three representations | Path B win — evaluators see typed contracts flow into TS automatically; no hand-written DTOs. Regenerated via `make contracts`. |

### Frontend Architecture

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| F1 | Server state | **TanStack Query v6** | 2026 standard; cache, dedupe, invalidation, retry out of box; SSE events from A2 call `queryClient.invalidateQueries` to refresh. |
| F2 | Client UI state | **Zustand** for global UI state; `useState` for purely local. **No Redux. No Context for fast-changing state.** | Zustand + TanStack Query covers 95% of real apps in 2026; Context churns on every value change and would torch our 50ms keyboard budget. |
| F3 | Routing | **TanStack Router** (file-based, type-safe, integrates with TanStack Query) | Type-safe routes match TS-strict discipline; few cockpit routes total. |
| F4 | Form handling | **None.** `useState` for input surfaces (Decision Zone editor, Undo modal, drag-correct labels). | UX §2.1: "Intake has already happened. The case is never a blank form." Form library would be ceremony. |
| F5 | Rich-text editor (Decision Zone) | **Tiptap** (ProseMirror-based) | Headless, extensible, works with React 19; light formatting (paragraphs, citation tokens). |
| F6 | Code splitting | **Route-based via TanStack Router** + manual `lazy()` for heavy components (UBO Canvas, Tiptap, react-flow) | Initial bundle ≤ 250 KB gzipped; heavy components load on demand. |
| F7 | Design tokens | **Tailwind 4 `@theme`** as single source of truth; consumed in JS via `theme(...)` for Framer Motion variants and chart colors. **No CSS-in-JS runtime.** | Tailwind's enforcement model: tokens-only, deviations show in diffs. |
| F8 | Accessibility tooling | **`eslint-plugin-jsx-a11y`** + **`axe-core` in Playwright e2e** + manual NVDA/VoiceOver passes per MVP journey | Three boring layers: lint-time, runtime, user-tier. |
| F9 | i18n scaffolding | **`react-i18next`** with English-only catalog at MVP; locale-aware date/number via `Intl.*` | NFR-AC6 mandates externalized strings from day one for future Hindi + regional Indian languages. |
| F10 | Storybook | **Skip in MVP**; inline TS doc comments + e2e snapshots cover the docs need | Path B benefits from one fewer build pipeline. Add later if design surface grows. |
| F11 | Visual regression | **Playwright screenshot diffs** on canonical flows + key components | Built into Playwright; no Chromatic/Percy add-on. |
| F12 | Error boundaries / suspense | **Per-route error boundary**; `<Suspense>` with skeleton fallback only on heavy lazy panels | Boring React 19 idiom. |
| F13 | OpenAPI → TS types | **`openapi-typescript` + `openapi-fetch`** as typed thin client | Zero hand-written API code in cockpit-ui; types regenerate from `make contracts`; tsc errors at refactor sites. |

**Cockpit-ui internal layout** (carried into Step 6):

```
apps/cockpit-ui/src/
├── routes/                # TanStack Router file-based routes
├── components/
│   ├── ui/                # shadcn/ui copies (owned)
│   └── cockpit/           # AgentFace, ConfidencePill, ReasoningTrace, DecisionZone, UBOCanvas, ...
├── stores/                # Zustand stores (mode, palette, focus)
├── lib/
│   ├── api.ts             # openapi-fetch typed client
│   ├── sse.ts             # EventSource wrapper → invalidates queries
│   └── crypto.ts          # WebCrypto Ed25519 sign for officer commits
├── hooks/                 # useCase, useAgentState, useKeyboardShortcuts
├── styles/                # tokens.css, base.css
└── api-types.ts           # generated, do not edit
```

### Infrastructure & Deployment

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| I1 | Reference cloud | **IBM Cloud** for canonical demo deployment; portable to AWS / Azure / on-prem via the adapter layers (S1, S2, D5) | Path B all-IBM showcase credibility; pluggable interfaces mean it's not lock-in. |
| I2 | Compute platform | **Single VM (or two for HA) running Docker Compose** in MVP; migration path to **IBM Cloud Code Engine** or **OpenShift** post-MVP. **No Kubernetes in MVP.** | At 10-analyst pilot scale, K8s is operational overkill; Compose + restart-policies meets 99.5% pilot SLO; "we ship this on a VM" reads better for Path B than "you need a K8s cluster." Architecture is K8s-ready. |
| I3 | Container build | **Multi-stage Dockerfiles**, one per app: `cockpit-ui`, `cockpit-api+agents` (combined per A3), `verifier`. Built via `docker buildx`. | Boring; no Buildah/Buildpacks novelty. |
| I4 | Container registry | **IBM Cloud Container Registry** (cloud); Docker Hub mirror for the public reference image | Tenant-scoped pulls; private by default. |
| I5 | IaC | **Terraform** with IBM Cloud provider; modules for tenant VPC, Postgres, COS bucket, HPCS, Secrets Manager, VM/Code Engine, DNS | Universal default; same `.tf` runs against AWS/Azure providers. |
| I6 | CI/CD | **GitHub Actions**: build/test/lint/contract-conformance/security-scan; container push; Terraform plan-on-PR + apply-on-merge to staging; manual gate to prod | Universal default; banks expect SAST/DAST integrations. |
| I7 | Observability stack | **Grafana + Tempo (traces) + Loki (logs) + Mimir (metrics)** as open-source backbone; **IBM Instana** as optional commercial enhancement per tenant | OTel-native; 2026-canonical open-source stack. |
| I8 | Error tracking | **Sentry self-hosted** (in single-tenant deployments to keep PII inside residency boundary); Sentry-cloud only after PII-scrubbing pipeline verified | Self-hosted respects DPDP residency. |
| I9 | Environments | **Three: `dev` (per developer, local Compose), `staging` (shared cluster on IBM Cloud), `prod` (per-tenant VPC)** | Maps to PRD's tenant-per-deployment model; staging shared to keep cost down. |
| I10 | CI secrets | **OIDC-federated** GitHub Actions ↔ IBM Cloud IAM (no long-lived cloud creds in repo); per-environment scoped roles | 2026 norm; eliminates a class of leak. |
| I11 | DR | **Daily Postgres logical backups + 15-min PITR**; S3 cross-region replication; ledger snapshots hourly; recovery runbook tested quarterly | Meets RPO ≤ 1h, RTO ≤ 4h. |
| I12 | CDN | **IBM Cloud CDN** in front of cockpit-ui static bucket; Cloudflare as multi-cloud option | Static assets cached at edge; API calls go straight to origin. |
| I13 | Local dev | **`docker compose up`** brings up Postgres + Redis + LocalStack (S3) + Vault Transit (HSM) + ADK Developer Edition + cockpit-api + cockpit-ui. **Sub-30-min clone-to-demo.** | Directly serves NFR-RI5; the most important DX investment. |
| I14 | Telemetry PII scrubbing | **OTel collector with attribute-redaction processor** at egress; redaction rules versioned in repo; CI test asserts no PII patterns leak | NFR-O3 requires; OTel collector handles natively. |

### Decision Impact Analysis

**Implementation sequence (decisions an engineer encounters in order):**

1. **Project init** (Step 3 commands) — establishes the repo skeleton.
2. **D1–D4 + I13** — Postgres + Redis + Compose locally. Smallest path to "I can run something."
3. **S1 + S2 + S6 + D6** — KeyVault adapter + ledger schema + Ed25519 chain. Without these, no audit-compliant write path.
4. **A1 + A4 + A10 + S3 + S4** — REST endpoints, OpenAPI export, OIDC, cookie session. The minimum viable API surface.
5. **A2 + F1 + F2 + F3 + F13** — SSE channel + frontend state + typed client. The cockpit comes alive.
6. **A3** — Orchestrate ADK agents in-process; first agent wired up (likely Document Intelligence as the simplest entry point).
7. **All remaining decisions** — operational hardening, observability, DR, CI/CD.

**Cross-component dependencies:**

- **Tenant scoping** (D2 + S1 + S2 + I9) is the most cross-cutting concern; every adapter, query, and signing operation must accept and validate `tenant_id`.
- **Pluggable adapters** (D5 + S1 + S2 + I7) all share the same shape: typed interface + reference impl + alternate impl + conformance suite. This is the Step 5 (Patterns) "Pluggable Adapter" pattern.
- **Real-time path** (A2 + F1 + D8) — SSE writes to Redis-backed connection registry; agent state changes publish to Redis; SSE handler subscribes; TanStack Query receives event and invalidates. Three components, one flow.
- **Audit path** (D6 + S1 + S6 + A7) — every officer commit (FR29) AND webhook dispatch (A7) writes a signed entry to the ledger. The HMAC for outbound webhooks is keyed by the same tenant HSM master that signs ledger entries.
- **Path B story** (NFR-RI1–7) is reinforced primarily by: A10 (Pydantic→OpenAPI→TS), S6 (visible WebCrypto), I2 (VM+Compose), I13 (one-command local). These are the four "I didn't know Orchestrate could do this" surface area decisions.

## Implementation Patterns & Consistency Rules

### Conflict Surface Area

~25 generic conflict points (naming, structure, format, communication, process) plus 8 project-specific patterns unique to this codebase (Pluggable Adapter, Tenant Scoping, Provenance, Agent Action, Officer Signing, SSE Event, Confidence Banding, Counterfactual Reasoning Trace). All resolved below; CI lints + conformance tests enforce.

### Naming Patterns

| Domain | Convention | Example |
|---|---|---|
| Python (vars/funcs/files) | `snake_case` (Ruff-enforced) | `case_supervisor.py`, `def commit_decision(...)` |
| Python classes | `PascalCase` | `class CaseSupervisor:` |
| TS variables/functions | `camelCase` | `const caseId`, `function openCase()` |
| TS components/types | `PascalCase` | `<DecisionZone />`, `type CaseId = string` |
| TS files (components) | `PascalCase.tsx` | `DecisionZone.tsx`, `AgentFace.tsx` |
| TS files (hooks/lib) | `camelCase.ts` | `useCase.ts`, `sse.ts` |
| Postgres tables | `snake_case`, **plural** | `cases`, `agent_actions`, `ledger_entries` |
| Postgres columns | `snake_case` | `tenant_id`, `created_at`, `agent_id` |
| Postgres FKs | `<referenced_singular>_id` | `case_id`, `tenant_id` |
| Postgres indexes | `ix_<table>_<columns>` | `ix_cases_tenant_id_state` |
| API routes | **kebab-case** path segments, **plural** resource names | `/t/{tenant_id}/v1/cases/{case_id}/reasoning-traces/{trace_id}` |
| API path params | `{snake_case}` | `{tenant_id}`, `{case_id}` |
| API query params | `snake_case` | `?after=<cursor>&limit=50&risk_band=high` |
| HTTP headers | `Pascal-Kebab-Case` (HTTP norm) + `X-Cockpit-` prefix for custom | `X-Cockpit-Idempotency-Key`, `X-Cockpit-Tenant-Id` |
| JSON fields (over the wire) | **`snake_case`** | `{ "case_id": "...", "tenant_id": "...", "risk_score": 62 }` |

> **Rationale for `snake_case` JSON over the wire:** Pydantic models are the source of truth (Python conventions match); `openapi-typescript` preserves property names without transformation; no `humps`/`camelize` translation layer to maintain. Cockpit-ui works directly with `snake_case` field names.

### Identifier Formats

| Identifier | Format | Example |
|---|---|---|
| Tenant ID | UUID v4 | `4f4a8c1e-...-9b2d` |
| Case ID | `case_<ULID>` | `case_01HXY3Q9KW4VPQF2ZT8C7M5R3N` |
| Agent action ID | `aa_<ULID>` | `aa_01HXY3...` |
| Ledger entry ID | `led_<ULID>` | `led_01HXY3...` |
| Officer ID | `usr_<ULID>` (cockpit-internal); bank IdP `sub` claim mapped at first login | `usr_01HXY3...` |
| Document ID | `doc_<ULID>` + SHA-256 hash separately stored | `doc_01HXY3...` |
| Webhook delivery ID | `whd_<ULID>` (used as idempotency key) | `whd_01HXY3...` |

ULID over UUID v7 for cockpit-internal IDs: sortable for cursor pagination, Crockford-Base32 (URL-safe), prefix-tagged for log/ledger debuggability. UUID v4 stays only for `tenant_id` — externally-provisioned, structurally inscrutable by design.

### Structural Patterns

```
Tests (Python):       tests/<module>/test_<thing>.py    (pytest convention, separate dir)
Tests (TS):           Component.test.tsx                (co-located)
Test fixtures:        apps/<app>/tests/fixtures/        (Python) or tests/fixtures/ (TS)
ADRs:                 docs/adr/NNNN-<kebab-title>.md    (sequential, never reused)
Migrations:           apps/cockpit-api/migrations/versions/<rev>_<desc>.py  (Alembic)
OpenAPI export:       packages/contracts/openapi.json   (build artifact, committed)
Generated TS types:   apps/cockpit-ui/src/api-types.ts  (header: "// @generated, do not edit")
Pydantic schemas:     packages/contracts/<domain>.py    (single source — never duplicated in apps)
shadcn/ui components: apps/cockpit-ui/src/components/ui/* (owned, manually edited)
Bespoke cockpit:      apps/cockpit-ui/src/components/cockpit/<Component>/{index.tsx, *.test.tsx}
```

### Format Patterns

| Concern | Convention |
|---|---|
| Success response | Direct payload, **no envelope** (no `{data: ...}` wrapper). Stripe-style. |
| Error response | RFC 7807 (locked at A5): `{"type": "...", "title": "...", "status": 400, "detail": "...", "instance": "...", "tenant_id": "...", "request_id": "..."}` |
| Date/time | ISO 8601 with explicit `Z`: `"2026-04-27T12:34:56Z"`. Never Unix epoch over the wire. |
| Booleans | `true`/`false` only, never `1`/`0` |
| Currency | Never floats. **String decimal** with explicit currency code: `{"amount": "1500000.00", "currency": "INR"}` |
| Pagination response | `{"items": [...], "next_cursor": "<opaque>", "has_more": true}` |
| Empty list | `[]`, never `null` |
| Optional field | Omit if absent (don't emit `null`); `Optional[T] = None` Pydantic side |

### Project-Specific Patterns

#### **P1 — Pluggable Adapter Pattern** *(D5 doc store, S1 KeyVault, S2 SecretsClient, screening vendor, doc AI stack, future jurisdiction packs)*

```python
# packages/contracts/screening.py
class ScreeningHit(BaseModel): ...
class ScreeningRequest(BaseModel): ...

class ScreeningAdapter(Protocol):
    """All screening vendors implement this. Conformance suite verifies."""
    async def screen(self, req: ScreeningRequest, *, tenant_id: TenantId) -> list[ScreeningHit]: ...

# apps/agents/adapters/screening_complyadvantage.py
class ComplyAdvantageAdapter(ScreeningAdapter): ...

# apps/agents/adapters/screening_mock.py  ← conformance pair (NFR-RI6)
class MockScreeningAdapter(ScreeningAdapter): ...
```

**Rule:** Every adapter ships with a second reference implementation (mock or alternative vendor). Conformance test suite runs the same `tests/contract/screening_contract.py` against every implementation. Adding a third vendor is one file + zero changes to agent code.

#### **P2 — Tenant Scoping Pattern** *(cross-cutting)*

```python
class CaseRequest(BaseModel):
    tenant_id: TenantId  # required, validated against session
    ...

async def fetch_case(case_id: CaseId, *, tenant_id: TenantId) -> Case:
    case = await session.execute(select(Case).where(Case.id == case_id, Case.tenant_id == tenant_id))
    if case is None: raise TenantScopeError(...)  # or NotFound — never leak existence
```

**Rule:** `tenant_id` is the first non-self keyword-only argument on every function that touches data. CI lint check (custom Ruff rule) flags any data-access function lacking it. `TenantScopeError` is logged as a security event (NFR-O6).

#### **P3 — Provenance Metadata Pattern** *(every datum rendered in the cockpit)*

```python
class Provenance(BaseModel):
    source_agent: AgentId
    source_system: str              # "MCA", "GST", "ComplyAdvantage", "officer_input"
    confidence: float               # [0.0, 1.0]
    confidence_band: ConfidenceBand # derived: low / medium_low / medium_high / high
    evidence_ids: list[EvidenceId]  # ledger refs that back this datum
    captured_at: datetime

class ProvenancedField[T](BaseModel):
    value: T
    provenance: Provenance
```

**Rule:** NFR-T4 mandates 100% coverage. Every UI-rendered datum is `ProvenancedField[T]`, not raw `T`. CI test asserts: any `<TextField>`/`<Pill>` etc. in cockpit-ui receives a `provenance` prop.

#### **P4 — Agent Action Pattern** *(every agent invocation)*

```python
class AgentActionLedgerEntry(BaseModel):
    id: AgentActionId          # aa_<ULID>
    tenant_id: TenantId
    case_id: CaseId
    agent_id: AgentId
    model_id: str
    prompt_template_id: str    # version-controlled template ref
    prompt_hash: Sha256Hex     # hash of rendered prompt + inputs
    tool_calls: list[ToolInvocation]
    input: dict                # Pydantic-validated input
    output: dict               # Pydantic-validated output
    started_at: datetime
    completed_at: datetime
    platform_signature: Ed25519Signature  # tenant-key-signed
    prev_hash: Sha256Hex       # hash chain
    chain_hash: Sha256Hex      # this entry's hash
```

**Rule:** Agents never return data without a ledger entry written first. Supervisor pattern enforces via decorator wrap; new agents follow this template — there is no other way to write an agent.

#### **P5 — Officer Action Pattern** *(every officer commit)*

Officer commits flow: **(client-side WebCrypto Ed25519 sign over canonical JSON) → (server verifies against stored public key) → (ledger entry)**. Tampering breaks the signature and the chain. The signed payload includes `case_id`, `decision`, `rationale_hash`, `timestamp`, `nonce`.

#### **P6 — SSE Event Pattern** *(real-time channel — A2)*

SSE events carry **minimal payloads — IDs only**. Clients invalidate TanStack Query cache and refetch:

```
event: agent.state_changed
data: {"agent_id": "screening", "state": "complete", "case_id": "case_01HXY..."}

event: case.risk_recalculated
data: {"case_id": "case_01HXY..."}
```

Event names: `<domain>.<past_tense_verb>` — dot-delimited, snake_case, past-tense. **No event payload may exceed 256 bytes.** Fat data lives behind the REST endpoint that the client refetches.

#### **P7 — Confidence Banding Pattern**

Internal: float `[0.0, 1.0]`. Display: 4-tier banded enum derived at the boundary:

```python
def to_band(c: float) -> ConfidenceBand:
    if c >= 0.85: return ConfidenceBand.HIGH
    if c >= 0.65: return ConfidenceBand.MEDIUM_HIGH
    if c >= 0.40: return ConfidenceBand.MEDIUM_LOW
    return ConfidenceBand.LOW
```

Thresholds calibrated per agent during pre-pilot validation (PRD Innovation Risk Mitigation). UI renders bands via shape + position + label (NFR-AC3).

#### **P8 — Counterfactual Reasoning Trace Pattern**

```python
class ReasoningTrace(BaseModel):
    what_searched: str
    what_hit: str
    confidence_self_rating: ConfidenceWithRationale
    counterfactual: str   # "Upgrade to high if DOB matches. Downgrade if address+photo confirm different person."
```

**Rule:** No agent reasoning trace ships without all four fields populated. Empty-string is a CI test failure. Forces every agent author to commit to the evidentiary boundary of the conclusion (Innovation #2 in PRD).

### Resolution of Deferred Decisions

- **Agent memory model** (deferred from Step 4): **Shared case-state with stateless-functional agents** — every agent reads from and writes to a single `Case` Pydantic aggregate scoped to `tenant_id` + `case_id`. Agents are pure functions of `(case_state, agent_input) → (agent_output, ledger_entry)`. No per-agent episodic memory. Why: simpler, more auditable, fits the Agent Action Pattern (P4), avoids cross-agent state-sync bugs, matches Orchestrate's collaborator composition. Aligns with the recommendation in the product brief distillate.
- **Screening vendor selection** (deferred): **Pick at procurement, not architecture.** The adapter contract (P1) makes this swappable in one file. Procurement recommendation: **ComplyAdvantage** as primary (PRD risk register's "strong sandbox" criterion); LSEG World-Check as fallback if larger banks demand it. Doc as ADR when procurement call is made.
- **Document AI stack** (deferred): **Pick at evaluation, not architecture.** Pluggable adapter (P1) means agent code stays the same. Recommended approach: 50-doc benchmark (NFR-T5: ≥ 95%) across IBM Document AI and Watson Discovery in parallel before locking; fall back to a custom OCR + entity-extraction pipeline if neither hits the floor.

### Communication Patterns

| Concern | Pattern |
|---|---|
| Logs | Structured JSON with required fields: `tenant_id`, `case_id` (where applicable), `agent_id` (where applicable), `actor`, `action`, `level`, `request_id`, `trace_id`, `timestamp` |
| Log levels | `DEBUG`, `INFO`, `WARN`, `ERROR`. Never `FATAL` (use `ERROR` + alert). |
| Trace propagation | OTel W3C `traceparent` at every HTTP boundary; `case_id` and `tenant_id` enriched as span attributes (PII-scrubbed at egress per I14) |
| Validation timing | At the boundary, never deeper. API in/out, agent in/out, tool in/out, ledger write — all Pydantic-validated. Internal calls assume valid types. |

### Process Patterns

| Concern | Pattern |
|---|---|
| Loading state | TanStack Query's `isPending` / `isFetching` only. Never custom flags. Never `loading: true` in Zustand. |
| Optimistic updates | Only on triage actions (`x` defer, `d` done). Never on commits. Decisions are sacred. |
| Retry | Exponential backoff with jitter (1s → 5s → 25s → 125s) on transient failures (5xx, network); never retry 4xx; idempotency-key required for any retried write |
| Error surfacing | Three channels: (1) inline next to failing element (most), (2) toast for cross-cutting (auth expired, vendor-down), (3) full-page error boundary for catastrophic. Never silent failure (NFR-A7). |
| Validation errors → user | RFC 7807 `detail` shown directly; `type` links to docs page if recoverable |
| Authentication failure | OIDC re-auth flow always returns user to the exact route they were on |

### Enforcement Guidelines

**All AI agents (and humans) MUST:**

1. Never duplicate a Pydantic schema. Schemas live in `packages/contracts/` only. Apps import.
2. Never write a data-access function without `tenant_id` as a keyword-only argument. CI lints for this.
3. Never write an agent without going through the Agent Action decorator (P4 ledger entry).
4. Never render a datum in the cockpit without `ProvenancedField[T]` (P3). CI test asserts.
5. Never emit an SSE payload over 256 bytes (P6).
6. Never compose a prompt by string concatenation. Use Jinja templates from `apps/agents/prompts/`.
7. Never log raw customer PII. PII fields scrubbed at OTel collector (I14); structured loggers strip them at source as defense-in-depth.
8. Every adapter ships with a second reference implementation. Conformance suite passes before merge.

**Pattern violations surface in three places:** Ruff/ESLint custom rules (lint-time) → contract conformance suite (CI) → architecture review checklist (PR template).

### Anti-Patterns to Refuse

- ❌ `camelCase` JSON over the wire (we picked `snake_case`)
- ❌ Pydantic schemas duplicated in apps (must import from `packages/contracts/`)
- ❌ Adapter without conformance pair (NFR-RI6)
- ❌ Agent that returns data without writing a ledger entry
- ❌ UI datum rendered without `ProvenancedField`
- ❌ Loading flag in Zustand (use TanStack Query)
- ❌ Retry of a non-idempotent write without idempotency key
- ❌ Stale data shown as fresh (NFR-A7 — surface block + reason instead)
- ❌ Silent agent failure (Case Supervisor must catch and flag — NFR-A5)
- ❌ Empty `counterfactual` field on a reasoning trace (P8)

## Project Structure & Boundaries

### Complete Project Tree

```
ibm_orchestrate_platform/
├── README.md                          # 30-min clone-to-demo (NFR-RI5)
├── Makefile                           # dev / test / lint / contracts / migrate / build
├── docker-compose.yml                 # local dev stack: postgres, redis, localstack, vault, ADK dev edition, api, ui
├── docker-compose.staging.yml         # mirrors prod topology for staging
├── pnpm-workspace.yaml                # JS workspace
├── .env.example                       # documented env vars; never .env in repo
├── .editorconfig
├── .gitignore
├── .pre-commit-config.yaml            # ruff, mypy, eslint, prettier on staged files
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                     # build, test, lint
│   │   ├── contracts.yml              # contract conformance + OpenAPI drift
│   │   ├── security-scan.yml          # Snyk/Dependabot, SAST
│   │   ├── visual-regression.yml      # Playwright screenshot diffs
│   │   └── deploy.yml                 # Terraform plan-on-PR / apply-on-merge
│   └── pull_request_template.md       # architecture review checklist
│
├── docs/
│   ├── README.md
│   ├── adr/                           # numbered ADRs (NFR-RI2)
│   │   ├── 0001-monorepo-poetry-pnpm.md
│   │   ├── 0002-postgres-over-db2.md
│   │   ├── 0003-sse-over-websocket.md
│   │   ├── 0004-snake-case-json-wire-format.md
│   │   ├── 0005-vm-compose-over-k8s-mvp.md
│   │   ├── 0006-pluggable-adapter-pattern.md
│   │   ├── 0007-shared-case-state-stateless-agents.md
│   │   ├── 0008-officer-app-managed-keypair.md
│   │   └── ...                        # one per non-trivial decision
│   ├── architecture/
│   │   ├── overview.md                # high-level diagram + key flows
│   │   ├── data-flow.md               # case lifecycle, agent fan-out, ledger write
│   │   ├── threat-model.md            # NFR-S4
│   │   └── tenant-isolation.md
│   └── runbooks/
│       ├── tenant-onboarding.md       # NFR-SC4
│       ├── tenant-offboarding.md
│       ├── screening-vendor-swap.md   # exercises P1 pluggability
│       ├── jurisdiction-pack-add.md
│       ├── break-glass-access.md      # FR50, NFR-T6
│       └── disaster-recovery.md       # NFR-A3
│
├── apps/
│   ├── cockpit-ui/                    # React + Vite + TS strict
│   │   ├── README.md
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   ├── tsconfig.json
│   │   ├── tailwind.config.ts         # @theme tokens (F7)
│   │   ├── postcss.config.js
│   │   ├── components.json            # shadcn config
│   │   ├── index.html
│   │   ├── public/
│   │   │   └── agent-faces/           # 8 illustrated avatars (UX §1.1)
│   │   ├── src/
│   │   │   ├── main.tsx
│   │   │   ├── App.tsx
│   │   │   ├── api-types.ts           # GENERATED — do not edit
│   │   │   ├── routes/                # TanStack Router file-based
│   │   │   │   ├── __root.tsx
│   │   │   │   ├── login.tsx
│   │   │   │   ├── _auth.tsx          # auth-protected layout shell
│   │   │   │   ├── _auth/
│   │   │   │   │   ├── queue.tsx                          # FR1-2
│   │   │   │   │   ├── cases.$caseId.tsx                  # FR3, FR7
│   │   │   │   │   ├── cases.$caseId.regulator-lens.tsx   # FR33
│   │   │   │   │   ├── approvals.tsx                      # FR36-38 Team Lead
│   │   │   │   │   └── portfolio.tsx                      # FR40-41 CCO
│   │   │   ├── components/
│   │   │   │   ├── ui/                # shadcn copies (owned)
│   │   │   │   │   ├── dialog.tsx
│   │   │   │   │   ├── popover.tsx
│   │   │   │   │   ├── dropdown-menu.tsx
│   │   │   │   │   ├── tabs.tsx
│   │   │   │   │   ├── tooltip.tsx
│   │   │   │   │   ├── toast.tsx
│   │   │   │   │   ├── slider.tsx
│   │   │   │   │   ├── scroll-area.tsx
│   │   │   │   │   └── separator.tsx
│   │   │   │   └── cockpit/           # bespoke (one folder per component)
│   │   │   │       ├── AgentFace/                # 8 states, breath/wake/chime
│   │   │   │       ├── ConfidencePill/           # P7 4-tier banding
│   │   │   │       ├── ProvenanceIndicator/      # P3 every datum
│   │   │   │       ├── ReasoningTraceSlideOut/   # P8 4-section trace
│   │   │   │       ├── CaseCanvas/               # FR7 collapsible panels
│   │   │   │       ├── DecisionZone/             # FR22-24 Tiptap editor + 120s undo
│   │   │   │       ├── QueueRail/                # FR1-2
│   │   │   │       ├── UBOCanvas/                # FR15-16 react-flow + drag-correct
│   │   │   │       ├── RiskScoreBar/             # FR20 stacked decomposition
│   │   │   │       ├── ScreeningExplainer/       # FR19 3-column card
│   │   │   │       ├── ModeSwitcher/             # FR4 ⌘+1-6
│   │   │   │       ├── CommandPalette/           # FR5 ⌘K
│   │   │   │       ├── AgentCopilotPane/         # FR11 live activity feed
│   │   │   │       ├── AuditTrailTimeline/       # FR30
│   │   │   │       ├── RegulatorLensFrame/       # FR33
│   │   │   │       ├── LedgerViewer/             # FR28-32 hash chain
│   │   │   │       └── EvidenceShelf/            # FR9
│   │   │   ├── stores/                # Zustand (F2)
│   │   │   │   ├── modeStore.ts       # current mode (Triage/Investigation/Zen/Lens)
│   │   │   │   ├── paletteStore.ts    # ⌘K open/closed
│   │   │   │   └── focusStore.ts      # currently-focused panel for soft-dim
│   │   │   ├── hooks/
│   │   │   │   ├── useCase.ts                 # TanStack Query
│   │   │   │   ├── useAgentState.ts           # SSE subscription
│   │   │   │   ├── useKeyboardShortcuts.ts    # j/k/x/d, ⌘K, ⌘+1-6 (FR2,4,5)
│   │   │   │   ├── useReasoningTrace.ts
│   │   │   │   └── useProvenance.ts
│   │   │   ├── lib/
│   │   │   │   ├── api.ts             # openapi-fetch typed client
│   │   │   │   ├── sse.ts             # EventSource wrapper → invalidates queries
│   │   │   │   ├── crypto.ts          # WebCrypto Ed25519 (S6, P5)
│   │   │   │   ├── confidence.ts      # to_band() mirror
│   │   │   │   └── i18n.ts            # react-i18next (F9)
│   │   │   ├── locales/
│   │   │   │   └── en/                # English-only at MVP (NFR-AC6)
│   │   │   └── styles/
│   │   │       ├── tokens.css         # CSS variable export from Tailwind theme
│   │   │       └── base.css
│   │   ├── tests/
│   │   │   ├── e2e/                   # Playwright (NFR-RI4)
│   │   │   │   ├── journey-1-sme-happy.spec.ts
│   │   │   │   ├── journey-2-edd-edge.spec.ts
│   │   │   │   ├── journey-3-team-lead-approval.spec.ts
│   │   │   │   ├── journey-4-regulator-lens-export.spec.ts
│   │   │   │   ├── a11y.spec.ts                   # axe-core (F8)
│   │   │   │   └── visual-regression.spec.ts
│   │   │   └── fixtures/
│   │   └── Dockerfile
│   │
│   ├── cockpit-api/                   # FastAPI gateway (also hosts agents in-process per A3)
│   │   ├── README.md
│   │   ├── pyproject.toml
│   │   ├── poetry.lock
│   │   ├── alembic.ini
│   │   ├── src/cockpit_api/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                # FastAPI app factory + uvicorn entrypoint
│   │   │   ├── config.py              # Pydantic Settings, env-driven
│   │   │   ├── deps.py                # auth dep, tenant dep, RBAC dep, db session dep
│   │   │   ├── routers/
│   │   │   │   ├── cases.py           # FR42-46 case ingest, GET case
│   │   │   │   ├── reasoning_traces.py # FR12
│   │   │   │   ├── decisions.py       # FR22-24 commit, undo
│   │   │   │   ├── approvals.py       # FR36-39 Team Lead workflow
│   │   │   │   ├── portfolio.py       # FR40-41 CCO dashboard
│   │   │   │   ├── exports.py         # FR33-35 Regulator Lens bundle
│   │   │   │   ├── webhooks.py        # FR44 outbound dispatch + inbound config
│   │   │   │   ├── auth.py            # FR47 OIDC callback, session
│   │   │   │   └── stream.py          # A2 SSE per-case
│   │   │   ├── services/              # business orchestration
│   │   │   │   ├── case_service.py
│   │   │   │   ├── decision_service.py # 120s undo, RFC 7807 errors
│   │   │   │   ├── ledger_service.py  # P4/P5 ledger append, hash chain
│   │   │   │   ├── webhook_dispatcher.py # A7 retry, HMAC sign
│   │   │   │   ├── rbac.py            # S5 role matrix
│   │   │   │   ├── sse_registry.py    # Redis-backed connection registry
│   │   │   │   └── retention_service.py # D10
│   │   │   ├── repositories/          # SQL only; nothing else
│   │   │   │   ├── case_repo.py
│   │   │   │   ├── ledger_repo.py
│   │   │   │   ├── document_repo.py
│   │   │   │   └── tenant_repo.py
│   │   │   ├── adapters/              # P1 pluggable
│   │   │   │   ├── doc_store/
│   │   │   │   │   ├── base.py
│   │   │   │   │   ├── ibm_cos.py
│   │   │   │   │   ├── aws_s3.py
│   │   │   │   │   └── minio_local.py
│   │   │   │   ├── key_vault/
│   │   │   │   │   ├── base.py
│   │   │   │   │   ├── ibm_hpcs.py
│   │   │   │   │   └── vault_transit.py
│   │   │   │   └── secrets/
│   │   │   │       ├── base.py
│   │   │   │       ├── ibm_secrets_manager.py
│   │   │   │       └── vault_kv.py
│   │   │   ├── middleware/
│   │   │   │   ├── tenant_scope.py    # P2 enforcement
│   │   │   │   ├── rate_limit.py      # NFR-S1 Redis-backed
│   │   │   │   ├── csrf.py            # S10
│   │   │   │   ├── request_id.py
│   │   │   │   └── error_handler.py   # RFC 7807 (A5)
│   │   │   ├── workers/               # Arq (D9)
│   │   │   │   ├── ledger_writer.py   # durable ledger append
│   │   │   │   ├── webhook_dispatcher.py # at-least-once retry
│   │   │   │   └── retention_runner.py
│   │   │   ├── db/
│   │   │   │   ├── session.py         # async SQLAlchemy session
│   │   │   │   ├── models.py          # ORM models
│   │   │   │   └── tenant_schemas.py  # per-tenant schema helpers (D2)
│   │   │   └── observability/
│   │   │       ├── tracing.py         # OTel setup
│   │   │       ├── logging.py         # structured JSON logger
│   │   │       └── metrics.py
│   │   ├── migrations/
│   │   │   └── versions/              # Alembic per-tenant migrations (D4)
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/           # against ephemeral Postgres
│   │   │   ├── contract/              # adapter conformance pairs
│   │   │   └── fixtures/
│   │   └── Dockerfile                 # multi-stage, combined with agents per A3
│   │
│   └── agents/                        # IBM watsonx Orchestrate ADK
│       ├── README.md
│       ├── pyproject.toml
│       ├── poetry.lock
│       ├── src/agents/
│       │   ├── __init__.py
│       │   ├── supervisor/
│       │   │   ├── case_supervisor.py
│       │   │   ├── case_supervisor.yaml      # ADK YAML manifest
│       │   │   └── action_decorator.py       # P4 enforces ledger entry
│       │   ├── intake/                       # L1 mesh layer
│       │   │   ├── document_intelligence.py
│       │   │   ├── document_intelligence.yaml
│       │   │   ├── entity_verification.py
│       │   │   └── entity_verification.yaml
│       │   ├── deep_dive/                    # L2 mesh layer
│       │   │   ├── ubo_graph.py              # FR15-17
│       │   │   ├── ubo_graph.yaml
│       │   │   ├── screening.py              # FR18-19
│       │   │   ├── screening.yaml
│       │   │   ├── risk_scoring.py           # FR20-21
│       │   │   ├── risk_scoring.yaml
│       │   │   ├── writing.py                # FR25-26 EDD drafter
│       │   │   └── writing.yaml
│       │   ├── interaction/                  # L3 mesh layer
│       │   │   ├── cockpit_chat.py           # FR13 mesh-as-tools
│       │   │   └── cockpit_chat.yaml
│       │   ├── tools/                        # ADK @tool functions
│       │   │   ├── mca_lookup.py             # FR17
│       │   │   ├── gst_verify.py             # FR17
│       │   │   ├── doc_extract.py
│       │   │   ├── ledger_append.py
│       │   │   ├── ubo_resolve.py
│       │   │   └── confidence_calibrate.py
│       │   ├── adapters/                     # P1 pluggable vendors
│       │   │   ├── screening/
│       │   │   │   ├── base.py
│       │   │   │   ├── complyadvantage.py
│       │   │   │   └── mock.py               # NFR-RI6 conformance pair
│       │   │   ├── doc_ai/
│       │   │   │   ├── base.py
│       │   │   │   ├── ibm_document_ai.py
│       │   │   │   ├── watson_discovery.py
│       │   │   │   └── mock.py
│       │   │   └── adverse_media/
│       │   │       ├── base.py
│       │   │       └── mock.py
│       │   ├── prompts/                      # version-controlled Jinja templates (NFR-RI7)
│       │   │   ├── document_intelligence/
│       │   │   │   ├── extract_v1.j2
│       │   │   │   └── extract_v1.golden.json
│       │   │   ├── writing/
│       │   │   │   ├── rationale_draft_v1.j2
│       │   │   │   ├── edd_memo_v1.j2
│       │   │   │   └── *.golden.json
│       │   │   └── ...
│       │   └── jurisdictions/                # config-driven, pluggable
│       │       ├── base.py
│       │       └── india/
│       │           ├── rules.py
│       │           ├── risk_weights.yaml
│       │           ├── sar_template.j2       # FIU-XML schema-ready
│       │           └── doc_taxonomy.yaml
│       └── tests/
│           ├── unit/
│           ├── integration/
│           ├── contract/                     # adapter conformance suite
│           ├── corpus/                       # 50-doc benchmark (NFR-T5 ≥ 95%)
│           │   ├── ground_truth/
│           │   └── samples/
│           └── golden/                       # prompt golden inputs
│
├── packages/
│   └── contracts/                            # P1/P2/P3/P4 source of truth
│       ├── pyproject.toml
│       ├── poetry.lock
│       ├── src/contracts/
│       │   ├── __init__.py
│       │   ├── ids.py                        # ULID/UUID typed wrappers
│       │   ├── tenant.py
│       │   ├── case.py                       # Case aggregate (shared state per agent memory model)
│       │   ├── agent_action.py               # P4
│       │   ├── ledger.py                     # entry, hash chain
│       │   ├── reasoning_trace.py            # P8 4-section
│       │   ├── provenance.py                 # P3 ProvenancedField[T]
│       │   ├── confidence.py                 # P7 banding + thresholds
│       │   ├── decision.py                   # commit, undo
│       │   ├── webhook.py                    # outbound contract
│       │   ├── screening.py                  # adapter contract
│       │   ├── doc_ai.py                     # adapter contract
│       │   ├── key_vault.py                  # adapter contract
│       │   ├── secrets.py                    # adapter contract
│       │   └── doc_store.py                  # adapter contract
│       ├── openapi.json                      # build artifact (committed)
│       └── tests/
│
├── tools/
│   └── verifier/                             # offline ledger verifier (FR35)
│       ├── README.md                         # how to run on a downloaded bundle
│       ├── pyproject.toml
│       ├── poetry.lock
│       ├── src/verifier/
│       │   ├── __init__.py
│       │   ├── verify.py                     # ≤ 300 LOC per PRD risk register
│       │   └── cli.py
│       └── tests/
│           └── golden/                       # known-good bundles for regression
│
└── infra/
    ├── terraform/
    │   ├── modules/
    │   │   ├── tenant-vpc/
    │   │   ├── postgres/
    │   │   ├── object-storage/
    │   │   ├── hpcs/
    │   │   ├── secrets-manager/
    │   │   ├── compute-vm/
    │   │   ├── code-engine/                  # post-MVP migration target
    │   │   └── observability/                # Grafana stack (I7)
    │   └── environments/
    │       ├── staging/
    │       └── prod-tenant-template/
    └── compose/
        ├── postgres.init.sql                 # creates schemas, roles
        ├── ledger-role.sql                   # INSERT-only ledger writer (D6)
        └── prometheus.yml                    # local OTel collector config
```

### Architectural Boundaries

**API boundary** — *only* `cockpit-api/routers/*` exposes HTTP/SSE. Cockpit-ui never talks to agents directly. Agents never expose HTTP.

**Agent boundary** — Agents are invoked *only* through `agents/supervisor/case_supervisor.py`. The Case Supervisor is invoked *only* through `cockpit-api/services/case_service.py`. No router calls an agent directly.

**Data boundary** — `repositories/*` own all SQL; nothing else touches the DB session. Services orchestrate. Routers translate HTTP↔services. SQLAlchemy ORM models (`db/models.py`) are internal-only; **wire types are always `packages/contracts` Pydantic**.

**Adapter boundary** — Agents and services call adapter `Protocol` interfaces from `packages/contracts/`. They never import vendor SDKs directly. The adapter implementation imports the SDK; the consumer doesn't know which adapter is wired up.

**Contract boundary** — All cross-app types live in `packages/contracts/`. **No app duplicates a Pydantic schema.** CI fails on duplicate definition (custom AST check).

**Observability boundary** — Structured logger at every service boundary; OTel `traceparent` propagated through HTTP, SSE, and Arq job submissions. PII scrubbed at the OTel collector egress (I14), with structured loggers stripping at source as defense-in-depth.

### Requirements-to-Structure Mapping

| FR Category | Frontend | Backend (cockpit-api) | Agents |
|---|---|---|---|
| Queue & Case Nav (FR1–6) | `routes/_auth/queue.tsx`, `components/cockpit/QueueRail`, `components/cockpit/CommandPalette`, `components/cockpit/ModeSwitcher`, `hooks/useKeyboardShortcuts` | `routers/cases.py` (list), `services/case_service.py` (ordering), `repositories/case_repo.py` | — |
| Case Canvas & Data (FR7–10) | `components/cockpit/CaseCanvas`, `components/cockpit/ProvenanceIndicator`, `components/cockpit/ConfidencePill` | `routers/cases.py` (get), services + repos | All agents emit `ProvenancedField[T]` |
| Agent Mesh Visibility (FR11–14) | `components/cockpit/AgentCopilotPane`, `components/cockpit/ReasoningTraceSlideOut`, `hooks/useAgentState` (SSE) | `routers/stream.py` (SSE), `routers/reasoning_traces.py`, `services/sse_registry.py` | Supervisor emits state events; cockpit chat (`agents/interaction/`) |
| UBO & Entity (FR15–17) | `components/cockpit/UBOCanvas` (react-flow + drag) | `routers/cases.py` (UBO PATCH for corrections, ledger learning event) | `agents/deep_dive/ubo_graph.py`, `agents/tools/mca_lookup.py`, `gst_verify.py` |
| Screening & Risk (FR18–21) | `components/cockpit/ScreeningExplainer`, `components/cockpit/RiskScoreBar` | `services/case_service.py` (re-score on edit) | `agents/deep_dive/screening.py`, `risk_scoring.py`, `adapters/screening/*` |
| Decision Authoring (FR22–27) | `components/cockpit/DecisionZone` (Tiptap), `lib/crypto.ts` (WebCrypto sign) | `routers/decisions.py`, `services/decision_service.py` (120s undo, edit-rate metric) | `agents/deep_dive/writing.py` (drafter) |
| Audit & Ledger (FR28–32) | `components/cockpit/LedgerViewer`, `components/cockpit/AuditTrailTimeline` | `services/ledger_service.py`, `repositories/ledger_repo.py`, `workers/ledger_writer.py` | All agents via `agents/supervisor/action_decorator.py` (P4) |
| Regulator Lens & Export (FR33–35) | `routes/_auth/cases.$caseId.regulator-lens.tsx`, `components/cockpit/RegulatorLensFrame` | `routers/exports.py`, `services/ledger_service.py` (bundle assembly) | — |
| Approval Workflows (FR36–39) | `routes/_auth/approvals.tsx` | `routers/approvals.py` | — |
| Portfolio & Reporting (FR40–41) | `routes/_auth/portfolio.tsx` | `routers/portfolio.py` | — |
| Platform Integration (FR42–46) | — | `routers/cases.py` (POST), `routers/webhooks.py`, `services/webhook_dispatcher.py`, `workers/webhook_dispatcher.py` | — |
| Identity, Access, Tenancy (FR47–51) | `routes/login.tsx`, `routes/_auth.tsx` (guard) | `routers/auth.py`, `deps.py`, `middleware/tenant_scope.py`, `services/rbac.py` | — |
| Agent Config & Ops (FR52–56) | — (admin UI is Future) | `adapters/*` (pluggable instantiation), tenant config in db | `agents/adapters/*`, `agents/jurisdictions/india/*` |

### Cross-Cutting Flow Examples

**Case ingest → decision-ready (Journey 1):**

```
core banking → POST /t/{tenant}/v1/cases
  → routers/cases.py
    → services/case_service.py.create()
      → repositories/case_repo.py.insert()
      → workers/ledger_writer enqueue (Arq)
      → triggers agents/supervisor/case_supervisor.py
        → fans out: document_intelligence → entity_verification → ubo_graph → screening → risk_scoring → writing
          → each agent wrapped by action_decorator (P4) → ledger_repo.append signed entry
        → emits SSE events via sse_registry on each state change
          → cockpit-ui hooks/useAgentState refetches via useCase
  → returns {case_id, state: "intake_scheduled"}
  → ~2 min later, webhook fires from workers/webhook_dispatcher
```

**Officer commit → audit ledger (Journey 1 close):**

```
DecisionZone (UI)
  → lib/crypto.ts WebCrypto sign canonical JSON (P5)
  → POST /t/{tenant}/v1/cases/{id}/decisions
    → routers/decisions.py
      → services/decision_service.py
        → verify Ed25519 signature against stored officer public key
        → repositories/ledger_repo.append signed entry (D6, P5)
        → workers/webhook_dispatcher enqueue (FR44)
      → 120s undo timer (NFR-T1) registered in Redis
      → returns 201 + RFC 7807 on failure
```

**Vendor swap (post-MVP demonstrating NFR-RI6):**

```
ops engineer
  → docs/runbooks/screening-vendor-swap.md
  → edit infra/terraform/.../tenant config: SCREENING_ADAPTER=lseg
  → run agents/tests/contract/screening_contract.py against LSEG adapter
  → terraform apply
  → zero changes to agent code, prompts, or contracts
```

### File Organization Rules

| Concern | Rule |
|---|---|
| Configuration | `apps/<app>/.env.example` documents every env var; `Pydantic Settings` in `config.py` reads them. No hardcoded secrets ever. |
| Static assets | `apps/cockpit-ui/public/` for shipped assets (favicon, agent faces); generated assets in `dist/` (gitignored). |
| Docs | Reference docs in `docs/` (committed); README per app for app-local quickstart; ADRs sequentially numbered, never reordered. |
| Tests | Python: separate `tests/` dir per app, mirrors `src/` layout. TS: co-located `Component.test.tsx` for unit; `tests/e2e/` for Playwright. |
| Build artifacts | `apps/cockpit-ui/dist/` (gitignored); `packages/contracts/openapi.json` (**committed** — used by CI for drift detection). |

### Development Workflow

```bash
# First-time setup (~30 min — NFR-RI5)
git clone <repo> && cd ibm_orchestrate_platform
make bootstrap                     # poetry install across all Python projects, pnpm install for ui
docker compose up -d               # postgres, redis, localstack, vault, ADK dev edition
make migrate                       # alembic upgrade per dev tenant schema
make seed                          # demo tenant + sample case data
make dev                           # uvicorn (api+agents) + vite (ui) in parallel

# Daily development
make test                          # pytest + vitest + contract conformance
make lint                          # ruff + mypy + eslint + prettier
make contracts                     # regen openapi.json + api-types.ts
make verify                        # run offline verifier on a sample bundle
```

### Build & Deployment

| Stage | Producer | Consumer |
|---|---|---|
| Cockpit-ui static SPA | `vite build` → `apps/cockpit-ui/dist/` | Containerized, served behind CDN (I12) |
| Cockpit-api + agents | Multi-stage Dockerfile in `apps/cockpit-api/` (combined per A3) | Runs as single uvicorn process; deployed to VM/Compose (I2) |
| Verifier | `tools/verifier/` standalone wheel | Distributed alongside Regulator Lens bundle as a download |
| OpenAPI spec | `packages/contracts/openapi.json` (built artifact) | CI drift check; ship to bank integration teams |
| Terraform plan | `infra/terraform/environments/<env>/` | GitHub Actions plan-on-PR; apply-on-merge |

## Architecture Validation Results

### Coherence Validation ✅

**Stack compatibility:** Python 3.11 + FastAPI 0.115 + Pydantic 2.7 + SQLAlchemy 2.0 + asyncpg + Alembic; React 19 + Vite 7 + Tailwind 4 + TanStack Query 6 + TanStack Router; Poetry workspaces + pnpm workspaces; IBM Cloud HPCS + COS + Postgres + Code Engine — all 2026-canonical and coexist.

**Pattern ↔ Decision alignment:**

- P1 Pluggable Adapter ↔ D5, S1, S2, screening, doc-AI: same shape across the codebase, conformance suite enforces ✓
- P2 Tenant Scoping ↔ D2 schema-per-tenant + S1 per-tenant key + I9 per-tenant VPC: tenant boundary is consistent at code, data, key, and infra layers ✓
- P3 Provenance ↔ NFR-T4 (100% coverage): CI test + Pydantic discipline ✓
- P4 Agent Action ledger ↔ D6 + S1 + FR28: every agent action signed and chained ✓
- P5 Officer Signing ↔ S6 + FR29: client-side WebCrypto + server verification + ledger entry ✓
- P6 SSE event minimal payload ↔ A2 + F1: events trigger TanStack invalidation, fat data behind REST refetch ✓
- P7 Confidence banding ↔ NFR-AC3: shape + position + label, not color alone ✓
- P8 Counterfactual ↔ FR12 + Innovation #2: 4-section reasoning trace mandatory ✓

**Coherence concerns surfaced (with explicit mitigations):**

| # | Concern | Resolution |
|---|---|---|
| **C1** | In-process agents (A3) and agent failure isolation (NFR-A5) — agent crash could affect API availability | `action_decorator` (P4) wraps every agent invocation in try/except → ledger entry with `error` state → Case Supervisor flags case for human. Uvicorn worker recycling (`max-requests` + `max-requests-jitter`) is the second layer. **If the pilot shows uvicorn worker churn, extract agents to a sidecar container** — the Pydantic-typed boundary is already shaped for it. |
| **C2** | SSE (A2) across multiple uvicorn workers — agent state change in one worker doesn't reach SSE connections held by another worker | `services/sse_registry.py` is **Redis pub/sub-backed** — every worker subscribes; agent state changes publish to a per-tenant channel; subscribers fan out to their open SSE connections. **Now explicit in the architecture.** |
| **C3** | 120-second undo (NFR-T1) and Redis availability — undo timer state in Redis; if Redis dies during the 120s window, timer is lost | **Policy: fail closed.** If Redis is unreachable when the undo window expires, the commit is **not** sealed (auto-cancel). When Redis recovers, the timer resumes from its remaining window. The decision is "pending seal" until either the timer expires or the officer commits. RFC 7807 surfaces this as a transient state to the cockpit. |

### Requirements Coverage Validation ✅

**Functional Requirements (FR1–FR56):** All 56 FRs mapped to specific files/components in the FR-to-location mapping table (Step 6). ✅

**Non-Functional Requirements:**

| NFR Family | Coverage |
|---|---|
| Performance (P1–P4) | TanStack Query + Zustand + SSE + pre-rendered cockpit hit the budget envelopes |
| Security (S1–S6) | Rate limiting middleware, account lockout, weekly Snyk scan, threat model authoring, pre-pilot pentest in CI/CD plan, prompt-injection three-layer defense (S7) |
| Availability (A1–A7) | 99.5% pilot SLO via Compose + restart-policies + I11 backup/PITR; agent isolation via P4 decorator; ledger atomicity via Postgres transaction + INSERT-only role; vendor-down → block + reason (no stale data) |
| Scalability (SC1–SC4) | Architecture is K8s-ready (just deferred); per-tenant isolation primitives ship production-grade from day one |
| Accessibility (AC1–AC6) | Radix primitives + WCAG 2.2 AA + axe-core in Playwright + keyboard-first + i18n scaffolding |
| Observability (O1–O6) | OTel + Orchestrate trace export + PII-scrub + per-tenant namespace + Grafana stack + alerting rules |
| Compatibility (CP1–CP4) | Browser-only SPA; minimum viewport drives Tailwind breakpoint config |
| Reference Implementation (RI1–RI7) | ADK pattern coverage explicit in `agents/` layout; ADR discipline in `docs/adr/`; ≥80% test coverage targeted; 30-min clone-to-demo via `make bootstrap`; conformance pair per adapter; Jinja prompt library |
| Specific Thresholds (T1–T6) | 120s undo (with C3 policy); 30-min session in `Pydantic Settings`; edit-rate metric in `decision_service.py`; provenance assertion CI test; 95% precision in corpus benchmark; 40-char break-glass enforced in router |
| Compliance | India jurisdiction pack scaffold; pluggable interface; FIU-XML SAR template; DPDP-aware retention; audit ledger holds for RBI/FIU |

### Implementation Readiness Validation ✅

**Decision completeness:** 47 decisions documented across D/S/A/F/I categories with version, rationale, and cascading implications.

**Pattern completeness:** 8 project-specific patterns (P1–P8) with code examples; ~25 generic conventions (naming, format, communication, process); enforcement mechanism per pattern (Ruff/ESLint custom rules → contract conformance suite → PR review checklist).

**Structure completeness:** Complete file tree from `apps/` down to specific modules; FR-category-to-location mapping table; cross-cutting flow examples for case ingest, officer commit, and vendor swap.

**Anti-patterns enumerated:** 10 anti-patterns; each one a CI-enforceable rule.

### Gap Analysis Results

**Critical gaps (block readiness):** **None.** Architecture is implementable today.

**Important gaps (track and resolve before pilot):**

| # | Gap | Owner |
|---|---|---|
| **G1** | Threat model document referenced as `docs/architecture/threat-model.md` but not yet authored. NFR-S4 mandates it. | Architecture review pre-pilot |
| **G2** | OpenAPI breaking-change governance — versioning is `/v1/` path-prefix, but evolution policy (when to bump to `/v2/`, deprecation window, dual-serving) is undefined. | First ADR after the contract package is non-trivial |
| **G3** | DR rehearsal cadence — runbook exists; quarterly rehearsal cadence implied but not codified as ops calendar item. | Pilot ops handoff |
| **G4** | Capacity / cost estimation — outside this workflow's scope but the buyer pipeline will ask. | Post-architecture artifact |

**Nice-to-have gaps:**

| # | Gap | Note |
|---|---|---|
| G5 | `ibm-watsonx-orchestrate` minimum version pin — pin once first integration is working | First implementation story |
| G6 | `make dev` cold-start budget — should be ≤ 90s for the inner loop to feel fluent | Set after first implementation |
| G7 | Performance SLOs as Grafana alerts — thresholds in NFRs are documented but not yet codified as alert rules | Pilot-prep |

### Architecture Completeness Checklist

**✅ Requirements Analysis** — context analyzed, scale assessed (enterprise/regulated), complexity drivers identified, cross-cutting concerns mapped, open decisions enumerated and tracked through the workflow.

**✅ Architectural Decisions** — 47 decisions across 5 categories, all with versions where applicable, all rationaled, three deferred decisions (screening vendor, doc AI stack, agent memory model) explicitly resolved or pinned to procurement.

**✅ Implementation Patterns** — 8 project-specific patterns with code; ~25 conventions across naming/format/comm/process; 10 anti-patterns; enforcement at lint/CI/review.

**✅ Project Structure** — complete file tree; FR-to-location mapping; architectural boundary definitions (API, agent, data, adapter, contract, observability); cross-cutting flow examples; build/deploy stages.

**✅ Validation** — coherence checked across stack/patterns/structure; three coherence concerns surfaced with explicit mitigations (C1–C3); requirements coverage 100% on FRs and NFR families; readiness confirmed with named gaps tracked.

### Architecture Readiness Assessment

**Overall Status:** **READY FOR IMPLEMENTATION**

**Confidence level:** **High.** The stack is conventional 2026 (no exotic bets), the regulatory floors (audit + provenance + tenant isolation) are designed-in not bolted-on, the Path B reference-implementation thesis is reinforced by specific decisions (S6 WebCrypto, A10 Pydantic→TS, I2 VM+Compose, I13 one-command local), and pluggability is mandated for every external dependency.

**Key strengths:**

1. **Tenant isolation is a deployment-shaped primitive**, not a code-shaped one — schema, key, VPC, observability namespace all tenant-scoped.
2. **Cryptographic guarantees live in data structure (hash chain + signatures), not infrastructure** — survives platform compromise, regulator-verifiable offline.
3. **Pluggable adapter pattern (P1) makes vendor decisions reversible** — screening, doc AI, key vault, secrets, doc store all swappable in one file.
4. **Path B "reference implementation" surface** is concrete: 4 specific decisions (A10, S6, I2, I13) carry the "I didn't know Orchestrate could do this" signal.
5. **MVP scope discipline:** every Future-deferred capability has an architectural hook (vector store can be added without migration; K8s migration without code change; multi-tenant lift via existing isolation primitives).

**Areas for future enhancement (not blockers):**

- Move agents to a sidecar container post-pilot if uvicorn worker churn surfaces (C1)
- Adopt OPA/Casbin if RBAC matrix grows beyond ~10 roles (S5 today is simpler hand-rolled)
- Migrate VM + Compose to Code Engine or OpenShift when scale or multi-tenant operational demand justifies (I2)
- Add pgvector when adverse media or perpetual-KYC scope arrives (D7)
- Add Storybook if the design surface outgrows inline docs (F10)

### Implementation Handoff

**AI Agent / Developer Guidelines:**

1. Follow architectural decisions exactly — every D/S/A/F/I decision is binding unless explicitly amended in an ADR.
2. Use patterns P1–P8 consistently — they have code examples in this document.
3. Respect boundaries (API / agent / data / adapter / contract / observability) — refactors that violate boundaries require ADR.
4. Refer to this document for all architectural questions; supplemental ADRs in `docs/adr/` for deltas.
5. New external dependency? Wraps in a Pluggable Adapter (P1) with conformance pair.
6. New agent? Goes through `action_decorator` (P4); reasoning trace populates all four sections of P8.
7. New UI datum? Wraps in `ProvenancedField[T]` (P3).

**First implementation priority** — execute Step 3's initialization commands in order:

```bash
# 1. cockpit-ui scaffold (Vite + shadcn/ui init)
# 2. agents scaffold (poetry init + ADK init)
# 3. cockpit-api scaffold (poetry init + FastAPI module-functionality layout)
# 4. packages/contracts scaffold (poetry init)
# 5. tools/verifier scaffold (poetry init)
# 6. Root Makefile + pnpm-workspace.yaml + docker-compose.yml + .pre-commit + GitHub Actions skeleton
# 7. First migration + first end-to-end auth flow + first agent (Document Intelligence) wired through P4
```

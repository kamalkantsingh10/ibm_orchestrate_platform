---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
workflow_completed: true
completion_date: 2026-04-27
status: complete
inputDocuments:
  - Documentation/planning-artifacts/prd.md
  - Documentation/planning-artifacts/architecture.md
  - Documentation/planning-artifacts/ux-design-specification.md
project_name: 'ibm_orchestrate_platform'
user_name: 'Kamal'
date: '2026-04-27'
sequencingPrinciple: 'progressive-complexity — start with scaffolding, layer one agent + minimal UX, expand outward'
---

# ibm_orchestrate_platform (KYC Cockpit) — Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for **KYC Cockpit**, decomposing requirements from the PRD, UX Design Specification, and Architecture into implementable stories.

**Sequencing principle:** *Start easy, progressively add complexity.* Foundations first, then the smallest end-to-end vertical slice (one agent, minimal UI, real auth + real ledger), then layered richness — more agents, more UX sophistication, more modes, audit/export, multi-role, hardening.

## Requirements Inventory

### Functional Requirements

**Queue & Case Navigation:**

- FR1: KYC Analysts can view a queue of assigned cases ordered by risk × SLA × continuity.
- FR2: KYC Analysts can navigate the queue using keyboard shortcuts (next/previous/open/defer).
- FR3: KYC Analysts can open a case and see all intake-agent-computed results without manual refresh.
- FR4: KYC Analysts can switch among officer modes (MVP: Deep Investigation, SAR/EDD Writing) via keyboard shortcuts.
- FR5: KYC Analysts can access a system-wide command palette to invoke any action by name.
- FR6: All roles receive in-app notifications when actions require their attention.

**Case Canvas & Data Display:**

- FR7: KYC Analysts can view a case's identity, documents, UBO, screening, risk, and timeline in collapsible panels on a single canvas.
- FR8: Every datum rendered in the cockpit displays a provenance indicator identifying its source agent, upstream source system, and confidence.
- FR9: KYC Analysts can open an Evidence Bundle shelf to view and attach supporting evidence (emails, forms, photos) to a case.
- FR10: All agent outputs render confidence using a consistent four-tier confidence-banded visual system.

**Agent Mesh Visibility & Interaction:**

- FR11: KYC Analysts can view a live activity feed of every agent working on the current case, including per-agent status (done, in-progress, blocked, needs-input).
- FR12: KYC Analysts can open a reasoning-trace slide-out for any agent action showing (a) what was searched, (b) what returned, (c) the agent's confidence self-rating, and (d) a counterfactual — what evidence would change the conclusion.
- FR13: KYC Analysts can converse with a Cockpit Chat agent that has access to the full mesh state and current case context.
- FR14: The agent mesh automatically runs intake agents on case creation without officer action.

**Entity & UBO Analysis:**

- FR15: KYC Analysts can view an interactive force-directed UBO graph with confidence-banded edges and basic nominee/shell heuristics flagged visually.
- FR16: KYC Analysts can drag UBO edges to correct relationships; corrections are captured as named "learning events" in the ledger with officer opt-in for future ground-truth use.
- FR17: The Entity Verification agent can cross-reference a case entity against MCA and GST sources and surface mismatches.

**Screening & Risk Analysis:**

- FR18: The Screening agent can evaluate case entities and associated individuals against the configured screening vendor and surface hits with match details.
- FR19: KYC Analysts can view a screening-hit explainer showing name-similarity, identifier matches/mismatches (DOB, address, ID), confidence, and the counterfactual.
- FR20: KYC Analysts can view a risk-score explainer decomposing the score across contributing factors (country, entity type, ownership clarity, screening, adverse media).
- FR21: Risk scores automatically recalculate in response to officer corrections (e.g., UBO edits, manual screening disposition).

**Decision Authoring & Commit:**

- FR22: KYC Analysts can view and edit an agent-drafted rationale in a dedicated Decision Zone before committing a decision.
- FR23: KYC Analysts can undo a committed decision within a defined undo window.
- FR24: KYC Analysts can commit case decisions with outcomes: approve, decline, approve-with-conditions, escalate-to-EDD.
- FR25: KYC Analysts can enter a dedicated SAR/EDD Writing mode with dark-background, minimized-chrome, evidence-docked UI.
- FR26: The Writing agent can draft a structured EDD narrative memo citing specific ledger entries and evidence items by reference ID.
- FR27: The platform measures and exposes the "edit-rate" metric — the proportion of each rationale that is officer-edited versus agent-drafted.

**Audit, Provenance & Ledger:**

- FR28: Every agent action is captured in an append-only, cryptographically hash-chained ledger including agent ID, model ID, prompt hash, tool inputs, outputs, timestamp, and platform signature.
- FR29: Every officer action is captured in the ledger including user ID, action type, inputs, rationale, and a user-credential-based signature.
- FR30: KYC Analysts, Team Leads, CCOs, and Internal Auditors can view a case timeline with interleaved agent and officer actions, scoped by role permissions.
- FR31: Uploaded documents are immutable after ingestion; SHA-256 hashes are recorded in the ledger and verifiable on download.
- FR32: The system prevents any write or delete operation on the ledger through normal application APIs.

**Regulator Lens & Export:**

- FR33: Internal Auditors can switch a case into a read-only Regulator Lens mode that reframes the cockpit into an audit-focused view.
- FR34: Internal Auditors can export a case (or a set of cases) as a PDF + JSON audit bundle.
- FR35: Each audit bundle is cryptographically self-verifying — hash chain and signatures can be validated offline using a bundled verification tool without calling the platform.

**Approval Workflows:**

- FR36: Team Leads can view a dedicated queue of cases pending their approval.
- FR37: Team Leads can approve, approve-with-conditions, or decline cases; conditions (enhanced monitoring, re-review triggers) are captured as structured state in the ledger.
- FR38: Team Leads can view full agent + officer history (audit trail) for any case in their scope.
- FR39: KYC Analysts can commit EDD-outcome decisions that automatically enqueue the case for Team Lead approval.

**Portfolio & Reporting:**

- FR40: Chief Compliance Officers can view a minimal Portfolio Dashboard summarizing: cases processed, median case time, SLA breaches, risk-band distribution, and audit-readiness indicator for their tenant.
- FR41: Chief Compliance Officers can export a tenant-level summary (aggregated, non-PII) for a time-bounded cohort.

**Platform Integration (API):**

- FR42: External systems (e.g., core banking) can submit new cases via authenticated REST API including customer metadata and document references.
- FR43: External systems can upload documents via presigned URLs or multipart streams.
- FR44: The platform emits authenticated webhooks to registered callbacks for case state changes and decision events.
- FR45: External systems can retrieve a case by ID per their API-consumer scope.
- FR46: Case creation is idempotent against a client-provided request ID.

**Identity, Access & Tenancy:**

- FR47: Users authenticate via tenant-configured SAML 2.0 or OIDC single sign-on.
- FR48: Role-based access control — KYC Analyst, Team Lead, CCO, Internal Auditor, Tenant Admin, API Consumer — is enforced at both API and UI layers with deny-by-default.
- FR49: All tenant data is isolated — no cross-tenant reads, writes, or queries are permitted by the platform.
- FR50: Tenant Admins (Future UI; MVP via runbook) can perform break-glass emergency read access with cryptographically-signed justification and ledger entry.
- FR51: The platform automatically signs users out after a configurable period of inactivity.

**Agent Configuration & Operations:**

- FR52: Tenant Admins (MVP: via scripted runbook) can configure the active screening vendor via a pluggable adapter interface.
- FR53: Tenant Admins (MVP: via scripted runbook) can configure jurisdiction rules, SAR templates, and document taxonomy.
- FR54: The platform supports feature flags per tenant to enable or disable individual agents and capabilities.
- FR55: Agent failures are isolated — a single agent failure does not cascade; the Case Supervisor retries or flags the case for human attention.
- FR56: External vendor integrations conform to contract-interface tests; swapping a vendor requires only the adapter implementation to change, not agent logic.

**Total Functional Requirements: 56**

### NonFunctional Requirements

**Performance:**

- NFR-P1: Keyboard-driven actions respond within 50 ms p95.
- NFR-P2: Cockpit panel expand/collapse renders within 150 ms p95.
- NFR-P3: Cockpit supports ≥ 50 UBO nodes without degradation.
- NFR-P4: All 8 MVP agents can run in parallel where deps permit, without resource contention causing p95 breach.
- *Plus:* UI nav ≤ 200 ms p95 · reasoning-trace slide-out ≤ 500 ms p95 · case creation API ≤ 1 s p95 · full mesh cold-start ≤ 2 min p95 · UBO Canvas render ≤ 1.5 s p95 · audit ledger export ≤ 10 s.

**Security:**

- NFR-S1: API rate limiting per API key/IP/endpoint; default 100 req/min, burst 500, configurable per tenant.
- NFR-S2: Account lockout after 5 failed auth attempts within 10 min; unlock via admin or timed cooldown.
- NFR-S3: Weekly Snyk/Dependabot scan; Critical CVEs resolved in 48h, High in 7 days.
- NFR-S4: Documented threat model covering agent mesh, ledger, screening boundary, document upload, auth; reviewed quarterly.
- NFR-S5: Pre-pilot external pentest; Critical/High remediated before pilot launch.
- NFR-S6: LLM prompt security — version-controlled, peer-reviewed templates; runtime injection guards.
- *Plus baseline:* TLS 1.3 · AES-256 · HSM-backed signing · per-tenant credentials · append-only ledger · RBAC deny-by-default · 30 min session timeout.

**Availability & Reliability:**

- NFR-A1: MVP pilot SLO 99.5% during business hours IST (Mon–Fri, 09:00–19:00).
- NFR-A2: GA target 99.9% annual.
- NFR-A3: DR — RPO ≤ 1h, RTO ≤ 4h.
- NFR-A4: P1 incident MTTR ≤ 2h.
- NFR-A5: Single agent failure must not exceed one case's processing.
- NFR-A6: Ledger write atomic — partial entry never visible.
- NFR-A7: Graceful degradation on vendor outage — never render stale data as current.

**Scalability:**

- NFR-SC1: MVP — 10 concurrent analysts, 500 open cases, 100 ingests/hour.
- NFR-SC2: 10× horizontal scale within a tenant without code changes.
- NFR-SC3: Ledger growth ~10 MB/case; hot/warm/cold tiering at 2y.
- NFR-SC4: Multi-tenant on shared infra post-MVP; isolation primitives production-grade from day one.

**Accessibility:**

- NFR-AC1: WCAG 2.2 Level AA conformance.
- NFR-AC2: All primary officer actions keyboard-accessible.
- NFR-AC3: Confidence-banded visual system uses shape + position + label in addition to color.
- NFR-AC4: Color contrast ≥ 4.5:1 body text, ≥ 3:1 UI chrome.
- NFR-AC5: Persistent, high-contrast focus indicators on every keyboard-navigable element.
- NFR-AC6: i18n architecture from day one — externalized strings, locale-aware date/number; English-only at MVP.

**Observability:**

- NFR-O1: Structured OpenTelemetry traces; agent activity enriched with case ID, agent ID, case state.
- NFR-O2: Orchestrate-native traces exported alongside application traces.
- NFR-O3: Telemetry PII-scrubbed at collection layer.
- NFR-O4: Per-tenant observability partitioning.
- NFR-O5: Product telemetry dashboards (case-time, edit-rate, mode-usage, agent precision, NPS, SLA breach, audit-readiness).
- NFR-O6: P1 alerts (ledger integrity, screening down, auth down, agent cascade) page on-call within 1 min.

**Compatibility:**

- NFR-CP1: Latest 2 versions of Chrome/Edge/Firefox/Safari on desktop; no IE; no tablet/mobile in MVP.
- NFR-CP2: Runs on Windows 10+, macOS 12+, Ubuntu 22.04+.
- NFR-CP3: Min viewport 1366×768; optimized for 1920×1080 and 2560×1440.
- NFR-CP4: Browser-only — no native client.

**Reference Implementation (Path B):**

- NFR-RI1: ADK pattern coverage — supervisor/collaborator, agent-as-tool, Pydantic-contracted tools, HITL approval, background/scheduled, parallel meta-critic, conversational-with-mesh-as-tools, Orchestrate-trace audit.
- NFR-RI2: Every agent has a README; every non-trivial decision in an ADR.
- NFR-RI3: Ruff + mypy strict (Python); ESLint + TS strict.
- NFR-RI4: ≥ 80% unit coverage on agent logic + tool adapters; integration tests at every contract boundary; e2e for the four canonical flows.
- NFR-RI5: Clone + local demo in ≤ 30 minutes.
- NFR-RI6: Every adapter ships with a second reference adapter.
- NFR-RI7: All LLM prompts in version-controlled Jinja templates with golden inputs.

**Specific Thresholds:**

- NFR-T1: Undo window 120 seconds.
- NFR-T2: Session inactivity 30 minutes (configurable [15, 60]).
- NFR-T3: Edit-rate target ≥ 60% (agent-drafted ≥ 80% AND officer-edited < 20%).
- NFR-T4: Provenance coverage 100% on rendered data points.
- NFR-T5: Agent precision floor — DocIntel ≥ 95% field extraction; UBO basic ≥ 95% structural.
- NFR-T6: Break-glass justification ≥ 40 characters.

**Compliance:** RBI Master Direction · PMLA 2002 + PML Rules 2005 (5y retention, STR within 7 days) · Section 12 PMLA (ongoing monitoring) · Companies Act 2013 §89/90 + SBO Rules 2018 · DPDP Act 2023 · FIU-India XML schema readiness.

### Additional Requirements

**From Architecture (decisions and patterns that drive specific work beyond raw FRs):**

- AR1: **Polyglot monorepo scaffold** — Vite + ADK init + FastAPI module-functionality layout + Poetry workspaces + pnpm workspace + Makefile orchestration. **Mandates Story 1.1 = "Set up initial project from scaffold."**
- AR2: **Pluggable adapter pattern (P1)** for: doc store (S3-compatible), key vault (HSM), secrets manager, screening vendor, doc AI stack, jurisdiction pack, adverse media — each with second-reference conformance pair (NFR-RI6).
- AR3: **Per-tenant data isolation (P2)** — separate Postgres schema, separate S3 bucket, separate HSM signing key; `tenant_id` enforced at every layer.
- AR4: **Cryptographic audit ledger** — same Postgres, separate `ledger` schema, INSERT-only role, DB triggers blocking UPDATE/DELETE, application-level Ed25519 hash chain.
- AR5: **Offline ledger verifier tool** — ≤ 300 LOC Python, separately distributable wheel.
- AR6: **Server-Sent Events real-time channel** with **Redis pub/sub registry** for multi-worker coordination.
- AR7: **Arq Redis-backed job queue** for ledger writes, webhook retries, retention runner.
- AR8: **OpenAPI 3.1 → TypeScript types pipeline** (Pydantic → openapi.json → openapi-typescript → api-types.ts via `make contracts`).
- AR9: **Structured JSON logging** with required fields (tenant_id, case_id, agent_id, actor, action, level, request_id, trace_id, timestamp).
- AR10: **OpenTelemetry tracing** with W3C `traceparent` propagation; PII scrubbing at OTel collector egress (NFR-O3).
- AR11: **Per-tenant observability namespace partitioning** (NFR-O4).
- AR12: **Officer Ed25519 keypair** generated at first login; private key encrypted at rest with tenant HSM master key; client-side WebCrypto signing.
- AR13: **ADR discipline** — every non-trivial decision documented in `docs/adr/NNNN-title.md` (NFR-RI2).
- AR14: **30-min clone-to-demo** via `make bootstrap` + `docker compose up` + `make migrate` + `make seed` + `make dev` (NFR-RI5).
- AR15: **Threat model document** at `docs/architecture/threat-model.md` (NFR-S4).
- AR16: **External pentest engagement** pre-pilot (NFR-S5).
- AR17: **Tenant onboarding/offboarding runbooks** (NFR-SC4).
- AR18: **Disaster recovery** — daily Postgres logical backups + 15-min PITR + S3 cross-region replication; quarterly rehearsal (NFR-A3).
- AR19: **Screening vendor procurement + sandbox onboarding** — real-world calendar dependency (recommended: ComplyAdvantage).
- AR20: **Document AI stack 50-doc corpus benchmark** — IBM Document AI vs Watson Discovery (NFR-T5 ≥ 95%).
- AR21: **India jurisdiction pack** — RBI rules, FIU-XML SAR template, doc taxonomy, risk weights.
- AR22: **GitHub Actions CI/CD** with OIDC-federated cloud creds (no long-lived secrets).
- AR23: **Terraform IaC modules** — tenant VPC, Postgres, COS, HPCS, Secrets Manager, compute.
- AR24: **Pre-commit hooks** for ruff/mypy/eslint/prettier (language-agnostic, not Husky).
- AR25: **Contract conformance test suite** per adapter — same test file runs against every implementation.
- AR26: **Pydantic Settings env-driven configuration** — no hardcoded secrets.
- AR27: **Idempotency-key header convention** (`X-Cockpit-Idempotency-Key`) for retried writes.
- AR28: **Rate limiting middleware** (Redis-backed token bucket, 100 req/min default, configurable per tenant).
- AR29: **Confidence calibration study** pre-pilot — calibrate per-agent thresholds against ground-truth accuracy.
- AR30: **8 prompt template families** with golden inputs (NFR-RI7) — version-controlled Jinja templates.
- AR31: **Per-tenant Alembic migrations** — migrations applied per-tenant schema via tenant-onboarding runbook.

### UX Design Requirements

UX-DR items below are first-class requirements derived from the UX Design Specification. Each is specific enough to generate a story with testable acceptance criteria.

**Design tokens & visual foundation:**

- UX-DR1: Tailwind 4 `@theme` tokens for "marble and spring flowers" palette — white marble base, true black structure, four confidence-band colors, six agent-identity hues at ~8% saturation, semantic success/warning/danger, dark-mode variants.
- UX-DR2: Typography scale (12/13/14/16/18/20/24/32/48), variable sans family + variable mono family, serif family for Zen mode, weight scale 400/500/600/700, line-height rhythm.
- UX-DR3: Spacing rhythm — 4px-grid base with named steps (xs/sm/md/lg/xl/2xl); per-mode density variants.
- UX-DR4: Restrained radii (sm:4, md:6, lg:8, pill:999) and subtle shadows (sm hover, md panel focus, lg slide-out) — no dramatic elevation.
- UX-DR5: Three motion curves — `snap` (100ms ease-out, click feedback), `ease` (250ms cubic-bezier, expansion), `reveal` (300ms ease-in-out, slide-out); 400ms ceiling.

**Agent face system:**

- UX-DR6: Eight illustrated agent face avatars (Pixar-restraint style, dignified — *not* cartoonish) for: Case Supervisor, Document Intelligence, Entity Verification, UBO Graph, Screening, Risk Scoring, Writing, Cockpit Chat.
- UX-DR7: Agent face state machine (idle, working with breath animation, complete with chime/glow, blocked with dimmed error mark, needs-input looking toward officer); SVG-with-CSS-state-classes (no Lottie).

**Component primitives:**

- UX-DR8: Four-tier `ConfidencePill` component — low / medium-low / medium-high / high — rendered via shape + position + label + color (NFR-AC3 — never color alone).
- UX-DR9: `ProvenanceIndicator` provenance pill on every UI-rendered datum; click reveals reasoning trace.
- UX-DR10: `ReasoningTraceSlideOut` with fixed 4-section schema — what searched · what hit · confidence self-rating · counterfactual.
- UX-DR11: Three motion flavors implemented as shared Framer Motion utilities — `expand`, `focus-dim`, `slide-out`.
- UX-DR12: Persistent high-contrast focus indicators on every keyboard-navigable element (NFR-AC5).

**Cockpit zones:**

- UX-DR13: `QueueRail` (260px, left) with risk × SLA × continuity ordering and rich row layout (name + risk bar + SLA chip + delta).
- UX-DR14: `CaseCanvas` (center, fluid) with collapsible panels (identity, docs, screening, UBO, tx, timeline, log, ripple); soft-dim focus on click; panel expansion easing.
- UX-DR15: `AgentCopilotPane` (320px, right) with live activity feed, NL chat, and reasoning-trace slide-out.
- UX-DR16: `DecisionZone` (bottom of canvas) — spatially + typographically distinct (font scale 14→16, headings 20→24), tonal palette shift, soft-dim of canvas, Tiptap rich-text editor.
- UX-DR17: `TopBar` (MVP minimal) — environment badge, mode switcher, command palette trigger.
- UX-DR18: `BottomRibbon` (MVP minimal) — agent pulse, SLA, quick actions.

**Flagship visualizations:**

- UX-DR19: `UBOCanvas` — force-directed react-flow graph with confidence-banded edges; drag-correct-and-teach interaction with named learning-event ledger entry.
- UX-DR20: `RiskScoreBar` — stacked-bar component-level decomposition on hover; animated delta on officer edit.
- UX-DR21: `ScreeningExplainer` — 3-column "what matched / what didn't / counterfactual" card.

**Mode & navigation:**

- UX-DR22: `ModeSwitcher` (⌘+1–⌘+6) — MVP supports Investigation + SAR/EDD Zen; density-gradient visual shift between modes.
- UX-DR23: `CommandPalette` (⌘K) — universal action entrypoint (mode switch, find case, agent re-run, export).
- UX-DR24: Keyboard triage loop (`j` next · `k` previous · `Enter` open · `x` defer · `d` done) within QueueRail.
- UX-DR25: Keyboard shortcut help overlay (`?`) showing mode-specific shortcuts.

**Decision experience:**

- UX-DR26: SAR/EDD Zen mode — dark canvas, evidence dock right, typography enlarged, minimal chrome.
- UX-DR27: `UndoPill` with 120-second countdown ring + reason-capture modal (≥ 40 chars).
- UX-DR28: Seal animation on commit — subtle, 400 ms ease-out.
- UX-DR29: Auto-save throughout — no Save buttons anywhere in cockpit.

**Audit / Compliance experience:**

- UX-DR30: `AuditTrailTimeline` interleaving agent + officer actions with timestamps and signatures.
- UX-DR31: `RegulatorLensFrame` — read-only, audit-styled reframing of canvas.
- UX-DR32: `LedgerViewer` — cryptographic hash chain visualization with signature verification status.
- UX-DR33: `EvidenceShelf` — Evidence Bundle shelf with attachment ingest UI.

**Mesh visibility:**

- UX-DR34: Live agent activity feed with status pills (done/in-progress/blocked/needs-input) for each MVP agent.

**Foundation experience:**

- UX-DR35: Single-page-app spatial continuity — no page reloads, only within-app transitions.
- UX-DR36: WCAG 2.2 AA compliance with `axe-core` integrated into Playwright e2e tests on every canonical flow.
- UX-DR37: Color contrast ratios ≥ 4.5:1 for body text, ≥ 3:1 for UI chrome and non-text indicators.
- UX-DR38: i18n scaffolding via `react-i18next` with English-only catalog at MVP; locale-aware date/number formatting via `Intl.*`.

### FR Coverage Map

| FR | Epic | Notes |
|---|---|---|
| FR1 | Epic 2 (basic) → Epic 4 (full) | queue ordering — basic created_at in Epic 2, full risk × SLA × continuity in Epic 4 |
| FR2 | Epic 4 | keyboard nav (j/k/x/d/Enter) |
| FR3 | Epic 3 | intake-complete on case open |
| FR4 | Epic 4 (Investigation only) → Epic 8 (Zen added) | mode switch ⌘+1–6 |
| FR5 | Epic 4 | ⌘K command palette |
| FR6 | Epic 4 | in-app notifications |
| FR7 | Epic 3 (basic) → Epic 5 (UBO + Risk panels) → Epic 6 (Screening panel) | collapsible canvas panels |
| FR8 | Epic 3 | provenance pill on every datum |
| FR9 | Epic 7 (basic) → Epic 8 (full attachment ingest) | evidence shelf |
| FR10 | Epic 3 | 4-tier confidence band |
| FR11 | Epic 4 | live agent activity feed |
| FR12 | Epic 6 | reasoning trace with counterfactual |
| FR13 | Epic 6 | Cockpit Chat with mesh-as-tools |
| FR14 | Epic 3 | auto-run intake agents on case creation |
| FR15 | Epic 5 | UBO graph + nominee/shell heuristics |
| FR16 | Epic 5 | drag-correct-and-teach learning event |
| FR17 | Epic 5 | Entity Verification cross-references MCA/GST |
| FR18 | Epic 6 | Screening evaluation |
| FR19 | Epic 6 | Screening Explainer 3-column |
| FR20 | Epic 5 | Risk Score decomposition |
| FR21 | Epic 5 | risk auto-recalc on officer edit |
| FR22 | Epic 7 | Decision Zone editable rationale |
| FR23 | Epic 7 | 120s undo |
| FR24 | Epic 7 | commit outcomes (approve/decline/conditions/escalate) |
| FR25 | Epic 8 | SAR/EDD Zen mode UI |
| FR26 | Epic 8 | Writing agent EDD memo drafter |
| FR27 | Epic 7 | edit-rate metric tracking |
| FR28 | Epic 3 | agent action ledger entries |
| FR29 | Epic 7 | officer-signed ledger entries |
| FR30 | Epic 9 | case timeline (interleaved agent + officer actions) |
| FR31 | Epic 3 | immutable docs + SHA-256 hashes |
| FR32 | Epic 3 | no app-level ledger writes/deletes |
| FR33 | Epic 9 | Regulator Lens read-only mode |
| FR34 | Epic 9 | PDF + JSON audit bundle export |
| FR35 | Epic 9 | offline verification tool |
| FR36 | Epic 10 | Team Lead approval queue |
| FR37 | Epic 10 | approve-with-conditions structured state |
| FR38 | Epic 10 | full agent + officer history view |
| FR39 | Epic 8 | EDD outcome auto-enqueues for Lead approval |
| FR40 | Epic 10 | CCO Portfolio Dashboard |
| FR41 | Epic 10 | cohort summary export |
| FR42 | Epic 2 | case ingest API |
| FR43 | Epic 2 | document upload (presigned/multipart) |
| FR44 | Epic 2 | webhook dispatch |
| FR45 | Epic 2 | case retrieval API |
| FR46 | Epic 2 | idempotent case creation |
| FR47 | Epic 1 | OIDC / SAML SSO |
| FR48 | Epic 1 | deny-by-default RBAC |
| FR49 | Epic 1 | tenant isolation |
| FR50 | Epic 10 | break-glass with signed justification |
| FR51 | Epic 1 | session inactivity timeout |
| FR52 | Epic 11 | screening vendor config (runbook) |
| FR53 | Epic 11 | jurisdiction config (runbook) |
| FR54 | Epic 11 | per-tenant feature flags |
| FR55 | Epic 3 | agent failure isolation (foundational pattern) |
| FR56 | Epic 3 | adapter conformance (foundational pattern) |

**All 56 FRs covered. No gaps.**

## Epic List

### Epic 1 — Foundations & First Sign-In

A KYC Analyst can log in via the bank's IdP, land on the cockpit shell with their tenant context, and sign out cleanly. No domain logic yet — auth, tenant scoping, RBAC, design tokens, and the polyglot monorepo scaffold are all in place.

**FRs covered:** FR47, FR48, FR49, FR51
**ARs covered:** AR1, AR3, AR9, AR10, AR11, AR13, AR14, AR22, AR23, AR24, AR26, AR28
**UX-DRs covered:** UX-DR1, UX-DR2, UX-DR3, UX-DR4, UX-DR5, UX-DR12, UX-DR35, UX-DR36, UX-DR37, UX-DR38

### Epic 2 — Case Ingest & Lifecycle

External systems (core banking) can submit a case via authenticated REST API; cases appear in the analyst's queue with metadata and document references; webhook callbacks fire on state changes. No agents yet.

**FRs covered:** FR1 (basic), FR42, FR43, FR44, FR45, FR46
**ARs covered:** AR8, AR27
**UX-DRs covered:** UX-DR13 (basic QueueRail rendering)

### Epic 3 — First Agent & Cryptographic Audit Ledger

When a case arrives, Document Intelligence extracts fields automatically; the analyst opens the case and sees data with provenance pills and confidence bands; every agent action is signed and ledgered. The foundational pluggable adapter + ledger + provenance pattern is established here.

**FRs covered:** FR3, FR7 (basic docs panel), FR8, FR10, FR14, FR28, FR31, FR32, FR55, FR56
**ARs covered:** AR2 (first uses: doc-AI, doc-store, key-vault, secrets adapters), AR4, AR12 (HSM signing for agent actions), AR20, AR25, AR30
**UX-DRs covered:** UX-DR8, UX-DR9, UX-DR14 (CaseCanvas with documents panel)

### Epic 4 — Triage Mode & Live Mesh Visibility

Analyst navigates the queue with keyboard (j/k/x/d), opens cases instantly, sees agent status updates streaming in real time via SSE, and uses ⌘K to invoke any action. The cockpit "comes alive."

**FRs covered:** FR1 (full ordering), FR2, FR4 (Investigation only), FR5, FR6, FR11
**ARs covered:** AR6, AR7
**UX-DRs covered:** UX-DR6, UX-DR7, UX-DR11, UX-DR13 (full QueueRail), UX-DR15, UX-DR17, UX-DR18, UX-DR22 (Investigation), UX-DR23, UX-DR24, UX-DR25, UX-DR29, UX-DR34

### Epic 5 — Entity & UBO Investigation

Analyst sees UBO ownership rendered as a force-directed graph, drag-corrects nominee structures with a learning-event ledger entry, watches risk score recalculate. MCA + GST entity verification surfaces mismatches.

**FRs covered:** FR7 (UBO + Risk panels), FR15, FR16, FR17, FR20, FR21
**ARs covered:** AR2 (more adapters)
**UX-DRs covered:** UX-DR19, UX-DR20

### Epic 6 — Screening, Reasoning Traces & Conversational Mesh

Analyst clicks any agent finding to open a 4-section reasoning trace including the counterfactual; screening hits show as a 3-column explainer; analyst converses with the Cockpit Chat agent for case context.

**FRs covered:** FR7 (Screening panel), FR12, FR13, FR18, FR19
**ARs covered:** AR2 (screening adapter — mock + ComplyAdvantage), AR19
**UX-DRs covered:** UX-DR10, UX-DR21

### Epic 7 — Decision Authoring & Officer Signing

Analyst edits an agent-drafted rationale in the Decision Zone, commits with WebCrypto Ed25519 signature, has 120 seconds to undo. Edit-rate metric tracks how much officer work was on top of the agent draft.

**FRs covered:** FR9 (basic evidence access), FR22, FR23, FR24, FR27, FR29
**ARs covered:** AR12 (officer keypair + WebCrypto), AR29 partial
**UX-DRs covered:** UX-DR16, UX-DR27, UX-DR28

### Epic 8 — SAR/EDD Zen Mode & Narrative Drafting

Analyst enters Zen mode (⌘+4) — dark canvas, evidence docks right, typography enlarges. Writing agent drafts an EDD memo citing ledger entries by ID. Analyst edits the narrative and commits, automatically queueing the case for Team Lead approval.

**FRs covered:** FR9 (full evidence shelf), FR25, FR26, FR39
**UX-DRs covered:** UX-DR22 (Zen mode added), UX-DR26, UX-DR33

### Epic 9 — Audit Trail, Regulator Lens & Offline Verifier

Internal Auditor opens cases in Regulator Lens mode (read-only, audit-styled); exports cases as PDF + JSON bundle; the offline verifier tool validates the hash chain and signatures without calling the platform.

**FRs covered:** FR30, FR33, FR34, FR35
**ARs covered:** AR5
**UX-DRs covered:** UX-DR30, UX-DR31, UX-DR32

### Epic 10 — Multi-Role Workflows (Approvals & Portfolio)

Team Lead approves/conditions/declines EDD cases from a dedicated queue; CCO sees portfolio dashboard with audit-readiness indicator; Tenant Admin can perform break-glass access via signed runbook.

**FRs covered:** FR36, FR37, FR38, FR40, FR41, FR50
**ARs covered:** AR17

### Epic 11 — Pilot Hardening

System is pilot-ready. Mock internal audit returns zero remediation. Threat model authored. External pentest done with Critical/High remediated. DR rehearsal passed. WCAG 2.2 AA third-party audit passed. Performance budgets verified across canonical journeys. Confidence thresholds calibrated.

**FRs covered:** FR52, FR53, FR54 (config-driven runbooks; FR55/FR56 already verified end-to-end)
**ARs covered:** AR15, AR16, AR18, AR21, AR29 (full study)
**UX-DRs covered:** UX-DR36 (full WCAG audit completion)
**NFR validation:** All NFRs explicitly verified — performance budgets, security baseline, accessibility audit, observability dashboards, compliance readiness.

---

## Epic 1: Foundations & First Sign-In

A KYC Analyst can log in via the bank's IdP, land on a cockpit shell scoped to their tenant, and sign out cleanly. No domain logic — but auth, tenant scoping, RBAC, design tokens, and the polyglot monorepo are all real.

### Story 1.1: Bootstrap the polyglot monorepo from the canonical scaffold

As a developer joining the project,
I want the polyglot monorepo (Vite + ADK + FastAPI + Poetry + pnpm) scaffolded per the architecture decision document,
So that every subsequent story has a place to live and the codebase reads cleanly as a reference implementation.

**Acceptance Criteria:**

**Given** the architecture document specifies the scaffold (AR1) and Step 3 of `architecture.md` has the exact init commands
**When** I run the README's "first-time setup" section in a clean clone
**Then** `apps/cockpit-ui/` contains a Vite + React + TS strict project with `@radix-ui/react-*`, `framer-motion`, `lucide-react`, `reactflow`, `tailwindcss`, `postcss`, `autoprefixer` installed
**And** `apps/cockpit-api/` contains a Poetry-managed FastAPI 0.115+ project with `pydantic`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic` dependencies
**And** `apps/agents/` contains a Poetry-managed `ibm-watsonx-orchestrate` project with the ADK init scaffold completed
**And** `packages/contracts/` exists as a minimal Poetry project with `pydantic` only
**And** `tools/verifier/` exists as a minimal Poetry project with `cryptography` + `pydantic` only
**And** `pnpm-workspace.yaml` at the root registers `apps/cockpit-ui`
**And** the root contains `Makefile`, `.gitignore`, `.editorconfig`, `.pre-commit-config.yaml`, `.env.example`, `README.md`

**Given** the repo is fresh
**When** I run `pnpm install` in `apps/cockpit-ui/`
**Then** install succeeds with zero warnings

**Given** the repo is fresh
**When** I run `poetry install` inside each Python subproject
**Then** each install succeeds and writes a `poetry.lock`

### Story 1.2: One-command local development environment

As a developer who has just cloned the repo,
I want a single command that brings up all dependencies plus the cockpit-api, agents runtime, and cockpit-ui in dev mode,
So that I am demoing the project within 30 minutes of clone (NFR-RI5).

**Acceptance Criteria:**

**Given** the scaffold from Story 1.1 is in place
**When** I run `docker compose up -d` followed by `make bootstrap` then `make dev`
**Then** Postgres 16, Redis, LocalStack (S3 emulator), Vault Transit (HSM emulator), and the ADK Developer Edition are running in containers
**And** `cockpit-api` is serving on `http://localhost:8000` with `/docs` reachable
**And** `cockpit-ui` is serving on `http://localhost:5173` with HMR working

**Given** a developer unfamiliar with the project
**When** they follow only the README from clone
**Then** they reach a "hello cockpit" screen in their browser within 30 minutes

**Given** Postgres is running
**When** I run `make migrate` then `make seed`
**Then** the dev tenant schema is created with sample empty tables and one demo tenant + one demo officer user

### Story 1.3: CI/CD skeleton with OIDC-federated cloud creds

As the project maintainer,
I want a CI pipeline that lints, type-checks, tests, and produces container images on every PR,
So that the architecture's quality gates (Ruff, mypy, ESLint, TS strict, Vitest, pytest) are continuously enforced.

**Acceptance Criteria:**

**Given** a PR is opened against `main`
**When** GitHub Actions runs `ci.yml`
**Then** it runs `make lint` and `make test` and fails on any error
**And** total CI runtime for a clean PR is ≤ 5 minutes

**Given** the workflow needs cloud credentials
**When** it authenticates to IBM Cloud
**Then** it uses OIDC-federated short-lived tokens (AR22)
**And** zero long-lived secrets exist in the GitHub repo

**Given** a PR modifies code in `apps/cockpit-api/`
**When** the contracts workflow runs
**Then** it regenerates `packages/contracts/openapi.json` and `apps/cockpit-ui/src/api-types.ts` and fails the PR if either differs from the committed version (drift detection per A10/F13)

### Story 1.4: ADR discipline and architecture documentation skeleton

As a future contributor evaluating the codebase,
I want every non-trivial design decision to live as a numbered ADR in `docs/adr/`,
So that decisions are traceable to rationale and the reference-implementation thesis (NFR-RI2) is honored.

**Acceptance Criteria:**

**Given** the repo from Story 1.1
**When** I open `docs/adr/`
**Then** I find ADRs 0001–0008 already authored (mirroring decisions in `architecture.md`)
**And** an `0000-template.md` exists with the canonical ADR structure (Status / Context / Decision / Consequences)

**Given** any developer is writing a new decision
**When** they run `make adr-new title="my-decision"`
**Then** a new sequentially numbered ADR file is created from the template

**Given** `docs/architecture/` exists
**When** I look inside
**Then** `overview.md`, `data-flow.md`, `tenant-isolation.md`, and a `threat-model.md` placeholder are present

### Story 1.5: Postgres tenant-schema isolation primitives

As the platform,
I want `tenant_id` to be a hard isolation primitive at the database layer,
So that no query can ever cross a tenant boundary by accident (FR49).

**Acceptance Criteria:**

**Given** the dev Postgres is running
**When** the first migration runs
**Then** a `tenants` table exists in the public schema with: `id` (UUID v4), `name`, `created_at`, `signing_public_key` (Ed25519 PEM), `idp_config_json`
**And** helpers in `apps/cockpit-api/src/cockpit_api/db/tenant_schemas.py` exist to derive a per-tenant schema name

**Given** a function in `cockpit-api` reads or writes case data
**When** that function is called without a `tenant_id` keyword argument
**Then** a custom Ruff rule fails the lint check
**And** at runtime, the DB session helper raises `TenantScopeError` if a query is built without a `tenant_id` filter on a tenant-scoped table

### Story 1.6: OIDC authentication with cookie session

As a KYC Analyst,
I want to log in using my bank's identity provider (OIDC),
So that I authenticate with credentials I already have (FR47).

**Acceptance Criteria:**

**Given** a tenant has an OIDC IdP configured
**When** I navigate to `/t/{tenant_id}/login`
**Then** I am redirected to the IdP's authorization endpoint
**And** after successful authentication I am returned to `/t/{tenant_id}/auth/callback`
**And** the cockpit-api creates a server-side session in Redis keyed by an opaque session token
**And** sets an `HttpOnly`, `Secure`, `SameSite=Strict` cookie containing only the session token

**Given** I am logged in
**When** I make a request to a protected endpoint
**Then** the session is loaded from Redis using the cookie and my user ID + role attached to the request context

**Given** I click "Sign Out"
**When** the request hits `/t/{tenant_id}/auth/logout`
**Then** the Redis session is deleted, the cookie is cleared, and I am redirected to a public sign-out page

### Story 1.7: Deny-by-default RBAC dependency

As the platform,
I want every API route to require an explicit role declaration,
So that protected resources fail closed by default (FR48).

**Acceptance Criteria:**

**Given** a FastAPI route in `cockpit-api`
**When** the route does not declare `Depends(require_role(...))`
**Then** access is denied with a 401 response (deny-by-default)
**And** a custom Ruff rule warns at lint time about routes missing role declaration

**Given** a route declares `Depends(require_role("kyc_analyst"))`
**When** I am authenticated as a `kyc_analyst`
**Then** the request succeeds
**When** I am authenticated with any other role
**Then** the request fails with 403 RFC 7807 Problem Details

**Given** the role matrix lives in `services/rbac.py`
**When** I read the file
**Then** I see a typed `RoleMatrix` mirroring the PRD's six-role matrix
**And** unit tests cover at least one positive + one negative case per role × resource

### Story 1.8: Tenant scoping middleware

As the platform,
I want every authenticated request to carry an authoritative `tenant_id` from the URL path validated against the user's session,
So that tenant scoping is enforced at the API boundary (P2).

**Acceptance Criteria:**

**Given** a route mounted under `/t/{tenant_id}/v1/...`
**When** a request arrives
**Then** middleware extracts `tenant_id` from the path
**And** validates it matches the authenticated session's `tenant_id`
**And** raises 403 RFC 7807 + logs a security event if mismatched (NFR-O6)
**And** attaches `tenant_id` to request state for downstream dependencies

**Given** a request arrives without `tenant_id` in the path on a tenant-scoped route
**Then** the middleware rejects with 404 (don't leak tenant route existence)

### Story 1.9: Session inactivity timeout

As the platform,
I want sessions to expire after a configured period of inactivity,
So that abandoned sessions cannot be hijacked (FR51, NFR-T2).

**Acceptance Criteria:**

**Given** the default inactivity timeout is 30 minutes (configurable per tenant within [15, 60])
**When** a session has been idle for 30 minutes
**Then** the next request is rejected with 401 (RFC 7807 with `type=session_expired`)
**And** the session is deleted from Redis
**And** the cockpit-ui detects 401, redirects me to the IdP for re-auth, and returns me to the route I was on

**Given** a session is active
**When** a request is processed
**Then** the session's `last_activity` timestamp is updated in Redis with a TTL refresh

### Story 1.10: Empty cockpit shell with auth-protected routes

As an authenticated KYC Analyst,
I want to see a recognizable cockpit shell with the six-zone scaffold and "marble and spring flowers" visual language,
So that the foundation is visible and ready for subsequent epics to fill in.

**Acceptance Criteria:**

**Given** I have logged in
**When** I land on `/t/{tenant_id}/queue`
**Then** I see the six-zone layout: Queue Rail (left, 260 px, empty list), Top Bar (with my name + sign-out + tenant indicator), Case Canvas (center, "no case selected" empty state), Agent Copilot Pane (right, 320 px, empty), Decision Zone placeholder, Bottom Ribbon
**And** Tailwind 4 `@theme` tokens are applied (UX-DR1)
**And** typography hierarchy follows UX-DR2; spacing/radii/shadows follow UX-DR3, UX-DR4
**And** three motion utilities (`expand`, `focus-dim`, `slide-out`) are exported from `lib/motion.ts` (UX-DR11)

**Given** I press `Tab` repeatedly
**When** focus moves through interactive elements
**Then** every focusable element shows a high-contrast persistent focus indicator (UX-DR12, NFR-AC5)

**Given** my role is not `kyc_analyst`
**When** I attempt `/t/{tenant_id}/queue`
**Then** I am denied with 403 and redirected to a role-appropriate route (or sign-out if none applies)

### Story 1.11: i18n scaffolding and locale-aware formatting

As a future operator who needs to deploy in non-English markets,
I want the cockpit's strings externalized and `Intl.*` formatting in place from day one,
So that adding Hindi or any regional language post-MVP is a translation task (NFR-AC6, UX-DR38).

**Acceptance Criteria:**

**Given** the cockpit-ui from Story 1.10
**When** I inspect the codebase
**Then** every visible string is keyed via `react-i18next`
**And** an English (`en`) catalog exists at `apps/cockpit-ui/src/locales/en/common.json`
**And** dates are formatted with `Intl.DateTimeFormat`, numbers with `Intl.NumberFormat`, currencies with `Intl.NumberFormat({style:'currency', currency:...})`

**Given** a string is added without going through `useTranslation`
**When** `make lint` runs
**Then** ESLint flags it with a custom rule

## Epic 2: Case Ingest & Lifecycle

External systems (core banking) can submit a case via authenticated REST API; cases appear in the analyst's queue with metadata and document references; webhook callbacks fire on state changes. No agents yet.

### Story 2.1: Case schema and state machine

As the platform,
I want a typed `Case` aggregate and a persisted state machine,
So that ingest, processing, and decision flows have a canonical lifecycle (FR42, FR45).

**Acceptance Criteria:**

**Given** Alembic migrations
**When** I run `make migrate`
**Then** a `cases` table exists per tenant schema with columns: `id` (`case_<ULID>`), `tenant_id`, `state` (enum: `intake_scheduled`, `decision_ready`, `committed`, `escalated`, `closed`), `customer_metadata` (JSONB), `assigned_to_user_id` (nullable), `risk_band` (nullable), `created_at`, `updated_at`, `closure_date` (nullable)
**And** a Pydantic `Case` model lives in `packages/contracts/case.py` mirroring the schema

**Given** the state machine
**When** code attempts an invalid transition (e.g., `closed → intake_scheduled`)
**Then** a `CaseStateTransitionError` is raised and logged

**Given** the state machine documentation
**When** I read `docs/architecture/data-flow.md`
**Then** the case state diagram is documented with allowed transitions

### Story 2.2: POST /v1/cases ingestion endpoint

As an integration developer at a partner bank,
I want to submit a new case via authenticated REST API including customer metadata and document references,
So that the cockpit ingests cases from our core banking system (FR42).

**Acceptance Criteria:**

**Given** an authenticated API consumer
**When** they POST to `/t/{tenant_id}/v1/cases` with a Pydantic-validated body (customer metadata + document references)
**Then** a new `Case` row is created with state `intake_scheduled`
**And** the response is `201` with `{ case_id, state, _links }` and an idempotency-key header echoed back
**And** the OpenAPI spec at `/docs` (Scalar) shows the schema accurately

**Given** a malformed body
**When** the request is rejected
**Then** the response is 422 RFC 7807 with `detail` listing each Pydantic validation error

**Given** an API consumer with the `api_consumer` role
**When** they attempt to POST to a tenant they don't have scope for
**Then** the request is rejected with 403

### Story 2.3: Idempotent case creation

As an integration developer,
I want to safely retry a `POST /cases` request without creating duplicates,
So that network blips during ingestion don't pollute the case ledger (FR46).

**Acceptance Criteria:**

**Given** I include `X-Cockpit-Idempotency-Key: <ULID>` on a POST `/cases` request
**When** the first request succeeds
**Then** the same key + request body returned within 24h returns 200 (not 201) with the same `case_id`

**Given** the same idempotency key is sent with a different request body
**When** the request is processed
**Then** it is rejected with 409 Conflict + RFC 7807 `detail` explaining "idempotency key reused with different payload"

**Given** an idempotency key is missing on POST
**Then** the request still succeeds (idempotency is opt-in) but a `Warning` header notes that retries cannot be safely deduplicated

### Story 2.4: Document upload via presigned URL flow

As an integration developer,
I want to upload supporting documents as part of case ingestion using presigned URLs,
So that large files don't transit through cockpit-api (FR43).

**Acceptance Criteria:**

**Given** an authenticated API consumer who has just received a `case_id`
**When** they POST to `/t/{tenant_id}/v1/cases/{case_id}/documents/presigned` with `{ filename, mime_type, size }`
**Then** they receive a presigned PUT URL valid for 15 minutes pointing at the tenant's S3-compatible bucket via the `DocStore` adapter

**Given** a document is uploaded via presigned URL
**When** the upload completes
**Then** the cockpit-api receives an S3 event (or polled signal) and records a `documents` row with: `id` (`doc_<ULID>`), `case_id`, `tenant_id`, `s3_key`, `sha256`, `uploaded_at`, `mime_type`, `size`
**And** the SHA-256 is computed by the API on first read and stored alongside (FR31)

**Given** a document is uploaded with a mime type outside the allowed list (configurable per tenant)
**When** the document record is created
**Then** the document is marked `quarantined` and a security event is logged

### Story 2.5: GET case retrieval (API consumer)

As an integration developer,
I want to fetch a case by ID via authenticated REST API,
So that our core banking system can poll case state and decision (FR45).

**Acceptance Criteria:**

**Given** an authenticated API consumer with scope on a tenant
**When** they GET `/t/{tenant_id}/v1/cases/{case_id}`
**Then** they receive the case payload (Pydantic-serialized) including current state, risk_band, decision (if any), and `_links` to documents and reasoning traces

**Given** an API consumer who created a case via POST
**When** they retrieve only that case (their scope is limited to ingests they originated)
**Then** they cannot enumerate other cases in the tenant via API

**Given** a case ID that does not exist or belongs to a different tenant
**Then** the response is 404 (don't leak existence)

### Story 2.6: Case appears in Queue Rail (basic ordering)

As a KYC Analyst,
I want newly ingested cases to appear in my Queue Rail ordered by creation time,
So that I have a queue to work from even before risk-scoring agents exist (FR1 basic).

**Acceptance Criteria:**

**Given** I am logged in as a KYC Analyst (Story 1.6) and viewing the Queue Rail (Story 1.10)
**When** a case is ingested via POST `/cases`
**Then** within ≤ 2 seconds the new case appears in my Queue Rail row list (driven by SSE — but full SSE infra lands in Epic 4; for Epic 2, use TanStack Query polling at 5s interval as a placeholder, replaced in Story 4.6)
**And** the row shows: customer name, ingested-at timestamp, current state badge

**Given** the basic ordering is `created_at DESC`
**When** I open Queue Rail
**Then** newer cases appear at the top
**And** the architecture's risk × SLA × continuity ordering is deferred to Story 4.1

### Story 2.7: Webhook subscription configuration per tenant

As a Tenant Admin (via runbook),
I want to configure outbound webhook callbacks per tenant for case state changes and decision events,
So that core banking systems get notified (FR44 part 1).

**Acceptance Criteria:**

**Given** the tenant config schema includes a `webhook_subscriptions` array (event_type, callback_url, hmac_secret_id)
**When** I run the tenant config CLI runbook
**Then** I can register a webhook for `case.decision_ready`, `case.committed`, `case.escalated` events
**And** `hmac_secret_id` references a Secrets Manager binding (no raw secret in DB)

**Given** an existing subscription
**When** I update its callback URL
**Then** future events fire to the new URL; in-flight events to the old URL still complete or retry per Story 2.9

### Story 2.8: Outbound webhook dispatch with HMAC signing

As an integration developer,
I want webhook payloads to be HMAC-signed so I can verify they came from the cockpit,
So that I trust the events I act on (FR44 part 2, AR2 webhook adapter).

**Acceptance Criteria:**

**Given** a case state transition fires an event
**When** the event reaches `services/webhook_dispatcher.py`
**Then** the payload is enqueued to Arq (D9)
**And** the worker dispatches an HTTP POST to the registered callback URL with header `X-Cockpit-Signature: sha256=<hex>` over the canonical JSON body using the per-tenant HMAC secret
**And** `X-Cockpit-Idempotency-Key: whd_<ULID>` is set on every dispatch

**Given** I am the receiver
**When** I receive a webhook
**Then** I can verify HMAC-SHA256 against the documented canonical-JSON algorithm and reject mismatches

### Story 2.9: At-least-once webhook retry

As an integration developer,
I want webhook delivery to retry on transient failures with exponential backoff and idempotency keys,
So that a brief network blip doesn't lose an event (A7).

**Acceptance Criteria:**

**Given** a webhook dispatch fails with 5xx or network error
**When** the worker handles the failure
**Then** it retries on schedule 1s → 5s → 25s → 125s and gives up after 1 hour
**And** every attempt sends the same `X-Cockpit-Idempotency-Key`, allowing the receiver to dedupe

**Given** a 4xx response from the receiver
**Then** the dispatch is **not retried** (4xx is the receiver's contract violation, not a transient error)
**And** a delivery-failure ledger entry is created

**Given** all retries exhausted
**Then** a `webhook.delivery_failed` event is emitted to observability and a `notifications` row is created for the Tenant Admin

### Story 2.10: API rate limiting middleware

As the platform,
I want per-key/IP/endpoint rate limiting to protect against abuse,
So that one misbehaving client doesn't degrade service for others (NFR-S1).

**Acceptance Criteria:**

**Given** a tenant has the default rate limit (100 req/min, burst 500) configured
**When** a single API key exceeds 100 req/min
**Then** the next request is rejected with 429 RFC 7807 + `Retry-After` header
**And** the Redis-backed token bucket state is per `(tenant_id, api_key, endpoint)` triple

**Given** a tenant requests a higher limit
**When** an admin updates the tenant config
**Then** the new limit takes effect within 30s without service restart

### Story 2.11: OpenAPI export and Scalar docs serving

As an integration developer reviewing the API contract,
I want a beautiful, navigable docs UI generated from the live API,
So that I can quickly understand and integrate (A4, AR8).

**Acceptance Criteria:**

**Given** the cockpit-api is running
**When** I visit `/docs`
**Then** I see Scalar rendering the OpenAPI 3.1 spec
**And** every endpoint shows: method, path, request schema, response schema, error responses (RFC 7807), example payloads

**Given** any code change in `apps/cockpit-api/src/cockpit_api/routers/`
**When** `make contracts` runs
**Then** `packages/contracts/openapi.json` is regenerated
**And** `apps/cockpit-ui/src/api-types.ts` is regenerated via `openapi-typescript`
**And** CI fails the PR if either differs from committed (drift detection)

## Epic 3: First Agent & Cryptographic Audit Ledger

When a case arrives, Document Intelligence extracts fields automatically; the analyst opens the case and sees data with provenance pills and confidence bands; every agent action is signed and ledgered. The foundational pluggable adapter + ledger + provenance pattern is established here.

### Story 3.1: Cryptographic ledger schema with INSERT-only role

As the platform,
I want a tamper-evident ledger schema with database-level INSERT-only enforcement,
So that no app code (buggy or malicious) can mutate ledger entries (D6, FR32).

**Acceptance Criteria:**

**Given** Alembic migrations
**When** `make migrate` runs
**Then** a `ledger` schema exists per tenant with a `ledger_entries` table including: `id` (`led_<ULID>`), `tenant_id`, `case_id`, `actor_type` (`agent` | `officer` | `system`), `actor_id`, `payload` (JSONB), `prev_hash` (sha256), `chain_hash` (sha256), `signature` (Ed25519), `signing_key_id`, `created_at`
**And** a Postgres role `ledger_writer` exists per tenant with INSERT-only privileges on `ledger_entries`
**And** DB triggers `BEFORE UPDATE OR DELETE ON ledger_entries RAISE EXCEPTION` are installed

**Given** I attempt an UPDATE or DELETE on `ledger_entries` from any session
**Then** the operation fails with the trigger-raised exception

### Story 3.2: KeyVault adapter Protocol with Vault Transit (dev) impl

As the platform,
I want a pluggable `KeyVault` interface with a working dev implementation against Vault Transit,
So that signing operations work locally and the production HPCS impl is a drop-in replacement (S1, P1).

**Acceptance Criteria:**

**Given** `packages/contracts/key_vault.py`
**When** I read it
**Then** I see a `KeyVault` Protocol with methods `sign(payload: bytes, *, tenant_id: TenantId) -> Ed25519Signature`, `verify(payload: bytes, signature: Ed25519Signature, *, tenant_id: TenantId) -> bool`, `get_public_key(*, tenant_id: TenantId) -> Ed25519PublicKey`

**Given** `apps/cockpit-api/src/cockpit_api/adapters/key_vault/vault_transit.py`
**When** I run `docker compose up vault`
**Then** the Vault Transit adapter implements the Protocol and uses Vault's signing API
**And** unit tests mock the HTTP calls

**Given** `apps/cockpit-api/tests/contract/key_vault_contract.py`
**When** the contract suite runs
**Then** every `KeyVault` implementation must pass: sign-then-verify roundtrip, signature mismatch detection, tenant isolation

### Story 3.3: KeyVault HPCS implementation + conformance pair

As the platform deployed to IBM Cloud,
I want an HPCS-backed `KeyVault` impl that passes the same conformance suite as the Vault Transit impl,
So that production signing uses FIPS 140-2 Level 4 hardware (S1, NFR-RI6).

**Acceptance Criteria:**

**Given** the HPCS adapter at `apps/cockpit-api/src/cockpit_api/adapters/key_vault/ibm_hpcs.py`
**When** I run the contract conformance suite (Story 3.2) against this adapter (with a sandbox HPCS instance)
**Then** all conformance tests pass

**Given** environment variable `KEY_VAULT_PROVIDER=ibm_hpcs`
**When** the cockpit-api starts
**Then** the HPCS adapter is wired in via Pydantic Settings dependency injection

**Given** a tenant onboarding event
**When** the runbook generates a tenant signing key
**Then** the key is created and stored in HPCS, never appears in plaintext outside the HSM

### Story 3.4: Ed25519 hash chain primitive in ledger_service

As the platform,
I want a `LedgerService` that appends entries with hash chaining and Ed25519 signing,
So that every ledger entry is tamper-evident and offline-verifiable (FR28, D6).

**Acceptance Criteria:**

**Given** the `LedgerService.append(entry: LedgerEntryInput, *, tenant_id: TenantId)` method
**When** called with a payload
**Then** the service computes `chain_hash = sha256(prev_hash || canonical_json(payload))` where `prev_hash` is the chain_hash of the most recent entry for the tenant (or genesis hash for the first)
**And** signs `chain_hash` with the tenant's HSM key via the `KeyVault` adapter
**And** persists the entry under the `ledger_writer` role in a single transaction (NFR-A6 atomicity)

**Given** two entries appended concurrently for the same tenant
**When** the transaction completes
**Then** the chain remains linear (one entry's `chain_hash` is the next entry's `prev_hash`)
**And** Postgres advisory lock per tenant prevents race conditions

**Given** a verifier walking the chain
**When** any byte in any entry is altered post-write
**Then** verification fails at the first altered entry

### Story 3.5: Agent Action decorator (P4)

As an agent author,
I want a `@ledgered_action` decorator that automatically writes a `AgentActionLedgerEntry` for every agent invocation,
So that I cannot accidentally produce data without a ledger trail (P4).

**Acceptance Criteria:**

**Given** an agent function decorated with `@ledgered_action(agent_id="document_intelligence")`
**When** I call the agent
**Then** before the agent's logic runs, a "started" record is held in memory
**And** after the agent returns, the decorator captures input, output, model_id, prompt_template_id, prompt_hash, tool_calls, started_at, completed_at, signs via LedgerService, and persists the entry

**Given** the agent raises an exception
**Then** the decorator catches it, persists a ledger entry with `output: {error: <type+message>}`, and re-raises a typed `AgentExecutionError` so the supervisor can flag (FR55, NFR-A5)

**Given** an agent author writes a new agent without the decorator
**When** they call `LedgerService.append` directly to bypass it
**Then** a custom Ruff rule blocks this pattern outside `agents/supervisor/action_decorator.py`

### Story 3.6: Pydantic contracts for ledger, provenance, confidence

As the platform,
I want canonical Pydantic models for `AgentActionLedgerEntry`, `ProvenancedField[T]`, and `ConfidenceBand`,
So that every agent and every UI render speaks the same wire format (P3, P4, P7).

**Acceptance Criteria:**

**Given** `packages/contracts/`
**When** I read it
**Then** I find `agent_action.py`, `provenance.py`, `confidence.py`, `ledger.py` matching the architecture document's code examples (P3, P4, P7)
**And** `ProvenancedField[T]` is generic and works with `T = str | int | float | dict | list[...]`

**Given** the `ConfidenceBand` enum
**When** I import it from JS
**Then** `openapi-typescript` produces the same enum for cockpit-ui

**Given** a `to_band(confidence: float) -> ConfidenceBand` helper
**When** I pass test thresholds (0.0, 0.39, 0.40, 0.64, 0.65, 0.84, 0.85, 1.0)
**Then** outputs are LOW, LOW, MEDIUM_LOW, MEDIUM_LOW, MEDIUM_HIGH, MEDIUM_HIGH, HIGH, HIGH (per architecture P7)

### Story 3.7: DocStore adapter with multi-cloud impls + conformance

As the platform,
I want pluggable document storage spanning IBM COS, AWS S3, and MinIO (local),
So that deployments can target the cloud most appropriate per tenant (D5, P1, NFR-RI6).

**Acceptance Criteria:**

**Given** `packages/contracts/doc_store.py` defines a `DocStore` Protocol with `presign_put`, `presign_get`, `head`, `compute_sha256`, `verify_sha256` methods, all `tenant_id`-scoped

**Given** three impls in `apps/cockpit-api/src/cockpit_api/adapters/doc_store/`: `ibm_cos.py`, `aws_s3.py`, `minio_local.py`
**When** the conformance suite runs against each
**Then** all pass: presign roundtrip, hash computation, tenant isolation, expiry semantics

**Given** environment variable `DOC_STORE_PROVIDER=minio_local`
**When** the cockpit-api starts in dev
**Then** documents land in LocalStack/MinIO

### Story 3.8: DocAI adapter with mock + IBM Document AI impls

As the platform,
I want a pluggable `DocAI` interface with a mock impl for dev/CI and an IBM Document AI impl for production,
So that document field extraction is swappable per the deferred decision (P1, AR2).

**Acceptance Criteria:**

**Given** `packages/contracts/doc_ai.py` defines a `DocAI` Protocol: `extract_fields(doc: DocumentRef, taxonomy: DocTaxonomy, *, tenant_id: TenantId) -> ExtractionResult`
**And** `ExtractionResult` returns a list of `ProvenancedField[FieldValue]` per detected field with confidence

**Given** `mock_doc_ai.py` returns deterministic fixtures keyed by document hash
**When** the conformance suite runs
**Then** input → output is reproducible across test runs

**Given** `ibm_document_ai.py` calls the IBM Document AI service
**When** the conformance suite runs against it (with a sandbox key)
**Then** all conformance tests pass

### Story 3.9: Document Intelligence agent

As the platform,
I want a Document Intelligence agent that extracts CoI, PAN, GST, bank statement, and utility bill fields with provenance and confidence,
So that the analyst sees structured intake data on case open (FR3, FR14, NFR-T5 ≥ 95%).

**Acceptance Criteria:**

**Given** a case has documents (Story 2.4) and the Case Supervisor (Story 3.10) fires intake
**When** the Document Intelligence agent is invoked through `@ledgered_action`
**Then** it calls the `DocAI` adapter with the India jurisdiction's `DocTaxonomy`
**And** returns a list of `ProvenancedField[FieldValue]` (e.g., `company_name`, `cin`, `pan`, `gstin`, `registered_address`, `incorporation_date`, etc.)
**And** writes a `AgentActionLedgerEntry` with the model_id, prompt_template_id, prompt_hash, full input, full output, signature

**Given** the corpus benchmark
**When** Story 3.11 runs the corpus
**Then** field-extraction precision is ≥ 95% for the chosen DocAI impl

### Story 3.10: Case Supervisor (intake fan-out)

As the platform,
I want a Case Supervisor agent that automatically fans out the intake mesh on case creation,
So that the analyst never sees a "loading" canvas and intake is always done by case-open time (FR14).

**Acceptance Criteria:**

**Given** a case is created via Story 2.2
**When** the case state transitions to `intake_scheduled`
**Then** the Case Supervisor agent is invoked
**And** it calls Document Intelligence (Story 3.9) — Entity Verification + UBO + Risk + Screening land in later epics
**And** when all intake agents complete, the Case Supervisor transitions the case to `decision_ready` and emits a webhook + SSE event

**Given** a single agent fails
**When** the Supervisor catches the typed `AgentExecutionError`
**Then** it marks the case as `intake_blocked` with the failed agent named
**And** the case appears in the queue with a clear "blocked: {agent}" badge (NFR-A5, FR55)
**And** the failure does not cascade to the other agents

### Story 3.11: 50-doc corpus benchmark for Document Intelligence

As the team validating MVP readiness,
I want a 50-document benchmark across IBM Document AI vs Watson Discovery (vs custom fallback),
So that we lock the doc-AI vendor based on measured precision (NFR-T5 ≥ 95%, AR20).

**Acceptance Criteria:**

**Given** 50 ground-truth-annotated SME onboarding documents (CoI, PAN, GST, bank statement, utility) at `apps/agents/tests/corpus/`
**When** I run `make benchmark-doc-ai`
**Then** for each adapter (ibm_document_ai, watson_discovery, mock-as-control), per-field precision and recall are reported
**And** field-level errors are surfaced for diff review

**Given** the benchmark output
**When** the team reviews
**Then** the chosen vendor is recorded in `docs/adr/00NN-doc-ai-stack.md`

### Story 3.12: Documents panel on Case Canvas with provenance pills

As a KYC Analyst,
I want to see extracted document fields on the Case Canvas with a provenance pill on every value,
So that I trust the source and can drill into reasoning (FR7 docs panel, FR8, P3).

**Acceptance Criteria:**

**Given** I open a case with intake complete (Story 3.10)
**When** the Case Canvas renders
**Then** I see a "Documents" panel listing extracted fields per document
**And** every field value displays a `ProvenanceIndicator` showing source agent, source system, confidence band
**And** clicking a provenance pill opens a placeholder reasoning trace stub (full slide-out lands in Epic 6)

**Given** the cockpit-ui is rendered
**When** any field is rendered without `ProvenancedField[T]`
**Then** a CI test failure surfaces (NFR-T4 100% provenance coverage)

### Story 3.13: ConfidencePill component

As a KYC Analyst,
I want confidence shown as a 4-tier banded pill (low / medium-low / medium-high / high),
So that I instantly see how much to trust each datum without reading numbers (FR10, NFR-AC3, P7, UX-DR8).

**Acceptance Criteria:**

**Given** the `ConfidencePill` component
**When** I pass `confidence={0.62}`
**Then** the pill renders with `MEDIUM_LOW` styling (per Story 3.6 thresholds)
**And** the visual treatment uses shape + position + label + color (NFR-AC3 — color-blind safe)

**Given** I pass an invalid confidence (NaN, < 0, > 1)
**Then** the component renders an `unknown` band with a debug warning
**And** TypeScript catches the type at the call site

### Story 3.14: Document SHA-256 hashing and immutability verification

As the platform,
I want every uploaded document's SHA-256 stored in the ledger and verifiable on download,
So that document tampering is detectable end-to-end (FR31).

**Acceptance Criteria:**

**Given** a document is uploaded (Story 2.4)
**When** the document record is finalized
**Then** the SHA-256 hash is stored in the `documents` row AND in a `document.uploaded` ledger entry

**Given** I download a document via presigned GET
**When** the cockpit-ui receives the response
**Then** the cockpit-ui can re-hash and compare against the ledger entry
**And** a mismatch surfaces a clear error to the officer (FR31)

## Epic 4: Triage Mode & Live Mesh Visibility

Analyst navigates the queue with keyboard (j/k/x/d), opens cases instantly, sees agent status updates streaming in real time via SSE, and uses ⌘K to invoke any action. The cockpit "comes alive."

### Story 4.1: Risk × SLA × continuity ordering for Queue Rail

As a KYC Analyst,
I want the queue ordered by risk × SLA × continuity rather than just creation time,
So that I work the right case next without manual sorting (FR1).

**Acceptance Criteria:**

**Given** my queue contains cases with various risk_band, sla_remaining_minutes, and continuity_with_my_recent_work
**When** Queue Rail renders
**Then** ordering is: highest-risk first, then earliest-SLA, then highest-continuity (recently-touched cases or related-entity cases)
**And** the ordering helper lives in `services/case_service.py.queue_order(...)`
**And** unit tests cover at least 5 distinct ordering scenarios

**Given** I refresh
**When** ordering recomputes
**Then** ties break deterministically by `created_at DESC`

### Story 4.2: Keyboard triage loop (j/k/x/d/Enter)

As a fluent KYC Analyst,
I want to navigate the queue without leaving home row,
So that I work at keyboard speed (FR2, UX-DR24).

**Acceptance Criteria:**

**Given** I am focused on Queue Rail
**When** I press `j`
**Then** focus moves to the next queue item with a 100 ms `snap` motion (UX-DR5)
**When** I press `k`
**Then** focus moves to the previous item

**Given** focus is on a queue item
**When** I press `Enter`
**Then** the case opens in Case Canvas

**Given** focus is on a queue item
**When** I press `x`
**Then** a "defer" menu opens (deferred-until selector); `Esc` cancels

**Given** focus is on a closed/committed queue item
**When** I press `d`
**Then** the item is marked done in my view filter (not the underlying case state)

**Given** I tab into Queue Rail with screen-reader on
**When** I activate any of these shortcuts
**Then** the screen-reader announces the action via aria-live region (NFR-AC2)

### Story 4.3: Eight illustrated agent face SVGs with state machine

As a KYC Analyst,
I want each MVP agent to have a dignified illustrated face that reflects its current state,
So that the mesh feels like a small company of specialists, not a grid of spinners (UX-DR6, UX-DR7).

**Acceptance Criteria:**

**Given** `apps/cockpit-ui/public/agent-faces/`
**When** I open it
**Then** I find 8 SVG files: `case-supervisor.svg`, `document-intelligence.svg`, `entity-verification.svg`, `ubo-graph.svg`, `screening.svg`, `risk-scoring.svg`, `writing.svg`, `cockpit-chat.svg`
**And** each is dignified, geometric, low-detail — no kiddish or cartoonish features (Pixar-restraint)

**Given** the `AgentFace` React component
**When** I pass `state="idle"`
**Then** the face is static
**When** I pass `state="working"`
**Then** subtle "breath" animation (1s cycle, 8% scale variation)
**When** I pass `state="complete"`
**Then** subtle chime + glow (300 ms, fades)
**When** I pass `state="blocked"`
**Then** dimmed with a small error mark
**When** I pass `state="needs_input"`
**Then** the face turns slightly toward the officer (visual focus pull)

**Given** the component
**When** I render a static screenshot
**Then** Playwright visual regression catches any unintended pixel drift

### Story 4.4: Three motion flavors as Framer Motion utilities

As an implementer of cockpit components,
I want `expand`, `focus-dim`, and `slide-out` motion utilities as shared Framer Motion presets,
So that motion language stays consistent (UX-DR5, UX-DR11).

**Acceptance Criteria:**

**Given** `apps/cockpit-ui/src/lib/motion.ts`
**When** I import it
**Then** I get three presets: `expand` (250 ms cubic-bezier, used for panel expansion), `focusDim` (150 ms ease-out, used for soft-dim of non-focused zones), `slideOut` (300 ms ease-in-out, used for slide-out drawers)

**Given** any cockpit component animation
**When** code review runs
**Then** the three presets are used (custom durations require ADR)

**Given** Playwright e2e
**When** measuring animation duration on a panel expand
**Then** total animation completes within 250 ms ± 30 ms

### Story 4.5: Agent Copilot Pane with live activity feed

As a KYC Analyst,
I want the Agent Copilot Pane on the right showing each agent's current state at a glance,
So that I see the mesh working without parsing log lines (FR11, UX-DR15).

**Acceptance Criteria:**

**Given** I open a case
**When** the Agent Copilot Pane renders
**Then** I see 8 rows (one per MVP agent), each with: agent face (Story 4.3), agent name, current state badge, last activity timestamp

**Given** an agent transitions state
**When** the SSE event fires (Story 4.6)
**Then** the row updates within ≤ 500 ms with the new state
**And** the agent face transitions through the corresponding animation

**Given** I click an agent row
**When** there is a recent reasoning trace
**Then** the trace slide-out opens (full implementation Epic 6)

### Story 4.6: SSE stream endpoint

As the cockpit-ui,
I want a Server-Sent Events stream per case with minimal payload events that trigger TanStack Query invalidation,
So that the cockpit feels alive without polling overhead (A2, P6).

**Acceptance Criteria:**

**Given** an authenticated KYC Analyst
**When** the cockpit-ui opens an `EventSource` to `/t/{tenant_id}/v1/cases/{case_id}/stream`
**Then** the connection is authenticated by cookie session (`withCredentials: true`)
**And** the server validates tenant scope + RBAC (Stories 1.7, 1.8) before opening the stream

**Given** an event is published (Story 4.7)
**When** the SSE worker dispatches
**Then** the client receives event types: `agent.state_changed`, `case.risk_recalculated`, `case.committed`, `agent.reasoning_trace_ready` — all ≤ 256 bytes payload (P6)

**Given** the connection drops
**When** EventSource auto-reconnects
**Then** the client receives a `lastEventId` header and the server replays missed events from a 60-second buffer (Redis stream)

**Given** the client closes the page
**When** the connection terminates
**Then** the SSE worker cleans up its registry entry within 5s

### Story 4.7: Redis pub/sub registry for multi-worker SSE coordination

As the platform with multiple uvicorn workers,
I want SSE state changes from any worker to fan out to subscribers held by any other worker,
So that load-balanced deployments don't lose events (C2 from architecture validation).

**Acceptance Criteria:**

**Given** `services/sse_registry.py`
**When** an agent state change is published
**Then** the event is published to a Redis channel `tenant:{tenant_id}:case:{case_id}`
**And** every uvicorn worker subscribes to channels for the case_ids its connected EventSources care about

**Given** worker A holds an SSE connection for case_X and worker B publishes a state change for case_X
**When** the message is published
**Then** worker A receives the event from Redis pub/sub and forwards to its EventSource within ≤ 100 ms

**Given** Redis is unavailable
**When** the SSE worker tries to publish
**Then** the publish fails fast with a logged error
**And** the cockpit-ui falls back to TanStack Query polling at 10s interval (graceful degradation)

### Story 4.8: Mode switcher (Investigation only)

As a KYC Analyst,
I want to switch into Investigation mode via ⌘+1,
So that the cockpit's UI footprint is tuned for the work I'm doing (FR4 partial, UX-DR22).

**Acceptance Criteria:**

**Given** I am on a case
**When** I press ⌘+1
**Then** the cockpit enters "Investigation" mode (the default; Zen mode lands in Epic 8)
**And** `stores/modeStore.ts` updates global mode state
**And** the visual change is immediate (snap motion)

**Given** I attempt ⌘+2 through ⌘+6
**When** the modes don't yet exist (this epic only Investigation)
**Then** a toast announces "Mode not yet available" and current mode is preserved

### Story 4.9: Command palette (⌘K)

As a KYC Analyst,
I want a universal action palette accessible by ⌘K,
So that any cockpit action is one keystroke away (FR5, UX-DR23).

**Acceptance Criteria:**

**Given** the cockpit
**When** I press ⌘K
**Then** a centered modal overlay appears with a search input focused
**And** I can search and execute: "open case <id|name>", "switch to investigation mode", "go to queue", "sign out", "show keyboard shortcuts"
**And** results are typeable + arrow-keys navigable + Enter executes + Esc closes

**Given** the palette is open
**When** I type a partial query
**Then** results update with fuzzy match within 50 ms p95 (NFR-P1)

**Given** the palette
**When** rendered with screen-reader
**Then** results announce via aria-live; selected result announces on arrow-key change

### Story 4.10: In-app notifications system

As any role,
I want in-app notifications for actions requiring my attention,
So that I see queue updates, approvals due, and system events (FR6).

**Acceptance Criteria:**

**Given** a `notifications` table per tenant with `id`, `user_id`, `type`, `payload`, `read_at`, `created_at`
**When** an event creates a notification (e.g., new case assigned, approval due, vendor outage)
**Then** the notification appears in a Top Bar bell icon with unread count
**And** clicking the bell opens a dropdown listing unread notifications

**Given** a notification has an action target
**When** I click it
**Then** I navigate to that route (e.g., approvals queue, the affected case)
**And** the notification is marked `read_at`

### Story 4.11: Keyboard shortcut help overlay (?)

As a KYC Analyst,
I want a `?` overlay showing all keyboard shortcuts for the current mode,
So that I learn fluency without leaving the cockpit (UX-DR25).

**Acceptance Criteria:**

**Given** any cockpit screen
**When** I press `?` (Shift + /)
**Then** a centered overlay appears listing shortcuts grouped by category (Navigation: j/k/Enter/x/d, Modes: ⌘+1, Palette: ⌘K, Help: ?, Sign out: ⌘⇧Q)
**And** Esc closes
**And** shortcuts shown are mode-aware (only those active in current mode)

### Story 4.12: Status pills for agent states

As a KYC Analyst,
I want a clear status pill for each agent — done / in-progress / blocked / needs-input,
So that I quickly assess mesh readiness on case open (UX-DR34).

**Acceptance Criteria:**

**Given** the AgentCopilotPane (Story 4.5)
**When** an agent is in any of the 4 states
**Then** a `StatusPill` component renders next to the agent face with shape + label + color
**And** colors meet contrast 4.5:1 against the pane background (NFR-AC4)

## Epic 5: Entity & UBO Investigation

Analyst sees UBO ownership rendered as a force-directed graph, drag-corrects nominee structures with a learning-event ledger entry, watches risk score recalculate. MCA + GST entity verification surfaces mismatches.

### Story 5.1: Entity Verification agent

As the platform,
I want the Entity Verification agent to cross-reference the case entity against MCA + GST sources and surface mismatches,
So that the analyst sees authority-source-grounded entity status (FR17).

**Acceptance Criteria:**

**Given** a case has CIN and GSTIN extracted by Document Intelligence (Story 3.9)
**When** the Case Supervisor invokes Entity Verification
**Then** it calls the MCA tool (Story 5.2) and GST tool (Story 5.3) via ADK `@tool` functions
**And** returns a structured `EntityVerificationResult` with `mca_status` (active/struck-off/dormant), `gst_status` (active/cancelled), `mismatches: list[FieldMismatch]`
**And** writes a `AgentActionLedgerEntry` via `@ledgered_action`

**Given** any tool fails (vendor down, network)
**When** the agent surfaces the failure
**Then** the case state becomes `intake_blocked` with reason "EntityVerification: <tool> unavailable" — no stale data (NFR-A7)

### Story 5.2: MCA lookup tool

As the platform,
I want a `@tool` that wraps the MCA company-master lookup,
So that the Entity Verification agent has a typed authority source (FR17).

**Acceptance Criteria:**

**Given** the tool at `apps/agents/src/agents/tools/mca_lookup.py`
**When** called with a CIN
**Then** it returns a Pydantic-typed `MCACompanyMaster` (name, status, registered_office, directors[])
**And** rate-limits per MCA's published terms; 429 surfaces as a transient `MCATemporaryError`

**Given** an invalid CIN
**Then** raises a typed `MCANotFoundError` (not generic Exception)

### Story 5.3: GST verify tool

As the platform,
I want a `@tool` that verifies a GSTIN against the GST portal,
So that Entity Verification grounds the entity in tax-authority data (FR17).

**Acceptance Criteria:**

**Given** the tool at `apps/agents/src/agents/tools/gst_verify.py`
**When** called with a GSTIN
**Then** it returns a typed `GSTRegistration` (legal_name, trade_name, status, registration_date, principal_place)

**Given** the GSTIN is invalid format
**Then** the tool fails fast with a typed validation error before hitting the network

### Story 5.4: UBO Graph agent (basic)

As the platform,
I want a UBO Graph agent that constructs a force-directed ownership graph from MCA director + shareholding data,
So that the analyst sees ownership structure visually (FR15, NFR-T5 ≥ 95% structural).

**Acceptance Criteria:**

**Given** the case has Entity Verification complete (Story 5.1)
**When** the Case Supervisor invokes UBO Graph
**Then** it constructs a `UBOGraph` Pydantic model with nodes (Person | Entity) and edges (Owns | Director | Beneficial)
**And** each edge carries a `Provenance` (source: MCA / GST / officer_input) and confidence
**And** writes a ledger entry per `@ledgered_action`

**Given** basic nominee/shell heuristics (e.g., shared registered address with filing agent, foreign LLC with no MCA)
**When** detected
**Then** the affected edges are flagged with a "nominee_suspected" tag (officer-correctable in Story 5.6)

**Given** the corpus benchmark (Story 5.10)
**When** evaluated
**Then** structural accuracy ≥ 95% on the basic UBO test set (NFR-T5)

### Story 5.5: UBO Canvas component (force-directed react-flow)

As a KYC Analyst,
I want to see the UBO graph as a force-directed canvas with confidence-banded edges and nominee-suspected flags,
So that I understand ownership structure at a glance (FR15, UX-DR19).

**Acceptance Criteria:**

**Given** I open a case where UBO Graph has run
**When** the UBO panel expands on Case Canvas
**Then** react-flow renders the graph with force-directed layout
**And** edges are styled per `ConfidenceBand` (P7) — shape + color
**And** "nominee_suspected" edges are rendered as red dotted

**Given** ≥ 50 UBO nodes
**When** I interact (pan/zoom/select)
**Then** interactions remain smooth — frame-time stays under 16 ms p95 (NFR-P3)

### Story 5.6: Drag-correct interaction with learning-event ledger entry

As a KYC Analyst,
I want to drag UBO edges to correct relationships, with the agent asking permission to learn from my correction,
So that I improve the mesh's future detections without RLHF baggage (FR16, UX-DR19).

**Acceptance Criteria:**

**Given** I am on UBO Canvas
**When** I drag an edge from one node to another
**Then** a tooltip prompts "Tag relationship: <select: real_ubo / nominee / director / removed>"
**And** I can attach an evidence note (e.g., "RM email 2024-11")

**Given** I confirm the correction
**When** the cockpit-api receives it
**Then** a `learning_event` ledger entry is written with my user ID, signature (Story 7.4 — until then a temporary platform sig acceptable in Epic 5), correction details, and evidence reference
**And** the agent's offer to "treat as ground-truth correction for future shell/nominee detection" is captured as opt-in (officer's choice recorded)

**Given** the corrections are stored
**When** the data team runs the quarterly retraining cycle (out of MVP scope)
**Then** corrections are reviewable as labeled signal (mitigation: not auto-applied, prevents poisoning)

### Story 5.7: Risk Scoring agent

As the platform,
I want a Risk Scoring agent that decomposes risk into named contributing factors,
So that the analyst sees not just a number but a stacked explanation (FR20).

**Acceptance Criteria:**

**Given** Entity Verification, UBO, and Screening (when present — for now placeholder) data are on the case
**When** Risk Scoring runs
**Then** it returns a `RiskScore` with `total: int (0-100)`, `band: low|medium|high`, `components: list[RiskComponent]` where each component has name (e.g., "country", "entity_type", "ownership_clarity", "screening", "adverse_media"), value, weight, contribution, rationale

**Given** the model_id and prompt_template_id
**When** Risk Scoring writes its ledger entry
**Then** all are captured per P4

### Story 5.8: Risk Score stacked-bar with hover decomposition

As a KYC Analyst,
I want to see the risk score as a stacked bar I can hover for component decomposition,
So that I understand which factors are driving risk (FR20, UX-DR20).

**Acceptance Criteria:**

**Given** I open a case
**When** the Risk panel renders on Case Canvas
**Then** I see a horizontal stacked bar with each component proportional to its contribution
**And** hovering any segment shows the component's name, value, weight, contribution, and rationale

**Given** a component changes value
**When** the bar re-renders (Story 5.9)
**Then** the affected segment animates a 200 ms cross-fade (UX-DR20)

### Story 5.9: Auto-recalc on officer correction

As a KYC Analyst,
I want the risk score to recalculate when I make a correction (UBO edit, manual screening disposition, etc.),
So that the score I commit on reflects my interventions (FR21).

**Acceptance Criteria:**

**Given** I edit a UBO relationship via Story 5.6
**When** the correction is committed
**Then** the cockpit-api fires a `case.risk_recalculated` event (P6) which triggers re-invocation of Risk Scoring
**And** Risk Scoring writes a new ledger entry (the prior score is preserved in the chain)

**Given** the cockpit-ui receives `case.risk_recalculated`
**When** TanStack Query invalidates the case query
**Then** the Risk Score stacked bar re-renders with the new components within 500 ms (NFR-P perf)

### Story 5.10: UBO + Risk panels on Case Canvas

As a KYC Analyst,
I want UBO and Risk panels visible on the Case Canvas alongside the Documents panel,
So that I have all investigation context in one canvas (FR7).

**Acceptance Criteria:**

**Given** I open a case where Entity Verification, UBO, and Risk Scoring have all run
**When** the Case Canvas renders
**Then** I see three collapsible panels: Documents (Story 3.12), UBO (Story 5.5), Risk (Story 5.8)
**And** each panel can be expanded/collapsed via click + keyboard (`Tab` to focus, `Space` to toggle)
**And** expansion uses the `expand` motion preset (Story 4.4)

## Epic 6: Screening, Reasoning Traces & Conversational Mesh

Analyst clicks any agent finding to open a 4-section reasoning trace including the counterfactual; screening hits show as a 3-column explainer; analyst converses with the Cockpit Chat agent for case context.

### Story 6.1: Screening adapter Protocol with mock impl

As the platform,
I want a `ScreeningAdapter` Protocol with a mock impl for dev/CI,
So that the screening agent works in dev without procurement dependency (P1, FR18, FR56).

**Acceptance Criteria:**

**Given** `packages/contracts/screening.py`
**When** I read it
**Then** I see `ScreeningRequest`, `ScreeningHit`, `ScreeningAdapter` Protocol with method `screen(req: ScreeningRequest, *, tenant_id: TenantId) -> list[ScreeningHit]`

**Given** `apps/agents/src/agents/adapters/screening/mock.py`
**When** the conformance suite runs
**Then** it returns deterministic fixtures keyed by name+DOB

**Given** environment variable `SCREENING_PROVIDER=mock`
**When** dev runs
**Then** screening uses the mock without any external network calls

### Story 6.2: ComplyAdvantage screening adapter

As the platform deploying to a real tenant,
I want a ComplyAdvantage-backed screening adapter that passes the conformance suite,
So that production screening uses the chosen vendor (P1, AR19).

**Acceptance Criteria:**

**Given** `apps/agents/src/agents/adapters/screening/complyadvantage.py`
**When** the contract conformance suite runs (with sandbox creds)
**Then** all conformance tests pass: search returns hits, hits have name_match_score + DOB + identifiers + categories, errors are typed (`VendorTemporaryError` vs `VendorPermanentError`)

**Given** the tenant's screening config selects `complyadvantage`
**When** the cockpit-api starts
**Then** the adapter is wired up via Pydantic Settings

**Given** Story 6.10 (procurement runbook) is complete and a sandbox API key exists
**Then** dev integration test passes against the sandbox

### Story 6.3: Screening agent

As the platform,
I want a Screening agent that evaluates the entity + key associated individuals against the configured screening vendor,
So that PEP/sanction/adverse-media hits surface as part of intake (FR18).

**Acceptance Criteria:**

**Given** the case has entity + UBO data
**When** the Case Supervisor invokes Screening
**Then** it calls the configured ScreeningAdapter for: the entity, every director, every UBO with ≥ 10% ownership
**And** for each hit returned, the agent writes a structured `ScreeningHit` to the case
**And** the agent writes a `AgentActionLedgerEntry` per `@ledgered_action`

**Given** a hit has a low name-match (< 0.5) and identifier mismatches
**When** the agent processes it
**Then** the hit is auto-filtered as `dismissed_by_agent` with confidence rationale (officer can manually re-include)

### Story 6.4: Screening Explainer 3-column component

As a KYC Analyst,
I want to see each screening hit as a 3-column "what matched / what didn't / counterfactual" card,
So that I can quickly assess match quality without parsing dense data (FR19, UX-DR21).

**Acceptance Criteria:**

**Given** I view a case with screening hits
**When** the Screening panel renders on Case Canvas
**Then** each hit is shown as a 3-column card: "Matched" (e.g., "name 73% similar"), "Didn't match" (e.g., "DOB 1961 vs 1978"), "Counterfactual" (e.g., "would upgrade if DOB matches")
**And** the confidence band is shown via `ConfidencePill` (Story 3.13)

**Given** I click "Re-run with different parameters"
**When** I edit (e.g., relax DOB tolerance)
**Then** the agent re-runs screening with the new params and the result updates via SSE

### Story 6.5: ReasoningTrace contract — 4-section schema enforcement

As an agent author,
I want the `ReasoningTrace` Pydantic contract to enforce all four sections populated,
So that the counterfactual is non-skippable across every agent output (P8, Innovation #2).

**Acceptance Criteria:**

**Given** `packages/contracts/reasoning_trace.py`
**When** I read it
**Then** I see a `ReasoningTrace` Pydantic model with non-empty `what_searched`, `what_hit`, `confidence_self_rating: ConfidenceWithRationale`, `counterfactual` fields (all required, all min-length validated)

**Given** an agent attempts to produce a `ReasoningTrace` with empty `counterfactual`
**Then** Pydantic validation rejects + the agent's `@ledgered_action` decorator raises typed `IncompleteReasoningTraceError`

### Story 6.6: GET reasoning trace endpoint

As the cockpit-ui,
I want to fetch a specific agent action's reasoning trace,
So that the slide-out can render it on demand (FR12).

**Acceptance Criteria:**

**Given** an authenticated KYC Analyst
**When** they GET `/t/{tenant_id}/v1/cases/{case_id}/agent-actions/{aa_id}/reasoning-trace`
**Then** the cockpit-api returns the `ReasoningTrace` payload from the ledger entry
**And** p95 latency ≤ 500 ms (PRD perf budget)

**Given** an agent action with no reasoning trace produced (e.g., a tool call that returned a deterministic value)
**Then** the response is 204 No Content (UI shows "no trace produced")

### Story 6.7: ReasoningTraceSlideOut component

As a KYC Analyst,
I want a slide-out panel that shows the 4-section reasoning trace for any agent finding I click,
So that I see the agent's logic with counterfactual (FR12, UX-DR10).

**Acceptance Criteria:**

**Given** I click a provenance pill or an agent face
**When** the slide-out opens
**Then** it slides in from the right edge with `slideOut` motion preset (Story 4.4) within 500 ms (perf SLO)
**And** it shows the 4 fixed sections: What searched · What hit · Confidence · What would change it
**And** Esc closes; arrow keys scroll within sections; Tab cycles through interactive elements

**Given** the slide-out is open
**When** the canvas behind it soft-dims via `focusDim` motion
**Then** the visual hierarchy makes the trace primary

### Story 6.8: Cockpit Chat agent with mesh-as-tools

As a KYC Analyst,
I want to converse with a Cockpit Chat agent that has access to the case state and the rest of the mesh as tools,
So that I can ask "explain this risk score" or "re-run screening with X" in natural language (FR13).

**Acceptance Criteria:**

**Given** the Cockpit Chat agent at `apps/agents/src/agents/interaction/cockpit_chat.py`
**When** invoked from the cockpit-ui chat input
**Then** it has tools: `get_case`, `get_reasoning_trace`, `re_run_agent` (Screening, Risk Scoring, UBO), `query_ledger`
**And** every tool call is itself a ledger entry per `@ledgered_action`

**Given** my message "explain why screening is amber"
**When** the agent responds
**Then** it cites specific ledger entry IDs in its explanation
**And** broken citations (referencing non-existent IDs) surface as render-time errors

**Given** my message asks the agent to re-run screening with different params
**Then** the agent confirms the action with me before invoking the tool (HITL pattern)

### Story 6.9: Cockpit Chat conversational UI in Agent Copilot Pane

As a KYC Analyst,
I want a chat input at the bottom of the Agent Copilot Pane,
So that I can converse with the mesh without leaving the cockpit (FR13, UX-DR15).

**Acceptance Criteria:**

**Given** the Agent Copilot Pane (Story 4.5)
**When** the chat surface renders
**Then** the bottom of the pane shows a chat input + send button + transcript above
**And** typing "@" surfaces a mention picker for specific agents

**Given** I send a message
**When** the agent responds
**Then** the response streams via SSE token-by-token (typewriter effect) within the pane
**And** citations are rendered as inline `ProvenancePill`s

### Story 6.10: Screening procurement runbook + sandbox onboarding

As the program lead,
I want a runbook for procuring + onboarding the screening vendor,
So that Story 6.2's sandbox dependency is unblocked early (AR19).

**Acceptance Criteria:**

**Given** `docs/runbooks/screening-vendor-onboarding.md`
**When** the program lead follows it
**Then** they: (1) procure ComplyAdvantage trial, (2) provision sandbox API key, (3) configure rate limits, (4) load 5 test entities, (5) run conformance suite (Story 6.2) against sandbox
**And** the procurement story is the calendar dependency to unblock Stories 6.2-6.4 — the team should start it during Epic 1-2 work

## Epic 7: Decision Authoring & Officer Signing

Analyst edits an agent-drafted rationale in the Decision Zone, commits with WebCrypto Ed25519 signature, has 120 seconds to undo. Edit-rate metric tracks how much officer work was on top of the agent draft.

### Story 7.1: Officer Ed25519 keypair generation at first login

As a KYC Analyst,
I want a personal signing keypair generated automatically at first login,
So that I can sign decisions cryptographically without managing keys manually (FR29, S6, AR12).

**Acceptance Criteria:**

**Given** I log in for the first time
**When** the cockpit-api detects no `officer_keys` row for my user ID
**Then** the cockpit-ui generates an Ed25519 keypair via WebCrypto API
**And** the public key is POSTed to `/t/{tenant_id}/v1/auth/officer-keys`
**And** the cockpit-api stores it in the `officer_keys` table (`user_id`, `public_key_pem`, `created_at`, `revoked_at`)

**Given** the private key
**When** stored client-side
**Then** it is wrapped with a tenant-key-derived KEK (Story 7.2) and persisted in IndexedDB; never sent to the server in plaintext

### Story 7.2: Encrypt + store private key with tenant master key

As the platform,
I want the officer's private key encrypted at rest in the browser using a tenant-derived KEK,
So that key compromise scope is bounded and recovery uses the tenant HSM (S6, AR12).

**Acceptance Criteria:**

**Given** the cockpit-api derives a per-officer KEK from the tenant HSM (HKDF with user_id as info)
**When** the cockpit-ui persists the private key
**Then** the key is wrapped with the KEK via AES-GCM and stored in IndexedDB
**And** subsequent logins re-derive the KEK from the tenant HSM and unwrap the key

**Given** an officer changes browsers/devices
**When** they log in on the new device
**Then** a new keypair is generated (key-per-device); the public key is added to `officer_keys`
**And** historical signatures from prior devices remain verifiable (public keys retained even if device retired)

### Story 7.3: Client-side WebCrypto signing utility

As an implementer of the Decision Zone,
I want a `lib/crypto.ts` utility that signs canonical-JSON payloads via WebCrypto Ed25519,
So that decision commits carry officer signatures (P5).

**Acceptance Criteria:**

**Given** `apps/cockpit-ui/src/lib/crypto.ts`
**When** I import `signOfficerAction(payload, keyHandle)`
**Then** the function canonicalizes the payload (RFC 8785 JSON Canonicalization Scheme) and produces a Ed25519 signature
**And** unit tests verify roundtrip: sign with the JS impl, verify with the Python impl in `cockpit-api`

**Given** an unsupported browser
**When** WebCrypto Ed25519 is missing
**Then** a clear error message is shown — sign-out, document the user's browser is unsupported (NFR-CP1 latest 2 versions)

### Story 7.4: Server-side Ed25519 verification

As the cockpit-api,
I want to verify officer signatures against stored public keys before persisting decisions,
So that signature tampering is detected at the API boundary (P5, S6).

**Acceptance Criteria:**

**Given** a POST to `/t/{tenant_id}/v1/cases/{case_id}/decisions` with `signature` + `signing_key_id` headers
**When** the cockpit-api processes the request
**Then** it loads the officer's public key, verifies the signature against the canonical JSON of the request body, and rejects with 403 RFC 7807 on mismatch
**And** the verification function lives in `services/decision_service.py` and is unit-tested with mock keypairs

**Given** the signing key is revoked (`revoked_at` set)
**When** a decision arrives signed with that key
**Then** the request is rejected with 403 + a clear message

### Story 7.5: Decision Zone component with Tiptap editor

As a KYC Analyst,
I want to edit the agent-drafted rationale in a clean rich-text editor with light formatting,
So that I can express my reasoning without form ceremony (FR22, UX-DR16).

**Acceptance Criteria:**

**Given** I am viewing a case with `decision_ready` state
**When** the Decision Zone renders at the bottom of Case Canvas
**Then** I see a Tiptap editor pre-loaded with the Writing agent's draft (Story 7.7)
**And** light formatting available: paragraph, bold, italic, citation token (inserts a ledger-entry-id reference)

**Given** I type
**When** my edits propagate
**Then** auto-save persists every 5s to a `decision_drafts` table (versioned)
**And** on reload I see the most recent draft

### Story 7.6: Tonal/typographic shift on Decision Zone focus

As a KYC Analyst,
I want the Decision Zone to feel like a different room when I focus into it — typography enlarges, the canvas behind soft-dims,
So that committing feels weighty, not incidental (UX-DR16, "Decisions are sacred").

**Acceptance Criteria:**

**Given** I focus into the Decision Zone (click or `⌘+Shift+D`)
**When** the focus transition fires
**Then** the canvas above soft-dims to 70% opacity (`focusDim` motion preset)
**And** Decision Zone typography enlarges (body 14→16, headings 20→24)
**And** the palette shifts subtly into a "calmer" register (per UX tokens)

**Given** I leave the Decision Zone (focus elsewhere or Esc)
**When** the focus exits
**Then** the canvas un-dims; Decision Zone typography returns to normal scale

### Story 7.7: Writing agent v1 — rationale draft

As the platform,
I want a Writing agent that drafts a rationale paragraph based on the case state,
So that the analyst never starts from a blank page (FR26 partial, NFR-T3).

**Acceptance Criteria:**

**Given** a case has reached `decision_ready` (intake complete + screening + risk all run)
**When** the Writing agent is invoked
**Then** it produces a `DraftedRationale` with 2-4 paragraphs citing key findings by ledger entry ID (citations rendered as inline tokens in Tiptap)
**And** the draft uses a Jinja template at `apps/agents/src/agents/prompts/writing/rationale_draft_v1.j2`
**And** golden inputs validate output structure (NFR-RI7)

**Given** the draft cites a ledger ID that doesn't exist (hallucination)
**When** the cockpit-ui renders the citation
**Then** it shows a render-time error pill on the broken citation (forces officer to fix before commit)

### Story 7.8: 120-second undo timer with fail-closed Redis policy

As the platform,
I want a 120-second undo window after decision commit, fail-closed if Redis becomes unavailable,
So that officer mistakes are correctable while ensuring no orphan timers seal silently (NFR-T1, C3 from architecture validation).

**Acceptance Criteria:**

**Given** an officer commits a decision (Story 7.11)
**When** the cockpit-api processes it
**Then** the decision enters `pending_seal` state
**And** a Redis key `decision:{case_id}:undo` with 120s TTL is set
**And** the cockpit-ui shows the UndoPill (Story 7.9)

**Given** the 120s elapses normally
**When** the TTL expires
**Then** an Arq job seals the decision (state → `committed`, ledger entry written), removes the Redis key, and fires SSE + webhook events

**Given** Redis becomes unavailable mid-window
**When** the cockpit-api attempts to read the timer
**Then** the decision remains in `pending_seal` (never auto-seals on Redis failure)
**And** when Redis recovers, the timer resumes from its remaining window
**And** if Redis is unavailable for > 1 hour, the decision is auto-cancelled and the officer is notified (FR6 notification)

### Story 7.9: UndoPill with countdown ring + reason capture modal

As a KYC Analyst,
I want a visible 120-second countdown after I commit, with a clear way to undo and capture my reason,
So that mistakes are correctable and the undo itself becomes audit evidence (NFR-T1, UX-DR27).

**Acceptance Criteria:**

**Given** I just committed a decision
**When** the UndoPill appears at the bottom of the screen
**Then** it shows a countdown ring (visual progression 120→0) and "Undo" button
**And** the ring uses the `snap` motion preset for tick visualization

**Given** I click Undo
**When** the modal opens
**Then** I must enter a reason ≥ 40 characters (NFR-T6) before the modal "Confirm Undo" button is enabled

**Given** I confirm the undo
**When** the cockpit-api processes
**Then** the decision returns to `decision_ready` state
**And** an `officer.decision_undone` ledger entry is written with my reason + signature (Story 7.4)

### Story 7.10: Seal animation on commit

As a KYC Analyst,
I want a subtle "seal" animation when my decision is sealed (after 120s elapses or undo skipped),
So that the moment carries weight without theatrics (UX-DR28).

**Acceptance Criteria:**

**Given** the decision transitions to `committed`
**When** the cockpit-ui receives the SSE event
**Then** a 400 ms ease-out seal animation plays on the Decision Zone
**And** the UndoPill fades and is replaced by a "Sealed" indicator with the ledger entry ID
**And** Tiptap becomes read-only

### Story 7.11: POST decision endpoint with signature verification

As the cockpit-ui,
I want to commit a decision via POST with the officer's signature attached,
So that the cockpit-api verifies before persisting (FR24, FR29).

**Acceptance Criteria:**

**Given** I have edited the rationale in Decision Zone
**When** I press `⌘+Enter` (or click Commit)
**Then** the cockpit-ui canonicalizes `{case_id, outcome, rationale_hash, timestamp, nonce}`, signs via Story 7.3, and POSTs to `/t/{tenant_id}/v1/cases/{case_id}/decisions` with `signature` + `signing_key_id` headers
**And** the cockpit-api verifies (Story 7.4) and starts the 120s undo timer (Story 7.8)

**Given** outcome enum
**When** committed
**Then** outcomes include: `approve`, `decline`, `approve_with_conditions` (with conditions array), `escalate_to_edd`

**Given** the ledger entry is written
**When** I query the case
**Then** the rationale text matches what I committed (immutable post-seal)

### Story 7.12: Officer-signed ledger entry

As the platform,
I want every officer commit to produce a fully signed ledger entry with the officer's Ed25519 signature,
So that decisions are non-repudiable (FR29, P5).

**Acceptance Criteria:**

**Given** Story 7.11 has verified the officer signature
**When** the LedgerService appends
**Then** the entry includes both the officer's signature (covering the canonical decision payload) AND the platform's chain signature (covering chain hash)
**And** the verifier tool (Epic 9) checks both

### Story 7.13: Edit-rate metric tracking

As the team monitoring product success,
I want the edit-rate metric (officer changes vs agent draft) tracked per decision,
So that NFR-T3 (≥ 60% edit-rate) is observable (FR27).

**Acceptance Criteria:**

**Given** a decision is committed
**When** the cockpit-api persists
**Then** `decisions.edit_rate` column stores: `(diff_chars(agent_draft, officer_final) / max(len(agent_draft), len(officer_final)))`
**And** values 0.0 = no edits (rubber stamp), 1.0 = total rewrite, target band [0.05, 0.5] for healthy edits (architecture's "edit-don't-author")

**Given** the CCO portfolio dashboard (Epic 10)
**When** rendering metrics
**Then** edit-rate distribution is shown as a histogram per analyst per week

### Story 7.14: Basic Evidence shelf (read-only) for context

As a KYC Analyst,
I want to see attached evidence on the side while drafting,
So that I can reference documents without leaving Decision Zone (FR9 partial).

**Acceptance Criteria:**

**Given** I focus into Decision Zone
**When** I click "Evidence" toggle in the side rail
**Then** an `EvidenceShelf` opens showing each document + extracted-fields summary in read-only form
**And** the full attachment-ingest UI lands in Epic 8 (Story 8.5)

### Story 7.15: Decision outcomes (approve / decline / approve-with-conditions / escalate-to-EDD)

As a KYC Analyst,
I want to commit one of four outcomes per case,
So that the platform represents the full decision space (FR24).

**Acceptance Criteria:**

**Given** Decision Zone
**When** I select an outcome
**Then** outcomes are: `approve`, `decline`, `approve_with_conditions`, `escalate_to_edd`
**And** for `approve_with_conditions` I am required to enter at least one condition (e.g., "enhanced monitoring 6mo", "re-review on screening delta")
**And** for `escalate_to_edd` the case auto-enqueues for Team Lead approval (Epic 8 Story 8.7)

## Epic 8: SAR/EDD Zen Mode & Narrative Drafting

Analyst enters Zen mode (⌘+4) — dark canvas, evidence docks right, typography enlarges. Writing agent drafts an EDD memo citing ledger entries by ID. Analyst edits the narrative and commits, automatically queueing the case for Team Lead approval.

### Story 8.1: ⌘+4 mode switch to Zen

As a KYC Analyst,
I want to switch into SAR/EDD Writing Zen mode via ⌘+4,
So that my environment changes when I shift to narrative work (FR4 full, FR25, UX-DR22).

**Acceptance Criteria:**

**Given** I am on a case
**When** I press ⌘+4
**Then** the cockpit transitions into Zen mode within 250 ms (`expand` preset)
**And** `stores/modeStore.ts` updates to `zen`
**And** the Zen mode visual treatment (Story 8.2) is applied

### Story 8.2: Zen mode visual treatment

As a KYC Analyst writing an EDD memo,
I want a calm, focused environment — dark canvas, evidence docked right, typography enlarged, minimal chrome,
So that I can think clearly while writing (FR25, UX-DR26).

**Acceptance Criteria:**

**Given** Zen mode is active
**When** the cockpit renders
**Then** background is dark (per Zen tokens — UX-DR1 dark variants)
**And** Tiptap editor occupies most of the canvas (centered, max-width ~720px)
**And** typography uses serif family at scale +1 (e.g., 18px body) per UX-DR2
**And** EvidenceShelf docks on the right with attachment list
**And** Top Bar reduces to mode indicator + back to Investigation button
**And** Bottom Ribbon hidden

**Given** Zen mode
**When** I switch out (⌘+1 to Investigation)
**Then** the transition is `expand` motion to the dense Investigation layout

### Story 8.3: Writing agent v2 — EDD memo drafter

As the platform,
I want a Writing agent that drafts a structured EDD narrative memo,
So that the analyst doesn't author from scratch on EDD outcomes (FR26).

**Acceptance Criteria:**

**Given** a case is escalated to EDD (outcome = `escalate_to_edd` from Story 7.15)
**When** the Writing agent is invoked with `mode=edd_memo`
**Then** it produces a structured EDD memo with sections: Executive Summary, Findings, Risk Factors, Mitigating Factors, Recommendation
**And** it cites specific ledger entry IDs in each section
**And** the prompt template lives at `apps/agents/src/agents/prompts/writing/edd_memo_v1.j2`
**And** golden inputs validate structure

**Given** the memo is rendered in Tiptap
**When** the analyst edits
**Then** the auto-save flow (Story 7.5) applies

### Story 8.4: Citation-by-ledger-ID enforcement in Writing output

As the platform,
I want the Writing agent's output to cite ledger entries by ID, with broken citations surfacing at render time,
So that hallucinated facts are caught immediately (FR26, P8 spirit).

**Acceptance Criteria:**

**Given** the Writing agent's output schema
**When** the Pydantic model is validated
**Then** any inline `{{led_<ULID>}}` tokens must reference real ledger entries for this case
**And** the agent's ledger entry includes a citations array

**Given** a citation references a non-existent ledger entry
**When** the cockpit-ui renders the memo
**Then** the broken citation displays a visible error chip; commit is blocked until corrected (FR26 spirit, P8)

### Story 8.5: EvidenceShelf with attachment ingest UI

As a KYC Analyst working an EDD case,
I want to attach supporting evidence (emails, photos, additional docs) to the case,
So that my memo can reference materials beyond the original intake (FR9 full).

**Acceptance Criteria:**

**Given** EvidenceShelf in Zen mode
**When** I click "Add Evidence"
**Then** I can: drag-drop a file, paste from clipboard, paste an email body
**And** each upload uses the DocStore presigned flow (Story 2.4)
**And** a SHA-256 hash is computed and stored in the ledger as a `case.evidence_attached` entry signed by my key (Story 7.4)

**Given** an evidence item is attached
**When** I drag it into the Tiptap editor
**Then** an inline reference token is inserted (rendered as a chip with click-to-preview)

### Story 8.6: Evidence attachment with SHA-256 hash

As the platform,
I want every evidence attachment to be hash-recorded in the ledger,
So that evidence integrity is verifiable end-to-end (FR9, FR31 spirit).

**Acceptance Criteria:**

**Given** an evidence item is uploaded
**When** the cockpit-api finalizes
**Then** the SHA-256 is computed by the API on first read
**And** stored in both the `documents` row and a `case.evidence_attached` ledger entry signed by the officer

**Given** I download the evidence later
**When** the cockpit-ui re-hashes
**Then** mismatch surfaces a clear error (same as Story 3.14)

### Story 8.7: EDD outcome auto-enqueue for Lead approval

As a KYC Analyst,
I want to commit an EDD-outcome decision and have it automatically appear in my Team Lead's approval queue,
So that the workflow is friction-free (FR39).

**Acceptance Criteria:**

**Given** I commit a decision with outcome `escalate_to_edd` or `approve_with_conditions` (high-risk)
**When** the cockpit-api persists
**Then** the case state moves to `pending_lead_approval`
**And** a `case.escalated_for_approval` event fires (SSE + webhook)
**And** the case appears in the Team Lead's approval queue (Epic 10)

**Given** the Team Lead approval workflow lands in Epic 10
**When** Epic 8 ships
**Then** the queue may not exist yet — but the case state and event are correct, awaiting Epic 10 to add the consumer

## Epic 9: Audit Trail, Regulator Lens & Offline Verifier

Internal Auditor opens cases in Regulator Lens mode (read-only, audit-styled); exports cases as PDF + JSON bundle; the offline verifier tool validates the hash chain and signatures without calling the platform.

### Story 9.1: AuditTrailTimeline component

As a KYC Analyst, Team Lead, CCO, or Internal Auditor,
I want to see a case's complete history as a timeline interleaving agent + officer actions,
So that I can reconstruct what happened and when (FR30, UX-DR30).

**Acceptance Criteria:**

**Given** I open a case
**When** I click "Audit Trail" in the case canvas
**Then** an `AuditTrailTimeline` panel renders chronologically: every agent action + every officer action with timestamp, actor, action type, signature status
**And** each entry is expandable to show the full payload + signature verification

**Given** my role is `kyc_analyst`
**Then** I see only this case's trail (RBAC scoping)

**Given** my role is `internal_auditor`
**Then** I see all entries including HSM-key-id metadata for forensic replay

### Story 9.2: Case timeline endpoint with role-scoped permissions

As the cockpit-ui,
I want to fetch the case timeline scoped by my role,
So that the AuditTrailTimeline renders the right level of detail (FR30, FR48).

**Acceptance Criteria:**

**Given** an authenticated user
**When** they GET `/t/{tenant_id}/v1/cases/{case_id}/timeline`
**Then** the response is the chronological array of ledger entries scoped by their role
**And** sensitive fields (e.g., signing_key_id) are stripped for non-auditor roles

**Given** the Internal Auditor role
**When** they GET the same endpoint with `?role=internal_auditor` query
**Then** they receive the full payload

### Story 9.3: Regulator Lens read-only mode

As an Internal Auditor,
I want to switch a case into Regulator Lens mode — read-only, audit-styled, full timeline visible,
So that I can review the case as a regulator would (FR33, UX-DR31).

**Acceptance Criteria:**

**Given** my role is `internal_auditor`
**When** I navigate to `/t/{tenant_id}/v1/cases/{case_id}/regulator-lens`
**Then** the page renders the case in read-only mode with the audit timeline taking center stage
**And** all interactive cockpit controls (decision commit, drag-correct UBO, agent re-run) are disabled
**And** a clear "REGULATOR LENS" indicator shows in the Top Bar

**Given** any non-auditor role attempts the route
**Then** they receive 403

### Story 9.4: PDF export bundle assembly

As an Internal Auditor,
I want to export a case (or set of cases) as a PDF audit bundle,
So that I can share with regulators or store offline (FR34).

**Acceptance Criteria:**

**Given** I am viewing a case in Regulator Lens (Story 9.3)
**When** I click "Export Bundle"
**Then** the cockpit-api streams a PDF download containing: cover page, case summary, full audit timeline, all reasoning traces, all officer rationale, all signatures with verification status, page numbers, generated-at timestamp
**And** the PDF is generated server-side via a deterministic template (no fonts/styles dependent on local renderer)

**Given** I select multiple cases for bulk export
**When** the export generates
**Then** the bundle contains an index page + per-case sections

### Story 9.5: JSON export bundle assembly with hash chain

As an Internal Auditor,
I want a JSON bundle alongside the PDF that contains the cryptographic hash chain + signatures for offline verification,
So that the bundle is mathematically self-validating (FR34, FR35).

**Acceptance Criteria:**

**Given** the PDF export (Story 9.4)
**When** the cockpit-api generates the bundle
**Then** alongside the PDF, a JSON file is included containing: every ledger entry's full payload, prev_hash, chain_hash, signature, signing_key_id, public_key (so verifier can validate without calling the platform)

**Given** the JSON bundle structure
**When** I run the offline verifier (Story 9.6) against it
**Then** verification succeeds for an unmodified bundle

### Story 9.6: Offline verifier CLI

As an Internal Auditor or regulator,
I want a standalone CLI tool that validates an audit bundle's hash chain and signatures without calling the platform,
So that trust is in math, not in our infrastructure (FR35, AR5).

**Acceptance Criteria:**

**Given** the verifier at `tools/verifier/src/verifier/cli.py`
**When** I run `python -m verifier check bundle.json`
**Then** it: (1) walks the chain checking `chain_hash[N] == sha256(prev_hash[N] || canonical_json(payload[N]))`, (2) verifies each entry's signature against its bundled public key, (3) reports any inconsistency with the offending entry ID

**Given** an unmodified bundle
**When** verification runs
**Then** the output is `OK · <N> entries verified · <duration>` and exit code 0

**Given** a tampered bundle (any byte changed in any entry)
**When** verification runs
**Then** the output identifies the first failing entry, with hash diff
**And** exit code is non-zero

**Given** the verifier source code
**When** measured
**Then** it is ≤ 300 LOC of Python, depends only on `cryptography` + `pydantic` (no platform dependencies)

### Story 9.7: Verifier wheel packaging + distribution

As an Internal Auditor downloading an audit bundle,
I want the verifier tool packaged as a standalone wheel I can run on any laptop,
So that I can verify without internet or platform access (FR35).

**Acceptance Criteria:**

**Given** the verifier at `tools/verifier/`
**When** `make build-verifier` runs
**Then** a `verifier-<version>.whl` is produced
**And** it ships alongside every audit export bundle (the bundle is a `.zip` containing `bundle.pdf`, `bundle.json`, `verifier.whl`, `README.md`)

**Given** the README in the bundle
**When** an auditor reads it
**Then** they see the 3-line install + verify command (`pip install verifier.whl && python -m verifier check bundle.json`)

### Story 9.8: LedgerViewer with hash chain visualization

As an Internal Auditor inside the cockpit,
I want a `LedgerViewer` panel that visualizes the hash chain with signature verification status,
So that I see the cryptographic structure visually (UX-DR32).

**Acceptance Criteria:**

**Given** I am in Regulator Lens (Story 9.3)
**When** the LedgerViewer panel renders
**Then** I see a vertical timeline of entries, each showing: entry ID, type, hash (truncated), signature status (green check / red X), signing_key_id

**Given** I click an entry
**When** it expands
**Then** I see the full hash, signature, public key, and the canonical-JSON payload

## Epic 10: Multi-Role Workflows (Approvals & Portfolio)

Team Lead approves/conditions/declines EDD cases from a dedicated queue; CCO sees portfolio dashboard with audit-readiness indicator; Tenant Admin can perform break-glass access via signed runbook.

### Story 10.1: Team Lead approval queue route

As a Team Lead,
I want a dedicated approval queue showing cases pending my approval,
So that I can quickly process EDD escalations from my team (FR36).

**Acceptance Criteria:**

**Given** my role is `team_lead`
**When** I navigate to `/t/{tenant_id}/approvals`
**Then** I see a list of cases in `pending_lead_approval` state assigned to my team
**And** each row shows: customer name, escalating analyst, reason, time waiting, risk band

**Given** I open a case from this queue
**When** the case canvas renders
**Then** it is read-only (can't edit rationale) with an "Approve / Approve with Conditions / Decline" action panel pinned at the bottom

**Given** my role is not `team_lead`
**When** I attempt the route
**Then** 403

### Story 10.2: Approve-with-conditions structured state in ledger

As a Team Lead,
I want my approval to capture conditions as structured state, not free-form text,
So that downstream systems can act on conditions deterministically (FR37).

**Acceptance Criteria:**

**Given** the approval action panel
**When** I select "Approve with conditions"
**Then** I see a typed form: condition type (enum: enhanced_monitoring, re_review_trigger, restricted_products, information_request), parameters (e.g., monitoring duration, trigger criteria), expiry date

**Given** I commit
**When** the cockpit-api persists
**Then** conditions are stored as structured `Condition` Pydantic objects in the case's `decision.conditions` array
**And** captured in the ledger entry

### Story 10.3: Lead approval ledger entry with signature

As the platform,
I want every Team Lead approval to be ledgered with the Lead's Ed25519 signature,
So that the approval is non-repudiable (FR37, P5).

**Acceptance Criteria:**

**Given** the Team Lead approval flow
**When** the Lead commits via the approval panel
**Then** the cockpit-ui signs the canonical decision payload using the Lead's keypair (Story 7.1 reused — Team Leads also have officer keys)
**And** the cockpit-api verifies and writes a `lead.approval_committed` ledger entry

### Story 10.4: CCO Portfolio Dashboard route

As a Chief Compliance Officer,
I want a Portfolio Dashboard summarizing my tenant's KYC operations,
So that I have a board-ready view (FR40).

**Acceptance Criteria:**

**Given** my role is `cco`
**When** I navigate to `/t/{tenant_id}/portfolio`
**Then** I see widgets: cases processed (this week), median case time, SLA breaches, risk-band distribution (donut), edit-rate distribution (histogram), audit-readiness indicator ("100% sealed ledger entries", "last mock audit: N remediations")

**Given** I click a widget
**When** drilldown is available
**Then** I see the underlying cohort (case list) — non-PII summary; full PII access requires `internal_auditor` role

### Story 10.5: Cohort export CSV

As a CCO,
I want to export aggregated, non-PII summary metrics for a time-bounded cohort,
So that I can share with the Board / Compliance Committee (FR41).

**Acceptance Criteria:**

**Given** I am on Portfolio Dashboard
**When** I click "Export Cohort"
**Then** I select a date range and grouping (e.g., by analyst, by case type, by jurisdiction)
**And** receive a CSV download with aggregated metrics (no PII)

**Given** my role is `cco`
**When** the export runs
**Then** PII fields are stripped at the API boundary (deny-by-default)

### Story 10.6: Break-glass admin runbook

As a Tenant Admin (via runbook in MVP),
I want to perform emergency read access to a case with cryptographic justification,
So that incidents can be resolved while maintaining audit (FR50, NFR-T6).

**Acceptance Criteria:**

**Given** the runbook at `docs/runbooks/break-glass-access.md`
**When** an admin follows it
**Then** they: (1) generate a justification ≥ 40 chars, (2) sign the justification with their admin key, (3) invoke a CLI script that creates a 24h read grant + signed `admin.break_glass_invoked` ledger entry
**And** the grant auto-expires; cannot be self-renewed

**Given** a break-glass grant is active
**When** the admin reads case data
**Then** every read is logged separately with the grant ID

### Story 10.7: Tenant config CLI runbook

As a Tenant Admin (via runbook),
I want to configure jurisdiction rules, SAR templates, and document taxonomy via runbook,
So that tenants can be onboarded without an admin UI in MVP (FR53).

**Acceptance Criteria:**

**Given** `docs/runbooks/tenant-config.md`
**When** the admin follows the steps
**Then** they: (1) edit `apps/agents/src/agents/jurisdictions/<jurisdiction>/` files (rules.py, risk_weights.yaml, sar_template.j2, doc_taxonomy.yaml), (2) update tenant config row to point to the jurisdiction, (3) restart cockpit-api

**Given** the runbook
**When** followed for screening vendor swap
**Then** the admin: (1) updates `SCREENING_PROVIDER` env var, (2) runs the conformance suite (Story 6.2), (3) restarts — zero changes to agent code (FR56, NFR-RI6)

## Epic 11: Pilot Hardening

System is pilot-ready. Mock internal audit returns zero remediation. Threat model authored. External pentest done with Critical/High remediated. DR rehearsal passed. WCAG 2.2 AA third-party audit passed. Performance budgets verified across canonical journeys. Confidence thresholds calibrated.

### Story 11.1: Threat model authoring

As the security lead,
I want a documented threat model covering agent mesh, ledger, screening boundary, document upload, and authentication,
So that NFR-S4 is satisfied and the model can be reviewed quarterly (NFR-S4, AR15).

**Acceptance Criteria:**

**Given** `docs/architecture/threat-model.md`
**When** the document is complete
**Then** it covers: data flow diagram with trust boundaries, STRIDE per asset (cases, ledger, documents, signing keys, screening adapter, OIDC), known mitigations referencing architecture decisions (S1–S10), residual risks, quarterly review schedule

**Given** the document
**When** reviewed by an external security advisor
**Then** advisor sign-off is recorded

### Story 11.2: External pentest engagement and remediation

As the security lead,
I want a third-party pentest completed with Critical and High findings remediated,
So that the platform is pilot-ready (NFR-S5, AR16).

**Acceptance Criteria:**

**Given** the pentest engagement (vendor selected, scope defined to cover the four canonical user journeys + API + admin runbooks)
**When** the pentest report is delivered
**Then** Critical findings are remediated and verified by re-test
**And** High findings are remediated within 7 days (NFR-S3 cadence)
**And** Medium/Low findings have triage tickets with target dates

**Given** remediation
**When** the report is finalized
**Then** the executive summary is filed in `docs/security/pentest-summary-<date>.md`

### Story 11.3: DR rehearsal with metrics capture

As the platform team,
I want a documented DR rehearsal that proves RPO ≤ 1h and RTO ≤ 4h,
So that NFR-A3 is verified, not just claimed (NFR-A3, AR18).

**Acceptance Criteria:**

**Given** `docs/runbooks/disaster-recovery.md`
**When** the team executes a controlled rehearsal in staging
**Then** they: (1) simulate primary cluster outage at T0, (2) execute the runbook, (3) measure: time to detect, time to declare incident, time to first byte from DR target, time to verified data restoration
**And** RPO observed ≤ 1h, RTO observed ≤ 4h
**And** rehearsal report filed with metrics + improvements

**Given** the rehearsal cadence
**When** the calendar is set
**Then** a quarterly recurring entry exists in the ops calendar (G3 from validation)

### Story 11.4: WCAG 2.2 AA third-party audit

As the accessibility lead,
I want a third-party WCAG 2.2 AA audit covering the MVP scope,
So that NFR-AC1 is verified (NFR-AC1, NFR-AC2, NFR-AC3, NFR-AC4, NFR-AC5).

**Acceptance Criteria:**

**Given** the engaged accessibility firm
**When** they audit the MVP cockpit
**Then** they cover: keyboard-only navigation across all canonical journeys, screen-reader (NVDA + VoiceOver) walkthroughs, color contrast across all tokens, focus indicator visibility, the confidence-banded system for color-blind users

**Given** findings
**When** Critical/High remediated and Medium/Low triaged
**Then** an audit certificate is filed and an executive summary lands in `docs/accessibility/audit-<date>.md`

### Story 11.5: Performance budget verification across canonical journeys

As the platform team,
I want measured evidence that the four canonical journeys hit the performance budgets,
So that NFRs P1–P4 are verified at pilot scale (NFR-P1, NFR-P2, NFR-P3, NFR-P4).

**Acceptance Criteria:**

**Given** Playwright e2e tests with Lighthouse + tracing
**When** I run the four canonical journeys (Triage, Investigation, Decision Commit, Regulator Lens Export) under a simulated 10-analyst concurrent load
**Then** measurements meet:
- Keyboard action p95 ≤ 50 ms (NFR-P1)
- Panel expand p95 ≤ 150 ms (NFR-P2)
- 50-node UBO Canvas interaction stays smooth (NFR-P3)
- Full mesh cold-start ≤ 2 min (NFR-P4 spirit)

**Given** budgets are violated
**When** the team triages
**Then** fixes are landed before pilot launch — performance budgets are non-negotiable

### Story 11.6: Confidence calibration study

As the data team,
I want a calibration study confirming each agent's confidence values match observed accuracy,
So that the 4-tier confidence system is meaningful, not cosmetic (P7, AR29).

**Acceptance Criteria:**

**Given** a held-out validation set per agent (DocIntel, Entity Verification, UBO, Screening, Risk Scoring)
**When** the calibration study runs
**Then** for each agent: Brier score, expected vs observed accuracy by band, recommended threshold adjustments
**And** thresholds in `lib/confidence.ts` and `agents/tools/confidence_calibrate.py` are updated

**Given** the calibrated thresholds
**When** the cockpit-ui re-renders cases
**Then** confidence pills reflect calibrated bands

### Story 11.7: India jurisdiction pack lockdown

As the compliance lead,
I want the India jurisdiction pack reviewed by an ex-RBI advisor and locked,
So that pilot deployment passes regulatory scrutiny (AR21).

**Acceptance Criteria:**

**Given** the advisor review
**When** rules at `apps/agents/src/agents/jurisdictions/india/rules.py`, risk_weights, SAR template, and doc taxonomy are reviewed
**Then** advisor sign-off is recorded
**And** any rule changes are merged before pilot launch

**Given** the FIU-XML SAR template
**When** validated against the latest FIU-India schema
**Then** generated SARs pass validation

### Story 11.8: Tenant onboarding/offboarding runbook full test

As the platform team,
I want the tenant onboarding + offboarding runbooks executed end-to-end against staging,
So that NFR-SC4 is verified (AR17, NFR-SC4).

**Acceptance Criteria:**

**Given** the onboarding runbook at `docs/runbooks/tenant-onboarding.md`
**When** executed against staging from a clean state
**Then** the result is: per-tenant Postgres schema created, per-tenant S3 bucket created, per-tenant HSM signing key created, IdP configured, initial users invited, sample case ingested + processed end-to-end

**Given** the offboarding runbook
**When** executed against the same tenant
**Then** the result is: full export bundle generated, data deleted (after retention period), ledger reference preserved (hash chain integrity)

### Story 11.9: Mock internal audit pass with zero remediation

As the program lead,
I want an internal-auditor walkthrough of 5 closed cases with zero remediation findings,
So that the audit story is verified before regulator review (PRD Success Criteria).

**Acceptance Criteria:**

**Given** 5 sample SME onboarding cases closed end-to-end through the cockpit
**When** the internal auditor (or a named ex-auditor advisor) runs through Regulator Lens + offline verifier
**Then** zero remediation asks are filed
**And** the audit summary is filed in `docs/audits/mock-internal-<date>.md`

### Story 11.10: Feature flags per tenant

As the operations team,
I want per-tenant feature flags enabling/disabling individual agents and capabilities,
So that pilot tenants can be configured incrementally without code changes (FR54).

**Acceptance Criteria:**

**Given** a `tenant_features` table per tenant with rows for each agent and capability
**When** a flag is toggled
**Then** the cockpit-api respects it on the next request (no restart needed)
**And** disabled agents are skipped in the Case Supervisor's fan-out (their state shows "disabled" in the AgentCopilotPane)

**Given** the runbook
**When** ops toggles a flag
**Then** the change is ledgered as a `tenant.config_changed` entry (per the audit story)

### Story 11.11: Observability dashboards

As the operations team,
I want product telemetry dashboards in Grafana,
So that NFR-O5 is verified before pilot (NFR-O5).

**Acceptance Criteria:**

**Given** Grafana + Tempo + Loki + Mimir running per I7
**When** I open the cockpit operations dashboard
**Then** I see panels for: case-time distribution (per analyst, per week), edit-rate distribution, mode-usage frequency, agent precision (sampled), NPS trend (when survey lands), SLA-breach rate, audit-readiness indicator

**Given** P1 alerts are configured
**When** any of the trigger conditions occur (ledger integrity failure, screening down, auth down, agent cascade)
**Then** on-call is paged within 1 min (NFR-O6)

---

## Story Count Summary

| Epic | Story Count | Cumulative |
|---|---|---|
| Epic 1 — Foundations | 11 | 11 |
| Epic 2 — Case Ingest | 11 | 22 |
| Epic 3 — First Agent + Ledger | 14 | 36 |
| Epic 4 — Triage Mode + Mesh Visibility | 12 | 48 |
| Epic 5 — Entity & UBO | 10 | 58 |
| Epic 6 — Screening + Reasoning Traces | 10 | 68 |
| Epic 7 — Decision Authoring | 15 | 83 |
| Epic 8 — Zen Mode + EDD Writing | 7 | 90 |
| Epic 9 — Audit + Regulator Lens + Verifier | 8 | 98 |
| Epic 10 — Multi-Role | 7 | 105 |
| Epic 11 — Pilot Hardening | 11 | 116 |

**Total: 116 stories across 11 epics.** Each independently completable, each contributing to a user-value-focused epic, no forward dependencies within an epic.

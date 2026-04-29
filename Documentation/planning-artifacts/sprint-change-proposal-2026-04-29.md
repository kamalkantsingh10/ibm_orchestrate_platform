---
title: Sprint Change Proposal — Demo Re-Scope
date: 2026-04-29
project_name: ibm_orchestrate_platform
user_name: Kamal
trigger: strategic-pivot
scope_classification: major
status: pending-approval
inputDocuments:
  - Documentation/planning-artifacts/prd.md
  - Documentation/planning-artifacts/architecture.md
  - Documentation/planning-artifacts/epics.md
  - Documentation/implementation-artifacts/sprint-status.yaml
---

# Sprint Change Proposal — Demo Re-Scope

## Section 1 — Issue Summary

### Problem Statement

The current scope (11 epics, 116 stories) targets a regulated-bank production platform — OIDC SSO, multi-tenant schema isolation, HSM-backed Ed25519 hash-chained audit ledger, offline cryptographic verifier, multi-cloud adapters, pre-pilot pentest, DR rehearsal, WCAG 2.2 AA third-party audit. That scope is appropriate for the **bank-buyer audience** that the PRD names alongside the **Path B (Orchestrate + ADK reference implementation) audience**.

Mid-execution (Epic 1 in progress: 3 stories at `review`, 8 at `ready-for-dev`), the user has clarified the actual deliverable:

> *"Me and my 3 bosses — I want to prove that we can use a full-fledged application can be built using Agents (IBM ADK). This can be a local demo — this will not proceed to 'something bigger'. I want the UI (look) to be professional. I want to show agentic workflows happening."*

This is the **Path B audience exclusively**. The bank-buyer audience is removed. The demo runs locally on the user's machine, synchronously (Kamal driving, three bosses watching), and is a terminal artifact — no production rollout follows.

### Issue Type

**Strategic pivot.** Not a misunderstanding; the original PRD correctly named both audiences. What changed is the user's chosen audience for this build.

### Evidence

- Original PRD §"Project Classification" identifies dual audience (bank buyer + Path B Orchestrate/ADK reference)
- Original PRD §"Success Criteria" includes both bank-buyer outcomes (LOI, pilot live, paying bank) and Path B outcomes (ADK pattern coverage, developer-audience "wow")
- Original sprint scope (11 epics, 116 stories) was sized for the bank-buyer audience including Epic 11 (Pilot Hardening) — pentests, DR, WCAG audit, performance budgets — none of which serve a local demo
- User has explicitly approved a 63-story re-scope across 9 conversational rounds covering: epic-level cuts, story-level cuts, tech simplification choices, demo-specific additions

---

## Section 2 — Impact Analysis

### Epic Impact

| Epic | Original | Re-scoped | Action |
|------|---------:|----------:|--------|
| 1 — Foundations & First Sign-In | 11 | 4 | Gut: drop OIDC, RBAC, multi-tenant isolation, session timeout, i18n, ADR discipline, CI/CD with federated cloud creds. Replace with user-switcher (3 hardcoded users) + monorepo + dev env + ≤60min fresh-clone story. Rename to **"Foundations & Cockpit Shell"**. |
| 2 — Case Ingest & Lifecycle | 11 | 4 | Gut: drop ingestion API, idempotency, presigned URL upload, webhook subscription/dispatch/retry, rate limiting, OpenAPI/Scalar serving. Keep case schema, GET case retrieval, queue-rail population, fixture loader. |
| 3 — First Agent & Cryptographic Audit Ledger | 14 | 7 | Drop HSM/KeyVault/HPCS adapters, Ed25519 hash chain primitive, multi-cloud DocStore adapter, multi-impl DocAI adapter, 50-doc benchmark, document SHA-256 hashing. Replace cryptographic ledger with JSON append-only log. Rename to **"First Agent & Audit Log"**. |
| 4 — Triage Mode & Live Mesh Visibility | 12 | 9 | Drop Redis pub/sub coordination, in-app notifications, keyboard shortcut help overlay. Single-worker SSE. Command palette **kept**. |
| 5 — Entity & UBO Investigation | 10 | 9 | Drop GST verify tool (MCA alone proves multi-tool agent pattern). |
| 6 — Screening, Reasoning Traces & Conversational Mesh | 10 | 8 | Drop ComplyAdvantage adapter (mock-only), drop screening procurement runbook. |
| 7 — Decision Authoring & Officer Signing | 15 | 9 | Drop officer keypair generation, encrypted private-key storage, client-side WebCrypto signing, server-side Ed25519 verification, officer-signed ledger entry, edit-rate metric tracking. Basic evidence shelf in Decision Zone (7-14) **kept** (was a candidate cut at item #9; not in approved 1-7 list). Rename to **"Decision Authoring"**. |
| 8 — SAR/EDD Zen Mode & Narrative Drafting | 7 | 7 | **No cuts.** (8-5 EvidenceShelf with attachment ingest, 8-6 evidence SHA-256, 8-7 EDD outcome auto-enqueue were all candidate cuts at items #10–12 of the ranked cut list; not in the approved 1-7 cuts.) |
| 9 — Audit Trail, Regulator Lens & Offline Verifier | 8 | 3 | Drop offline verifier CLI, verifier wheel packaging, JSON export with hash chain (no real chain), LedgerViewer chain visualization, role-scoped timeline endpoint (UI-side gating). Keep audit trail timeline component, regulator lens read-only mode, PDF export bundle. Rename to **"Audit Trail, Regulator Lens & Export"**. |
| 10 — Multi-Role Workflows | 7 | 3 | Drop CCO Portfolio Dashboard, cohort CSV export, break-glass admin runbook, tenant config CLI runbook. Keep team lead approval queue, approve-with-conditions, lead approval log entry (no crypto signature). Rename to **"Multi-Role (Lead Approvals)"**. |
| 11 — Pilot Hardening | 11 | **0** | **Cut entirely.** Pentest, DR rehearsal, WCAG audit, performance budgets, confidence calibration, India jurisdiction lockdown, tenant onboarding test, mock internal audit, feature flags, observability dashboards — none serve a local demo. |
| **Totals** | **116** | **63** | **46% reduction** |

### Story Impact

**Stories already at `review` status** — must not be reverted; remain in place but acceptance criteria may simplify:
- 1-1 Bootstrap polyglot monorepo (canonical scaffold)
- 1-2 One-command local development environment
- 1-3 CI/CD skeleton with OIDC federated cloud creds → **simplify to optional basic CI** (build + lint only)

**Stories already at `ready-for-dev`** — most of Epic 1's `ready-for-dev` set is being cut or transformed:
- 1-4 ADR discipline → **defer** (optional for demo; can revive if Path B docs needed)
- 1-5 Postgres tenant schema isolation → **cut** (SQLite, no multi-tenant)
- 1-6 OIDC authentication → **replace with user-switcher**
- 1-7 Deny-by-default RBAC → **simplify to UI-side role gating**
- 1-8 Tenant scoping middleware → **cut**
- 1-9 Session inactivity timeout → **cut**
- 1-10 Empty cockpit shell with auth-protected routes → **transform** to "Cockpit shell with user-switcher (3 hardcoded users)"
- 1-11 i18n scaffolding → **cut**

**New stories to add:**
- New Epic 1 story: **"Fresh-clone to running demo in ≤60 min"** (README polish, setup verification script, seeded fixtures, single-command bootstrap)
- New Epic 1 story: **"User-switcher with 3 hardcoded roles (Analyst / Team Lead / Regulator)"**
- New Epic 2 story: **"Fixture case loader (3 seeded cases: clean approval, hairy shell-company UBO, screening hit)"**

### Artifact Conflicts

#### PRD (`Documentation/planning-artifacts/prd.md`)

**Audience reduction** — PRD currently names two audiences:
1. Bank buyer (CCO at mid-size bank, 500K–10M accounts, jurisdiction-first India)
2. Path B (Orchestrate + ADK reference implementation showcase)

For this re-scope, **only audience #2 remains active**. Audience #1's success criteria (LOIs, pilot, paying bank, RBI/FIU validation) are deferred indefinitely.

**Functional Requirements impact:**

| FR Category | Status | Notes |
|---|---|---|
| FR1–4 Queue & Case Navigation | **Kept** | Queue, keyboard nav, mode switching all in scope |
| FR5 Command palette | **Deferred** | Cut from Epic 4 |
| FR6 In-app notifications | **Deferred** | Cut from Epic 4; manual user-switching for the demo |
| FR7–10 Case Canvas & Data Display | **Kept** | All four FRs in scope |
| FR11–14 Agent Mesh Visibility | **Kept** | Live activity feed, reasoning trace, Cockpit Chat, auto-intake — all preserved |
| FR15–17 Entity & UBO | **Kept** (FR17 partially) | UBO graph + drag-correct kept; FR17 reduced from MCA+GST cross-ref to MCA-only |
| FR18–21 Screening & Risk | **Kept** | Mock screening adapter; auto-recalc kept |
| FR22–26 Decision Authoring & Commit | **Kept** | Decision Zone, undo, outcomes, Zen mode, Writing Agent v1+v2 with citation — all preserved |
| FR27 Edit-rate metric | **Deferred** | Cut from Epic 7; can be re-added trivially if requested |
| FR28 Cryptographic hash-chained ledger | **Simplified** | Replaced with JSON append-only log file; visual treatment (LedgerViewer) deferred |
| FR29 Officer-signed actions | **Simplified** | Log entry without Ed25519 signature; user identity recorded |
| FR30 Role-scoped timeline | **Kept** (UI-side) | Timeline still rendered; role gating moves to UI level instead of endpoint level |
| FR31 Document immutability via SHA-256 | **Deferred** | Documents stored on local filesystem; provenance pill suffices for demo |
| FR32 Prevent ledger writes via normal APIs | **N/A** | No external API in demo; ledger is internal-only |
| FR33 Regulator Lens read-only mode | **Kept** | One of three "tangible artifact" demo moments |
| FR34 PDF + JSON audit bundle export | **Kept (PDF)** | PDF export kept; JSON bundle deferred (no hash chain to export) |
| FR35 Self-verifying audit bundle (offline verifier) | **Deferred** | No verifier CLI in demo |
| FR36–39 Approval workflows | **Kept** | Lead approval queue, approve-with-conditions, lead approval ledger entry, EDD escalation (manual) |
| FR40–41 Portfolio & Reporting | **Deferred** | CCO Dashboard cut entirely |
| FR42–46 Platform Integration API | **Deferred** | No external API for the demo |
| FR47 SAML/OIDC SSO | **Replaced** | User-switcher dropdown with 3 hardcoded users |
| FR48 RBAC deny-by-default | **Simplified** | UI-side role gating |
| FR49 Tenant isolation | **Deferred** | Single-tenant; no multi-tenant abstraction |
| FR50 Break-glass admin | **Deferred** | N/A for single-tenant demo |
| FR51 Session inactivity timeout | **Deferred** | N/A |
| FR52–56 Agent Configuration & Operations | **Deferred (FR55 partial)** | Tenant admin config, feature flags, vendor adapter conformance — all deferred. Agent failure isolation still desirable but not formalized. |

**Non-Functional Requirements impact:**

- **NFR-P (performance):** Targets remain aspirational; no formal verification in demo
- **NFR-S (security):** All deferred — no rate limiting, no account lockout, no Snyk scan, no threat model, no pentest
- **NFR-A (availability):** Deferred — no SLO, no DR, no MTTR
- **NFR-SC (scalability):** Deferred — single-machine demo; 10× horizontal scale claim removed
- **NFR-AC (accessibility):** Aspirational — design follows WCAG by convention but no third-party audit
- **NFR-O (observability):** Simplified — no OpenTelemetry/Orchestrate trace export; structured logs sufficient
- **NFR-CP (compatibility):** Single browser (Chrome) for demo; multi-browser claim removed
- **NFR-RI (Reference Implementation / Path B):** **PROMOTED to primary success metric.** Kept and prioritized:
  - NFR-RI1 ADK pattern coverage — *kept* (supervisor/collaborator, agent-as-tool, Pydantic-contracted tools, HITL approval, conversational-with-mesh-as-tools all demonstrated in Epics 3/5/6/7/8/10)
  - NFR-RI2 ADR discipline — *deferred* (optional)
  - NFR-RI3 Ruff/mypy/ESLint/TS strict — *kept* (low cost, professional appearance)
  - NFR-RI4 80% test coverage on agent logic — *aspirational* (not formally enforced)
  - NFR-RI5 Clone + local demo ≤ 30 min — **TIGHTENED to ≤60 min** as explicit Epic 1 acceptance criterion (was 30 min in PRD; relaxing to 60 min makes the success criterion realistic without dropping it)
  - NFR-RI6 Every adapter ships with second reference adapter — *deferred* (mock-only)
  - NFR-RI7 LLM prompts in Jinja templates with golden inputs — *kept* (cheap, professional)
- **NFR-Compliance:** All deferred — no RBI Master Direction posture, no DPDP Act handling, no FIU-XML schema, no auditability floor

#### Architecture (`Documentation/planning-artifacts/architecture.md`)

Major sections requiring update:

| Section | Change |
|---|---|
| Project Context Analysis → Scale & Complexity | Reclassify from "Enterprise / regulated" to "Reference implementation / demo." Remove dual-audience framing. |
| Project Context Analysis → Cross-Cutting Concerns | Demote tenant scoping, provenance signing pipeline, pluggability conformance, real-time streaming with tenant isolation, LLM PII minimization. Promote ADK pattern coverage. |
| Open Architectural Decisions Inherited from Planning | Resolve all 6 decisions:<br/>1. Screening vendor → **mock-only**<br/>2. Document AI → **LLM-based extraction (no DocAI integration)**<br/>3. HITL UX → **blocking inside Decision Zone (no async notifications)**<br/>4. Jurisdictional scope → **India-only narrative; no pluggable proof**<br/>5. Agent memory → **shared case-state, stateless-functional**<br/>6. Frontend → **resolved (React + FastAPI as PRD specified; Streamlit explicitly rejected for UI fidelity reasons re-confirmed during re-scope discussion)** |
| Starter Template Evaluation | Keep Polyglot monorepo (Poetry + pnpm preserved per user decision); simplify infra/IaC scope |
| Repository Layout | Keep `apps/cockpit-ui`, `apps/cockpit-api`, `apps/agents`, `packages/contracts`. **Drop** `tools/verifier` (no offline verifier in demo). **Drop or simplify** `infra/` to a `docker-compose.yml`-equivalent (or none, since SQLite doesn't need it). |
| Persistence | **Postgres → SQLite** (single file). SQLAlchemy 2.0 + Alembic stay. asyncpg removed. |
| Auth | OIDC SSO + SAML → **user-switcher dropdown** (3 hardcoded users in seed data) |
| Caching / Pub-Sub | Redis → **in-memory (single worker)** |
| Background work | Celery/Arq/Temporal → **FastAPI background tasks** |
| Object storage | S3-compatible adapter → **local filesystem (`./fixtures/uploads/`)** |
| HSM / Signing | HSM-backed Ed25519 → **JSON append-only log file** |
| Audit ledger | Hash-chained → **append-only JSON log** |
| Vendor adapters | Two-impl conformance (Vault Transit + HPCS, Vault + S3, etc.) → **mock-only** |
| Document AI | IBM Document AI / Watson Discovery / custom → **single LLM call against extracted text** |
| Deployment topology | Multi-service / multi-cloud → **single FastAPI process + Vite dev server + SQLite + filesystem** |
| Observability | OpenTelemetry + Orchestrate trace export + per-tenant partitioning → **structured stdout logs** |
| Pre-pilot pentest, DR rehearsal, WCAG audit, performance budgets | **All deferred** |

**Recommended approach:** Add a **"Demo Scope Addendum"** section near the top of architecture.md (after Project Context Analysis) summarizing all simplifications in a single anchor, rather than scatter-editing every section. The addendum acts as the canonical demo-time interpretation; original sections preserve the bank-buyer architecture for posterity.

#### UX Design Specification (`ux-design-specification.md`)

**No changes required.** UI fidelity is the load-bearing constraint of the re-scope. Every visual primitive (confidence pills, provenance pills, status pills, agent face SVGs, motion flavors, Tiptap editor, force-directed UBO, seal animation, undo countdown ring, Zen mode treatment, tonal typographic shift, command palette styling) is preserved or governed by stories that are kept.

Two minor UX-spec implications worth flagging:
- **Command palette styling** is preserved as a design primitive but not implemented (story 4-9 cut). If the spec describes it as required for the demo, recommend annotating "deferred" inline.
- **In-app notification visual** similarly: kept in spec, story cut.

#### Documentation Project (`docs/index.md`)

Not present — no impact.

### Technical Impact

**Code already merged (Epic 1 stories at `review`):**
- `1-1-bootstrap-the-polyglot-monorepo-from-the-canonical-scaffold` — **no rollback needed**; the polyglot monorepo structure is preserved per user decision to keep Poetry + pnpm
- `1-2-one-command-local-development-environment` — **no rollback needed**; aligns directly with new "≤60 min fresh-clone" goal, may need extension to include seeded fixtures and verification script
- `1-3-cicd-skeleton-with-oidc-federated-cloud-creds` — **simplification recommended**: strip federated-cloud OIDC config; basic GH Actions CI (lint + test on PR) suffices. If user prefers, the entire story can be reverted to backlog and CI omitted from the demo.

**Infrastructure simplifications (low effort, high clarity gain):**
- Remove Postgres setup from dev env → SQLite (single file, zero infra)
- Remove Redis setup
- Remove S3-compatible mock setup
- Remove HSM mock setup

**Stories at `ready-for-dev` to be cut (8 of 11 in Epic 1):** No code written yet; clean cut.

---

## Section 3 — Recommended Approach

### Option Evaluation

| Option | Viability | Effort | Risk | Notes |
|---|---|---|---|---|
| **1. Direct Adjustment** | Partially viable | Medium | Low | Most cut stories haven't been started; modifying remaining stories within the existing epic structure is straightforward. But Epic 11 needs full removal and Epics 1, 7, 9 need substantial restructuring — beyond simple "modify in place." |
| **2. Potential Rollback** | Limited applicability | Low | Low | Only 3 stories at `review` (1-1, 1-2, 1-3). No rollback needed for 1-1 and 1-2; 1-3 only needs simplification, not rollback. |
| **3. PRD MVP Review** | **Viable — recommended** | Medium | Low | This is fundamentally an MVP-scope reduction driven by an audience pivot. The cleanest path is to formally redefine the MVP at the PRD level (audience reduced to Path B; bank-buyer audience deferred), regenerate epics, and update architecture. |

### Selected Approach: **MVP Review (Option 3)**

**Justification:** The change is not a tactical course-correction inside the existing plan — it is a strategic redefinition of the deliverable from "regulated-bank platform with reference-implementation co-benefit" to "reference-implementation demo with professional UI." Treating this as Direct Adjustment would leave the PRD asserting bank-buyer success criteria (LOIs, pilot, RBI validation) that no longer apply, and the architecture asserting cryptographic guarantees that aren't being built. Better to formally redefine the MVP than to leave artifacts inconsistent with execution.

### Implementation effort estimate

- **Re-scoped epics + stories:** ~10 hours of re-authoring (epics.md, sprint-status.yaml, individual story files for the new stories)
- **Architecture updates:** ~3 hours (add Demo Scope Addendum + update affected sections)
- **PRD update:** ~2 hours (add Demo Scope Addendum noting audience reduction; flag deferred FRs/NFRs)
- **Net implementation effort gained:** Very large — 53 stories (~46%) removed from build queue

### Risk assessment

- **Low** — the cuts preserve every UI fidelity element (the critical constraint) and every named ADK pattern (the success criterion). The risk is operational only: ensuring all four planning artifacts (PRD, architecture, epics, sprint-status) remain consistent after the re-scope.

### Timeline impact

User has explicitly de-emphasized timeline ("do not worry about the demo day"). Net effect: **~46% reduction in build queue, no other timeline anchor.**

---

## Section 4 — Detailed Change Proposals

### 4.1 — `epics.md`

**Action:** Full rewrite.

Re-scoped structure (10 epics, 63 stories). Sequencing principle preserved: progressive complexity, foundations first, vertical slice through one agent + minimal UI early, layered richness after.

| # | Epic | Stories | Demo role |
|---|------|--------:|-----------|
| 1 | Foundations & Cockpit Shell | 4 | Monorepo, dev env, ≤60min clone, cockpit shell with user-switcher |
| 2 | Case Ingest & Lifecycle | 4 | Case schema, GET case, queue rail, fixture loader (3 seeded cases) |
| 3 | First Agent & Audit Log | 7 | Agent action decorator, Pydantic contracts, Document Intelligence agent, Case Supervisor intake fan-out, documents panel with provenance, confidence pill, JSON append-only log |
| 4 | Triage Mode & Live Mesh Visibility | 9 | Queue ordering, keyboard triage, agent face SVGs, motion flavors, Agent Copilot pane with live activity feed, single-worker SSE, mode switcher, status pills |
| 5 | Entity & UBO Investigation | 9 | Entity Verification agent (mock MCA), UBO Graph agent, force-directed canvas, drag-correct with learning event, Risk Scoring agent, risk score breakdown, auto-recalc, panels |
| 6 | Screening, Reasoning Traces & Cockpit Chat | 8 | Mock Screening adapter, Screening agent, screening explainer, reasoning-trace contract + endpoint + slide-out, Cockpit Chat agent (mesh-as-tools) + UI |
| 7 | Decision Authoring | 9 | Decision Zone with Tiptap, tonal typographic shift, Writing Agent v1 (rationale draft), undo timer + UndoPill, seal animation, POST /decision endpoint, evidence shelf basic, decision outcomes |
| 8 | Zen Mode & EDD Memo Drafting | 7 | Cmd+4 mode switch, Zen visual treatment, Writing Agent v2 (EDD memo), citation-by-ledger-ID enforcement, narrative rendering with structured sections, evidence reference list, Zen exit/commit |
| 9 | Audit Trail, Regulator Lens & Export | 3 | AuditTrailTimeline component, Regulator Lens read-only mode, PDF export bundle |
| 10 | Multi-Role (Lead Approvals) | 3 | Team Lead approval queue, approve-with-conditions structured state, lead approval log entry |
| **Total** | | **63** | |

**Cut entirely:** Epic 11 (Pilot Hardening) — 11 stories.

### 4.2 — `sprint-status.yaml`

**Action:** Full rewrite, preserving status of in-flight stories.

```yaml
development_status:
  epic-1: in-progress
  1-1-bootstrap-the-polyglot-monorepo-from-the-canonical-scaffold: review        # preserved
  1-2-one-command-local-development-environment: review                         # preserved
  1-3-cockpit-shell-with-user-switcher-three-hardcoded-roles: backlog          # NEW (replaces old 1-3 OIDC CI/CD)
  1-4-fresh-clone-to-running-demo-in-sixty-minutes: backlog                    # NEW
  epic-1-retrospective: optional

  epic-2: backlog
  2-1-case-schema-and-state-machine: backlog
  2-2-get-case-retrieval-api: backlog
  2-3-case-appears-in-queue-rail-basic-ordering: backlog
  2-4-fixture-case-loader-with-three-seeded-cases: backlog                     # NEW
  epic-2-retrospective: optional

  # ... (epics 3–10 follow; full structure in re-written file)

  # epic-11: REMOVED
```

**Old stories preserved as `done` or `review`:** 1-1, 1-2 (no rollback). Old 1-3 marked with replacement note.

**Old stories deleted from tracking:** 1-4 through 1-11 (Epic 1 cuts). All Epic 2 originals except 2-1, 2-5, 2-6 (renumbered). All Epic 11 stories. Selectively in Epics 3–10 per Section 2 table above.

### 4.3 — `architecture.md`

**Action:** Insert "Demo Scope Addendum" section after "Project Context Analysis." Original sections preserved as bank-buyer-audience reference.

**New section content (summarized):**

```markdown
## Demo Scope Addendum (2026-04-29)

This project's deliverable has been re-scoped to a Path B (Orchestrate + ADK
reference implementation) demo. The bank-buyer audience and its commercial
roadmap are deferred. Below are the architectural choices for the demo build.
The original architecture sections in this document remain valid for the
bank-buyer scope and can be revived if that path resumes.

### Stack changes for demo
- **Persistence:** SQLite (single file) replaces Postgres + asyncpg.
- **Auth:** User-switcher dropdown with 3 hardcoded roles replaces SAML/OIDC.
- **Caching / Pub-Sub:** In-memory state, single worker. No Redis.
- **Background work:** FastAPI background tasks. No Celery/Arq/Temporal.
- **Object storage:** Local filesystem `./fixtures/uploads/`. No S3.
- **HSM / signing:** None. Audit log is a JSON append-only file.
- **Audit ledger:** JSON append-only log. Not hash-chained, not signed.
- **Vendor adapters:** Mock-only. No second reference adapter.
- **Document AI:** Single LLM call against extracted text (no DocAI integration).
- **Observability:** Structured stdout logs. No OpenTelemetry, no Orchestrate trace export.

### Cross-cutting concerns demoted
- Tenant scoping: single-tenant, no `tenant_id` enforcement.
- Provenance signing pipeline: provenance metadata kept; signing dropped.
- Pluggability via conformance suites: dropped.
- Real-time tenant-partitioned streaming: replaced with single-worker SSE.
- LLM PII minimization: deferred (synthetic fixture data only).
- Keyboard + screen-reader concurrency: aspirational, not audited.
- Per-tenant observability partitioning: N/A (single-tenant).

### What stays
- Polyglot monorepo (Poetry + pnpm) — user decision to preserve.
- Pydantic contracts on every agent and tool boundary (NFR-RI1 critical).
- ADK pattern coverage (NFR-RI1) — supervisor/collaborator, agent-as-tool,
  Pydantic-contracted tools, HITL approval, conversational-with-mesh-as-tools.
- React + FastAPI + TypeScript strict.
- Radix + Tailwind + shadcn/ui + Framer Motion + Lucide + react-flow.
- ≤60 min fresh-clone-to-running-demo (relaxed from NFR-RI5 ≤30 min).
- LLM prompts in Jinja templates with golden inputs (NFR-RI7).

### What's deferred indefinitely
- Pre-pilot pentest, DR rehearsal, WCAG 2.2 AA third-party audit
- Performance budget verification
- Confidence calibration study
- India jurisdiction-pack lockdown
- Tenant onboarding/offboarding runbook
- Mock internal audit pass
- Per-tenant feature flags
- Observability dashboards
- ADR discipline (optional; can revive if Path B docs needed)
- 80% test coverage gate (aspirational; not enforced)
```

### 4.4 — `prd.md`

**Action:** Insert "Demo Re-Scope Note" section after "Executive Summary." Original PRD content preserved.

**New section content (summarized):**

```markdown
## Demo Re-Scope Note (2026-04-29)

This PRD originally targeted two audiences: (1) bank-buyer (CCO at mid-size
bank) and (2) Path B (IBM Orchestrate + ADK reference implementation). The
build has been re-scoped to audience #2 only. The deliverable is a local demo
shown synchronously to the user and three internal stakeholders, proving that
a full-fledged professional application can be built using IBM ADK agents.
The bank-buyer commercial roadmap (LOIs, pilot, paying bank, RBI/FIU
validation) is deferred indefinitely.

### Success criteria for demo (active)
- All 8 MVP agents demonstrably exercise distinct ADK patterns per Path B
  pattern checklist (NFR-RI1)
- Three bosses watching synchronously walk away saying "I didn't know
  Orchestrate could do this"
- UI fidelity matches the mockup; demo presents as a professional product,
  not a tooling demo

### Success criteria deferred (bank-buyer)
- Median SME case time ≤ 15 min, officer NPS ≥ 40, 80% "changes how I feel
  about the work," mock audit zero remediation, agent precision ≥ 95% on
  benchmarks, signed pilot LOIs, paid bank by 12-month — ALL DEFERRED.

### Functional/non-functional requirements impact
See Sprint Change Proposal 2026-04-29 §2 for the full FR/NFR table. Briefly:
- Decision Authoring, Zen Mode, Reasoning Traces, Cockpit Chat, UBO graph,
  Regulator Lens read-only, PDF export, Lead approval workflow — ALL KEPT.
- OIDC, multi-tenant isolation, cryptographic ledger, offline verifier,
  HSM signing, vendor adapter conformance, pentest, DR, WCAG audit, CCO
  Portfolio Dashboard, platform integration API — ALL DEFERRED.
```

### 4.5 — UX Design Specification (`ux-design-specification.md`)

**Action:** No changes required. (UI fidelity is the load-bearing demo constraint; every UI primitive in the spec is preserved or governed by retained stories.)

Optional (not in this proposal): annotate command palette and notification system as "deferred" inline if Kamal wants the spec to reflect demo scope.

---

## Section 5 — Implementation Handoff

### Scope Classification: **Major**

This is a fundamental MVP redefinition affecting all four planning artifacts (PRD, architecture, epics, sprint-status), not a tactical story-level change.

### Handoff Plan

| Recipient | Responsibility |
|---|---|
| **PM (John, this skill)** | Owns this proposal. After approval, executes file rewrites for `epics.md`, `sprint-status.yaml`, and the addenda for `prd.md` and `architecture.md`. |
| **Architect (Winston)** | Optional — if Kamal wants the architecture's Demo Scope Addendum elaborated into full-section rewrites with diagrams, route to `bmad-agent-architect`. For this proposal, the addendum approach is recommended (cheaper, preserves bank-buyer scope intact). |
| **Dev (Amelia)** | Picks up after planning artifacts are updated. Story 1-3 (old: CI/CD with OIDC federated creds) requires either rollback to `backlog` or simplification scope. Story 1-2 (one-command dev env) acceptance criteria should be reviewed against the new "≤60 min fresh-clone" story. |
| **Sprint planning (`bmad-sprint-planning`)** | After file updates, run sprint planning to regenerate sprint structure cleanly. |

### Success Criteria for This Sprint Change Proposal

- [ ] `epics.md` rewritten with 10 epics, 63 stories
- [ ] `sprint-status.yaml` rewritten preserving in-flight statuses
- [ ] `prd.md` Demo Re-Scope Note inserted
- [ ] `architecture.md` Demo Scope Addendum inserted
- [ ] In-flight stories (1-1, 1-2, old 1-3) confirmed for either preservation or simplification
- [ ] User explicit approval recorded
- [ ] No orphaned story files in `Documentation/implementation-artifacts/` (cut stories' files removed or archived)

---

## Section 6 — Approval

**Approved by:** _pending_
**Date:** _pending_

Once approved, this proposal becomes the canonical statement of the demo re-scope. PM executes file updates immediately following approval.

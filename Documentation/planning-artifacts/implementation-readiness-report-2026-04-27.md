---
stepsCompleted:
  - step-01-document-discovery
  - step-02-prd-analysis
  - step-03-epic-coverage-validation
  - step-04-ux-alignment
  - step-05-epic-quality-review
  - step-06-final-assessment
workflow_completed: true
completion_date: 2026-04-27
inputDocuments:
  - Documentation/planning-artifacts/prd.md
  - Documentation/planning-artifacts/architecture.md
  - Documentation/planning-artifacts/ux-design-specification.md
missingDocuments:
  - epics-and-stories
workflowType: 'implementation-readiness'
project_name: 'ibm_orchestrate_platform'
user_name: 'Kamal'
date: '2026-04-27'
status: 'partial-complete'
overallVerdict: 'UPSTREAM READY · EPICS REQUIRED BEFORE IMPLEMENTATION'
---

# Implementation Readiness Assessment Report

**Date:** 2026-04-27
**Project:** ibm_orchestrate_platform (KYC Cockpit)

## Step 1 — Document Discovery

### Inventory

| Document Type | Status | File | Size | Modified |
|---|---|---|---|---|
| PRD | ✅ Found | `Documentation/planning-artifacts/prd.md` | 77 KB | 2026-04-24 |
| Architecture | ✅ Found | `Documentation/planning-artifacts/architecture.md` | 85 KB | 2026-04-27 |
| UX Design | ✅ Found | `Documentation/planning-artifacts/ux-design-specification.md` | 151 KB | 2026-04-25 |
| UX Visual artifacts | ✅ Supporting | `ux-design-directions.html`, `ux-mockups.html` | 71 KB / 136 KB | 2026-04-25 |
| Epics & Stories | ❌ **Not found** | — | — | — |
| Product Brief (informational) | ✅ Found | `Documentation/planning-artifacts/product-brief.md`, `product-brief-distillate.md` | 9 KB / 10 KB | 2026-04-24 |

### Critical Issues

- ⚠️ **Epics & Stories document is missing.** This readiness check will run in **partial mode** — it can validate PRD ↔ Architecture ↔ UX alignment but cannot validate epic coverage or epic quality.
- ✅ **No duplicates.** Every document exists as a single whole file; no whole+sharded conflicts.

### Path Selected

**Path 1 (partial):** Validate upstream document alignment now; epics/stories to be authored next via `bmad-create-epics-and-stories`, after which a full readiness check can be re-run.

## Step 2 — PRD Analysis

### Functional Requirements (56 FRs across 12 categories)

**Queue & Case Navigation (FR1–FR6):**

- **FR1:** KYC Analysts can view a queue of assigned cases ordered by risk × SLA × continuity.
- **FR2:** KYC Analysts can navigate the queue using keyboard shortcuts (next/previous/open/defer).
- **FR3:** KYC Analysts can open a case and see all intake-agent-computed results without manual refresh.
- **FR4:** KYC Analysts can switch among officer modes (MVP: Deep Investigation, SAR/EDD Writing) via keyboard shortcuts.
- **FR5:** KYC Analysts can access a system-wide command palette to invoke any action by name.
- **FR6:** All roles receive in-app notifications when actions require their attention.

**Case Canvas & Data Display (FR7–FR10):**

- **FR7:** KYC Analysts can view a case's identity, documents, UBO, screening, risk, and timeline in collapsible panels on a single canvas.
- **FR8:** Every datum rendered in the cockpit displays a provenance indicator identifying its source agent, upstream source system, and confidence.
- **FR9:** KYC Analysts can open an Evidence Bundle shelf to view and attach supporting evidence to a case.
- **FR10:** All agent outputs render confidence using a consistent four-tier confidence-banded visual system.

**Agent Mesh Visibility & Interaction (FR11–FR14):**

- **FR11:** KYC Analysts can view a live activity feed of every agent working on the current case, with per-agent status (done, in-progress, blocked, needs-input).
- **FR12:** KYC Analysts can open a reasoning-trace slide-out for any agent action: (a) what was searched, (b) what returned, (c) confidence self-rating, (d) counterfactual.
- **FR13:** KYC Analysts can converse with a Cockpit Chat agent that has access to the full mesh state and current case context.
- **FR14:** The agent mesh automatically runs intake agents on case creation without officer action.

**Entity & UBO Analysis (FR15–FR17):**

- **FR15:** KYC Analysts can view an interactive force-directed UBO graph with confidence-banded edges and basic nominee/shell heuristics flagged.
- **FR16:** KYC Analysts can drag UBO edges to correct relationships; corrections captured as named "learning events" in the ledger with officer opt-in for future ground-truth use.
- **FR17:** Entity Verification agent can cross-reference a case entity against MCA and GST sources and surface mismatches.

**Screening & Risk Analysis (FR18–FR21):**

- **FR18:** Screening agent evaluates case entities and individuals against the configured screening vendor and surfaces hits with match details.
- **FR19:** KYC Analysts can view a screening-hit explainer showing name-similarity, identifier matches/mismatches (DOB, address, ID), confidence, counterfactual.
- **FR20:** KYC Analysts can view a risk-score explainer decomposing across contributing factors (country, entity type, ownership clarity, screening, adverse media).
- **FR21:** Risk scores automatically recalculate in response to officer corrections (e.g., UBO edits, manual screening disposition).

**Decision Authoring & Commit (FR22–FR27):**

- **FR22:** KYC Analysts can view and edit an agent-drafted rationale in a dedicated Decision Zone before committing.
- **FR23:** KYC Analysts can undo a committed decision within a defined undo window.
- **FR24:** KYC Analysts can commit case decisions with outcomes: approve, decline, approve-with-conditions, escalate-to-EDD.
- **FR25:** KYC Analysts can enter a dedicated SAR/EDD Writing mode with dark-background, minimized-chrome, evidence-docked UI.
- **FR26:** Writing agent can draft a structured EDD narrative memo citing specific ledger entries and evidence items by reference ID.
- **FR27:** The platform measures and exposes the "edit-rate" metric — proportion of each rationale that is officer-edited vs agent-drafted.

**Audit, Provenance & Ledger (FR28–FR32):**

- **FR28:** Every agent action captured in append-only, hash-chained ledger including agent ID, model ID, prompt hash, tool inputs, outputs, timestamp, platform signature.
- **FR29:** Every officer action captured in the ledger including user ID, action type, inputs, rationale, user-credential-based signature.
- **FR30:** Officers/Leads/CCO/Auditor can view a case timeline with interleaved agent + officer actions, scoped by role.
- **FR31:** Uploaded documents are immutable after ingestion; SHA-256 hashes recorded in ledger, verifiable on download.
- **FR32:** Platform prevents any write or delete operation on the ledger through normal application APIs.

**Regulator Lens & Export (FR33–FR35):**

- **FR33:** Internal Auditors can switch a case into a read-only Regulator Lens mode reframing the cockpit into an audit-focused view.
- **FR34:** Internal Auditors can export a case (or set of cases) as a PDF + JSON audit bundle.
- **FR35:** Each audit bundle is cryptographically self-verifying — hash chain and signatures validatable offline using a bundled verification tool.

**Approval Workflows (FR36–FR39):**

- **FR36:** Team Leads can view a dedicated queue of cases pending their approval.
- **FR37:** Team Leads can approve / approve-with-conditions / decline cases; conditions captured as structured state in ledger.
- **FR38:** Team Leads can view full agent + officer history for any case in their scope.
- **FR39:** KYC Analysts can commit EDD-outcome decisions that automatically enqueue the case for Team Lead approval.

**Portfolio & Reporting (FR40–FR41):**

- **FR40:** CCOs can view a minimal Portfolio Dashboard summarizing: cases processed, median case time, SLA breaches, risk-band distribution, audit-readiness indicator.
- **FR41:** CCOs can export a tenant-level summary (aggregated, non-PII) for a time-bounded cohort.

**Platform Integration / API (FR42–FR46):**

- **FR42:** External systems can submit new cases via authenticated REST API including customer metadata + document references.
- **FR43:** External systems can upload documents via presigned URLs or multipart streams.
- **FR44:** Platform emits authenticated webhooks to registered callbacks for case state changes and decision events.
- **FR45:** External systems can retrieve a case by ID per their API-consumer scope.
- **FR46:** Case creation is idempotent against a client-provided request ID.

**Identity, Access & Tenancy (FR47–FR51):**

- **FR47:** Users authenticate via tenant-configured SAML 2.0 or OIDC SSO.
- **FR48:** RBAC — KYC Analyst, Team Lead, CCO, Internal Auditor, Tenant Admin, API Consumer — enforced at API + UI with deny-by-default.
- **FR49:** All tenant data isolated — no cross-tenant reads, writes, or queries permitted.
- **FR50:** Tenant Admins can perform break-glass emergency read access with cryptographically-signed justification + ledger entry.
- **FR51:** Platform automatically signs users out after a configurable inactivity period.

**Agent Configuration & Operations (FR52–FR56):**

- **FR52:** Tenant Admins can configure the active screening vendor via a pluggable adapter interface.
- **FR53:** Tenant Admins can configure jurisdiction rules, SAR templates, document taxonomy.
- **FR54:** Platform supports feature flags per tenant to enable/disable individual agents and capabilities.
- **FR55:** Agent failures are isolated — single agent failure doesn't cascade; Case Supervisor retries or flags for human.
- **FR56:** External vendor integrations conform to contract-interface tests; vendor swap requires only adapter implementation change, not agent logic.

**Total FRs: 56**

### Non-Functional Requirements

**Performance (NFR-P1–P4):**

- **NFR-P1:** Keyboard-driven actions (j/k, mode switch, ⌘K) respond within **50 ms p95**.
- **NFR-P2:** Cockpit panel expand/collapse renders within **150 ms p95**.
- **NFR-P3:** Cockpit supports simultaneous display of ≥ **50 UBO nodes** without degradation.
- **NFR-P4:** Concurrent agent mesh execution scales to all 8 MVP agents in parallel where dependencies permit, without resource contention causing p95 breach.

**Plus performance from Domain Constraints:** UI nav ≤ 200 ms p95 · reasoning-trace slide-out ≤ 500 ms p95 · case creation API ≤ 1 s p95 · full mesh cold-start ≤ 2 min p95 · UBO Canvas render ≤ 1.5 s p95 (≤ 50 nodes) · audit ledger export ≤ 10 s.

**Security (NFR-S1–S6):**

- **NFR-S1:** API rate limiting — per API key/IP/endpoint; default 100 req/min, burst 500, configurable per tenant.
- **NFR-S2:** Failed auth attempts lock account after 5 failures within 10 min; unlock via admin or timed cooldown.
- **NFR-S3:** All production deps scanned weekly (Dependabot/Snyk); Critical+High CVEs resolved within SLA (Critical 48h, High 7 days).
- **NFR-S4:** Documented threat model covering agent mesh, ledger, screening boundary, document upload, auth; reviewed quarterly.
- **NFR-S5:** Pre-pilot external pentest; Critical/High remediated before pilot launch.
- **NFR-S6:** LLM prompt security — version-controlled, peer-reviewed templates; runtime injection guards (input sanitization + instruction containment) for document-derived text.

**Plus baseline:** TLS 1.3 · AES-256 · HSM-backed signing · per-tenant credentials · append-only audit log · RBAC deny-by-default at API+UI · 30 min session inactivity timeout · all API access audit-logged · anomaly detection on admin actions.

**Availability & Reliability (NFR-A1–A7):**

- **NFR-A1:** MVP pilot SLO: **99.5% during business hours IST** (Mon–Fri, 09:00–19:00).
- **NFR-A2:** GA target: **99.9%** annual availability.
- **NFR-A3:** DR — **RPO ≤ 1 hour, RTO ≤ 4 hours**.
- **NFR-A4:** P1 incident MTTR ≤ **2 hours**.
- **NFR-A5:** Single agent failure must not exceed one case's processing; Case Supervisor isolates, retries, or flags.
- **NFR-A6:** Ledger write atomic — partially-written entry never visible to readers/exports.
- **NFR-A7:** Graceful degradation on vendor outage — surface reason, block case closure, never render stale screening as current.

**Scalability (NFR-SC1–SC4):**

- **NFR-SC1:** MVP pilot — 10 concurrent analysts, 500 open cases, 100 case ingests/hour.
- **NFR-SC2:** 10× horizontal scaling within a tenant without code changes (target: 100 analysts, 5,000 cases, 1,000 ingests/hr).
- **NFR-SC3:** Ledger growth ~10 MB/case; cold-storage tiering at 2 years bounds hot storage.
- **NFR-SC4:** Multi-tenant on shared infra post-MVP; isolation primitives production-grade from day one.

**Accessibility (NFR-AC1–AC6):**

- **NFR-AC1:** Cockpit conforms to **WCAG 2.2 Level AA**.
- **NFR-AC2:** All primary officer actions keyboard-accessible; no action mouse-only.
- **NFR-AC3:** Confidence-banded visual system uses **shape + position + label in addition to color**.
- **NFR-AC4:** Color contrast ≥ 4.5:1 body text, ≥ 3:1 UI chrome (WCAG AA).
- **NFR-AC5:** Persistent, high-contrast focus indicators on every keyboard-navigable element.
- **NFR-AC6:** Localization — English-only at MVP; architecture i18n-ready (externalized strings, locale-aware date/number).

**Observability (NFR-O1–O6):**

- **NFR-O1:** Structured OpenTelemetry traces; agent activity enriched with case ID, agent ID, case state.
- **NFR-O2:** Orchestrate-native traces (agent-as-tool, HITL checkpoints, tool calls) exported alongside application traces.
- **NFR-O3:** Telemetry PII-scrubbed at collection layer.
- **NFR-O4:** Per-tenant observability partitioning — no cross-tenant visibility in observability UI.
- **NFR-O5:** Product telemetry dashboards: case-time distribution, edit-rate, mode-usage, agent precision, NPS trend, SLA breach, audit-readiness.
- **NFR-O6:** P1 alerts for ledger integrity, screening-vendor-down, auth-down, agent-runtime cascade; on-call paged within 1 minute.

**Compatibility (NFR-CP1–CP4):**

- **NFR-CP1:** Latest 2 versions of Chrome/Edge/Firefox/Safari on desktop; no IE; no tablet/mobile in MVP.
- **NFR-CP2:** Runs on Windows 10+, macOS 12+, Ubuntu 22.04+.
- **NFR-CP3:** Min viewport 1366×768; optimized for 1920×1080 and 2560×1440.
- **NFR-CP4:** No native client required for MVP — browser-only.

**Reference Implementation (NFR-RI1–RI7):**

- **NFR-RI1:** ADK pattern coverage with commentary — supervisor/collaborator, agent-as-tool, Pydantic-contracted tools, HITL approval, background/scheduled, parallel meta-critic, conversational with mesh-as-tools, Orchestrate-trace audit.
- **NFR-RI2:** Every agent has a README; every non-trivial decision in an ADR.
- **NFR-RI3:** Python: Ruff + mypy; TS: ESLint + strict.
- **NFR-RI4:** Unit coverage ≥ 80% on agent logic + tool adapters; integration tests at every contract boundary; e2e for the four canonical flows.
- **NFR-RI5:** Clone + local demo in ≤ 30 minutes by a developer unfamiliar with the project.
- **NFR-RI6:** Every vendor/jurisdiction adapter ships with a second reference adapter.
- **NFR-RI7:** All LLM prompts in version-controlled Jinja templates; no string-concat of user data; tested with golden inputs.

**Specific Thresholds (NFR-T1–T6):**

- **NFR-T1:** Undo window — 120 seconds.
- **NFR-T2:** Session inactivity — 30 minutes (configurable [15, 60]).
- **NFR-T3:** Edit-rate target ≥ 60% of decisions satisfy (agent-drafted ≥ 80% AND officer-edited < 20%).
- **NFR-T4:** Provenance coverage — 100% of rendered data points carry provenance metadata.
- **NFR-T5:** Agent precision floors — DocIntel ≥ 95% field extraction; UBO basic ≥ 95% structural accuracy.
- **NFR-T6:** Break-glass justification ≥ 40 characters; rationale + reader identity signed into ledger.

**Compliance:** RBI Master Direction on KYC; PMLA 2002 + PML Rules 2005 (5y retention, STR within 7 days); Section 12 PMLA (ongoing monitoring); Companies Act 2013 §89/90 + SBO Rules 2018 (UBO disclosure); DPDP Act 2023; FIU-India XML schema readiness.

**Total NFRs: 41 numbered + multiple compliance/baseline items**

### Additional Requirements

**Constraints & Assumptions:**

- 4–6 week MVP timebox to "SME Onboarding Slice"
- India-first jurisdiction; pluggable interface for future EU/UK/US/Singapore/UAE
- IBM watsonx Orchestrate + Python ADK is the target agent runtime (the *raison d'être* of the project)
- Single-tenant per deployment in MVP; multi-tenant ready
- "Edit, don't author" mandate — no auto-commit ever; officer rationale is canonical record
- No mobile in MVP (deferred); no offline mode (real-time mesh requires connectivity)
- Path-B internal architectural intent (reference implementation for IBM watsonx Orchestrate + ADK) drives architecture and NFR decisions; not a product promise to bank buyers

**Integration requirements:**

- Core banking system (REST + webhook + SFTP fallback), single screening vendor, MCA, GST portal, S3-compatible doc storage, bank IdP (SAML 2.0 / OIDC), email + in-app notifications, OpenTelemetry
- Future: Aadhaar eKYC, PAN-NSDL, Digilocker, mobile push, FIU-India STR/CTR submission

**Domain-specific risk mitigations** (13 items in PRD): screening vendor lock-in, agent precision drift, regulator rejection, PII leakage, hallucination, prompt injection, jurisdictional drift, ledger tampering, retention cost, adoption resistance, over-automation, core banking brittleness, evidence integrity.

### PRD Completeness Assessment

| Aspect | Assessment |
|---|---|
| FR coverage | ✅ **Excellent.** 56 FRs grouped logically into 12 categories. Every FR is testable and binding. |
| NFR coverage | ✅ **Excellent.** 10 NFR families with 41 numbered NFRs plus compliance baseline. Specific thresholds (T1–T6) prevent ambiguity. |
| User journeys | ✅ Six journeys documented (Priya happy + edge, Team Lead, Auditor, CCO, API Consumer); each names capabilities revealed. |
| Innovation areas | ✅ Seven novel innovations enumerated with validation methods + fallback positions. |
| Risk register | ✅ Technical + market + resource risks each with mitigation and "what we'd cut first." |
| Compliance | ✅ India regulatory specifics (RBI, PMLA, Companies Act, DPDP, FIU-XML) named explicitly; pluggable jurisdictional interface mandated. |
| RBAC matrix | ✅ Six roles with detailed read/write/execute matrix. |
| Success criteria | ✅ Quantitative + qualitative, with baselines and signals. |
| Implementation approach | ✅ B2B SaaS specifics (tenant model, deployment, versioning, on/offboarding) explicit. |
| Scoping | ✅ MVP IN/OUT clearly delineated; deferred items inventoried; risk-based scoping with cut order. |
| **Ambiguities found** | ⚠️ Three architectural decisions deferred from PRD ("six open architecture decisions") — five resolved during architecture workflow; **screening vendor + doc-AI stack remain pinned to procurement/benchmark, not architecture**. This is correct, but epics should reflect that the vendor pick is a milestone gating MVP, not a free variable. |

**Verdict on PRD:** Ready for epic decomposition. No rewrite needed. Two items to flag for the epics author: (1) screening vendor pick + sandbox onboarding is itself a story, (2) doc-AI evaluation benchmark is itself a story.

## Step 3 — Epic Coverage Validation

### Status: ⏭️ DEFERRED (no epics document exists)

**Rationale:** Path 1 (partial readiness check) was selected because epics/stories have not yet been authored. This step cannot run without the input document.

### Coverage Statistics

| Metric | Value |
|---|---|
| Total PRD FRs | 56 |
| FRs covered in epics | N/A — epics not authored |
| Coverage % | N/A — to be measured after `bmad-create-epics-and-stories` |

### Pre-emptive guidance for the epics author

When epics are authored, ensure the following are explicitly stories or epic items (not assumed):

1. **Screening vendor procurement + sandbox onboarding** (touches FR18, FR52, NFR-RI6) — pluggable, but the vendor pick is a real-world calendar dependency.
2. **Document AI stack evaluation benchmark** (touches FR-Document Intelligence, NFR-T5 ≥ 95%) — 50-doc corpus benchmark across IBM Document AI vs Watson Discovery before lock-in.
3. **Threat model authoring** (NFR-S4) — referenced in architecture as `docs/architecture/threat-model.md`.
4. **External pentest engagement** (NFR-S5) — must complete before pilot launch.
5. **Tenant onboarding runbook** (FR53, NFR-SC4) — MVP supports admin via CLI runbook, not UI.
6. **Officer Ed25519 keypair flow at first login** (FR29, S6) — non-obvious from FR list; comes from architecture S6.
7. **Offline verifier tool packaging + distribution** (FR35) — separate deliverable from main app.
8. **Confidence calibration study pre-pilot** (P7, Innovation Risk Mitigation) — calibrating per-agent thresholds before pilot is itself a story.
9. **Adapter conformance pair for every external integration** (NFR-RI6) — second reference adapter is part of every adapter story, not an afterthought.
10. **Ledger DR rehearsal** (NFR-A3, G3) — quarterly cadence; itself a recurring story.

### Coverage Re-check Plan

After epics authored, re-run readiness check; this step will populate the FR×Epic coverage matrix and verify all 56 FRs map to at least one story.

## Step 4 — UX Alignment Assessment

### UX Document Status

✅ **Found.** `Documentation/planning-artifacts/ux-design-specification.md` (151 KB, 14 steps completed, status `workflow_completed: true`). Plus visual artifacts (`ux-design-directions.html`, `ux-mockups.html`).

### UX ↔ PRD Alignment

| Aspect | PRD | UX Spec | Verdict |
|---|---|---|---|
| Primary persona (Priya) | KYC Analyst, mid-size bank, 8–12 cases/day | Same persona; expanded with keyboard fluency, ~70% workforce | ✅ Aligned |
| Secondary personas | Team Lead, CCO, Internal Auditor, API Consumer | Same set: Rohan, Meera, Anika, Core Banking; plus hidden Path B audience (solution architect/dev) | ✅ Aligned + UX adds Path B explicitly |
| Six-zone cockpit | Queue · Case Canvas · Agent Copilot · Decision Zone · Top Bar · Bottom Ribbon | Same structure with detailed dimensions (260px / fluid / 320px) | ✅ Aligned |
| MVP zones (4 of 6) | Queue · Canvas · Agent Copilot · Decision Zone | Same | ✅ Aligned |
| MVP modes (2 of 6) | Deep Investigation · SAR/EDD Writing Zen | Same; full 6 modes documented for Future | ✅ Aligned |
| MVP agents (8 of 14) | Case Supervisor · DocIntel · EntityVerify · UBO basic · Screening · Risk · Writing · Cockpit Chat | Same 8 agents have illustrated faces in MVP | ✅ Aligned |
| Six PRD design principles | Visible / Provenance / Sacred decisions / Keyboard / Density / Confidence visual / Officer cognitive | UX adds 8 *experience* principles complementing (not duplicating) PRD's *governance* principles | ✅ Complementary — UX explicitly notes the distinction |
| User journeys | 6 journeys (Priya happy + edge, Lead, Auditor, CCO, API) | UX has Defining Experience + Experience Mechanics covering same scenarios | ✅ Aligned |
| Edit-don't-author principle | PRD NFR-T3 ≥ 60% edit-rate | UX defining experience is "edit the draft" | ✅ Aligned |
| 120s undo | PRD NFR-T1 | UX section 2.5 explicit | ✅ Aligned |
| Confidence 4-tier banding | PRD FR10 + NFR-AC3 (shape+position+label) | UX makes this a *design primitive* every component must declare | ✅ UX strengthens PRD |
| Counterfactual reasoning trace | PRD FR12 + Innovation #2 | UX section 2.5 has 4-section fixed schema | ✅ Aligned |
| Provenance pill on every datum | PRD FR8 + NFR-T4 100% | UX confirms; one-click trace | ✅ Aligned |
| Keyboard shortcuts | PRD FR2/FR4/FR5 + NFR-AC2 | UX details: j/k/x/d, ⌘K, ⌘+1–6 | ✅ Aligned |
| Density gradient | PRD design principle #5 | UX section 2.5 details per-mode UI footprint shifts | ✅ Aligned (UX more concrete) |
| Mobile/multi-monitor | Deferred (Future) | Same | ✅ Aligned |
| WCAG 2.2 AA + keyboard + screen-reader concurrent | PRD NFR-AC1–AC6 | UX has dedicated treatment, axe-core integration plan | ✅ Aligned |

**UX requirements not in PRD (additions, not contradictions):**

- **Visual vision: "marble and spring flowers"** — light, typographic, restrained color. Not in PRD; informs architecture's Tailwind theming and font choice.
- **Eight illustrated agent faces** with state animations (idle/working/complete/blocked/needs-input). PRD mentions "agent faces" briefly; UX makes them a design primitive.
- **Three motion flavors** (expand / focus-dim / slide-out) at 150–300 ms durations. PRD doesn't specify; UX mandates as the motion language.
- **Earned calm** as the primary emotional goal. Not in PRD; informs design decisions (silent by default, motion discipline, etc.).

These are healthy additions; UX is allowed to define the *how* of the *what* PRD specifies.

### UX ↔ Architecture Alignment

| UX Requirement | Architecture Decision | Verdict |
|---|---|---|
| 50 ms keyboard p95 (NFR-P1) | F2 Zustand for global UI state, no Context for fast-changing values; F1 TanStack Query for server state | ✅ Architecturally supported |
| 150 ms panel expand (NFR-P2) | F12 React 19 Suspense + skeleton on heavy panels; Framer Motion utilities | ✅ Supported (with note below) |
| Reasoning trace ≤ 500 ms (PRD perf) | A2 SSE + F1 TanStack Query invalidate-and-refetch on event | ✅ Supported |
| 50 UBO nodes without degradation (NFR-P3) | react-flow chosen explicitly for force-directed UBO Canvas; F6 lazy-loaded so it doesn't bloat initial bundle | ✅ Supported |
| Three motion flavors | Framer Motion installed; Tailwind motion curves: snap/ease/reveal | ✅ Supported |
| Eight illustrated agent faces | `apps/cockpit-ui/public/agent-faces/` directory + `components/cockpit/AgentFace/` component | ✅ Captured (asset format TBD — see gap U2) |
| 4-tier confidence-banded primitive | P7 Confidence Banding pattern + `components/cockpit/ConfidencePill` + `lib/confidence.ts` | ✅ Supported as a first-class pattern |
| Provenance pill on every datum | P3 Provenance Metadata Pattern + `ProvenancedField[T]` + CI test enforcement (NFR-T4) | ✅ Architecturally enforced |
| ⌘K command palette | `components/cockpit/CommandPalette` + `stores/paletteStore.ts` + `hooks/useKeyboardShortcuts` | ✅ Supported |
| Mode switching ⌘+1–6 | `components/cockpit/ModeSwitcher` + `stores/modeStore.ts` | ✅ Supported |
| Decision Zone rich-text editor | F5 Tiptap (ProseMirror-based) chosen for headless editor | ✅ Supported |
| Drag-correct-and-teach on UBO | react-flow + ledger learning event in `agents/tools/ubo_resolve.py` + ledger entry | ✅ Supported |
| Regulator Lens read-only mode | `routes/_auth/cases.$caseId.regulator-lens.tsx` + `components/cockpit/RegulatorLensFrame` | ✅ Supported |
| Officer-signed commits | S6 in-browser WebCrypto Ed25519 (`lib/crypto.ts`) | ✅ Supported |
| WCAG 2.2 AA + keyboard + screen-reader | Radix primitives (accessibility built in) + axe-core in Playwright + i18n scaffold | ✅ Supported |
| Marble + spring flowers visual | Tailwind 4 `@theme` tokens, no IBM Carbon, no opinionated UI lib | ✅ Architecturally allows |

### Alignment Issues Found

**Minor gaps / sub-decisions to call out (none are blockers):**

| # | Item | Severity | Recommendation |
|---|---|---|---|
| **U1** | **Density gradient** is a UX-mandated design primitive (UX §1.1, §2.5) but is not called out as a pattern in the architecture's pattern catalog (P1–P8). It's *implied* via `stores/modeStore.ts` driving conditional component rendering, but the discipline ("Triage stays dense; Decision Zone reduces info density by ~40%; Zen relaxes typography one scale step") isn't codified. | Minor | Add a **P9 Density Gradient Pattern** to the architecture document, or capture it as a design-tokens-per-mode mapping in `apps/cockpit-ui/src/styles/tokens.css`. Story-level concern, not blocking. |
| **U2** | **Agent face illustration asset format** is not specified. UX requires state animations (wake / breath / complete chime / blocked / needs-input). SVG with CSS-controlled paths is the natural fit (small, scalable, themeable); PNG sequences or Lottie would conflict with UX §1.1's "no Lottie" decision. | Minor | First implementation story for AgentFace specifies SVG-with-CSS-state-classes. Trivial to fix in flight. |
| **U3** | **Specific font family** is unpinned. UX names candidates (Inter / Geist for sans; JetBrains Mono / Geist Mono for mono; Source Serif / iA Writer Duo for Zen). Architecture's Tailwind config will need to lock one combination. | Trivial | Lock during Phase 1 of starter scaffold; document in an ADR. Recommend Inter + JetBrains Mono + Source Serif to match Stripe-style typographic restraint. |
| **U4** | **Empty / error states per component** are not explicitly designed. Architecture's RFC 7807 error format covers the technical contract; UX's emotional principles ("reassurance under friction") imply a treatment but don't spec each empty/error state. | Minor | Add to UX backlog as components are built; not blocking architecture or epics. Component-level concern. |
| **U5** | **Animation timing — coexistence of NFR-P2 (≤150 ms p95 panel expand) with UX's "150–300 ms, never longer"** could read as conflicting at first glance. They're not — NFR-P2 measures *response start* (frame begins drawing), UX measures *animation duration* (frame sequence ends). | Trivial — clarification only | Document the distinction in a comment in `lib/api.ts` or as part of the perf SLO doc. No architectural change needed. |

**Architectural alignment with UX is strong.** Every UX requirement maps to a concrete architectural decision or component. The five items above are **all minor** and resolvable during implementation, not blockers for readiness.

### Warnings

None. The UX spec is mature (14 workflow steps completed, marked `workflow_completed: true`) and the architecture (just completed) explicitly cites UX-derived constraints throughout (NFR-AC*, F1–F13 frontend decisions, P7 Confidence Banding, P8 Counterfactual Reasoning Trace).

## Step 5 — Epic Quality Review

### Status: ⏭️ DEFERRED (no epics document exists)

**Rationale:** Path 1 (partial readiness check) was selected because epics/stories have not yet been authored. This step's standards (epic independence, no forward dependencies, story sizing, BDD acceptance criteria, starter-template-as-Story-1.1, etc.) cannot be applied to a document that doesn't exist.

### Pre-emptive guidance for the epics author (best-practice reminders)

When `bmad-create-epics-and-stories` runs, the resulting epics should satisfy:

| Standard | What it means here |
|---|---|
| **Epics deliver user value** | Avoid technical epics like "API Development" or "Authentication System." Frame as "Officer can ingest and triage SME cases," "Officer can investigate UBO graph and correct it," etc. |
| **Epic independence** | Epic 2 (e.g., "Investigation") must function with only Epic 1 (e.g., "Triage") output. The "SME Onboarding Slice" MVP gives a natural ordering: ingest → triage → investigate → decide → audit. |
| **No forward dependencies in stories** | Story 1.4 cannot say "depends on Story 2.1." Build forward, not backward. |
| **Database tables created when needed** | Don't have an "Epic 1 Story 1 — create all tables." Each story creates schemas it needs (Alembic migration per slice). |
| **Story 1.1 = starter scaffold** | Architecture mandates a specific monorepo scaffold (Vite + ADK init + FastAPI + Poetry + pnpm). **Story 1.1 must be: "Set up initial project from polyglot scaffold."** Without this, Story 1.2 has no place to live. |
| **Acceptance criteria in BDD form** | Given / When / Then; testable; covers happy path + named error cases. |
| **Traceability to FRs** | Each story should name the FR(s) it satisfies. With 56 FRs, the FR×Story coverage matrix becomes the readiness check input. |

### Specific story-shape suggestions for this codebase

Drawing from architecture decisions and patterns, the epics author should anticipate stories like:

- **Epic 1 — Foundations:** Story 1.1 monorepo scaffold · Story 1.2 Makefile + Compose + pre-commit + GitHub Actions · Story 1.3 first migration + Postgres schemas (cases, ledger, audit_meta) · Story 1.4 OIDC auth flow with cookie session · Story 1.5 tenant scoping middleware (P2) · Story 1.6 RBAC dependency (S5) · Story 1.7 first agent (DocIntel) wired through P4 action_decorator · Story 1.8 SSE channel + Redis pub/sub registry · Story 1.9 cockpit-ui shell with TanStack Router routes
- **Epic 2 — Triage & Case Open:** Queue ordering, keyboard navigation, case canvas open with intake-complete state, agent activity feed, provenance pills
- **Epic 3 — Investigation:** UBO Canvas + drag-correct-and-teach, Screening Explainer, Risk Score Bar, reasoning-trace slide-out
- **Epic 4 — Decision Authoring:** Decision Zone, Tiptap editor, WebCrypto signing, 120s undo, ledger entry, edit-rate metric
- **Epic 5 — Audit & Export:** Regulator Lens mode, PDF + JSON bundle, offline verifier tool packaging
- **Epic 6 — Approvals & Portfolio:** Team Lead approval queue, CCO portfolio dashboard
- **Epic 7 — API & Integration:** External case ingest API, webhook dispatch with HMAC + retries, idempotency

(Names indicative only; the epics author has authority to organize differently.)

### Re-check Plan

After epics authored, re-run readiness; this step will rigorously validate epic independence, story sizing, dependency direction, BDD acceptance criteria, and starter-as-Story-1.1.

## Summary and Recommendations

### Overall Readiness Status

**Upstream Documents (PRD · Architecture · UX): ✅ READY**
**Implementation Phase: ⚠️ NEEDS EPICS** — cannot start until `bmad-create-epics-and-stories` runs and produces a story breakdown.

### Findings by Severity

#### 🔴 Critical (block implementation start)

| # | Finding | Action |
|---|---|---|
| **CR1** | **Epics & Stories document does not exist.** Implementation cannot start without a story breakdown — there is no work-unit definition to assign, sequence, or estimate. This is the *only* critical finding in this readiness check. | Run `bmad-create-epics-and-stories` next. |

#### 🟠 Major (resolve before pilot, not before implementation start)

| # | Finding | Action |
|---|---|---|
| **MJ1** | **Threat model document** referenced in architecture as `docs/architecture/threat-model.md` is not yet authored. NFR-S4 mandates it. | Author during early implementation (Epic 1 or 2 era); do not wait until pilot. |
| **MJ2** | **External pentest engagement** (NFR-S5) is named in the architecture but not procured. Critical/High findings must remediate before pilot launch. | Begin vendor selection in parallel with implementation. |
| **MJ3** | **Screening vendor procurement** is pinned to procurement, not architecture (deliberately). The vendor pick + sandbox onboarding is a real-world calendar dependency that the epics must surface as a story, not assume. | Add a procurement-tracking story in Epic 1 or 2; recommended pick: ComplyAdvantage (PRD risk register). |
| **MJ4** | **Document AI stack benchmark** (NFR-T5 ≥ 95% precision floor) must be performed against IBM Document AI vs Watson Discovery before lock-in. Not yet started. | Add as a benchmark story in the same epic that introduces Document Intelligence agent. 50-doc corpus needed. |

#### 🟡 Minor (resolve during implementation)

| # | Finding | Action |
|---|---|---|
| **MN1 (U1)** | **Density Gradient** is a UX-mandated design primitive but isn't called out as a named pattern (P9) in the architecture. Implied via `modeStore`, but not codified. | Add a P9 Density Gradient pattern note to architecture, or capture as design-tokens-per-mode mapping. |
| **MN2 (U2)** | **Agent face asset format** unspecified. SVG-with-CSS-state-classes is the natural fit (UX excludes Lottie). | Capture in the AgentFace component story. |
| **MN3 (U3)** | **Specific font family** unpinned (UX names candidates only). | Lock during Phase 1 of starter scaffold; document as ADR. Recommended: Inter + JetBrains Mono + Source Serif. |
| **MN4 (U4)** | **Empty / error states** per component not yet designed. Architecture has RFC 7807; UX has emotional principles; component-level treatments TBD. | Add to UX backlog as components are built. Not blocking. |
| **MN5 (U5)** | **NFR-P2 (≤150 ms panel expand) vs UX 150–300 ms motion** could read as conflicting. They aren't (response-start vs animation-duration). | Document the distinction in code comments or perf SLO doc. |
| **MN6 (G3)** | **DR rehearsal cadence** runbook exists in architecture; quarterly cadence implied but not codified as ops calendar item. | Pilot ops handoff. |
| **MN7 (G4)** | **Capacity / cost estimation** outside this readiness scope but the buyer pipeline will ask. | Post-architecture artifact; not blocking. |

### Strengths Observed

1. **PRD is exceptionally mature.** 56 FRs across 12 categories, all binding and testable; 41 numbered NFRs across 10 families with specific thresholds (T1–T6); compliance, RBAC, journeys, innovation areas, and risk register all present. No PRD rewrite is needed.
2. **UX spec is workflow-completed and detail-dense.** 14 steps marked complete; covers personas, journeys, mental model, novel patterns, design system, visual foundation, motion language, accessibility, and component strategy. Architecture explicitly cites UX-derived constraints throughout.
3. **Architecture is freshly produced and self-validating.** 47 decisions, 8 project-specific patterns, complete file tree, FR-to-location mapping, three coherence concerns surfaced with explicit mitigations, four important gaps tracked. NFR-RI1–RI7 (Path B reference-implementation quality) explicitly designed-in.
4. **Cross-document traceability is excellent.** PRD ↔ UX ↔ Architecture references each other consistently — same persona names (Priya, Rohan, Meera, Anika), same zone count (six), same mode count (six, two in MVP), same agent count (14, eight in MVP), same mode names (Triage, Deep Investigation, Factory Refresh, SAR/EDD Zen, Regulator Lens, Training).
5. **MVP scope discipline is consistent.** All three docs treat "SME Onboarding Slice" as the single vertical, with the same In/Out boundaries (8 of 14 agents, 4 of 6 zones, 2 of 6 modes, India-only with pluggable interface).

### Recommended Next Steps (in order)

1. **Run `bmad-create-epics-and-stories`** to author the epics + stories document. Use the pre-emptive guidance in Step 5 of this report (especially: Story 1.1 = monorepo scaffold; database tables created when needed, not upfront; epic independence in MVP order Foundations → Triage → Investigation → Decision → Audit → Approvals → API).
2. **Re-run `bmad-check-implementation-readiness`** with epics in place. Steps 3 (epic coverage of 56 FRs) and 5 (epic quality review) will become first-class checks.
3. **Address Major findings (MJ1–MJ4) in the epic plan** so they aren't surprises during build:
   - Author threat model (MJ1) — add to Epic 1 or 2.
   - Begin pentest vendor selection (MJ2).
   - Surface screening vendor procurement (MJ3) as an explicit story.
   - Surface doc-AI benchmark (MJ4) as an explicit story.
4. **Once epics are validated**, execute the architecture's first implementation priority (the seven-step init sequence at the end of `architecture.md`).
5. **Resolve Minor findings during implementation** as the relevant components are built — none are blockers.

### Final Note

This partial readiness assessment found **1 critical issue** (epics don't exist), **4 major issues** (none of which block implementation start once epics exist), and **7 minor issues** (all resolvable during implementation). The upstream alignment between PRD, Architecture, and UX is excellent — there is no rework required on those documents.

**Once epics are authored, the project is positioned to begin implementation with high confidence.** The architecture is opinionated and complete; the patterns make agent-driven implementation enforceable; the file structure is concrete enough that "what goes where" is rarely ambiguous.

— Paul, Implementation Readiness PM (acting on behalf of Winston, System Architect)
2026-04-27

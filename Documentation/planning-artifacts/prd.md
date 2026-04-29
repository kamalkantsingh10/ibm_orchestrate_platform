---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
inputDocuments:
  - Documentation/planning-artifacts/product-brief-distillate.md
  - Documentation/brainstorming/brainstorming-summary-2026-04-24.md
documentCounts:
  briefs: 1
  research: 0
  brainstorming: 1
  projectDocs: 0
classification:
  projectType: saas_b2b
  domain: fintech
  complexity: high
  projectContext: greenfield
  primaryIntent: reference_implementation_orchestrate_adk_showcase
workflowType: 'prd'
---

# Product Requirements Document - KYC Cockpit

**Author:** Kamal
**Date:** 2026-04-24

## Executive Summary

**KYC Cockpit** is an officer-first agentic KYC platform for banks, built on IBM watsonx Orchestrate and the Agent Development Kit (ADK). It replaces the form-based case-management UIs that dominate today's KYC tooling with a purpose-built analyst cockpit sitting on top of a visible, collaboratable mesh of 14 specialized agents.

**Problem.** Mid-size universal banks spend 2–5 hours per SME onboarding case, stitching data across 4+ systems (KYC DB, core banking, screening, adverse media). Periodic-refresh backlogs, alert fatigue, and audit-trail anxiety compound. Every shipping "agentic KYC" platform — Fenergo, Moody's, IBM Consulting KYC-AI, Genpact, Fulcrum FD Ryze, Lyzr, Akira — bolts agents onto legacy case-management forms. Officers get faster clerical work; they don't get agency.

**Target user (primary).** Priya, 28, KYC Analyst at a mid-size universal bank. Three years of experience, 8–12 cases/day, mix of retail + SME onboarding + periodic refresh. Represents ~70% of the KYC officer workforce — features built for her scale up to seniors.

**Buyer.** Chief Compliance Officer / Head of Financial Crime at banks with 500K–10M accounts. Jurisdiction-first rollout: India (RBI / FIU-India), pluggable by design.

**Solution.** A six-zone cockpit (Queue Rail · Case Canvas · Agent Copilot Pane · Decision Zone · Top Bar · Bottom Ribbon) rendering a five-layer, 14-agent mesh (Supervisor · Intake · Deep-Dive · Interaction · Background) composed via Orchestrate + ADK. Six officer modes (Triage · Deep Investigation · Factory Refresh · SAR/EDD Writing Zen · Regulator Lens · Training). Every agent action is provenance-tagged; every officer decision is edit-don't-author, reversible with reason, and captured in a cryptographic audit ledger.

**MVP (4–6 weeks) — SME Onboarding Slice.** 8 of 14 agents, 4 of 6 zones, 2 of 6 modes, single screening vendor. Target outcomes: case time ≤ 15 min (baseline 2–5 hours), officer touch time ↓ ≥ 70%, 100% decisions with agent-drafted rationale (edited, not authored), Regulator Lens export passes mock internal audit with zero remediation asks, officer NPS ≥ 40 from 10-analyst pilot.

### What Makes This Special

**Agents are commoditizing. The defensible layer is the human–agent interaction surface.** Officers want AI that explains and learns, not AI that decides silently.

Three things KYC Cockpit does that the market does not:

1. **Agent mesh is the product, cockpit is the moat.** Competitors bolt agents onto 2015-era case forms. KYC Cockpit makes mesh activity legible in real time — officers see which agent is doing what, open a reasoning-trace slide-out showing what an agent searched, what hit, why medium-confidence, and what would change its mind, edit the rationale, and the agent learns from the edit. Collaboration, not supervision.
2. **Decisions are sacred, not incidental.** A dedicated Decision Zone with pre-drafted rationale, 120-second undo, agent self-rated confidence, and a cryptographic audit ledger. Regulator Lens is one click — PDF + JSON export an auditor can verify.
3. **Density gradient as a design primitive.** Dense cockpit for triage → calm Decision Zone → zen writing mode for SAR/EDD. Keyboard-first (⌘K palette, ⌘1–⌘6 mode switch, j/k/x/d triage loop). Officers feel senior, not clerical.

**Defensibility timer.** Incumbents (Fenergo, Moody's, IBM Consulting KYC-AI) ship agent capability today but still on legacy UIs. The whitespace for an officer-first cockpit is open ~12–18 months before a counter-move ships. Speed and design-as-DNA are the mitigations.

### Design Principles

Every downstream design and architecture decision is filtered through these seven principles. If a proposed feature violates any, it does not ship.

1. **Agent work is visible, not hidden.** Officers collaborate with the mesh, they do not supervise a black box. Every agent action is observable in-context.
2. **Every datum is provenance-tagged.** Source, confidence, and chain-of-custody for every piece of data rendered in the cockpit. Zero unlabeled facts.
3. **Decisions are sacred.** Distinct from data interactions. Audited end-to-end. Reversible only with reason. Signed by the officer.
4. **Keyboard beats clicks.** Fluent officers never leave home row for navigation, mode-switching, or triage actions. Mouse is a fallback, not the primary path.
5. **Density gradient, not uniform density.** Dense for triage, calm for decision, zen for writing. Mode-appropriate information architecture.
6. **Confidence is visual, not textual.** Four tiers rendered consistently — shape, position, and label, not just color.
7. **Officer cognitive design is first-class.** Fatigue, tempo limits, and well-being are measured signals, not side concerns. Over-automation that disengages officers is itself a product failure.

These principles thread through User Journeys, Functional Requirements, Non-Functional Requirements, and the UX Design work that follows this PRD.

## Demo Re-Scope Note (2026-04-29)

**This PRD has been re-scoped for a local demo build.** The sections that follow remain as-authored for posterity and for future revival of the bank-buyer scope. This addendum is the canonical statement of what is in scope for the current build.

### Audience reduction

The original PRD targets two audiences:

1. **Bank buyer** — Chief Compliance Officer at mid-size bank (500K–10M accounts), India jurisdiction-first, commercial product
2. **Path B** — IBM watsonx Orchestrate + Agent Development Kit (ADK) reference implementation showcase

**The current build serves audience #2 only.** The deliverable is a local demo run synchronously by Kamal for three internal stakeholders, proving that a full-fledged professional application can be built using IBM ADK agents. The bank-buyer commercial roadmap (LOIs, pilot, paying bank, RBI/FIU validation) is deferred indefinitely. The build is terminal — no production rollout follows.

### Re-scoped success criteria (active)

- All MVP agents demonstrably exercise distinct ADK patterns per the Path B pattern checklist (NFR-RI1) — supervisor/collaborator, agent-as-tool, Pydantic-contracted tools, HITL approval, conversational-with-mesh-as-tools
- Three stakeholders watching synchronously walk away with a clear "I didn't know Orchestrate could do this" reaction
- UI fidelity matches the mockup; demo presents as a professional product, not a tooling demo
- Fresh-clone to running demo in **≤60 minutes** (relaxed from NFR-RI5's ≤30 min target)

### Deferred success criteria (bank-buyer)

- Median SME case time ≤ 15 min, officer NPS ≥ 40, 80% "changes how I feel about the work," mock audit zero remediation, agent precision ≥ 95% on benchmarks, signed pilot LOIs, paid bank by 12-month — **all deferred indefinitely.**

### Functional requirements impact (summary)

| Status | Requirements |
|---|---|
| **Kept** | FR1–4, FR7–17 (FR17 reduced to MCA-only), FR18–21, FR22–26, FR30 (UI-side gating), FR33–34 (PDF only), FR36–39 |
| **Simplified** | FR28 (JSON log instead of cryptographic chain), FR29 (log entry instead of Ed25519 signature) |
| **Deferred** | FR5–6, FR27, FR31–32, FR35, FR40–56 |

### Non-functional requirements impact (summary)

- **NFR-RI (Path B / Reference Implementation):** **Promoted to primary success metric.** NFR-RI1 (ADK pattern coverage), NFR-RI3 (Ruff/mypy/ESLint/TS strict), NFR-RI5 (clone-to-demo, relaxed to ≤60 min), and NFR-RI7 (Jinja templates with golden inputs) all kept.
- **NFR-S (security), NFR-A (availability), NFR-SC (scalability), NFR-AC (accessibility audit), NFR-O (observability infrastructure), NFR-Compliance:** All deferred for the demo.
- **NFR-P (performance):** Targets remain aspirational; no formal verification.

### Reference

For the full impact analysis, recommended approach, and detailed change proposals, see `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`. For the re-scoped epic and story breakdown, see `Documentation/planning-artifacts/epics.md` (rewritten 2026-04-29).

---

## Project Classification

| Dimension | Value |
|-----------|-------|
| **Project Type** | B2B SaaS platform (`saas_b2b`) |
| **Domain** | Fintech — KYC/AML (`fintech`) — high regulatory complexity (RBI, FIU-India, pluggable multi-jurisdiction) |
| **Complexity** | High — multi-agent orchestration, cryptographic audit, regulated-industry data handling, vendor pluggability, cross-system integration (core banking, screening, MCA, GST) |
| **Project Context** | Greenfield — no existing system; product brief approved v1 on 2026-04-24 |
| **Primary Stack** | IBM watsonx Orchestrate + Python Agent Development Kit (ADK) · React + FastAPI frontend · Pydantic contracts on agent/tool boundaries |
| **Internal Architectural Intent** *(not a product promise)* | Reference implementation / showcase for IBM watsonx Orchestrate + ADK patterns — drives architecture and NFR decisions; invisible to the bank-buyer-facing product narrative |

## Success Criteria

### User Success

**Primary user: Priya — KYC Analyst**

| Outcome | Target | Baseline | Signal |
|---------|--------|----------|--------|
| Case completion time (SME onboarding) | ≤ 15 min | 2–5 hours | Time from case-open to decision-commit, measured server-side |
| Officer active touch time per case | ↓ ≥ 70% vs baseline | Current active touch time (captured during pilot week 1) | Keystroke + mouse-event telemetry during case open |
| Decisions with agent-drafted rationale | 100% | 0% (today officers author from scratch) | Ratio of committed decisions where rationale field originated from agent draft |
| Officer NPS (10-analyst pilot, post 4-week use) | ≥ 40 | N/A | Post-pilot survey |
| "Cockpit changes how I feel about the work" (post-pilot) | ≥ 80% agree/strongly agree | N/A | 5-point Likert, post-pilot survey |

**Emotional success moments (what we're designing for):**

1. **First reasoning-trace slide-out.** Priya clicks what an agent did, panel opens, she goes "oh — I can actually see what it's thinking." Reported qualitatively in pilot interviews.
2. **First edit-don't-author.** Priya reviews an agent-drafted EDD rationale, edits two sentences, commits. She didn't write from a blank page. Measured: % of first-week decisions committed within 30 seconds of opening Decision Zone.
3. **First silent auto-close** (Future, perpetual-KYC). A refresh case closes itself, Priya is told "nothing changed, we verified." She approves in one click. Feeling: "I got my Friday back."
4. **First Regulator Lens export.** Priya exports a closed case for an internal auditor, auditor returns zero remediation. Feeling: "the trail is unimpeachable."

### Business Success

**Buyer: Chief Compliance Officer / Head of Financial Crime (mid-size bank, 500K–10M accounts)**

| Timeline | Outcome | Target | Signal |
|----------|---------|--------|--------|
| **3-month (post-MVP)** | Signed pilot LOIs with mid-size banks | 1–2 | Paper-signed pilot agreements |
| **3-month** | MVP demo lands with RBI/FIU-India ex-regulator advisor | "Pass" on cryptographic ledger + Regulator Lens | Advisor validation call; issues list ≤ 5 non-blocking |
| **6-month** | Pilot live, case volume running | ≥ 10 analysts · ≥ 200 SME cases processed | Production telemetry |
| **12-month** | First paying bank · second bank in evaluation | 1 paid + 1 LOI | Commercial contract |
| **12-month** | Whitespace timer — no incumbent has shipped competing cockpit UI | True | Competitive quarterly review |

**Path-B showcase dimension (internal; not part of the bank-buyer promise):**

| Outcome | Target | Signal |
|---------|--------|--------|
| Orchestrate + ADK reference adoption | Project referenced in ≥ 1 IBM Orchestrate case study, docs, or DevX example | IBM marketing / docs inclusion |
| ADK pattern coverage demonstrated | Canonical examples of: supervisor/collaborator composition · agent-as-tool · Pydantic-contracted tools · HITL approval steps · background/scheduled agents · parallel meta-critic · conversational agent with mesh-as-tools · Orchestrate-trace-backed audit | Pattern checklist verified in code review |
| Developer-audience "wow" | Qualitative: architect/dev reviewer reports ≥ 1 "I didn't know Orchestrate could do this" moment | Internal DevX review session |

### Technical Success

| Requirement | Target | Signal |
|-------------|--------|--------|
| Agent precision — Document Intelligence | ≥ 95% on field extraction | Corpus benchmark (500-doc test set) |
| Agent precision — UBO construction (basic, no shell/nominee) | ≥ 95% structural accuracy | Known-good ground-truth set |
| Decision rationale "edit-rate" | ≥ 60% of committed rationale is ≥ 80% agent-drafted (officer edits < 20%) | Diff tracking on rationale commits |
| Cryptographic audit ledger | Tamper-evident; every officer decision + agent action signed; Regulator Lens export passes mock internal audit with zero remediation | Mock audit artifact |
| Agent action provenance coverage | 100% of data points rendered in cockpit carry provenance metadata | Automated UI test asserting provenance pill on every rendered datum |
| End-to-end case throughput (single case, cold start) | Full mesh resolves SME case to decision-ready state in ≤ 2 min (agent work; officer time excluded) | Telemetry on MVP demo cases |
| Availability (pilot SLO) | 99.5% during business hours (India) | Uptime monitoring |
| Screening-vendor pluggability | Changing vendor requires ≤ 1 adapter file modification, zero changes to agent contracts | Architecture review |

### Measurable Outcomes

The MVP is **not successful** unless **all of these hold simultaneously** at the end of the 4-week pilot window:

1. Median SME onboarding case time ≤ 15 min (95th percentile ≤ 30 min)
2. Officer NPS ≥ 40
3. ≥ 80% of officers agree "cockpit changes how I feel about the work"
4. Mock audit returns zero remediation asks on Regulator Lens export
5. Agent precision benchmarks ≥ 95% on Document Intelligence and UBO (basic)
6. All 8 MVP agents demonstrably exercise distinct ADK patterns per the Path-B pattern checklist

## Product Scope

### MVP — Minimum Viable Product

**Timebox:** 4–6 weeks. **Slice:** "SME Onboarding" — the richest single vertical that exercises the full story in one flow. Persona Priya's real-world job spans SME + retail + periodic refresh; MVP covers only the SME slice — retail and refresh are in Future Considerations.

| Dimension | In | Out |
|-----------|-----|-----|
| **Case type** | SME onboarding | Retail onboarding, periodic refresh, EDD on PEP, adverse media investigation |
| **Agents (8 of 14)** | Case Supervisor · Document Intelligence · Entity Verification · UBO Graph (basic — no shell/nominee) · Screening (single vendor) · Risk Scoring · Writing (rationale + EDD only) · Cockpit Chat | Identity Verification · Investigation · Decision Guardrail · pKYC Watcher · Regulatory Intelligence · Meta-Critic |
| **Cockpit zones (4 of 6)** | Queue Rail · Case Canvas · Agent Copilot Pane · Decision Zone | Top Bar (polished) · Bottom Ribbon |
| **Officer modes (2 of 6)** | Deep Investigation · SAR/EDD Writing (Zen) | Triage · Factory Refresh · Regulator Lens (export works; mode UI polish deferred) · Training/Shadow |
| **Visualizations** | UBO Canvas · Risk Score Breakdown · Screening Explainer | Timeline causality arrows · Ripple map |
| **Output** | Case closure · Regulator Lens export (PDF + JSON) · cryptographic audit ledger | Multi-jurisdiction SAR |
| **Jurisdiction** | India (RBI / FIU-India) | All others (pluggable interface must exist, not populated) |
| **Compliance floors (non-negotiable in MVP)** | Every datum provenance-tagged · decisions reversible-with-reason · audit ledger cryptographically verifiable · officer sign-off captured per decision | — |

### Future Considerations

Items deferred from MVP — not phased, prioritized by pilot feedback when the time comes:

- **Retail onboarding** — second case type; unlocks pilot breadth
- **Identity Verification agent** — retail onboarding dependency
- **Aadhaar eKYC · PAN-NSDL · Digilocker integrations** — retail identity flow; production Aadhaar needs KUA license handled by deploying bank via pluggable adapter
- **Perpetual KYC Watcher + silent auto-close** — event-driven refresh, backlog elimination
- **Investigation agent + Decision Guardrail** — adverse-media alert flow
- **Triage mode + Factory (Batch Refresh) mode** — keyboard-loop throughput modes
- **Regulatory Intelligence agent** — jurisdiction rule-change tracking
- **Meta-Critic** — parallel shadow-run agents reviewing agents
- **Mobile senior-approval flow** — EDD on PEP end-to-end
- **Second screening vendor** — pluggability proof
- **Timeline with causality arrows · Ripple map**
- **Full Admin UI** — operational self-service for tenant config
- **Polished CCO Portfolio Dashboard** with cohort drill-down
- **FIU-India STR/CTR automated submission**
- **Case Time-Machine** — scrub any case back in time
- **Voice-Approve on mobile** — Team Leads approving from the car
- **Live collaborative cursors** — multi-officer real-time
- **Banker's Desk skeuomorphic skin** (optional)
- **"Commit with reservation"** — officer uncertainty as first-class state
- **Full multi-jurisdiction** — US (FinCEN), EU (6AMLD), UK, Singapore (MAS), UAE
- **Training/Shadow mode** — junior learns via redacted live-follow and case replay
- **Agent self-programming** — agents propose their own tool additions via Meta-Critic

## User Journeys

### Journey 1 — Priya · SME Onboarding, Happy Path

**Scene.** Tuesday 10:45 AM. Priya opens her cockpit. Queue Rail (left, 260px) lists 11 cases ordered by risk × SLA × continuity. Second from top: **Shree Venkat Trading Pvt Ltd** — new SME, documents uploaded 9 minutes ago. She presses `j j Enter`. Case opens on Canvas.

**Rising action.** The case is not a blank form. Intake agents have already run:
- Document Intelligence extracted 23 fields from CoI, PAN, GST, bank statement, 3 utilities. Every field carries a **provenance pill** (source + confidence).
- Entity Verification cross-referenced MCA and GST — structure matches, active, no red flags.
- UBO Graph renders 3 directors + 2 shareholders as a force-directed canvas, confidence-banded.
- Screening hit: one amber — a director's name partially matches a PEP record.
- Risk Scoring: 62/100 "Medium" — stacked bar decomposes Country (low) · Entity type (medium) · Ownership clarity (medium) · Screening (medium-amber).

Priya scans in 40 seconds. Right-hand Agent Copilot Pane shows a live mesh activity feed with status pills (done/in-progress/blocked/needs-input). She clicks the amber screening hit.

**Climax — the reasoning-trace slide-out.** A panel slides out from the right:
- **What Screening searched:** "Name: Ramesh Kumar, DOB: 1978-04-15, against ComplyAdvantage"
- **What hit:** 1 PEP record — Ramesh Kumar (India), 73% name match, **DOB mismatch (1961)**
- **Confidence self-rating:** 62% · "medium — would upgrade to high if DOB-match; downgrade to low if address+photo confirm different person"
- **What would change it:** DOB confirmation, address match, or photo ID match

Priya types a one-liner — *"DOB mismatch; PEP name common; no corroborating evidence."* The agent's pre-drafted rationale was already 80% there; she edits two sentences in the Decision Zone.

**Resolution.** She commits. 120s undo timer ticks. Rationale seals into the cryptographic audit ledger. Regulator Lens export button goes live. **Total case time: 11 min 40 sec.** She presses `j` and moves on.

**Capabilities revealed:** Queue Rail risk-SLA ordering · keyboard nav (j/k/x/d) · Case Canvas with collapsible panels · provenance pills on every datum · UBO Canvas (basic) · Agent Copilot live feed + status pills · reasoning-trace slide-out · Risk Score stacked-bar explainer · Screening Explainer 3-column card · Decision Zone with pre-drafted rationale + 120s undo · cryptographic audit ledger write · Regulator Lens export trigger.

### Journey 2 — Priya · SME Edge Case, Unclear UBO → EDD

**Scene.** Wednesday 2:15 PM. New case: **Sureshwara Enterprises LLP.** Documents in, intake ran, but the UBO Graph shows a **red confidence band** — 3 nominee directors flagged (same registered address as a filing agent), one shareholder is a Mauritius LLC with no disclosed UBO. Priya's gut says: shell candidate.

**Rising action.** She opens UBO Canvas. Red dotted edges mark "nominee suspected" relationships. She clicks the Mauritius node. Reasoning trace: *"Foreign entity; no MCA data; jurisdictional opacity; unable to resolve UBO ≥ 95% confidence."*

**Climax — drag-correct-and-teach.** From past cases, Priya knows the real UBO is a trust held by a known individual, disclosed via an RM email from Nov 2024. She **drags an edge** from the trust node to the UBO, tags it *"real UBO — source: RM email 2024-11,"* attaches the email (evidence bundle shelf opens). The UBO agent asks: *"Treat as ground-truth correction for future shell/nominee detection?"* She says yes. Agent records a learning event.

**Rising action cont.** Risk Score updates to 78/100 "High." Case auto-promotes to **EDD track.** Priya switches to **SAR/EDD Writing mode (⌘+4)** — dark background, minimal chrome, evidence dock docked right. The Writing agent has drafted a 2-page EDD memo citing the UBO correction. She edits 3 paragraphs. Decision: **"Proceed with enhanced monitoring — 3-month review."**

**Resolution.** Commit. Audit ledger seals the UBO correction, the evidence attachment, the agent learning event, and the officer decision. Case closes to EDD monitoring queue.

**Capabilities revealed:** UBO Canvas drag-correct-and-teach · evidence bundle shelf with attachment ingest · agent learning event capture · automatic risk re-scoring on correction · mode switch ⌘+4 to SAR/EDD Writing Zen · Writing agent narrative drafter · EDD-outcome decision state ("enhanced monitoring — N-month review") · EDD monitoring queue promotion.

### Journey 3 — Rohan · Team Lead · Senior Approval on EDD

**Scene.** Thursday 5:00 PM. Rohan is Priya's Team Lead. He gets a desktop notification: *"2 cases pending your approval."* Cockpit opens to his **Team Lead view** — read-only analyst cases + a dedicated approval queue.

**Rising action.** Opens case Sureshwara. Sees Priya's UBO correction, the EDD narrative, the risk score, and the Audit Trail panel — full history of agent actions (timestamped, model-ID'd) and officer actions (signed).

**Climax.** Clicks **"Approve with conditions."** Modal asks for reason + monitoring scope. He types *"Approved; 3-month enhanced monitoring; re-review trigger on any screening delta."* Commits.

**Resolution.** Priya gets a notification. Audit ledger seals his approval with his signature. Case moves to *Approved — EDD Monitoring.*

**Capabilities revealed:** Team Lead read-only + approval view · dedicated approval queue · Audit Trail panel with agent + officer history · approve-with-conditions workflow with rationale + scope capture · role-based access control · inter-role notifications · per-actor digital signatures in ledger.

*(Note: mobile senior-approval flow is Future — MVP is desktop-only.)*

### Journey 4 — Anika · Internal Auditor · Regulator Lens Export

**Scene.** Monday morning. Anika is the bank's internal auditor, prepping for a scheduled RBI inspection in 3 weeks. Her ask: verify 50 closed cases from the last quarter hold up.

**Rising action.** She opens each case in **Regulator Lens mode** — the cockpit reconfigures into a read-only, audit-framed view. Timeline on top. Agent actions below (each with input → output → model ID → timestamp → signature). Officer decisions as sealed commits. Hash chain visible.

**Climax.** She selects 5 cases, clicks **Export Bundle.** Out comes PDF (human-readable narrative + full trail) and JSON (machine-verifiable with hash chain). She runs the bundled verification tool — all hashes match. Every agent action carries model ID, prompt hash, and a signed output. Every officer decision has a signed commit.

**Resolution.** Audit returns **zero remediation asks.** She writes a one-line note to the CCO: *"Ledger holds."*

**Capabilities revealed:** Regulator Lens mode toggle (read-only audit framing) · full case timeline with interleaved agent + officer actions · cryptographic hash chain + signed events · PDF + JSON export bundle · bundled offline verification tool · per-action model ID + prompt hash capture · per-actor signatures.

### Journey 5 — Meera · Chief Compliance Officer · Buyer View (Portfolio)

**Scene.** Friday 9:00 AM. Meera is the bank's CCO. She pulls up her **Portfolio Dashboard.**

**Rising action.** Sees this week at a glance: cases processed (by analyst, case type, jurisdiction) · median case time · SLA breaches · risk-band distribution · EDD throughput · screening-hit false-positive rate · audit readiness indicator. A **Regulator Readiness** widget shows *"100% of closed cases have sealed ledger entries; last mock audit: 0 remediations."*

**Climax.** She drills into a specific cohort — SME onboardings this month that went to EDD. Sees aggregate rationale themes (auto-clustered by Writing agent), Team Lead approval rate, time-to-decision. One theme catches her eye: 4 cases flagged "nominee suspected." She flags them for a retrospective.

**Resolution.** She's ready for her Compliance Committee update. She exports a CCO summary. Board-ready.

**Capabilities revealed:** Portfolio Dashboard (read-only aggregate) · cohort drill-down · auto-clustered rationale themes · Regulator Readiness widget · CCO summary export.

*(Note: MVP ships a minimal version of this — fully polished dashboard is Future.)*

### Journey 6 — Core Banking System · API-Driven Case Ingestion

**Scene.** An RM submits a new SME KYC request via the bank's core banking portal.

**Rising action.** Core banking POSTs to KYC Cockpit: `POST /v1/cases` with customer metadata + document references (presigned URLs or multipart). API returns `{case_id, state: "intake_scheduled"}`. Case Supervisor agent fires. Intake mesh runs.

**Climax.** Within ~2 minutes, case is *"decision-ready"* and appears in Priya's Queue Rail. KYC Cockpit emits webhook `{case_id, state: "decision_ready", assigned_to: priya.id}` back to core banking.

**Resolution.** Priya processes, commits. KYC Cockpit posts back: `POST <callback_url> {case_id, decision: "approve_with_conditions", rationale_excerpt, ledger_ref}`. Core banking updates the customer record and notifies the RM.

**Capabilities revealed:** REST API for case ingestion (POST `/v1/cases`) · presigned URL / multipart doc upload · bank-to-platform auth (API keys or OAuth client credentials) · webhook/callback for state changes and decisions · case state machine exposed in API contract · idempotency on case creation.

### Journey Requirements Summary

**Capability clusters revealed (rollup across journeys):**

| Cluster | Capabilities |
|---------|--------------|
| **Queue & Navigation** | Queue Rail · risk-SLA-continuity ordering · keyboard nav · mode switching ⌘+1–⌘+6 · notifications (inter-role) |
| **Case Canvas & Data** | Collapsible panels (identity, docs, UBO, screening, risk, timeline) · provenance pills on every datum · evidence bundle shelf |
| **UBO & Entity** | UBO Canvas force-directed graph · confidence-banded edges · drag-correct-and-teach · agent learning events · nominee/shell heuristics (basic) |
| **Agent Mesh Visibility** | Agent Copilot Pane live feed · status pills · reasoning-trace slide-out (what searched · what hit · confidence · what would change) |
| **Screening & Risk** | Screening Explainer 3-column card · Risk Score stacked-bar · pluggable screening vendor adapter |
| **Decision & Writing** | Decision Zone with pre-drafted rationale · 120s undo · approve/decline/EDD-monitor outcomes · SAR/EDD Writing Zen mode · Writing agent narrative drafter · approve-with-conditions capture |
| **Audit & Compliance** | Cryptographic audit ledger · per-action model ID + prompt hash · per-actor signatures · Regulator Lens mode · PDF + JSON export bundle · offline hash verification tool |
| **Roles & Approvals** | Analyst · Team Lead (read-only + approval queue) · CCO (portfolio dashboard) · Auditor (Regulator Lens) · Admin (jurisdiction config, Future) · RBAC |
| **Integration** | REST API for case ingestion · presigned/multipart doc upload · webhook callbacks · state-machine API contract · idempotency |
| **Portfolio & Reporting** | CCO Portfolio Dashboard · cohort drill-down · auto-clustered rationale themes (Writing agent) · Regulator Readiness widget |
| **Admin (Future)** | Jurisdiction onboarding (rules, SAR templates, DocIntel training packs) · screening vendor swap · RBAC config |

## Domain-Specific Requirements

### Compliance & Regulatory

**India (MVP jurisdiction — binding):**

| Regulation | What it requires |
|------------|-------------------|
| **RBI Master Direction on KYC (2016, updated through 2024)** | Customer Due Diligence (CDD); Risk categorization (Low/Medium/High); Periodic review cadence (Low: 10y, Medium: 8y, High: 2y); Enhanced Due Diligence on High-risk and PEPs |
| **PMLA 2002 + PML Rules 2005** | Record retention ≥ 5 years post-case; STR filing within 7 days of detection to FIU-India; CTR for cash transactions > INR 10 lakh |
| **Section 12, PMLA** | Ongoing monitoring obligation — not a one-time check |
| **Companies Act 2013 §89/90 + Significant Beneficial Owner Rules 2018** | UBO disclosure (individuals with ≥ 10% ownership or significant influence); captured in UBO Canvas |
| **DPDP Act 2023** | Data Protection — consent, data principal rights, breach notification; customer data minimization; purpose limitation |
| **FIU-India reporting standards** | XML schema for STR/CTR; MVP must export in this format (automated submission is Future; MVP captures data to support it) |

**Pluggable (Future, via jurisdiction config):**

- **EU:** 6AMLD; EBA Guidelines on ML/TF risk factors; GDPR
- **UK:** MLR 2017 (as amended); FCA Handbook (SYSC, FCG)
- **US:** BSA + FinCEN CDD Rule; OFAC sanctions
- **Singapore:** MAS Notice 626 (banks); AML/CFT Notices
- **UAE:** Central Bank AML/CFT Guidelines

**Explainability floor (non-negotiable in MVP):**

- Every automated agent output is decomposable — what was searched, what returned, confidence, what would change it
- Every risk score stacks into component contributions (country · entity type · ownership clarity · screening · adverse media)
- Every screening hit exposes what-matched (name similarity · DOB · address · photo · other identifiers)
- Every decision rationale is human-readable and human-signed
- Zero "black box" decisions — if an agent cannot produce a reasoning trace, the case blocks for human attention

**Auditable (non-negotiable in MVP):**

- Every agent action and officer decision is reconstructible from ledger
- Each agent action captures: agent ID, model ID, prompt hash, tool inputs, outputs, timestamp, platform signature
- Each officer action captures: user ID, action type, inputs, signature from user credentials
- Hash chain verifiable **offline** via shipped verification tool (regulators cannot be required to call our platform)
- Immutable append-only; no mutation or deletion API

### Technical Constraints

**Security (OWASP ASVS Level 2 baseline):**

- TLS 1.3 for all data in transit
- AES-256 for data at rest (field-level encryption for customer PII)
- Secrets: vault/HSM-backed — never env vars or config files
- Platform signing key HSM-protected; per-user credentials for officer signatures
- Append-only audit log; cryptographic hash chain linking entries
- RBAC enforced at **both** API and UI layers (deny-by-default)
- Session timeout: 30 min inactivity (compliance-sector norm)
- All API access audit-logged; anomaly detection on admin actions
- Threat model: screening vendor compromise, PII exfiltration, ledger tampering, model prompt-injection

**Privacy & Data Handling:**

- **Data minimization:** only case-relevant PII rendered in UI; cross-case aggregation requires privacy review
- **Data residency:** India MVP hosted onshore; jurisdiction-specific residency rules configurable
- **Retention:** 10 years post-case closure (max regulated period); cold-storage tiering after 2 years; rolling delete post-10y with ledger reference preservation
- **Consent handling:** Aadhaar eKYC (retail, Future) requires KUA license + per-instance consent capture
- **PII in agent prompts:** Prompt templates reviewed for PII minimization; structured redaction layer between agents and telemetry; no customer data in LLM provider training pipelines without explicit consent

**Performance:**

| Target | SLO |
|--------|-----|
| UI navigation actions (p95) | ≤ 200 ms |
| Reasoning-trace slide-out (p95) | ≤ 500 ms |
| Case creation API (p95) | ≤ 1 s |
| Full mesh cold-start to decision-ready (p95) | ≤ 2 min |
| UBO Canvas initial render (p95, ≤ 50 nodes) | ≤ 1.5 s |
| Audit ledger export (single case) | ≤ 10 s |

**Availability & Resilience:**

- MVP pilot SLO: **99.5% business hours IST** (target uptime during analyst work)
- GA SLO: 99.9%
- DR: **RPO ≤ 1 hour, RTO ≤ 4 hours**
- Agent failure isolation: one agent failure must not cascade — Case Supervisor retries or flags for human
- Graceful degradation: if screening vendor is down, case blocks with clear reason; no stale screening results surfaced

**Operational Modes:**

- **Asynchronous-eager intake:** agents fire on case creation; ingestion API returns immediately
- **Synchronous officer interaction:** all cockpit actions respond ≤ 200ms p95
- **Event-triggered / scheduled background agents** (pKYC, Regulatory Intel — Future): cron or event-bus driven

### Integration Requirements

| System | Direction | Protocol | MVP | Notes |
|--------|-----------|----------|-----|-------|
| **Core banking system** | In (case ingestion) + Out (decision callback) | REST + webhook; SFTP batch fallback for legacy banks | ✓ | Idempotent case creation; state-machine exposed |
| **Screening vendor** (single) | Out | Vendor REST API | ✓ | Pluggable adapter; MVP picks one of ComplyAdvantage / LSEG World-Check / Dow Jones / ABBYY (architecture decision open) |
| **MCA (Ministry of Corporate Affairs)** | Out | REST + scraping fallback | ✓ | Company master, director lookup, filings |
| **GST portal** | Out | REST | ✓ | GSTIN verification |
| **Adverse media** | Out | Vendor REST | ✓ (basic — via screening vendor if supported) | Pluggable |
| **Aadhaar eKYC** (retail) | Out | UIDAI API (KUA license required) | ✗ Future | Retail onboarding unlock |
| **PAN-NSDL** | Out | REST | ✗ Future | Retail onboarding unlock |
| **Digilocker** | Out | OAuth + Digilocker API | ✗ Future | Consent-based doc pull |
| **Identity provider (bank's)** | In | SAML 2.0 / OIDC | ✓ | SSO for officers |
| **Document storage** | Internal | S3-compatible (AWS S3 / IBM COS / bank on-prem) | ✓ | Presigned URLs; encrypted at rest; separate from metadata store |
| **Email / in-app notifications** | Out | SMTP + in-app | ✓ | Officer notifications, approvals |
| **Mobile push** | Out | Native push | ✗ Future | Team Lead approvals |
| **Observability** | Out | OpenTelemetry + Orchestrate trace export | ✓ | Traces enriched with case context; PII-scrubbed |
| **FIU-India STR/CTR submission** | Out | FIU-XML schema | ✗ Future | Agent generates; officer approves; submission via bank's existing FIU pipe in MVP |

**Pluggability guarantee (MVP architecture mandate):** Every external vendor integration sits behind a contract interface (Pydantic schema at agent boundary). Swapping vendors requires one adapter file change, zero agent logic changes. Verified by a contract-conformance test suite.

### Risk Mitigations

| Risk | Mitigation |
|------|------------|
| **Screening vendor lock-in** | Pluggable adapter from day 1; contract-conformance tests validate new vendors |
| **Agent precision drift over time** | Meta-Critic agent (Future) shadow-runs; MVP captures officer ground-truth corrections as labeled signal |
| **Regulator rejects agent-authored rationale** | "Edit, don't author" mandate — zero commits without officer edit or explicit sign-off; officer rationale is canonical record in ledger |
| **PII leakage in LLM prompts / telemetry** | Prompt templates reviewed for PII minimization; structured redaction layer between agents and telemetry; no customer data in LLM provider training pipelines |
| **Model hallucination in rationale drafts** | Writing agent cites ledger entries by ID; hallucination surfaces as broken citation; mandatory officer edit catches; Meta-Critic (Future) flags |
| **Prompt injection via document content** | Input sanitization; structured agent/tool boundaries with Pydantic contracts; agents treat document-derived text as data not instructions |
| **Jurisdictional drift in scope** | India-first with pluggable interfaces; jurisdictional rules are configuration, not code |
| **Ledger tampering or key compromise** | HSM-backed signing keys; hash chain detects tampering at verification time; offline verifier tool means regulator doesn't trust our platform — only math |
| **Cold-storage retention cost blowout** | Tiered storage (hot 90 days → warm 2y → cold 2–10y → purge); ledger references preserved even after customer data purged |
| **Officer adoption resistance (cockpit = surveillance)** | Confidence banding, fatigue signals, officer-in-design; no hidden telemetry; "what we capture" page in cockpit settings |
| **Over-automation drift** (silent auto-close rates too high, officers disengage) | Configurable auto-close thresholds; sampling-based human review; monthly automation KPI review |
| **Core banking integration brittleness** | Webhook + SFTP batch fallback; idempotency on case creation; explicit state machine in API contract |
| **Evidence integrity** (uploaded docs tampered post-ingestion) | Documents immutable after ingest; SHA-256 hash stored in ledger; checksum verifiable on download |

## Innovation & Novel Patterns

### Detected Innovation Areas

Seven areas with genuine novelty — validated against the competitive landscape in the product brief. Commodity capabilities (multi-agent orchestration, pluggable vendor interfaces, document intelligence) are intentionally excluded.

#### 1. Officer-First Cockpit UX for Agentic KYC *(market inversion)*

Every shipping "agentic KYC" platform — Fenergo, Moody's, IBM Consulting KYC-AI, Genpact, Fulcrum FD Ryze, Lyzr, Akira — bolts agents onto 2015-era case-management forms. KYC Cockpit inverts the stack: **agent mesh is the product, cockpit is the moat.** The cockpit is a purpose-built workspace (six zones, six modes, density gradient) that makes mesh activity legible and collaboratable. Genuine UX inversion, not an incremental polish. Whitespace is open ~12–18 months before a counter-move lands.

#### 2. "What would change your mind?" Reasoning Traces *(novel interaction pattern)*

Industry baseline for LLM explainability is *"show the reasoning"* (chain-of-thought, citation rendering). KYC Cockpit goes further: every agent output exposes a **counterfactual** — "my confidence is 62% medium; would upgrade to high if DOB matches, downgrade to low if address+photo confirm different person." Forces agents to commit to the evidentiary boundary of their own conclusion, gives officers actionable next steps, and produces a better audit record than raw reasoning traces alone.

#### 3. Drag-Correct-and-Teach on UBO Canvas *(novel human→agent feedback loop)*

When Priya drags an edge on the UBO graph to correct a nominee assignment, the agent **asks permission** to treat the correction as ground truth for future cases. Captured as a named "learning event" in the ledger (officer ID, correction, context, timestamp). Production-grade, audit-compliant, opt-in feedback loop — not silent RLHF, not a thumbs-up button, not a training-data collection scheme. Closest industry analog: interactive structured-data annotation (Labelbox, Scale) — none of which run inside a real decision workflow.

#### 4. Offline-Verifiable Cryptographic Audit Ledger *(first-of-kind for KYC)*

Industry standard for KYC audit is *activity logs + database queries*. Regulators trust the platform's word. KYC Cockpit ships a **hash-chained, signed, offline-verifiable** ledger + a standalone verification tool — regulators verify math, not our platform. Every agent action captures model ID, prompt hash, and signed output; every officer decision is signed with user credentials. Cryptographic guarantees survive even if our platform is offline, compromised, or sunsetted.

#### 5. "Edit, Don't Author" as a Measured Product Principle *(novel product metric)*

"Human-in-the-loop" and "co-pilot" are buzzwords. KYC Cockpit turns this into a **measured metric**: % of decisions where rationale originated ≥ 80% agent-drafted and was edited < 20% by the officer. Goal is ≥ 60%. Below that, the writing agent is either too vague or officers are rewriting — either way, the product is failing its principle. Product-level metric tied to UX, not an agent-eval metric.

#### 6. Confidence-Banded Visual System *(design primitive, not a component)*

Four confidence tiers rendered consistently across every agent output — data pills, graph edges, score bars, screening hits, decision recommendations. Officers allocate brain-spend proportionally. Elevated from a UI component to a **design primitive**: any new feature must declare its confidence-band treatment in the design spec before implementation. Industry analog: confidence bars in Grammarly, autopilot trust levels in Tesla FSD — neither is a system-wide primitive.

#### 7. Six-Mode Cockpit with Density Gradient *(novel workspace design)*

Six officer modes (Triage, Deep Investigation, Factory Refresh, SAR/EDD Zen, Regulator Lens, Training) with a **density gradient** — dense triage → full cockpit → calm decision zone → zen writing. Same underlying case data, radically different UI footprint per task. Switching is instant (⌘+1–⌘+6). No shipping KYC platform offers modes; they offer one screen that tries to do everything. Closest analog: Figma's design-vs-prototype modes.

### Market Context & Competitive Landscape

**Direct agentic-KYC competitors (already shipping agents):**

| Vendor | Agent claim | Officer UI |
|--------|-------------|------------|
| **Fenergo** | MVP in QKS AI Maturity Matrix 2026; agentic data sourcing, materiality, decisioning | Form-based case management |
| **Moody's pKYC** | Chartis category winner (2y); 600M+ companies, 1.7B ownership links | Form-based case management + dashboards |
| **IBM Consulting KYC-AI** (AWS Marketplace) | 50%+ manual task automation via agents | Form-based case management |
| **Genpact Banking Analyst Suite** | Multi-agent orchestrator + worker architecture | Form-based case management |
| **Fulcrum FD Ryze · Lyzr.ai · Akira.ai · Fintechera** | Agentic KYC startups | Form-based (varies) |
| **JPMorgan (in-house)** | 90% productivity gain claim | Internal — not a product |

**Traditional AML/KYC platforms (less agent-native):**

- SymphonyAI, NICE Actimize (Forrester AML Wave leaders — rule/ML-heavy)
- Oracle FCCM, SAS, Napier, Quantexa, Lucinity, ComplyAdvantage

**Whitespace confirmed.** No shipping platform pairs an agent mesh with a purpose-built officer cockpit. Every incumbent could plausibly add one — this is a **12–18 month window**, not a permanent moat.

**Adjacent UX inspiration (non-KYC):**

- Bloomberg Terminal (keyboard-first, dense, mode-switchable)
- Linear (density + keyboard palette + mode discipline)
- Figma (mode switching + collaborative object manipulation)
- GitHub Copilot Chat (inline reasoning traces + edit-don't-author flow)

### Validation Approach

Each innovation has a specific validation test. Not all are binary pass/fail — some are directional.

| Innovation | Validation method | Signal |
|------------|-------------------|--------|
| **Officer-first cockpit UX** | 3–5 officer interviews pre-MVP + 10-analyst pilot post-MVP | Officer NPS ≥ 40; ≥ 80% agree "cockpit changes how I feel"; qualitative "I can't go back" statements |
| **"What would change your mind?" reasoning traces** | Officer task-completion study: scenario with ambiguous screening hit | Officers using counterfactual-augmented trace reach decision ≥ 25% faster than those using reasoning-only trace |
| **Drag-correct-and-teach** | Precision-over-time study on UBO agent | Agent precision on nominee/shell detection improves measurably in pilot week 4 vs week 1 after ≥ 20 correction events |
| **Offline-verifiable ledger** | Mock internal audit + advisor review by ex-regulator | Zero remediation asks; ex-regulator validates ledger holds for RBI/FIU-India inspection |
| **"Edit, don't author" metric** | Rationale-diff tracking in pilot | ≥ 60% of decisions: ≥ 80% agent-drafted, < 20% officer-edited |
| **Confidence-banded visual system** | Eye-tracking pilot (small-sample, qualitative) | Officers fixate proportionally more on low-confidence items; self-report matches observation |
| **Six-mode cockpit with density gradient** | Mode-usage telemetry in pilot | ≥ 4 of 6 modes used per analyst per week; mode-switch frequency ≥ 10×/day/analyst |

**Fallback for each innovation if validation fails:**

- **Cockpit UX** — fall back to single-mode "Deep Investigation only" (still agent-visible, still cockpit-styled, but less mode ambition)
- **Counterfactual reasoning** — fall back to standard reasoning traces without "what would change it"
- **Drag-correct-and-teach** — fall back to manual corrections without learning-event capture (correction still audits, just doesn't feed back)
- **Offline ledger** — fall back to signed online-only verification (regulators can query our API); weaker audit story but still stronger than industry baseline
- **"Edit, don't author" metric** — adjust threshold from 60% to whatever observed baseline is; make the metric a dashboard rather than a release gate
- **Confidence bands** — fall back to binary (high-confidence / low-confidence) vs 4-tier
- **Six modes** — fall back to 2 modes (Deep Investigation + Writing) and add others only when demand proven

### Risk Mitigation *(innovation-specific)*

Additional risks beyond those covered in Domain-Specific Requirements:

| Innovation risk | Mitigation |
|------------------|------------|
| **"Counterfactual reasoning" is a research frontier — agents may not produce reliable counterfactuals** | Counterfactual generation is a constrained templated task (not free-form); structured output schema via Pydantic; Meta-Critic (Future) validates counterfactual correctness against ground truth |
| **Drag-correct-and-teach becomes a poisoning vector** (officer corrects wrongly, agent learns wrong thing) | Corrections captured but **not auto-trained** — they're labeled signal, reviewed quarterly before any fine-tuning; Team Lead approval required for corrections on closed cases |
| **Confidence bands feel gimmicky if bands don't correlate with actual agent accuracy** | Calibration study pre-pilot: does "62% medium" actually mean 62% of such calls are correct? If not, recalibrate the band thresholds per agent |
| **"Edit-rate" metric drives wrong behavior** (officers rubber-stamp to hit the metric) | Pair with an **accuracy audit** — sampled mock-auditor review of committed rationales; edit-rate is meaningless if decisions are wrong |
| **Modes add cognitive load** (officers get confused about which mode to be in) | Default to Deep Investigation; mode switches are discoverable but not required; pilot mode-usage telemetry tells us if anyone adopts the other modes |
| **Cockpit UX feels gimmicky to senior analysts** who want speed over polish | Keyboard-first is the answer — if ⌘K, j/k/x/d, and ⌘+1-6 are fluent, the polish doesn't slow them down. If pilot seniors report friction, strip animations/transitions without changing functionality |

## B2B SaaS Specific Requirements

### Project-Type Overview

KYC Cockpit is a **B2B SaaS platform** delivered to regulated banks. Each customer is a bank (the tenant); within a tenant, multiple officer roles operate. The product is positioned for **cloud-hosted** delivery with an **on-prem / VPC** option for banks with strict data-residency or regulatory requirements.

### Technical Architecture Considerations

**Tenant isolation posture.** Bank data must never cross tenant boundaries. This is a hard security invariant, not a soft constraint — enforced at API, agent, and datastore layers. Signing keys are per-tenant. Screening vendor credentials are per-tenant. LLM prompts never include data from other tenants.

**Deployment model.** Default is cloud-hosted SaaS on IBM Cloud / AWS / Azure with per-tenant isolation. On-prem / VPC deployment supported for banks that require it — same image, different runtime; no code fork. Telemetry, observability, and upgrade paths work in both.

**Upgrade/versioning.** Tenants on different version trains (pilot, GA, LTS). Per-tenant feature flagging so a pilot bank can enable pKYC Watcher while a GA bank cannot. Backwards-compatible API contracts; breaking changes require version bump.

### Tenant Model

**MVP:** Single-tenant deployment per bank. Simpler isolation, faster to ship, fits pilot scope. Architecture supports multi-tenant from day one but it's not activated.

**Future:** True multi-tenant where economically justified (e.g., cohort of smaller banks sharing infra with hard isolation). Requires multi-tenant hardening + per-tenant key management + regulatory blessing.

| Concern | MVP implementation |
|---------|-------------------|
| **Tenant identity** | `tenant_id` in URL path (`/t/{tenant_id}/v1/...`) + JWT claim; validated at API gateway and every agent/tool boundary |
| **Data isolation** | Separate database schema per tenant; separate S3 bucket per tenant for documents; separate HSM signing key per tenant |
| **Cross-tenant query** | Forbidden by default; any query lacking tenant_id raises `TenantScopeError` and is logged as a security event |
| **Agent data boundaries** | Every Pydantic contract includes `tenant_id`; agents read/write within tenant scope only; violation trips automated test failure |
| **LLM prompt isolation** | Prompts and retrieved context are tenant-scoped; no prompt template can reference cross-tenant state |
| **Tenant onboarding** | Admin-initiated: config pack (jurisdiction rules, screening vendor, SAR template) + SSO setup + signing key gen + initial user invites |
| **Tenant offboarding** | Export bundle (all case data + ledger) → data deletion after regulatory retention satisfied; ledger reference preserved for hash chain integrity |

### Permission Model (RBAC Matrix)

Six roles; MVP ships roles 1–4 + role 6 (API Consumer). Role 5 (Tenant Admin) has a runbook-equivalent in MVP; full Admin UI is Future.

| Role | Description | MVP? |
|------|-------------|------|
| **1. KYC Analyst** (Priya) | Processes cases: triage, investigate, decide, write rationale/EDD | ✓ |
| **2. Team Lead** (Rohan) | Reviews and approves EDD/high-risk cases; read-only access to analyst queues | ✓ |
| **3. Chief Compliance Officer** (Meera) | Portfolio dashboard; cohort analytics; approves policy-level decisions | ✓ (minimal) |
| **4. Internal Auditor** (Anika) | Regulator Lens mode + ledger export; no case modification | ✓ |
| **5. Tenant Admin** (Devang) | Manages users, roles, SSO, screening vendor config, jurisdiction rules | Future (MVP supports admin operations via scripted runbook) |
| **6. API Consumer** (core banking integration) | Programmatic: case ingest, decision callback, status query | ✓ |

**Permission matrix (MVP, compact view — "R" read, "W" write, "X" execute action):**

| Resource | Analyst | Team Lead | CCO | Auditor | Admin | API Consumer |
|----------|:-------:|:---------:|:---:|:-------:|:-----:|:------------:|
| **Own case (assigned)** | R/W | R | R | R | — | — |
| **Other analysts' cases (same team)** | R | R | R | R | — | — |
| **Other teams' cases** | — | R (if lead) | R | R | — | — |
| **Case decision commit** | X | X (conditional) | — | — | — | — |
| **Case approval (EDD)** | — | X | — | — | — | — |
| **Agent configuration** | — | — | — | — | X | — |
| **Agent reasoning trace (own case)** | R | R | R | R | — | — |
| **Audit ledger (own tenant)** | R (own case) | R (team) | R (tenant) | R (tenant) | R | — |
| **Audit ledger export** | — | — | X (portfolio) | X (individual cases) | — | — |
| **Portfolio dashboard** | — | — | R | — | — | — |
| **User management** | — | — | — | — | X | — |
| **Tenant config (jurisdiction, vendor, SAR)** | — | — | — | — | X | — |
| **API: POST /v1/cases** | — | — | — | — | — | X |
| **API: GET /v1/cases/{id}** | — | — | — | — | — | X (own ingests) |
| **API: webhook callback target** | — | — | — | — | — | — (outbound) |

**RBAC enforcement principles:**

- **Deny-by-default** at every layer (API, service, datastore)
- **Role assertions in agent contracts** — every agent action includes the acting role in its Pydantic input; violations trip runtime guards
- **Attribute-based overlays** — team membership, case assignment, and escalation state modify the base role permissions (e.g., analyst can write only on own assigned case; Team Lead can approve only within their team's risk-threshold band)
- **Segregation of duties** — analyst cannot self-approve EDD; Admin cannot read case content (configures the platform, not inspects data)
- **Break-glass** — emergency read access for a named set of roles, fully audited and signed; used for incident response only
- **Impersonation** — Admin cannot impersonate users (single-tenant model); Future multi-tenant may permit support-team view-only impersonation with cryptographic audit

### Implementation Considerations

- **Deployment topology per tenant:** compute cluster, per-tenant database schema, per-tenant S3 bucket, per-tenant HSM key, per-tenant observability namespace
- **Tenant onboarding runbook:** MVP ships as a scripted runbook (invoked by developers); Future moves to Admin UI
- **Screening vendor swap:** behind the contract-conformance test suite — one file change, verify tests pass, ship
- **Jurisdiction pack add:** config-driven bundle (rules, risk weights, SAR template, document taxonomy); MVP has only India pack; pluggability proven by shipping one alternate pack in Future (even if no buyer yet)
- **Version rollout:** canary per tenant; feature flags per tenant; rollback via infrastructure, not data migration (never roll back a tenant's data to a prior schema)

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**Approach: Hybrid Experience MVP + Platform MVP.**

| Dimension | What we're proving | How we prove it |
|-----------|---------------------|-----------------|
| **Experience MVP** | The officer-first cockpit UX actually changes how KYC analysts work — faster cases, higher confidence, better audit posture | 10-analyst, 4-week pilot at a mid-size bank; case-time + NPS + mock audit |
| **Platform MVP** | The agent mesh composes cleanly on IBM watsonx Orchestrate + ADK as a canonical reference architecture | Pattern-coverage checklist verified in code review; developer reviewer "I can build this" signal |

**Explicitly not pursuing:** Revenue MVP (Path B: no monetization in scope); problem-solving-only MVP (too narrow — would leave the Path-B showcase thesis untested).

**The two validation targets:**

| Audience | Success = |
|----------|-----------|
| **Bank officer (Priya)** | Closes her first SME case in ≤ 15 min with an agent-drafted rationale she edits < 20%, the close passes internal audit, and she says "I can't go back" |
| **Solution architect / developer evaluator** | Reads the codebase and says "I understand how to build my own agent mesh on Orchestrate from this reference" — ≥ 1 unprompted "wow" per evaluator session |

**Fastest path to validated learning:** 10-analyst pilot at one mid-size bank, 4-week run, post-pilot NPS + mock audit + pattern-coverage checklist review.

### MVP Feature Set

Feature detail is in **Product Scope → MVP — Minimum Viable Product** above. Strategic summary:

**Scope boundaries (what's in):**

- One case type (SME onboarding) — richest single vertical, exercises full story
- 8 of 14 agents — sufficient to demonstrate all five mesh layers with at least one agent each
- 4 of 6 cockpit zones — Queue, Canvas, Agent Copilot, Decision Zone
- 2 of 6 officer modes — Deep Investigation (default), SAR/EDD Writing (Zen)
- User Journeys 1–2 (Priya happy + edge), 3 (Team Lead minimal), 4 (Auditor minimal), 6 (API ingest); Journey 5 (CCO portfolio) is minimal-viable-only
- One jurisdiction (India), one screening vendor, India-hosted deployment
- Explainability floor + auditability floor (non-negotiable — if either fails, MVP fails)

**What's manual / deferred / mocked:**

- Admin UI is CLI-only runbook (no web UI)
- CCO Portfolio dashboard is minimal (counts, not cohorts)
- Regulator Lens export works end-to-end but UI polish is basic
- Retail onboarding, Identity Verification agent, Aadhaar/PAN/Digilocker — deferred to Future
- Mobile senior approval — deferred
- FIU-India STR/CTR submission — deferred (data captured but emission not automated)
- Second screening vendor — deferred; pluggability interface exists but not exercised

### Future Considerations

Detailed list is in **Product Scope → Future Considerations** above. Items not phased — deprioritized against pilot learnings when the time comes.

### Risk-Based Scoping

Five risks materially shape MVP scope. Each has a mitigation and a **"what we'd cut first"** if pressure mounts.

**Technical Risks:**

| Risk | Likelihood × Impact | Mitigation | If it breaks, cut |
|------|---------------------|------------|---------------------|
| **Agent precision < 95% on Doc Intelligence or UBO** | Medium × High | Corpus benchmarks pre-pilot; Pydantic contracts catch structural failures; manual override flow keeps product usable | Drop UBO shell/nominee detection to Future; ship UBO Canvas with basic structure only |
| **Cryptographic audit ledger has spec gaps** | Low × Critical | Standard primitives (Ed25519 + SHA-256); offline verifier is ≤ 300 lines of Python; ex-regulator advisor validates spec pre-MVP | Cannot cut — auditability is non-negotiable. Delay MVP instead |
| **LLM hallucination in rationale drafts produces bad-faith citations** | Medium × High | Writing agent cites ledger entries by ID (broken citations surface at render time); mandatory officer edit; Meta-Critic (Future) | Tighten Writing agent output schema; reduce free-form text share |
| **Agent mesh composition exposes Orchestrate/ADK immaturity** | Medium × Medium (higher for Path B) | Early architecture spike (Week 1); fall back to direct Python composition with ADK tool primitives if Orchestrate-level collaboration layer is unstable | Drop Meta-Critic and pKYC Watcher (already in Future); keep MVP mesh as linear supervisor → collaborators flow |

**Market Risks:**

| Risk | Likelihood × Impact | Mitigation | If it breaks, cut |
|------|---------------------|------------|---------------------|
| **Incumbent counter-move ships competing cockpit UX** | Medium × High (12–18mo timer) | Speed-to-pilot; design-as-DNA | No cut — respond with deeper UX differentiation |
| **Bank compliance rejects agent-drafted rationale as "unauditable"** | Medium × Critical | Edit-don't-author mandate; officer rationale is canonical record; ex-regulator advisor review pre-pilot | Ship with Writing agent disabled; officer authors from blank page |
| **No pilot bank materializes in timeline** | Medium × High | Leverage IBM Orchestrate sales channels; start with 1–2 warm intros; keep reference-implementation value as fallback | Pivot to IBM-internal showcase + DevX asset first, commercial pilot later |

**Resource Risks:**

| Risk | Likelihood × Impact | Mitigation | If it breaks, cut |
|------|---------------------|------------|---------------------|
| **4–6 week timebox slips** | High × Medium | Aggressive scope discipline; weekly scope review; AI-assisted engineering velocity | Cut in this order: (1) CCO Portfolio minimal, (2) Regulator Lens UI polish (keep export), (3) Team Lead workflow → MVP becomes Priya-only end-to-end |
| **Screening vendor API access / sandbox blocked** | Medium × High | Pick a vendor with strong sandbox (likely ComplyAdvantage); mock adapter fallback for MVP demo | Ship MVP with mocked screening for demo; un-mock in Future |
| **Internal bank compliance review cycles delay pilot start** | High × Medium | Engage compliance advisor early; pre-review design artifacts | Push pilot start by 2–4 weeks rather than compress scope |

## Functional Requirements

### Queue & Case Navigation

- **FR1:** KYC Analysts can view a queue of assigned cases ordered by risk × SLA × continuity.
- **FR2:** KYC Analysts can navigate the queue using keyboard shortcuts (next/previous/open/defer).
- **FR3:** KYC Analysts can open a case and see all intake-agent-computed results without manual refresh.
- **FR4:** KYC Analysts can switch among officer modes (MVP: Deep Investigation, SAR/EDD Writing) via keyboard shortcuts.
- **FR5:** KYC Analysts can access a system-wide command palette to invoke any action by name.
- **FR6:** All roles receive in-app notifications when actions require their attention.

### Case Canvas & Data Display

- **FR7:** KYC Analysts can view a case's identity, documents, UBO, screening, risk, and timeline in collapsible panels on a single canvas.
- **FR8:** Every datum rendered in the cockpit displays a provenance indicator identifying its source agent, upstream source system, and confidence.
- **FR9:** KYC Analysts can open an Evidence Bundle shelf to view and attach supporting evidence (emails, forms, photos) to a case.
- **FR10:** All agent outputs render confidence using a consistent four-tier confidence-banded visual system.

### Agent Mesh Visibility & Interaction

- **FR11:** KYC Analysts can view a live activity feed of every agent working on the current case, including per-agent status (done, in-progress, blocked, needs-input).
- **FR12:** KYC Analysts can open a reasoning-trace slide-out for any agent action showing (a) what was searched, (b) what returned, (c) the agent's confidence self-rating, and (d) a counterfactual — what evidence would change the conclusion.
- **FR13:** KYC Analysts can converse with a Cockpit Chat agent that has access to the full mesh state and current case context.
- **FR14:** The agent mesh automatically runs intake agents on case creation without officer action.

### Entity & UBO Analysis

- **FR15:** KYC Analysts can view an interactive force-directed UBO graph with confidence-banded edges and basic nominee/shell heuristics flagged visually.
- **FR16:** KYC Analysts can drag UBO edges to correct relationships; corrections are captured as named "learning events" in the ledger with officer opt-in for future ground-truth use.
- **FR17:** The Entity Verification agent can cross-reference a case entity against MCA and GST sources and surface mismatches.

### Screening & Risk Analysis

- **FR18:** The Screening agent can evaluate case entities and associated individuals against the configured screening vendor and surface hits with match details.
- **FR19:** KYC Analysts can view a screening-hit explainer showing name-similarity, identifier matches/mismatches (DOB, address, ID), confidence, and the counterfactual.
- **FR20:** KYC Analysts can view a risk-score explainer decomposing the score across contributing factors (country, entity type, ownership clarity, screening, adverse media).
- **FR21:** Risk scores automatically recalculate in response to officer corrections (e.g., UBO edits, manual screening disposition).

### Decision Authoring & Commit

- **FR22:** KYC Analysts can view and edit an agent-drafted rationale in a dedicated Decision Zone before committing a decision.
- **FR23:** KYC Analysts can undo a committed decision within a defined undo window.
- **FR24:** KYC Analysts can commit case decisions with outcomes: approve, decline, approve-with-conditions, escalate-to-EDD.
- **FR25:** KYC Analysts can enter a dedicated SAR/EDD Writing mode with dark-background, minimized-chrome, evidence-docked UI.
- **FR26:** The Writing agent can draft a structured EDD narrative memo citing specific ledger entries and evidence items by reference ID.
- **FR27:** The platform measures and exposes the "edit-rate" metric — the proportion of each rationale that is officer-edited versus agent-drafted.

### Audit, Provenance & Ledger

- **FR28:** Every agent action is captured in an append-only, cryptographically hash-chained ledger including agent ID, model ID, prompt hash, tool inputs, outputs, timestamp, and platform signature.
- **FR29:** Every officer action is captured in the ledger including user ID, action type, inputs, rationale, and a user-credential-based signature.
- **FR30:** KYC Analysts, Team Leads, CCOs, and Internal Auditors can view a case timeline with interleaved agent and officer actions, scoped by role permissions.
- **FR31:** Uploaded documents are immutable after ingestion; SHA-256 hashes are recorded in the ledger and verifiable on download.
- **FR32:** The system prevents any write or delete operation on the ledger through normal application APIs.

### Regulator Lens & Export

- **FR33:** Internal Auditors can switch a case into a read-only Regulator Lens mode that reframes the cockpit into an audit-focused view.
- **FR34:** Internal Auditors can export a case (or a set of cases) as a PDF + JSON audit bundle.
- **FR35:** Each audit bundle is cryptographically self-verifying — hash chain and signatures can be validated offline using a bundled verification tool without calling the platform.

### Approval Workflows

- **FR36:** Team Leads can view a dedicated queue of cases pending their approval.
- **FR37:** Team Leads can approve, approve-with-conditions, or decline cases; conditions (e.g., enhanced monitoring, re-review triggers) are captured as structured state in the ledger.
- **FR38:** Team Leads can view full agent + officer history (audit trail) for any case in their scope.
- **FR39:** KYC Analysts can commit EDD-outcome decisions that automatically enqueue the case for Team Lead approval.

### Portfolio & Reporting

- **FR40:** Chief Compliance Officers can view a minimal Portfolio Dashboard summarizing: cases processed, median case time, SLA breaches, risk-band distribution, and audit-readiness indicator for their tenant.
- **FR41:** Chief Compliance Officers can export a tenant-level summary (aggregated, non-PII) for a time-bounded cohort.

### Platform Integration (API)

- **FR42:** External systems (e.g., core banking) can submit new cases via authenticated REST API including customer metadata and document references.
- **FR43:** External systems can upload documents via presigned URLs or multipart streams.
- **FR44:** The platform emits authenticated webhooks to registered callbacks for case state changes and decision events.
- **FR45:** External systems can retrieve a case by ID per their API-consumer scope.
- **FR46:** Case creation is idempotent against a client-provided request ID.

### Identity, Access & Tenancy

- **FR47:** Users authenticate via tenant-configured SAML 2.0 or OIDC single sign-on.
- **FR48:** Role-based access control — KYC Analyst, Team Lead, CCO, Internal Auditor, Tenant Admin, API Consumer — is enforced at both API and UI layers with deny-by-default.
- **FR49:** All tenant data is isolated — no cross-tenant reads, writes, or queries are permitted by the platform.
- **FR50:** Tenant Admins (Future UI; MVP via runbook) can perform break-glass emergency read access with cryptographically-signed justification and ledger entry.
- **FR51:** The platform automatically signs users out after a configurable period of inactivity.

### Agent Configuration & Operations

- **FR52:** Tenant Admins (MVP: via scripted runbook) can configure the active screening vendor via a pluggable adapter interface.
- **FR53:** Tenant Admins (MVP: via scripted runbook) can configure jurisdiction rules, SAR templates, and document taxonomy.
- **FR54:** The platform supports feature flags per tenant to enable or disable individual agents and capabilities.
- **FR55:** Agent failures are isolated — a single agent failure does not cascade; the Case Supervisor retries or flags the case for human attention.
- **FR56:** External vendor integrations conform to contract-interface tests; swapping a vendor requires only the adapter implementation to change, not agent logic.

**Capability Contract:** This FR list is binding. UX designers, architects, and the epics/stories breakdown will implement exactly these capabilities — nothing less, nothing more without an explicit PRD update.

## Non-Functional Requirements

### NFR Summary

| Category | Relevant? | Source of detail |
|----------|:---------:|-------------------|
| Performance | ✓ | Domain Requirements → Technical Constraints → Performance table |
| Security | ✓ | Domain Requirements → Security (OWASP ASVS L2, TLS 1.3, AES-256, HSM) |
| Privacy & Data Protection | ✓ | Domain Requirements → Privacy & Data Handling |
| Availability & Reliability | ✓ | Extended below |
| Scalability | ✓ | Specified below |
| Accessibility | ✓ | Specified below |
| Observability | ✓ | Specified below |
| Compatibility | ✓ | Specified below |
| Reference-Implementation Quality (Path B) | ✓ | Specified below |
| Specific Thresholds (FR-referenced) | ✓ | Specified below |
| Compliance | ✓ | Domain Requirements → Compliance & Regulatory |

### Performance *(see Domain Requirements → Technical Constraints → Performance)*

Supplementary NFRs not in Domain section:

- **NFR-P1:** Keyboard-driven actions (j/k navigation, mode switch, ⌘K palette) respond within **50 ms p95** — fluent keyboard feel requires sub-frame feedback.
- **NFR-P2:** Cockpit panel expand/collapse renders within **150 ms p95** — no perceptible lag.
- **NFR-P3:** Cockpit supports simultaneous display of ≥ **50 UBO nodes** without interaction degradation.
- **NFR-P4:** Concurrent agent mesh execution for a single case scales to **all 8 MVP agents running in parallel** where dependencies permit, without resource contention causing p95 breach.

### Security *(see Domain Requirements → Technical Constraints → Security)*

Supplementary NFRs:

- **NFR-S1:** API rate limiting — per API key, per IP, per endpoint; default 100 req/min with burst 500, configurable per tenant.
- **NFR-S2:** Failed authentication attempts lock the account after 5 failures within 10 minutes; unlock via tenant admin or timed cooldown.
- **NFR-S3:** Dependency security — all production dependencies scanned weekly (Dependabot/Snyk); Critical + High CVEs resolved within SLA (Critical 48h, High 7 days).
- **NFR-S4:** Threat-model coverage — documented threat model covering agent mesh, ledger, screening vendor boundary, document upload, authentication; reviewed quarterly.
- **NFR-S5:** Penetration test — pre-pilot external pentest (by third party); findings triaged with Critical/High remediated before pilot launch.
- **NFR-S6:** LLM prompt security — prompt templates are version-controlled, peer-reviewed; runtime prompt injection guards (input sanitization + instruction containment) for all document-derived text.

### Availability & Reliability

- **NFR-A1:** MVP pilot SLO: **99.5% during business hours IST** (Mon–Fri, 09:00–19:00). Scheduled maintenance windows excluded; communicated ≥ 7 days in advance.
- **NFR-A2:** GA target: **99.9%** annual availability.
- **NFR-A3:** Disaster recovery: **RPO ≤ 1 hour**, **RTO ≤ 4 hours**.
- **NFR-A4:** Mean-time-to-recovery (MTTR) for P1 incidents: ≤ **2 hours**.
- **NFR-A5:** Agent failure blast radius: a single agent failure must not exceed one case's processing; Case Supervisor isolates, retries, or flags for human.
- **NFR-A6:** Ledger write is atomic — a partially-written ledger entry is never visible to readers or exports.
- **NFR-A7:** Graceful degradation on vendor outage — screening vendor downtime surfaces the reason in the cockpit and blocks case closure with a clear error; stale screening results are never rendered as current.

### Scalability

- **NFR-SC1:** MVP pilot target: **10 concurrent analysts**, **500 open cases**, **100 case ingestions per hour**.
- **NFR-SC2:** Architecture supports **10× horizontal scaling** within a tenant without code changes (target: 100 analysts, 5,000 open cases, 1,000 ingests/hr for a single tenant).
- **NFR-SC3:** Ledger growth is projected at ~10 MB / case (including agent traces and docs metadata, excluding document binaries); cold-storage tiering at 2 years keeps hot storage bounded.
- **NFR-SC4:** The design supports multiple tenants on shared infrastructure post-MVP; MVP is single-tenant per deployment, but isolation primitives (tenant_id in every query, per-tenant signing keys) are production-grade from day one.

### Accessibility

- **NFR-AC1:** Cockpit UI conforms to **WCAG 2.2 Level AA**. Regulated B2B banking context — assume screen-reader use by some officers.
- **NFR-AC2:** All primary officer actions are keyboard-accessible — no action is mouse-only. Required for compliance with NFR-AC1 and core to the product's keyboard-first design principle.
- **NFR-AC3:** Confidence-banded visual system uses **shape, position, and label in addition to color** — color-blind officers (≈ 8% of males) must distinguish all four bands without color.
- **NFR-AC4:** Color contrast ratios: ≥ 4.5:1 for body text, ≥ 3:1 for UI chrome and non-text indicators (WCAG AA).
- **NFR-AC5:** Focus indicators are persistent, high-contrast, and visible on every keyboard-navigable element.
- **NFR-AC6:** Localization — MVP ships English only; architecture supports i18n (externalized strings, locale-aware date/number formatting) from day one for future Hindi + regional Indian languages.

### Observability

- **NFR-O1:** All services emit structured OpenTelemetry traces; agent activity is enriched with case ID, agent ID, and case state.
- **NFR-O2:** Orchestrate-native traces (agent-as-tool invocations, HITL checkpoints, tool calls) are exported to the tenant's observability namespace alongside application traces.
- **NFR-O3:** Telemetry is PII-scrubbed at the collection layer — case IDs and agent IDs are safe; customer PII is not emitted to telemetry backends.
- **NFR-O4:** Per-tenant observability partitioning — a tenant's metrics, traces, and logs are not visible to other tenants via any observability UI.
- **NFR-O5:** Product telemetry dashboards for: case-time distribution, edit-rate, mode-usage, agent precision (sampled), NPS trend, SLA-breach rate, audit-readiness indicator.
- **NFR-O6:** Alerting: P1 alerts for ledger integrity failures, screening-vendor-down, auth service down, agent-runtime cascade; pages on-call within 1 minute of detection.

### Compatibility

- **NFR-CP1:** Browser support — latest 2 versions of Chrome, Edge, Firefox, Safari on desktop. No IE. No tablet/mobile browsers in MVP (mobile is Future).
- **NFR-CP2:** Operating system — runs on Windows 10+, macOS 12+, Ubuntu 22.04+.
- **NFR-CP3:** Minimum viewport — 1366 × 768 (standard bank-issue laptop). Optimized for 1920 × 1080 and 2560 × 1440.
- **NFR-CP4:** No native client required for MVP — browser-only access.

### Reference-Implementation Quality *(Path-B specific)*

Reflects the internal architectural intent — the codebase and architecture must be learnable and referenceable by other solution architects / developers building on IBM watsonx Orchestrate + ADK.

- **NFR-RI1:** **ADK pattern coverage.** The codebase demonstrates — with commentary — each of: supervisor/collaborator composition, agent-as-tool, Pydantic-contracted tools, HITL approval steps, background/scheduled agents (scaffolded even if Future), parallel meta-critic invocation (scaffolded), conversational agent with mesh-as-tools, Orchestrate-trace-backed audit.
- **NFR-RI2:** **Documentation.** Every agent has a README covering purpose, input/output schema, tool dependencies, and tested prompt templates. Every non-trivial design decision is captured in an ADR (architecture decision record).
- **NFR-RI3:** **Code quality.** Python code conforms to Ruff linting + typing with mypy; React code passes ESLint + TypeScript strict mode.
- **NFR-RI4:** **Test coverage.** Unit test coverage ≥ 80% on agent logic and tool adapters; integration tests for every agent contract boundary; end-to-end tests for the four canonical cockpit flows.
- **NFR-RI5:** **Reproducibility.** The codebase can be cloned and a local demo environment spun up in ≤ 30 minutes by a developer unfamiliar with the project, following the README only.
- **NFR-RI6:** **Pluggability proof.** Every vendor/jurisdiction adapter is accompanied by a second reference adapter (mock or alternative) that demonstrates swap viability — even if not activated in MVP.
- **NFR-RI7:** **Prompt-library discipline.** All LLM prompts live in version-controlled templates (Jinja or equivalent); no string concatenation of user data into prompts; tested with golden inputs.

### Specific Thresholds (FR-referenced)

FRs reference thresholds without specifying them; they live here:

- **NFR-T1: Undo window (referenced by FR23):** Committed decisions can be reverted within **120 seconds** of commit, after which the commit is sealed in the ledger.
- **NFR-T2: Session inactivity timeout (referenced by FR51):** **30 minutes** inactivity triggers automatic sign-out. Configurable per tenant within bounds [15 min, 60 min].
- **NFR-T3: Edit-rate target (referenced by FR27):** Product-level goal is ≥ **60%** of decisions satisfy (agent-drafted ≥ 80% AND officer-edited < 20%). Below this in pilot, the writing agent or UI needs iteration.
- **NFR-T4: Provenance coverage (referenced by FR8):** **100%** of rendered data points carry provenance metadata. Enforced by an automated UI test that asserts a provenance indicator on every rendered datum.
- **NFR-T5: Agent precision floors (referenced by success criteria):** Document Intelligence ≥ **95%** field extraction; UBO basic construction ≥ **95%** structural accuracy, measured on agreed corpus benchmarks.
- **NFR-T6: Break-glass justification length (referenced by FR50):** Break-glass access requires a rationale of ≥ **40 characters** before being permitted; rationale and reader identity are both signed into the ledger.

### Compliance *(see Domain Requirements → Compliance & Regulatory)*

No additional NFRs beyond the Domain Requirements section. Compliance posture — explainability floor, auditability floor, DPDP alignment, RBI/FIU-India support, pluggable multi-jurisdiction — is fully specified there.

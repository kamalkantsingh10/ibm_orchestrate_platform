# KYC Cockpit — Distillate

**Purpose:** Compressed project context for downstream LLM work (PRD, UX, architecture). Preserves decisions, constraints, and rationale; drops narrative.

---

## Identity
- **Product:** KYC Cockpit (working title)
- **Category:** Agentic KYC platform for banks
- **Positioning:** Officer-first agentic KYC — cockpit as moat, agent mesh as product
- **Stack:** IBM watsonx Orchestrate + Python + Agent Development Kit (ADK), custom React + FastAPI frontend
- **Primary user:** Priya persona — KYC Analyst at mid-size universal bank, 8–12 cases/day, retail + SME + refresh
- **Buyer:** Chief Compliance Officer / Head of Financial Crime at banks with 500K–10M accounts
- **Jurisdiction:** India (RBI / FIU-India) first; pluggable by design
- **Status:** Brief approved v1 on 2026-04-24

## Problem (compressed)
Banking compliance officers spend 2–5 hours per SME onboarding, manually stitching data across 4+ systems (KYC DB, core banking, screening, adverse media). Today's KYC platforms solve for throughput, turning investigators into clerks. Periodic refresh backlog, alert fatigue, and audit-trail anxiety compound.

## Opportunity (compressed)
Agentic AI for KYC is mature — Fenergo, Moody's, IBM Consulting KYC-AI, Genpact, Fulcrum Digital (FD Ryze), Lyzr, Akira.ai all ship agent-driven KYC. **But all of them bolt agents onto form-based case-management UIs.** Whitespace = officer-first cockpit experience with visible, collaboratable agent mesh.

## Core Product Insight
Agents are commoditizing. The defensible moat is the **human–agent interaction surface.** Officers want AI that explains and learns, not AI that decides silently.

## Six Design Principles
1. Agent work visible, not hidden
2. Every datum provenance-tagged
3. Decisions are sacred (distinct, audited, reversible-with-reason)
4. Keyboard beats clicks
5. Density gradient (dense cockpit → calm decision zone → zen writing)
6. Confidence is visual, not textual

## Agent Mesh (14 agents, 5 layers)

**L0 — Supervisor (1):** Case Supervisor
**L1 — Intake (3):** Document Intelligence · Identity Verification · Entity Verification
**L2 — Deep-Dive (5):** UBO Graph · Screening · Risk Scoring · Investigation · Writing
**L3 — Interaction (2):** Cockpit Chat · Decision Guardrail
**L4 — Background (3):** Perpetual KYC Watcher · Regulatory Intelligence · Meta-Critic

## Cockpit Anatomy (6 zones)
1. Queue Rail (L, 260px) — risk × SLA × continuity ordering
2. Case Canvas (C, fluid) — collapsible panels (identity, docs, screening, UBO, tx, timeline, log, ripple)
3. Agent Copilot Pane (R, 320px) — live activity feed + NL chat + reasoning-trace slide-out
4. Decision Zone (bottom of canvas) — pre-drafted rationale, 120s undo, confidence self-rating
5. Top Bar — ⌘K palette, env badge, notifications, mode switcher
6. Bottom Ribbon — agent pulse, SLA, quick actions

## Six Officer Modes
- Triage · Deep Investigation · Batch Refresh (Factory) · SAR/EDD Writing (Zen) · Regulator Lens · Training/Shadow
- Mode switch: ⌘+1 through ⌘+6

## Four Canonical Flows
- **A. SME Onboarding** (MVP demo flow)
- **B. Periodic Refresh** (pKYC — silent auto-close + delta review)
- **C. Adverse Media Alert** (investigation + guardrails + writing)
- **D. EDD on PEP** (story mode → narrative drafter → mobile senior approval)

## MVP Scope (4–6 weeks)
**"SME Onboarding Slice"**
- **Agents (8 of 14):** Case Supervisor · Document Intelligence · Entity Verification · UBO Graph (basic, no shell/nominee) · Screening (single vendor) · Risk Scoring · Writing (rationale + EDD only) · Cockpit Chat
- **Zones (4 of 6):** Queue · Canvas · Agent Copilot · Decision Zone
- **Modes (2 of 6):** Deep Investigation · EDD/SAR Writing
- **Viz:** UBO Canvas · Risk Score Breakdown · Screening Explainer
- **Output:** Case closure + Regulator Lens export + cryptographic audit ledger
- **Deferred:** Identity Verification (retail), Investigation Agent, Decision Guardrail, pKYC Watcher, Regulatory Intel, Meta-Critic, mobile, collaboration, training mode, factory mode, multi-jurisdiction SAR

## Flagship 6 Features (highest conviction)
1. Agent Copilot Pane (live mesh activity + NL chat + reasoning trace)
2. UBO Canvas + shell/nominee detector (drag-correct-and-teach)
3. EDD Story Mode + narrative drafter (edit-don't-author)
4. Perpetual KYC delta agent + silent auto-close
5. Regulator Lens + cryptographic audit ledger
6. Timeline with agent-drawn causality arrows

## Quick Wins (polish first)
Risk-score explainer (stacked bar) · Screening hit explainer (3-column card) · ⌘K command palette · Evidence bundle shelf · "Explain back to me" · Confidence-banded visual system (4 tiers)

## ADK / Orchestrate Mapping
| Mesh Concept | Orchestrate/ADK |
|---|---|
| Supervisor | Top-level `@agent` with collaborators |
| Specialists | Collaborator agents (agent-as-tool) |
| Tools (MCA, GST, screening, etc.) | ADK `@tool` functions in Python |
| Contracts | Pydantic schemas on boundaries |
| HITL checkpoints | Human-approval steps |
| Background agents | Scheduled / event-triggered |
| Meta-Critic | Parallel agent eval via supervisor |
| Cockpit Chat | Conversational agent with mesh as tools |
| Audit ledger | Orchestrate trace + signed event ledger |
| Frontend | React + FastAPI + Orchestrate APIs |

## Success Criteria
- Case time ≤ 15 min for SME onboarding (baseline: 2–5 hrs)
- Officer touch time ↓ ≥ 70%
- 100% decisions have agent-drafted rationale (edited, not authored)
- Regulator Lens export passes mock internal audit with zero remediation asks
- Officer NPS ≥ 40 from 10-analyst pilot
- ≥ 80% officers report "cockpit changes how I feel about the work" post-pilot

## Key Assumptions to Validate
1. **Officers prefer collaboration over automation** — "AI that explains and learns" beats "AI that decides." *Validate via 3–5 officer interviews.*
2. **Agent precision ≥ 95%** on document intelligence and UBO construction — below this, edit-mode collapses into rewrite-mode. *Validate with corpus benchmarks.*
3. **Cryptographic ledger satisfies regulators** — must pass actual RBI/FIU scrutiny, not cosmetic. *Validate via ex-regulator advisor or pilot regulator conversation.*

## Key Risks
1. Incumbent counter-moves (Fenergo, Moody's, IBM Consulting KYC-AI add cockpit UI) — mitigate with speed + design-as-DNA
2. Screening vendor lock-in — mitigate with pluggable interface from day one
3. Jurisdictional drift (India-first may not demo in US/EU) — mitigate with config-driven jurisdiction rules
4. Officer adoption friction (cockpit seen as surveillance not assistance) — mitigate with officer-in-design + confidence/fatigue as first-class signals

## Six Open Architecture Decisions (resolve before building)
1. **Screening vendor:** ComplyAdvantage | LSEG World-Check | Dow Jones | ABBYY
2. **Document AI stack:** IBM Document AI | Watson Discovery | custom
3. **HITL UX:** blocking agent graph vs. async notifications
4. **Jurisdictional scope:** India-only vs. multi-jurisdiction from day one (recommend: India-only, pluggable interfaces)
5. **Agent memory model:** per-agent episodic vs. shared case-state (recommend: shared, stateless-functional agents)
6. **Frontend:** React + FastAPI (real demo) vs. Streamlit (internal prototype)

## Competitive Snapshot
- **Fenergo** — MVP in QKS AI Maturity Matrix 2026; agentic AI for data sourcing, materiality, explainable decisioning
- **IBM Consulting KYC-AI** (AWS Marketplace) — 50%+ manual task automation via agents
- **Moody's pKYC** — Chartis category winner (2 years); 600M+ companies, 1.7B ownership links
- **JPMorgan in-house** — 90% productivity gain claim
- **Genpact Banking Analyst Suite** — multi-agent orchestrator + worker architecture
- **Fulcrum FD Ryze · Lyzr.ai · Akira.ai · Fintechera** — agentic KYC startups
- **SymphonyAI, NICE Actimize** — Forrester AML Wave leaders (rule/ML-heavy, less agent-native)
- **Oracle FCCM, SAS, Napier, Quantexa, Lucinity, ComplyAdvantage** — established AML/KYC vendors

## Recommended Next Steps
1. Officer interviews (3–5) to validate Assumption 1
2. Resolve 6 open architecture decisions (≈2-hour workshop)
3. PRD for SME Onboarding Slice (handoff to PM John via `bmad-agent-pm` → `CP`)
4. UX spike: wireframes for 4 MVP cockpit zones (via `bmad-create-ux-design`)
5. MVP build — 4–6 weeks
6. Pilot — 1–2 mid-size bank compliance teams

## Source Artifacts
- `Documentation/brainstorming/brainstorming-session-2026-04-24-0130.md` — full 214-idea session + research foundation + 18 sources
- `Documentation/brainstorming/brainstorming-summary-2026-04-24.md` — clustered handoff summary with agent mesh + ADK mapping
- `Documentation/planning-artifacts/product-brief.md` — 10-section product brief (approved v1)

## Facilitation Ledger (what decisions were made and why)
- **Persona locked as Priya** (intermediate KYC analyst, mid-size bank) because she represents ~70% of the officer workforce — ideas built for her scale up to seniors
- **Technique sequence chosen as D→B** (Day-in-the-Life → Cockpit Deep-Dive) because grounding in a real day produced concrete features before spatial design
- **MVP scoped to SME Onboarding only** because it's the richest single vertical — exercises UBO, document intelligence, screening disambiguation, EDD narrative in one flow
- **Positioning pivoted from "agentic KYC"** (claimed already) **to "officer-first agentic KYC"** after competitive sweep revealed Fenergo/IBM Consulting/Moody's etc. are already in the agentic-KYC space
- **Brief written as a real product brief, not a demo pitch** — user directive: "show off IBM Orchestrate but don't mention this in the brief; this is an example product we will build"

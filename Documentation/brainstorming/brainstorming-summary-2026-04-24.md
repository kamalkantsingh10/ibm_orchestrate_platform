# Agentic KYC Cockpit — Brainstorming Summary

**Date:** 2026-04-24
**Facilitator:** Mary (Business Analyst) with Kamal
**Full session doc:** [`brainstorming-session-2026-04-24-0130.md`](./brainstorming-session-2026-04-24-0130.md)

---

## The Opportunity

Build an **agent-driven KYC system for a bank** on **IBM watsonx Orchestrate + Python + Agent Development Kit (ADK)**, with a first-class banking-officer-facing UI that closely mirrors real officer workflows.

### Whitespace Identified in Existing Market

- Strong agent platforms exist (IBM watsonx Orchestrate + ABBYY, Fenergo, Appian, ServiceNow FSO)
- Strong UIs exist (traditional case-management platforms with rule engines)
- **Nobody has built a cockpit-grade officer UI on top of a visible, interactive agent mesh.** That's our product.

---

## Research Foundation

Six parallel web searches (April 2026) established the problem space. Key pain points from the KYC/AML officer literature:

1. **Manual document review** — 3–5 staff hours per customer, doesn't scale
2. **Swivel-chair syndrome** — context-switching across 4+ systems to decide one alert
3. **Alert overload / false-positive fatigue** — genuine red flags masked by noise
4. **Onboarding vs. compliance tension** — officer caught between RM speed and Compliance depth
5. **Periodic review backlogs** — 1/3/5-year refresh cycles done largely manually
6. **Audit-trail anxiety** — every decision must be defensible years later

Industry direction of travel: **periodic review → event-driven → perpetual KYC (pKYC)**.

See the session doc for the full source list (18 sources).

---

## Persona Anchor: Priya

> **Priya, 28, KYC Analyst at a mid-size universal bank.** 3 years experience. Handles retail + SME onboarding + periodic refresh. Reports to a Team Lead. Queue: 8–12 cases/day. Today's tools: core banking portal, 3rd-party screening tool, shared drive, Outlook, Excel.

Represents ~70% of the officer workforce; ideas built for her scale up to seniors.

---

## Ideation Output: 214 Ideas across 10 Themes

| # | Theme | Center of Gravity |
|---|---|---|
| T1 | Perpetual-KYC Paradigm | Calendar → event-driven shift |
| T2 | The Officer Cockpit (6 zones) | Physical workspace + spatial skeleton |
| T3 | Agent-Human Trust Layer | Legibility, confidence-banding, explainability |
| T4 | Document & Entity Intelligence | Docs→data, UBO, shell/nominee detection |
| T5 | Investigation Support | Risk scoring, timeline, screening explainer, typology |
| T6 | Regulatory Writing & Audit | SAR, Regulator Lens, immutable ledger |
| T7 | Officer Cognitive Design | Fatigue, focus, well-being, tempo limits |
| T8 | Power-User Superpowers | Keyboard, customization, collaboration, mobile |
| T9 | Agent Orchestration Mesh | Chaining, handoff, self-critique, macros |
| T10 | Continuous Learning & Training | Junior training, knowledge capture, replay |

---

## 🏆 Flagship 6 (High-Impact, High-Conviction)

1. **Agent Copilot Pane** — live agent activity + NL chat + reasoning trace. The differentiator.
2. **UBO Canvas + Shell/Nominee Detector** — force-directed graph with agent-correctable ownership structure.
3. **EDD Story Mode + Narrative Drafter** — conversational EDD capture; agent writes the 2-page memo for officer edit.
4. **Perpetual-KYC Delta Agent + Silent Auto-Close** — only show what changed; auto-close low-risk no-change refreshes.
5. **Regulator Lens + Immutable Audit Ledger** — one-click inspector view; cryptographically verifiable audit trail.
6. **Timeline with Causality Arrows** — two-track spine (customer + external events) with agent-drawn causality.

## ⚡ Quick Wins

1. Risk-score explainer (stacked-bar component breakdown)
2. Screening hit explainer (3-column what-matched card)
3. ⌘K command palette (does everything)
4. Evidence bundle shelf (auto-assembled, PDF-exportable)
5. "Explain back to me" (agent rephrases its reasoning for officer's rationale note)
6. Confidence-banded visual system (4 tiers)

## 💎 Breakthroughs (V2 / Wildcards)

1. Case Time-Machine (scrub any case back in time)
2. Agent Self-Critique meta-agent (agents reviewing agents)
3. Voice-Approve on mobile (Lead approvals from the car)
4. "Commit with reservation" (respects analyst uncertainty)
5. Banker's Desk Mode (skeuomorphic optional skin)
6. Live collaborative cursors (magical-when-it-hits)

---

## Six Design Principles for the Cockpit

1. **Agent work is visible, not hidden**
2. **Every datum is provenance-tagged**
3. **Decisions are sacred** (distinct, audited, reversible-with-reason)
4. **Keyboard beats clicks**
5. **Density gradient** (dense cockpit, calm decision zone, zen writing)
6. **Confidence is visual, not textual**

---

## Six Officer Modes

| Mode | Purpose | Key Trait |
|---|---|---|
| Triage | Rapid morning queue processing | Keyboard `j`/`k`/`x`/`d` |
| Deep Investigation | Default full cockpit | All panels available |
| Batch Refresh (Factory) | Throughput refresh work | `y`/`n`/`e` keyboard loop |
| SAR / EDD Writing (Zen) | Focused regulatory writing | Dark bg, minimal chrome, evidence dock |
| Regulator Lens | Audit-ready view | One-click export (PDF + JSON) |
| Training / Shadow | Junior learning + case replay | Redacted live-follow + replay |

Switch via `⌘+1` through `⌘+6`.

---

## 🎯 MVP Scope — "Agentic KYC Cockpit: SME Onboarding Slice"

**Timebox:** 4–6 weeks

| Dimension | MVP Scope | Deferred |
|---|---|---|
| Case types | SME onboarding only | Retail, periodic refresh |
| Cockpit zones | Queue, Canvas, Agent Copilot, Decision | Regulator Lens polish, Factory mode |
| Modes | Deep Investigation + SAR/EDD Writing | Triage, Factory, Training, Mobile |
| Viz | UBO Canvas + Risk Breakdown + Screening Explainer | Timeline causality, Ripple map |
| Output | Case closure + Regulator export + audit ledger | Multi-jurisdiction SAR |

**Rationale:** SME onboarding is the richest vertical slice — UBO graphs, document intelligence, screening disambiguation, EDD narrative all exercised in one flow. Wins the demo.

---

## Key Insights Earned

- **"Edit, don't author"** — the biggest time-savings come from agents drafting outputs for officer editing (emails, memos, SARs, rationale notes)
- **"Diff everything"** — deltas over absolutes, at every granularity
- **"Confidence-banded UX"** — proportional brain-spend by visual cue
- **"Blast-radius thinking"** — decisions ripple; agents map before analyst thinks
- **"Event-driven, not calendar-driven"** — perpetual KYC is the paradigm

---

## Agent Mesh Design (14 Agents across 5 Layers)

### Architecture

- **Layer 0 — Supervisor (1):** Case Supervisor Agent
- **Layer 1 — Intake (3):** Document Intelligence · Identity Verification · Entity Verification
- **Layer 2 — Deep-Dive (5):** UBO Graph · Screening · Risk Scoring · Investigation · Writing
- **Layer 3 — Interaction (2):** Cockpit Chat · Decision Guardrail
- **Layer 4 — Background (3):** Perpetual KYC Watcher · Regulatory Intelligence · Meta-Critic

### Mapping to IBM watsonx Orchestrate + ADK

| Mesh Concept | Orchestrate / ADK Primitive |
|---|---|
| Supervisor | Top-level `@agent` with collaborators |
| Specialists | Collaborator agents invoked agent-as-tool |
| Tools (MCA, GST, screening APIs) | ADK `@tool` functions in Python |
| Contracts | Pydantic schemas on tool/agent boundaries |
| HITL checkpoints | Human-approval steps in agentic workflows |
| Background agents | Scheduled / event-triggered agents |
| Meta-Critic shadow-runs | Parallel agent evaluation |
| Cockpit Chat | Conversational agent with mesh as tools |
| Audit ledger | Orchestrate trace + signed event ledger |
| Officer UI | Custom React + Python FastAPI middle-tier |

### MVP Agent Subset (SME Onboarding, 4–6 weeks)

Ship 8 agents: Supervisor · Doc Intelligence · Entity Verification · UBO Graph (basic) · Screening (single vendor) · Risk Scoring · Writing (rationale + EDD only) · Cockpit Chat.

Defer 6: Identity Verification · Investigation · Decision Guardrail · pKYC Watcher · Regulatory Intel · Meta-Critic.

### Four Canonical Flows

- **Flow A — SME Onboarding:** the MVP demo flow
- **Flow B — Periodic Refresh (pKYC):** silent auto-close + delta review
- **Flow C — Adverse Media Alert:** investigation + guardrails + writing
- **Flow D — EDD on PEP:** story mode + narrative drafting + mobile senior approval

### Open Architecture Decisions

1. Screening vendor (ComplyAdvantage / LSEG / Dow Jones / ABBYY)
2. Document AI stack (IBM Document AI / Watson Discovery / custom)
3. HITL UX — blocking vs. async checkpoints
4. Jurisdictional scope — India-only MVP with pluggable interfaces recommended
5. Agent memory — shared case-state vs. per-agent episodic (shared recommended)
6. Frontend — React + FastAPI + Orchestrate recommended for real demo

---

## Recommended Next Steps

1. **Resolve the 6 open architecture decisions** (above) — 1–2 hour workshop
2. **Product Brief** — use Flagship 6 + MVP scope + Agent mesh as input (skill: `bmad-product-brief`)
3. **UX design spike** — low-fi wireframes of Zones 1–4 for SME onboarding flow (skill: `bmad-create-ux-design`)
4. **Technical research** — IBM watsonx Orchestrate + ADK capability deep-dive against MVP agent list (skill: `bmad-technical-research`)
5. **Architecture pass** — solution design locking agent contracts and flows (skill: `bmad-create-architecture`)
6. **Epics & Stories** — break MVP into implementable user stories (skill: `bmad-create-epics-and-stories`)

# Product Brief — KYC Cockpit

**Working title:** KYC Cockpit
**Tagline:** *Where compliance officers pilot an agent mesh instead of fighting forms.*
**Date:** 2026-04-24
**Author:** Kamal Singh (with Mary, BA)
**Status:** Approved v1 (2026-04-24)

---

## 1. The Problem

Banking compliance officers are the hidden labor of financial trust. A single SME onboarding case consumes 2–5 hours of expert human time: pulling data from four or more systems, verifying entity registration, unwrapping beneficial ownership, screening every party, assessing risk, and drafting a decision the bank can defend to a regulator years later. Periodic refresh adds a continuous backlog. Adverse media alerts and regulatory change generate constant noise.

Today's KYC platforms solve for *throughput*. Officers get tickets, queues, and forms. They become clerks managing cases rather than investigators making decisions. The tools fight them instead of fighting for them.

## 2. The Opportunity

Agentic AI has moved from research demo to production reality. Multi-agent systems can now handle document intake, entity resolution, UBO unwrapping, screening disambiguation, and narrative drafting at scale. Fenergo, Moody's, IBM Consulting, Genpact, and startups like Fulcrum Digital and Lyzr are all shipping agent-driven KYC.

But every one of them repeats the same mistake: **they bolt agents onto traditional case-management UIs.** The officer still lives in forms and tabs. Agent decisions arrive as finished work for *review*, not as live work for *collaboration*. Audit logs replace transparency. Throughput replaces craft.

This creates a clear market gap: **an officer-first platform where the agent mesh is the product, and the cockpit is the interface.**

## 3. The Product

**KYC Cockpit** is an agentic KYC platform built on IBM watsonx Orchestrate, Python, and an Agent Development Kit, with a dedicated officer-facing cockpit UI.

**Under the hood** — a mesh of 14 specialist agents. A Case Supervisor orchestrates. Intake agents handle documents, identity, and entity verification. Deep-dive agents build UBO graphs, run screening, score risk, investigate adverse media, and draft narratives. Interaction agents power natural-language collaboration and decision guardrails. Background agents run continuous perpetual-KYC monitoring. A meta-critic agent silently audits quality.

**Above the hood** — a cockpit interface that makes the mesh legible. Officers see a live agent activity feed, interrogate any decision with a "why?" click, correct agent mistakes that the mesh learns from, and commit decisions in a dedicated Decision Zone with pre-drafted rationale and confidence self-rating. Six purpose-built modes — Triage, Deep Investigation, Factory Refresh, EDD Writing, Regulator Lens, and Training — match the analyst's current cognitive task.

**The result** — a platform where officers make more decisions, better, faster, with stronger defensibility, while the bank can demonstrate AI-governed compliance to a regulator at the click of a button.

## 4. Target Users and Buyer

**Primary user:** The KYC Analyst at mid-size universal banks — handles 8–12 cases per day across retail and SME onboarding, works across four or more systems today, reports to a Team Lead, accountable to audit.

**Secondary users:**
- Compliance Leads reviewing and approving cases
- Chief Compliance Officers owning the regulatory narrative
- Relationship Managers who need case-status visibility for customer conversations

**Buyer:** Chief Compliance Officers and Heads of Financial Crime at banks with 500K–10M customer accounts — large enough to have dedicated compliance operations, small enough to feel the pain acutely. Secondary buyer segment: Tier-1 banks wanting to augment existing case management without a full rip-and-replace.

## 5. Differentiation

| Today's KYC Platforms | KYC Cockpit |
|---|---|
| Agents bolted onto form-based UIs | Agents and cockpit co-designed |
| Officer reviews agent output | Officer collaborates with agent mesh |
| "Black-box" AI with exportable logs | Live agent activity feed + reasoning traces |
| One UI for all case work | Six modes matched to analyst cognitive state |
| Compliance-as-throughput | Compliance-as-craft |
| Audit trail via log export | One-click Regulator Lens + cryptographic ledger |

The defensible moat is not the agents themselves — it is the **human–agent interaction surface.** Agents are increasingly commoditized; the experience of collaborating with them is not.

## 6. MVP Scope (4–6 weeks)

**"The SME Onboarding Slice"** — one vertical flow, end-to-end, from document upload to committed decision.

**Ships:**
- 8 of the 14 agents: Case Supervisor · Document Intelligence · Entity Verification · UBO Graph · Screening · Risk Scoring · Writing · Cockpit Chat
- 4 of the 6 cockpit zones: Queue · Case Canvas · Agent Copilot Pane · Decision Zone
- 2 of the 6 modes: Deep Investigation · EDD/SAR Writing
- Flagship visualizations: UBO Canvas · Risk Score Breakdown · Screening Explainer
- Case closure with Regulator Lens export and cryptographic audit ledger

**Defers to V2:** retail onboarding, perpetual KYC refresh mode, mobile companion, training/shadow mode, collaborative multi-user cursors, multi-jurisdiction SAR.

**Rationale:** SME onboarding is the richest single vertical — it exercises UBO graphs, document intelligence, screening disambiguation, and EDD narrative drafting in one flow. The most compelling evidence of product value in the smallest buildable scope.

## 7. Success Criteria

**Product:**
- Time-to-decision on an SME onboarding case: **≤ 15 minutes** (industry baseline: 2–5 hours)
- Officer touch time reduced **≥ 70%** on the onboarding flow
- **100%** of committed decisions carry agent-drafted rationale that the officer edited (not authored)
- Regulator Lens export passes a mock internal audit review with zero remediation asks

**User:**
- Officer NPS **≥ 40** from a 10-analyst pilot cohort
- **≥ 80%** of officers report the cockpit "changes how I feel about the work" in post-pilot interviews

## 8. Key Assumptions to Validate

1. **Officers want agent collaboration, not agent automation.** The cockpit bets that analysts prefer "AI that explains and learns" over "AI that decides." *Validate via 3–5 compliance officer interviews before MVP.*
2. **Agent accuracy is good enough for edit-don't-author.** Document intelligence and UBO construction must hit ≥95% precision. Below that, "edit" collapses into "rewrite," and the time-savings argument breaks. *Validate with early document corpus benchmarks.*
3. **The audit story holds up to a regulator.** Cryptographic ledger and Regulator Lens must be more than cosmetic. *Validate via early conversation with a friendly regulator contact or an ex-regulator advisor.*

## 9. Key Risks

1. **Incumbent counter-moves.** Fenergo, Moody's, and IBM Consulting could ship cockpit UIs on top of their agent stacks. *Mitigation: speed to market; the officer-centric design philosophy as durable product DNA, not a feature.*
2. **Screening vendor lock-in.** Single-vendor integration is simpler for MVP but creates long-term dependency. *Mitigation: design screening interface pluggable from day one, even if only one vendor is wired up.*
3. **Regulatory jurisdiction drift.** KYC rules vary by country. MVP scoped to India (RBI/FIU-India) may not demo well to US/EU prospects. *Mitigation: India-first but jurisdictional rules isolated as config, not hardcoded logic.*
4. **Officer adoption friction.** Even the best cockpit faces change-management resistance if the analyst sees it as "surveillance" rather than "assistance." *Mitigation: officer involvement in design from day one; cockpit explicitly models officer confidence and fatigue as first-class signals.*

## 10. Next Steps

1. **User research:** 3–5 compliance officer interviews to validate collaboration-over-automation assumption
2. **Architecture decisions:** lock screening vendor, document AI stack, HITL UX model, jurisdictional approach, agent memory model, and frontend choice (see companion artifact: brainstorming-summary-2026-04-24.md, "Open Architecture Decisions")
3. **PRD:** full product requirements document for the SME Onboarding Slice
4. **UX design spike:** low-fidelity wireframes for the four MVP cockpit zones
5. **MVP build:** 4–6 week implementation
6. **Pilot:** 1–2 mid-size bank compliance teams

---

## Appendix — Source Artifacts

- `Documentation/brainstorming/brainstorming-summary-2026-04-24.md` — clustered themes, flagship features, 14-agent mesh, 4 canonical flows, open architecture decisions
- `Documentation/brainstorming/brainstorming-session-2026-04-24-0130.md` — full 214-idea brainstorming session with research foundation and source citations

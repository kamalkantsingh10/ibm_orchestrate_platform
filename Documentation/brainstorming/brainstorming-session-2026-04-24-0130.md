---
stepsCompleted: [1, 2, 3, 4]
inputDocuments: []
session_topic: 'Agent-based KYC system for a bank, built on IBM Orchestrate with Python + ADK — strong UI, rich features, closely mirroring real banking officer needs'
session_goals: 'Generate a wide, divergent pool of ideas for KYC agents, officer-facing UI, features, and workflows — to feed into a product brief / architecture'
selected_approach: 'user-driven: D (Day-in-the-Life) then B (Officer Cockpit UI deep-dive)'
techniques_used: ['Day-in-the-Life Walkthrough (Priya, KYC Analyst)', 'Officer Cockpit UI Deep-Dive']
ideas_generated: 214
context_file: ''
session_active: false
workflow_completed: true
---

# Brainstorming Session Results

**Facilitator:** Mary (Business Analyst) — with Kamal
**Date:** 2026-04-24

## Session Overview

**Topic:** Agent-based KYC system for a bank, built on IBM Orchestrate with Python + Agent Development Kit (ADK). The solution must have a strong banking-officer-facing UI, rich features, and closely mirror real banking officer workflows.

**Goals:** Generate a wide, divergent pool of ideas — agent decomposition, officer UX, feature surface area, risk/compliance angles, integrations, edge cases — to feed downstream product brief / PRD / architecture work.

### Context Guidance

_No project-context.md found. Working from user-provided constraints: IBM Orchestrate, Python, ADK, banking officer persona._

### Session Setup

_Fresh session initialized. User provided topic in activation turn; proceeding with user-driven approach (web-research-grounded divergence)._

---

## Research Foundation (2026-04-24)

### Part 1 — Banking Officer Pain Points (cross-referenced from 6 sources)

1. **Manual document review** — officers manually check IDs, utility bills, corporate docs, UBO certs. ~3–5 staff hours per customer; scales poorly.
2. **Swivel-chair syndrome** — data stitched from KYC DB + core banking + screening + adverse media platforms; hours lost to context-switching.
3. **Alert overload / false-positive fatigue** — genuine red flags masked by noise.
4. **Onboarding-vs-compliance tension** — RM wants speed, Compliance wants depth; officer is the friction point.
5. **Periodic review backlogs** — corporate/commercial re-KYC on 1/3/5 year cycles is mostly manual.
6. **Audit-trail anxiety** — every decision must be defensible and reconstructable years later.

### Part 2 — What a Modern KYC System Consists Of

Five concentric layers:

| Layer | What Happens | Officer Touchpoint |
|---|---|---|
| CIP | Identity verification — ID docs, selfie/liveness, address proof | Exception queue |
| CDD | Risk-scoring, sanctions/PEP/adverse-media screening, UBO capture | Standard review queue |
| EDD | Source of funds/wealth, PEP relationships, pattern analysis | Investigator workbench + senior approval |
| Ongoing Monitoring | Transaction monitoring, behavioral analytics, trigger detection, refresh scheduling | Alert triage queue |
| Reporting & Case Mgmt | SAR/STR drafting and filing, regulatory reports, audit trail | Case management workbench |

**Core case lifecycle:** Create → Triage → Assign → Investigate → Decide → Remediate → Close → Audit.

**Industry direction:** periodic review → event-driven refresh → perpetual KYC (pKYC).

### Part 3 — What IBM Orchestrate + Agents Already Do

- ABBYY + watsonx Orchestrate: document intake → validation → routing with compliance monitoring.
- Multi-agent continuous KYC pattern: Agent A pulls public data → Agent B scores risk → Agent C files updates.
- Domain agents in watsonx Orchestrate for financial approvals, compliance checks, case routing.

**Whitespace:** a banking-officer-first *cockpit UI* on top of agent networks — most tools today are either strong agent platforms with weak UX, or strong UX with rule engines underneath.

### Sources

- [AML and KYC compliance guide for banks — ShadowDragon](https://shadowdragon.io/blog/aml-and-kyc-compliance-guide-for-banks/)
- [KYC in Banking 2026 — iDenfy](https://idenfy.com/blog/kyc-in-banking/)
- [Top 5 KYC Challenges — iDenfy](https://www.idenfy.com/blog/kyc-challenges/)
- [KYC and AML Compliance in 2026 — Finologee](https://finologee.com/kyc-and-aml-compliance-in-2026-what-financial-institutions-need-to-know/)
- [KYC Process: The Complete Guide — Appian](https://appian.com/learn/topics/know-your-customer-process/kyc-guide)
- [KYC in Banking Explained — Appian](https://appian.com/learn/topics/know-your-customer-process/kyc-in-banking-explained)
- [CIP, CDD, EDD — Middesk](https://www.middesk.com/blog/cip-cdd-edd)
- [CDD vs EDD — Persona](https://withpersona.com/blog/cdd-vs-edd-whats-the-difference)
- [KYC Case Management — Know Your Customer](https://knowyourcustomer.com/kyc-case-management/)
- [ServiceNow FSO KYC Onboarding](https://www.servicenow.com/community/fso-articles/unlocking-efficiency-transform-onboarding-and-kyc-in-banking/ta-p/3404553)
- [ABBYY + IBM watsonx.ai Orchestrate — KYC Automation](https://www.abbyy.com/blog/abbyy-and-ibm-watsonx-ai-orchestrate-transform-kyc-automation-at-enterprise-scale/)
- [IBM watsonx Orchestrate — new agentic workflows](https://www.ibm.com/new/announcements/new-agentic-workflows-and-domain-agents-in-ibm-watsonx-orchestrate)
- [Agentic AI in Banking — Deloitte](https://www.deloitte.com/us/en/insights/industry/financial-services/agentic-ai-banking.html)
- [AML Case Management & SAR Filing — Persona](https://help.withpersona.com/articles/3PQYXlkWnkxRyWmAijjVux/)
- [Event-driven KYC refresh — Finextra](https://www.finextra.com/blogposting/31323/event-driven-kyc-refresh-why-periodic-review-fails-operationally)
- [Perpetual KYC — ComplyAdvantage](https://complyadvantage.com/insights/perpetual-kyc/)
- [Perpetual KYC Guide — Quantexa](https://www.quantexa.com/resources/perpetual-kyc-guide/)
- [KYC Refresh — EY](https://www.ey.com/en_us/insights/financial-services/kyc-refresh-effective-risk-based-program)

---

## Technique 1: Day-in-the-Life Walkthrough

### Persona: Priya
28, KYC Analyst at a mid-size universal bank. 3 years experience. Handles retail + SME onboarding + periodic refresh. Reports into a Team Lead. Typical queue 8–12 cases/day. Tools today: core banking portal, third-party screening tool, shared drive, Outlook, Excel.

### Her Day (stops used for ideation)

- 8:30 — Login & dashboard check
- 9:00 — Queue triage & team huddle
- 9:30 — Retail onboarding (savings account)
- 10:30 — SME onboarding (private ltd, UBO)
- 11:30 — Adverse media alert on existing customer
- 12:30 — Lunch
- 1:30 — Periodic refresh batch (3 cases)
- 3:00 — EDD on a PEP
- 4:30 — SAR/STR drafting
- 5:30 — EOD handoff

### Ideas Generated (100)

**Morning Dashboard (8:30)**
1. [UI] Morning briefing pane — agent-generated 60-second summary
2. [Agent] Overnight watcher agent — checks adverse media / sanctions deltas against active book
3. [UI] Risk-weighted queue — ordered by risk × SLA × completion-proximity
4. [Automation] Resume-where-you-left-off
5. [UI] Cold-case surfacing with reason-for-stuck
6. [Integration] One-click SSO across core banking, screening, doc vault
7. [Human] Personal load indicator — anti-burnout signal
8. [Agent] Voice-playable briefing for morning commute
9. [Edge] Shift-handoff ledger surfaced per case
10. [UI] Regulatory "weather report" tagged to affected cases

**Queue Triage & Huddle (9:00)**
11. [Agent] Huddle-listener agent — transcribes standup, tags action items to cases
12. [Agent] Regulator-circular agent — summarizes new circulars, tags affected cases
13. [UI] Team-view panel showing Lead's priority overrides
14. [Automation] Workload rebalancer — suggests reassignment before Lead does
15. [UI] "What's new since yesterday" per-case timeline diff
16. [Human] Trainee shadow mode for juniors
17. [Agent] Peer-comparison — "Arjun closed a similar case last week, here's how"
18. [Edge] Conflict-of-interest auto-check
19. [UI] Queue complexity heatmap for energy pacing
20. [Agent] SLA-forecast agent

**Retail Onboarding (9:30)**
21. [Agent] Address-reconciliation agent with confidence score
22. [UI] Side-by-side doc viewer with color-coded field matches
23. [Automation] One-click benign-variant resolution
24. [Agent] Customer-comms drafter for clarification emails
25. [UI] Character-level diff visualizer
26. [Integration] Utility-bill freshness check via provider API
27. [Agent] Silent deepfake/forgery detector
28. [Human] Confidence-banded UX visualization
29. [Edge] Multi-document conflict graph
30. [Agent] Explainability generator for every decision

**SME Onboarding (10:30)**
31. [Agent] Entity-verification agent (MCA/GST/tax DB parallel lookup)
32. [Agent] UBO graph builder with auto ≥25% threshold highlighting
33. [UI] Interactive UBO canvas with drag-correct + agent training
34. [Agent] Shell-company detector
35. [Agent] Common-name disambiguator
36. [UI] "Explain this hit" screening overlay
37. [Automation] Director cross-reference across portfolio
38. [Agent] Adverse media summarizer (paragraph + source trail)
39. [Integration] Real-time GST verification
40. [Agent] Document-completeness agent + RM-request drafter
41. [UI] Progress ribbon across case
42. [Edge] Nominee-director pattern detector
43. [Agent] Risk-score explainer (component-level reasoning)
44. [Human] Informal second-opinion button
45. [UI] Collapsible investigation log for audit

**Adverse Media Alert (11:30)**
46. [Agent] Materiality classifier
47. [Agent] Source credibility ranker
48. [UI] Compare-to-profile diff panel
49. [Agent] Timeline builder (customer activity + external events)
50. [Agent] Precedent-finder — similar historical decisions
51. [Automation] Auto-draft restriction memo + customer comms
52. [Human] Escalation pre-flight with 3 clarifying questions
53. [Edge] Related-party ripple check
54. [UI] Decision confidence slider
55. [Agent] Continuous-watch upgrade offer

**Periodic Refresh Batch (1:30)**
56. [Agent] Perpetual-KYC delta agent (change-only view)
57. [Automation] Silent auto-close for no-change low-risk refreshes
58. [UI] Queue with delta preview
59. [Agent] Customer-facing refresh bot (WhatsApp/SMS)
60. [Integration] Government-registry change feeds
61. [Automation] Consent-based continuous monitoring
62. [Agent] Stale-data decay scoring
63. [UI] Factory-mode workbench for repetitive batches
64. [Human] Fatigue tracker
65. [Agent] Trigger-explanation agent
66. [Edge] Dormant-account special refresh flow
67. [Agent] Bulk risk recalibration on rule change

**EDD on a PEP (3:00)**
68. [Agent] Source-of-funds corroboration agent
69. [Agent] PEP relationship grapher
70. [UI] EDD story mode (conversational → structured doc)
71. [Agent] EDD narrative drafter
72. [Automation] Senior-approval pre-pack with Lead's preferred format
73. [Agent] Jurisdiction-aware PEP treatment rules
74. [UI] Decision-tree visualizer for PEP rules
75. [Human] Four-eyes handoff with 60-second audio summary
76. [Agent] Ongoing-PEP watcher post-approval
77. [Integration] Election-commission / appointments feed
78. [Edge] Retroactive PEP sweep across book
79. [Regulatory] "Regulator lens" mode — one-click inspector view
80. [Training] Learning-case library from closed EDD cases

**SAR/STR Drafting (4:30)**
81. [Agent] SAR narrative drafter in jurisdictional templates
82. [UI] Regulator red-flag editor (flags vague language, missing 5Ws)
83. [Agent] Evidence bundler matched to narrative order
84. [Integration] Regulator-portal auto-submit + ack retrieval
85. [Agent] Typology-precedent finder
86. [UI] Diff-only review mode for Lead
87. [Agent] Tipping-off safety net on outbound comms
88. [Regulatory] Immutable, tamper-evident audit ledger
89. [Agent] Post-SAR follow-up scheduler
90. [Human] Emotional-load indicator
91. [Mobile] Secure mobile Lead approval flow
92. [Edge] Multi-jurisdiction SAR generator

**EOD Handoff (5:30)**
93. [Agent] EOD auto-recap of the day
94. [UI] Continuity note per case
95. [Automation] Kill-the-Excel — first-class filtered views
96. [Agent] Leave-coverage handoff composer
97. [Human] Reflection prompt for process improvement
98. [Agent] Night-shift orchestrator of background work
99. [UI] "Why am I here tomorrow?" preview
100. [Training] Daily micro-learning nudge to teach the knowledge base

---

## Technique 2: Officer Cockpit UI Deep-Dive

### Design Posture

Three fused mental models: **trading terminal** (density + keyboard-first), **detective's evidence wall** (spatial + chronological), **pilot cockpit** (attention on off-nominal + engaged autopilot).

### Six Design Principles

1. Agent work is visible, not hidden
2. Every datum is provenance-tagged
3. Decisions are sacred (distinct, audited, reversible-with-reason)
4. Keyboard beats clicks
5. Density gradient — dense cockpit, calm decision zone, zen writing
6. Confidence is visual, not textual

### Ideas 101–214 (Cockpit Design)

**Zone 1 — Queue Rail**
101. Risk × SLA × continuity ordering
102. Rich queue item (name + type + risk bar + SLA + delta chip)
103. Cold-case chip with stuck-reason
104. j/k keyboard nav without leaving current case
105. Peek mode — 400ms hover ghost preview
106. Tabs: Mine | Team | Lead-flagged | Cold | Awaiting customer
107. Drag-to-teammate handoff with Lead-approval dialog
108. Micro agent-status dot per case

**Zone 2 — Case Canvas**
109. ⌘+⇧+P panel commander
110. Per-case-type learned panel defaults
111. z-key zoom-out to panel-title strips
112. ⌘+\ split canvas for related parties

**Zone 3 — Agent Copilot Pane**
113. Live agent activity feed with click-to-jump
114. Context-aware agent chat (NL, case-scoped)
115. Reasoning-trace slide-out per agent event
116. Always-visible "Pause all agents" emergency button
117. Agent runbook picker
118. Detach pane to second monitor

**Zone 4 — Decision Zone**
119. Persistent, visually distinct zone
120. Four primary verbs color-distinct
121. Pre-drafted rationale (edit-not-author)
122. Confidence self-rating slider
123. Commit dialog with full transparency
124. 120-second Undo pill with reason capture
125. "Commit with reservation" option

**Zone 5 — Top Bar**
126. ⌘K command palette does everything
127. Environment badge color-distinct
128. Notification center for overnight findings
129. Mode switcher
130. Teammate presence dots

**Zone 6 — Bottom Ribbon**
131. System-wide agent pulse strip
132. Per-case SLA + progress
133. Quick actions (screenshot, voice, hotkey toggle)

**Modes**
134–136. Triage Mode — rapid queue processing
137. Deep Investigation Mode (default full cockpit)
138–141. Batch Refresh / Factory Mode — keyboard-driven throughput
142–145. SAR/EDD Writing Zen Mode
146–148. Regulator Lens Mode
149–150. Training / Shadow + Replay Mode
Mode switch via ⌘+1 through ⌘+6

**Agent-Human Interaction Patterns**
151. Ambient suggestions, never modal interruptions
152. Four-tier confidence-banded visuals (≥95 / 80-94 / 60-79 / <60)
153. "Why?" affordance on every agent element
154. Cheap disagreement (per-branch re-eval on Modify)
155. Agent handoff breadcrumbs
156. Suggested-action chip in decision zone (never auto-commit)
157. "Explain back to me" for Priya's own rationale note
158. Long-running agent contract (upfront duration)
159. Interruption etiquette (pause animations when typing)
160. One-click "Undo the agent" with reason
161. Agents can ask Priya questions (learn from answer)

**Power Patterns**
162. Agent macros (saved sequences)
163. Parallel agent comparison (two scorers side-by-side)
164. Agent self-critique by meta-agent
165. "Agent off" mode per case (training/audit)

**Information Visualization**

*UBO Canvas*
166. Force-directed graph with ownership-% node sizing
167. Verification-state color code
168. % labeled + dashed edges for unverified
169. Click-node doc + screening slide-out
170. Drag-to-re-parent with agent recomputation
171. ≥25% effective-owner toggle
172. Timeline scrubber for historical structure

*Risk Score*
173. Horizontal stacked bar per factor
174. Hover for sub-calculation
175. "What-if" slider for stress-testing
176. Delta indicator with cause

*Timeline*
177. Two-track spine (customer + external events)
178–180. Customer events / external events / pinch-zoom granularity
181. Agent-drawn causality arrows

*Document Diff*
182. Character-level text diff
183. Pixel-level image doc diff with spatial highlight
184. Field-extraction overlay with confidence shading

*Evidence Bundle*
185. Persistent evidence shelf
186. Agent-populated, Priya-curated
187. Signed PDF bundle export

*Screening Explainer*
188. What-matched / source / what-doesn't-match card
189. Auto-excluded matches collapsed with reason

*Related-Party Ripple*
190. Connected-party node graph
191. Risk-trend color-tint per party
192. Blast-radius preview before restrictive actions

**Superpowers**
193. Contextual `?` hotkey overlay per mode
194. Vim-profile opt-in keybindings
195. ⌘K palette does everything
196. Saveable workspace layouts per case type
197. Draggable dashboard widgets
198. Color-blind-safe first-class palette
199. Dark mode redesigned not auto-inverted
200. Live cursors for shared cases
201. Inline @mention notes as actionable tasks
202. Voice notes with auto-transcription
203. Post-it stickies for casual marginalia
204. Full keyboard navigation + screen-reader a11y
205. Focus mode (pink noise + mute)
206. Active fatigue indicator
207. Tempo limits on rapid decisions
208. One-click "show to auditor"
209. Cryptographic audit-ledger viewer
210. Case time-machine scrub
211. Slim mobile companion for Lead approvals
212. Biometric + device-bound encryption + shoulder-surf blur
213. Voice-approve on mobile
214. Wildcard: optional skeuomorphic Banker's Desk Mode

---

## Idea Organization and Prioritization

### Thematic Clusters (10 themes over 214 ideas)

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

### Prioritization

**Flagship 6 (high impact + whitespace + agent-fit):**
1. Agent Copilot Pane (Zone 3)
2. UBO Canvas + Shell/Nominee Detector
3. EDD Story Mode + Narrative Drafter
4. Perpetual-KYC Delta Agent + Silent Auto-Close
5. Regulator Lens + Immutable Audit Ledger
6. Timeline with Causality Arrows

**Quick Wins (small scope, high polish):**
- Risk-score explainer (#43)
- Screening hit explainer (#36)
- ⌘K command palette (#195)
- Evidence bundle shelf (#185–187)
- "Explain back to me" (#157)
- Confidence-banded visual system (#152)

**Breakthroughs (V2 / wildcards):**
- Case Time-Machine (#210)
- Agent Self-Critique meta-agent (#164)
- Voice-Approve on mobile (#213)
- "Commit with reservation" (#125)
- Banker's Desk Mode (#214)
- Live collaborative cursors (#200)

**Defer / drop for MVP:**
- Skeuomorphic skin
- Ambient pink-noise focus mode
- Live cursors (multiplayer infra)
- Multi-jurisdiction SAR (single-jurisdiction first)

### MVP Scope Recommendation

**"The Agentic KYC Cockpit: SME Onboarding Slice"** (4–6 weeks):
- Case types: SME onboarding only
- Cockpit zones: 1 (Queue), 2 (Canvas), 3 (Agent Copilot), 4 (Decision)
- Modes: Deep Investigation + SAR/EDD Writing
- Viz: UBO Canvas + Risk Breakdown + Screening Explainer
- Output: case closure + Regulator Lens export + audit ledger
- Out of scope: retail, refresh, mobile, collaboration, training, factory mode

---

## Session Summary and Insights

### Key Achievements
- Generated 214 structured ideas across 10 themes
- Grounded in 2026 research on KYC/AML officer pain points + IBM Orchestrate whitespace
- Identified 6 flagship features, 6 quick wins, 6 breakthroughs
- Scoped a 4–6 week MVP vertical slice (SME onboarding)

### Key Insights Earned
1. **"Edit, don't author"** — most time-saving comes from agents drafting outputs (emails, memos, SARs, rationale notes) for analyst editing
2. **"Diff everything"** — deltas over absolutes, at every granularity (field, doc, case, day)
3. **"Confidence-banded UX"** — proportional brain-spend by visual cue, not text-reading
4. **"Blast-radius thinking"** — every decision ripples across connected entities; agent maps before analyst thinks
5. **"Event-driven, not calendar-driven"** — perpetual KYC is the paradigm; periodic review is legacy
6. **The whitespace** — cockpit UI that sits *on top of* an agent mesh, with the mesh visible and interactive. No existing tool nails this combo.

### Creative Breakthroughs
- **Agent Copilot Pane** — genuinely new primitive for officer tooling
- **Sacred Decision Zone** with confidence-self-rating + 120s undo
- **Six Modes** — especially Factory Mode and Regulator Lens
- **Perpetual-KYC Delta Agent** — treats refresh as continuous diff, not periodic audit
- **Case Time-Machine + Cryptographic Audit Ledger** — future-proof regulator story

### Session Reflections
The D → B flow worked: grounding in a real officer's day produced concrete features (not generic AI-slop), then the cockpit deep-dive gave them a spatial home. Research up-front kept us from reinventing table stakes. Rotating creative domains every 10 ideas (per anti-bias protocol) visibly increased diversity.

### Session Status
- Workflow: Complete
- Ideas generated: 214
- Techniques used: Day-in-the-Life + Officer Cockpit Deep-Dive (user-driven sequence)
- Next recommended step: Agent decomposition (Step 3 of the session)

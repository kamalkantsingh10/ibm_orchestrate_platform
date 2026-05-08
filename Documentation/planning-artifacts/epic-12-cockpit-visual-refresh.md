---
status: draft
date: 2026-05-08
author: Kamal
supersedes_design_tokens_in:
  - apps/cockpit-ui/tailwind.config.ts
  - apps/cockpit-ui/src/index.css
relates_to:
  - Documentation/planning-artifacts/epics.md
  - Documentation/planning-artifacts/ux-design-specification.md
  - Documentation/implementation-artifacts/sprint-status.yaml
preserves_FRs:
  - All FRs from prd.md (this epic is purely visual/IA refinement; no functional change)
---

# Epic 12 — Cockpit Visual Refresh (Tier-1 Private Bank Aesthetic)

## Why this epic exists

The cockpit currently renders the demo's spec-defined components but reads as a polished prototype, not as a workstation an officer at a tier-1 institution would sit in front of for eight hours a day. Specifically:

- The cockpit content sits inside a centered max-width column with empty grey gutters on either side at 1440px+ viewports — wasting the workstation real estate the spec promises
- The case-detail H1 is display-poster sized and dominates above-the-fold real estate that should be doing work
- The queue rail shows three undifferentiated fields per row (name · age · "Ready") — yet the queue's whole purpose (FR1) is risk × SLA × continuity ordering
- The Documents panel is heading-per-document with double provenance icons, reading more like a checklist than tabular evidence
- The Agent Copilot pane stacks 8 agents flatly; 5 of 8 say "No activity yet" — the cognitive load is the noise, not the signal
- The Risk Score panel buries its hero number under a donut and below 800px of scroll, then duplicates the decomposition twice
- The chrome (header + footer) does not advertise the cockpit's actual capabilities (mode switcher, ⌘K, ledger state, current case)
- The "Investigation" pill exists in the header with no peers, hinting at modes that are never visible
- Approvals and Regulator Lens routes bottom out at the literal text "Story 10-1 will populate this"

This epic resets the visual language to one that would feel native inside a tier-1 private-banking environment: full-viewport workstation chrome, restrained palette, type-led hierarchy, tabular density where officers expect it, and panels that earn every pixel.

**Reference aesthetic (not to be cloned, but to calibrate against):** professional financial workstations — Bloomberg Anywhere, Linear's command surfaces, Stripe Atlas's document chrome, the print-grade typography of high-end financial reports. Restraint over decoration. Numbers in tabular figures. Color reserved for signal.

## Hard constraint — full-viewport workstation

The cockpit **must occupy the entire browser viewport**: 100vw × 100vh, no centered max-width container around the shell, no decorative gutters. Internal panels flex within the full width via a CSS grid (queue rail · main canvas · agent rail). Min supported viewport is 1366 × 768 (PRD-defined); above that, the canvas and rails grow proportionally. This is a load-bearing decision that informs Story 12.1's shell layout — every other story builds on it.

## Non-goals

- **No functional changes.** Every existing FR remains satisfied. Behaviors of shipped stories are preserved end-to-end; this epic only re-skins and re-lays-out.
- **No backend changes.** No new endpoints, no schema migrations, no contract drift.
- **No new agent work.** Agent registry, ADK integration, ledger format are untouched.
- **No re-architecture of the macro IA.** The three-pane shell (queue rail · canvas · agent rail) stays; this epic refines within those zones and makes them fill the screen.
- **Not a brand exercise.** No logo, no name, no marketing surface. Internal cockpit only.

## Design principles

1. **Full viewport, always.** No centered column, no decorative gutter. The cockpit is the workstation.
2. **Restraint over decoration.** Color is signal. Hairline 1px borders, charcoal-on-off-white, one accent for true alerts.
3. **Type-led hierarchy.** A 7-step type ramp (display → micro) replaces ad-hoc `text-2xl/3xl`. Numbers are tabular figures everywhere.
4. **Tabular density where it belongs.** Documents, risk decomposition, queue lists become tables. Whitespace is reserved for the canvas and decision zone.
5. **Document-grade case canvas.** The case is a regulator-grade document — title block · quick facts · section nav · sectioned body · decision drawer. Print-comprehensible if exported.
6. **Cockpit chrome that earns its pixels.** The top bar carries identity, navigation, search, and mode. The bottom bar carries ledger and connection state. Neither is empty.
7. **Quiet motion.** Active agents pulse subtly; sections settle. No bouncy springs.
8. **Confidence as shape and position, not just hue.** The 4-tier confidence primitive is preserved; this epic tightens its execution so it works in monochrome.

## Story List (5 stories)

| # | Story | Surface area | Estimate |
|---|---|---|---:|
| 12.1 | Foundation: full-viewport shell, design tokens, chrome, mode switcher | `tailwind.config.ts`, `index.css`, `__root.tsx`, new chrome components | 2.0 d |
| 12.2 | Queue rail + case canvas IA — tabular density and document-grade structure | `QueueRail/`, `cases.$caseId.tsx`, new title-block + section-nav components | 2.5 d |
| 12.3 | Documents panel + Risk panel rebuild — tabular evidence, banker hero | `DocumentsPanel/`, `RiskPanel/`, `RiskScoreBar/` | 2.0 d |
| 12.4 | Agent activity strip + UBO refresh — horizontal rail, expand mode, sober nodes | `AgentCopilotPane/`, `UBOCanvas/`, `UBOPanel/` | 2.0 d |
| 12.5 | Decision drawer + Approvals/Regulator scaffolds | new `DecisionDrawer/`, `routes/approvals.tsx`, `routes/regulator-lens.tsx` | 1.5 d |
| **Total** | | | **~10 d** |

Per-story detail lives in `Documentation/implementation-artifacts/12-1-...` through `12-5-...`.

## Story sequencing

1. **12.1** — foundation; everything else assumes the new tokens and the full-viewport shell
2. **12.2** — IA refactor; depends on 12.1
3. **12.3** + **12.4** — independent panel rebuilds; can land in parallel after 12.2
4. **12.5** — depends on 12.2 (decision drawer slots into the canvas chrome)

## Risks

- **Token migration breaks shipped components.** Mitigation: 12.1 keeps deprecated blue tokens aliased to graphite for one release window; remove only after manual visual QA across all routes.
- **IA refactor (12.2) collides with in-flight Epic 6 / 7 work.** Mitigation: gate 12.2 on Epic 6's screening explainer reaching `review` status before merge.
- **Aesthetic subjectivity.** Mitigation: a single visual-QA review pass per story against the design principles above; no story closes without that pass logged in the story file.
- **Type/font hosting.** Pick Google-hosted Source Serif 4 + Inter Tight as defaults; revisit if a brand exercise picks a different pair later.

## Out of scope (explicit)

- Dark mode (deferred)
- Mobile / responsive below 1366px (PRD says desktop only)
- Accessibility audit (no regressions, but no new audit work in this epic)
- Localization / i18n (PRD-deferred for demo scope)
- Logo / brand mark design (placeholder monogram only)

## Splice plan

This file is a standalone epic draft. Once approved, the splice into `Documentation/planning-artifacts/epics.md` is:

1. Add `Epic 12 — Cockpit Visual Refresh` to the active scope summary table at the top of `epics.md`, bringing the active epic count to 11 and story count to ~70
2. Append the per-story detail (12.1–12.5) to `epics.md` after Epic 10's stories, mirroring the Given/When/Then format used elsewhere
3. Add `epic-12: backlog` and `12-1` … `12-5` entries to `Documentation/implementation-artifacts/sprint-status.yaml`

The five story files in `Documentation/implementation-artifacts/12-1-...` through `12-5-...` are created alongside this draft.

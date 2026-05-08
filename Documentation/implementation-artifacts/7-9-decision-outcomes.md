# Story 7.9: Decision outcomes (approve / decline / approve-with-conditions / escalate-to-EDD)

Status: review

## Story

As a KYC Analyst,
I want a `OutcomeSelector` UI component in the Decision Zone (Story 7-1) that lets me pick one of four mutually-exclusive outcomes — `approve`, `decline`, `approve_with_conditions`, `escalate_to_edd` — with `approve_with_conditions` revealing a chip-style conditions editor (≥ 1 condition required, max 10, each ≤ 200 chars), and `escalate_to_edd` showing a small "this will go to Team Lead approval" hint, plus the formal `DecisionOutcome` Pydantic Literal in `packages/contracts/` that Stories 7-7 / 7-1 / 7-3 depend on,
So that the demo's commit beat fully represents the four-state decision space (FR24), the `approve_with_conditions` UX supports the J1 Vora narrative ("approve with enhanced monitoring 6mo"), and `escalate_to_edd` flags the case for downstream Lead approval (Epic 10 Story 10-1) while remaining a valid commit in this epic.

## Scope note (2026-04-29 demo re-scope)

Story preserved verbatim from bank-buyer Story 7.15. The `escalate_to_edd` auto-enqueue for Team Lead approval is partially deferred: Story 10-1 (Lead Approval Queue) consumes the same outcome to surface the case in the Lead's queue. This story only commits the outcome to the ledger; queue surfacing is Epic 10's responsibility.

| Bank-buyer scope (original 7.15) | Demo replacement |
|---|---|
| Four outcomes | **Same.** |
| `approve_with_conditions` requires ≥ 1 condition | **Same.** Conditions max 10, each ≤ 200 chars (added — bank-buyer didn't bound). |
| `escalate_to_edd` auto-enqueues for Team Lead approval (Epic 8 Story 8.7) | **Demo: Epic 10 Story 10-1 surfaces escalated cases.** This story commits the outcome; queue-side rendering is Story 10-1. |
| Tenant-scoped persistence | **Single-tenant.** |

What survives: **the four-outcome contract Literal/StrEnum, conditions-as-chips UI, validation (≥ 1 for `approve_with_conditions`), the small EDD escalation hint, integration with Story 7-1's Decision Zone footer.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`, `architecture.md#Format Patterns` (snake_case wire enum), `prd.md#Functional Requirements` FR24.

## Acceptance Criteria

1. **AC1 — Formal `DecisionOutcome` contract.**

    Replace Story 7-7's draft Literal with a refined definition. **If Story 7-7 has merged with `DecisionOutcome` as a Literal, swap to a `StrEnum`** — same wire format, more ergonomic in Python:

    ```python
    # packages/contracts/src/contracts/decision.py

    from enum import StrEnum

    class DecisionOutcome(StrEnum):
        APPROVE = "approve"
        DECLINE = "decline"
        APPROVE_WITH_CONDITIONS = "approve_with_conditions"
        ESCALATE_TO_EDD = "escalate_to_edd"
    ```

    The Pydantic models in Story 7-7 (`CommitDecisionRequest.outcome`, `Decision.outcome`, `OfficerDecisionCommittedPayload.outcome`, `DecisionSealedPayload.outcome`) update from `Literal[…]` to `DecisionOutcome`. Pydantic's wire format remains identical (`"approve"`, `"decline"`, etc.) — `use_enum_values=True` is **NOT** needed; Pydantic v2 serializes `StrEnum` by value automatically.

    Tests verify backward-compat:
    * Existing JSON payloads with `"outcome": "approve"` still round-trip.
    * `DecisionOutcome("approve") == "approve"` (StrEnum equivalence).
    * Invalid string `"foo"` rejected with `ValidationError`.

2. **AC2 — Re-export from `packages/contracts/src/contracts/__init__.py`** (alphabetical).

3. **AC3 — `OutcomeSelector` component at `apps/cockpit-ui/src/components/cockpit/DecisionZone/OutcomeSelector.tsx`.**

    ```typescript
    import type { components } from '@/api-types';

    type DecisionOutcome = components['schemas']['DecisionOutcome'];   // 'approve' | 'decline' | 'approve_with_conditions' | 'escalate_to_edd'

    export interface OutcomeSelectorProps {
        outcome: DecisionOutcome | null;
        conditions: string[];
        onOutcomeChange: (o: DecisionOutcome | null) => void;
        onConditionsChange: (c: string[]) => void;
        disabled?: boolean;          // true when case state is pending_seal / committed
    }

    export function OutcomeSelector(props: OutcomeSelectorProps): JSX.Element { ... }
    ```

    Renders as a small grouped UI:
    * **Outcome dropdown** (Radix Select) — 4 options. Labels (visible to user, not the wire value):
        * `approve` → "Approve"
        * `decline` → "Decline"
        * `approve_with_conditions` → "Approve with conditions"
        * `escalate_to_edd` → "Escalate to EDD"
    * **Conditions editor** — visible only when `outcome === 'approve_with_conditions'`. A chip-style input: each existing condition rendered as a removable chip (`bg-zinc-100 px-2 py-0.5 rounded text-xs` + `<X>` button); a text input below for adding new conditions; Enter or comma submits the input as a new chip. Max 10 chips; the input disables when at max.
    * **Escalation hint** — visible only when `outcome === 'escalate_to_edd'`. Small italicized line below the dropdown: `<p className="text-xs text-zinc-500 italic mt-1">This case will appear in the Team Lead's approval queue after sealing.</p>`.

4. **AC4 — Conditions editor specifics.**

    * Each chip displays its full text on hover via tooltip (Radix Tooltip).
    * Empty conditions are rejected — the input clears unsubmitted whitespace; chips are never blank.
    * Max length per condition: 200 chars. The input enforces via `maxLength={200}`.
    * Pasting multi-line content splits on newlines and creates one chip per line, up to the max-10 cap.
    * Removing a chip is via the `<X>` button OR via Backspace when input is empty (boring UX convention from chip-style inputs).
    * Order matters (officer can re-order via drag — **demo cut**: no reorder, just append-only). Tests verify append behavior.

5. **AC5 — Replace the stub in `DecisionZone.tsx`.**

    Story 7-1 § AC8 instructed devs to render a stub when 7-9 hadn't landed. This story removes the stub and imports `OutcomeSelector`:

    ```tsx
    import { OutcomeSelector } from './OutcomeSelector';
    // ...
    <OutcomeSelector
        outcome={draft.outcome}
        conditions={draft.conditions}
        onOutcomeChange={draft.setOutcome}
        onConditionsChange={draft.setConditions}
        disabled={isReadOnly}
    />
    ```

    Update Story 7-1's stub TODO comment removal in the same PR.

6. **AC6 — Disabled state.**

    When `disabled === true` (case state `pending_seal` or `committed`), the outcome dropdown is non-interactive (Radix's `disabled` prop), the conditions editor's chips render as plain text (no remove buttons), the input is hidden, and the escalation hint stays visible (informational).

7. **AC7 — Backend: `escalated_to_edd` does NOT auto-transition the case to `escalated` state.**

    Important divergence from a naive reading: the `case.state` enum has `ESCALATED` for cases that hit a blocker during intake (Story 5-1 / 6-2 use this). `escalate_to_edd` is a **decision outcome** — the case still flows through `pending_seal → committed` like any other outcome. The Team Lead's queue (Story 10-1) reads `decisions.outcome` to find escalated cases; it does NOT read `cases.state == 'escalated'`. Document this in `decision_service.py`'s `commit_decision` docstring + this story's pitfalls.

8. **AC8 — Tests at `packages/contracts/tests/test_decision.py` (extend Story 7-7's tests).**

    * `DecisionOutcome("approve")` returns the enum member; `DecisionOutcome("foo")` raises.
    * `CommitDecisionRequest(outcome="approve", ...)` accepts both string and enum-member.
    * Pydantic JSON dump emits `"outcome": "approve"` (lowercase string), not `"OUTCOME.APPROVE"`.
    * `approve_with_conditions` + empty conditions → ValidationError.
    * `approve` + non-empty conditions → still valid (conditions are silently allowed but ignored downstream — or rejected? **Pick rejected** to keep contracts tight: any outcome other than `approve_with_conditions` requires `conditions == []`. Add a model_validator).

    Updated `model_validator`:

    ```python
    @model_validator(mode="after")
    def _conditions_match_outcome(self):
        if self.outcome == DecisionOutcome.APPROVE_WITH_CONDITIONS and not self.conditions:
            raise ValueError("approve_with_conditions requires at least one condition")
        if self.outcome != DecisionOutcome.APPROVE_WITH_CONDITIONS and self.conditions:
            raise ValueError(f"{self.outcome.value!r} must not include conditions")
        return self
    ```

9. **AC9 — Tests at `apps/cockpit-ui/src/components/cockpit/DecisionZone/OutcomeSelector.test.tsx`.**

    * Renders 4 outcome options.
    * Selecting `approve_with_conditions` reveals the conditions input.
    * Selecting `escalate_to_edd` shows the escalation hint.
    * Selecting `approve` after `approve_with_conditions` clears the previous conditions (callback invoked with `[]`).
    * Adding a condition via Enter creates a chip.
    * Removing a chip via X click fires the callback with the updated array.
    * Max 10 chips — input disabled at 10.
    * Empty/whitespace-only input rejected (no chip created).
    * `disabled=true` → dropdown non-interactive, input hidden, chips read-only.
    * Multi-line paste splits into chips up to the max-10 cap.

10. **AC10 — Tests at `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.test.tsx` (extend Story 7-1's tests — replace the stub-related tests).**

    * Outcome dropdown is the real OutcomeSelector (snapshot or specific assertion).
    * Selecting an outcome updates `useDecisionDraft.setOutcome`.
    * Commit button enable/disable behavior unchanged from Story 7-1.

11. **AC11 — TS types regenerate.**

    `make contracts` writes `DecisionOutcome` (and the unchanged sibling types from Story 7-7) into `apps/cockpit-ui/src/api-types.ts`. Verify via grep.

12. **AC12 — `make lint && make test` clean.** Net new test count: ≥ 5 in `test_decision.py` (extend), ≥ 10 in `OutcomeSelector.test.tsx`, ≥ 1 in `DecisionZone.test.tsx` (replace stub).

13. **AC13 — End-to-end manual demo.**

    Open Vora's case (state `decision_ready`):
    1. Decision Zone footer shows `OutcomeSelector` with no outcome selected; Commit disabled.
    2. Click outcome dropdown → 4 options appear.
    3. Select "Approve" → Commit button enables.
    4. Select "Approve with conditions" → conditions input appears below; Commit button disables (no conditions yet).
    5. Type "enhanced monitoring 6mo" + Enter → chip appears; Commit enables.
    6. Type "re-review on screening delta" + Enter → second chip; max-10 status visible (e.g., "2 / 10").
    7. Click `<X>` on first chip → removed; only second chip remains.
    8. Add 8 more chips; input disables at 10.
    9. Switch outcome to "Approve" → conditions cleared (or stay? Per AC9 they clear; verify visually).
    10. Switch to "Escalate to EDD" → escalation hint appears, conditions input disappears, Commit enabled.
    11. Press `⌘+Enter` → POST fires with `outcome=escalate_to_edd, conditions=[]`; case → `pending_seal`.
    12. After Story 10-1 (Lead Approval Queue) ships, switch to Lead role via user-switcher → Vora's case appears in the Lead's queue.
    13. macOS Reduce Motion ON → outcome dropdown opens without animation; chip add/remove instant.

## Tasks / Subtasks

- [x] **Task 1 — `DecisionOutcome` StrEnum + validator extension** (AC: #1, #2, #7, #8, #11)
  - [x] Subtask 1.1 — Convert Story 7-7's Literal to StrEnum in `packages/contracts/src/contracts/decision.py`.
  - [x] Subtask 1.2 — Update `_conditions_match_outcome` validator to reject conditions on non-`approve_with_conditions` outcomes.
  - [x] Subtask 1.3 — Re-export from `__init__.py`.
  - [x] Subtask 1.4 — `make contracts`.
  - [x] Subtask 1.5 — Extend `packages/contracts/tests/test_decision.py` (≥ 5 cases).

- [x] **Task 2 — `OutcomeSelector` component** (AC: #3, #4, #6, #9)
  - [x] Subtask 2.1 — `apps/cockpit-ui/src/components/cockpit/DecisionZone/OutcomeSelector.tsx`.
  - [x] Subtask 2.2 — Conditions chip-style input.
  - [x] Subtask 2.3 — Escalation hint.
  - [x] Subtask 2.4 — Disabled-state styling.
  - [x] Subtask 2.5 — `OutcomeSelector.test.tsx` (≥ 10 cases).

- [x] **Task 3 — Replace stub in DecisionZone** (AC: #5, #10)
  - [x] Subtask 3.1 — Import `OutcomeSelector`; remove stub.
  - [x] Subtask 3.2 — Update Story 7-1's stub TODO comment.
  - [x] Subtask 3.3 — Adjust `DecisionZone.test.tsx` (≥ 1 case replacement).

- [x] **Task 4 — Verification** (AC: #12, #13)
  - [x] Subtask 4.1 — `make lint && make test` green.
  - [x] Subtask 4.2 — Manual demo per AC13.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Format Patterns`] enum values snake_case on the wire — `approve_with_conditions`, not `approveWithConditions`.
* [Source: `architecture.md#Naming Patterns`] Python classes PascalCase (`DecisionOutcome`); enum members upper-case (`APPROVE`).
* [Source: `architecture.md#Frontend Architecture`] Radix Select for the dropdown; Radix Tooltip for chip hover.
* [Source: `prd.md#Functional Requirements` FR24] commit one of four outcomes.
* [Source: `prd.md#Functional Requirements` FR36-39] approval workflow surface (Lead's queue is Epic 10's responsibility).

### Critical pitfalls

1. **`StrEnum` with Pydantic v2 serializes by value.** No `model_config = {"use_enum_values": True}` needed; Pydantic v2 handles `StrEnum` natively. Tests AC8 verify wire format.

2. **`escalate_to_edd` is NOT the same as `case.state == 'escalated'`.** The state is a flow-control marker for blocked intake; the outcome is a decision verb. Conflating them would make an Epic 10 Lead's queue display intake-blocked cases alongside EDD-escalated cases — wrong audience for both. AC7 + the `decision_service.py` docstring lock the distinction.

3. **Conditions must be cleared when switching away from `approve_with_conditions`.** Otherwise the validator (AC8) raises ValidationError on commit ("approve must not include conditions"). The `OutcomeSelector` clears conditions on outcome change. Tests AC9 verify.

4. **Max 10 conditions is arbitrary.** No FR / NFR mandates 10. The cap exists to prevent UI degradation (a long list of chips wraps awkwardly) and Pydantic abuse. If a real case needs 11+ conditions, raise the cap; for the demo, 10 is generous.

5. **Don't add a `notes` field on conditions.** A condition is a single string (e.g., "enhanced monitoring 6mo"). Bank-buyer scope might layer structured fields on each condition (deadline, owner, escalation policy); demo doesn't.

6. **Backward compat for Story 7-7's Literal-to-StrEnum swap.** Pydantic's wire format is identical; existing tests should pass without change. If any test compares `outcome == "approve"` (string equality) → still passes (StrEnum is a str subclass). If any test does `outcome.value == "approve"` → still passes. Verify by running the full test suite after the contract change.

7. **Radix Select's accessibility is correct.** Don't roll a custom dropdown; the demo's marble-grade UX expects keyboard nav (↑/↓, Home/End, type-ahead) which Radix Select provides for free.

8. **Multi-line paste splitting** is a small ergonomic win — copy-pasting from a list works. Tests AC9 verify; if it adds complexity, ship without and document as a polish backlog item.

9. **Tooltip on long chips** — if a condition is 195 chars, the chip wraps awkwardly. The Radix Tooltip on hover shows the full text; the chip itself can truncate via `max-w-[200px] truncate`. Tests verify truncation.

10. **`DecisionOutcome` enum members are UPPERCASE in Python; the Literal in Story 7-7 was lowercase strings**. Pydantic accepts both forms in its discriminator: `DecisionOutcome.APPROVE` (member) or `"approve"` (value). Tests AC8 verify both. **Document the convention** in the contract module's docstring.

### Story dependencies

* **Strict prereqs:** Story 7-7 (`DecisionOutcome` Literal — this story refines), Story 7-1 (DecisionZone host — replaces stub).
* **Read by:** Story 7-3 (Writing agent's prompt may reference outcomes — N/A in v1, future), Story 8-7 / 10-1 (Lead approval queue reads `decisions.outcome == 'escalate_to_edd'`).

### Project Structure Notes

This story creates:
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/OutcomeSelector.tsx`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/OutcomeSelector.test.tsx`

This story modifies:
- `packages/contracts/src/contracts/decision.py` — Literal → StrEnum; tightened `_conditions_match_outcome`
- `packages/contracts/src/contracts/__init__.py` — public exports
- `packages/contracts/tests/test_decision.py` — extend
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.tsx` — imports real OutcomeSelector; removes stub
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.test.tsx` — adjust
- `apps/cockpit-ui/src/api-types.ts` — regenerated

This story does NOT create:
- The Lead approval queue (Epic 10 Story 10-1)
- A separate `escalated_to_edd` case state (intentionally; the outcome surfaces via Lead's queue, not via state)

### References

- [Source: `epics.md#Epic 7` § Story 7.15] verbatim
- [Source: `architecture.md#Format Patterns`]
- [Source: `architecture.md#Naming Patterns`]
- [Source: `architecture.md#Frontend Architecture`]
- [Source: `prd.md#Functional Requirements`] FR24, FR36-39
- [Source: `7-7-post-decision-endpoint-no-signature-verify.md`] Decision contracts to refine
- [Source: `7-1-decision-zone-component-with-tiptap-editor.md`] stub to replace

### Demo verification protocol

Per AC13. The Lead-queue verification (step 12) requires Story 10-1 — defer that step until Epic 10 ships.

If any step fails, the bug is in this story; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 7.9 drafted. DecisionOutcome StrEnum (refining Story 7-7's draft Literal), tightened conditions/outcome validator (conditions must match approve_with_conditions exclusively), OutcomeSelector with chip-style conditions editor + escalation hint, replaces Story 7-1's stub. EDD escalation does NOT auto-transition case state; surfaces via Lead queue (Epic 10). |

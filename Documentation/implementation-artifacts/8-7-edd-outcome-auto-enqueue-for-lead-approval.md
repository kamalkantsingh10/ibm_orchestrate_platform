# Story 8.7: EDD outcome auto-enqueue for Lead approval

Status: backlog

## Story

As a KYC Analyst,
I want to commit an EDD-outcome decision and have it automatically appear in my Team Lead's approval queue,
So that the workflow is friction-free (FR39).

## Scope note

This is a small wiring story that closes the loop between Decision Authoring (Epic 7) and Multi-Role Approvals (Epic 10). When a decision is committed with `outcome ∈ {escalate_to_edd, approve_with_conditions}`:
1. The case state transitions to `pending_lead_approval`
2. A `case.escalated_for_approval` ledger entry is appended
3. An SSE event is broadcast on the existing single-worker channel (Story 4-6)

The Team Lead approval queue (Story 10-1) is the consumer. **Epic 10 may not have shipped yet when this story lands** — that is fine and explicitly accepted: this story produces the upstream signal correctly so that whenever 10-1 lands, it has data to render.

**Demo-scope notes:**

- **No Ed25519 signing** on the ledger entry (per scope addendum) — `actor_id` carries the user ID, no signature.
- **Single-worker SSE** (Story 4-6) is the broadcast mechanism. No Redis pub/sub.

**Dependencies:**
- Story 7-7 (POST /decision endpoint — the entry point that triggers state transition)
- Story 7-9 (Decision outcomes — defines `escalate_to_edd` and `approve_with_conditions` as valid outcome values)
- Story 2-1 (case state machine — receives the new `pending_lead_approval` state)
- Story 3-1 (JSON ledger writer)
- Story 4-6 (SSE single-worker channel)

## Acceptance Criteria

1. **AC1 — `pending_lead_approval` is a valid case state.** `apps/cockpit-api/src/cockpit_api/models/case.py` (or wherever Story 2-1's state enum lives) gains `pending_lead_approval` as a valid `CaseState`. The state-machine transition table allows `decision_ready → pending_lead_approval` (triggered by qualifying decision commit) and `pending_lead_approval → approved | declined` (triggered by Team Lead approval — the Epic 10 transitions; declared here, consumed there).

2. **AC2 — Decision-service triggers transition on qualifying outcomes.** `apps/cockpit-api/src/cockpit_api/services/decision_service.py.commit_decision(...)` is extended:
   - If `decision.outcome == 'escalate_to_edd'`: transition state to `pending_lead_approval`
   - If `decision.outcome == 'approve_with_conditions'` AND `case.risk_band in {'high', 'medium_high'}`: transition state to `pending_lead_approval`
   - Otherwise: no state-machine bump (case follows its existing post-decision state — typically `approved` / `declined`)
   - The transition is part of the same transaction as the decision commit (atomic)

3. **AC3 — `case.escalated_for_approval` ledger entry.** When the transition fires, a ledger entry is appended via the Story 3-1 writer:
   - `entry_type: "case.escalated_for_approval"`
   - `case_id: <case_id>`
   - `actor_type: "officer"`
   - `actor_id: <user_id of analyst who committed>`
   - `payload: { decision_id, outcome, prior_state: 'decision_ready', new_state: 'pending_lead_approval', escalation_reason: <derived: 'edd' | 'high_risk_conditions'> }`
   - The Pydantic schema lives in `packages/contracts/src/contracts/ledger.py`

4. **AC4 — SSE event broadcast.** Immediately after the ledger entry is persisted, the existing SSE single-worker channel (Story 4-6) broadcasts an event:
   - `event: case.escalated_for_approval`
   - `data: { case_id, decision_id, outcome, escalation_reason, timestamp }`
   - Subscribers (the Team Lead's approvals route, when Story 10-1 lands) react by re-fetching their queue.

5. **AC5 — Cockpit-ui acknowledges escalation in the UI.** When the analyst commits a qualifying decision, the post-commit confirmation in the existing DecisionZone (Story 7-1 + 7-6 seal animation) shows an additional line:
   - `Sent to <Team Lead name> for approval` if a team lead is configured for this analyst
   - `Sent to Team Lead approval queue` if no specific lead is configured
   - The team lead resolution uses the existing `IdentityProvider` (Story 1-6) — for the demo, the single Team Lead user `Rohan Mehta` is the constant target.

6. **AC6 — Idempotency.** Committing the same decision twice (network retry / double-click) results in only one state transition and one ledger entry. The decision-commit endpoint already enforces this for the decision itself (Story 7-7); this story extends the idempotency guard to cover the escalation entry — no duplicate `case.escalated_for_approval` rows.

7. **AC7 — Backend tests.** `apps/cockpit-api/tests/test_decision_escalation.py`:
   - `commit_with_escalate_to_edd_transitions_to_pending_lead_approval`
   - `commit_with_approve_with_conditions_high_risk_transitions_to_pending_lead_approval`
   - `commit_with_approve_with_conditions_low_risk_does_not_transition`
   - `commit_with_approve_outcome_does_not_transition`
   - `escalation_ledger_entry_appended_with_correct_payload_shape`
   - `sse_event_broadcast_on_escalation` (use the existing SSE test harness from 4-6)
   - `double_commit_does_not_duplicate_escalation_entry`

8. **AC8 — Frontend test.** `DecisionZone.test.tsx::shows_sent_for_approval_message_on_qualifying_outcomes`

9. **AC9 — `make lint` + `make test` clean.**

## Tasks / Subtasks

- [ ] **Task 1 — Add `pending_lead_approval` to the case state enum** (AC: #1)
  - [ ] Update transition table in the state-machine module
- [ ] **Task 2 — Extend `commit_decision`** (AC: #2)
  - [ ] Compute escalation predicate
  - [ ] Bump state in same transaction
- [ ] **Task 3 — Pydantic `EscalatedForApprovalEntry`** (AC: #3)
- [ ] **Task 4 — Append ledger entry** (AC: #3)
- [ ] **Task 5 — SSE broadcast** (AC: #4)
  - [ ] Reuse Story 4-6's broadcast utility
- [ ] **Task 6 — UI confirmation message** (AC: #5)
- [ ] **Task 7 — Idempotency** (AC: #6)
- [ ] **Task 8 — Tests** (AC: #7, #8)
- [ ] **Task 9 — `make lint` + `make test` clean** (AC: #9)
- [ ] **Task 10 — Update sprint-status.yaml to `review`**

## Dev Notes

- **Why `approve_with_conditions` only escalates on high-risk cases (AC2).** Low-risk cases approved with conditions (e.g., enhanced monitoring) do not need lead approval — that would be friction theater. High-risk cases approved with conditions need the second pair of eyes. This predicate is defensible policy.
- **The Team Lead queue may not exist yet.** Story 10-1 is in backlog. This story produces the upstream data correctly so that whenever 10-1 lands, the queue is populated retroactively. This is the right sequencing — produce the signal before the consumer.
- **`escalation_reason` discriminator** distinguishes `edd` (analyst escalated to EDD) vs `high_risk_conditions` (analyst approved-with-conditions on a high-risk case). Future analytics may want this.
- **Idempotency (AC6)** matters because the SSE event is broadcast — a duplicate emit could confuse subscribers that are listening for "case escalated, refresh queue."
- **Single-worker SSE** is the demo-scope simplification. In production, this would route through Redis pub/sub so all FastAPI workers can broadcast. For the demo, one worker is sufficient.

### File List

**To create**
- `apps/cockpit-api/tests/test_decision_escalation.py`

**To modify**
- `apps/cockpit-api/src/cockpit_api/models/case.py` (or state machine module — add `pending_lead_approval`)
- `apps/cockpit-api/src/cockpit_api/services/case_service.py` (extend transition table)
- `apps/cockpit-api/src/cockpit_api/services/decision_service.py` (extend `commit_decision` with escalation predicate)
- `apps/cockpit-api/src/cockpit_api/routers/decisions.py` (idempotency guard extension)
- `apps/cockpit-api/src/cockpit_api/services/sse_service.py` (or whichever module hosts Story 4-6's broadcast — emit event)
- `packages/contracts/src/contracts/ledger.py` (add `EscalatedForApprovalEntry`)
- `packages/contracts/src/contracts/cases.py` (add state to enum)
- `packages/contracts/tests/`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.tsx` (post-commit confirmation message)
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.test.tsx`
- `Documentation/implementation-artifacts/sprint-status.yaml`

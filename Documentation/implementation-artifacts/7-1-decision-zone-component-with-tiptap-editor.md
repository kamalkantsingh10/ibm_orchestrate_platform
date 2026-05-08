# Story 7.1: Decision Zone component with Tiptap editor

Status: review

## Story

As a KYC Analyst,
I want a `DecisionZone` component mounted at the bottom of the Case Canvas that — when the case is in `decision_ready` state — renders a Tiptap rich-text editor pre-loaded with the Writing agent's drafted rationale (Story 7-3), supports inline citation tokens that resolve to `ProvenancePill`s, exposes an outcome selector + Commit button (`⌘+Enter`), persists the draft to `localStorage` every 5 seconds, and becomes read-only when the case state is `pending_seal` or `committed`,
So that Priya's J1 commit beat lands ("she edits the agent's draft, presses ⌘+Enter, the seal animation plays"), the demo's "edit, don't author" principle has a tactile UI surface, and Story 7-2's tonal shift, Story 7-5's UndoPill, and Story 7-6's seal animation have a host component to attach to (FR22, FR24, FR26 partial, UX-DR16 "Decisions are sacred", NFR-RI1 HITL approval pattern).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 7.5. The bank-buyer scope persisted decision drafts to a server-side `decision_drafts` table (versioned); the demo uses `localStorage` (per-browser-per-case key).

| Bank-buyer scope (original 7.5) | Demo replacement in this story |
|---|---|
| Auto-save persists every 5s to `decision_drafts` table (versioned) | **`localStorage` per case_id** — `cockpit:decision-draft:{case_id}` key. No server table. Survives reload, not device switch. |
| Tenant-scoped query keys | **Single-tenant.** |
| Citation tokens insert ledger-entry-id references | **Same.** Inline `ProvenancePill` rendering for `led_<ULID>` strings, mirrors Story 6-8's `parseCitations` approach. |
| Required `case.state === 'decision_ready'` to render | **Same** — but additionally renders read-only when state is `pending_seal` or `committed`, since Stories 7-5/7-6 need a host component. |
| Tiptap with light formatting (paragraph, bold, italic, citation) | **Same.** Tiptap StarterKit + a small custom Citation mark. |
| Officer signature ceremony before POST | **Cut.** Story 7-7's POST endpoint records officer identity from session (no Ed25519). |

What survives: **Tiptap editor, Writing-agent-draft pre-load, citation tokens with ProvenancePill rendering, broken-citation render-time errors, outcome selector (Story 7-9), Commit via `⌘+Enter`, read-only states for `pending_seal` / `committed`, the Decision Zone as the host for Stories 7-2 / 7-5 / 7-6 / 7-8.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`, `architecture.md#Frontend Architecture` § F5 (Tiptap), `ux-design-specification.md` § DecisionZone, `prd.md#Functional Requirements` FR22 / FR24 / FR26.

## Acceptance Criteria

1. **AC1 — Tiptap dependencies in `apps/cockpit-ui/package.json`.**

    Add:
    ```
    "@tiptap/react": "^2.6.0",
    "@tiptap/starter-kit": "^2.6.0",
    "@tiptap/extension-placeholder": "^2.6.0"
    ```

    Architecture § F5 already names Tiptap as the Decision Zone editor; this story adds it. Version pinning: use the latest 2.x stable available at implementation time (verify via `pnpm view @tiptap/react versions` — pick the latest `2.x`, do not adopt 3.x without architecture review). After editing `package.json`, run `pnpm install` from the repo root.

2. **AC2 — `useDecisionDraft(caseId)` hook at `apps/cockpit-ui/src/hooks/useDecisionDraft.ts`.**

    ```typescript
    export interface DecisionDraftState {
        rationaleHtml: string;          // Tiptap output
        outcome: 'approve' | 'decline' | 'approve_with_conditions' | 'escalate_to_edd' | null;
        conditions: string[];           // populated when outcome === 'approve_with_conditions'
        updatedAt: string;              // ISO timestamp
    }

    export function useDecisionDraft(caseId: string): {
        draft: DecisionDraftState;
        setRationale: (html: string) => void;
        setOutcome: (o: DecisionDraftState['outcome']) => void;
        setConditions: (conds: string[]) => void;
        clear: () => void;
        loadInitial: (draftHtml: string) => void;       // called once when Writing agent's draft arrives
    } { ... }
    ```

    Storage:
    * Key: `cockpit:decision-draft:{caseId}`
    * Value: JSON-serialized `DecisionDraftState`
    * Auto-save: debounced 5s (use `setTimeout` ref + cleanup; no third-party debounce — boring is correct)
    * On mount: read from localStorage; if absent, return empty state
    * `loadInitial(draftHtml)` — only sets `rationaleHtml` if `localStorage` is empty (don't clobber officer edits with the agent's draft on every render)

    Tests at `useDecisionDraft.test.tsx`: mount with empty storage → empty state; setRationale → state updates + 5s later localStorage written; mount with existing storage → state hydrated; clear → storage removed; loadInitial doesn't clobber existing draft.

3. **AC3 — `useWritingAgentDraft(caseId)` hook.**

    Reads Story 7-3's drafted rationale via `GET /v1/cases/{caseId}/intake` (extending the intake row to include `writing.draft_html` per Story 7-3 § AC) — OR via a dedicated `GET /v1/cases/{caseId}/decision-draft` if Story 7-3 ships that endpoint instead. Match Story 7-3's chosen surface; default expectation: the draft is on the intake row alongside other agent outputs.

    ```typescript
    export function useWritingAgentDraft(caseId: string): UseQueryResult<{ rationaleHtml: string; agentActionId: string }> { ... }
    ```

    Tests: returns the draft; null when absent (writing agent hasn't run yet); uses existing intake query key to share TanStack Query cache.

4. **AC4 — `DecisionZone` component at `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.tsx`.**

    ```typescript
    export interface DecisionZoneProps {
        caseId: string;
    }

    export function DecisionZone({ caseId }: DecisionZoneProps): JSX.Element | null {
        const { data: caseData } = useCase(caseId);
        const { data: writingDraft } = useWritingAgentDraft(caseId);
        const draft = useDecisionDraft(caseId);
        const isReadOnly = caseData?.state === 'pending_seal' || caseData?.state === 'committed';
        const isHidden = caseData?.state === 'intake_scheduled' || caseData?.state === 'closed';

        // Hide entirely on early/terminal states
        if (isHidden) return null;

        // ... render
    }
    ```

    Layout:
    * **Header bar** (`flex items-center justify-between px-5 py-3 border-b border-zinc-200`):
        * Left: `<h2 className="text-base font-semibold text-zinc-900">Decision Zone</h2>` + small state pill (`decision_ready` → "Ready to commit"; `pending_seal` → "Sealing in {n}s" — value comes from Story 7-5; `committed` → "Sealed").
        * Right: `<OutcomeSelector />` (Story 7-9 component).
    * **Editor body** (`px-5 py-4 max-w-4xl mx-auto`):
        * Tiptap editor — content from `draft.rationaleHtml` (or, on first mount with no localStorage and writingDraft loaded, call `draft.loadInitial(writingDraft.rationaleHtml)`).
        * `editable={!isReadOnly}`.
    * **Footer bar** (`flex items-center justify-between px-5 py-3 border-t border-zinc-200`):
        * Left: small "Auto-saved" hint with last-saved relative timestamp.
        * Right: `<CommitButton />` — disabled when outcome is null OR (outcome === 'approve_with_conditions' AND conditions empty) OR there's a broken citation in the rationale (AC7); enabled otherwise. `⌘+Enter` keyboard shortcut fires the same handler.

    Mount inside `apps/cockpit-ui/src/routes/cases.$caseId.tsx` below the panel grid:
    ```tsx
    <div className="grid grid-cols-2 gap-4 max-w-5xl">
        ...DocumentsPanel, ScreeningPanel, UBOPanel, RiskPanel...
    </div>
    <DecisionZone caseId={caseId} />
    ```

5. **AC5 — Tiptap config + StarterKit slimming.**

    `apps/cockpit-ui/src/components/cockpit/DecisionZone/editor.ts`:

    ```typescript
    import { useEditor } from '@tiptap/react';
    import StarterKit from '@tiptap/starter-kit';
    import Placeholder from '@tiptap/extension-placeholder';
    import { CitationMark } from './CitationMark';

    export function useDecisionEditor(opts: { initialHtml: string; editable: boolean; onUpdate: (html: string) => void }) {
        return useEditor({
            extensions: [
                StarterKit.configure({
                    heading: false,
                    codeBlock: false,
                    code: false,
                    horizontalRule: false,
                    blockquote: false,
                    bulletList: false,
                    orderedList: false,
                    listItem: false,
                    strike: false,
                }),
                Placeholder.configure({
                    placeholder: 'Write your rationale here, or wait for the Writing agent to populate one…',
                }),
                CitationMark,
            ],
            content: opts.initialHtml,
            editable: opts.editable,
            onUpdate: ({ editor }) => opts.onUpdate(editor.getHTML()),
        });
    }
    ```

    Slimming: kept extensions are paragraph (default in StarterKit), bold, italic, history (undo/redo). The full block-list machinery is overkill for KYC rationales.

6. **AC6 — `CitationMark` Tiptap mark.**

    `apps/cockpit-ui/src/components/cockpit/DecisionZone/CitationMark.ts`:

    ```typescript
    import { Mark } from '@tiptap/core';

    export const CitationMark = Mark.create({
        name: 'citation',
        addAttributes() {
            return {
                ledgerId: { default: null, parseHTML: el => el.getAttribute('data-ledger-id') },
            };
        },
        parseHTML() {
            return [{ tag: 'span[data-ledger-id]' }];
        },
        renderHTML({ HTMLAttributes }) {
            return ['span', { ...HTMLAttributes, 'data-ledger-id': HTMLAttributes.ledgerId, class: 'citation-token' }, 0];
        },
    });
    ```

    Insertion: a small toolbar button or slash command — for the demo, a single button in the editor toolbar that prompts (via a Radix Popover with a text input) for a `led_<ULID>`. Validate the input shape (regex matches `^led_[0-9A-HJKMNP-TV-Z]{26}$`). On confirm, insert as a citation mark wrapping the entered text. The Writing agent's draft (Story 7-3) embeds these tokens directly in HTML, so manual insertion is a backup path.

    Rendered visually: `.citation-token` Tailwind class — `inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-blue-50 text-blue-800 text-xs font-mono ring-1 ring-blue-200`. **Broken citation override** — when Story 7-7's commit-time validator finds a `data-ledger-id` that doesn't resolve in the case's ledger, the citation renders red (`bg-rose-100 text-rose-800 ring-rose-200`) with a tooltip "ledger entry not found". Done at render time, not at save time — see AC7.

7. **AC7 — Broken-citation detection (commit-time gate).**

    Before enabling the Commit button, parse the editor's HTML for `data-ledger-id` attrs and resolve each against the case's ledger (TanStack Query — Story 6-7's `GET /v1/cases/{caseId}/ledger`). A citation is "broken" if the ledger doesn't include an entry with that ID.

    Helper at `apps/cockpit-ui/src/components/cockpit/DecisionZone/citationValidator.ts`:

    ```typescript
    export function findCitations(html: string): string[] {
        const re = /data-ledger-id="(led_[0-9A-HJKMNP-TV-Z]{26})"/g;
        return Array.from(html.matchAll(re), m => m[1]);
    }

    export function findBrokenCitations(html: string, ledgerIds: Set<string>): string[] {
        return findCitations(html).filter(id => !ledgerIds.has(id));
    }
    ```

    The Commit button's `disabled` condition includes `findBrokenCitations(...).length > 0`. A small inline error strip above the footer lists the broken IDs ("Cannot commit — citation `led_01HXY3...` does not resolve. Edit or remove."), with a `role="alert"` for screen readers. No commit is allowed until clean.

8. **AC8 — Outcome selector contract slot.**

    `<OutcomeSelector />` component is owned by Story 7-9 (formal contract + UI). For this story, **import it** and pass it the draft state from `useDecisionDraft`. If Story 7-9 hasn't landed yet, **render a stub** — a `<select>` with the four outcome literals, plus a conditional `<input>` for conditions when `approve_with_conditions` is selected. Wire the stub to `draft.setOutcome` / `draft.setConditions`. When 7-9 lands, swap the stub for the real component (one-line change).

    Document the stub in a code comment: `// TODO(7-9): replace with OutcomeSelector when Story 7-9 ships.`

9. **AC9 — Commit handler.**

    The Commit button + `⌘+Enter` both invoke `commitDecision(...)`:

    ```typescript
    async function commitDecision() {
        if (!draft.outcome) return;
        if (findBrokenCitations(draft.rationaleHtml, ledgerIds).length > 0) return;

        const res = await fetch(`/v1/cases/${caseId}/decisions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                outcome: draft.outcome,
                conditions: draft.conditions,
                rationale_html: draft.rationaleHtml,
            }),
        });
        if (!res.ok) {
            // toast / inline error — Story 7-7 returns RFC 7807
            return;
        }
        // case state will SSE-flip to pending_seal; Story 7-5's UndoPill mounts.
        // Optimistic: invalidate ['case', caseId] so the canvas refetches.
    }
    ```

    Story 7-7 owns the endpoint shape; this story consumes it. The localStorage draft is **NOT cleared on commit** — Story 7-5's undo flow re-opens the editor with the same draft if the officer undoes. Cleared only when the case state transitions to `committed` (via SSE listener that calls `draft.clear()`).

10. **AC10 — Read-only state.**

    When `case.state === 'pending_seal'` (Story 7-7's new state) or `'committed'`, the editor renders with `editable: false`. The Commit button is hidden; replaced by Story 7-5's UndoPill (during pending_seal) or by a "Sealed (`led_<ULID>`)" indicator (during committed — wired via Story 7-6).

    Read-only Tiptap retains the citation rendering and styling — analyst sees the committed rationale verbatim with citations clickable (clicking a citation opens Story 6-6's slide-out for that ledger entry — wire by intercepting clicks on `.citation-token` elements; for the demo, just a `window.dispatchEvent(new CustomEvent('cockpit:open-trace', {detail: ledgerId}))` and route-level handler. Or simpler: navigate to `?trace=led_...` query param. Pick the simpler path).

11. **AC11 — Auto-save persistence + reload.**

    * Type a rationale; wait 5s; refresh the page → rationale survives.
    * Switch to a different case; switch back → that case's rationale (per `caseId` storage key) is restored.
    * The Writing agent's draft is **the seed** — only used on first paint when localStorage is empty.

12. **AC12 — Tests at `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.test.tsx`.**

    * Renders nothing when `case.state === 'intake_scheduled'`.
    * Renders editable Tiptap when `case.state === 'decision_ready'`.
    * Loads Writing agent's draft when localStorage empty.
    * Does NOT clobber localStorage draft when Writing agent draft arrives later.
    * Outcome selector stub renders 4 options.
    * Conditions input renders only when `approve_with_conditions` selected.
    * Commit button disabled when outcome null.
    * Commit button disabled when broken citation present (assert error strip visible).
    * `⌘+Enter` triggers commit handler.
    * POST to `/v1/cases/{id}/decisions` fires with the right body.
    * Read-only state when `case.state === 'pending_seal'`.
    * Click on citation token dispatches the open-trace event / sets the query param (whichever path picked).

13. **AC13 — Tests at `apps/cockpit-ui/src/hooks/useDecisionDraft.test.tsx`.**

    * Empty state on mount when localStorage empty.
    * Hydrates from localStorage on mount.
    * `setRationale` debounces 5s before write.
    * `loadInitial` writes only when state empty.
    * `clear()` removes the storage key.

14. **AC14 — Tests at `citationValidator.test.ts`.**

    * `findCitations` returns all `led_<ULID>` substrings.
    * `findBrokenCitations` filters by the ledger set.
    * Edge: HTML with no citations → empty array.

15. **AC15 — `make lint && make test` clean.** Net new test count: ≥ 12 in `DecisionZone.test.tsx`, ≥ 5 in `useDecisionDraft.test.tsx`, ≥ 3 in `citationValidator.test.ts`.

16. **AC16 — End-to-end manual demo.**

    `make demo-reset && make seed && <run intake on Vora>`, then `make dev`:
    1. Open Vora's case. Documents / Screening / UBO / Risk panels render. Decision Zone is hidden because state is `intake_scheduled`.
    2. After intake completes (via SSE event from Story 6-2 supervisor), case transitions to `decision_ready`. Decision Zone appears at the bottom of the canvas.
    3. Decision Zone editor pre-populated with Writing agent's draft (Story 7-3) — 2-4 paragraphs citing screening / risk findings as inline blue citation tokens.
    4. Click a citation token → Story 6-6's slide-out opens with that agent action's reasoning trace.
    5. Type — auto-save fires after 5s pause, "Auto-saved 5s ago" hint updates.
    6. Reload the page — draft survives.
    7. Select outcome `approve_with_conditions`; conditions input appears; type "enhanced monitoring 6mo".
    8. Press `⌘+Enter` → POST fires; case state SSE-flips to `pending_seal`; UndoPill (Story 7-5) appears; editor becomes read-only.

## Tasks / Subtasks

- [x] **Task 1 — Tiptap deps + base editor** (AC: #1, #5, #6)
  - [x] Subtask 1.1 — Add Tiptap packages to `package.json`; `pnpm install`.
  - [x] Subtask 1.2 — `editor.ts` with `useDecisionEditor` hook.
  - [x] Subtask 1.3 — `CitationMark.ts`.
  - [x] Subtask 1.4 — Tailwind class for `.citation-token`.

- [x] **Task 2 — Storage hooks** (AC: #2, #3, #13)
  - [x] Subtask 2.1 — `useDecisionDraft.ts`.
  - [x] Subtask 2.2 — `useWritingAgentDraft.ts`.
  - [x] Subtask 2.3 — Hook tests (≥ 5 cases each).

- [x] **Task 3 — `DecisionZone` component** (AC: #4, #8, #10, #12)
  - [x] Subtask 3.1 — `DecisionZone.tsx` with header / body / footer.
  - [x] Subtask 3.2 — `OutcomeSelector` stub (replace when 7-9 lands).
  - [x] Subtask 3.3 — `index.ts` re-export.
  - [x] Subtask 3.4 — `DecisionZone.test.tsx` (≥ 12 cases).

- [x] **Task 4 — Citation validation** (AC: #7, #14)
  - [x] Subtask 4.1 — `citationValidator.ts`.
  - [x] Subtask 4.2 — `citationValidator.test.ts` (≥ 3 cases).
  - [x] Subtask 4.3 — Wire into Commit-button enable/disable + error strip.

- [x] **Task 5 — Commit handler** (AC: #9, #11)
  - [x] Subtask 5.1 — `commitDecision` function.
  - [x] Subtask 5.2 — `⌘+Enter` keyboard binding (mirror Story 4-2's keyboard hook pattern).
  - [x] Subtask 5.3 — Click-to-open-trace on citation tokens.

- [x] **Task 6 — Wire into route** (AC: #4, #16)
  - [x] Subtask 6.1 — Mount `<DecisionZone caseId={caseId} />` in `cases.$caseId.tsx`.
  - [x] Subtask 6.2 — Verify SSE event integration: case state transitions invalidate `['case', caseId]`; Decision Zone re-renders.

- [x] **Task 7 — Verification** (AC: #15, #16)
  - [x] Subtask 7.1 — `make lint && make test` green for new code (cockpit-ui ESLint + Prettier clean; 32 new vitests pass; 5 pre-existing failures in `useCase.test.tsx` / `useCases.test.tsx` predate this story).
  - [ ] Subtask 7.2 — Manual demo per AC16 — **deferred** until Stories 7-3 (Writing agent) and 7-7 (POST endpoint + `pending_seal` state) ship; full demo flow is gated on those.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Frontend Architecture` § F5] Tiptap (ProseMirror-based) is the chosen Decision Zone editor — headless, extensible, React-19 compatible, light formatting only.
* [Source: `architecture.md#Frontend Architecture` § F4] No form library — `useState` is the form layer. Tiptap-state lives inside the editor instance; outcome / conditions are plain `useState`.
* [Source: `architecture.md#Project-Specific Patterns` § P5 Officer Action Pattern] **bank-buyer scope**: client-side WebCrypto Ed25519 sign over canonical JSON. **Demo scope**: cut. Decision payload posts as plain JSON; cockpit-api records officer identity from session.
* [Source: `architecture.md#Frontend Architecture` § F1] TanStack Query for server state; `['case', caseId]` invalidates on SSE events, refetches the case envelope including state. Decision Zone re-renders when `case.state` changes.
* [Source: `ux-design-specification.md` § DecisionZone] anatomy + serif rationale typography (Story 7-2 introduces the actual font shift; this story uses default zinc text).
* [Source: `prd.md#Functional Requirements`] FR22 (rich-text editor with citation tokens), FR24 (commit decision), FR26 (writing agent provides draft).

### Critical pitfalls

1. **Don't persist the draft to a server-side `decision_drafts` table.** Bank-buyer scope had it; demo cuts it. localStorage is per-browser — fine for the demo (Kamal driving, three bosses watching). The day someone wants cross-device sync, add the table.

2. **`loadInitial` only seeds on empty state — don't clobber officer edits.** If the Writing agent's draft re-arrives via SSE after the officer has typed, `loadInitial` must short-circuit. Tests AC12/AC13 verify.

3. **Read-only Tiptap when state is `pending_seal` / `committed`.** Don't unmount the editor — the officer is still reading the rationale during the 120s window. Just flip `editable: false`. Story 7-5's UndoPill mounts as an overlay.

4. **`editable` cannot be flipped after Tiptap initialization** in some versions — verify against the installed version. If immutable, key the editor by `isReadOnly` to force remount: `<Editor key={isReadOnly ? 'ro' : 'rw'} ... />`. This loses cursor position on transition, which is acceptable for the demo (the transition is rare and committal).

5. **Citation validation happens client-side only**. Story 7-7's POST endpoint **does not** re-validate citations — the client is the gate. This is acceptable for the demo (single-officer, no adversarial input). Document in a code comment + Story 7-7's pitfalls.

6. **`⌘+Enter` keyboard shortcut must NOT fire when typing inside a modal.** If Story 7-5's reason-capture modal is open, `⌘+Enter` should not commit a new decision. The keyboard hook should check active focus — Story 4-2's existing keyboard hook (`useKeyboardShortcuts`) likely has this; reuse it.

7. **localStorage quota** — a typical browser allows ~5MB. A KYC rationale is < 4KB. Even with conditions and metadata, < 10KB. No quota concerns; don't add a serializer-size guard.

8. **Don't use a `<form>` element.** Tiptap's editor is a `contenteditable` `<div>`; wrapping in a `<form>` confuses keyboard handling and adds Enter-to-submit semantics that conflict with Tiptap's paragraph creation. Render the Decision Zone as `<section>`; Commit handler is a button click + `⌘+Enter`.

9. **`useDecisionDraft` localStorage key includes `caseId`** — case-switching must not bleed drafts across cases. Confirm in tests.

10. **Outcome selector `OutcomeSelector` from Story 7-9** — if 7-9 hasn't landed when this story is dev'd, ship the stub. The integration is one import swap. Don't block this story on 7-9.

11. **Render-time error pill on broken citations** — UX-spec mandates this (line 1291). The error strip is the commit gate; the citation-token's red coloring is the visual hint. Both must exist.

12. **`case.state === 'committed'`** still renders the editor (read-only) **forever** — the officer / regulator can revisit. Don't unmount Decision Zone; only hide on `intake_scheduled` and `closed`.

13. **`pending_seal` is a NEW case state** added by Story 7-7. Story 2-1's existing CaseState enum (`packages/contracts/src/contracts/cases.py`) doesn't include it yet. Don't add it in this story — Story 7-7 owns the contract change. This story consumes the new state when it arrives.

### Story dependencies

* **Strict prereqs:** Story 7-3 (Writing agent provides initial draft via `useWritingAgentDraft`), Story 7-7 (POST endpoint + `pending_seal` state), Story 7-9 (`OutcomeSelector` component — stub acceptable until then), Story 6-7 (`GET /v1/cases/{id}/ledger` for citation validation), Story 6-6 (citation click → reasoning trace slide-out), Story 4-6 (SSE invalidation drives re-render on state transitions).
* **Read by:** Story 7-2 (tonal shift extends this component), Story 7-5 (UndoPill mounts inside this component during `pending_seal`), Story 7-6 (seal animation fires on this component), Story 7-8 (Evidence shelf toggle lives in this component's header).

### Project Structure Notes

This story creates:
- `apps/cockpit-ui/src/hooks/useDecisionDraft.ts`
- `apps/cockpit-ui/src/hooks/useDecisionDraft.test.tsx`
- `apps/cockpit-ui/src/hooks/useWritingAgentDraft.ts`
- `apps/cockpit-ui/src/hooks/useWritingAgentDraft.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.tsx`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/editor.ts`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/CitationMark.ts`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/citationValidator.ts`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/citationValidator.test.ts`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/index.ts`

This story modifies:
- `apps/cockpit-ui/package.json` — adds Tiptap packages
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` — mounts `<DecisionZone>`
- `apps/cockpit-ui/src/styles/tokens.css` (or equivalent) — adds `.citation-token` Tailwind utility if not via Tailwind classes inline

This story does NOT create:
- Server-side draft persistence (cut — localStorage suffices)
- Officer keypair / signing / Ed25519 verification (cut from demo)
- The Writing agent itself (Story 7-3)
- The POST /decisions endpoint (Story 7-7)
- The case state transition logic (Story 7-7)
- The 120s timer (Story 7-4)
- UndoPill (Story 7-5)
- Seal animation (Story 7-6)
- Evidence shelf (Story 7-8)
- The OutcomeSelector component (Story 7-9 — stubbed here)

### References

- [Source: `epics.md#Epic 7` § Story 7.5] original AC (verbatim shape; server-side draft persistence cut → localStorage; tenant_id cut)
- [Source: `architecture.md#Frontend Architecture`] § F1, F4, F5
- [Source: `architecture.md#Project-Specific Patterns`] § P5 (officer action — sign cut for demo)
- [Source: `ux-design-specification.md` § DecisionZone]
- [Source: `prd.md#Functional Requirements`] FR22, FR24, FR26
- [Source: `apps/cockpit-ui/src/components/cockpit/ProvenanceIndicator/`] (existing) citation styling reference
- [Source: `6-7-cockpit-chat-agent-with-mesh-as-tools.md`] `GET /v1/cases/{id}/ledger` consumed for citation validation
- [Source: `6-6-reasoning-trace-slide-out-component.md`] citation click target

### Demo verification protocol

Per AC16. If any step fails, the bug is in this story; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

- Tiptap `useEditor` reads `content` once on mount. Initial implementation used a runtime `setContent` effect to seed the writing-agent draft; jsdom + the Tiptap v2.27 transaction loop swallowed the update silently (test case "seeds the editor with the writing-agent draft" timed out).
- Switched to a deps-driven rebuild: `useDecisionEditor` now takes a `rebuildKey` (caseId + readOnly + seedSignature) and Tiptap recreates the editor when the key flips. Typing leaves the key untouched, so cursor state survives.
- ESLint flagged `setSeedNonce` in the writing-draft effect and the `setDraft(_readInitial(caseId))` in the caseId-change effect (`react-hooks/set-state-in-effect`). Refactored both to setState-during-render patterns: `useDecisionDraft` uses the React-recommended "Adjust state when a prop changes" idiom (`storedCaseId` state + sync setState during render), and `DecisionZone` derives its rebuild signature from `Boolean(writingDraft?.rationaleHtml)` directly so no nonce is needed.
- 5 pre-existing test failures (`useCase.test.tsx` x3, `useCases.test.tsx` x2) verified out of scope: confirmed by stashing all my changes and re-running — the failures persist, so they predate Story 7.1 and stem from Story 4.6's removal of `refetchInterval` + `useCurrentUser` not being initialized in those legacy tests.

### Completion Notes List

- All 16 ACs implemented. AC #16 (manual demo) is gated on Stories 7-3 / 7-7 / 7-9 — until those land the auto-draft seed comes back as `null` (graceful empty state) and POSTing to `/v1/cases/{id}/decisions` 404s; the editor + citation gate + auto-save + read-only states all work today.
- Net new tests: **14** in `DecisionZone.test.tsx` (≥12 required), **7** in `useDecisionDraft.test.tsx` (≥5 required), **6** in `citationValidator.test.ts` (≥3 required), **5** in `useWritingAgentDraft.test.tsx` (bonus). 32 total — all green.
- `cockpit-ui` ESLint + Prettier + Vitest all clean for new files. `vite build` succeeds.
- The "click a citation → open reasoning trace slide-out" path (AC #10) goes through a `cockpit:open-trace` window CustomEvent that the route handler listens for and feeds into `setTraceTarget`. The simpler `?trace=led_…` query-param alternative was passed over because the slide-out is already wired to the route's `traceTarget` state machine.
- Pitfall #4 (Tiptap `editable` flips don't always propagate post-init) handled by including `isReadOnly` in the editor's `rebuildKey`. Cursor position is lost on the read-only flip — acceptable per story dev notes (transition is rare and committal).
- The localStorage timer cleanup on case-switch was intentionally dropped: pending debounced writes capture the *old* caseId in their closures, so a half-typed draft from Case A still persists to `cockpit:decision-draft:case_A` after the analyst switches to Case B. No cross-case bleed.
- Effective rationale at commit time = `draft.rationaleHtml || writingDraft.rationaleHtml || ''`. An analyst can commit a clean agent-drafted rationale without ever typing.

### File List

**Created:**
- `apps/cockpit-ui/src/hooks/useDecisionDraft.ts`
- `apps/cockpit-ui/src/hooks/useDecisionDraft.test.tsx`
- `apps/cockpit-ui/src/hooks/useWritingAgentDraft.ts`
- `apps/cockpit-ui/src/hooks/useWritingAgentDraft.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.tsx`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/editor.ts`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/CitationMark.ts`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/citationValidator.ts`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/citationValidator.test.ts`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/OutcomeSelector.tsx` (stub for Story 7-9)
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/index.ts`

**Modified:**
- `apps/cockpit-ui/package.json` — adds `@tiptap/core`, `@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-placeholder` (`^2.27.2`)
- `apps/cockpit-ui/pnpm-lock.yaml` (auto-generated)
- `apps/cockpit-ui/src/index.css` — adds `.citation-token` + `.citation-broken` utility classes
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` — mounts `<DecisionZone>` below the panel grid; subscribes to `cockpit:open-trace` window events to drive the existing `ReasoningTraceSlideOut` from citation clicks.
- `Documentation/implementation-artifacts/sprint-status.yaml` — `7-1` flipped to `review`.

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 7.1 drafted. Demo replacement for bank-buyer Story 7.5: Tiptap editor with StarterKit + custom CitationMark; Writing-agent-draft seed via useWritingAgentDraft; localStorage auto-save replaces server-side decision_drafts table; broken-citation commit-gate; ⌘+Enter handler; OutcomeSelector stub for Story 7-9. WebCrypto signing cut. |
| 2026-05-08 | Implemented Story 7.1 (Amelia). 12 new files, 3 modified. Tiptap @ 2.27.2 wired with StarterKit slimmed to paragraph + bold + italic + history. Custom CitationMark renders `<span data-ledger-id>` tokens with shared `.citation-token` styling; broken-citation override switches to a rose palette + ARIA-alert error strip. `useDecisionDraft` debounces 5s to localStorage; `useWritingAgentDraft` polls a future `GET /v1/cases/{id}/intake/writing` endpoint (Story 7-3) and gracefully returns null on 404. `DecisionZone` is hidden on `intake_scheduled` / `closed` / `escalated`, editable on `decision_ready`, read-only on `pending_seal` / `committed`. Commit handler POSTs to Story 7-7's future `/decisions` endpoint; `⌘+Enter` shortcut wired through a section-scoped keydown listener that defers to active modals. 32 new vitest cases — all green. Status flipped to `review`. |

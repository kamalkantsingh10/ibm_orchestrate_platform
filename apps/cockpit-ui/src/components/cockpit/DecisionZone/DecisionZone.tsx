// DecisionZone — Story 7.1 / AC #4, #9, #10, #11, #12.
//
// Mounted at the bottom of the Case Canvas. Hides on
// `intake_scheduled` / `closed`; renders an editable Tiptap rationale on
// `decision_ready`; renders read-only on `pending_seal` (Story 7-7) and
// `committed` so the analyst can re-read the rationale during the
// 120-second undo window and forever afterward.
//
// Citation tokens (`<span data-ledger-id="led_…">`) are validated client-
// side against the case ledger. Broken citations disable the Commit
// button and surface an inline error strip; clicking a clean citation
// dispatches a `cockpit:open-trace` CustomEvent so the route can open
// the Story 6-6 reasoning-trace slide-out.
//
// Pitfall #4 (story dev notes): we key the EditorContent on the
// read-only flag so that `editable` flips after init don't get swallowed
// by Tiptap. Cursor position is lost on transition — acceptable; the
// transition is rare and committal.

import { useQueryClient, useQuery } from '@tanstack/react-query';
import { EditorContent } from '@tiptap/react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { components } from '@/api-types';
import { useCase } from '@/hooks/useCase';
import { useDecisionDraft } from '@/hooks/useDecisionDraft';
import { useDocumentIntelligence } from '@/hooks/useDocumentIntelligence';
import { useEddMemoDraft } from '@/hooks/useEddMemoDraft';
import { useSealAnimation } from '@/hooks/useSealAnimation';
import { useWritingAgentDraft } from '@/hooks/useWritingAgentDraft';
import { useCurrentUser } from '@/stores/currentUser';
import { useDecisionZoneFocusStore } from '@/stores/decisionZoneStore';
import { formatRelative } from '@/lib/formatRelative';
import { useDecisionEditor } from './editor';
import { findBrokenCitations } from './citationValidator';
import { OutcomeSelector } from './OutcomeSelector';
import { SealIcon } from './SealIcon';
import { SealedIndicator } from './SealedIndicator';

type LedgerEntry = components['schemas']['LedgerEntry'];

// Story 7-7 introduces `pending_seal`. Until 7-7 ships the contract,
// compare against a string-widened union so the UI is forward-compatible.
type ExtendedCaseState = components['schemas']['CaseState'] | 'pending_seal';

export interface DecisionZoneProps {
  caseId: string;
  /** Story 7.8 — when supplied, the Evidence button renders in the
   *  header bar and clicking it invokes this callback. The route owns
   *  the open-state via useState and mounts EvidenceShelf separately.
   */
  onToggleEvidence?: () => void;
  /** Story 7.8 — drives the Evidence button's `aria-pressed` state. */
  evidenceOpen?: boolean;
}

const _STATE_LABEL: Partial<Record<ExtendedCaseState, string>> = {
  decision_ready: 'Ready to commit',
  pending_seal: 'Sealing…',
  committed: 'Sealed',
};

const _STATE_PILL_CLASSES: Partial<Record<ExtendedCaseState, string>> = {
  decision_ready: 'bg-blue-100 text-blue-800',
  pending_seal: 'bg-amber-100 text-amber-800',
  committed: 'bg-green-100 text-green-800',
};

export function DecisionZone({
  caseId,
  onToggleEvidence,
  evidenceOpen = false,
}: DecisionZoneProps) {
  const { data: caseData } = useCase(caseId);
  const { data: writingDraft } = useWritingAgentDraft(caseId);
  // Story 8.3 — when the case has been escalated to EDD, the v2 memo
  // takes priority over the v1 rationale for editor seeding.
  const { data: eddMemoDraft } = useEddMemoDraft(caseId);
  const { data: docIntel } = useDocumentIntelligence(caseId);
  const draft = useDecisionDraft(caseId);
  const queryClient = useQueryClient();
  const setDzFocused = useDecisionZoneFocusStore((s) => s.setFocused);
  const [commitError, setCommitError] = useState<string | null>(null);
  const [isCommitting, setIsCommitting] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const containerRef = useRef<HTMLElement | null>(null);

  const state = (caseData?.state as ExtendedCaseState | undefined) ?? null;
  const isHidden = state === 'intake_scheduled' || state === 'closed' || state === 'escalated';
  const isReadOnly = state === 'pending_seal' || state === 'committed';

  // Pitfall #2 — never clobber officer edits. The seed used at editor-
  // build time is the localStorage draft if present, otherwise the EDD
  // memo (Story 8.3) if present, otherwise the v1 Writing rationale,
  // otherwise empty. Computing the fallback at build time (rather than
  // via a setState-in-effect) means a draft that arrives after the
  // analyst started typing is silently ignored.
  const seedSignature = eddMemoDraft?.html
    ? 'edd-seeded'
    : writingDraft?.rationaleHtml
      ? 'seeded'
      : 'unseeded';

  // Clear the localStorage draft when the case state lands in
  // 'committed'. Story 7-5's undo flow re-opens the editor with the
  // same draft if the officer undoes, so we explicitly do NOT clear on
  // the optimistic transition to 'pending_seal'.
  useEffect(() => {
    if (state === 'committed') {
      draft.clear();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  // Pull the case ledger so we can resolve citation IDs. AC #7.
  const { data: ledgerEntries = [] } = useQuery<LedgerEntry[]>({
    queryKey: ['cases', caseId, 'ledger'],
    enabled: !isHidden,
    staleTime: 30_000,
    queryFn: async () => {
      const userId = useCurrentUser.getState().user.id;
      const res = await fetch(`/v1/cases/${encodeURIComponent(caseId)}/ledger?limit=200`, {
        headers: { Accept: 'application/json', 'X-Cockpit-Demo-User': userId },
      });
      if (!res.ok) {
        throw new Error(`ledger fetch failed (${res.status})`);
      }
      return (await res.json()) as LedgerEntry[];
    },
  });

  const ledgerIds = useMemo(() => new Set(ledgerEntries.map((e) => e.id)), [ledgerEntries]);

  // Effective rationale = officer edits if any, else the EDD memo
  // (Story 8.3), else the v1 writing-agent draft. Used both for
  // citation validation (commit gate) and for the commit body — the
  // analyst can commit a clean agent-drafted rationale without ever
  // typing.
  const effectiveRationaleHtml =
    draft.draft.rationaleHtml || eddMemoDraft?.html || writingDraft?.rationaleHtml || '';

  const broken = useMemo(
    () => findBrokenCitations(effectiveRationaleHtml, ledgerIds),
    [effectiveRationaleHtml, ledgerIds],
  );

  // The editor takes its initialHtml ONCE per `rebuildKey`. Typing
  // never bumps the key (so we don't lose cursor/state), but caseId
  // change, read-only flip, and the writing-agent-seed signal all do.
  const editor = useDecisionEditor({
    initialHtml: effectiveRationaleHtml,
    editable: !isReadOnly,
    onUpdate: (html) => draft.setRationale(html),
    rebuildKey: `${caseId}:${isReadOnly ? 'ro' : 'rw'}:${seedSignature}`,
  });

  // Story 7.2 / AC #2 — track DOM-level focus inside the Decision Zone.
  // Uses native focusin/focusout (not Tiptap's reactive editor.isFocused)
  // to avoid extra editor-tree re-renders. The
  // `containerRef.current?.contains(relatedTarget)` check absorbs
  // focus shifts between sibling controls (editor → outcome selector
  // → commit button) so the dim doesn't flicker on a tab traversal.
  useEffect(() => {
    const root = containerRef.current;
    if (!root) return;
    const onFocusIn = (e: FocusEvent) => {
      if (root.contains(e.target as Node)) {
        setIsFocused(true);
        setDzFocused(true);
      }
    };
    const onFocusOut = (e: FocusEvent) => {
      // relatedTarget is the element receiving focus next; if it's
      // still inside the Decision Zone, suppress the un-focus.
      const next = e.relatedTarget as Node | null;
      if (next && root.contains(next)) return;
      setIsFocused(false);
      setDzFocused(false);
    };
    root.addEventListener('focusin', onFocusIn);
    root.addEventListener('focusout', onFocusOut);
    return () => {
      root.removeEventListener('focusin', onFocusIn);
      root.removeEventListener('focusout', onFocusOut);
    };
  }, [setDzFocused]);

  // Story 7.2 / AC #6 — `Esc` blurs the active element to exit focus,
  // unless a Radix dialog/popover is open (let Radix's own Esc handler
  // close it first; the analyst can press Esc again to exit focus).
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (document.querySelector('[role="dialog"][data-state="open"]')) return;
      if (document.querySelector('[data-radix-popper-content-wrapper]')) return;
      const active = document.activeElement as HTMLElement | null;
      if (active && containerRef.current?.contains(active)) {
        active.blur();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, []);

  // Click-to-open-trace on citation tokens (AC #10). Use a single
  // delegated listener on the container so we don't have to wire each
  // span individually.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const handler = (ev: MouseEvent) => {
      if (!(ev.target instanceof HTMLElement)) return;
      const span = ev.target.closest('span[data-ledger-id]');
      if (!span) return;
      const ledgerId = span.getAttribute('data-ledger-id');
      if (!ledgerId) return;
      ev.preventDefault();
      window.dispatchEvent(new CustomEvent('cockpit:open-trace', { detail: { ledgerId, caseId } }));
    };
    el.addEventListener('click', handler);
    return () => el.removeEventListener('click', handler);
  }, [caseId]);

  const canCommit =
    !isReadOnly &&
    !isCommitting &&
    draft.draft.outcome !== null &&
    !(draft.draft.outcome === 'approve_with_conditions' && draft.draft.conditions.length === 0) &&
    broken.length === 0;

  const commitDecision = async () => {
    if (!canCommit || !draft.draft.outcome) return;
    setIsCommitting(true);
    setCommitError(null);
    try {
      const userId = useCurrentUser.getState().user.id;
      const res = await fetch(`/v1/cases/${encodeURIComponent(caseId)}/decisions`, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          'X-Cockpit-Demo-User': userId,
        },
        body: JSON.stringify({
          outcome: draft.draft.outcome,
          conditions: draft.draft.conditions,
          rationale_html: effectiveRationaleHtml,
        }),
      });
      if (!res.ok) {
        const problem = (await res.json().catch(() => null)) as { detail?: string } | null;
        setCommitError(problem?.detail ?? `Commit failed (${res.status})`);
        return;
      }
      // Story 8.7 AC #5 — qualifying outcomes route the case to the
      // Team Lead approval queue; surface that out-of-band so the
      // analyst doesn't expect the 120s undo / seal flow.
      try {
        const body = (await res.json().catch(() => null)) as {
          case_state?: string;
        } | null;
        if (body?.case_state === 'pending_lead_approval') {
          // Lazy import keeps the test surface (which doesn't mock
          // sonner here) decoupled.
          const { toast } = await import('sonner');
          toast('Sent to Team Lead approval queue', {
            description: 'Rohan Mehta will see this in the approvals queue.',
            duration: 4000,
          });
        }
      } catch {
        /* swallow — confirmation toast is best-effort */
      }
      // Optimistic — case state SSE-flips to pending_seal /
      // pending_lead_approval momentarily; refetch picks up the
      // authoritative state.
      void queryClient.invalidateQueries({ queryKey: ['case', caseId] });
    } catch (err) {
      setCommitError(err instanceof Error ? err.message : 'Commit failed');
    } finally {
      setIsCommitting(false);
    }
  };

  // ⌘+Enter shortcut while focused inside the Decision Zone (AC #9).
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const handler = (ev: KeyboardEvent) => {
      if (ev.key !== 'Enter') return;
      if (!(ev.metaKey || ev.ctrlKey)) return;
      // Don't fire if a modal (Story 7-5 reason-capture) is the active
      // element ancestor — the keyboard event should target that modal.
      const active = document.activeElement;
      if (active && active.closest('[role="dialog"]')) return;
      ev.preventDefault();
      void commitDecision();
    };
    el.addEventListener('keydown', handler);
    return () => el.removeEventListener('keydown', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canCommit, draft.draft.outcome, draft.draft.conditions, draft.draft.rationaleHtml]);

  // Tag broken citations with a CSS class at render time so the red
  // styling lights up. We mutate the editor DOM directly because Tiptap
  // doesn't have a one-line API for "annotate this mark when render-time
  // validation flags it." Pure-CSS alternative would require encoding
  // the broken set into the mark's attrs, which polutes the data layer.
  useEffect(() => {
    const root = containerRef.current;
    if (!root) return;
    const spans = root.querySelectorAll('span[data-ledger-id]');
    spans.forEach((span) => {
      const id = span.getAttribute('data-ledger-id');
      if (id && !ledgerIds.has(id)) {
        span.classList.add('citation-broken');
        span.setAttribute('title', 'ledger entry not found');
      } else {
        span.classList.remove('citation-broken');
        span.removeAttribute('title');
      }
    });
  });

  // Story 7.6 — seal animation. Phase advances on the SSE
  // `decision.sealed` event; the steady-state SealedIndicator is
  // gated on `case.state === 'committed'` so a page reload of an
  // already-sealed case still shows the indicator without replaying
  // the stamp.
  const sealState = useSealAnimation(caseId);
  const reduceMotion = useReducedMotion();
  const isSealing = sealState.phase === 'sealing';
  const sealLedgerEntryId =
    sealState.phase === 'sealing' || sealState.phase === 'sealed' ? sealState.ledgerEntryId : null;

  if (isHidden || !state) return null;

  const stateLabel = _STATE_LABEL[state] ?? state;
  const statePillClass = _STATE_PILL_CLASSES[state] ?? 'bg-zinc-100 text-zinc-700';
  const lastSaved = draft.draft.updatedAt ? formatRelative(draft.draft.updatedAt) : null;

  // Variants honour prefers-reduced-motion: collapsed to no-op when
  // the user has the system preference set.
  const sealVariants = reduceMotion
    ? { idle: {}, sealing: {} }
    : {
        idle: { y: 0, scale: 1 },
        sealing: {
          y: [0, -2, 0],
          scale: [1, 0.998, 1],
          transition: { duration: 0.4, ease: [0.4, 0, 0.2, 1] as [number, number, number, number] },
        },
      };
  const bodyOpacity = isSealing && !reduceMotion ? { opacity: [1, 0.7, 1] } : { opacity: 1 };

  // Story 7.2 / AC #3 — tonal swap on focus. zinc → stone is one step
  // warmer; the body shifts to the serif rationale typeface; transition
  // is colour-only so layout doesn't reflow.
  const sectionClass = [
    'mt-4 max-w-5xl rounded-md border shadow-sm',
    'transition-colors duration-300 ease-out motion-reduce:transition-none',
    isFocused
      ? 'bg-stone-50 text-stone-900 border-stone-200'
      : 'bg-white text-zinc-900 border-zinc-200',
  ].join(' ');
  const headerClass = [
    'flex items-center justify-between px-5 py-3 border-b',
    isFocused ? 'border-stone-200' : 'border-zinc-200',
  ].join(' ');
  const editorBodyClass = [
    'editor-body px-5 py-4 max-w-4xl mx-auto',
    'transition-[font,font-size] duration-300 ease-out motion-reduce:transition-none',
    isFocused ? 'font-serif text-base leading-relaxed' : 'font-sans text-sm leading-normal',
  ].join(' ');

  return (
    <motion.section
      ref={containerRef}
      data-testid="decision-zone"
      data-case-state={state}
      data-focused={isFocused ? 'true' : 'false'}
      data-seal-phase={sealState.phase}
      className={`${sectionClass} relative`}
      aria-label="Decision Zone"
      variants={sealVariants}
      animate={isSealing ? 'sealing' : 'idle'}
      initial="idle"
    >
      <header className={headerClass}>
        <div className="flex items-center gap-3">
          {/* AC #8 — header h2 stays font-sans (operational label, not
              the sacred rationale body). */}
          <h2 className="text-base font-semibold font-sans text-zinc-900">Decision Zone</h2>
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium font-sans ${statePillClass}`}
          >
            {stateLabel}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* Story 7.8 — Evidence shelf toggle. Renders only when the
             route wires the callback (the EvidenceShelf is mounted by
             the route, not by DecisionZone, so the drawer can portal
             cleanly). */}
          {onToggleEvidence ? (
            <button
              type="button"
              onClick={onToggleEvidence}
              aria-pressed={evidenceOpen}
              data-testid="decision-zone-evidence-toggle"
              className="rounded px-2.5 py-1 text-xs font-medium font-sans text-zinc-700 ring-1 ring-zinc-200 hover:bg-zinc-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              {(() => {
                const docCount = docIntel
                  ? new Set(docIntel.extracted_fields.map((f) => f.document_ref)).size
                  : 0;
                return docCount > 0 ? `Evidence (${docCount})` : 'Evidence';
              })()}
            </button>
          ) : null}
          <OutcomeSelector
            outcome={draft.draft.outcome}
            conditions={draft.draft.conditions}
            onOutcomeChange={draft.setOutcome}
            onConditionsChange={draft.setConditions}
            disabled={isReadOnly}
          />
        </div>
      </header>

      <motion.div
        className={editorBodyClass}
        data-decision-zone-focus-target
        animate={bodyOpacity}
        transition={{ duration: 0.4, ease: 'easeOut' }}
      >
        <EditorContent editor={editor} />
      </motion.div>

      {broken.length > 0 ? (
        <div
          role="alert"
          className="mx-5 mb-3 rounded border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800"
        >
          {broken.map((id) => (
            <div key={id}>
              Cannot commit — citation <code className="font-mono">{id}</code> does not resolve.
              Edit or remove.
            </div>
          ))}
        </div>
      ) : null}

      {commitError ? (
        <div
          role="alert"
          className="mx-5 mb-3 rounded border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800"
        >
          {commitError}
        </div>
      ) : null}

      <footer className="flex items-center justify-between px-5 py-3 border-t border-zinc-200">
        <span className="text-xs text-zinc-500">
          {lastSaved ? `Auto-saved ${lastSaved}` : 'Auto-saves every 5 seconds'}
        </span>
        {isReadOnly ? (
          state === 'committed' && sealLedgerEntryId ? (
            <SealedIndicator ledgerEntryId={sealLedgerEntryId} />
          ) : (
            <span className="text-xs italic text-zinc-500">
              {state === 'committed' ? 'Sealed (read-only).' : 'Awaiting seal…'}
            </span>
          )
        ) : (
          <button
            type="button"
            onClick={() => void commitDecision()}
            disabled={!canCommit}
            data-testid="decision-commit-button"
            className="rounded bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
          >
            {isCommitting ? 'Committing…' : 'Commit decision (⌘+Enter)'}
          </button>
        )}
      </footer>

      {/* Story 7.6 — animated seal stamp. Decorative; the
         SealedIndicator above carries the click-to-trace affordance. */}
      <AnimatePresence>
        {isSealing ? (
          <motion.div
            key="seal-stamp"
            data-testid="decision-zone-seal-stamp"
            className="pointer-events-none absolute right-6 bottom-3"
            initial={{ scale: 1.6, opacity: 0, rotate: -8 }}
            animate={{ scale: 1, opacity: 1, rotate: 0 }}
            exit={{ scale: 1.05, opacity: 0 }}
            transition={
              reduceMotion
                ? { duration: 0 }
                : { duration: 0.4, ease: [0.34, 1.56, 0.64, 1] as [number, number, number, number] }
            }
          >
            <SealIcon />
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.section>
  );
}

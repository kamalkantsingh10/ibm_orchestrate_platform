// useDecisionDraft — Story 7.1 / AC #2.
//
// Per-case decision draft persisted to localStorage. Auto-save fires on a
// 5-second debounce after the last edit. The Writing agent's draft is the
// SEED — `loadInitial` only writes the rationale when the local draft is
// empty, so officer edits are never clobbered (Story 7.1 pitfall #2).
//
// localStorage key shape: `cockpit:decision-draft:{caseId}`. Switching
// cases scopes the draft naturally; a single browser tab can hold one
// in-flight draft per case without bleeding across them.

import { useCallback, useEffect, useRef, useState } from 'react';

export type DecisionOutcome = 'approve' | 'decline' | 'approve_with_conditions' | 'escalate_to_edd';

export interface DecisionDraftState {
  rationaleHtml: string;
  outcome: DecisionOutcome | null;
  conditions: string[];
  updatedAt: string;
}

export interface UseDecisionDraftResult {
  draft: DecisionDraftState;
  setRationale: (html: string) => void;
  setOutcome: (o: DecisionOutcome | null) => void;
  setConditions: (conds: string[]) => void;
  clear: () => void;
  loadInitial: (draftHtml: string) => void;
}

export const DECISION_DRAFT_DEBOUNCE_MS = 5_000;

const _EMPTY: DecisionDraftState = {
  rationaleHtml: '',
  outcome: null,
  conditions: [],
  updatedAt: '',
};

function _storageKey(caseId: string): string {
  return `cockpit:decision-draft:${caseId}`;
}

function _readInitial(caseId: string): DecisionDraftState {
  if (typeof window === 'undefined') return _EMPTY;
  try {
    const raw = window.localStorage.getItem(_storageKey(caseId));
    if (!raw) return _EMPTY;
    const parsed = JSON.parse(raw) as Partial<DecisionDraftState>;
    return {
      rationaleHtml: typeof parsed.rationaleHtml === 'string' ? parsed.rationaleHtml : '',
      outcome: (parsed.outcome ?? null) as DecisionOutcome | null,
      conditions: Array.isArray(parsed.conditions) ? parsed.conditions.map(String) : [],
      updatedAt: typeof parsed.updatedAt === 'string' ? parsed.updatedAt : '',
    };
  } catch {
    return _EMPTY;
  }
}

function _isEffectivelyEmpty(state: DecisionDraftState): boolean {
  // The Writing agent's draft seeds an empty draft. Whitespace-only HTML
  // (Tiptap's default `<p></p>`) counts as empty — otherwise the seed
  // never lands when localStorage exists from a prior render.
  const stripped = state.rationaleHtml.replace(/<[^>]+>/g, '').trim();
  return stripped === '' && state.outcome === null && state.conditions.length === 0;
}

export function useDecisionDraft(caseId: string): UseDecisionDraftResult {
  const [draft, setDraft] = useState<DecisionDraftState>(() => _readInitial(caseId));
  const [storedCaseId, setStoredCaseId] = useState(caseId);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // "Adjust state when a prop changes" pattern (React docs): re-hydrate
  // synchronously during render when the analyst switches between
  // cases, so the new draft surfaces on the *same* render rather than a
  // post-effect tick. React discards and retries the render. Pending
  // debounce timers from the previous case capture the old caseId in
  // their closure, so they correctly persist the old draft to the old
  // storage key — no cross-case bleed.
  if (storedCaseId !== caseId) {
    setStoredCaseId(caseId);
    setDraft(_readInitial(caseId));
  }

  const _scheduleWrite = useCallback(
    (next: DecisionDraftState) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        try {
          window.localStorage.setItem(_storageKey(caseId), JSON.stringify(next));
        } catch {
          // localStorage may throw under quota or private-mode constraints;
          // for the demo we silently drop the write — see story note #7.
        }
      }, DECISION_DRAFT_DEBOUNCE_MS);
    },
    [caseId],
  );

  // Cleanup pending timers on unmount.
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const setRationale = useCallback(
    (html: string) => {
      setDraft((prev) => {
        const next: DecisionDraftState = {
          ...prev,
          rationaleHtml: html,
          updatedAt: new Date().toISOString(),
        };
        _scheduleWrite(next);
        return next;
      });
    },
    [_scheduleWrite],
  );

  const setOutcome = useCallback(
    (outcome: DecisionOutcome | null) => {
      setDraft((prev) => {
        const next: DecisionDraftState = {
          ...prev,
          outcome,
          conditions: outcome === 'approve_with_conditions' ? prev.conditions : [],
          updatedAt: new Date().toISOString(),
        };
        _scheduleWrite(next);
        return next;
      });
    },
    [_scheduleWrite],
  );

  const setConditions = useCallback(
    (conditions: string[]) => {
      setDraft((prev) => {
        const next: DecisionDraftState = {
          ...prev,
          conditions,
          updatedAt: new Date().toISOString(),
        };
        _scheduleWrite(next);
        return next;
      });
    },
    [_scheduleWrite],
  );

  const clear = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    try {
      window.localStorage.removeItem(_storageKey(caseId));
    } catch {
      // ignore
    }
    setDraft(_EMPTY);
  }, [caseId]);

  const loadInitial = useCallback(
    (draftHtml: string) => {
      setDraft((prev) => {
        if (!_isEffectivelyEmpty(prev)) return prev;
        const next: DecisionDraftState = {
          ...prev,
          rationaleHtml: draftHtml,
          updatedAt: new Date().toISOString(),
        };
        _scheduleWrite(next);
        return next;
      });
    },
    [_scheduleWrite],
  );

  return { draft, setRationale, setOutcome, setConditions, clear, loadInitial };
}

// useSealAnimation — Story 7.6 / AC #1.
//
// Subscribes to the case's SSE channel via the existing
// `cockpit:decision-event` window event (Story 7.4 / 7.5 wires this
// up). On `decision.sealed` the hook flips to ``sealing`` for the
// 400ms animation window, then to ``sealed`` (steady state). Page
// reload starts in ``idle`` even for an already-committed case — the
// stamp does NOT replay (story pitfall #5). The SealedIndicator is
// rendered separately based on case state, not on this hook's phase.

import { useEffect, useState } from 'react';

const _SEAL_ANIMATION_MS = 400;

export type SealState =
  | { phase: 'idle' }
  | { phase: 'sealing'; ledgerEntryId: string }
  | { phase: 'sealed'; ledgerEntryId: string };

interface _DecisionSealedDetail {
  case_id?: string;
  caseId?: string;
  ledger_entry_id?: string;
  ledgerEntryId?: string;
  event?: string;
  data?: { case_id?: string; ledger_entry_id?: string };
}

export function useSealAnimation(caseId: string): SealState {
  const [state, setState] = useState<SealState>({ phase: 'idle' });

  useEffect(() => {
    const handler = (ev: Event) => {
      const detail = (ev as CustomEvent<_DecisionSealedDetail>).detail;
      if (!detail) return;
      // Accept multiple shapes for forward-compat with the SSE wire.
      const eventName = detail.event ?? '';
      if (eventName !== 'decision.sealed' && !detail.ledger_entry_id && !detail.ledgerEntryId) {
        return;
      }
      const targetCaseId = detail.case_id ?? detail.caseId ?? detail.data?.case_id;
      if (targetCaseId && targetCaseId !== caseId) return;
      const ledgerEntryId =
        detail.ledger_entry_id ?? detail.ledgerEntryId ?? detail.data?.ledger_entry_id ?? '';
      setState({ phase: 'sealing', ledgerEntryId });
      const t = setTimeout(() => {
        setState({ phase: 'sealed', ledgerEntryId });
      }, _SEAL_ANIMATION_MS);
      return () => clearTimeout(t);
    };
    window.addEventListener('cockpit:decision-event', handler);
    window.addEventListener('cockpit:decision-sealed', handler);
    return () => {
      window.removeEventListener('cockpit:decision-event', handler);
      window.removeEventListener('cockpit:decision-sealed', handler);
    };
  }, [caseId]);

  return state;
}

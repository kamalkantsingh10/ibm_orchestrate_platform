// SealedIndicator — Story 7.6 / AC #4.
//
// Inline pill rendered in the Decision Zone footer once the case is
// committed. Click dispatches `cockpit:open-trace` so the
// route-level handler opens Story 6.6's reasoning-trace slide-out
// for the seal ledger entry. Mirrors the citation-token click pattern
// from Story 7.1's DecisionZone.

import type { KeyboardEvent } from 'react';

export interface SealedIndicatorProps {
  ledgerEntryId: string;
}

export function SealedIndicator({ ledgerEntryId }: SealedIndicatorProps) {
  const open = () =>
    window.dispatchEvent(
      new CustomEvent('cockpit:open-trace', { detail: { ledgerId: ledgerEntryId } }),
    );

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      open();
    }
  };

  return (
    <button
      type="button"
      onClick={open}
      onKeyDown={onKeyDown}
      data-testid="sealed-indicator"
      aria-label={`Sealed (ledger entry ${ledgerEntryId}); click to inspect`}
      className="inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-900 ring-1 ring-amber-200 hover:bg-amber-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
    >
      <span aria-hidden>●</span>
      <span>Sealed</span>
      <code className="font-mono text-[10px] text-amber-800">
        {ledgerEntryId.length > 12 ? `${ledgerEntryId.slice(0, 12)}…` : ledgerEntryId}
      </code>
    </button>
  );
}

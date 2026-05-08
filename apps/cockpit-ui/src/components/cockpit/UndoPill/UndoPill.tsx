// UndoPill — Story 7.5 / AC #4, #6.
//
// Pinned bottom-center while a decision sits in pending_seal.
// Click Undo → Radix Dialog modal requires reason ≥ 40 chars; on
// confirm POSTs to /v1/cases/{id}/decisions/{decision_id}/undo. The
// component unmounts itself by virtue of `useDecisionTimer` flipping
// to ``no-timer`` on the SSE event.

import * as Dialog from '@radix-ui/react-dialog';
import { AnimatePresence, motion } from 'framer-motion';
import { useState, type FormEvent } from 'react';
import { toast } from 'sonner';
import { useDecisionTimer } from '@/hooks/useDecisionTimer';
import { useCurrentUser } from '@/stores/currentUser';
import { CountdownRing } from './CountdownRing';

export interface UndoPillProps {
  caseId: string;
}

const _REASON_MIN = 40;

export function UndoPill({ caseId }: UndoPillProps) {
  const timer = useDecisionTimer(caseId);
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const isActive = timer.status === 'active';
  const remaining = isActive ? timer.remainingSeconds : 0;
  const total = isActive ? timer.windowSeconds : 0;
  const decisionId = isActive ? timer.decisionId : '';

  const handleConfirm = async (e?: FormEvent) => {
    e?.preventDefault();
    if (reason.length < _REASON_MIN) return;
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const userId = useCurrentUser.getState().user.id;
      const res = await fetch(
        `/v1/cases/${encodeURIComponent(caseId)}/decisions/${encodeURIComponent(decisionId)}/undo`,
        {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
            'X-Cockpit-Demo-User': userId,
          },
          body: JSON.stringify({ reason }),
        },
      );
      if (res.ok) {
        setOpen(false);
        setReason('');
        toast('Decision reverted.', { duration: 2500 });
        return;
      }
      if (res.status === 409) {
        setOpen(false);
        setReason('');
        toast('Decision already sealed; cannot undo.', { duration: 3500 });
        return;
      }
      const problem = (await res.json().catch(() => null)) as { detail?: string } | null;
      setSubmitError(problem?.detail ?? `Undo failed (${res.status})`);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Undo failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const canConfirm = reason.length >= _REASON_MIN && !isSubmitting;

  return (
    <>
      {/* Story 7.6 — AnimatePresence drives the exit choreography
         when the timer flips to no-timer (decision sealed or undone).
         The pill fades + drops 10px; the seal stamp on the Decision
         Zone enters during the same window so the two motions
         crossfade. */}
      <AnimatePresence>
        {isActive ? (
          <motion.div
            key="undo-pill"
            data-testid="undo-pill"
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 rounded-full bg-white px-4 py-2.5 shadow-lg ring-1 ring-zinc-200"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.3 }}
          >
            <CountdownRing remaining={remaining} total={total} />
            <span className="text-sm font-medium text-zinc-900">
              Decision committed · sealing in {Math.ceil(remaining)}s
            </span>
            <button
              type="button"
              onClick={() => setOpen(true)}
              data-testid="undo-pill-button"
              className="ml-1 rounded-full bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-700 hover:bg-rose-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400"
            >
              Undo
            </button>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
          <Dialog.Content className="fixed top-1/2 left-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-[480px] rounded-lg bg-white p-6 shadow-2xl">
            <Dialog.Title className="text-base font-semibold text-zinc-900">
              Undo this decision
            </Dialog.Title>
            <Dialog.Description className="mt-1 text-sm text-zinc-600">
              Tell me why — at least {_REASON_MIN} characters. The undo + reason become part of the
              audit ledger.
            </Dialog.Description>
            <form onSubmit={(e) => void handleConfirm(e)}>
              <textarea
                ref={(el) => {
                  // Imperative focus when the modal opens — preferred
                  // to the autoFocus prop per jsx-a11y. The modal
                  // opens via explicit user action so capturing focus
                  // is not surprising.
                  if (el && open) el.focus();
                }}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={4}
                className="mt-4 w-full rounded border border-zinc-300 p-2 text-sm font-sans focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-300"
                aria-label="Reason for undo"
                data-testid="undo-reason-input"
              />
              <div className="mt-2 flex justify-between text-xs text-zinc-500">
                <span>
                  {reason.length}/{_REASON_MIN} minimum
                </span>
              </div>
              {submitError ? (
                <p role="alert" className="mt-2 text-xs text-rose-700">
                  {submitError}
                </p>
              ) : null}
              <div className="mt-5 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="rounded px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!canConfirm}
                  data-testid="undo-confirm-button"
                  className="rounded bg-rose-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-rose-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSubmitting ? 'Reverting…' : 'Confirm Undo'}
                </button>
              </div>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}

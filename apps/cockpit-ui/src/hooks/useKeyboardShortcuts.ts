// Queue-route keyboard shortcuts — Story 4.2 (j/k/Enter/x/d/Esc).
// Mounted only in /queue. The cross-route bindings (⌘K, Cmd+1..6) live in
// useGlobalShortcuts so they fire on the case canvas too.
//
// Listens on window (capture phase). Bypassed when the active element is an
// input / textarea / contenteditable so typing doesn't trigger shortcuts.

import { useEffect } from 'react';
import { useNavigate } from '@tanstack/react-router';
import type { Case } from '@/lib/types/case';
import { useQueueFocus } from '@/stores/queueFocusStore';
import { useDoneFilter } from '@/stores/doneFilterStore';
import { useAnnouncer } from '@/stores/announcerStore';

export interface UseKeyboardShortcutsOptions {
  /** Currently visible queue rows (already filtered + ordered upstream). */
  cases: Case[];
  /** Open the defer popover anchored to the focused row. */
  onOpenDefer: () => void;
  /** True while the defer popover is open — Esc closes it instead of clearing focus. */
  isDeferOpen: boolean;
  /** Close the defer popover without selecting. */
  onCloseDefer: () => void;
}

function _isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (target.isContentEditable) return true;
  return false;
}

const _COMMITTED_STATES = new Set(['committed', 'closed']);

export function useKeyboardShortcuts({
  cases,
  onOpenDefer,
  isDeferOpen,
  onCloseDefer,
}: UseKeyboardShortcutsOptions): void {
  const navigate = useNavigate();
  const { focusedIndex, setFocus, clearFocus } = useQueueFocus();
  const announce = useAnnouncer((s) => s.announce);
  const markDone = useDoneFilter((s) => s.markDone);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't fire shortcuts when typing into a field. The defer popover's
      // Cancel/options ARE buttons, not inputs — those are fine.
      if (_isTypingTarget(e.target)) return;

      // Esc — close popover if open, else clear focus.
      if (e.key === 'Escape') {
        if (isDeferOpen) {
          e.preventDefault();
          onCloseDefer();
          return;
        }
        if (focusedIndex >= 0) {
          e.preventDefault();
          clearFocus();
        }
        return;
      }

      // No bindings while popover is open (radio selection inside the popover
      // is separate; arrow-key handling is Radix's job).
      if (isDeferOpen) return;

      if (cases.length === 0) return;

      switch (e.key) {
        case 'j': {
          e.preventDefault();
          const next = Math.min(cases.length - 1, focusedIndex < 0 ? 0 : focusedIndex + 1);
          const target = cases[next];
          if (target) {
            setFocus(target.id, next);
            announce(`Focused: ${target.customer_metadata.customer_name}`);
          }
          break;
        }
        case 'k': {
          e.preventDefault();
          const next = Math.max(0, focusedIndex < 0 ? 0 : focusedIndex - 1);
          const target = cases[next];
          if (target) {
            setFocus(target.id, next);
            announce(`Focused: ${target.customer_metadata.customer_name}`);
          }
          break;
        }
        case 'Enter': {
          if (focusedIndex < 0) break;
          const target = cases[focusedIndex];
          if (!target) break;
          e.preventDefault();
          announce(`Opened case ${target.customer_metadata.customer_name}`);
          clearFocus();
          void navigate({ to: '/cases/$caseId', params: { caseId: target.id } });
          break;
        }
        case 'x': {
          if (focusedIndex < 0) break;
          e.preventDefault();
          onOpenDefer();
          break;
        }
        case 'd': {
          if (focusedIndex < 0) break;
          const target = cases[focusedIndex];
          if (!target) break;
          if (!_COMMITTED_STATES.has(String(target.state))) {
            e.preventDefault();
            announce(
              `Cannot mark done — ${target.customer_metadata.customer_name} is not committed`,
            );
            break;
          }
          e.preventDefault();
          markDone(target.id);
          announce(`Marked ${target.customer_metadata.customer_name} done in your view`);
          break;
        }
      }
    };

    window.addEventListener('keydown', handler, { capture: true });
    return () => window.removeEventListener('keydown', handler, { capture: true });
  }, [
    cases,
    focusedIndex,
    setFocus,
    clearFocus,
    announce,
    markDone,
    navigate,
    isDeferOpen,
    onOpenDefer,
    onCloseDefer,
  ]);
}

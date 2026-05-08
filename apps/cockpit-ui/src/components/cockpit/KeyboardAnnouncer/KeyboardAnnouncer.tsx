// KeyboardAnnouncer — Story 4.2 AC #7.
//
// Visually-hidden aria-live=polite span. The keyboard shortcut hook writes
// to ``announcerStore``; this component renders the message and clears it
// after 3 s so the screen reader doesn't re-read a stale string.

import { useEffect } from 'react';
import { useAnnouncer } from '@/stores/announcerStore';

const _AUTO_CLEAR_MS = 3000;

export function KeyboardAnnouncer(): JSX.Element {
  const message = useAnnouncer((s) => s.message);
  const clear = useAnnouncer((s) => s.clear);

  useEffect(() => {
    if (!message) return;
    const id = window.setTimeout(clear, _AUTO_CLEAR_MS);
    return () => window.clearTimeout(id);
  }, [message, clear]);

  return (
    <span
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className="sr-only"
      data-testid="keyboard-announcer"
    >
      {message}
    </span>
  );
}

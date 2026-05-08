// Live-region announcer — Story 4.2 AC #7.
//
// One global string consumed by KeyboardAnnouncer's aria-live=polite node.
// Hook actions push human-readable strings ("Focused: Vora …", "Opened case
// …", "Marked … done"). Messages auto-clear after 3 s so the SR doesn't
// re-read a stale string on the next focus event.

import { create } from 'zustand';

interface AnnouncerState {
  message: string;
  announce: (msg: string) => void;
  clear: () => void;
}

export const useAnnouncer = create<AnnouncerState>((set) => ({
  message: '',
  announce: (msg) => set({ message: msg }),
  clear: () => set({ message: '' }),
}));

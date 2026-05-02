// Active demo user — Zustand store with localStorage persistence (Story 1.4 AC #4).
//
// The user-switcher dropdown is the only writer; every other consumer reads.
// Persistence keeps the same role on browser refresh during a demo.

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { DEMO_USERS, type User } from '@/lib/demoUsers';

interface CurrentUserState {
  user: User;
  setUser: (user: User) => void;
}

const STORAGE_KEY = 'cockpit-current-user';
// DEMO_USERS is a const tuple of length 3; index 0 is the analyst (Kamal).
const ANALYST = DEMO_USERS.find((u) => u.role === 'analyst');
if (!ANALYST) {
  throw new Error('Invariant violated: DEMO_USERS must contain an analyst.');
}

export const useCurrentUser = create<CurrentUserState>()(
  persist(
    (set) => ({
      user: ANALYST,
      setUser: (user) => set({ user }),
    }),
    { name: STORAGE_KEY },
  ),
);

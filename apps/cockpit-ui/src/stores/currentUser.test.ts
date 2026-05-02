// Unit tests for the currentUser Zustand store (Story 1.4 AC #4).

import { beforeEach, describe, expect, it } from 'vitest';
import { useCurrentUser } from './currentUser';
import { DEMO_USERS } from '@/lib/demoUsers';

describe('useCurrentUser', () => {
  beforeEach(() => {
    localStorage.clear();
    // Reset to analyst between tests so persistence doesn't leak state.
    const analyst = DEMO_USERS.find((u) => u.role === 'analyst');
    if (analyst) useCurrentUser.setState({ user: analyst });
  });

  it('initializes to the analyst on first load', () => {
    const { user } = useCurrentUser.getState();
    expect(user.role).toBe('analyst');
    expect(user.name).toBe('Kamal Singh');
  });

  it('updates the active user when setUser is called', () => {
    const lead = DEMO_USERS.find((u) => u.role === 'team_lead')!;
    useCurrentUser.getState().setUser(lead);
    expect(useCurrentUser.getState().user.role).toBe('team_lead');
  });

  it('persists the active user to localStorage', () => {
    const regulator = DEMO_USERS.find((u) => u.role === 'regulator')!;
    useCurrentUser.getState().setUser(regulator);
    const stored = localStorage.getItem('cockpit-current-user');
    expect(stored).toContain('regulator');
  });
});

// Component tests for UserSwitcher (Story 1.4 AC #2, #10, #13, #14).

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { UserSwitcher } from './UserSwitcher';
import { DEMO_USERS } from '@/lib/types/user';
import { useCurrentUser } from '@/stores/currentUser';

const navigateMock = vi.fn();

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => navigateMock,
}));

describe('UserSwitcher', () => {
  beforeEach(() => {
    localStorage.clear();
    navigateMock.mockReset();
    const analyst = DEMO_USERS.find((u) => u.role === 'analyst')!;
    useCurrentUser.setState({ user: analyst });
  });

  it('renders the active user in the trigger', () => {
    render(<UserSwitcher />);
    // Trigger has aria-label naming the current user.
    expect(screen.getByRole('button', { name: /Kamal Singh/ })).toBeInTheDocument();
  });

  it('shows three options when opened', async () => {
    const user = userEvent.setup();
    render(<UserSwitcher />);
    await user.click(screen.getByRole('button', { name: /Kamal Singh/ }));
    expect(screen.getByRole('menuitem', { name: /Kamal Singh/ })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /Rohan Mehta/ })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /Anika Iyer/ })).toBeInTheDocument();
  });

  it('switches user and navigates to that role default route on select', async () => {
    const user = userEvent.setup();
    render(<UserSwitcher />);
    await user.click(screen.getByRole('button', { name: /Kamal Singh/ }));
    await user.click(screen.getByRole('menuitem', { name: /Rohan Mehta/ }));

    expect(useCurrentUser.getState().user.role).toBe('team_lead');
    expect(navigateMock).toHaveBeenCalledWith({ to: '/approvals' });
  });

  it('announces the switch via the aria-live region', async () => {
    const user = userEvent.setup();
    render(<UserSwitcher />);
    await user.click(screen.getByRole('button', { name: /Kamal Singh/ }));
    await user.click(screen.getByRole('menuitem', { name: /Anika Iyer/ }));

    expect(screen.getByRole('status').textContent).toMatch(/Switched to Anika Iyer, Regulator/);
  });

  it('does not navigate when the active user is re-selected', async () => {
    const user = userEvent.setup();
    render(<UserSwitcher />);
    await user.click(screen.getByRole('button', { name: /Kamal Singh/ }));
    await user.click(screen.getByRole('menuitem', { name: /Kamal Singh/ }));

    expect(navigateMock).not.toHaveBeenCalled();
  });
});

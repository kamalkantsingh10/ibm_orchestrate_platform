// UndoPill tests — Story 7.5 / AC #10.

import type { ReactNode } from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const { useDecisionTimerMock, toastMock } = vi.hoisted(() => ({
  useDecisionTimerMock: vi.fn(),
  toastMock: vi.fn(),
}));

vi.mock('@/hooks/useDecisionTimer', () => ({
  useDecisionTimer: useDecisionTimerMock,
}));
vi.mock('sonner', () => ({
  toast: toastMock,
}));

import { UndoPill } from './UndoPill';
import { useCurrentUser } from '@/stores/currentUser';
import { DEMO_USERS } from '@/lib/demoUsers';

const CASE_ID = 'case_01HZ7ZK4G7EXAMPLE0000000DD';

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

beforeEach(() => {
  const analyst = DEMO_USERS.find((u) => u.role === 'analyst')!;
  useCurrentUser.setState({ user: analyst });
  useDecisionTimerMock.mockReset();
  toastMock.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('UndoPill', () => {
  it('renders nothing when timer is no-timer', () => {
    useDecisionTimerMock.mockReturnValue({ status: 'no-timer' });
    const { container } = render(<UndoPill caseId={CASE_ID} />, { wrapper: makeWrapper() });
    expect(container.firstChild).toBeNull();
  });

  it('renders the pill with countdown when active', () => {
    useDecisionTimerMock.mockReturnValue({
      status: 'active',
      decisionId: 'dec_test_777',
      remainingSeconds: 90,
      windowSeconds: 120,
    });
    render(<UndoPill caseId={CASE_ID} />, { wrapper: makeWrapper() });
    expect(screen.getByTestId('undo-pill')).toBeInTheDocument();
    expect(screen.getByTestId('countdown-ring')).toBeInTheDocument();
    expect(screen.getByText(/sealing in 90s/i)).toBeInTheDocument();
  });

  it('shows ceil(remainingSeconds) in the countdown text', () => {
    useDecisionTimerMock.mockReturnValue({
      status: 'active',
      decisionId: 'dec_x',
      remainingSeconds: 89.4,
      windowSeconds: 120,
    });
    render(<UndoPill caseId={CASE_ID} />, { wrapper: makeWrapper() });
    expect(screen.getByText(/sealing in 90s/)).toBeInTheDocument();
  });

  it('CountdownRing flips to urgent at the 30-second threshold', () => {
    useDecisionTimerMock.mockReturnValue({
      status: 'active',
      decisionId: 'dec_x',
      remainingSeconds: 29,
      windowSeconds: 120,
    });
    render(<UndoPill caseId={CASE_ID} />, { wrapper: makeWrapper() });
    const ring = screen.getByTestId('countdown-ring');
    expect(ring.dataset.urgent).toBe('true');
  });

  it('CountdownRing is not urgent above 30 seconds', () => {
    useDecisionTimerMock.mockReturnValue({
      status: 'active',
      decisionId: 'dec_x',
      remainingSeconds: 60,
      windowSeconds: 120,
    });
    render(<UndoPill caseId={CASE_ID} />, { wrapper: makeWrapper() });
    expect(screen.getByTestId('countdown-ring').dataset.urgent).toBe('false');
  });

  it('clicking Undo opens the modal', () => {
    useDecisionTimerMock.mockReturnValue({
      status: 'active',
      decisionId: 'dec_x',
      remainingSeconds: 90,
      windowSeconds: 120,
    });
    render(<UndoPill caseId={CASE_ID} />, { wrapper: makeWrapper() });
    fireEvent.click(screen.getByTestId('undo-pill-button'));
    expect(screen.getByText('Undo this decision')).toBeInTheDocument();
  });

  it('Confirm button is disabled when reason is below 40 characters', () => {
    useDecisionTimerMock.mockReturnValue({
      status: 'active',
      decisionId: 'dec_x',
      remainingSeconds: 90,
      windowSeconds: 120,
    });
    render(<UndoPill caseId={CASE_ID} />, { wrapper: makeWrapper() });
    fireEvent.click(screen.getByTestId('undo-pill-button'));
    fireEvent.change(screen.getByTestId('undo-reason-input'), {
      target: { value: 'short' },
    });
    expect(screen.getByTestId('undo-confirm-button')).toBeDisabled();
  });

  it('Confirm button is enabled when reason is 40+ characters', () => {
    useDecisionTimerMock.mockReturnValue({
      status: 'active',
      decisionId: 'dec_x',
      remainingSeconds: 90,
      windowSeconds: 120,
    });
    render(<UndoPill caseId={CASE_ID} />, { wrapper: makeWrapper() });
    fireEvent.click(screen.getByTestId('undo-pill-button'));
    fireEvent.change(screen.getByTestId('undo-reason-input'), {
      target: { value: 'a'.repeat(40) },
    });
    expect(screen.getByTestId('undo-confirm-button')).not.toBeDisabled();
  });

  it('Confirm POSTs to /undo with the reason body', async () => {
    useDecisionTimerMock.mockReturnValue({
      status: 'active',
      decisionId: 'dec_undo',
      remainingSeconds: 90,
      windowSeconds: 120,
    });
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        case_id: CASE_ID,
        decision_id: 'dec_undo',
        case_state: 'decision_ready',
        ledger_entry_id: 'led_01ABCDEFGHJKMNPQRSTVWXYZ12',
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    render(<UndoPill caseId={CASE_ID} />, { wrapper: makeWrapper() });
    fireEvent.click(screen.getByTestId('undo-pill-button'));
    const reasonText = 'Officer realized the OFAC hit needed more review.';
    fireEvent.change(screen.getByTestId('undo-reason-input'), {
      target: { value: reasonText },
    });
    await act(async () => {
      fireEvent.click(screen.getByTestId('undo-confirm-button'));
    });
    expect(fetchMock).toHaveBeenCalled();
    const url = fetchMock.mock.calls[0]?.[0] as string;
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(url).toContain(`/v1/cases/${CASE_ID}/decisions/dec_undo/undo`);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string).reason).toBe(reasonText);
  });

  it('200 response closes the modal and toasts', async () => {
    useDecisionTimerMock.mockReturnValue({
      status: 'active',
      decisionId: 'dec_undo',
      remainingSeconds: 90,
      windowSeconds: 120,
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ ok: true })));
    render(<UndoPill caseId={CASE_ID} />, { wrapper: makeWrapper() });
    fireEvent.click(screen.getByTestId('undo-pill-button'));
    fireEvent.change(screen.getByTestId('undo-reason-input'), {
      target: { value: 'a'.repeat(50) },
    });
    await act(async () => {
      fireEvent.click(screen.getByTestId('undo-confirm-button'));
    });
    expect(toastMock).toHaveBeenCalledWith('Decision reverted.', expect.any(Object));
  });

  it('409 response closes modal + toasts already-sealed', async () => {
    useDecisionTimerMock.mockReturnValue({
      status: 'active',
      decisionId: 'dec_undo',
      remainingSeconds: 90,
      windowSeconds: 120,
    });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'already sealed' }, 409)),
    );
    render(<UndoPill caseId={CASE_ID} />, { wrapper: makeWrapper() });
    fireEvent.click(screen.getByTestId('undo-pill-button'));
    fireEvent.change(screen.getByTestId('undo-reason-input'), {
      target: { value: 'a'.repeat(50) },
    });
    await act(async () => {
      fireEvent.click(screen.getByTestId('undo-confirm-button'));
    });
    expect(toastMock).toHaveBeenCalledWith(
      'Decision already sealed; cannot undo.',
      expect.any(Object),
    );
  });

  it('CountdownRing has motion-reduce:transition-none class for accessibility', () => {
    useDecisionTimerMock.mockReturnValue({
      status: 'active',
      decisionId: 'dec_x',
      remainingSeconds: 90,
      windowSeconds: 120,
    });
    render(<UndoPill caseId={CASE_ID} />, { wrapper: makeWrapper() });
    const ring = screen.getByTestId('countdown-ring');
    expect(ring.getAttribute('class')).toMatch(/motion-reduce:transition-none/);
  });
});

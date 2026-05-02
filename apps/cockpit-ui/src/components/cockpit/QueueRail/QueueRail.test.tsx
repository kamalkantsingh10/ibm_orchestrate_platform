// QueueRail component tests — Story 2.3 / AC #10.

import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { QueueRail } from './QueueRail';
import type { Case, CaseState } from '@/lib/types/case';
import { CASE_STATE_BADGES } from '@/lib/caseState';

function makeCase(overrides: Partial<Case> = {}): Case {
  const id =
    overrides.id ??
    `case_01HZ${Math.random().toString(36).slice(2, 8).toUpperCase().padEnd(22, 'A')}`;
  return {
    id,
    state: 'intake_scheduled',
    customer_metadata: { customer_name: 'Acme Pte Ltd', extra: {} },
    assigned_to_user_id: null,
    risk_band: null,
    created_at: '2026-04-30T11:55:00Z',
    updated_at: '2026-04-30T11:55:00Z',
    closure_date: null,
    _links: { documents: null, reasoning_traces: null },
    ...overrides,
  };
}

describe('QueueRail', () => {
  it('renders the empty-state copy when cases is []', () => {
    render(<QueueRail cases={[]} />);
    expect(screen.getByText('No cases yet.')).toBeInTheDocument();
    expect(screen.getByText(/make seed/)).toBeInTheDocument();
  });

  it('renders 4 skeleton placeholders while pending with no cases', () => {
    render(<QueueRail cases={[]} isPending />);
    const skeleton = screen.getByTestId('queue-rail-skeleton');
    expect(skeleton.children).toHaveLength(4);
  });

  it('renders an alert + retry button on error', async () => {
    const onRetry = vi.fn();
    render(<QueueRail cases={[]} isError onRetry={onRetry} />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it('renders rows in the order received (no client-side sort)', () => {
    const cases: Case[] = [
      makeCase({
        id: 'case_01HZ7ZK4G7AAAAAAAAAAAAAAAA',
        customer_metadata: { customer_name: 'First', extra: {} },
      }),
      makeCase({
        id: 'case_01HZ7ZK4G7BBBBBBBBBBBBBBBB',
        customer_metadata: { customer_name: 'Second', extra: {} },
      }),
    ];
    render(<QueueRail cases={cases} />);
    const labels = screen.getAllByRole('button').map((b) => b.textContent ?? '');
    expect(labels[0]).toContain('First');
    expect(labels[1]).toContain('Second');
  });

  it('each row renders customer name, relative time, and state badge', () => {
    const cases = [makeCase({ created_at: '2026-04-30T11:55:00Z', state: 'decision_ready' })];
    const now = new Date('2026-04-30T12:00:00Z');
    vi.setSystemTime(now);
    try {
      render(<QueueRail cases={cases} />);
      expect(screen.getByText('Acme Pte Ltd')).toBeInTheDocument();
      expect(screen.getByText('5 minutes ago')).toBeInTheDocument();
      expect(screen.getByText('Ready')).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it.each(Object.entries(CASE_STATE_BADGES))('maps %s to its humanized label', (state, badge) => {
    const cases = [makeCase({ state: state as CaseState })];
    render(<QueueRail cases={cases} />);
    expect(screen.getByText(badge.label)).toBeInTheDocument();
  });

  it('clicking a row calls onSelect with the case id', async () => {
    const onSelect = vi.fn();
    const c = makeCase({ id: 'case_01HZ7ZK4G7CCCCCCCCCCCCCCCC' });
    render(<QueueRail cases={[c]} onSelect={onSelect} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button'));
    expect(onSelect).toHaveBeenCalledWith(c.id);
  });
});

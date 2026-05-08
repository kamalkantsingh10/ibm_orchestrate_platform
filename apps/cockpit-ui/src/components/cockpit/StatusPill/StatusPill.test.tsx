// StatusPill tests — Story 4.9 AC #8.

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusPill, type StatusPillState } from './StatusPill';

const STATES: StatusPillState[] = ['done', 'in-progress', 'blocked', 'needs-input'];
const DEFAULT_LABELS: Record<StatusPillState, string> = {
  done: 'Done',
  'in-progress': 'In progress',
  blocked: 'Blocked',
  'needs-input': 'Needs input',
};

describe('StatusPill', () => {
  it.each(STATES)('renders for state=%s with default label + data-attr', (state) => {
    const { container } = render(<StatusPill state={state} />);
    expect(container.querySelector(`[data-status-state="${state}"]`)).toBeInTheDocument();
    expect(screen.getByText(DEFAULT_LABELS[state])).toBeInTheDocument();
  });

  it.each(STATES)('default aria-label for state=%s names the status', (state) => {
    render(<StatusPill state={state} />);
    expect(screen.getByLabelText(`${DEFAULT_LABELS[state]} — agent status`)).toBeInTheDocument();
  });

  it('custom label overrides default text', () => {
    render(<StatusPill state="done" label="Shipped" />);
    expect(screen.getByText('Shipped')).toBeInTheDocument();
  });

  it('custom aria-label wins', () => {
    render(<StatusPill state="done" aria-label="Document Intelligence — Done" />);
    expect(screen.getByLabelText('Document Intelligence — Done')).toBeInTheDocument();
  });

  it('renders icon SVGs for every state', () => {
    for (const state of STATES) {
      const { container, unmount } = render(<StatusPill state={state} />);
      expect(container.querySelector('svg')).toBeInTheDocument();
      unmount();
    }
  });

  it('size=md applies the larger sizing classes', () => {
    const { container } = render(<StatusPill state="done" size="md" />);
    const node = container.querySelector('[data-status-state="done"]');
    expect(node?.className).toContain('px-2');
    expect(node?.className).toContain('py-1');
  });

  it('size=sm (default) applies the smaller sizing classes', () => {
    const { container } = render(<StatusPill state="done" />);
    const node = container.querySelector('[data-status-state="done"]');
    expect(node?.className).toContain('px-1.5');
  });
});

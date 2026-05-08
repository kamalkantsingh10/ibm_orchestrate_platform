// SealedIndicator tests — Story 7.6 / AC #10.

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { SealedIndicator } from './SealedIndicator';

const LED_ID = 'led_01ABCDEFGHJKMNPQRSTVWXYZ12';

describe('SealedIndicator', () => {
  it('renders truncated ledger id and Sealed label', () => {
    render(<SealedIndicator ledgerEntryId={LED_ID} />);
    expect(screen.getByText('Sealed')).toBeInTheDocument();
    // Truncated to first 12 chars + ellipsis (led_01ABCDEF…).
    expect(screen.getByTestId('sealed-indicator').textContent).toContain('led_01ABCDEF');
    expect(screen.getByTestId('sealed-indicator').textContent).toContain('…');
  });

  it('click dispatches the cockpit:open-trace custom event with the ledger id', () => {
    const listener = vi.fn();
    window.addEventListener('cockpit:open-trace', listener as EventListener);
    render(<SealedIndicator ledgerEntryId={LED_ID} />);
    fireEvent.click(screen.getByTestId('sealed-indicator'));
    expect(listener).toHaveBeenCalled();
    const evt = listener.mock.calls[0]?.[0] as CustomEvent<{ ledgerId: string }>;
    expect(evt.detail.ledgerId).toBe(LED_ID);
    window.removeEventListener('cockpit:open-trace', listener as EventListener);
  });

  it('Enter key activates the indicator', () => {
    const listener = vi.fn();
    window.addEventListener('cockpit:open-trace', listener as EventListener);
    render(<SealedIndicator ledgerEntryId={LED_ID} />);
    fireEvent.keyDown(screen.getByTestId('sealed-indicator'), { key: 'Enter' });
    expect(listener).toHaveBeenCalled();
    window.removeEventListener('cockpit:open-trace', listener as EventListener);
  });

  it('Space key activates the indicator', () => {
    const listener = vi.fn();
    window.addEventListener('cockpit:open-trace', listener as EventListener);
    render(<SealedIndicator ledgerEntryId={LED_ID} />);
    fireEvent.keyDown(screen.getByTestId('sealed-indicator'), { key: ' ' });
    expect(listener).toHaveBeenCalled();
    window.removeEventListener('cockpit:open-trace', listener as EventListener);
  });
});

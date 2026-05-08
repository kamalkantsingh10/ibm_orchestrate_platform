// KeyboardAnnouncer tests — Story 4.2 AC #9.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { KeyboardAnnouncer } from './KeyboardAnnouncer';
import { useAnnouncer } from '@/stores/announcerStore';

describe('KeyboardAnnouncer', () => {
  beforeEach(() => {
    useAnnouncer.getState().clear();
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders an aria-live polite status node', () => {
    render(<KeyboardAnnouncer />);
    const node = screen.getByTestId('keyboard-announcer');
    expect(node).toHaveAttribute('role', 'status');
    expect(node).toHaveAttribute('aria-live', 'polite');
    expect(node).toHaveAttribute('aria-atomic', 'true');
  });

  it('renders the announcer message', () => {
    render(<KeyboardAnnouncer />);
    act(() => {
      useAnnouncer.getState().announce('Focused: Vora Capital Holdings');
    });
    expect(screen.getByTestId('keyboard-announcer')).toHaveTextContent(
      'Focused: Vora Capital Holdings',
    );
  });

  it('auto-clears the message after 3s', () => {
    render(<KeyboardAnnouncer />);
    act(() => {
      useAnnouncer.getState().announce('Hello');
    });
    expect(screen.getByTestId('keyboard-announcer')).toHaveTextContent('Hello');
    act(() => {
      vi.advanceTimersByTime(3001);
    });
    expect(screen.getByTestId('keyboard-announcer').textContent).toBe('');
  });
});

// useKeyboardShortcuts tests — Story 4.2 AC #9.

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render } from '@testing-library/react';
import { useKeyboardShortcuts } from './useKeyboardShortcuts';
import type { Case } from '@/lib/types/case';
import { useQueueFocus } from '@/stores/queueFocusStore';
import { useDoneFilter } from '@/stores/doneFilterStore';
import { useAnnouncer } from '@/stores/announcerStore';

const navigateMock = vi.fn();
const toastMock = vi.fn();
vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => navigateMock,
}));
vi.mock('sonner', () => ({
  toast: (...args: unknown[]) => toastMock(...args),
}));

function makeCase(name: string, id: string, state: Case['state'] = 'intake_scheduled'): Case {
  return {
    id,
    state,
    customer_metadata: { customer_name: name, extra: {} },
    assigned_to_user_id: null,
    risk_band: null,
    created_at: '2026-04-30T11:55:00Z',
    updated_at: '2026-04-30T11:55:00Z',
    closure_date: null,
    _links: { documents: null, reasoning_traces: null },
  };
}

interface HarnessProps {
  cases: Case[];
  isDeferOpen?: boolean;
  onOpenDefer?: () => void;
  onCloseDefer?: () => void;
}

function Harness({
  cases,
  isDeferOpen = false,
  onOpenDefer = () => {},
  onCloseDefer = () => {},
}: HarnessProps) {
  useKeyboardShortcuts({ cases, isDeferOpen, onOpenDefer, onCloseDefer });
  return null;
}

function press(key: string, modifiers: KeyboardEventInit = {}): void {
  act(() => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, ...modifiers }));
  });
}

function setFocus(caseId: string, index: number): void {
  act(() => {
    useQueueFocus.getState().setFocus(caseId, index);
  });
}

const cases: Case[] = [
  makeCase('Alpha', 'case_a'),
  makeCase('Bravo', 'case_b'),
  makeCase('Charlie', 'case_c'),
];

describe('useKeyboardShortcuts', () => {
  beforeEach(() => {
    useQueueFocus.getState().clearFocus();
    useDoneFilter.getState().reset();
    useAnnouncer.getState().clear();
    navigateMock.mockReset();
    toastMock.mockReset();
  });

  it('j moves focus to next, clamped at last', () => {
    render(<Harness cases={cases} />);
    press('j');
    expect(useQueueFocus.getState().focusedIndex).toBe(0);
    press('j');
    expect(useQueueFocus.getState().focusedIndex).toBe(1);
    press('j');
    press('j'); // clamped at 2
    expect(useQueueFocus.getState().focusedIndex).toBe(2);
  });

  it('k moves focus back, clamped at first', () => {
    render(<Harness cases={cases} />);
    setFocus('case_c', 2);
    press('k');
    expect(useQueueFocus.getState().focusedIndex).toBe(1);
    press('k');
    press('k'); // clamped at 0
    expect(useQueueFocus.getState().focusedIndex).toBe(0);
  });

  it('Enter navigates to the focused case canvas', () => {
    render(<Harness cases={cases} />);
    setFocus('case_b', 1);
    press('Enter');
    expect(navigateMock).toHaveBeenCalledWith({
      to: '/cases/$caseId',
      params: { caseId: 'case_b' },
    });
    expect(useQueueFocus.getState().focusedIndex).toBe(-1); // cleared
  });

  it('x calls onOpenDefer when a row is focused', () => {
    const onOpenDefer = vi.fn();
    render(<Harness cases={cases} onOpenDefer={onOpenDefer} />);
    setFocus('case_a', 0);
    press('x');
    expect(onOpenDefer).toHaveBeenCalledOnce();
  });

  it('d on a non-committed case is a no-op + announces "cannot"', () => {
    render(<Harness cases={cases} />);
    setFocus('case_a', 0);
    press('d');
    expect(useDoneFilter.getState().doneCaseIds.has('case_a')).toBe(false);
    expect(useAnnouncer.getState().message).toMatch(/cannot/i);
  });

  it('d marks done when the case is committed', () => {
    const committed = [makeCase('Done', 'case_done', 'committed')];
    render(<Harness cases={committed} />);
    setFocus('case_done', 0);
    press('d');
    expect(useDoneFilter.getState().doneCaseIds.has('case_done')).toBe(true);
  });

  it('Esc closes the defer popover when open', () => {
    const onCloseDefer = vi.fn();
    render(<Harness cases={cases} isDeferOpen onCloseDefer={onCloseDefer} />);
    press('Escape');
    expect(onCloseDefer).toHaveBeenCalledOnce();
  });

  it('Esc clears focus when the popover is closed', () => {
    render(<Harness cases={cases} />);
    setFocus('case_a', 0);
    press('Escape');
    expect(useQueueFocus.getState().focusedIndex).toBe(-1);
  });

  // Cmd+K and Cmd+1..6 bindings now live in `useGlobalShortcuts` (mounted
  // in __root.tsx so they fire on every route, including the case canvas).
  // See `useGlobalShortcuts.test.tsx` for those cases.

  it('does not fire when an input is focused', () => {
    render(
      <>
        <Harness cases={cases} />
        <input data-testid="text-input" />
      </>,
    );
    const input = document.querySelector<HTMLInputElement>('[data-testid="text-input"]')!;
    input.focus();
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'j', bubbles: true }));
    expect(useQueueFocus.getState().focusedIndex).toBe(-1);
  });
});

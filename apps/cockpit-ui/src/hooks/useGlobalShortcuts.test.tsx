// useGlobalShortcuts tests — Stories 4.7 / 4.8.

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render } from '@testing-library/react';
import { useGlobalShortcuts } from './useGlobalShortcuts';
import { useMode } from '@/stores/modeStore';
import { usePalette } from '@/stores/paletteStore';

const toastMock = vi.fn();
vi.mock('sonner', () => ({
  toast: (...args: unknown[]) => toastMock(...args),
}));

function Harness() {
  useGlobalShortcuts();
  return null;
}

function press(key: string, modifiers: KeyboardEventInit = {}): void {
  act(() => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, ...modifiers }));
  });
}

describe('useGlobalShortcuts', () => {
  beforeEach(() => {
    useMode.getState().setMode('investigation');
    usePalette.getState().setOpen(false);
    toastMock.mockReset();
  });

  it('Cmd+K toggles the command palette', () => {
    render(<Harness />);
    press('k', { metaKey: true });
    expect(usePalette.getState().open).toBe(true);
    press('k', { metaKey: true });
    expect(usePalette.getState().open).toBe(false);
  });

  it('Ctrl+K also toggles the palette (non-Mac)', () => {
    render(<Harness />);
    press('k', { ctrlKey: true });
    expect(usePalette.getState().open).toBe(true);
  });

  it('Cmd+K bypasses input-focus guard so the toggle works from inside any input', () => {
    render(
      <>
        <Harness />
        <input data-testid="text-input" />
      </>,
    );
    const input = document.querySelector<HTMLInputElement>('[data-testid="text-input"]')!;
    input.focus();
    act(() => {
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }));
    });
    expect(usePalette.getState().open).toBe(true);
  });

  it('Cmd+1 sets investigation mode', () => {
    useMode.getState().setMode('zen');
    render(<Harness />);
    press('1', { metaKey: true });
    expect(useMode.getState().mode).toBe('investigation');
  });

  it('Cmd+2 toasts "not yet available" without changing mode', () => {
    render(<Harness />);
    press('2', { metaKey: true });
    expect(toastMock).toHaveBeenCalled();
    expect(useMode.getState().mode).toBe('investigation');
  });

  it('plain "1" without modifier does nothing', () => {
    useMode.getState().setMode('zen');
    render(<Harness />);
    press('1');
    expect(useMode.getState().mode).toBe('zen');
  });

  it('Cmd+1 does not fire when an input is focused', () => {
    useMode.getState().setMode('zen');
    render(
      <>
        <Harness />
        <input data-testid="ti" />
      </>,
    );
    const input = document.querySelector<HTMLInputElement>('[data-testid="ti"]')!;
    input.focus();
    act(() => {
      input.dispatchEvent(new KeyboardEvent('keydown', { key: '1', metaKey: true, bubbles: true }));
    });
    expect(useMode.getState().mode).toBe('zen');
  });

  it('Cmd+Shift+D focuses the Decision Zone target when present (Story 7.2)', () => {
    render(
      <>
        <Harness />
        <div data-decision-zone-focus-target>
          <div contentEditable suppressContentEditableWarning data-testid="dz-editor">
            rationale
          </div>
        </div>
      </>,
    );
    press('d', { metaKey: true, shiftKey: true });
    const editor = document.querySelector<HTMLElement>('[data-testid="dz-editor"]')!;
    expect(document.activeElement).toBe(editor);
  });

  it('Cmd+Shift+D is a no-op when no Decision Zone target is mounted', () => {
    render(<Harness />);
    expect(() => press('d', { metaKey: true, shiftKey: true })).not.toThrow();
    // No focus change — body remains the active element.
    expect(document.activeElement).toBe(document.body);
  });
});

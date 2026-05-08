// ZenMode tests — Story 8.2 AC #8.

import { beforeEach, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { useMode } from '@/stores/modeStore';
import { ZenMode } from './ZenMode';

function FakeEditor() {
  return <div data-testid="fake-editor">Rationale draft</div>;
}

describe('ZenMode', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/');
    useMode.getState().setMode('investigation');
  });

  it('applies_data_mode_zen_to_root_when_mode_is_zen', () => {
    // Switching the store flips the mode value to `zen`. The ZenMode
    // wrapper carries `data-mode="zen"` so global CSS rules under that
    // selector activate (AC #1).
    useMode.getState().setMode('zen');
    expect(useMode.getState().mode).toBe('zen');

    render(
      <ZenMode caseId="case-001">
        <FakeEditor />
      </ZenMode>,
    );
    const root = screen.getByTestId('zen-mode-root');
    expect(root.getAttribute('data-mode')).toBe('zen');
  });

  it('tiptap_editor_renders_at_720px_max_width', () => {
    // AC #2 — the editor frame caps at 720px and uses the serif face.
    render(
      <ZenMode caseId="case-001">
        <FakeEditor />
      </ZenMode>,
    );
    const frame = screen.getByTestId('zen-editor-frame');
    expect(frame.style.maxWidth).toBe('720px');
    expect(frame.style.minHeight).toBe('75vh');
    expect(frame.className).toMatch(/font-serif/);
    // Editor slot renders inside the frame.
    expect(frame.contains(screen.getByTestId('fake-editor'))).toBe(true);
  });

  it('evidenceshelf_dock_renders_placeholder_when_8_5_not_implemented', () => {
    // AC #3 — until Story 8.5 lands, the dock shows a placeholder row.
    render(
      <ZenMode caseId="case-001">
        <FakeEditor />
      </ZenMode>,
    );
    const dock = screen.getByTestId('zen-evidence-dock');
    expect(dock).toBeInTheDocument();
    expect(screen.getByTestId('zen-evidence-dock-placeholder').textContent).toBe(
      'Evidence shelf — ships in Story 8.5',
    );
  });

  it('status_bar_and_drawer_hidden_in_zen', () => {
    // AC #5 — the bottom-ribbon footer (Epic 12 status bar's
    // current placeholder) must not render under the Zen canvas. ZenMode
    // is a full-canvas replacement and renders no footer chrome of its
    // own. The route layer is responsible for hiding the root footer
    // when `mode === 'zen'`; here we assert ZenMode itself contributes
    // no `bottom-ribbon-placeholder` element.
    const { container } = render(
      <ZenMode caseId="case-001">
        <FakeEditor />
      </ZenMode>,
    );
    expect(container.querySelector('[data-testid="bottom-ribbon-placeholder"]')).toBeNull();
    // And no Epic 12.5 decision drawer either (when it lands it will
    // honour the same gate at the layout level).
    expect(container.querySelector('[data-testid="decision-drawer"]')).toBeNull();
  });

  it('Back to Investigation button switches mode (AC #6)', () => {
    useMode.getState().setMode('zen');
    render(
      <ZenMode caseId="case-001">
        <FakeEditor />
      </ZenMode>,
    );
    const back = screen.getByTestId('zen-back-to-investigation');
    back.click();
    expect(useMode.getState().mode).toBe('investigation');
  });
});

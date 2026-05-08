import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { CollapsiblePanel } from './CollapsiblePanel';

describe('CollapsiblePanel', () => {
  it('renders header with title and summary', () => {
    render(
      <CollapsiblePanel title="UBO" summary="6 nodes" expanded={false} onToggle={() => {}}>
        <div>body</div>
      </CollapsiblePanel>,
    );
    expect(screen.getByText('UBO')).toBeInTheDocument();
    expect(screen.getByText('6 nodes')).toBeInTheDocument();
  });

  it('aria-expanded reflects state', () => {
    const { rerender } = render(
      <CollapsiblePanel title="UBO" summary="—" expanded={false} onToggle={() => {}}>
        <div>body</div>
      </CollapsiblePanel>,
    );
    const header = screen.getByTestId('collapsible-panel-header-ubo');
    expect(header).toHaveAttribute('aria-expanded', 'false');
    rerender(
      <CollapsiblePanel title="UBO" summary="—" expanded={true} onToggle={() => {}}>
        <div>body</div>
      </CollapsiblePanel>,
    );
    expect(header).toHaveAttribute('aria-expanded', 'true');
  });

  it('clicking header invokes onToggle with the new state', () => {
    const onToggle = vi.fn();
    render(
      <CollapsiblePanel title="UBO" summary="—" expanded={false} onToggle={onToggle}>
        <div>body</div>
      </CollapsiblePanel>,
    );
    fireEvent.click(screen.getByTestId('collapsible-panel-header-ubo'));
    expect(onToggle).toHaveBeenCalledWith(true);
  });

  it('Space key toggles', () => {
    const onToggle = vi.fn();
    render(
      <CollapsiblePanel title="UBO" summary="—" expanded={false} onToggle={onToggle}>
        <div>body</div>
      </CollapsiblePanel>,
    );
    fireEvent.keyDown(screen.getByTestId('collapsible-panel-header-ubo'), { key: ' ' });
    expect(onToggle).toHaveBeenCalledWith(true);
  });

  it('Enter key toggles', () => {
    const onToggle = vi.fn();
    render(
      <CollapsiblePanel title="UBO" summary="—" expanded={true} onToggle={onToggle}>
        <div>body</div>
      </CollapsiblePanel>,
    );
    fireEvent.keyDown(screen.getByTestId('collapsible-panel-header-ubo'), { key: 'Enter' });
    expect(onToggle).toHaveBeenCalledWith(false);
  });

  it('renders body when expanded', () => {
    render(
      <CollapsiblePanel title="UBO" summary="—" expanded={true} onToggle={() => {}}>
        <div>panel-body-content</div>
      </CollapsiblePanel>,
    );
    expect(screen.getByText('panel-body-content')).toBeInTheDocument();
  });

  it('applies the attention tonal class when tone="attention"', () => {
    render(
      <CollapsiblePanel
        title="Screening"
        summary="—"
        expanded={false}
        onToggle={() => {}}
        tone="attention"
      >
        <div>body</div>
      </CollapsiblePanel>,
    );
    const header = screen.getByTestId('collapsible-panel-header-screening');
    const section = header.closest('section');
    expect(section).toHaveAttribute('data-tone', 'attention');
    expect(section).toHaveClass('border-amber-200');
  });

  it('uses the default tonal class when tone is omitted', () => {
    render(
      <CollapsiblePanel title="UBO" summary="—" expanded={false} onToggle={() => {}}>
        <div>body</div>
      </CollapsiblePanel>,
    );
    const header = screen.getByTestId('collapsible-panel-header-ubo');
    const section = header.closest('section');
    expect(section).toHaveAttribute('data-tone', 'default');
    expect(section).toHaveClass('border-zinc-200');
  });

  it('does not render body initially when collapsed', () => {
    render(
      <CollapsiblePanel title="UBO" summary="—" expanded={false} onToggle={() => {}}>
        <div>panel-body-content</div>
      </CollapsiblePanel>,
    );
    expect(screen.queryByText('panel-body-content')).not.toBeInTheDocument();
  });
});

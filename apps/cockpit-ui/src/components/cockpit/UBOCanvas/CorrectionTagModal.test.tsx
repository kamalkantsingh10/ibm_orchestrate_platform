// CorrectionTagModal — Story 5.5 / AC #11.

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { CorrectionTagModal } from './CorrectionTagModal';
import type { UBOEdge } from './adapter';

const FAKE_PROVENANCE = {
  source_agent: 'ubo_graph',
  source_system: 'mca_mock',
  confidence: 0.55,
  confidence_band: 'medium_low',
  evidence_ids: [],
  captured_at: '2026-05-08T00:00:00Z',
} as UBOEdge['confidence']['provenance'];

function makeEdge(kind: 'owns' | 'director' = 'owns'): UBOEdge {
  return {
    kind,
    from_id: 'ubo_e_coastal_equity_partners_pte_ltd',
    to_id: 'ubo_e_u67120mh2024ptc444789',
    ownership_pct: kind === 'owns' ? 70 : null,
    designation: kind === 'director' ? 'director' : null,
    confidence: { value: 0.55, provenance: FAKE_PROVENANCE },
    nominee_flag: 'nominee_suspected',
    rationale: 'Test',
  };
}

describe('CorrectionTagModal', () => {
  it('renders all four tag options as radio buttons', () => {
    render(
      <CorrectionTagModal
        open
        onOpenChange={vi.fn()}
        edge={makeEdge()}
        newTargetId="ubo_e_u67120mh2024ptc444789"
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByTestId('tag-radio-real_ubo')).toBeInTheDocument();
    expect(screen.getByTestId('tag-radio-nominee')).toBeInTheDocument();
    expect(screen.getByTestId('tag-radio-director')).toBeInTheDocument();
    expect(screen.getByTestId('tag-radio-removed')).toBeInTheDocument();
  });

  it('disables the director radio when edge.kind != "director"', () => {
    render(
      <CorrectionTagModal
        open
        onOpenChange={vi.fn()}
        edge={makeEdge('owns')}
        newTargetId="ubo_e_u67120mh2024ptc444789"
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByTestId('tag-radio-director')).toBeDisabled();
    expect(screen.getByTestId('tag-radio-real_ubo')).not.toBeDisabled();
  });

  it('enables the director radio when edge.kind == "director"', () => {
    render(
      <CorrectionTagModal
        open
        onOpenChange={vi.fn()}
        edge={makeEdge('director')}
        newTargetId="ubo_e_u67120mh2024ptc444789"
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByTestId('tag-radio-director')).not.toBeDisabled();
  });

  it('disables Confirm until both tag and evidence note are populated', () => {
    render(
      <CorrectionTagModal
        open
        onOpenChange={vi.fn()}
        edge={makeEdge()}
        newTargetId="ubo_e_u67120mh2024ptc444789"
        onConfirm={vi.fn()}
      />,
    );
    const confirm = screen.getByTestId('confirm-button');
    expect(confirm).toBeDisabled();

    fireEvent.click(screen.getByTestId('tag-radio-real_ubo'));
    expect(confirm).toBeDisabled(); // evidence note still empty

    fireEvent.change(screen.getByTestId('evidence-note-textarea'), {
      target: { value: 'RM email 2024-11' },
    });
    expect(confirm).not.toBeDisabled();
  });

  it('calls onConfirm with the captured tag, note, and opt-in flag', () => {
    const onConfirm = vi.fn();
    render(
      <CorrectionTagModal
        open
        onOpenChange={vi.fn()}
        edge={makeEdge()}
        newTargetId="ubo_e_u67120mh2024ptc444789"
        onConfirm={onConfirm}
      />,
    );
    fireEvent.click(screen.getByTestId('tag-radio-real_ubo'));
    fireEvent.change(screen.getByTestId('evidence-note-textarea'), {
      target: { value: 'RM email 2024-11 disclosed offshore family trust' },
    });
    fireEvent.click(screen.getByTestId('opt-in-checkbox'));
    fireEvent.click(screen.getByTestId('confirm-button'));
    expect(onConfirm).toHaveBeenCalledWith(
      'real_ubo',
      'RM email 2024-11 disclosed offshore family trust',
      true,
    );
  });

  it('Cancel button invokes onOpenChange(false)', () => {
    const onOpenChange = vi.fn();
    render(
      <CorrectionTagModal
        open
        onOpenChange={onOpenChange}
        edge={makeEdge()}
        newTargetId="ubo_e_u67120mh2024ptc444789"
        onConfirm={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByText('Cancel'));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('applies destructive style when "Remove" tag is selected', () => {
    render(
      <CorrectionTagModal
        open
        onOpenChange={vi.fn()}
        edge={makeEdge()}
        newTargetId="ubo_e_u67120mh2024ptc444789"
        onConfirm={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId('tag-radio-removed'));
    fireEvent.change(screen.getByTestId('evidence-note-textarea'), {
      target: { value: 'no relationship exists' },
    });
    const confirm = screen.getByTestId('confirm-button');
    // Destructive class signature
    expect(confirm.className).toMatch(/bg-rose-600/);
  });
});

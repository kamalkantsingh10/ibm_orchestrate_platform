// DocumentsPanel — Story 3.6 AC #8.

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { components } from '@/api-types';
import { DocumentsPanel } from './DocumentsPanel';

type Output = components['schemas']['DocumentIntelligenceOutput'];
type ExtractedField = components['schemas']['ExtractedField'];

function makeField(
  field_name: string,
  document_ref: string,
  value: string,
  confidence = 0.92,
): ExtractedField {
  return {
    field_name,
    document_ref,
    value: {
      value,
      provenance: {
        source_agent: 'document_intelligence',
        source_system: 'fixture_doc_ai',
        confidence,
        confidence_band:
          confidence >= 0.85
            ? 'high'
            : confidence >= 0.65
              ? 'medium_high'
              : confidence >= 0.4
                ? 'medium_low'
                : 'low',
        evidence_ids: ['led_01HZZZZZZZZZZZZZZZZZZZZZZZ'],
        captured_at: '2026-04-30T12:00:00Z',
      },
    },
  };
}

const VORA = 'case_01KQC7GQ70GYHP15CZ8JB5ZT6A';

describe('DocumentsPanel', () => {
  it('renders empty state when output is null', () => {
    render(<DocumentsPanel output={null} />);
    expect(screen.getByText(/intake has not yet run/i)).toBeTruthy();
  });

  it('renders skeleton when pending and no output', () => {
    const { container } = render(<DocumentsPanel output={null} isPending />);
    expect(container.querySelector('[data-testid="documents-panel-skeleton"]')).toBeTruthy();
  });

  it('renders error state when isError', () => {
    render(<DocumentsPanel output={null} isError />);
    expect(screen.getByRole('alert').textContent).toContain('Could not load');
  });

  it('renders 5 fields across 2 documents grouped by document_ref', () => {
    const output: Output = {
      case_id: VORA,
      extracted_fields: [
        makeField('company_name', 'incorp.pdf', 'Vora'),
        makeField('cin', 'incorp.pdf', 'U67120MH'),
        makeField('incorporation_date', 'incorp.pdf', '2024-08-22'),
        makeField('pan', 'pan.pdf', 'AAFCV1234R'),
        makeField('name', 'pan.pdf', 'Vora'),
      ],
    };
    render(<DocumentsPanel output={output} />);
    // Verify both document headers visible
    expect(screen.getByText('incorp.pdf')).toBeTruthy();
    expect(screen.getByText('pan.pdf')).toBeTruthy();
    // Verify the field-count summary
    expect(screen.getByText(/5 fields extracted/)).toBeTruthy();
    // Each field is humanized
    expect(screen.getByText('Company name')).toBeTruthy();
    expect(screen.getByText('CIN')).toBeTruthy();
  });

  it('NFR-T4 coverage: every field row has a provenance indicator', () => {
    const output: Output = {
      case_id: VORA,
      extracted_fields: [
        makeField('a', 'x.pdf', 'A'),
        makeField('b', 'x.pdf', 'B'),
        makeField('c', 'y.pdf', 'C'),
      ],
    };
    render(<DocumentsPanel output={output} />);
    // Each provenance indicator is either a group (non-interactive) or a
    // button (interactive). Use confidence pill aria-label as the proxy.
    const pills = screen.getAllByLabelText(/confidence:/i);
    // Three pills (one per field).
    expect(pills.length).toBe(3);
  });

  it('click on a provenance pill calls onProvenanceClick with the field', () => {
    const handler = vi.fn();
    const fields: ExtractedField[] = [makeField('cin', 'incorp.pdf', 'U67120MH')];
    const output: Output = { case_id: VORA, extracted_fields: fields };
    render(<DocumentsPanel output={output} onProvenanceClick={handler} />);
    const button = screen.getByRole('button', { name: /field provenance/i });
    fireEvent.click(button);
    expect(handler).toHaveBeenCalledWith(fields[0]);
  });

  it('renders empty-fields state when intake ran but extracted nothing', () => {
    render(<DocumentsPanel output={{ case_id: VORA, extracted_fields: [] }} />);
    expect(screen.getByText(/no fields were extracted/i)).toBeTruthy();
  });
});

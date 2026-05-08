// EvidenceShelf tests — Story 7.8 / AC #8.

import type { ReactNode } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const { useDocumentIntelligenceMock } = vi.hoisted(() => ({
  useDocumentIntelligenceMock: vi.fn(),
}));

vi.mock('@/hooks/useDocumentIntelligence', () => ({
  useDocumentIntelligence: useDocumentIntelligenceMock,
}));

import { EvidenceShelf } from './EvidenceShelf';

const CASE_ID = 'case_01HZ7ZK4G7EXAMPLE0000000DD';

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

function _field(name: string, doc: string, confidence: number, value: string = 'x') {
  return {
    field_name: name,
    document_ref: doc,
    value: {
      value,
      provenance: {
        source_agent: 'document_intelligence',
        source_system: 'fixture_doc_ai',
        confidence,
        confidence_band:
          confidence >= 0.85 ? 'high' : confidence >= 0.65 ? 'medium_high' : 'medium_low',
        evidence_ids: [],
        captured_at: '2026-05-08T00:00:00Z',
      },
    },
  };
}

beforeEach(() => {
  useDocumentIntelligenceMock.mockReset();
  useDocumentIntelligenceMock.mockReturnValue({
    data: null,
    isPending: false,
    isError: false,
    isSuccess: true,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('EvidenceShelf', () => {
  it('renders nothing visible when open=false', () => {
    const { queryByTestId } = render(
      <EvidenceShelf caseId={CASE_ID} open={false} onOpenChange={() => {}} />,
      { wrapper: makeWrapper() },
    );
    expect(queryByTestId('evidence-shelf')).toBeNull();
  });

  it('shows the empty state when no fields are extracted', () => {
    useDocumentIntelligenceMock.mockReturnValue({
      data: { case_id: CASE_ID, extracted_fields: [] },
      isPending: false,
      isError: false,
      isSuccess: true,
    });
    render(<EvidenceShelf caseId={CASE_ID} open={true} onOpenChange={() => {}} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.getByText('No documents on this case.')).toBeInTheDocument();
  });

  it('shows the loading skeleton when isPending', () => {
    useDocumentIntelligenceMock.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      isSuccess: false,
    });
    render(<EvidenceShelf caseId={CASE_ID} open={true} onOpenChange={() => {}} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.getByTestId('evidence-shelf-skeleton')).toBeInTheDocument();
  });

  it('renders one section per document', () => {
    useDocumentIntelligenceMock.mockReturnValue({
      data: {
        case_id: CASE_ID,
        extracted_fields: [
          _field('cin', 'incorporation_certificate.pdf', 0.95),
          _field('pan', 'pan_card.pdf', 0.92),
        ],
      },
      isPending: false,
      isError: false,
      isSuccess: true,
    });
    render(<EvidenceShelf caseId={CASE_ID} open={true} onOpenChange={() => {}} />, {
      wrapper: makeWrapper(),
    });
    const sections = screen.getAllByTestId('evidence-shelf-doc-section');
    expect(sections).toHaveLength(2);
    expect(screen.getByText('incorporation_certificate.pdf')).toBeInTheDocument();
    expect(screen.getByText('pan_card.pdf')).toBeInTheDocument();
  });

  it('shows top-3 fields by confidence per document', () => {
    useDocumentIntelligenceMock.mockReturnValue({
      data: {
        case_id: CASE_ID,
        extracted_fields: [
          _field('field_low', 'd.pdf', 0.4, 'low'),
          _field('field_high', 'd.pdf', 0.95, 'high'),
          _field('field_mid_high', 'd.pdf', 0.7, 'mid'),
          _field('field_lowest', 'd.pdf', 0.2, 'lowest'),
        ],
      },
      isPending: false,
      isError: false,
      isSuccess: true,
    });
    render(<EvidenceShelf caseId={CASE_ID} open={true} onOpenChange={() => {}} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.getByText('field_high')).toBeInTheDocument();
    expect(screen.getByText('field_mid_high')).toBeInTheDocument();
    expect(screen.getByText('field_low')).toBeInTheDocument();
    // Lowest excluded — only top 3.
    expect(screen.queryByText('field_lowest')).toBeNull();
  });

  it('Esc closes the shelf', () => {
    const onOpenChange = vi.fn();
    useDocumentIntelligenceMock.mockReturnValue({
      data: { case_id: CASE_ID, extracted_fields: [_field('x', 'd.pdf', 0.9)] },
      isPending: false,
      isError: false,
      isSuccess: true,
    });
    render(<EvidenceShelf caseId={CASE_ID} open={true} onOpenChange={onOpenChange} />, {
      wrapper: makeWrapper(),
    });
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('clicking the close button fires onOpenChange(false)', () => {
    const onOpenChange = vi.fn();
    useDocumentIntelligenceMock.mockReturnValue({
      data: { case_id: CASE_ID, extracted_fields: [_field('x', 'd.pdf', 0.9)] },
      isPending: false,
      isError: false,
      isSuccess: true,
    });
    render(<EvidenceShelf caseId={CASE_ID} open={true} onOpenChange={onOpenChange} />, {
      wrapper: makeWrapper(),
    });
    fireEvent.click(screen.getByLabelText('Close evidence shelf'));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('renders motion-reduce:transition-none on overlay + content', () => {
    useDocumentIntelligenceMock.mockReturnValue({
      data: { case_id: CASE_ID, extracted_fields: [_field('x', 'd.pdf', 0.9)] },
      isPending: false,
      isError: false,
      isSuccess: true,
    });
    render(<EvidenceShelf caseId={CASE_ID} open={true} onOpenChange={() => {}} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.getByTestId('evidence-shelf').className).toMatch(/motion-reduce:transition-none/);
    expect(screen.getByTestId('evidence-shelf-overlay').className).toMatch(
      /motion-reduce:transition-none/,
    );
  });

  it('shows field count subtitle per document', () => {
    useDocumentIntelligenceMock.mockReturnValue({
      data: {
        case_id: CASE_ID,
        extracted_fields: [
          _field('a', 'd.pdf', 0.9),
          _field('b', 'd.pdf', 0.8),
          _field('c', 'd.pdf', 0.7),
          _field('d', 'd.pdf', 0.6),
        ],
      },
      isPending: false,
      isError: false,
      isSuccess: true,
    });
    render(<EvidenceShelf caseId={CASE_ID} open={true} onOpenChange={() => {}} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.getByText('4 fields extracted')).toBeInTheDocument();
  });
});

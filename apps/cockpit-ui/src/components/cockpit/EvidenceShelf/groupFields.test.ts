// groupFields tests — Story 7.8 / AC #9.

import { describe, expect, it } from 'vitest';
import type { components } from '@/api-types';
import { groupByDocument, topByConfidence, uniqueDocumentCount } from './groupFields';

type ExtractedField = components['schemas']['ExtractedField'];

function _field(name: string, doc: string, confidence: number): ExtractedField {
  return {
    field_name: name,
    document_ref: doc,
    value: {
      value: 'x',
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
  } as ExtractedField;
}

describe('groupByDocument', () => {
  it('returns an empty map for empty input', () => {
    expect(groupByDocument([])).toEqual(new Map());
  });

  it('groups fields by document_ref preserving insertion order', () => {
    const fields = [
      _field('cin', 'incorporation_certificate.pdf', 0.95),
      _field('pan', 'pan_card.pdf', 0.92),
      _field('company_name', 'incorporation_certificate.pdf', 0.85),
    ];
    const grouped = groupByDocument(fields);
    expect(grouped.size).toBe(2);
    expect(grouped.get('incorporation_certificate.pdf')!.map((f) => f.field_name)).toEqual([
      'cin',
      'company_name',
    ]);
    expect(grouped.get('pan_card.pdf')!.map((f) => f.field_name)).toEqual(['pan']);
  });
});

describe('topByConfidence', () => {
  it('returns top n by descending confidence', () => {
    const fields = [
      _field('a', 'doc.pdf', 0.5),
      _field('b', 'doc.pdf', 0.95),
      _field('c', 'doc.pdf', 0.7),
    ];
    expect(topByConfidence(fields, 2).map((f) => f.field_name)).toEqual(['b', 'c']);
  });

  it('returns empty array for n=0', () => {
    expect(topByConfidence([_field('a', 'd.pdf', 0.9)], 0)).toEqual([]);
  });

  it('returns all fields when n exceeds list length', () => {
    const fields = [_field('a', 'd.pdf', 0.5), _field('b', 'd.pdf', 0.6)];
    expect(topByConfidence(fields, 5)).toHaveLength(2);
  });
});

describe('uniqueDocumentCount', () => {
  it('counts distinct document refs', () => {
    const fields = [
      _field('a', 'doc1.pdf', 0.9),
      _field('b', 'doc1.pdf', 0.8),
      _field('c', 'doc2.pdf', 0.7),
    ];
    expect(uniqueDocumentCount(fields)).toBe(2);
  });

  it('returns 0 for empty input', () => {
    expect(uniqueDocumentCount([])).toBe(0);
  });
});

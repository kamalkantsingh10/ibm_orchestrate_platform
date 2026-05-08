// EvidenceShelf field-grouping helpers — Story 7.8 / AC #4.
//
// Pure functions used by the EvidenceShelf to project the flat list
// of `ExtractedField` into per-document sections sorted by confidence.

import type { components } from '@/api-types';

export type ExtractedField = components['schemas']['ExtractedField'];

export function groupByDocument(fields: ExtractedField[]): Map<string, ExtractedField[]> {
  const out = new Map<string, ExtractedField[]>();
  for (const f of fields) {
    const list = out.get(f.document_ref) ?? [];
    list.push(f);
    out.set(f.document_ref, list);
  }
  return out;
}

export function topByConfidence(fields: ExtractedField[], n = 3): ExtractedField[] {
  if (n <= 0) return [];
  return [...fields]
    .sort((a, b) => b.value.provenance.confidence - a.value.provenance.confidence)
    .slice(0, n);
}

export function uniqueDocumentCount(fields: ExtractedField[]): number {
  return new Set(fields.map((f) => f.document_ref)).size;
}

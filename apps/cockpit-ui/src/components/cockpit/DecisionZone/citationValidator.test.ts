// citationValidator tests — Story 7.1 / AC #14.

import { describe, expect, it } from 'vitest';
import { findBrokenCitations, findCitations } from './citationValidator';

const A = 'led_01ABCDEFGHJKMNPQRSTVWXYZ12';
const B = 'led_01HXY3GHJKMNPQRSTVWXYZ7HX2';
const NOT_IN_LEDGER = 'led_01ZZZZZZZZZZZZZZZZZZZZZ7HX';

describe('findCitations', () => {
  it('returns every led_<ULID> that appears as a data-ledger-id attribute', () => {
    const html = `<p>Approve based on <span data-ledger-id="${A}" class="citation-token">screening hit</span> and <span data-ledger-id="${B}" class="citation-token">UBO graph</span>.</p>`;
    expect(findCitations(html)).toEqual([A, B]);
  });

  it('returns an empty array when there are no citation marks', () => {
    expect(findCitations('<p>plain rationale, no citations</p>')).toEqual([]);
  });

  it('does not match malformed ledger ids (wrong length, lowercase ulid)', () => {
    const html =
      '<span data-ledger-id="led_01TOOSHORT">x</span><span data-ledger-id="led_lowercase00000000000000000">y</span>';
    expect(findCitations(html)).toEqual([]);
  });
});

describe('findBrokenCitations', () => {
  it('filters citations that are not in the ledger set', () => {
    const html = `<span data-ledger-id="${A}">a</span><span data-ledger-id="${NOT_IN_LEDGER}">b</span>`;
    expect(findBrokenCitations(html, new Set([A]))).toEqual([NOT_IN_LEDGER]);
  });

  it('returns an empty array when every citation resolves', () => {
    const html = `<span data-ledger-id="${A}">a</span><span data-ledger-id="${B}">b</span>`;
    expect(findBrokenCitations(html, new Set([A, B]))).toEqual([]);
  });

  it('returns an empty array when the rationale has no citations at all', () => {
    expect(findBrokenCitations('<p>none here</p>', new Set([A]))).toEqual([]);
  });
});

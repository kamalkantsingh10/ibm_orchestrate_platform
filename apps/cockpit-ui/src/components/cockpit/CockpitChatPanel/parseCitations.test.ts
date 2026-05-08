// parseCitations tests — Story 6.8 / AC #5.

import { describe, expect, it } from 'vitest';
import { parseCitations } from './parseCitations';

describe('parseCitations', () => {
  it('returns a single text segment when no citations are present', () => {
    expect(parseCitations('hello world')).toEqual([{ kind: 'text', text: 'hello world' }]);
  });

  it('returns a single citation segment when the input is a citation', () => {
    expect(parseCitations('led_01ABCDEFGHJKMNPQRSTVWXYZ12')).toEqual([
      { kind: 'citation', ledgerId: 'led_01ABCDEFGHJKMNPQRSTVWXYZ12' },
    ]);
  });

  it('interleaves text and citations correctly', () => {
    const segments = parseCitations(
      'Screening returned 1 hit (led_01ABCDEFGHJKMNPQRSTVWXYZ12) at 73%.',
    );
    expect(segments).toEqual([
      { kind: 'text', text: 'Screening returned 1 hit (' },
      { kind: 'citation', ledgerId: 'led_01ABCDEFGHJKMNPQRSTVWXYZ12' },
      { kind: 'text', text: ') at 73%.' },
    ]);
  });

  it('handles multiple citations in one string', () => {
    const segments = parseCitations(
      'See led_01ABCDEFGHJKMNPQRSTVWXYZ12 and led_23BCDEFGHJKMNPQRSTVWXYZ234.',
    );
    const citations = segments.filter((s) => s.kind === 'citation');
    expect(citations).toHaveLength(2);
  });

  it('does NOT match invalid prefixes (case-sensitive)', () => {
    expect(parseCitations('Led_01ABCDEFGHJKMNPQRSTVWXYZ12')).toEqual([
      { kind: 'text', text: 'Led_01ABCDEFGHJKMNPQRSTVWXYZ12' },
    ]);
  });

  it('does NOT match truncated IDs', () => {
    expect(parseCitations('led_01HXY3')).toEqual([{ kind: 'text', text: 'led_01HXY3' }]);
  });
});

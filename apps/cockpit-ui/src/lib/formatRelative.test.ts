// Tests for formatRelative — Story 2.3 / AC #10.

import { describe, expect, it } from 'vitest';
import { formatRelative } from './formatRelative';

const NOW = new Date('2026-04-30T12:00:00Z');

describe('formatRelative', () => {
  it.each([
    ['just now (10s ago)', new Date('2026-04-30T11:59:50Z'), 'just now'],
    ['just now (clock skew, 30s in future)', new Date('2026-04-30T12:00:30Z'), 'just now'],
    ['1 minute ago', new Date('2026-04-30T11:59:00Z'), '1 minute ago'],
    ['5 minutes ago', new Date('2026-04-30T11:55:00Z'), '5 minutes ago'],
    ['59 minutes ago', new Date('2026-04-30T11:01:00Z'), '59 minutes ago'],
    ['1 hour ago', new Date('2026-04-30T11:00:00Z'), '1 hour ago'],
    ['3 hours ago', new Date('2026-04-30T09:00:00Z'), '3 hours ago'],
    ['short month + day for older dates', new Date('2026-04-28T08:00:00Z'), 'Apr 28'],
  ])('%s', (_label, input, expected) => {
    expect(formatRelative(input, NOW)).toBe(expected);
  });

  it('accepts ISO 8601 strings', () => {
    expect(formatRelative('2026-04-30T11:55:00Z', NOW)).toBe('5 minutes ago');
  });
});

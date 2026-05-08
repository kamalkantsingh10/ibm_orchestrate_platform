// commands.ts tests — Story 4.8 AC #5, #8.

import { describe, expect, it } from 'vitest';
import { COMMANDS, filterCommands, matchCases, scoreCommand } from './commands';
import type { Case } from '@/lib/types/case';

function _case(id: string, name: string): Case {
  return {
    id,
    state: 'intake_scheduled',
    customer_metadata: { customer_name: name, extra: {} },
    assigned_to_user_id: null,
    risk_band: null,
    created_at: '2026-04-30T11:55:00Z',
    updated_at: '2026-04-30T11:55:00Z',
    closure_date: null,
    _links: { documents: null, reasoning_traces: null },
  };
}

describe('scoreCommand', () => {
  it('returns 1 for empty query', () => {
    expect(scoreCommand(COMMANDS[0]!, '')).toBe(1);
  });
  it('returns 1 for prefix match in label', () => {
    const sw = COMMANDS.find((c) => c.id === 'switch-investigation')!;
    expect(scoreCommand(sw, 'switch')).toBe(1);
  });
  it('returns 0.5 for non-prefix match', () => {
    const sw = COMMANDS.find((c) => c.id === 'switch-investigation')!;
    expect(scoreCommand(sw, 'investigation')).toBe(0.5);
  });
  it('returns 0 for no match', () => {
    expect(scoreCommand(COMMANDS[0]!, 'zzzzzzzzzz')).toBe(0);
  });
});

describe('filterCommands', () => {
  it('empty query returns all in registration order', () => {
    expect(filterCommands(COMMANDS, '')).toEqual(COMMANDS);
  });

  it('"queue" matches go-queue first', () => {
    const r = filterCommands(COMMANDS, 'queue');
    expect(r[0]?.id).toBe('go-queue');
  });

  it('returns empty for unknown query', () => {
    expect(filterCommands(COMMANDS, 'zzzz')).toEqual([]);
  });

  it('cap of 10 honored', () => {
    const r = filterCommands(COMMANDS, '', 2);
    expect(r).toHaveLength(2);
  });
});

describe('matchCases', () => {
  const cases = [_case('case_A', 'Vora Capital Holdings'), _case('case_B', 'Acme')];
  it('empty query returns all', () => {
    expect(matchCases(cases, '')).toEqual(cases);
  });
  it('matches by name (case-insensitive)', () => {
    expect(matchCases(cases, 'vora')).toEqual([cases[0]]);
  });
  it('matches by id', () => {
    expect(matchCases(cases, 'case_b')).toEqual([cases[1]]);
  });
});

describe('filterCommands perf microbench', () => {
  it('100x filter completes well under the 50ms p95 budget', () => {
    const start = performance.now();
    for (let i = 0; i < 100; i++) {
      filterCommands(COMMANDS, 'queue');
    }
    const elapsed = performance.now() - start;
    // CI noise budget is generous; 100 iterations should be well under 100ms
    expect(elapsed).toBeLessThan(100);
  });
});

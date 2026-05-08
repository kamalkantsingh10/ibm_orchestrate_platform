// agentLabels tests — Story 4.3 AC #6.

import { describe, expect, it } from 'vitest';
import { AGENT_LABELS, AGENT_ORDER, type AgentSlug } from './agentLabels';

describe('agentLabels', () => {
  it('has eight slugs', () => {
    expect(Object.keys(AGENT_LABELS)).toHaveLength(8);
    expect(AGENT_ORDER).toHaveLength(8);
  });

  it('AGENT_ORDER covers every label key', () => {
    const labelKeys = new Set(Object.keys(AGENT_LABELS) as AgentSlug[]);
    const orderKeys = new Set(AGENT_ORDER);
    expect(orderKeys).toEqual(labelKeys);
  });

  it('every slug has a non-empty label', () => {
    for (const slug of AGENT_ORDER) {
      expect(AGENT_LABELS[slug].length).toBeGreaterThan(0);
    }
  });

  it('Case Supervisor is first in canonical order', () => {
    expect(AGENT_ORDER[0]).toBe('case-supervisor');
  });
});

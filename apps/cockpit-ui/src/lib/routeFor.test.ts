// Unit test for defaultRouteFor (Story 1.4 AC #5).

import { describe, expect, it } from 'vitest';
import { defaultRouteFor } from './routeFor';

describe('defaultRouteFor', () => {
  it('maps analyst → /queue', () => {
    expect(defaultRouteFor('analyst')).toBe('/queue');
  });

  it('maps team_lead → /approvals', () => {
    expect(defaultRouteFor('team_lead')).toBe('/approvals');
  });

  it('maps regulator → /regulator-lens', () => {
    expect(defaultRouteFor('regulator')).toBe('/regulator-lens');
  });
});

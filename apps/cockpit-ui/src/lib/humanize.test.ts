import { describe, expect, it } from 'vitest';
import { humanizeFieldName } from './humanize';

describe('humanizeFieldName', () => {
  it.each([
    ['company_name', 'Company name'],
    ['cin', 'CIN'],
    ['registered_address', 'Registered address'],
    ['annual_income_inr', 'Annual income INR'],
    ['pan', 'PAN'],
    ['gstin', 'GSTIN'],
    ['din', 'DIN'],
    ['ubo_chain', 'UBO chain'],
    ['account_holder_name', 'Account holder name'],
    ['', ''],
  ])('humanizes %s to %s', (input, expected) => {
    expect(humanizeFieldName(input)).toBe(expected);
  });
});
